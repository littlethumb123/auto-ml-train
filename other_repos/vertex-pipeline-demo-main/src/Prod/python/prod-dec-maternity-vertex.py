import utils.gcp_handling
import utils.components as components
import os
from datetime import datetime, timedelta
# Import necessary libraries
from kfp.v2 import dsl
from kfp.v2.dsl import component
from kfp.v2 import compiler
from google.cloud import aiplatform


user_constants = {
    "EMAIL": "sahil_gadge_aetna_com",
    "COSTCENTER": "13070",
    "TENANT": "hcm-cm-de",
    "USE_COMPUTE_PROJECT": True,
    "OWNER": "sahil_gadge_aetna_com",
    "COMPUTE_PROJECT": "anbc-prod-hcm-cm-de",
    "PROJECT": "anbc-prod-hcm-cm-de",
    'LABELS': {
        'owner': 'sahil_gadge_aetna_com',
        'costcenter': '13070',
        'tenant': 'hcm-cm-de',
        'self_serve': 'true',
        'lob': 'hcb',
        'pipeline_type': 'scoring'
    },
    "LOB": "hcb",
    "MODEL_DESCRIPTION": "maternity_prod_scoring",
    "PIPELINE_TYPE": "prediction",
    
    # SQL Variables for BigQuery queries
    "GCP_PROJECT": "anbc-hcb-prod",
    "GCP_DB": "clin_analytics_dec_hcb_prod",
    "PREFIX": "a974930_prod_data_maternity",
    "DEFAULT_EXP": "INTERVAL 2 DAY",
    
    # Production date variables - UPDATE THESE FOR EACH SCORING RUN
    "INDEX_DT": "CURRENT_DATE()",  # Use CURRENT_DATE() for real-time scoring
    "KMDO_DT": "'2025-01-15'",  # Komodo data date - update to latest available
    "SDOH_YR": "2024",  # SDOH year - use most recent available
    "BATCH_PREDICTION": {
    "model_resource_name": "projects/979416662908/locations/us-east4/models/2421401681292951552@2",
    "key_field": "asdb_member_key",
    "compute_dataset": "hcm_cm_de_dec_beam_prod_hcm_cm_de",
    "expiration_days": 2,
    "excluded_fields": ["pre_term_max", "index_dt", "asdb_member_key"],
    "included_fields": [],
    "machine_type": {"machine_type": "n1-standard-16"},
    "starting_replica_count": 1,
    "max_replica_count": 1
    }
}
from google.auth import impersonated_credentials
from google.oauth2 import service_account
import google.auth
source_credentials, _ = google.auth.default()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "anbc-prod-hcm-cm-de")
REGION = os.getenv("REGION", "us-east4")
PIPELINE_ROOT = os.getenv("PIPELINE_ROOT", "gs://hcm-cm-de-dec-hcb-prod/vertex-test/")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "projects/cvs-key-vault-prod/locations/us-east4/keyRings/gkr-prod-us-east4/cryptoKeys/gk-anbc-prod-hcm-cm-de-us-east4")
TARGET_SERVICE_ACCOUNT = os.getenv("TARGET_SERVICE_ACCOUNT")  # optional

print(f"Impersonating service account: {TARGET_SERVICE_ACCOUNT}")

# Create impersonated credentials
target_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal=TARGET_SERVICE_ACCOUNT,
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
test_query = """
    SELECT dispatch_outreach_status FROM anbc-hcb-prod.clin_analytics_dec_hcb_prod.DE_RAP_PCR_ACC_TRACKER_summarizedDISPATCHcalls LIMIT 1
    """
from google.cloud import bigquery
bq_client = bigquery.Client(
        project=PROJECT_ID,
        credentials=target_credentials
    )
query_job = bq_client.query(test_query)
results = query_job.result()
print(f"Impersonating: {TARGET_SERVICE_ACCOUNT}")
# If a TARGET_SERVICE_ACCOUNT is provided by the workflow, use it for batch prediction component
if TARGET_SERVICE_ACCOUNT:
    user_constants["service_account"] = TARGET_SERVICE_ACCOUNT

constants = user_constants
os.environ["OWNER"] = constants["EMAIL"]
os.environ["COSTCENTER"] = constants["COSTCENTER"]

