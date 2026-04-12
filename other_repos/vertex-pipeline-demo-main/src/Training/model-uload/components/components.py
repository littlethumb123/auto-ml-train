"""
MLOps Pipeline Components

This module contains KFP v2 components for the complete MLOps pipeline:
- BigQuery feature extraction
- Vertex AI hyperparameter tuning
- Model evaluation
- Model registry registration
"""
from typing import Any, Dict, List, Optional, Text, Tuple, Union, Sequence, Callable, NamedTuple
from kfp.v2.dsl import component, Output, Dataset


@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        # "google-cloud-logging>=3.0.0",
        "google-api-python-client>=2.0.0"
    ]
)
def vertex_hyperparameter_tuning_component(
    project: str,
    service_account: str,
    cmek_key: str,
    location: str,
    pipeline_root: str,
    image_uri: str,
    command: list = None,
    package_uris: list = None,
    python_module: str = None,
    training_args: list = None,
    parameter_spec_dict: dict = None,
    eval_metrics: dict = None,
    machine_type: dict = {"machine_type": "n1-standard-16"},
    parallel_trials: int = 1,
    max_trials: int = 8,
    max_failed_trials: int = 2,
    alert_emails: list = None,
    sender_email: str = None,
) -> NamedTuple("Outputs",[("hptune_job_resource_name",str),("best_hyperparameters",Dict[str,Union[float,int,str]])]):
    """
    A containerized component to trigger Vertex AI hyperparameter tuning job.
    
    Args:
        image_uri: str - Container image URI for training
        command: list - Command to run in container (e.g., ["python3", "script.py"])
        training_args: list - Arguments to pass to training script
        parameter_spec_dict: dict - Parameter specifications in simplified format
            Example: {"max_depth": {"type": "integer", "min": 4, "max": 128, "scale": "linear"}}
        eval_metrics: dict - Metrics to optimize {"roc": "maximize"}
        machine_type: dict - Machine type for training eg.{"machineType": "n1-standard-16","acceleratorType": None,"acceleratorCount": None}
        parallel_trials: int - Number of parallel trials
        max_trials: int - Maximum number of trials
        max_failed_trials: int - Maximum failed trials before cancellation
        
    Returns:
        str: The hyperparameter tuning job resource name
    """
    import json
    from google.cloud import aiplatform
    from google.cloud.aiplatform import hyperparameter_tuning as hpt
    
    def convert_parameter_spec(param_dict: dict) -> dict:
        """Convert simplified parameter spec to Vertex AI format."""
        converted_params = {}

        for param_name, spec in param_dict.items():
            param_type = spec.get("type", "").lower()
            min_val = spec.get("min")
            max_val = spec.get("max") 
            scale = spec.get("scale", "linear").lower()  # Changed to lower()

            # Map scale to Vertex AI format - corrected mapping
            scale_mapping = {
                "linear": "linear",           # Keep as-is for hpt specs
                "log": "log",                 # Keep as-is for hpt specs  
                "reverse_log": "reverse_log"  # Keep as-is for hpt specs
            }
            vertex_scale = scale_mapping.get(scale, "linear")

            if param_type == "integer":
                converted_params[param_name] = hpt.IntegerParameterSpec(
                    min=min_val, 
                    max=max_val, 
                    scale=vertex_scale
                )
            elif param_type == "double" or param_type == "float":
                converted_params[param_name] = hpt.DoubleParameterSpec(
                    min=min_val, 
                    max=max_val, 
                    scale=vertex_scale
                )
            elif param_type == "categorical":
                values = spec.get("values", [])
                converted_params[param_name] = hpt.CategoricalParameterSpec(values=values)
            elif param_type == "discrete":
                values = spec.get("values", [])
                converted_params[param_name] = hpt.DiscreteParameterSpec(values=values)

        return converted_params

    # Validation logic
    if command is None:
        if not (package_uris and python_module):
            raise ValueError("If 'command' is not provided, both 'package_uris' and 'python_module' must be specified.")
    else:
        if package_uris or python_module:
            raise ValueError("If 'command' is provided, 'package_uris' and 'python_module' must not be specified.")

    # Initialize Vertex AI
    aiplatform.init(
        project=project,
        location=location,
        service_account=service_account,
        staging_bucket=pipeline_root  # or another GCS bucket you control
    )

    # Convert parameter specifications
    vertex_parameter_spec = convert_parameter_spec(parameter_spec_dict)

    ## machine_type
    machine_type = {k: v for k, v in machine_type.items() if v is not None}

    # Build worker pool specs
    if command:
        worker_pool_specs = [
            {
                "machine_spec": machine_type,
                "replica_count": 1,
                "container_spec": {
                    "image_uri": image_uri,
                    "command": command,
                    "args": training_args or [],
                },
            }
        ]
    else:
        worker_pool_specs = [
            {
                "machine_spec": machine_type,
                "replica_count": 1,
                "python_package_spec": {
                    "executor_image_uri": image_uri,
                    "package_uris": package_uris,
                    "python_module": python_module,
                    "args": training_args or [],
                },
            }
        ]

    # Create custom job
    custom_job = aiplatform.CustomJob(
        display_name="hptune_custom_job",
        worker_pool_specs=worker_pool_specs,
    )

    # Create hyperparameter tuning job
    hptune_job = aiplatform.HyperparameterTuningJob(
        display_name="containerized_hptune_job",
        custom_job=custom_job,
        metric_spec=eval_metrics,
        parameter_spec=vertex_parameter_spec,
        max_trial_count=max_trials,
        parallel_trial_count=parallel_trials,
        max_failed_trial_count=max_failed_trials,
        search_algorithm=None,  # Will default to appropriate algorithm
        encryption_spec_key_name=cmek_key,
    )

    # Run the job
    hptune_job.run(sync=True)
    
    # Get best trial and its hyperparameters
    best_trial = hptune_job.trials[0] if hptune_job.trials else None
    if best_trial and hasattr(best_trial, "parameters"):
        best_hyperparameters = {p.parameter_id: p.value for p in best_trial.parameters}
        
    return (
        hptune_job.resource_name,
        best_hyperparameters
    )
    
