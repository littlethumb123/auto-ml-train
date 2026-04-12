import os
import sys
from google.cloud import aiplatform
from google.auth import impersonated_credentials
import google.auth

def run_pipeline_from_bucket():
    """Runs a pre-compiled pipeline from a JSON file."""
    
    # Get the source credentials and set up impersonation
    source_credentials, _ = google.auth.default()
    target_service_account = os.environ.get('IMPERSONATED_SERVICE_ACCOUNT')
    pipeline_file_name = os.environ.get('PIPELINE_TEMPLATE_PATH')
    
    if not pipeline_file_name:
        print("Error: PIPELINE_TEMPLATE_PATH environment variable not set!")
        sys.exit(1)
    
    print(f"Impersonating service account: {target_service_account}")
    print(f"Using pipeline file: {pipeline_file_name}")

    # Create impersonated credentials
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=target_service_account,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    # Initialize the Vertex AI client with impersonated credentials
    aiplatform.init(
        project="anbc-dev-hcm-cm-de",
        location="us-east4",
        credentials=target_credentials
    )

    print(f"Initialized Vertex AI with project: anbc-dev-hcm-cm-de, location: us-east4")

    # Define the pipeline job using the pre-compiled JSON
    pipeline_job = aiplatform.PipelineJob(
        display_name="pipeline-from-bucket",
        template_path=pipeline_file_name,  # This should be the downloaded JSON file
        pipeline_root="gs://hcm-cm-de-code-hcb-dev/vertex-test/",
        parameter_values={},
        encryption_spec_key_name="projects/cvs-key-vault-nonprod/locations/us-east4/keyRings/gkr-nonprod-us-east4/cryptoKeys/gk-anbc-dev-hcm-cm-de-us-east4"
    )

    print("Created pipeline job, submitting...")

    # Submit the pipeline job
    pipeline_job.run(
        service_account=target_service_account,
        sync=True
    )

    print("Pipeline job submitted successfully!")

if __name__ == "__main__":
    run_pipeline_from_bucket()