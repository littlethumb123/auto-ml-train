import os
import sys
from google.cloud import aiplatform
from google.auth import impersonated_credentials
import google.auth
#test
def register_model():
    """Registers a model in Vertex AI with automatic versioning."""
    
    # Get environment variables
    environment = os.environ.get('ENVIRONMENT')
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    target_service_account = os.environ.get('IMPERSONATED_SERVICE_ACCOUNT')
    model_display_name = os.environ.get('MODEL_DISPLAY_NAME')
    model_artifact_uri = os.environ.get('MODEL_ARTIFACT_URI')
    serving_container_image_uri = os.environ.get('SERVING_CONTAINER_IMAGE_URI')
    encryption_spec_key_name = os.environ.get('KMS_KEY')
    
    # Validate required environment variables
    required_vars = {
        'ENVIRONMENT': environment,
        'GOOGLE_CLOUD_PROJECT': project_id,
        'IMPERSONATED_SERVICE_ACCOUNT': target_service_account,
        'MODEL_DISPLAY_NAME': model_display_name,
        'MODEL_ARTIFACT_URI': model_artifact_uri,
        'SERVING_CONTAINER_IMAGE_URI': serving_container_image_uri
    }
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            print(f"Error: {var_name} environment variable not set!")
            sys.exit(1)
    
    print(f"Registering model in {environment.upper()} environment")
    print(f"Project: {project_id}")
    print(f"Model name: {model_display_name}")
    print(f"Artifact URI: {model_artifact_uri}")
    print(f"Container image: {serving_container_image_uri}")
    if encryption_spec_key_name:
        print(f"Encryption key: {encryption_spec_key_name}")
    else:
        print("No encryption key specified")

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

        # Check if model with same name already exists
        try:
            existing_models = aiplatform.Model.list(
                filter=f'display_name="{model_display_name}"',
                order_by="create_time desc"
            )
            
            if existing_models:
                print(f"Found {len(existing_models)} existing model(s) with name '{model_display_name}'")
                latest_model = existing_models[0]
                print(f"Latest model version: {latest_model.version_id}")
                print("Will create new version of existing model...")
                
                # Prepare upload parameters for new version
                upload_params = {
                    'display_name': model_display_name,
                    'artifact_uri': model_artifact_uri,
                    'serving_container_image_uri': serving_container_image_uri,
                    'serving_container_predict_route': "/predict",
                    'serving_container_health_route': "/health",
                    'description': f"Model registered via CI/CD in {environment} environment - Version update",
                    'parent_model': latest_model.resource_name,  # This creates a new version
                    'sync': True
                }
                
                # Add encryption if specified
                if encryption_spec_key_name:
                    upload_params['encryption_spec_key_name'] = encryption_spec_key_name
                
                # Upload new version of existing model
                vertex_model = aiplatform.Model.upload(**upload_params)
                print(f"Successfully uploaded new version of model: {vertex_model.display_name}")
                print(f"New version ID: {vertex_model.version_id}")
            else:
                print(f"No existing model found with name '{model_display_name}'. Creating new model...")
                
                # Prepare upload parameters for new model
                upload_params = {
                    'display_name': model_display_name,
                    'artifact_uri': model_artifact_uri,
                    'serving_container_image_uri': serving_container_image_uri,
                    'serving_container_predict_route': "/predict",
                    'serving_container_health_route': "/health",
                    'description': f"Model registered via CI/CD in {environment} environment - Initial version",
                    'sync': True
                }
                
                # Add encryption if specified
                if encryption_spec_key_name:
                    upload_params['encryption_spec_key_name'] = encryption_spec_key_name
                
                # Upload new model (first version)
                vertex_model = aiplatform.Model.upload(**upload_params)
                print(f"Successfully uploaded new model: {vertex_model.display_name}")
                print(f"Model ID: {vertex_model.name}")
                print(f"Version ID: {vertex_model.version_id}")
                
        except Exception as list_error:
            print(f"Error checking existing models, proceeding with new model creation: {list_error}")
            
            # Prepare upload parameters for fallback model creation
            upload_params = {
                'display_name': model_display_name,
                'artifact_uri': model_artifact_uri,
                'serving_container_image_uri': serving_container_image_uri,
                'serving_container_predict_route': "/predict",
                'serving_container_health_route': "/health",
                'description': f"Model registered via CI/CD in {environment} environment",
                'sync': True
            }
            
            # Add encryption if specified
            if encryption_spec_key_name:
                upload_params['encryption_spec_key_name'] = encryption_spec_key_name
            
            # Upload new model (fallback)
            vertex_model = aiplatform.Model.upload(**upload_params)
            print(f"Successfully uploaded model: {vertex_model.display_name}")

        print(f"Model registration completed successfully in {environment.upper()} environment!")
        print(f"Model resource name: {vertex_model.resource_name}")
        print(f"Model URI: {vertex_model.uri}")

    except Exception as e:
        print(f"Error registering model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    register_model()