def process_sql_file(sql_file_path, constants, base_path="src/Prod/prod_sql_queries/"):
    import os
    import re
    
    # Construct full path
    full_path = os.path.join(base_path, sql_file_path)
    
    # Read the SQL file content
    with open(full_path, 'r') as file:
        sql_content = file.read()
    
    # Find all variables in the SQL file
    variables_in_sql = re.findall(r'\{([^}]+)\}', sql_content)
    
    # Create a clean substitution dictionary from constants
    substitution_dict = {}
    
    for key, value in constants.items():
        # Skip nested dictionaries and non-string values that aren't useful for SQL
        if isinstance(value, dict):
            continue  # Skip LABELS and other nested objects
        elif isinstance(value, bool):
            substitution_dict[key] = str(value).upper()  # Convert True/False to TRUE/FALSE
        else:
            substitution_dict[key] = str(value)  # Convert everything to string
    
    # Add additional mappings for common SQL variable patterns
    additional_mappings = {
        'COST_CENTER': constants.get('COSTCENTER', ''),
    }
    
    # Merge additional mappings
    substitution_dict.update(additional_mappings)
    
    # Check which variables can be substituted
    missing_variables = []
    available_substitutions = {}
    
    for var_name in variables_in_sql:
        if var_name in substitution_dict:
            available_substitutions[var_name] = substitution_dict[var_name]
        else:
            missing_variables.append(var_name)
    
    # Warn about missing variables but don't fail
    if missing_variables:
        print(f"Warning: Variables not found in constants: {missing_variables}")
        print(f"Available substitutions: {list(substitution_dict.keys())}")
        print(f"Variables in SQL: {variables_in_sql}")
    
    # Substitute variables using **kwargs
    try:
        sql_query = sql_content.format(**available_substitutions)
    except KeyError as e:
        print(f"Error: Missing variable {e} in SQL file {sql_file_path}")
        print(f"Available substitutions: {list(available_substitutions.keys())}")
        raise
    
    return sql_query

from kfp.v2.dsl import component

