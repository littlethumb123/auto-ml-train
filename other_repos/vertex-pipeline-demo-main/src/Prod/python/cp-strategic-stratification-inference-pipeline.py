import sys
import os
import json

# Add project root to Python path to import from utils
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import utils.gcp_handling
import utils.components as components

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
PIPELINE_ROOT          = os.getenv("PIPELINE_ROOT", f"gs://hcm-cm-de-code-hcb-{ENV}/mlops_cp_strategic_strat/")
ENCRYPTION_KEY         = os.getenv("ENCRYPTION_KEY", "projects/cvs-key-vault-nonprod/locations/us-east4/keyRings/gkr-nonprod-us-east4/cryptoKeys/gk-anbc-dev-hcm-cm-de-us-east4")
TARGET_SERVICE_ACCOUNT = os.getenv("TARGET_SERVICE_ACCOUNT")
CODE_BUCKET            = f"hcm-cm-de-code-hcb-{ENV}"

user_constants = {
    "EMAIL": "parked_aetna_com",
    "COSTCENTER": "13070",
    "TENANT": "hcm-cm-de",
    "USE_COMPUTE_PROJECT": True,
    "COMPUTE_PROJECT": f"anbc-{ENV}-hcm-cm-de",
    "PROJECT": f"anbc-{ENV}-hcm-cm-de",
    "LOB": "hcb",
    "MODEL_DESCRIPTION": "cp-strategic-stratification-inference-pipeline",
    "PIPELINE_TYPE": "model_prediction",
    "DATA_BUCKET": f"hcm-cm-de-data-hcb-{ENV}",
    "CODE_BUCKET": CODE_BUCKET,
    "DATASET": f"anbc-hcb-{ENV}",
    "SCHEMA": f"clin_analytics_hcb_{ENV}",
    "prefix": "cp_strategic_stratification",
    "database_name": f"anbc-hcb-{ENV}.clin_analytics_hcb_{ENV}",
    "dec_database_name": f"anbc-hcb-{ENV}.clin_analytics_hcb_{ENV}",
    "SHARE_SCHEMA": f"anbc-hcb-{ENV}.clin_analytics_share_hcb_{ENV}",
    "OWNER": "parked_aetna_com",
    "COMPUTE_DATASET": f"hcm_cm_de_beam_{ENV}_hcm_cm_de",
}

# Service accounts
if ENV == "dev":
    env_id = "ontpd"
    cron_schedule = None
elif ENV == "test":
    env_id = "onppq"
    cron_schedule = None
elif ENV == "prod":
    env_id = "onppp"
    cron_schedule = None
else:
    env_id = "ontpd"
    cron_schedule = None

service_account_email = f"gchcb-hcm-cm-de-{env_id}@anbc-{ENV}-hcm-cm-de.iam.gserviceaccount.com"
decrypt_sa = f"gchcb-hcm-cm-de-dec-{env_id}@anbc-{ENV}-hcm-cm-de.iam.gserviceaccount.com"

print(f"Impersonating service account: {TARGET_SERVICE_ACCOUNT}")

# Create impersonated credentials
target_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal=TARGET_SERVICE_ACCOUNT,
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

if TARGET_SERVICE_ACCOUNT:
    user_constants["service_account"] = TARGET_SERVICE_ACCOUNT

constants = user_constants
constants["service_account"] = service_account_email

os.environ["OWNER"] = constants["EMAIL"]
os.environ["COSTCENTER"] = constants["COSTCENTER"]


def process_sql_file(sql_file, constants, base_path="src/Prod/prod_sql_queries/mlops-cp-ss"):
    import os
    import re
    """
    Fetches the SQL query from a file stored in a GCS bucket and substitutes
    {PLACEHOLDER} variables from the constants dictionary.
    """
    from google.cloud import storage

    sql_file_path = os.path.join(base_path, sql_file)

    client      = storage.Client(project=shared_project, credentials=target_credentials)
    bucket      = client.bucket(CODE_BUCKET)
    blob        = bucket.blob(sql_file_path)
    sql_content = blob.download_as_text()

    variables_in_sql = re.findall(r'\{([^}]+)\}', sql_content)

    substitution_dict = {}
    for key, value in constants.items():
        if isinstance(value, dict):
            continue
        elif isinstance(value, bool):
            substitution_dict[key] = str(value).upper()
        else:
            substitution_dict[key] = str(value)

    substitution_dict.update({'COST_CENTER': constants.get('COSTCENTER', '')})

    missing_variables = []
    available_substitutions = {}
    for var_name in variables_in_sql:
        if var_name in substitution_dict:
            available_substitutions[var_name] = substitution_dict[var_name]
        else:
            missing_variables.append(var_name)

    if missing_variables:
        print(f"Warning: Variables not found in constants: {missing_variables}")
        print(f"Available substitutions: {list(substitution_dict.keys())}")
        print(f"Variables in SQL: {variables_in_sql}")

    try:
        sql_query = sql_content.format(**available_substitutions)
    except KeyError as e:
        print(f"Error: Missing variable {e} in SQL file {sql_file}")
        print(f"Available substitutions: {list(available_substitutions.keys())}")
        raise

    return sql_query