@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0"
    ]
)
def custom_job_training_component(
    project: str,
    location: str,
    service_account: str,
    pipeline_root:str,
    model_dir:str,
    cmek_key: str,
    image_uri: str,
    best_hyperparameters: dict,
    command: list = None,
    package_uris: list = None,
    python_module: str = None,
    training_args: list = None,
    machine_type: dict = {"machine_type": "n1-standard-16"},
) -> NamedTuple("Outputs",[("train_job_resource_name",str),("model_gcs_location",str)]):
    """
    Runs a Vertex AI CustomJob for model training using best hyperparameters.
    """
    from google.cloud import aiplatform
    # Validation logic
    if command is None:
        if not (package_uris and python_module):
            raise ValueError("If 'command' is not provided, both 'package_uris' and 'python_module' must be specified.")
    else:
        if package_uris or python_module:
            raise ValueError("If 'command' is provided, 'package_uris' and 'python_module' must not be specified.")

            
    aiplatform.init(
        project=project,
        location=location,
        service_account=service_account,
        staging_bucket=pipeline_root
    )

    # Merge best hyperparameters into training_args if needed
    args = training_args or []
    if best_hyperparameters:
        for k, v in best_hyperparameters.items():
            args += [f"--{k}", str(v)]

    machine_type = {k: v for k, v in machine_type.items() if v is not None}

    if command:
        worker_pool_specs = [
            {
                "machine_spec": machine_type,
                "replica_count": 1,
                "container_spec": {
                    "image_uri": image_uri,
                    "command": command,
                    "args": args,
                },
            }
        ]
    else:
        worker_pool_specs = [
            {
                "machine_spec": machine_type,
                "replica_count": 1,
                "python_package_spec": {
                    "executor_image_uri": image_uri,
                    "package_uris": package_uris,
                    "python_module": python_module,
                    "args": args,
                },
            }
        ]

    custom_job = aiplatform.CustomJob(
        display_name="model_training_job",
        worker_pool_specs=worker_pool_specs,
        encryption_spec_key_name=cmek_key,
    )

    custom_job.run(sync=True)
    return (custom_job.resource_name,model_dir)

   