@component(
    base_image="us-docker.pkg.dev/vertex-ai/training/xgboost-cpu.2-1:latest",
    packages_to_install=["google-cloud-bigquery[pandas]", "google-cloud-bigquery", "google-cloud-bigquery-storage", "pyarrow", "db-dtypes", "pandas"]
)
def python_postprocess_component(
    project_id: str,
    input_table: str,     # e.g., {GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_predictors
    output_table: str     # e.g., {GCP_PROJECT}.{GCP_DB}.{PREFIX}_post_py
) -> str:
    import pandas as pd
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)

    df2 = client.list_rows(input_table).to_dataframe(create_bqstorage_client=True)

    print(df2.shape)
    df2 = df2[['asdb_member_key', 'index_dt','mom_age', 'multi', 'bleeding_in_current_preg', 'Cocaine',
       'Nicotine', 'lab_hCG', 'lab_hba1c_current', 'lab_glucose_pre',
       'glucose_challenge_pre', 'lab_hdl', 'lab_ldl', 'lab_triglyc_pre',
       'lab_triglyc_current', 'lab_creat', 'lab_altsgpt', 'lab_bilirub',
       'lab_sodium', 'lab_ferritin', 'sum_ed_visits_yr1',
       'low_sev_ed_visits_yr1', 'med_high_sev_ed_visits_yr1',
       'emis_ed_clm_yr1', 'emis_ed_clm_yr2', 'emis_ip_clm_yr2',
       'emis_lab_clm_yr2', 'coe_ip_hos_clm_yr2', 'coe_lab_clm_yr2',
       'coe_op_hos_clm_yr2', 'coe_maternity_clm_yr2', 'coe_mh_clm_yr2',
       'coe_surg_clm_yr2', 'abdominal_pain', 'CHO', 'VNA', 'MOH', 'HYP',
       'immune', 'bipolar', 'major_chronic_cnt', 'rx_claim_cnt_yr1',
       'gpi4_cnt_yr1', 'retail_fills_yr1', 'ss_brand_fills_yr1',
       'formulary_fills_yr1', 'maint_drug_fills_yr1',
       'antidiabetic_days_supply_yr1', 'beta_blocker_days_supply_yr1',
       'antidepressant_scripts_yr1', 'antidepressant_days_supply_yr1',
       'days_supply_sum_yr2', 'ss_brand_fills_yr2',
       'beta_blocker_days_supply_yr2', 'calcium_channel_blk_days_supply_yr2',
       'antidepressant_days_supply_yr2', 'tenure_yr1', 'tenure_yr2',
       'zip_weight_avg_medinc', 'acs_social_risk_score', 'sdi_score',
       'svi_score', 'adi_score', 'citizenship_index', 'education_index',
       'food_access', 'health_access', 'health_habits', 'housing_desert',
       'housing_ownership', 'housing_quality', 'income_index',
       'income_inequality', 'language_score', 'natural_disaster',
       'poverty_score', 'proactive_health', 'racial_diversity',
       'social_isolation', 'technology_access', 'transport_access',
       'unemployment_index', 'water_quality', 'disability_score',
       'health_infra', 'csdi_social_risk_score', 'sum_spec', 'cms_sti_scrn',
       'emb31', 'emb39', 'emb49', 'emb90', 'emb131', 'emb157', 'emb177',
       'emb181', 'emb203', 'urbsubr', 'pre_term_max']]
    
    if 'urbsubr' in df2.columns:
        df2 = df2.copy()
        df2.loc[:, 'urbsubr_S'] = (df2['urbsubr'] == 'S').astype(int)
    if 'gest_age' not in df2.columns:
        df2.loc[:, 'gest_age'] = 0

    df2 = df2[[ 'gest_age', 'mom_age', 'multi', 'bleeding_in_current_preg', 'Cocaine',
        'Nicotine', 'lab_hCG', 'lab_hba1c_current', 'lab_glucose_pre',
        'glucose_challenge_pre', 'lab_hdl', 'lab_ldl', 'lab_triglyc_pre',
        'lab_triglyc_current', 'lab_creat', 'lab_altsgpt', 'lab_bilirub',
        'lab_sodium', 'lab_ferritin', 'sum_ed_visits_yr1',
        'low_sev_ed_visits_yr1', 'med_high_sev_ed_visits_yr1',
        'emis_ed_clm_yr1', 'emis_ed_clm_yr2', 'emis_ip_clm_yr2',
        'emis_lab_clm_yr2', 'coe_ip_hos_clm_yr2', 'coe_lab_clm_yr2',
        'coe_op_hos_clm_yr2', 'coe_maternity_clm_yr2', 'coe_mh_clm_yr2',
        'coe_surg_clm_yr2', 'abdominal_pain', 'CHO', 'VNA', 'MOH', 'HYP',
        'immune', 'bipolar', 'major_chronic_cnt', 'rx_claim_cnt_yr1',
        'gpi4_cnt_yr1', 'retail_fills_yr1', 'ss_brand_fills_yr1',
        'formulary_fills_yr1', 'maint_drug_fills_yr1',
        'antidiabetic_days_supply_yr1', 'beta_blocker_days_supply_yr1',
        'antidepressant_scripts_yr1', 'antidepressant_days_supply_yr1',
        'days_supply_sum_yr2', 'ss_brand_fills_yr2',
        'beta_blocker_days_supply_yr2', 'calcium_channel_blk_days_supply_yr2',
        'antidepressant_days_supply_yr2', 'tenure_yr1', 'tenure_yr2',
        'zip_weight_avg_medinc', 'acs_social_risk_score', 'sdi_score',
        'svi_score', 'adi_score', 'citizenship_index', 'education_index',
        'food_access', 'health_access', 'health_habits', 'housing_desert',
        'housing_ownership', 'housing_quality', 'income_index',
        'income_inequality', 'language_score', 'natural_disaster',
        'poverty_score', 'proactive_health', 'racial_diversity',
        'social_isolation', 'technology_access', 'transport_access',
        'unemployment_index', 'water_quality', 'disability_score',
        'health_infra', 'csdi_social_risk_score', 'sum_spec', 'cms_sti_scrn',
        'emb31', 'emb39', 'emb49', 'emb90', 'emb131', 'emb157', 'emb177',
        'emb181', 'emb203', 'urbsubr_S', 'pre_term_max', 'asdb_member_key', 'index_dt']]    
    # Write back to BigQuery
    job = client.load_table_from_dataframe(
        df2,
        output_table,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    )
    job.result()

    return output_table

