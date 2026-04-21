import os
from typing import Dict, Any
import kfp
from kfp import dsl
from kfp.dsl import component, pipeline, Input, Output, Artifact
from google.cloud import bigquery
import json

@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-bigquery==3.11.4",
        "google-auth==2.23.4",
    ]
)
def execute_sql_query(
    query_name: str,
    sql_query: str,
    config: Dict[str, Any],
    previous_step_complete: str = ""
) -> str:
    """Execute a BigQuery SQL query with variable substitution."""
    import logging
    from google.cloud import bigquery
    import time
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize BigQuery client
        client = bigquery.Client(project=config["GCP_PROJECT"])
        
        # Substitute variables in the SQL query
        formatted_query = sql_query.format(**config)
        
        logger.info(f"Executing query: {query_name}")
        logger.info(f"Query: {formatted_query[:500]}...")  # Log first 500 chars
        
        # Execute the query
        query_job = client.query(formatted_query)
        
        # Wait for the job to complete
        results = query_job.result()
        
        # Log results
        logger.info(f"Query {query_name} completed successfully")
        logger.info(f"Job ID: {query_job.job_id}")
        logger.info(f"Bytes processed: {query_job.total_bytes_processed}")
        logger.info(f"Slot milliseconds: {query_job.slot_millis}")
        
        if query_job.errors:
            logger.error(f"Query errors: {query_job.errors}")
            raise Exception(f"BigQuery job failed with errors: {query_job.errors}")
            
        return f"Query {query_name} completed successfully at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
    except Exception as e:
        logger.error(f"Error executing query {query_name}: {str(e)}")
        raise Exception(f"Failed to execute query {query_name}: {str(e)}")

@component(
    base_image="python:3.9",
    packages_to_install=["google-cloud-bigquery==3.11.4"]
)
def load_sql_query(query_file_path: str) -> str:
    """Load SQL query from file path."""
    import os
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # For now, we'll embed the queries directly since we can't easily read from GCS
        # This is a simplified version - in production you'd read from GCS bucket
        
        sql_queries = {
            "002_Med_Claims_yr1": """
-- Medical Claims Year 1 Query
DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_yr1`;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_yr1`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
       st.asdb_member_key,
       clm.asdb_plan_key,
       st.index_dt,
       clm.claimid,
       clm.asdb_coe_id,
       coe.asdb_coe_general_type,
       coe.asdb_coe_sub_cat,
       clm.asdb_svc_prov_key,
       clm.asdb_pcp_prov_key,
       CAST(clm.asdb_incurred_dt AS DATE) AS asdb_incurred_dt,
       CAST(clm.asdb_paid_dt AS DATE) AS asdb_paid_dt,
       clm.location,
       clm.revcode,
       clm.servcode,
       clm.billtype,
       clm.prindiag,
       clm.paid_amt,
       clm.emis_cat
FROM 
       (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{ST}`) AS st
INNER JOIN 
       (WITH latest_partitions AS 
           (SELECT
               asdb_member_key,
               asdb_plan_key,
               claimid,
               asdb_svc_prov_key,
               asdb_pcp_prov_key,
               asdb_incurred_dt,
               asdb_paid_dt,
               location,
               revcode,
               servcode,
               billtype,
               prindiag,
               paid_amt,
               emis_cat,
               insert_dts AS date,
               final_claim,
               status_header,
               status_detail,
               asdb_coe_id
            FROM 
                `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE`
            WHERE 
                CAST(insert_dts AS DATE) > DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)
           )
           SELECT * 
           FROM latest_partitions
           WHERE date = (SELECT MAX(date) FROM latest_partitions)
                AND final_claim = 1
                AND TRIM(UPPER(status_header)) = "PAID"
                AND TRIM(UPPER(status_detail)) NOT IN ("DENY", "DENIED")
        ) AS clm ON st.asdb_member_key = clm.asdb_member_key
LEFT JOIN 
       `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_TYPE_OF_SERVICE` AS coe
              ON clm.asdb_coe_id = coe.asdb_coe_id
WHERE 1 = 1
         AND CAST(asdb_incurred_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 12 MONTH) AND DATE_SUB(st.index_dt, INTERVAL 1 DAY)
         AND CAST(asdb_paid_dt AS DATE) < CAST(index_dt AS DATE);
""",
            "002_Med_Claims_yr2": """
-- Medical Claims Year 2 Query
DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_yr2`;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_yr2`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
       st.asdb_member_key,
       st.asdb_plan_key,
       st.index_dt,
       clm.claimid,
       clm.asdb_coe_id,
       coe.asdb_coe_general_type,
       coe.asdb_coe_sub_cat,
       clm.asdb_svc_prov_key,
       clm.asdb_pcp_prov_key,
       CAST(clm.asdb_incurred_dt AS DATE) AS asdb_incurred_dt,
       CAST(clm.asdb_paid_dt AS DATE) AS asdb_paid_dt,
       clm.location,
       clm.revcode,
       clm.servcode,
       clm.billtype,
       clm.prindiag,
       clm.paid_amt,
       clm.emis_cat
FROM 
       (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{ST}`) AS st
INNER JOIN 
       (WITH latest_partitions AS 
           (SELECT
               asdb_member_key,
               asdb_plan_key,
               claimid,
               asdb_svc_prov_key,
               asdb_pcp_prov_key,
               asdb_incurred_dt,
               asdb_paid_dt,
               location,
               revcode,
               servcode,
               billtype,
               prindiag,
               paid_amt,
               emis_cat,
               insert_dts AS date,
               final_claim,
               status_header,
               status_detail,
               asdb_coe_id
            FROM 
                `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE`
            WHERE 
                CAST(insert_dts AS DATE) > DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)
           )
           SELECT * 
           FROM latest_partitions
           WHERE date = (SELECT MAX(date) FROM latest_partitions)
                AND final_claim = 1
                AND TRIM(UPPER(status_header)) = "PAID"
                AND TRIM(UPPER(status_detail)) NOT IN ("DENY", "DENIED")
        ) AS clm ON st.asdb_member_key = clm.asdb_member_key
LEFT JOIN 
       `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_TYPE_OF_SERVICE` AS coe
              ON clm.asdb_coe_id = coe.asdb_coe_id
WHERE 1 = 1
         AND CAST(asdb_incurred_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 24 MONTH) AND DATE_SUB(DATE_SUB(st.index_dt, INTERVAL 1 DAY), INTERVAL 12 MONTH)
         AND CAST(asdb_paid_dt AS DATE) < CAST(index_dt AS DATE);
""",
            # Add more queries here as needed
            "013_non_embedding_feature_beast": """
-- Final feature consolidation query
DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_non_embedding_features`;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_non_embedding_features`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    st.asdb_member_key,
    st.asdb_plan_key,
    st.index_dt
    -- Add other columns as needed based on available tables
FROM (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{ST}`) AS st;
"""
        }
        
        query_name = os.path.basename(query_file_path).replace('.sql', '')
        
        if query_name in sql_queries:
            logger.info(f"Loaded SQL query for {query_name}")
            return sql_queries[query_name]
        else:
            raise Exception(f"Query {query_name} not found in embedded queries")
            
    except Exception as e:
        logger.error(f"Error loading query {query_file_path}: {str(e)}")
        raise Exception(f"Failed to load query {query_file_path}: {str(e)}")

