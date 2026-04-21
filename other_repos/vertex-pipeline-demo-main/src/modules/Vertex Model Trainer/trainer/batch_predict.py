"""Vertex AI Batch Prediction helper for the ss-models pipeline.

After the model is trained and registered in the Vertex AI Model Registry this
module triggers a BigQuery-to-BigQuery batch prediction job using the **same
test split that was used during evaluation**.

Why use X_test instead of a separate BQ table
----------------------------------------------
* X_test already has the selected features in the correct order.
* The target column and ID column are never accidentally sent to the model.
* The final output table includes the actual labels (y_test) alongside the
  model's predictions so results can be compared directly.

Flow
----
1. Build a "test + actuals" DataFrame from X_test (features) + y_test (labels).
   The ID is restored from the DataFrame index; the actual outcome is added as
   ``actual_<outcome_var>``.
2. Upload this DataFrame to a **temp input table** in the compute project.
3. Submit a Vertex AI batch prediction job via the REST API.
   ``excludedFields`` tells Vertex AI to keep the ID and actual-outcome columns
   in the output rows without sending them to the model – the model only sees
   the feature columns.
4. Wait for the job to finish using the Python SDK.
5. Copy the predictions temp table (features + id + actuals + prediction) to
   the final ``output_table`` in the shared project.
6. Clean up both temp tables.

The final output table has:
    <indexing_var>            – member / row identifier
    <feature_col_1> …         – the selected feature columns
    actual_<outcome_var>      – true label from the test split
    prediction                – Vertex AI model output (probability for binary)

Public API
----------
``run_batch_prediction(config, model_resource_name, X_test, y_test)``
    Main entry point.  Returns the batch prediction job resource name, or an
    empty string if batch prediction is disabled or the model was not registered.
"""

import json
import requests
import pandas as pd
import pandas_gbq