@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        "google-cloud-bigquery>=2.0.0",
        "google-auth>=2.0.0",
        "requests>=2.25.0"
    ]
)
def vertex_batch_predict_bigquery_component(
    project: str,
    location: str,
    service_account: str,
    cmek_key: str,
    cost_center: str,
    owner: str,
    #Model details
    model_resource_name: str,
    # BigQuery specific
    key_field: str,  # Unique key field in input table
    input_table: str,  # project.dataset.table
    output_table: str, # project.dataset.table (final output)
    compute_dataset: str, #hcm_cm_de_dec_beam_{ENV}_hcm_cm_de"
    expiration_days: int = 30, # BQ table expiration in days
    # Instance configuration - field filtering
    excluded_fields: list = None,  # Fields to exclude from predictions
    included_fields: list = None,  # Fields to include (if specified, only these will be sent)
    # Machine configuration
    machine_type: dict = {"machine_type": "n2-standard-64"},
    # Job configuration
    starting_replica_count: int = 1,
    max_replica_count: int = 1,
    batch_size: int = None,  # Auto-determined if None
) -> str:
    """
    Runs a Vertex AI batch prediction job with comprehensive parameter validation.
    
    Copies input table from shared project to compute project temp dataset,
    runs batch prediction to temp output table in compute project temp dataset, 
    then copies to final output table in shared project.

    Args:
        project: GCP project ID.
        location: GCP region.
        compute_dataset: temp dataset in compute project
        model_resource_name: Full resource name of the registered model.
        job_display_name: Display name for the batch prediction job.
        input_table: Input data table (BigQuery table).
        output_table: Output data table (BigQuery table).
        excluded_fields: List of field names to exclude from predictions.
        included_fields: List of field names to include (mutually exclusive with excluded_fields).
        machine_type: Machine type for batch prediction.
        expiration_days: Days until output table expires (default: 30).

    Returns:
        The resource name of the batch prediction job.
    """
    from google.cloud import aiplatform
    from google.cloud import bigquery
    import requests
    import json
    from google.auth import default
    from google.auth.transport.requests import Request
    # Initialize clients
    bq_client = bigquery.Client(project=project)
    
    # Setup table names and labels
    input_table_name = input_table.split(".")[-1]
    output_table_name = output_table.split(".")[-1]
    labels = f"""labels=[("owner","{owner}"),("costcenter","{cost_center}")]"""

    # Copy input table to temp dataset
    temp_input_table = f"{project}.{compute_dataset}.{input_table_name}_tmp"
    query = f"CREATE OR REPLACE TABLE {temp_input_table} OPTIONS({labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)) AS SELECT * FROM {input_table}"
    job = bq_client.query(query)
    job.result()

    # Prepare temp output table
    temp_output_table = f"{project}.{compute_dataset}.{output_table_name}_tmp"

    # Create batch prediction job using REST API
    
    # Get authentication credentials
    credentials, _ = default()
    credentials.refresh(Request())
    access_token = credentials.token
    
    # Extract project, location, and model ID from model resource name
    # Format: projects/{project}/locations/{location}/models/{model_id}
    model_parts = model_resource_name.split('/')
    model_project = model_parts[1]
    model_location = model_parts[3]
    model_id = model_parts[5]
    
    # Convert machine_type keys to camelCase for REST API
    def to_camel_case(snake_str):
        """Convert snake_case to camelCase"""
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

    machine_type = {k: to_camel_case(v) for k, v in machine_type.items() if v is not None}
    
    # Build instance config if field filtering is specified
    instance_config = {}
    if excluded_fields:
        instance_config["excludedFields"] = excluded_fields
    elif included_fields:
        instance_config["includedFields"] = included_fields
    job_display_name = f"{model_id}_model_prediction"
    # Build the REST API request payload
    batch_prediction_request = {
        "displayName": job_display_name,
        "model": model_resource_name,
        "serviceAccount": service_account,
        "inputConfig": {
            "instancesFormat": "bigquery",
            "bigquerySource": {"inputUri": f"bq://{temp_input_table}"}
        },
        "outputConfig": {
            "predictionsFormat": "bigquery",
            "bigqueryDestination": {"outputUri": f"bq://{temp_output_table}"}
        },
        "dedicatedResources": {
            "machineSpec": machine_type,
            "startingReplicaCount": starting_replica_count,
            "maxReplicaCount": max_replica_count
        },
        "encryptionSpec": {
            "kmsKeyName": cmek_key
        }
    }
    
    # Add optional parameters
    if batch_size:
        batch_prediction_request["manualBatchTuningParameters"] = {
            "batchSize": batch_size
        }
    if instance_config:
        batch_prediction_request["instanceConfig"] = instance_config
 
    print(json.dumps(batch_prediction_request, indent=2))
    # Make the REST API call (using v1beta1 to match documentation)
    # https://cloud.google.com/vertex-ai/docs/reference/rpc/google.cloud.aiplatform.v1beta1#batchpredictionjob
    # https://cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform.BatchPredictionJob
    url = f"https://{model_location}-aiplatform.googleapis.com/v1beta1/projects/{model_project}/locations/{model_location}/batchPredictionJobs"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=batch_prediction_request)
    
    if response.status_code != 200:
        raise Exception(f"Batch prediction job creation failed: {response.status_code} - {response.text}")
    
    batch_job_response = response.json()
    batch_predict_job_name = batch_job_response["name"]
    
    print(f"Batch prediction job created: {batch_predict_job_name}")
    
    # use Python SDK for job waiting
    aiplatform.init(project=project, location=location, service_account=service_account)
    batch_job = aiplatform.BatchPredictionJob(batch_predict_job_name)
    batch_job.wait_for_completion()  # Built-in exponential backoff and error handling
    
    print(f"Batch prediction job completed with state: {batch_job.state}")

    # Copy prediction table to final output table
    if expiration_days:
        options=f'{labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {expiration_days} DAY)'
    else:
        options=labels
    query = f"CREATE OR REPLACE TABLE {output_table} OPTIONS({options}) AS SELECT * FROM `{temp_output_table}`"
    copy_pred_job = bq_client.query(query)
    copy_pred_job.result()
    #clean up temp tables
    bq_client.delete_table(temp_input_table, not_found_ok=True)
    bq_client.delete_table(temp_output_table, not_found_ok=True)

    return batch_predict_job_name