@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        "google-cloud-storage>=2.0.0"
    ]
)
def upload_model_component(
    project: str,
    location: str,
    service_account: str,
    cmek_key: str,
    model_gcs_location: str,
    serving_container_image_uri: str,
    model_display_name: str,
    upload_to_existing_model: bool = False,
    existing_model_resource_name: str = "",
    description: str = None,
    serving_container_predict_route: str = "/predict",
    serving_container_health_route: str = "/health",
    model_framework: str = "XGBoost",  # Framework name
    model_type: str = "classifier",  # "classifier" or "regressor"
) -> str:
    """
    Registers a model in Vertex AI Model Registry with metadata.
    - Checks if the model file exists and is of an allowed type.
    - Can upload to a new model or an existing model.
    - Adds metadata for proper model serving.

    Args:
        project: GCP project ID.
        location: GCP region.
        model_gcs_location: GCS URI to the model artifact directory or file.
        serving_container_image_uri: URI of the serving container image.
        display_name: Display name for the model.
        upload_to_existing_model: If True, upload as a new version to existing model.
        existing_model_resource_name: Full resource name of the existing model (if applicable).
        encryption_spec_key_name: CMEK key (optional).
        description: model or version description
        serving_container_predict_route: Route for prediction endpoint (default: "/predict")
        serving_container_health_route: Route for health check endpoint (default: "/health")
        model_framework: ML framework name (e.g., "XGBoost", "scikit-learn", "TensorFlow")
        model_type: Model type ("classifier" or "regressor")

    Returns:
        The resource name of the uploaded model version.
    """
    import os
    from google.cloud import storage, aiplatform

    # Check model file(s) in GCS
    if not model_gcs_location.startswith("gs://"):
        raise ValueError("model_gcs_location must be a GCS URI (gs://...)")
    if upload_to_existing_model==True and existing_model_resource_name=="":
        raise ValueError("existing_model_resource_name must have value when upload_to_existing_model is True")
    
    aiplatform.init(project=project, location=location, service_account=service_account)

    # Build description with metadata
    metadata_description = f"""Framework: {model_framework}
    Model Type: {model_type}
    {description if description else ""}""".strip()

    # Upload as new version to existing model
    if upload_to_existing_model and existing_model_resource_name:
        existing_model = aiplatform.Model(existing_model_resource_name)
        new_model_version = aiplatform.Model.upload(
            display_name=model_display_name,
            version_description=metadata_description,
            artifact_uri=model_gcs_location,
            serving_container_image_uri=serving_container_image_uri,
            serving_container_predict_route=serving_container_predict_route,
            serving_container_health_route=serving_container_health_route,
            parent_model=existing_model.resource_name,
            encryption_spec_key_name=cmek_key,
        )
        return new_model_version.resource_name

    # Upload as a new model (default)
    model = aiplatform.Model.upload(
        display_name=model_display_name,
        description=metadata_description,
        artifact_uri=model_gcs_location,
        serving_container_image_uri=serving_container_image_uri,
        serving_container_predict_route=serving_container_predict_route,
        serving_container_health_route=serving_container_health_route,
        encryption_spec_key_name=cmek_key,
    )
    model.wait()
    return model.resource_name