from google.auth import default
from google.auth.transport.requests import Request
from google.cloud import aiplatform, bigquery


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_batch_prediction(
    config: dict,
    model_resource_name: str,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> str:
    """Trigger a BigQuery batch prediction job on the training test split.

    Args:
        config:              Full training config dict (from ``create_config_from_args``).
        model_resource_name: Full Vertex AI model resource name returned by the
                             Model Registry step, e.g.
                             ``projects/123/locations/us-east4/models/456``.
                             Pass an empty string to skip.
        X_test:              Test-split feature DataFrame (selected features only,
                             indexing_var as the DataFrame index, no target column).
        y_test:              Test-split target Series aligned with X_test.

    Returns:
        The batch prediction job resource name, or ``''`` if skipped.
    """
    bp_cfg = config.get('batch_prediction') or {}

    if not bp_cfg.get('enable', False):
        print("\n── Batch Prediction: skipped (set batch_prediction.enable: true to run) ──")
        return ''

    if not model_resource_name:
        print("\n── Batch Prediction: skipped (model was not registered in Model Registry) ──")
        return ''

    output_table    = bp_cfg.get('output_table', '').strip()
    compute_dataset = bp_cfg.get('compute_dataset', '').strip()

    if not (output_table and compute_dataset):
        raise ValueError(
            "batch_prediction.output_table and compute_dataset "
            "must both be set in config when batch_prediction.enable is true."
        )

    gcp           = config['gcp']
    project       = gcp['project']
    location      = config['model_registry'].get('location', 'us-east4')
    cmek_key      = config['model_registry'].get('cmek_key', '') or None
    svc_account   = (
        config['model_registry'].get('service_account', '')
        or config['vertex_ai'].get('service_account', '')
        or ''
    )
    indexing_var  = X_test.index.name   # already set from the training pipeline
    outcome_var   = config['data_processing']['outcome_var']
    bq_labels     = config.get('bigquery_labels', {})
    owner         = bq_labels.get('owner', '')
    cost_center   = str(bq_labels.get('costcenter', ''))

    expiration_days        = int(bp_cfg.get('expiration_days', 30))
    machine_type           = bp_cfg.get('machine_type', 'n2-standard-16')
    starting_replica_count = int(bp_cfg.get('starting_replica_count', 1))
    max_replica_count      = int(bp_cfg.get('max_replica_count', 1))
    batch_size             = bp_cfg.get('batch_size') or None

    print(f"\n── Step 17: Batch Prediction ──────────────────────────────────────")
    print(f"  Model           : {model_resource_name}")
    print(f"  Test rows       : {X_test.shape[0]:,}   |   Features: {X_test.shape[1]}")
    print(f"  Output table    : {output_table}")
    print(f"  Compute dataset : {compute_dataset}")

    job_name = _run_bq_batch_prediction(
        project                = project,
        location               = location,
        service_account        = svc_account,
        cmek_key               = cmek_key,
        cost_center            = cost_center,
        owner                  = owner,
        model_resource_name    = model_resource_name,
        X_test                 = X_test,
        y_test                 = y_test,
        outcome_var            = outcome_var,
        output_table           = output_table,
        compute_dataset        = compute_dataset,
        expiration_days        = expiration_days,
        machine_type           = machine_type,
        starting_replica_count = starting_replica_count,
        max_replica_count      = max_replica_count,
        batch_size             = batch_size,
    )

    print(f"\n  ✅ Batch prediction complete: {job_name}")
    return job_name


# ---------------------------------------------------------------------------
# Private implementation
# ---------------------------------------------------------------------------

def _run_bq_batch_prediction(
    project: str,
    location: str,
    service_account: str,
    cmek_key: str,
    cost_center: str,
    owner: str,
    model_resource_name: str,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    outcome_var: str,
    output_table: str,
    compute_dataset: str,
    expiration_days: int = 30,
    machine_type: str = 'n2-standard-16',
    starting_replica_count: int = 1,
    max_replica_count: int = 1,
    batch_size: int = None,
) -> str:
    """Core implementation: upload test split → batch predict → copy back → clean up.

    The input DataFrame is built from X_test (features, indexing_var as index)
    and y_test (actual labels).  The column ``actual_<outcome_var>`` and
    ``<indexing_var>`` are added to the batch prediction ``excludedFields`` so
    the model only receives feature values, while both columns are preserved in
    the output for result comparison.

    ``indexing_var`` is derived directly from ``X_test.index.name`` — no need
    to pass it explicitly.

    Returns:
        The batch prediction job resource name string.
    """
    bq_client  = bigquery.Client(project=project)
    labels_sql = f"""labels=[("owner","{owner}"),("costcenter","{cost_center}")]"""

    # ── Step 1: Build test-with-actuals DataFrame ──────────────────────────
    actual_col   = f"actual_{outcome_var}"
    indexing_var = X_test.index.name           # derived from the DataFrame index

    test_df = X_test.copy()
    test_df = test_df.reset_index()            # bring indexing_var in as a column
    test_df[actual_col] = y_test.values        # append actual labels

    feature_cols = list(X_test.columns)        # original feature columns only

    print(f"  Columns in input table : {indexing_var}, {actual_col}, "
          f"+ {len(feature_cols)} feature cols")

    # ── Step 2: Upload test DataFrame to temp input table in compute project ─
    model_parts      = model_resource_name.split('/')
    model_id         = model_parts[5] if len(model_parts) > 5 else 'model'
    temp_input_table = f"{project}.{compute_dataset}.{model_id}_test_input_tmp"
    temp_output_table = f"{project}.{compute_dataset}.{model_id}_test_output_tmp"

    print(f"  Uploading test data to : {temp_input_table}")
    pandas_gbq.to_gbq(
        test_df,
        destination_table=f"{compute_dataset}.{model_id}_test_input_tmp",
        project_id=project,
        if_exists='replace',
        progress_bar=False,
    )

    # ── Step 3: Submit batch prediction job via REST API ──────────────────
    # Exclude ID and actual-label columns so only feature values go to the
    # model.  Vertex AI preserves all source columns in the output rows.
    excluded_fields = [indexing_var, actual_col]

    credentials, _ = default()
    credentials.refresh(Request())
    access_token = credentials.token

    model_project  = model_parts[1]
    model_location = model_parts[3]

    job_display_name = f"{model_id}_test_batch_prediction"

    bp_request: dict = {
        'displayName': job_display_name,
        'model': model_resource_name,
        'inputConfig': {
            'instancesFormat': 'bigquery',
            'bigquerySource': {'inputUri': f'bq://{temp_input_table}'},
        },
        'outputConfig': {
            'predictionsFormat': 'bigquery',
            'bigqueryDestination': {'outputUri': f'bq://{temp_output_table}'},
        },
        'dedicatedResources': {
            'machineSpec': {'machineType': machine_type},
            'startingReplicaCount': starting_replica_count,
            'maxReplicaCount': max_replica_count,
        },
        'instanceConfig': {
            'excludedFields': excluded_fields,
        },
    }

    if cmek_key:
        bp_request['encryptionSpec'] = {'kmsKeyName': cmek_key}
    if service_account:
        bp_request['serviceAccount'] = service_account
    if batch_size:
        bp_request['manualBatchTuningParameters'] = {'batchSize': batch_size}

    print(f"\n  Batch prediction request:\n{json.dumps(bp_request, indent=4)}\n")

    url = (
        f"https://{model_location}-aiplatform.googleapis.com/v1beta1"
        f"/projects/{model_project}/locations/{model_location}/batchPredictionJobs"
    )
    response = requests.post(
        url,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json=bp_request,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Batch prediction job creation failed "
            f"({response.status_code}): {response.text}"
        )

    job_resource_name = response.json()['name']
    print(f"  Job created            : {job_resource_name}")

    # ── Step 4: Wait for completion via SDK ───────────────────────────────
    aiplatform.init(project=project, location=location)
    batch_job = aiplatform.BatchPredictionJob(job_resource_name)
    batch_job.wait_for_completion()
    print(f"  Job state              : {batch_job.state}")

    # ── Step 5: Copy predictions to final output table ────────────────────
    # Column order: indexing_var | actual_outcome | features | prediction
    feature_col_list = ', '.join(f'`{c}`' for c in feature_cols)
    print(f"  Copying predictions to : {output_table}")
    if expiration_days:
        opts = (
            f"{labels_sql}, "
            f"expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), "
            f"INTERVAL {expiration_days} DAY)"
        )
    else:
        opts = labels_sql

    _bq_run(bq_client, f"""
        CREATE OR REPLACE TABLE `{output_table}`
        OPTIONS({opts})
        AS
        SELECT
            `{indexing_var}`,
            `{actual_col}`,
            {feature_col_list},
            prediction
        FROM `{temp_output_table}`
    """)

    # ── Step 6: Clean up temp tables ──────────────────────────────────────
    bq_client.delete_table(temp_input_table,  not_found_ok=True)
    bq_client.delete_table(temp_output_table, not_found_ok=True)
    print("  Temp tables deleted.")

    return job_resource_name


def _bq_run(bq_client: bigquery.Client, query: str) -> None:
    """Execute a BigQuery statement and block until it completes."""
    job = bq_client.query(query)
    job.result()
