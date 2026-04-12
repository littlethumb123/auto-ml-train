import utils.gcp_handling
import utils.components as components
import os
from datetime import datetime, timedelta
# Import necessary libraries
from kfp.v2 import dsl
from kfp.v2.dsl import component
from kfp.v2 import compiler
from google.cloud import aiplatform


from google.auth import impersonated_credentials
from google.oauth2 import service_account
import google.auth
source_credentials, _ = google.auth.default()

PROJECT_ID             = os.getenv("GOOGLE_CLOUD_PROJECT", "anbc-dev-hcm-cm-de")
ENV                    = ''.join([x for x in ['dev', 'test', 'prod'] if x in PROJECT_ID])
shared_project         = f"anbc-hcb-{ENV}"
REGION                 = os.getenv("REGION", "us-east4")
PIPELINE_ROOT          = os.getenv("PIPELINE_ROOT", "gs://hcm-cm-de-code-hcb-dev/vertex-test/")
ENCRYPTION_KEY         = os.getenv("ENCRYPTION_KEY", "projects/cvs-key-vault-dev/locations/us-east4/keyRings/gkr-dev-us-east4/cryptoKeys/gk-anbc-dev-hcm-cm-de-us-east4")
TARGET_SERVICE_ACCOUNT = os.getenv("TARGET_SERVICE_ACCOUNT")  # optional
CODE_BUCKET            = f"hcm-cm-de-code-hcb-{ENV}"

user_constants = {
    "EMAIL": "navaneethakrishnanp_aetna_com",
    "COSTCENTER": "790071",
    "TENANT": "hcm-cm-de",    
    "USE_COMPUTE_PROJECT": True,
    "OWNER": "navaneethakrishnanp_aetna_com",
    "COMPUTE_PROJECT": f"anbc-{ENV}-hcm-cm-de",
    "PROJECT": f"anbc-{ENV}-hcm-cm-de",
    "LOB": "hcb",
    "MODEL_DESCRIPTION": "cp-cm-case-mix-redesign",
    "PIPELINE_TYPE": "pipeline",
    "DATA_BUCKET":f"hcm-cm-de-data-hcb-{ENV}",
    
    # SQL Variables for BigQuery queries
    "PROJECT_ID": f"anbc-hcb-{ENV}",
    "DATASET_ID": f"clin_analytics_hcb_{ENV}",
    "PREFIX":"a534864_test_cp_cm_savings_update",
    "PREFIX_RPT":"a534864_test_katie_transition",
    "DEC_DATASET_ID": f"clin_analytics_dec_hcb_{ENV}",
    "VOLTAGE_DATASET": f"voltage_anbc_hcb_{ENV}",
    "OWNER": "kukkadiputhurayaj_aetna_com",
    "COST_CENTER": "790071",
    "UNIQUE_ID": f"hcm-cm-gen-me-{ENV}",
    "TARGET_DB": f"anbc-hcb-{ENV}.clin_analytics_hcb_{ENV}",
    "START_DT":"'2023-01-01'",
    "TARGET_DB_DEC": f"anbc-hcb-{ENV}.clin_analytics_dec_hcb_{ENV}",
    
    # Production date variables - UPDATE THESE FOR EACH SCORING RUN
    "INDEX_DT": "CURRENT_DATE()",  # Use CURRENT_DATE() for real-time scoring
    "KMDO_DT": "'2025-01-15'",  # Komodo data date - update to latest available
    "SDOH_YR": "2024",  # SDOH year - use most recent available
    "BATCH_PREDICTION": {
    "model_resource_name": "projects/979416662908/locations/us-east4/models/2421401681292951552@2",
    "key_field": "asdb_member_key",
    "compute_dataset": f"hcm_cm_de_beam_{ENV}_hcm_cm_de",
    "expiration_days": 2,
    "excluded_fields": ["pre_term_max", "index_dt", "asdb_member_key"],
    "included_fields": [],
    "machine_type": {"machine_type": "n1-standard-16"},
    "starting_replica_count": 1,
    "max_replica_count": 1
    }
}

