from google_cloud_pipeline_components.v1 import bigquery
from kfp.v2.dsl import component, pipeline, Output
from kfp.v2 import compiler
from google.cloud import aiplatform
#Test
# Define a custom transformation component
@component(base_image="us-east4-docker.pkg.dev/anbc-dev-hcm-cm-de/hcm-cm-de-docker/ai-pipelines-test:2025-04-07")
def transform_data(input_table: str, output_table: str) -> str:
    import pandas as pd
    from google.cloud import bigquery

    # Initialize BigQuery client
    client = bigquery.Client()

    # Read data from the input table
    query = f"SELECT column_name, hist_mean FROM `{input_table}`"
    df = client.query(query).to_dataframe()

    # Apply a transformation (e.g., adding a new column)
    if 'hist_mean' in df.columns:
        df['hist_mean_transform'] = df['hist_mean'] * 2  # Example transformation
    else:
        raise ValueError("Column 'hist_mean' not found in the input table.")

    # Write transformed data to the output BigQuery table
    client.load_table_from_dataframe(df, output_table).result()

    return output_table

# Define the pipeline
@pipeline(name="bq-transform-pipeline", pipeline_root="gs://hcm-cm-de-code-hcb-dev/vertex-test/")
def bq_pipeline():
    # Step 1: Read data from BigQuery
    bq_read_op = bigquery.BigqueryQueryJobOp(
        query="SELECT column_name, num_rows, 0 AS test1, num_rows*2 as test2 FROM `anbc-hcb-dev.clin_analytics_hcb_dev.data_quality_metrics`",
        destination_table=Output[bigquery.BQTable],  # Define the output artifact for the destination table
        location="US",
        write_disposition="WRITE_TRUNCATE",
    )

    # Step 2: Transform the data
    transform_op = transform_data(
        input_table="anbc-hcb-dev.clin_analytics_hcb_dev.data_quality_metrics",
        output_table="anbc-hcb-dev.clin_analytics_hcb_dev.data_quality_metrics_temp2",
    )

    # Step 3: Write transformed data back to BigQuery
    bq_write_op = bigquery.BigqueryQueryJobOp(
        query=f"SELECT * FROM `{transform_op.output}`",
        destination_table=Output[bigquery.BQTable],  # Define the output artifact for the final table
        location="US",
        write_disposition="WRITE_TRUNCATE",
    )

# Compile the pipeline
compiler.Compiler().compile(
    pipeline_func=bq_pipeline,
    package_path="bq_transform_pipeline.json",
)

# Initialize Vertex AI
aiplatform.init(
    project="anbc-dev-hcm-cm-de",
    location="us-east4",
)

# Define and run the pipeline job
pipeline_job = aiplatform.PipelineJob(
    display_name="bq-transform-pipeline",
    template_path="bq_transform_pipeline.json",
    pipeline_root="gs://hcm-cm-de-code-hcb-dev/vertex-test/",
    parameter_values={},
    encryption_spec_key_name="projects/cvs-key-vault-nonprod/locations/us-east4/keyRings/gkr-nonprod-us-east4/cryptoKeys/gk-anbc-dev-hcm-cm-de-us-east4",
)

pipeline_job.run(
    service_account="gchcb-hcm-cm-de-ontpd@anbc-dev-hcm-cm-de.iam.gserviceaccount.com",
    sync=True
)