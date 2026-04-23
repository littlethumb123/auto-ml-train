import os
import sys
import atexit
from google.cloud import aiplatform
from google.auth import impersonated_credentials
import google.auth

def cleanup_pipeline_file(pipeline_file_name):
    """Clean up the downloaded pipeline file."""
    try:
        if os.path.exists(pipeline_file_name):
            os.remove(pipeline_file_name)
            print(f"Cleaned up pipeline file: {pipeline_file_name}")
    except Exception as e:
        print(f"Warning: Could not cleanup pipeline file {pipeline_file_name}: {e}")

def run_pipeline():
    """Runs a pre-compiled pipeline from a JSON/YAML file in specified environment."""
    
    # Get environment variables
    environment = os.environ.get('ENVIRONMENT')
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    target_service_account = os.environ.get('IMPERSONATED_SERVICE_ACCOUNT')
    pipeline_file_name = os.environ.get('PIPELINE_TEMPLATE_PATH')
    pipeline_root = os.environ.get('PIPELINE_ROOT')
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    
    # Register cleanup function
    atexit.register(cleanup_pipeline_file, pipeline_file_name)
    
    # Validate required environment variables
    required_vars = {
        'ENVIRONMENT': environment,
        'GOOGLE_CLOUD_PROJECT': project_id,
        'IMPERSONATED_SERVICE_ACCOUNT': target_service_account,
        'PIPELINE_TEMPLATE_PATH': pipeline_file_name,
        'PIPELINE_ROOT': pipeline_root,
        'ENCRYPTION_KEY': encryption_key
    }
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            print(f"Error: {var_name} environment variable not set!")
            sys.exit(1)
    
    print(f"Running pipeline in {environment.upper()} environment")
    print(f"Project: {project_id}")
    print(f"Impersonating service account: {target_service_account}")
    print(f"Using pipeline file: {pipeline_file_name}")
    print(f"Pipeline root: {pipeline_root}")

    # Check if the file exists
    if not os.path.exists(pipeline_file_name):
        print(f"Error: Pipeline file '{pipeline_file_name}' not found!")
        sys.exit(1)

    try:
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
            location="us-east4",
            credentials=target_credentials
        )

        print(f"Initialized Vertex AI with project: {project_id}, location: us-east4")

        # Create display name with environment suffix
        display_name = f"pipeline-from-bucket-{environment}"

        # Define the pipeline job using the pre-compiled JSON/YAML
        pipeline_job = aiplatform.PipelineJob(
            display_name=display_name,
            template_path=pipeline_file_name,
            pipeline_root=pipeline_root,
            parameter_values={},
            enable_caching=False,
            encryption_spec_key_name=encryption_key
        )

        print("Created pipeline job, submitting...")

        # Submit the pipeline job
        pipeline_job.run(
            service_account=target_service_account,
            sync=True
        )

        print(f"Pipeline job submitted successfully to {environment.upper()} environment!")

    except Exception as e:
        print(f"Error running pipeline: {e}")
        sys.exit(1)
    finally:
        # Cleanup will be handled by atexit, but we can also do it explicitly
        cleanup_pipeline_file(pipeline_file_name)

if __name__ == "__main__":
    run_pipeline()