# Service accounts #
if ENV=="dev":
   env_id   = 'ontpd'
elif ENV=="test":
   env_id   = 'onppq'
elif ENV=="prod":
   env_id   = 'onppp'

service_account = f"gchcb-hcm-cm-de-{env_id}@anbc-{ENV}-hcm-cm-de.iam.gserviceaccount.com"

print(f"Impersonating service account: {TARGET_SERVICE_ACCOUNT}")

# Create impersonated credentials
target_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal=TARGET_SERVICE_ACCOUNT,
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
# If a TARGET_SERVICE_ACCOUNT is provided by the workflow, use it for batch prediction component
if TARGET_SERVICE_ACCOUNT:
    user_constants["service_account"] = TARGET_SERVICE_ACCOUNT

constants = user_constants
constants["service_account"] = service_account
#LABEL_DEF = "OPTIONS (labels=[(\"owner\",\"{OWNER}\"),(\"costcenter\",\"{COST_CENTER}\"),(\"unique_id\",\"{UNIQUE_ID}\")])"
#LABELS    = LABEL_DEF.format(OWNER=constants["EMAIL"], COST_CENTER=constants["COSTCENTER"], UNIQUE_ID=constants["UNIQUE_ID"])
#constants["LABELS"] = LABELS

os.environ["OWNER"] = constants["EMAIL"]
os.environ["COSTCENTER"] = constants["COSTCENTER"]

def process_sql_file(sql_file, constants, base_path="cp-case-mix/"):
    import os
    import re
    """
    Fetches the SQL query from a file stored in a GCS bucket.
    """
    from google.cloud import storage

    # Construct full path
    sql_file_path = os.path.join(base_path, sql_file)

    client      = storage.Client(project=shared_project, credentials=target_credentials)
    bucket      = client.bucket(CODE_BUCKET)
    blob        = bucket.blob(sql_file_path)
    sql_content = blob.download_as_text()
    
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
        print(f"Error: Missing variable {e} in SQL file {sql_file}")
        print(f"Available substitutions: {list(available_substitutions.keys())}")
        raise
    
    return sql_query

from kfp.v2.dsl import component

@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        "google-cloud-bigquery>=2.0.0",
        "google-auth>=2.0.0",
        "requests>=2.25.0",
        "pandas",
        "numpy",
        "db-dtypes"
    ]
)

