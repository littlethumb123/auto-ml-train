import os
import json
import requests
from typing import Dict, List, Optional

from google.cloud import aiplatform
from google.cloud import bigquery
import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request

def comma_list(s: str) -> Optional[List[str]]:
    s = (s or "").strip()
    if not s:
        return None
    return [p.strip() for p in s.split(",") if p.strip()]

def main() -> str:
    project = os.environ["PROJECT"]
    location = os.environ["LOCATION"]
    model_resource_name = os.environ["MODEL_RESOURCE_NAME"]
    input_table = os.environ["INPUT_TABLE"]
    output_table = os.environ["OUTPUT_TABLE"]
    target_sa = os.environ["SERVICE_ACCOUNT"]
    machine_type_str = os.environ.get("MACHINE_TYPE", "n1-standard-4")
    starting_replica_count = int(os.environ.get("STARTING_REPLICA_COUNT", "1"))
    max_replica_count = int(os.environ.get("MAX_REPLICA_COUNT", "1"))
    cmek_key = os.environ["CMEK_KEY"]
    compute_dataset = os.environ["COMPUTE_DATASET"]
    owner = os.environ["OWNER"]
    cost_center = os.environ["COST_CENTER"]
    expiration_days = 1
    access_token = os.environ.get("ACCESS_TOKEN")  # optional; we’ll impersonate in code

    # Impersonate the target SA for all Google clients
    source_creds, _ = google.auth.default()
    target_creds = impersonated_credentials.Credentials(
        source_credentials=source_creds,
        target_principal=target_sa,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=3600,
    )

    # BigQuery client with impersonated credentials
    bq_client = bigquery.Client(project=project, credentials=target_creds)

    input_table_name = input_table.split(".")[-1]
    output_table_name = output_table.split(".")[-1]
    labels_sql = f"""labels=[("owner","{owner}"),("costcenter","{cost_center}")]"""


    # 1) Copy input to temp with labels and TTL
    temp_input_table = f"{project}.{compute_dataset}.{input_table_name}_tmp"
    create_temp_input = f"""
    CREATE OR REPLACE TABLE `{temp_input_table}`
    OPTIONS({labels_sql}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 DAY))
    AS SELECT * FROM `{input_table}`
    """
    job = bq_client.query(create_temp_input)
    job.result()

    # Prepare temp output
    temp_output_table = f"{project}.{compute_dataset}.{output_table_name}_tmp"

    # 2) Create Batch Prediction via REST using impersonated token
    if not access_token:
        # Build an access token from impersonated creds
        target_creds.refresh(Request())
        access_token = target_creds.token

    parts = model_resource_name.split("/")
    model_project = parts[1]
    model_location = parts[3]
    model_id = parts[5]
    excluded_fields = ['index_date', 'index_dt', 'pre_term_max', 'asdb_member_key']

    batch_prediction_request: Dict = {
        "displayName": f"{model_id}_model_prediction",
        "model": model_resource_name,
        "serviceAccount": target_sa,
        "inputConfig": {
            "instancesFormat": "bigquery",
            "bigquerySource": {"inputUri": f"bq://{temp_input_table}"}
        },
        "outputConfig": {
            "predictionsFormat": "bigquery",
            "bigqueryDestination": {"outputUri": f"bq://{temp_output_table}"}
        },
        "dedicatedResources": {
            "machineSpec": {"machineType": machine_type_str},
            "startingReplicaCount": starting_replica_count,
            "maxReplicaCount": max_replica_count
        },
        "encryptionSpec": {"kmsKeyName": cmek_key},
        "instanceConfig": {"excludedFields": excluded_fields},
        "labels": {"owner": owner, "costcenter": cost_center},
    }

    print(json.dumps(batch_prediction_request, indent=2))

    url = f"https://{model_location}-aiplatform.googleapis.com/v1/projects/{model_project}/locations/{model_location}/batchPredictionJobs"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=batch_prediction_request)
    if resp.status_code != 200:
        raise RuntimeError(f"Batch Prediction creation failed: {resp.status_code} - {resp.text}")

    job_name = resp.json()["name"]
    print(f"✓ Batch prediction job created: {job_name}")

    # 3) Wait using Python SDK with impersonated credentials
    aiplatform.init(project=project, location=model_location, credentials=target_creds)
    bp = aiplatform.BatchPredictionJob(job_name)
    bp.wait_for_completion()
    print(f"✓ Batch prediction completed: {bp.state}")

    # 4) Copy predictions to final output with labels and optional TTL
    if expiration_days:
        options = f'{labels_sql}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {int(expiration_days)} DAY)'
    else:
        options = labels_sql

    copy_sql = f"""
    CREATE OR REPLACE TABLE `{output_table}`
    OPTIONS({options})
    AS SELECT * FROM `{temp_output_table}`
    """
    copy_job = bq_client.query(copy_sql)
    copy_job.result()
    print(f"✓ Final predictions written: {output_table}")

    # 5) Cleanup temp tables
    bq_client.delete_table(temp_input_table, not_found_ok=True)
    bq_client.delete_table(temp_output_table, not_found_ok=True)
    print("✓ Temp tables cleaned up")

    return job_name

if __name__ == "__main__":
    main()