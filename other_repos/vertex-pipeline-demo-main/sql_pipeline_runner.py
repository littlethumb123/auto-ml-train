"""
Vertex AI Pipeline Runner for Sequential SQL Execution
This script creates and runs a pipeline that executes SQL queries in sequence.
"""

import os
import json
from google.cloud import aiplatform
from google.auth import impersonated_credentials
import google.auth
from typing import Dict, Any


class SQLPipelineRunner:
    """Runs the sequential SQL pipeline on Vertex AI."""
    
    def __init__(self, 
                 project_id: str,
                 region: str = "us-central1",
                 service_account: str = None):
        """Initialize the pipeline runner."""
        self.project_id = project_id
        self.region = region
        self.service_account = service_account
        
        # Initialize Vertex AI
        if service_account:
            credentials = self._get_impersonated_credentials(service_account)
            aiplatform.init(project=project_id, location=region, credentials=credentials)
        else:
            aiplatform.init(project=project_id, location=region)
    
    def _get_impersonated_credentials(self, target_service_account: str):
        """Get impersonated service account credentials."""
        source_credentials, _ = google.auth.default()
        target_credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=target_service_account,
            target_scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        return target_credentials
    
    def run_pipeline(self, 
                     pipeline_config: Dict[str, Any],
                     pipeline_root: str,
                     encryption_key: str = None) -> None:
        """Run the sequential SQL pipeline."""
        
        try:
            # Compile the pipeline first
            self._compile_pipeline()
            
            # Create pipeline job
            job = aiplatform.PipelineJob(
                display_name=f"sequential-sql-pipeline-{pipeline_config.get('PREFIX', 'default')}",
                template_path="sequential_sql_pipeline.json",
                pipeline_root=pipeline_root,
                parameter_values={
                    "gcp_project": pipeline_config.get("GCP_PROJECT"),
                    "gcp_db": pipeline_config.get("GCP_DB"),
                    "prefix": pipeline_config.get("PREFIX"),
                    "owner": pipeline_config.get("OWNER"),
                    "cost_center": pipeline_config.get("COST_CENTER"),
                },
                encryption_spec_key_name=encryption_key
            )
            
            # Submit the pipeline
            print(f"Submitting pipeline job...")
            job.submit()
            
            print(f"Pipeline submitted successfully!")
            print(f"Job resource name: {job.resource_name}")
            print(f"View pipeline: https://console.cloud.google.com/vertex-ai/pipelines/runs/{job.name}?project={self.project_id}")
            
            # Wait for completion if desired
            # job.wait()
            
        except Exception as e:
            print(f"Error running pipeline: {str(e)}")
            raise
    
    def _compile_pipeline(self):
        """Compile the pipeline using the sequential_sql_pipeline.py file."""
        print("Compiling pipeline...")
        
        # Import and compile the pipeline
        import subprocess
        import sys
        
        # Install required packages if not available
        try:
            import kfp
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "kfp==2.7.0"])
        
        # Now compile the pipeline
        exec(open("sequential_sql_pipeline.py").read())
        
        if os.path.exists("sequential_sql_pipeline.json"):
            print("Pipeline compiled successfully!")
        else:
            raise Exception("Pipeline compilation failed - JSON file not created")


def main():
    """Main function to run the pipeline."""
    
    # Load configuration
    from sql_config import SQL_CONFIG
    
    # Environment variables for pipeline execution
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', SQL_CONFIG['GCP_PROJECT'])
    region = os.environ.get('VERTEX_AI_REGION', 'us-central1')
    pipeline_root = os.environ.get('PIPELINE_ROOT', f'gs://{project_id}-pipeline-root')
    service_account = os.environ.get('IMPERSONATED_SERVICE_ACCOUNT')
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    
    print(f"Running pipeline with configuration:")
    print(f"  Project: {project_id}")
    print(f"  Region: {region}")
    print(f"  Pipeline Root: {pipeline_root}")
    print(f"  Service Account: {service_account}")
    print(f"  Config: {json.dumps(SQL_CONFIG, indent=2)}")
    
    # Create and run pipeline
    runner = SQLPipelineRunner(
        project_id=project_id,
        region=region,
        service_account=service_account
    )
    
    runner.run_pipeline(
        pipeline_config=SQL_CONFIG,
        pipeline_root=pipeline_root,
        encryption_key=encryption_key
    )


if __name__ == "__main__":
    main()