@pipeline(
    name="sequential-sql-pipeline",
    description="Execute SQL queries in sequence for data pipeline"
)
def sequential_sql_pipeline(
    gcp_project: str = "anbc-hcb-dev",
    gcp_db: str = "cm_medicaid_hcb_dev",
    prefix: str = "a534354_mat_v2",
    owner: str = "palmere1_aetna_com",
    cost_center: str = "13070",
):
    """Pipeline that executes SQL queries in sequence."""
    
    # Configuration dictionary
    config = {
        "GCP_PROJECT": gcp_project,
        "GCP_DB": gcp_db,
        "PREFIX": prefix,
        "OWNER": owner,
        "COST_CENTER": cost_center,
        "DEFAULT_EXP": "INTERVAL 180 DAY",
        "SDOH_YEAR": "2023",
        "ST": f"{gcp_project}.{gcp_db}.{prefix}_st"
    }
    
    # Define the execution order
    query_order = [
        "002_Med_Claims_yr1",
        "002_Med_Claims_yr2",
        "013_non_embedding_feature_beast"  # Simplified for now
    ]
    
    previous_step = None
    
    for query_name in query_order:
        # Load SQL query
        load_query_task = load_sql_query(query_file_path=f"{query_name}.sql")
        load_query_task.set_display_name(f"Load {query_name} Query")
        
        # Execute SQL query
        execute_task = execute_sql_query(
            query_name=query_name,
            sql_query=load_query_task.output,
            config=config,
            previous_step_complete=previous_step.output if previous_step else ""
        )
        execute_task.set_display_name(f"Execute {query_name}")
        
        # Add dependency if there was a previous step
        if previous_step:
            execute_task.after(previous_step)
            
        previous_step = execute_task

if __name__ == "__main__":
    # Compile the pipeline
    from kfp import compiler
    
    compiler.Compiler().compile(
        pipeline_func=sequential_sql_pipeline,
        package_path="sequential_sql_pipeline.json"
    )
    
    print("Pipeline compiled successfully to sequential_sql_pipeline.json")