@component(
    base_image="python:3.9",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        "google-cloud-bigquery>=2.0.0",
        "google-auth>=2.0.0",
        "requests>=2.25.0"
    ]
)
def vertex_batch_predict_bigquery_component(
    project: str,
    location: str,
    service_account: str,
    cmek_key: str,
    cost_center: str,
    owner: str,
    #Model details
    model_resource_name: str,
    # BigQuery specific
    key_field: str,  # Unique key field in input table
    input_table: str,  # project.dataset.table
    output_table: str, # project.dataset.table (final output)
    compute_dataset: str, #hcm_cm_de_dec_beam_{ENV}_hcm_cm_de"
    expiration_days: int = 30, # BQ table expiration in days
    # Instance configuration - field filtering
    excluded_fields: list = None,  # Fields to exclude from predictions
    included_fields: list = None,  # Fields to include (if specified, only these will be sent)
    # Selected features configuration
    selected_features: list = None,  # List of feature names in proper order for model input
    # Machine configuration
    machine_type: dict = {"machine_type": "n2-standard-64"},
    # Job configuration
    starting_replica_count: int = 1,
    max_replica_count: int = 1,
    batch_size: int = None,  # Auto-determined if None
) -> str:
    """
    Runs a Vertex AI batch prediction job with comprehensive parameter validation.
    
    Copies input table from shared project to compute project temp dataset,
    runs batch prediction to temp output table in compute project temp dataset, 
    then copies to final output table in shared project.

    Args:
        project: GCP project ID.
        location: GCP region.
        compute_dataset: temp dataset in compute project
        model_resource_name: Full resource name of the registered model.
        job_display_name: Display name for the batch prediction job.
        input_table: Input data table (BigQuery table).
        output_table: Output data table (BigQuery table).
        excluded_fields: List of field names to exclude from predictions.
        included_fields: List of field names to include (mutually exclusive with excluded_fields).
        selected_features: List of feature names in proper order. If provided, only these features
                          will be selected from input_table in the specified order. The key_field
                          will be included automatically if not in selected_features.
        machine_type: Machine type for batch prediction.
        expiration_days: Days until output table expires (default: 30).

    Returns:
        The resource name of the batch prediction job.
    """
    from google.cloud import aiplatform
    from google.cloud import bigquery
    import requests
    import json
    from google.auth import default
    from google.auth.transport.requests import Request
    # Initialize clients
    bq_client = bigquery.Client(project=project)
    
    # Setup table names and labels
    input_table_name = input_table.split(".")[-1]
    output_table_name = output_table.split(".")[-1]
    labels = f"""labels=[("owner","{owner}"),("costcenter","{cost_center}")]"""

    # Copy input table to temp dataset with selected features in proper order
    temp_input_table = f"{project}.{compute_dataset}.{input_table_name}_tmp"
    
    # Build SELECT clause based on selected_features
    if selected_features:
        # Ensure key_field is included if not already in selected_features
        columns_to_select = selected_features.copy()
        if key_field not in columns_to_select:
            # Add key_field at the beginning to maintain it for joining results
            columns_to_select.insert(0, key_field)
        
        # Escape column names with backticks to handle special characters
        escaped_columns = [f"`{col}`" for col in columns_to_select]
        select_clause = ", ".join(escaped_columns)
        query = f"CREATE OR REPLACE TABLE {temp_input_table} OPTIONS({labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)) AS SELECT {select_clause} FROM `{input_table}`"
    else:
        # Fallback to SELECT * if no selected_features provided (backward compatibility)
        query = f"CREATE OR REPLACE TABLE {temp_input_table} OPTIONS({labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)) AS SELECT * FROM `{input_table}`"
    
    job = bq_client.query(query)
    job.result()

    # Prepare temp output table
    temp_output_table = f"{project}.{compute_dataset}.{output_table_name}_tmp"

    # Create batch prediction job using REST API
    
    # Get authentication credentials
    credentials, _ = default()
    credentials.refresh(Request())
    access_token = credentials.token
    
    # Extract project, location, and model ID from model resource name
    # Format: projects/{project}/locations/{location}/models/{model_id}
    model_parts = model_resource_name.split('/')
    model_project = model_parts[1]
    model_location = model_parts[3]
    model_id = model_parts[5]
    
    # Convert machine_type keys to camelCase for REST API
    def to_camel_case(snake_str):
        """Convert snake_case to camelCase"""
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

    machine_type = {k: to_camel_case(v) for k, v in machine_type.items() if v is not None}
    
    # Build instance config if field filtering is specified
    instance_config = {}
    if excluded_fields:
        instance_config["excludedFields"] = excluded_fields
    elif included_fields:
        instance_config["includedFields"] = included_fields
    job_display_name = f"{model_id}_model_prediction"
    # Build the REST API request payload
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
            "machineSpec": machine_type,
            "startingReplicaCount": starting_replica_count,
            "maxReplicaCount": max_replica_count
        },
        "encryptionSpec": {
            "kmsKeyName": cmek_key
        }
    }
    
    # Add optional parameters
    if batch_size:
        batch_prediction_request["manualBatchTuningParameters"] = {
            "batchSize": batch_size
        }
    if instance_config:
        batch_prediction_request["instanceConfig"] = instance_config
 
    print(json.dumps(batch_prediction_request, indent=2))
    # Make the REST API call (using v1beta1 to match documentation)
    # https://cloud.google.com/vertex-ai/docs/reference/rpc/google.cloud.aiplatform.v1beta1#batchpredictionjob
    # https://cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform.BatchPredictionJob
    url = f"https://{model_location}-aiplatform.googleapis.com/v1beta1/projects/{model_project}/locations/{model_location}/batchPredictionJobs"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=batch_prediction_request)
    
    if response.status_code != 200:
        raise Exception(f"Batch prediction job creation failed: {response.status_code} - {response.text}")
    
    batch_job_response = response.json()
    batch_predict_job_name = batch_job_response["name"]
    
    print(f"Batch prediction job created: {batch_predict_job_name}")
    
    # use Python SDK for job waiting
    aiplatform.init(project=project, location=location, service_account=service_account)
    batch_job = aiplatform.BatchPredictionJob(batch_predict_job_name)
    batch_job.wait_for_completion()  # Built-in exponential backoff and error handling
    
    print(f"Batch prediction job completed with state: {batch_job.state}")

    # Copy prediction table to final output table
    if expiration_days:
        options=f'{labels}, expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {expiration_days} DAY)'
    else:
        options=labels
    query = f"CREATE OR REPLACE TABLE {output_table} OPTIONS({options}) AS SELECT * FROM `{temp_output_table}`"
    copy_pred_job = bq_client.query(query)
    copy_pred_job.result()
    #clean up temp tables
    bq_client.delete_table(temp_input_table, not_found_ok=True)
    bq_client.delete_table(temp_output_table, not_found_ok=True)

    return batch_predict_job_name

