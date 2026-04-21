"""Common helper utilities shared across the ss-models pipeline."""
import re
import json
import pandas as pd
import numpy as np
from google.cloud import bigquery, storage


# ---------------------------------------------------------------------------
# Label distribution
# ---------------------------------------------------------------------------

def check_label_distribution(y) -> tuple:
    """Print and return label counts and the minority / majority ratio.

    Args:
        y: pandas Series or array-like with binary labels (0 / 1)

    Returns:
        tuple: (count_0, count_1, ratio_1_to_0)
    """
    count_0 = int((y == 0).sum())
    count_1 = int((y == 1).sum())
    ratio = count_1 / count_0 if count_0 != 0 else float('inf')
    print(f"  Label 0: {count_0:,}  |  Label 1: {count_1:,}  |  Ratio 1/0: {ratio:.6f}")
    return count_0, count_1, ratio


# ---------------------------------------------------------------------------
# Column name sanitisation
# ---------------------------------------------------------------------------

def sanitize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to be safe for XGBoost and BigQuery.

    Replaces dots and any non-alphanumeric characters with underscores,
    and prefixes columns that start with a digit with 'col_'.

    Args:
        df: DataFrame whose column names should be sanitised

    Returns:
        DataFrame with sanitised column names (in-place mutation + return)
    """
    new_cols = []
    for col in df.columns:
        col = col.replace('.', '_')
        col = re.sub(r'[^a-zA-Z0-9_]', '_', col)
        if col[0].isdigit():
            col = 'col_' + col
        new_cols.append(col)
    df.columns = new_cols
    return df


# ---------------------------------------------------------------------------
# GCS upload
# ---------------------------------------------------------------------------

def upload_to_gcs(local_path: str, bucket_name: str, gcs_path: str) -> None:
    """Upload a local file to Google Cloud Storage.

    Args:
        local_path: Local filesystem path
        bucket_name: GCS bucket name (without gs://)
        gcs_path: Destination object path inside the bucket
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    print(f"  ✅ Uploaded {local_path} → gs://{bucket_name}/{gcs_path}")


# ---------------------------------------------------------------------------
# BigQuery upload helpers
# ---------------------------------------------------------------------------

def upload_predictions_to_bq(
    df: pd.DataFrame,
    destination_table: str,
    bq_client: bigquery.Client,
    labels: dict = None,
    expiration_days: int = None,
) -> None:
    """Upload a DataFrame of predictions to BigQuery.

    Args:
        df: DataFrame containing predictions (must include individual_id, y_pred)
        destination_table: Full BQ table name: 'project.dataset.table'
        bq_client: Authenticated BigQuery client
        labels: Optional dict of BQ labels to set on the table
        expiration_days: Optional number of days before table expires
    """
    job_config = bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')
    if labels:
        job_config.labels = {k: str(v) for k, v in labels.items()
                             if k not in ('expiration_days',)}

    load_job = bq_client.load_table_from_dataframe(
        dataframe=df,
        destination=destination_table,
        job_config=job_config,
    )
    load_job.result()
    print(f"  ✅ Uploaded {len(df):,} rows to {destination_table}")

    if expiration_days:
        _set_table_expiry(bq_client, destination_table, expiration_days)

    if labels:
        _set_table_labels(bq_client, destination_table, labels)


def _set_table_expiry(bq_client: bigquery.Client, table_id: str, days: int) -> None:
    """Set expiration on an existing BigQuery table.

    Args:
        bq_client: Authenticated BigQuery client
        table_id: Full table id 'project.dataset.table'
        days: Days until expiration
    """
    query = f"""
    ALTER TABLE `{table_id}`
    SET OPTIONS (
        expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    )
    """
    bq_client.query(query).result()
    print(f"  Set {days}-day expiry on {table_id}")


def _set_table_labels(bq_client: bigquery.Client, table_id: str, labels: dict) -> None:
    """Apply BQ labels to an existing table via ALTER TABLE.

    Args:
        bq_client: Authenticated BigQuery client
        table_id: Full table id 'project.dataset.table'
        labels: dict of label key/value pairs
    """
    label_pairs = ', '.join(
        f'("{k}", "{v}")'
        for k, v in labels.items()
        if k not in ('expiration_days',)
    )
    query = f"ALTER TABLE `{table_id}` SET OPTIONS (labels=[{label_pairs}])"
    bq_client.query(query).result()
    print(f"  Applied labels to {table_id}")


# ---------------------------------------------------------------------------
# Vertex AI model-card helpers
# ---------------------------------------------------------------------------

def sanitize_vertex_label(s, max_len: int = 63) -> str:
    """Return a Vertex AI label-safe string.

    Rules enforced: lowercase, only ``[a-z0-9_-]``, max *max_len* characters.
    Dots, spaces, and other punctuation are replaced with underscores;
    consecutive underscores are collapsed; leading/trailing ones are stripped.

    Args:
        s:       Value to sanitize (any type; converted to str first).
        max_len: Maximum character length (Vertex AI limit is 63).

    Returns:
        Sanitized string safe for use as a Vertex AI label key or value.
    """
    s = str(s).lower()
    s = re.sub(r'[^a-z0-9_\-]', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s[:max_len]


def build_model_labels(
    config: dict,
    params: dict,
    roc_auc: float,
    eval_metrics: dict,
    n_train: int,
    n_test: int,
    n_val: int,
    n_features: int,
    training_timestamp: str,
) -> dict:
    """Build a Vertex AI ``labels`` dict from training metadata.

    All keys and values satisfy Vertex AI constraints:
    ``[a-z0-9_-]``, max 63 chars each, at most 64 labels total.
    Any label whose sanitised value is empty is silently omitted.

    Labels included
    ---------------
    * Identity        : model_name, tenant, self_serve,
                        vertex_model_id, vertex_model_version_alias,
                        vertex-ai-pipelines-run-billing-id
    * Governance      : owner, lob, costcenter, unique_id, pipeline_type
    * Data provenance : outcome_var, bq_project, bq_dataset
    * Split sizes     : train_rows, test_rows, val_rows, num_features
    * Hyperparameters : num_boost_round, max_depth, booster, objective,
                        learning_rate, subsample, colsample_bytree,
                        tree_method, random_seed
    * Evaluation      : roc_auc + one label per percentile metric
                        (lift_N_perc, ppv_N_perc, sensitivity_N_perc)
    * Provenance      : training_date (YYYY-MM-DD)

    Args:
        config:             Full training config dict.
        params:             Resolved XGBoost params dict used for training.
        roc_auc:            ROC-AUC score on the test set.
        eval_metrics:       Dict returned by ``calculate_metrics()``
                            (keys: lift_N_perc, ppv_N_perc, sensitivity_N_perc).
        n_train:            Number of training rows.
        n_test:             Number of test rows.
        n_val:              Number of validation rows.
        n_features:         Number of features used.
        training_timestamp: ISO-8601 UTC timestamp string (used for date label).

    Returns:
        dict[str, str] ready to pass as ``labels=`` to ``aiplatform.Model.upload()``.
    """
    lv = sanitize_vertex_label          # shorthand

    gcp      = config['gcp']
    bql      = config['bigquery_labels']
    data_cfg = config['data_processing']
    ml       = config.get('model_labels', {})   # identity / governance extras

    # Helper: add to dict only when the sanitised value is non-empty
    def _add(d, key, raw_value):
        v = lv(raw_value)
        if v:
            d[key] = v

    labels = {}

    # ── Model identity (from model_labels config section) ──────────────────
    _add(labels, 'model_name',                        ml.get('model_name', ''))
    _add(labels, 'tenant',                            ml.get('tenant', ''))
    _add(labels, 'self_serve',                        ml.get('self_serve', ''))
    _add(labels, 'vertex_model_id',                   ml.get('vertex_model_id', ''))
    _add(labels, 'vertex_model_version_alias',        ml.get('vertex_model_version_alias', ''))
    # hyphen key is valid in Vertex AI labels ([a-z0-9_-])
    _add(labels, 'vertex-ai-pipelines-run-billing-id',
         ml.get('vertex_ai_pipelines_run_billing_id', ''))

    # ── Governance (from bigquery_labels) ──────────────────────────────────
    _add(labels, 'owner',         bql.get('owner', ''))
    _add(labels, 'lob',           bql.get('lob', ''))
    _add(labels, 'costcenter',    str(bql.get('costcenter', '')))
    _add(labels, 'unique_id',     bql.get('unique_id', ''))
    _add(labels, 'pipeline_type', bql.get('pipeline_type', ''))

    # ── Data provenance ────────────────────────────────────────────────────
    _add(labels, 'outcome_var',  data_cfg.get('outcome_var', ''))
    _add(labels, 'bq_project',   gcp.get('gcp_project', ''))
    _add(labels, 'bq_dataset',   gcp.get('gcp_db', ''))

    # ── Dataset sizes (always numeric strings → never empty) ───────────────
    labels['train_rows']   = str(n_train)
    labels['test_rows']    = str(n_test)
    labels['val_rows']     = str(n_val)
    labels['num_features'] = str(n_features)

    # ── XGBoost hyperparameters ────────────────────────────────────────────
    _add(labels, 'num_boost_round',  str(config['model'].get('num_boost_round', '')))
    _add(labels, 'max_depth',        str(params.get('max_depth', '')))
    _add(labels, 'booster',          str(params.get('booster', '')))
    _add(labels, 'objective',        str(params.get('objective', '')))
    _add(labels, 'learning_rate',    f"{params.get('learning_rate', 0):.6g}")
    _add(labels, 'subsample',        f"{params.get('subsample', 0):.4f}")
    _add(labels, 'colsample_bytree', f"{params.get('colsample_bytree', 0):.4f}")
    _add(labels, 'tree_method',      str(params.get('tree_method', '')))
    _add(labels, 'random_seed',      str(data_cfg.get('random_seed', '')))

    # ── Evaluation ─────────────────────────────────────────────────────────
    labels['roc_auc']       = lv(f"{roc_auc:.4f}")
    labels['training_date'] = training_timestamp[:10]   # YYYY-MM-DD

    # One label per percentile metric (lift / ppv / sensitivity at each cut)
    for metric_key, metric_val in eval_metrics.items():
        _add(labels, lv(metric_key), f"{metric_val:.4f}")

    # Guard: Vertex AI allows at most 64 labels
    if len(labels) > 64:
        print(f"  ⚠️  Label count {len(labels)} exceeds Vertex AI limit (64); truncating.")
        labels = dict(list(labels.items())[:64])

    return labels


def save_model_metadata_to_gcs(
    metadata: dict,
    bucket_name: str,
    gcs_blob_path: str,
) -> None:
    """Serialise *metadata* as indented JSON and upload directly to GCS.

    No temporary local file is created; the JSON bytes are streamed straight
    to the GCS blob.

    Args:
        metadata:      Any JSON-serialisable dict (non-serialisable values
                       are coerced to strings via ``default=str``).
        bucket_name:   GCS bucket name without the ``gs://`` prefix.
        gcs_blob_path: Destination object path inside the bucket.
    """
    json_bytes = json.dumps(metadata, indent=2, default=str).encode('utf-8')
    client = storage.Client()
    blob   = client.bucket(bucket_name).blob(gcs_blob_path)
    blob.upload_from_string(json_bytes, content_type='application/json')
    print(f"  ✅ Metadata uploaded → gs://{bucket_name}/{gcs_blob_path}")