from google.cloud import aiplatform
import os

# Define the production pipeline
@dsl.pipeline(
    name="maternity-prod-scoring-pipeline",
    description="Production pipeline for maternity risk scoring using PREGNANCY_TABLE_W cohort"
)
def prod_bigquery_pipeline(
    project_id: str = PROJECT_ID,
    region: str = REGION,
    cmek_key: str = ENCRYPTION_KEY
):
    """
    Production Scoring Pipeline Dependency Graph:
    
    PHASE 0: Cohort Definition
    └── 000_cohort (creates _st, _final_timepoint from PREGNANCY_TABLE_W)
    
    PHASE 1: Parallel execution (after 000)
    ├── 001a_asdb_cpt_rev_icd
    ├── 001e_asdb_labs
    ├── 001f_edw_cpt_rev_icd
    ├── 001g_edw_labs
    ├── 001h_komodo_cpt_rev_icd
    ├── 002_Med_Claims
    ├── 004_Conditions
    ├── 006_Rx_Claims
    └── 007_Demographics

    PHASE 2: Secondary dependencies
    ├── 003_Cost_and_Utilization (after 002)
    ├── 010_preventative (after 003)
    ├── 008_GeoID (after 007)
    ├── 009_ACS (after 008)
    └── 011_CSDI_risk (after 008)
    
    PHASE 3: Aggregation
    ├── 001i_custom_predictors_joined (after 001a, 001e, 001f, 001g, 001h)
    ├── 001j_labs_joined (after 001e, 001g)
    └── 012_non_embedding_feature_beast (after 003-011)
    
    PHASE 4: Final Join
    └── 013_join_cust_pipeline_embed_features (after 001i, 001j, 012)
    """

    #################################
    # PHASE 0: Cohort from PREGNANCY_TABLE_W
    #################################
    
    sql_000 = process_sql_file('000_cohort.sql', constants)
    q_000 = components.query_bigquery_component(
        constants=constants,
        query=sql_000,
        display_name="000_cohort"
    )

    #################################
    # PHASE 1: Parallel execution
    #################################
    
    sql_001a = process_sql_file('001a_asdb_cpt_rev_icd.sql', constants)
    q_001a = components.query_bigquery_component(
        constants=constants,
        query=sql_001a,
        display_name="001a_asdb_cpt_rev_icd"
    ).after(q_000)

    # 001e: ASDB Labs
    sql_001e = process_sql_file('001e_asdb_labs.sql', constants)
    q_001e = components.query_bigquery_component(
        constants=constants,
        query=sql_001e,
        display_name="001e_asdb_labs"
    ).after(q_000)

    # 001f: EDW CPT/REV codes
    sql_001f = process_sql_file('001f_edw_cpt_rev_icd.sql', constants)
    q_001f = components.query_bigquery_component(
        constants=constants,
        query=sql_001f,
        display_name="001f_edw_cpt_rev_icd"
    ).after(q_000)

    # 001g: EDW Labs
    sql_001g = process_sql_file('001g_edw_labs.sql', constants)
    q_001g = components.query_bigquery_component(
        constants=constants,
        query=sql_001g,
        display_name="001g_edw_labs"
    ).after(q_000)
    
    # 001h: Komodo CPT/REV/ICD
    sql_001h = process_sql_file('001h_komodo_cpt_rev_icd.sql', constants)
    q_001h = components.query_bigquery_component(
        constants=constants,
        query=sql_001h,
        display_name="001h_komodo_cpt_rev_icd"
    ).after(q_000)

    # 002: Medical Claims (OPTIMIZED - single scan creates both yr1 and yr2 tables)
    sql_002 = process_sql_file('002_Med_Claims.sql', constants)
    q_002 = components.query_bigquery_component(
        constants=constants,
        query=sql_002,
        display_name="002_Med_Claims"
    ).after(q_000)
    
    # 003: Cost and Utilization (OPTIMIZED - single file creates all tables with year_flag)
    sql_003 = process_sql_file('003_Cost_and_Utilization.sql', constants)
    q_003 = components.query_bigquery_component(
        constants=constants,
        query=sql_003,
        display_name="003_Cost_and_Utilization"
    ).after(q_002)
    
    # 006: Rx Claims (OPTIMIZED - single scan creates both yr1 and yr2 tables)
    sql_006 = process_sql_file('006_Rx_Claims.sql', constants)
    q_006 = components.query_bigquery_component(
        constants=constants,
        query=sql_006,
        display_name="006_Rx_Claims"
    ).after(q_000)
    
    # 007: Demographics
    sql_007 = process_sql_file('007_Demographics.sql', constants)
    q_007 = components.query_bigquery_component(
        constants=constants,
        query=sql_007,
        display_name="007_Demographics"
    ).after(q_000)

    #################################
    # PHASE 2: Secondary dependencies
    #################################
    
    # 004: Conditions
    sql_004 = process_sql_file('004_Conditions.sql', constants)
    q_004 = components.query_bigquery_component(
        constants=constants,
        query=sql_004,
        display_name="004_Conditions"
    ).after(q_000)

    # 010: Preventative Care
    sql_010 = process_sql_file('010_preventative.sql', constants)
    q_010 = components.query_bigquery_component(
        constants=constants,
        query=sql_010,
        display_name="010_preventative"
    ).after(q_003)
   
    # 008: GeoID
    sql_008 = process_sql_file('008_GeoID.sql', constants)
    q_008 = components.query_bigquery_component(
        constants=constants,
        query=sql_008,
        display_name="008_GeoID"
    ).after(q_007)
     
    # 009: ACS Data
    sql_009 = process_sql_file('009_ACS.sql', constants)
    q_009 = components.query_bigquery_component(
        constants=constants,
        query=sql_009,
        display_name="009_ACS"
    ).after(q_008)

    # 011: CSDI Risk
    sql_011 = process_sql_file('011_CSDI_risk.sql', constants)
    q_011 = components.query_bigquery_component(
        constants=constants,
        query=sql_011,
        display_name="011_CSDI_risk"
    ).after(q_008)

    #################################
    # PHASE 3: Aggregation
    #################################
    
    # 001i: Custom Predictors Joined
    sql_001i = process_sql_file('001i_custom_predictors_joined.sql', constants)
    q_001i = components.query_bigquery_component(
        constants=constants,
        query=sql_001i,
        display_name="001i_custom_predictors_joined"
    ).after(*[q_001a, q_001e, q_001f, q_001h])
    
    # 001j: Labs Joined
    sql_001j = process_sql_file('001j_labs_joined.sql', constants)
    q_001j = components.query_bigquery_component(
        constants=constants,
        query=sql_001j,
        display_name="001j_labs_joined"
    ).after(*[q_001e, q_001g])
    
    # 012: Non-Embedding Feature Beast
    sql_012 = process_sql_file('012_non_embedding_feature_beast.sql', constants)
    q_012 = components.query_bigquery_component(
        constants=constants,
        query=sql_012,
        display_name="012_non_embedding_feature_beast"
    ).after(*[q_003, q_004, q_006, q_007, q_009, q_010, q_011])

    #################################
    # PHASE 4: Final Join
    #################################
    
    sql_013 = process_sql_file('013_join_cust_pipeline_embed_features.sql', constants)
    q_013 = components.query_bigquery_component(
        constants=constants,
        query=sql_013,
        display_name="013_join_cust_pipeline_embed_features"
    ).after(*[q_001i, q_001j, q_012])
    
    input_tbl = f"{constants['GCP_PROJECT']}.{constants['GCP_DB']}.{constants['PREFIX']}_all_predictors"
    output_tbl = f"{constants['GCP_PROJECT']}.{constants['GCP_DB']}.{constants['PREFIX']}_post_py"

    py_step = python_postprocess_component(
        project_id=project_id,
        input_table=input_tbl,
        output_table=output_tbl
    ).after(q_013)
    
    bp = constants["BATCH_PREDICTION"]

    batch_pred_job = vertex_batch_predict_bigquery_component(
        project=project_id,
        location=constants.get("REGION", region),
        service_account=TARGET_SERVICE_ACCOUNT,
        cmek_key=cmek_key,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name=bp["model_resource_name"],
        key_field=bp["key_field"],
        input_table=output_tbl,
        output_table=output_tbl.replace("_post_py", "_prediction"),
        compute_dataset=bp["compute_dataset"],
        expiration_days=bp["expiration_days"],
        excluded_fields=bp["excluded_fields"],
        included_fields=bp["included_fields"],
        machine_type=bp["machine_type"],
        starting_replica_count=bp["starting_replica_count"],
        max_replica_count=bp["max_replica_count"]
        # batch_size omitted to avoid None issues
    ).after(py_step)
    
# Compile and run the production pipeline
if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=prod_bigquery_pipeline,
        package_path="prod_bigquery_pipeline.json"
    )

    # Initialize Vertex AI client
    aiplatform.init(
        project=PROJECT_ID,
        location=REGION,
        credentials=target_credentials
    )

    # Define the pipeline job
    pipeline_job = aiplatform.PipelineJob(
        display_name="maternity-prod-scoring-pipeline",
        template_path="prod_bigquery_pipeline.json",
        pipeline_root=PIPELINE_ROOT,
        encryption_spec_key_name=ENCRYPTION_KEY,
        enable_caching=False,
        parameter_values={
            "project_id": PROJECT_ID,
            "region": REGION,
            "cmek_key": ENCRYPTION_KEY
        },
        labels={
            "owner": constants["OWNER"],
            "pipeline_type": "scoring",
            "lob": constants["LOB"],
            "costcenter": constants["COSTCENTER"],
            "tenant": constants["TENANT"],
            "self_serve": "true"
        }
    )

    # Submit the pipeline job
    pipeline_job.run(service_account=TARGET_SERVICE_ACCOUNT, sync=True)