@dsl.component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        "google-cloud-bigquery>=2.0.0",
        "google-auth>=2.0.0",
        "requests>=2.25.0",
    ]
)
def vertex_batch_predict_bigquery_component(
    project: str,
    location: str,
    service_account: str,
    cmek_key: str,
    cost_center: str,
    owner: str,
    # Model details
    model_resource_name: str,
    # BigQuery specific
    key_field: str,
    input_table: str,
    output_table: str,
    compute_dataset: str,
    expiration_days: int = 30,
    # Instance configuration - field filtering
    excluded_fields: list = None,
    included_fields: list = None,
    # Selected features configuration
    selected_features: list = None,
    # Machine configuration
    machine_type: dict = {"machine_type": "n2-standard-64"},
    # Job configuration
    starting_replica_count: int = 1,
    max_replica_count: int = 1,
    batch_size: int = None,
    informal_model_name: str = None,
) -> str:
    """
    Runs a Vertex AI batch prediction job with BigQuery input/output.

    Copies the input table from the shared project to a compute project temp dataset,
    runs batch prediction to a temp output table, then copies to the final output table
    in the shared project. Cleans up temp tables on completion.
    """
    from google.cloud import aiplatform
    from google.cloud import bigquery
    import requests
    import json
    from google.auth import default
    from google.auth.transport.requests import Request

    bq_client = bigquery.Client(project=project)

    input_table_name  = input_table.split(".")[-1]
    output_table_name = output_table.split(".")[-1]
    labels = f"""labels=[("owner","{owner}"),("costcenter","{cost_center}")]"""

    if informal_model_name:
        temp_input_table  = f"{project}.{compute_dataset}.{input_table_name}_{informal_model_name}_tmp"
        temp_output_table = f"{project}.{compute_dataset}.{output_table_name}_{informal_model_name}_tmp"
    else:
        temp_input_table  = f"{project}.{compute_dataset}.{input_table_name}_tmp"
        temp_output_table = f"{project}.{compute_dataset}.{output_table_name}_tmp"

    # Build the SELECT clause for the temp input table
    if selected_features:
        columns_to_select = selected_features.copy()
        if key_field not in columns_to_select:
            columns_to_select.insert(0, key_field)
        escaped_columns = [f"`{col}`" for col in columns_to_select]
        select_clause = ", ".join(escaped_columns)
        query = (
            f"CREATE OR REPLACE TABLE {temp_input_table} "
            f"OPTIONS({labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)) "
            f"AS SELECT {select_clause} FROM `{input_table}`"
        )
    else:
        query = (
            f"CREATE OR REPLACE TABLE {temp_input_table} "
            f"OPTIONS({labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)) "
            f"AS SELECT * FROM `{input_table}`"
        )

    bq_client.query(query).result()

    # Authenticate and build the batch prediction REST request
    credentials, _ = default()
    credentials.refresh(Request())
    access_token = credentials.token

    model_parts    = model_resource_name.split('/')
    model_project  = model_parts[1]
    model_location = model_parts[3]
    model_id       = model_parts[5]

    def to_camel_case(snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

    machine_type_cc = {to_camel_case(k): v for k, v in machine_type.items() if v is not None}

    instance_config = {}
    if excluded_fields:
        instance_config["excludedFields"] = excluded_fields
    elif included_fields:
        instance_config["includedFields"] = included_fields

    job_display_name = f"{model_id}_model_prediction"

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
            "machineSpec": machine_type_cc,
            "startingReplicaCount": starting_replica_count,
            "maxReplicaCount": max_replica_count
        },
        "encryptionSpec": {"kmsKeyName": cmek_key},
        "instanceConfig": {"includedFields": selected_features},
    }

    if batch_size:
        batch_prediction_request["manualBatchTuningParameters"] = {"batchSize": batch_size}
    if instance_config:
        batch_prediction_request["instanceConfig"] = instance_config

    print(json.dumps(batch_prediction_request, indent=2))

    url = (
        f"https://{model_location}-aiplatform.googleapis.com/v1beta1"
        f"/projects/{model_project}/locations/{model_location}/batchPredictionJobs"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=batch_prediction_request)
    if response.status_code != 200:
        raise Exception(
            f"Batch prediction job creation failed: {response.status_code} - {response.text}"
        )

    batch_predict_job_name = response.json()["name"]
    print(f"Batch prediction job created: {batch_predict_job_name}")

    aiplatform.init(project=project, location=location, service_account=service_account)
    batch_job = aiplatform.BatchPredictionJob(batch_predict_job_name)
    batch_job.wait_for_completion()
    print(f"Batch prediction job completed with state: {batch_job.state}")

    # Copy results to final output table
    if expiration_days:
        options = f'{labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {expiration_days} DAY)'
    else:
        options = labels

    copy_query = (
        f"CREATE OR REPLACE TABLE {output_table} "
        f"OPTIONS({options}) AS SELECT * FROM `{temp_output_table}`"
    )
    bq_client.query(copy_query).result()

    bq_client.delete_table(temp_input_table,  not_found_ok=True)
    bq_client.delete_table(temp_output_table, not_found_ok=True)

    return batch_predict_job_name