def python_script_component(
    project_sh: str,
    db_sh: str,     
    prefix_sh: str,  
    owner_sh: str,
    cost_center_sh: str,     
    case_prefix_sh: str,
    bucket_name: str,
    resource_id: str        
) -> str:
    
    """Download and execute a Python script from GCS."""
    from google.cloud import storage
    import subprocess
    import os
    import sys
    from datetime import datetime
    from pathlib import Path
    import tempfile
    
    # Check if today is the first of the month
    today = datetime.now()
    if today.day != 1:
        print(f"Today is {today.strftime('%Y-%m-%d')} - not the first of the month. Skipping script execution.")
        return "Report Generation skipped - not first of month"
    
    print(f"Today is the first of the month ({today.strftime('%Y-%m-%d')}). Running Report Generation scripts...")    
    
    # Create case_mix_non_bh_report
    # Download script from GCS
    client = storage.Client(project=project_sh)
    
    bucket = client.bucket(bucket_name)
    blob = bucket.blob("cp-case-mix/casemix_excel_report_withoutBH_009.py")
    blob.download_to_filename("/tmp/script.py")
    
    # Execute the script
    # Execute the script with arguments
    result = subprocess.run(["python", "/tmp/script.py", project_sh, db_sh, prefix_sh, owner_sh, cost_center_sh, case_prefix_sh, bucket_name, resource_id], capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        raise Exception(f"Script failed: {result.stderr}")
    
    # Create case_mix_bh_report
    # Download script from GCS
    client = storage.Client(project=project_sh)
    
    bucket = client.bucket(bucket_name)
    blob = bucket.blob("cp-case-mix/casemix_excel_report_withBH_010.py")
    blob.download_to_filename("/tmp/script.py")
    
    # Execute the script
    # Execute the script with arguments
    result = subprocess.run(["python", "/tmp/script.py", project_sh, db_sh, prefix_sh, owner_sh, cost_center_sh, case_prefix_sh, bucket_name, resource_id], capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        raise Exception(f"Script failed: {result.stderr}")    

    return "completed"
        
    
from google.cloud import aiplatform
import os

# Define the devuction pipeline
@dsl.pipeline(
    name="cp-cm-case-mix-pipeline",
    description="This pipeline tracks the commercial care management outreaches and associates Medical Cost Savings to these events"
)
def dev_case_mix_report_pipeline(
    project_id: str = PROJECT_ID,
    region: str = REGION,
    cmek_key: str = ENCRYPTION_KEY
):
    """
    Production Scoring Pipeline Dependency Graph:
    
    PHASE 1: pulling_current_cases
    └── 001_pulling_current_cases
    
    PHASE 2: risk_collection
    └── 002_risk_collection

    PHASE 3: risk_determination
    └── 003_risk_determination

    PHASE 4: cost_trend_determination
    └── 004_cost_trend_determination

    PHASE 5: savings_calculation
    └── 005_savings_calculation.sql

    PHASE 6: formatting_output_table
    └── 006_formatting_output_table     

    PHASE 7: adding_BH_flags
    └── 007_adding_BH_flags.sql

    PHASE 8: adding_dedup_logic
    └── 008_adding_dedup_logic

    PHASE 9: consolidated_cm_tableau_d
    └── 011_consolidated_case_mix_tableau               
    """

    #################################
    #   SQL Executions Definitions
    #################################
    
    sql_001 = process_sql_file('001_pulling_current_cases.sql', constants)
    q_001 = components.query_bigquery_component(
        constants=constants,
        query=sql_001,
        display_name="001_pulling_current_cases"
    )
   
    sql_002 = process_sql_file('002_risk_collection.sql', constants)
    q_002 = components.query_bigquery_component(
        constants=constants,
        query=sql_002,
        display_name="002_risk_collection"
    ).after(q_001)

    sql_003 = process_sql_file('003_risk_determination.sql', constants)
    q_003 = components.query_bigquery_component(
        constants=constants,
        query=sql_003,
        display_name="003_risk_determination"
    ).after(q_002)

    sql_004 = process_sql_file('004_cost_trend_determination.sql', constants)
    q_004 = components.query_bigquery_component(
        constants=constants,
        query=sql_004,
        display_name="004_cost_trend_determination"
    ).after(q_003)

    sql_005 = process_sql_file('005_savings_calculation.sql', constants)
    q_005 = components.query_bigquery_component(
        constants=constants,
        query=sql_005,
        display_name="005_savings_calculation"
    ).after(q_004)

    sql_006 = process_sql_file('006_formatting_output_table.sql', constants)
    q_006 = components.query_bigquery_component(
        constants=constants,
        query=sql_006,
        display_name="006_formatting_output_table"
    ).after(q_005)     

    sql_007 = process_sql_file('007_adding_BH_flags.sql', constants)
    q_007 = components.query_bigquery_component(
        constants=constants,
        query=sql_007,
        display_name="007_adding_BH_flags"
    ).after(q_006)

    sql_008 = process_sql_file('008_adding_dedup_logic.sql', constants)
    q_008 = components.query_bigquery_component(
        constants=constants,
        query=sql_008,
        display_name="008_adding_dedup_logic"
    ).after(q_007)
    
    create_case_mix_reports_task = python_script_component(
        project_sh=constants["PROJECT_ID"],
        db_sh=constants["DATASET_ID"],
        prefix_sh=constants["PREFIX_RPT"],
        owner_sh=constants["OWNER"],
        cost_center_sh=constants["COSTCENTER"],
        case_prefix_sh=constants["PREFIX"],
        bucket_name=constants["DATA_BUCKET"],
        resource_id=constants["service_account"]             
    ).after(q_008)

    @component(
    base_image="python:3.9",
    packages_to_install=[]
    )

    def determine_run_type() -> str:
        """Determine if this is a monthly or daily run based on current date"""
        from datetime import datetime
        today = datetime.now()
        if today.day == 1:
            return "monthly"
        else:
            return "daily"

    run_type = determine_run_type()

    with dsl.Condition(run_type.output == "monthly", name="consolidated-case-mix-tableau-monthly-execution"):    

         sql_009 = process_sql_file('012_consolidated_case_mix_tableau_monthly.sql', constants)
         q_009 = components.query_bigquery_component(
                 constants=constants,
                 query=sql_009,
                 display_name="012_consolidated_case_mix_tableau_monthly"
         ).after(create_case_mix_reports_task)     

    with dsl.Condition(run_type.output == "daily", name="consolidated-case-mix-tableau-daily-execution"):    

         sql_010 = process_sql_file('011_consolidated_case_mix_tableau.sql', constants)
         q_010 = components.query_bigquery_component(
                 constants=constants,
                 query=sql_010,
                 display_name="011_consolidated_case_mix_tableau_daily"
         ).after(create_case_mix_reports_task)                   

# Compile and run the pipeline
if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=dev_case_mix_report_pipeline,
        package_path="dev_case_mix_report_pipeline.json"
    )

    # Initialize Vertex AI client
    aiplatform.init(
        project=PROJECT_ID,
        location=REGION,
        credentials=target_credentials
    )

    # Define the pipeline job
    pipeline_job = aiplatform.PipelineJob(
        display_name="cp-cm-case-mix-pipeline",
        template_path="dev_case_mix_report_pipeline.json",
        pipeline_root=PIPELINE_ROOT,
        encryption_spec_key_name=ENCRYPTION_KEY,
        enable_caching=False, # make sure use True for Dev and Strictly False before migration to prod
        parameter_values={
            "project_id": PROJECT_ID,
            "region": REGION,
            "cmek_key": ENCRYPTION_KEY
        },
        labels={
            "owner": constants["OWNER"],
            "pipeline_type": "pipeline",
            "lob": constants["LOB"],
            "costcenter": constants["COSTCENTER"],
            "tenant": constants["TENANT"],
            "self_serve": "true"
        }
    )

    # Submit the pipeline job
    # List schedules
    schedules = aiplatform.PipelineJobSchedule.list(
        filter='display_name="cp-cm-case-mix-pipeline"',
        order_by="create_time desc",  # Optional: get newest first
        project=PROJECT_ID,
        location=REGION
    )

    if not schedules:
        print("No schedules found matching the filter")
    else:
        print(f"Found {len(schedules)} schedule(s) to delete")
        
        for schedule in schedules:
            try:
                print(f"\nDeleting schedule:")
                print(f"  Display Name: {schedule.display_name}")
                print(f"  Resource ID: {schedule.resource_name}")
                print(f"  State: {schedule.state}")
                
                # Pause first if active (optional but recommended)
                if schedule.state.name == "ACTIVE":
                    print("  Pausing schedule before deletion...")
                    schedule.pause()
                
                # Delete the schedule
                schedule.delete(sync=True)
                print(f"  ✓ Successfully deleted")
                
            except Exception as e:
                print(f"  ✗ Error deleting {schedule.resource_name}: {str(e)}")

    pipeline_job.create_schedule(
    display_name="cp-cm-case-mix-pipeline",
    cron="0 13 * * *",
    max_concurrent_run_count=1,
    service_account=TARGET_SERVICE_ACCOUNT,
    )

    pipeline_job.run(
        service_account=TARGET_SERVICE_ACCOUNT,
        sync=True
    )