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

# Get the source credentials and set up impersonation
source_credentials, _ = google.auth.default()

target_service_account = os.environ.get('IMPERSONATED_SERVICE_ACCOUNT')
print(f"Impersonating service account: {target_service_account}")

# Create impersonated credentials
target_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal=target_service_account,
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

# Initialize the Vertex AI client with impersonated credentials
aiplatform.init(
    project="anbc-test-hcm-cm-de",
    location="us-east4",
    credentials=target_credentials
)

print(f"Initialized Vertex AI with project: anbc-test-hcm-cm-de, location: us-east4")
print(f"Using impersonated credentials for: {target_service_account}")

# Define the pipeline job
pipeline_job = aiplatform.PipelineJob(
    display_name="simple-hello-pipeline",
    template_path="hello_world_pipeline.json",
    pipeline_root="gs://hcm-cm-de-code-hcb-test/vertex-test/",
    parameter_values={},
    enable_caching=False,
    encryption_spec_key_name="projects/cvs-key-vault-nonprod/locations/us-east4/keyRings/gkr-nonprod-us-east4/cryptoKeys/gk-anbc-test-hcm-cm-de-us-east4"
)

print("Created pipeline job, submitting...")

# Submit the pipeline 
pipeline_job.run(
    service_account="gchcb-hcm-cm-de-onppq@anbc-test-hcm-cm-de.iam.gserviceaccount.com",
    sync=True
)

print("Pipeline job submitted successfully!")