@dsl.pipeline(
    name="strategic-stratification-cp-bigquery-inference-pipeline",
    description="Pipeline to run BigQuery feature engineering and batch inference for CP strategic stratification models"
)
def cp_strategic_stratification_inference_pipeline(
    project_id: str = PROJECT_ID,
    region: str = REGION,
    cmek_key: str = ENCRYPTION_KEY,
):
    #################################
    #   Feature Engineering Steps
    #################################

    sql_cohort = process_sql_file('cohort.sql', constants)
    run_create_cohort = components.query_bigquery_component(
        constants=constants,
        query=sql_cohort,
        display_name="create_cohort"
    )

    sql_claims = process_sql_file('claims.sql', constants)
    run_claims = components.query_bigquery_component(
        constants=constants,
        query=sql_claims,
        display_name="claims"
    )

    sql_medical_case = process_sql_file('med_case.sql', constants)
    run_medical_case = components.query_bigquery_component(
        constants=constants,
        query=sql_medical_case,
        display_name="medical_case"
    )

    sql_hpd = process_sql_file('HPD.sql', constants)
    run_hpd = components.query_bigquery_component(
        constants=constants,
        query=sql_hpd,
        display_name="HPD"
    )

    sql_physician_visits = process_sql_file('physician_visit_stats.sql', constants)
    run_physician_visits = components.query_bigquery_component(
        constants=constants,
        query=sql_physician_visits,
        display_name="physician_visits"
    )

    sql_cost_cv = process_sql_file('cost_cv.sql', constants)
    run_cost_cv = components.query_bigquery_component(
        constants=constants,
        query=sql_cost_cv,
        display_name="cost_cv"
    )

    sql_analytic = process_sql_file('analytic.sql', constants)
    run_analytic = components.query_bigquery_component(
        constants=constants,
        query=sql_analytic,
        display_name="analytic"
    )

    sql_combine = process_sql_file('combine_model_runs.sql', constants)
    run_combine = components.query_bigquery_component(
        constants=constants,
        query=sql_combine,
        display_name="combine_runs"
    )

    #################################
    #   Batch Inference Steps
    #################################

    cancer_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/3744967390530633728",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_cancer_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'emb131', 'emb169', 'emb186', 'uniq_dx_cd_cnt_3mo', 'emb14', 'change_q1_minus_q_2',
            'Oncologic_case_pre_12', 'other_spec_visits_pre_1', 'cost_9_12', 'pcp_visits_pre_9',
            'spec_visits_pre_6', 'emb194', 'emb116', 'lab_max_psa_1yr', 'emb94', 'emb238',
            'emb125', 'emb190', 'dx_cd_cnt_6mo', 'Endocrine_Metabolic_case_pre_12', 'emb42',
            'emb166', 'emb89', 'cancer_cv', 'Cardiac_case_pre_12', 'spec_visit_cnt_6mo', 'emb248',
            'cancer_visits_pre_9', 'prostate_cancer', 'emb145', 'emb152', 'Respiratory_case_pre_12',
            'emb250', 'cost_6_9', 'emb176', 'emb222', 'endo_cv', 'cancer_visits_pre_12', 'emb61',
            'emb6', 'emb80', 'emb74', 'emb118', 'emb233', 'emb46', 'spec_visits_pre_1', 'emb92',
            'emb57', 'emb66', 'emb197', 'emb244', 'pcp_visits_pre_1', 'emb91', 'colorectal_cancer',
            'lab_max_psa_2yr', 'emb170', 'lab_visit_cnt_2yr', 'Musculoskeletal_case_pre_12',
            'spec_visits_pre_12', 'emb185', 'emb31', 'age', 'emb225', 'emb202', 'change_q1_minus_q_3',
            'Digestive_case_pre_12', 'emb86', 'change_h_1_minus_h_2', 'emb149', 'lab_visit_cnt_3mo',
            'spec_visits_pre_9', 'emb29', 'card_visits_pre_12', 'leukemia_myeloma', 'emb110',
            'health_habits', 'emb35', 'breast_cancer', 'emb219', 'cancer_visits_pre_3', 'emb242',
            'emb224', 'cancer', 'dx_diff', 'Oncologic_case_pre_3', 'emb21', 'cost_0_3', 'pcp_cv',
            'emb187', 'emb73', 'emb175', 'social_risk_score', 'emb142', 'emb2', 'brain_cancer',
            'uniq_proc_cd_cnt_6mo', 'emb62', 'clm_ln_cnt_2yr', 'emb160', 'Obstetric_case_pre_12',
            'emb24', 'emb37', 'emb68', 'language_score', 'uniq_rev_cd_cnt_3mo', 'emb77', 'cost_3_6',
            'emb128', 'emb25', 'cancer_visits_pre_1', 'clm_ln_cnt_1yr', 'emb214', 'er_clm_cnt_6mo',
            'lab_visit_cnt_6mo', 'emb41', 'emb75', 'emb137', 'emb234', 'emb85', 'emb56', 'emb207',
            'Injury_Poisoning_case_pre_12', 'emb203', 'rx_diff', 'emb32', 'emb182', 'emb232',
            'uniq_proc_cd_cnt_3mo', 'emb228', 'Renal_case_pre_12', 'Neurologic_case_pre_12', 'emb33',
            'index_month', 'emb71', 'hpd_count', 'emb143', 'emb235', 'emb159', 'emb247', 'emb120',
            'emb236', 'other_cancer', 'Infectious_case_pre_12', 'emb45', 'emb64', 'emb181', 'emb180',
            'emb124', 'pcp_visits_pre_6', 'Oncologic_case_pre_6', 'emb114', 'emb220', 'emb227',
            'ortho_visits_pre_3', 'change_q1_minus_q_4', 'emb147',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_cancer',
    )

    cardiac_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/4904644294578536448",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_cardiac_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'emb177', 'emb54', 'pcp_cv', 'emb41', 'gender_cd', 'emb164', 'Obstetric_case_pre_12',
            'emb18', 'pharmacy_days_supply_1yr_cnt', 'emb179', 'uniq_rev_cd_cnt_2yr', 'mem_mos_12_pre',
            'cost_0_3', 'uniq_proc_cd_cnt_6mo', 'emb31', 'uniq_dx_cd_cnt_6mo', 'emb210', 'emb151',
            'Respiratory_case_pre_12', 'Neurologic_case_pre_6', 'congential_heart_disease', 'skin_cancer',
            'emb130', 'card_cv', 'emb50', 'ortho_cv', 'emb87', 'emb234', 'dx_cd_cnt_6mo',
            'pharmacy_days_supply_6mo_cnt', 'lab_max_glucose_2yr', 'ischemic_heart_disease', 'bh',
            'cerebrovascular_condition', 'card_visits_pre_3', 'emb105', 'emb229', 'hpd_major_flag',
            'pharmacy_gpi4_3mo_count', 'language_score', 'emb154', 'change_q1_minus_q_4', 'emb142',
            'emb99', 'emb218', 'emb36', 'drug_ind', 'heart_failure', 'emb195', 'index_month',
            'atrial_fibrillation', 'emb121', 'emb100', 'health_acess', 'emb225', 'lab_max_cholest_2yr',
            'card_visits_pre_9', 'dx_diff', 'spec_cv', 'uniq_dx_cd_cnt_1yr', 'emb94',
            'pharmacy_gpi4_6mo_count', 'ventricular_arrhythmia', 'emb79', 'emb156', 'mm_2yr_cnt',
            'emb212', 'emb112', 'emb48', 'emb111', 'uniq_dx_cd_cnt_3mo', 'emb88', 'age', 'emb134',
            'Neurologic_case_pre_12', 'emb131', 'er_clm_cnt_1yr', 'emb90', 'emb21', 'emb47',
            'Oncologic_case_pre_12', 'Cardiac_case_pre_3', 'emb44', 'emb140', 'emb205', 'emb106',
            'Injury_Poisoning_case_pre_12', 'emb232', 'emb240', 'emb128', 'emb124', 'emb113',
            'Musculoskeletal_case_pre_12', 'emb76', 'emb181', 'change_q1_minus_q_3', 'Renal_case_pre_12',
            'emb182', 'card_visits_pre_6', 'inflammatory_bowel_disease', 'er_clm_cnt_6mo', 'emb96',
            'Digestive_case_pre_12', 'emb126', 'Infectious_case_pre_12', 'uniq_rev_cd_cnt_1yr',
            'cancer', 'lab_max_creat_1yr', 'emb52', 'emb224', 'emb245', 'card_visits_pre_1',
            'lab_max_creat_2yr', 'emb91', 'Cardiac_case_pre_12', 'lab_max_hba1c_1yr', 'er_clm_cnt_2yr',
            'emb2', 'emb144', 'emb98', 'racial_diversity', 'emb16', 'emb159',
            'Endocrine_Metabolic_case_pre_12', 'emb85', 'clm_ln_cnt_1yr', 'emb123', 'hpd_count',
            'emb68', 'emb49', 'pharmacy_gpi4_1yr_count', 'card_visits_pre_12',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_cardiac',
    )

    digestive_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/5672508031045206016",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_digestive_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'pharmacy_days_supply_1yr_cnt', 'colorectal_cancer', 'emb66', 'inflammatory_bowel_disease',
            'emb211', 'ortho_visits_pre_12', 'emb110', 'cost_0_3', 'emb39', 'uniq_rev_cd_cnt_1yr',
            'emb154', 'emb205', 'air_qualtiy', 'emb158', 'emb118', 'change_q1_minus_q_2',
            'Renal_case_pre_12', 'emb233', 'emb89', 'emb64', 'emb2', 'emb62', 'emb246', 'emb65',
            'emb169', 'emb199', 'emb208', 'lab_visit_cnt_6mo', 'emb226', 'er_clm_cnt_2yr',
            'uniq_rev_cd_cnt_6mo', 'emb1', 'emb71', 'Cardiac_case_pre_12', 'emb70',
            'gastro_visits_pre_3', 'emb77', 'gastro_visits_pre_9', 'emb84', 'dx_cd_cnt_6mo',
            'emb196', 'emb37', 'pharmacy_disp_6mo_cnt', 'emb17', 'iron_deficiency_anemia', 'emb112',
            'emb197', 'gastro_visits_pre_1', 'emb103', 'emb31', 'emb41', 'emb45', 'emb109',
            'Digestive_case_pre_6', 'cancer', 'proactive_health', 'emb43', 'emb32',
            'Injury_Poisoning_case_pre_6', 'pharmacy_days_supply_2yr_cnt', 'emb11', 'emb122',
            'clm_ln_cnt_3mo', 'emb253', 'emb104', 'emb107', 'emb222', 'emb24', 'Digestive_case_pre_3',
            'bh', 'clm_ln_cnt_1yr', 'emb212', 'emb149', 'uniq_dx_cd_cnt_3mo', 'region_missing',
            'emb251', 'emb49', 'emb44', 'Endocrine_Metabolic_case_pre_12', 'uniq_rev_cd_cnt_2yr',
            'emb35', 'pcp_visits_pre_3', 'emb56', 'emb234', 'emb164', 'Musculoskeletal_case_pre_12',
            'uniq_dx_cd_cnt_1yr', 'gastro_visits_pre_6', 'emb125', 'Infectious_case_pre_12',
            'region_regW', 'emb136', 'lab_max_ggt_2yr', 'emb67', 'emb152', 'pcp_visits_pre_1',
            'change_q1_minus_q_3', 'er_clm_cnt_6mo', 'housing_quality', 'emb85', 'emb179',
            'other_spec_visits_pre_3', 'Infectious_case_pre_3', 'gastro_cv', 'emb102', 'dx_diff',
            'uniq_proc_cd_cnt_2yr', 'lab_max_bilirub_2yr', 'obstructive_sleep_apnea', 'emb215',
            'emb190', 'emb180', 'Respiratory_case_pre_12', 'emb4', 'emb225',
            'Injury_Poisoning_case_pre_12', 'emb74', 'lab_visit_cnt_1yr', 'other_spec_visits_pre_1',
            'emb12', 'emb82', 'emb188', 'pcp_visits_pre_6', 'cost_6_9', 'emb156', 'emb181',
            'Oncologic_case_pre_12', 'Obstetric_case_pre_12', 'emb27', 'age', 'emb61',
            'pcp_visit_cnt_2yr', 'emb242', 'Neurologic_case_pre_12', 'emb191', 'emb34', 'emb176',
            'cholelithiasis_cholecystitis', 'emb250', 'cost_3_6', 'card_visits_pre_12', 'emb111',
            'emb92', 'alcoholism', 'ortho_cv', 'Digestive_case_pre_12', 'emb254', 'emb55', 'emb63',
            'emb47', 'cataract', 'nonspecific_gastritis_dyspepsia', 'index_month', 'pancreatitis',
            'emb88', 'emb121', 'uniq_dx_cd_cnt_2yr', 'emb26', 'esophageal_cancer', 'emb182',
            'gastro_visits_pre_12', 'diverticular_disease', 'emb171', 'emb90', 'change_h_1_minus_h_2',
            'hpd_count', 'emb79', 'emb170', 'emb95',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_digestive',
    )

    endocrine_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/3366665021831512064",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_endocrine_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'endo_visits_pre_6', 'lab_max_psa_1yr', 'emb195', 'uniq_rev_cd_cnt_6mo', 'emb229',
            'chronic_obstructive_pulmonary_disease', 'ortho_visits_pre_6', 'lab_visit_cnt_6mo',
            'emb234', 'emb230', 'emb233', 'Oncologic_case_pre_12', 'Obstetric_case_pre_12',
            'lab_visit_cnt_1yr', 'uniq_proc_cd_cnt_1yr', 'emb80', 'rx_diff', 'clm_ln_cnt_2yr',
            'emb56', 'endo_visits_pre_9', 'emb190', 'emb242', 'emb146', 'emb199', 'index_month',
            'lab_max_hba1c_2yr', 'emb3', 'emb144', 'emb231', 'emb44', 'emb60', 'allergy',
            'language_score', 'emb128', 'emb110', 'uniq_rev_cd_cnt_1yr', 'emb246', 'lab_max_hba1c_1yr',
            'emb244', 'pharmacy_gpi4_3mo_count', 'emb51', 'Endocrine_Metabolic_case_pre_6',
            'pharmacy_days_supply_6mo_cnt', 'lab_max_glucose_1yr', 'emb29', 'pcp_visits_pre_9',
            'endo_visits_pre_12', 'emb47', 'emb134', 'other_spec_visits_pre_6', 'card_visits_pre_12',
            'emb183', 'emb67', 'emb120', 'emb63', 'emb125', 'Neurologic_case_pre_12', 'mm_2yr_cnt',
            'emb23', 'emb49', 'clm_ln_cnt_1yr', 'age', 'Renal_case_pre_12', 'emb123',
            'other_spec_visits_pre_1', 'emb94', 'emb232', 'Infectious_case_pre_12', 'emb96', 'emb107',
            'obesity', 'other_spec_visits_pre_3', 'emb7', 'emb168', 'emb193', 'dx_diff', 'emb197',
            'lab_max_glucose_2yr', 'emb200', 'emb43', 'lab_visit_cnt_2yr', 'diverticular_disease',
            'emb17', 'Respiratory_case_pre_12', 'emb20', 'emb203', 'emb187', 'emb196', 'emb111',
            'diabetes_mellitus', 'uniq_dx_cd_cnt_6mo', 'emb127', 'emb75',
            'Endocrine_Metabolic_case_pre_12', 'Injury_Poisoning_case_pre_12', 'cost_0_3', 'emb157',
            'ortho_visits_pre_12', 'Endocrine_Metabolic_case_pre_3', 'emb224', 'emb174',
            'Cardiac_case_pre_12', 'endo_cv', 'cost_6_9', 'emb211', 'emb8', 'uniq_proc_cd_cnt_6mo',
            'emb34', 'emb2', 'emb182', 'emb194', 'emb202', 'crime_score', 'emb71', 'ortho_visits_pre_1',
            'emb69', 'Digestive_case_pre_12', 'emb31', 'emb243', 'emb176', 'emb98', 'cancer',
            'chronic_thyroid_disorders', 'Musculoskeletal_case_pre_12',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_endocrine',
    )

    msk_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/954987421374611456",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_msk_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'emb208', 'ortho_visits_pre_9', 'emb5', 'emb113', 'pharmacy_gpi4_3mo_count', 'ortho_cv',
            'other_spec_visits_pre_6', 'emb250', 'emb187', 'emb95', 'glaucoma', 'emb82', 'emb162',
            'citizenship_index', 'emb203', 'health_infra', 'emb158', 'emb104', 'low_back_pain',
            'emb83', 'emb170', 'emb61', 'emb4', 'emb27', 'emb58', 'emb93', 'emb149', 'language_score',
            'uniq_dx_cd_cnt_6mo', 'uniq_dx_cd_cnt_2yr', 'Endocrine_Metabolic_case_pre_12', 'emb225',
            'emb188', 'other_spec_visits_pre_3', 'cost_6_9', 'spec_visits_pre_9', 'bh',
            'lab_visit_cnt_6mo', 'clm_ln_cnt_3mo', 'uniq_rev_cd_cnt_1yr', 'emb55', 'emb207',
            'pharmacy_gpi4_6mo_count', 'emb79', 'pharmacy_days_supply_6mo_cnt', 'uniq_dx_cd_cnt_3mo',
            'emb120', 'emb68', 'emb48', 'uniq_proc_cd_cnt_2yr', 'Neurologic_case_pre_12', 'emb249',
            'emb156', 'emb179', 'income_inequality', 'emb70', 'emb185', 'emb196', 'emb232',
            'parkinsons_disease', 'change_h_1_minus_h_2', 'cancer_visits_pre_9', 'emb78',
            'pharmacy_gpi4_1yr_count', 'emb109', 'lab_visit_cnt_1yr', 'emb205', 'emb226', 'emb94',
            'cost_3_6', 'Injury_Poisoning_case_pre_3', 'pcp_cv', 'emb86', 'emb105',
            'ortho_visits_pre_12', 'emb7', 'cancer', 'card_visits_pre_12', 'emb62', 'emb137', 'emb57',
            'Renal_case_pre_12', 'er_clm_cnt_1yr', 'emb246', 'emb195', 'pharmacy_days_supply_3mo_cnt',
            'substances_related_disorders', 'emb122', 'emb107', 'emb242', 'cost_0_3',
            'Musculoskeletal_case_pre_3', 'pharmacy_gpi4_2yr_count', 'emb121', 'emb134', 'osteoporosis',
            'ortho_visits_pre_1', 'depression', 'emb72', 'emb194', 'air_qualtiy', 'emb59', 'emb42',
            'Cardiac_case_pre_12', 'pcp_visit_cnt_1yr', 'emb33', 'emb157', 'emb77', 'emb118',
            'emb212', 'emb169', 'lab_max_hba1c_2yr', 'endo_cv', 'emb206', 'pulmo_visits_pre_9',
            'Injury_Poisoning_case_pre_12', 'Musculoskeletal_case_pre_12', 'emb214',
            'Oncologic_case_pre_12', 'change_q1_minus_q_4', 'unemployment_index', 'emb45',
            'other_spec_visits_pre_9', 'emb235', 'dx_diff', 'emb22', 'gastro_visits_pre_6',
            'Infectious_case_pre_12', 'emb240', 'change_q1_minus_q_3', 'emb216', 'hpd_count',
            'emb150', 'emb75', 'racial_diversity', 'uniq_dx_cd_cnt_1yr', 'emb154', 'emb238',
            'osteoarthritis', 'spec_cv', 'emb21', 'emb224', 'Respiratory_case_pre_12', 'mm_2yr_cnt',
            'gender_cd', 'pharmacy_disp_2yr_cnt', 'clm_ln_cnt_1yr', 'emb130', 'emb119', 'neuro_cv',
            'dx_cd_cnt_6mo', 'emb91', 'emb85', 'emb253', 'emb220', 'emb176', 'other_spec_visits_pre_12',
            'Obstetric_case_pre_12', 'index_month', 'emb30', 'Digestive_case_pre_12', 'lab_visit_cnt_2yr',
            'lab_visit_cnt_3mo', 'alcoholism', 'emb69', 'emb197', 'obesity', 'emb56',
            'ortho_visits_pre_3', 'age', 'emb227', 'emb132', 'emb204', 'pharmacy_days_supply_1yr_cnt',
            'pharmacy_disp_1yr_cnt',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_msk',
    )

    neuro_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/3249571431519879168",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_neuro_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'pharmacy_gpi4_3mo_count', 'clm_ln_cnt_1yr', 'pharmacy_disp_1yr_cnt', 'lab_visit_cnt_2yr',
            'emb62', 'emb134', 'emb247', 'Musculoskeletal_case_pre_12', 'emb104', 'emb174',
            'Respiratory_case_pre_12', 'emb154', 'hpd_major_flag', 'Endocrine_Metabolic_case_pre_12',
            'clm_ln_cnt_3mo', 'pharmacy_disp_6mo_cnt', 'urg_cv', 'emb31', 'emb188', 'emb2', 'emb113',
            'neuro_cv', 'emb181', 'neuro_visits_pre_6', 'Renal_case_pre_12', 'emb47',
            'neuro_visits_pre_12', 'emb242', 'cost_6_9', 'emb218', 'emb74', 'endo_cv', 'dx_diff',
            'emb200', 'emb129', 'card_visits_pre_12', 'emb163', 'pharmacy_days_supply_3mo_cnt',
            'emb225', 'cost_9_12', 'emb50', 'hpd_count', 'age', 'emb167', 'other_spec_visits_pre_9',
            'emb126', 'emb94', 'uniq_rev_cd_cnt_6mo', 'Cardiac_case_pre_12', 'index_month',
            'uniq_dx_cd_cnt_6mo', 'emb162', 'emb131', 'emb221', 'Obstetric_case_pre_12',
            'Neurologic_case_pre_12', 'er_clm_cnt_2yr', 'emb101', 'change_h_1_minus_h_2', 'emb224',
            'Infectious_case_pre_12', 'emb33', 'cost_3_6', 'emb26', 'natural_disaster',
            'Injury_Poisoning_case_pre_12', 'health_acess', 'emb217', 'emb197', 'uniq_rev_cd_cnt_3mo',
            'uniq_dx_cd_cnt_2yr', 'emb25', 'pharmacy_days_supply_2yr_cnt', 'emb81', 'cost_0_3',
            'lab_max_triglyc_1yr', 'epilepsy', 'emb65', 'emb246', 'emb34', 'emb118',
            'Oncologic_case_pre_12', 'lab_max_bilirub_1yr', 'mm_1yr_cnt', 'Neurologic_case_pre_3',
            'emb106', 'Neurologic_case_pre_6', 'emb236', 'emb178', 'uniq_dx_cd_cnt_3mo',
            'neuro_visits_pre_3', 'emb43', 'emb97', 'Digestive_case_pre_12', 'uniq_proc_cd_cnt_6mo',
            'emb139', 'emb173', 'emb45', 'multiple_sclerosis', 'depression', 'emb170', 'emb0',
            'neuro_visits_pre_9', 'parkinsons_disease', 'emb18', 'emb49', 'emb88', 'emb244',
            'cerebrovascular_disease', 'dementia', 'emb109',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_neuro',
    )

    resp_inference = vertex_batch_predict_bigquery_component(
        project=project_id,
        service_account=constants["service_account"],
        cmek_key=cmek_key,
        location=region,
        cost_center=constants["COSTCENTER"],
        owner=constants["OWNER"],
        model_resource_name="projects/46378383599/locations/us-east4/models/7293803896898584576",
        key_field="individual_id",
        input_table=constants["dec_database_name"] + "." + constants["prefix"] + "_analytic",
        output_table=constants["dec_database_name"] + "." + constants["prefix"] + "_resp_model",
        compute_dataset=constants["COMPUTE_DATASET"],
        expiration_days=31,
        excluded_fields=["individual_id", "index_dt"],
        selected_features=[
            'Infectious_case_pre_3', 'emb153', 'Endocrine_Metabolic_case_pre_12', 'head_neck_cancer',
            'emb139', 'emb92', 'emb100', 'Infectious_case_pre_12', 'emb62', 'clm_ln_cnt_2yr', 'emb3',
            'emb142', 'mem_mos_12_pre', 'emb89', 'emb227', 'emb46', 'pulmo_visits_pre_12', 'emb219',
            'emb108', 'emb129', 'emb31', 'index_month', 'Respiratory_case_pre_12', 'emb220', 'emb172',
            'Neurologic_case_pre_12', 'congential_heart_disease', 'pharmacy_gpi4_6mo_count', 'emb54',
            'endo_cv', 'emb255', 'lab_max_altsgpt_2yr', 'emb52', 'emb35',
            'Musculoskeletal_case_pre_12', 'language_score', 'emb25', 'esophageal_cancer', 'emb199',
            'emb94', 'uniq_dx_cd_cnt_2yr', 'emb96', 'emb59', 'emb204', 'emb229',
            'Oncologic_case_pre_3', 'mm_2yr_cnt', 'proactive_health', 'emb48', 'Digestive_case_pre_12',
            'Renal_case_pre_12', 'emb69', 'emb110', 'emb10', 'spec_visit_cnt_6mo', 'emb147', 'emb91',
            'hpd_count', 'pharmacy_gpi4_3mo_count', 'oral_cancer', 'pulmo_visits_pre_9', 'emb44',
            'emb224', 'cancer_visits_pre_6', 'er_clm_cnt_3mo', 'uniq_rev_cd_cnt_1yr', 'emb23', 'emb6',
            'food_access', 'emb7', 'emb101', 'lab_visit_cnt_2yr', 'pharmacy_days_supply_6mo_cnt',
            'change_q1_minus_q_4', 'emb70', 'card_visits_pre_12', 'uniq_dx_cd_cnt_3mo', 'emb192',
            'asthma', 'technology_access', 'uniq_dx_cd_cnt_1yr', 'emb47', 'emb182',
            'Obstetric_case_pre_12', 'cost_6_9', 'uniq_rev_cd_cnt_3mo', 'emb16', 'emb126', 'emb149',
            'emb36', 'emb177', 'unemployment_index', 'emb240', 'Cardiac_case_pre_12', 'clm_ln_cnt_1yr',
            'chronic_renal_failure', 'pulmo_visits_pre_1', 'emb230', 'cost_3_6', 'age', 'emb88',
            'dx_cd_cnt_6mo', 'emb235', 'emb215', 'emb63', 'emb98', 'emb17', 'emb196', 'rx_diff',
            'pharmacy_days_supply_3mo_cnt', 'emb211', 'emb166', 'emb60', 'emb55',
            'Oncologic_case_pre_12', 'emb186', 'emb244', 'emb50', 'emb53', 'emb170',
            'pharmacy_gpi4_2yr_count', 'emb117', 'chronic_obstructive_pulmonary_disease', 'emb64',
            'emb72', 'emb49', 'citizenship_index', 'emb181', 'emb87', 'emb214',
            'change_q1_minus_q_2', 'emb161', 'emb122', 'emb203', 'other_spec_cv', 'emb191', 'cost_0_3',
            'emb13', 'Injury_Poisoning_case_pre_12', 'lab_visit_cnt_6mo', 'mm_1yr_cnt', 'emb104',
            'emb156', 'lab_max_hba1c_2yr', 'emb210', 'emb136', 'emb127', 'spec_visit_cnt_3mo',
            'emb21', 'emb33', 'clm_ln_cnt_3mo', 'emb248', 'emb150', 'emb141',
        ],
        machine_type={"machine_type": "n2-standard-16"},
        starting_replica_count=80,
        max_replica_count=80,
        batch_size=1024,
        informal_model_name='ss_resp',
    )

    #################################
    #   DAG Dependencies
    #################################

    run_claims.after(run_create_cohort)

    parallel_feature_tasks = [
        run_medical_case,
        run_hpd,
        run_physician_visits,
        run_cost_cv,
    ]
    for task in parallel_feature_tasks:
        task.after(run_claims)

    run_analytic.after(*parallel_feature_tasks)

    # Inference runs in batched waves to control concurrency
    wave_1 = [cancer_inference, cardiac_inference]
    wave_2 = [digestive_inference, endocrine_inference]
    wave_3 = [msk_inference, neuro_inference]

    for task in wave_1:
        task.after(run_analytic)
    for task in wave_2:
        task.after(*wave_1)
    for task in wave_3:
        task.after(*wave_2)

    resp_inference.after(*wave_3)
    run_combine.after(resp_inference)


