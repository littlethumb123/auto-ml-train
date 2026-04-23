# Import necessary libraries
import os
from kfp.v2 import dsl
from kfp.v2.dsl import component
from kfp.v2 import compiler
from google.cloud import aiplatform
from google.auth import impersonated_credentials
from google.oauth2 import service_account
import google.auth

# Define a simple component
@component(base_image="python:3.9", packages_to_install=["pandas==2.2.0", "numpy"])
def hello_world_component():
    import pandas as pd
    print("Hello, World!")

# Define the pipeline
@dsl.pipeline(
    name="hello-world-pipeline",
    description="A simple Hello World pipeline"
)
def hello_world_pipeline():
    hello_world_component()

# Compile the pipeline
if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=hello_world_pipeline,
        package_path="hello_world_pipeline.json"
    )

# Get environment variables
project_id = os.environ.get('PROJECT_ID') or os.environ.get('GOOGLE_CLOUD_PROJECT')
region = os.environ.get('REGION', 'us-east4')
pipeline_root = os.environ.get('PIPELINE_ROOT')
encryption_key = os.environ.get('ENCRYPTION_KEY')
target_service_account = os.environ.get('IMPERSONATED_SERVICE_ACCOUNT') or os.environ.get('TARGET_SERVICE_ACCOUNT')
pipeline_service_account = os.environ.get('TARGET_SERVICE_ACCOUNT')

# Validate required environment variables
if not project_id:
    raise ValueError("PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable is required")
if not pipeline_root:
    raise ValueError("PIPELINE_ROOT environment variable is required")
if not target_service_account:
    raise ValueError("IMPERSONATED_SERVICE_ACCOUNT or TARGET_SERVICE_ACCOUNT environment variable is required")
if not pipeline_service_account:
    raise ValueError("TARGET_SERVICE_ACCOUNT environment variable is required")

print(f"Impersonating service account: {target_service_account}")

# Get the source credentials and set up impersonation
source_credentials, _ = google.auth.default()

# Create impersonated credentials
target_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal=target_service_account,
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

# Initialize the Vertex AI client with impersonated credentials
aiplatform.init(
    project=project_id,
    location=region,
    credentials=target_credentials
)

print(f"Initialized Vertex AI with project: {project_id}, location: {region}")
print(f"Using impersonated credentials for: {target_service_account}")

# Define the pipeline job
pipeline_job = aiplatform.PipelineJob(
    display_name="simple-hello-pipeline",
    template_path="hello_world_pipeline.json",
    pipeline_root=pipeline_root,
    parameter_values={},
    enable_caching=False,
    encryption_spec_key_name=encryption_key
)

print("Created pipeline job, submitting...")

# Submit the pipeline job
pipeline_job.run(
    service_account=pipeline_service_account,
    sync=True
)

print("Pipeline job submitted successfully!")