if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=cp_strategic_stratification_inference_pipeline,
        package_path="cp_strategic_strat_inference.json"
    )

    # Initialize Vertex AI client
    aiplatform.init(
        project=PROJECT_ID,
        location=REGION,
        credentials=target_credentials
    )

    # Define the pipeline job
    pipeline_job = aiplatform.PipelineJob(
        display_name="cp-strategic-stratification-inference-pipeline",
        template_path="cp_strategic_strat_inference.json",
        pipeline_root=PIPELINE_ROOT,
        encryption_spec_key_name=ENCRYPTION_KEY,
        enable_caching=False,
        parameter_values={
            "project_id": PROJECT_ID,
            "region": REGION,
            "cmek_key": ENCRYPTION_KEY,
        },
        labels={
            "owner": constants["OWNER"],
            "pipeline_type": "model_prediction",
            "lob": constants["LOB"],
            "costcenter": constants["COSTCENTER"],
            "tenant": constants["TENANT"],
        }
    )

    # Delete any existing schedules before re-creating
    schedules = aiplatform.PipelineJobSchedule.list(
        filter='display_name="cp-strategic-stratification-inference-pipeline"',
        order_by="create_time desc",
        project=PROJECT_ID,
        location=REGION,
    )

    if not schedules:
        print("No schedules found matching the filter")
    else:
        print(f"Found {len(schedules)} schedule(s) to delete")
        for schedule in schedules:
            try:
                print(f"\nDeleting schedule:")
                print(f"  Display Name: {schedule.display_name}")
                print(f"  Resource ID:  {schedule.resource_name}")
                print(f"  State:        {schedule.state}")

                if schedule.state.name == "ACTIVE":
                    print("  Pausing schedule before deletion...")
                    schedule.pause()

                schedule.delete(sync=True)
                print(f"  Successfully deleted")

            except Exception as e:
                print(f"  Error deleting {schedule.resource_name}: {str(e)}")

    pipeline_job.create_schedule(
        display_name="cp-strategic-stratification-inference-pipeline",
        cron=cron_schedule,
        max_concurrent_run_count=1,
        service_account=TARGET_SERVICE_ACCOUNT,
    )

    if ENV in ["dev", "test"]:
        pipeline_job.run(service_account=TARGET_SERVICE_ACCOUNT, sync=True)
