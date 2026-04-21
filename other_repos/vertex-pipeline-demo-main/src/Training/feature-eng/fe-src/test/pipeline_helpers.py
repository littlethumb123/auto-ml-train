"""Helper functions for the feature engineering pipeline notebook.
These functions handle package building, uploading, and pipeline creation.
Stakeholders don't need to modify these - they're used automatically.
"""
import os
import sys
import subprocess
from pathlib import Path
from google.cloud import storage
from google_cloud_pipeline_components.v1 import custom_job
from typing import Optional, List, Dict, Any
from cytoolz.curried import merge


def build_package(training_dir=".", output_dir="dist"):
    """Build Python package as tar.gz"""
    training_path = Path(training_dir)
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    
    setup_py = training_path / "setup.py"
    if not setup_py.exists():
        raise FileNotFoundError(f"setup.py not found in {training_dir}")
    
    print(f"Building package from {training_dir}...")
    result = subprocess.run(
        [sys.executable, "setup.py", "sdist", "--dist-dir", str(output_path)],
        cwd=str(training_path.resolve()),
        capture_output=True,
        text=True
    )
    
    if result.stdout:
        print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        raise RuntimeError(f"Package build failed: {result.stderr}")
    
    # Find the created tar.gz file
    dist_files = list(output_path.glob("*.tar.gz"))
    if not dist_files:
        raise RuntimeError("No tar.gz file created")
    
    package_file = max(dist_files, key=lambda p: p.stat().st_mtime)
    print(f"✅ Package built: {package_file}")
    return package_file


def upload_to_gcs(package_file, gcs_path, project=None):
    """Upload package to GCS"""
    print(f"Uploading {package_file} to {gcs_path}...")
    
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path: {gcs_path}")
    
    path_parts = gcs_path.replace("gs://", "").split("/", 1)
    bucket_name = path_parts[0]
    blob_path = path_parts[1] if len(path_parts) > 1 else package_file.name
    
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    blob.upload_from_filename(str(package_file))
    package_uri = f"gs://{bucket_name}/{blob_path}"
    print(f"✅ Uploaded to: {package_uri}")
    return package_uri


def build_and_upload_package(
    training_dir=".",
    output_dir="dist",
    gcs_path=None,
    project=None,
    pipeline_root=None
):
    """Build package and upload to GCS"""
    # Build package
    package_file = build_package(training_dir, output_dir)
    
    # Determine GCS path
    if not gcs_path:
        if pipeline_root:
            gcs_path = f"{pipeline_root}/packages/{package_file.name}"
        else:
            gcs_path = f"gs://hcm-cm-de-code-hcb-dev/vertex-test/packages/{package_file.name}"
    
    # Upload to GCS
    package_uri = upload_to_gcs(package_file, gcs_path, project)
    
    return package_uri, package_file


def required_kf_info(constants: dict):
    """Get the correct project / service account / cmek key"""
    project = constants["COMPUTE_PROJECT"] or constants["PROJECT"]
    service_account = (
        constants.get("SERVICE_ACCOUNT_COMPUTE_PROJECT")
        or constants["SERVICE_ACCOUNT"]
    )
    cmek_key = (
        constants.get("CMEK_KEY_COMPUTE_PROJECT")
        or constants["CMEK_KEY"]
    )
    return project, service_account, cmek_key


def generate_compute_environment(pipeline_root: str, constants: dict, env: dict = None):
    """Generate environment variables for the job"""
    base_env = {
        "PYTHONPATH": "$PYTHONPATH:/home/jupyter/my_repo/:/home/jupyter/builtin_scripts",
        "LOB": constants["LOB"],
        "PROJECT": constants["PROJECT"],
        "COMPUTE_PROJECT": str(constants.get("COMPUTE_PROJECT") or "False"),
        "SHARED_PROJECT": constants["SHARED_PROJECT"],
        "AIP_DIR": pipeline_root,
        **{k.upper(): v for k, v in constants["LABELS"].items()},
    }
    
    env = env or {}
    final_env = merge(base_env, env)
    final_env = [{"name": k, "value": str(v)} for k, v in final_env.items() if v]
    return final_env


def create_custom_training_job_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    package_uris: List[str],
    python_module: str,
    display_name: str,
    env: Optional[dict] = None,
    args: Optional[List[str]] = None,
):
    """Create a custom training job component using Python package"""
    import json
    import base64
    
    project, service_account, cmek_key = required_kf_info(constants)
    ENV = generate_compute_environment(pipeline_root, constants, env)
    
    # Process args to ensure JSON strings are properly handled
    # JSON strings in args can break the JSON payload structure when serialized
    # Solution: Use base64 encoding for JSON strings to avoid JSON escaping issues
    processed_args = []
    json_arg_flags = {
        '--sql-queries', '--feature-classification', '--model-config',
        '--undersampling-config', '--rfecv-config', '--metrics-config',
        '--output-config', '--bigquery-query-config', '--exclude-for-variance',
        '--exclude-for-classification'
    }
    
    if args:
        i = 0
        while i < len(args):
            arg = args[i]
            processed_args.append(arg)  # Add the flag
            
            # Check if the next arg is a value for a JSON argument
            if i + 1 < len(args) and arg in json_arg_flags:
                value = args[i + 1]
                arg_str = str(value).strip()
                
                # Skip if already base64 encoded (starts with 'base64:')
                if arg_str.startswith('base64:'):
                    processed_args.append(value)
                    i += 2
                    continue
                
                # Check if it looks like JSON (starts with { or [)
                if (arg_str.startswith('{') or arg_str.startswith('[')) and len(arg_str) > 1:
                    try:
                        # Validate it's valid JSON
                        parsed = json.loads(arg_str)
                        # Re-serialize to ensure proper formatting
                        json_str = json.dumps(parsed, ensure_ascii=False, separators=(',', ':'))
                        # Base64 encode to avoid JSON escaping issues in the payload
                        # Prefix with 'base64:' so task.py knows to decode it
                        encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
                        processed_args.append(f'base64:{encoded}')
                        i += 2
                        continue
                    except (json.JSONDecodeError, TypeError):
                        # If it's not valid JSON, pass as-is
                        processed_args.append(value)
                        i += 2
                        continue
                else:
                    processed_args.append(value)
                    i += 2
                    continue
            else:
                i += 1
    else:
        processed_args = []

    # Filter out "null" accelerator values from machine_type
    # During compilation, acceleratorType might be a PipelineParameterChannel
    # At runtime, if it's the string "null" or empty, we need to remove it
    machine_spec = {}
    
    # Copy machineType (always present)
    if "machineType" in machine_type:
        machine_spec["machineType"] = machine_type["machineType"]
    
    # Conditionally add accelerator config only if it's present and valid
    # Check if acceleratorType exists in the dict
    if "acceleratorType" in machine_type:
        accelerator_type_value = machine_type.get("acceleratorType")
        
        # Try to determine if the value is valid (works at runtime, not during compilation)
        should_add_accelerator = True
        
        # If it's a string, check for "null" or empty values
        if isinstance(accelerator_type_value, str):
            if accelerator_type_value.strip().lower() in ("null", "none", ""):
                should_add_accelerator = False
        # If it's None, don't add it
        elif accelerator_type_value is None:
            should_add_accelerator = False
        
        # Add accelerator config if valid
        if should_add_accelerator:
            machine_spec["acceleratorType"] = accelerator_type_value
            if "acceleratorCount" in machine_type:
                machine_spec["acceleratorCount"] = machine_type["acceleratorCount"]
    
    # Create the custom training job component
    custom_job_component = custom_job.CustomTrainingJobOp(
        project=str(project),
        display_name=display_name,
        location=constants["LOCATION"],
        worker_pool_specs=[
            {
                "machineSpec": machine_spec,
                "replicaCount": "1",
                "pythonPackageSpec": {
                    "executorImageUri": constants["DOCKER_URI"],
                    "packageUris": package_uris,
                    "pythonModule": python_module,
                    "args": processed_args,
                },
                "env": ENV,
            }
        ],
        labels=constants["LABELS"],
        base_output_directory=os.getenv("AIP_MODEL_DIR", pipeline_root),
        service_account=service_account,
        encryption_spec_key_name=cmek_key,
    )
    
    custom_job_component.set_display_name(display_name)
    return custom_job_component


def create_hyperparameter_tuning_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    file_to_run: str = None,  # GCS path to task.py (optional, deprecated)
    python_module: str = None,  # Python module path (e.g., "trainer.hp_tuning.task")
    package_uris: List[str] = None,  # Package URIs (required if using python_module)
    parameter_spec: dict = None,  # Dictionary with parameter specs from config
    eval_metric: dict = {"roc_auc": "maximize"},
    parallel_trials: int = 2,
    max_trials: int = 10,
    max_failed_trials: int = 2,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, Any]] = None,
    packages: Optional[List[str]] = None,
):
    """Create a hyperparameter tuning component.
    
    Can use either:
    1. Python package module (recommended): Set python_module and package_uris
    2. GCS file (legacy): Set file_to_run (deprecated)
    
    Args:
        pipeline_root: GCS path for pipeline outputs
        constants: Pipeline constants dictionary
        machine_type: Machine type specification (e.g., {"machine_type": "n1-standard-8"})
        file_to_run: GCS path to the hyperparameter tuning task.py file (deprecated, use python_module instead)
        python_module: Python module path (e.g., "trainer.hp_tuning.task") - recommended
        package_uris: List of package URIs (required if using python_module)
        parameter_spec: Dictionary of parameter specifications from config.yaml
        eval_metric: Dictionary of metrics to optimize (e.g., {"roc_auc": "maximize"})
        parallel_trials: Number of parallel trials
        max_trials: Maximum number of trials
        max_failed_trials: Maximum failed trials before stopping
        args: Command-line arguments for the task.py script
        env: Additional environment variables
        packages: List of packages to install
    """
    from google_cloud_pipeline_components.v1 import hyperparameter_tuning_job
    from google.cloud.aiplatform import hyperparameter_tuning as hpt
    
    project, service_account, cmek_key = required_kf_info(constants)
    ENV = generate_compute_environment(pipeline_root, constants, env)
    
    # Determine which method to use: package module (preferred) or GCS file (legacy)
    use_package_module = python_module is not None and package_uris is not None
    
    if use_package_module:
        # Use Python package module (recommended approach)
        print(f"✅ Using Python package module: {python_module}")
        
        # Build package installation command
        if packages:
            packages_str = " ".join(packages)
            packages_install = f"pip install --root-user-action=ignore {packages_str}"
        else:
            packages_install = "pip install --root-user-action=ignore cloudml-hypertune"
        
        # Build args string - join args with proper quoting
        if args:
            args_placeholders = []
            for i, arg in enumerate(args):
                args_placeholders.append(f"${{ARG{i}}}")
            args_str = " ".join(args_placeholders)
            
            # Add args as environment variables
            for i, arg in enumerate(args):
                ENV.append({"name": f"ARG{i}", "value": str(arg)})
        else:
            args_str = ""
        
        # Build the command using Python package
        if args_str:
            command = [
                "bash", "-c",
                f"{packages_install} && "
                f"python3 -m {python_module} {args_str}"
            ]
        else:
            command = [
                "bash", "-c",
                f"{packages_install} && "
                f"python3 -m {python_module}"
            ]
        
        # Build worker pool specs with Python package
        # Convert machine_type dict keys to match Vertex AI API format
        machine_spec_dict = {}
        if "machine_type" in machine_type:
            machine_spec_dict["machineType"] = machine_type["machine_type"]
        if "acceleratorType" in machine_type:
            machine_spec_dict["acceleratorType"] = machine_type["acceleratorType"]
        if "acceleratorCount" in machine_type:
            machine_spec_dict["acceleratorCount"] = machine_type["acceleratorCount"]
            
        worker_pool_specs = [
            {
                "machine_spec": machine_spec_dict,
                "replica_count": 1,
                "python_package_spec": {
                    "executor_image_uri": constants["DOCKER_URI"],
                    "package_uris": package_uris,
                    "python_module": python_module,
                    "args": args if args else [],
                },
                "env": ENV,
            }
        ]
    else:
        # Legacy: Use GCS file (deprecated but still supported)
        if not file_to_run:
            raise ValueError("Either python_module+package_uris or file_to_run must be provided")
        
        print(f"⚠️  Using GCS file (legacy): {file_to_run}")
        print(f"   Consider migrating to python_module for better package management")
        
        # Add the GCS file path as an environment variable
        ENV.append({"name": "TASK_FILE_GCS", "value": file_to_run})
        
        # Build package installation command
        if packages:
            packages_str = " ".join(packages)
            packages_install = f"pip install --root-user-action=ignore {packages_str}"
        else:
            packages_install = "pip install --root-user-action=ignore cloudml-hypertune google-cloud-bigquery-storage google-cloud-storage google-cloud-bigquery pandas numpy xgboost scikit-learn pandas-gbq tqdm db-dtypes"
        
        # Build args string - join args with proper quoting
        if args:
            args_placeholders = []
            for i, arg in enumerate(args):
                args_placeholders.append(f"${{ARG{i}}}")
            args_str = " ".join(args_placeholders)
            
            # Add args as environment variables
            for i, arg in enumerate(args):
                ENV.append({"name": f"ARG{i}", "value": str(arg)})
        else:
            args_str = ""
        
        # Build the command - use environment variables for args
        if args_str:
            command = [
                "bash", "-c",
                f"{packages_install} && pip list && "
                f"gsutil cp $TASK_FILE_GCS ./task.py && "
                f"python3 ./task.py {args_str}"
            ]
        else:
            command = [
                "bash", "-c",
                f"{packages_install} && "
                f"gsutil cp $TASK_FILE_GCS ./task.py && "
                "python3 ./task.py"
            ]
        
        # Build worker pool specs with container spec
        # Convert machine_type dict keys to match Vertex AI API format
        machine_spec_dict = {}
        if "machine_type" in machine_type:
            machine_spec_dict["machineType"] = machine_type["machine_type"]
        if "acceleratorType" in machine_type:
            machine_spec_dict["acceleratorType"] = machine_type["acceleratorType"]
        if "acceleratorCount" in machine_type:
            machine_spec_dict["acceleratorCount"] = machine_type["acceleratorCount"]
            
        worker_pool_specs = [
            {
                "machine_spec": machine_spec_dict,
                "replica_count": 1,
                "container_spec": {
                    "image_uri": constants["DOCKER_URI"],
                    "command": command,
                    "env": ENV,
                },
            }
        ]
    
    # Convert config.yaml parameter_spec to hpt parameter specs
    # Handle both cases: dictionaries (from config.yaml) or already-constructed ParameterSpec objects
    hpt_parameter_spec = {}
    for param_name, param_config in parameter_spec.items():
        # Check if param_config is already a ParameterSpec object
        if isinstance(param_config, (hpt.DoubleParameterSpec, hpt.IntegerParameterSpec)):
            # Already a ParameterSpec object, use it directly
            hpt_parameter_spec[param_name] = param_config
        elif isinstance(param_config, dict):
            # It's a dictionary, convert it to ParameterSpec
            if param_config.get('scale') == 'log':
                hpt_parameter_spec[param_name] = hpt.DoubleParameterSpec(
                    min=param_config['min'],
                    max=param_config['max'],
                    scale='log'
                )
            elif param_config.get('scale') == 'linear':
                if isinstance(param_config['min'], int) and isinstance(param_config['max'], int):
                    hpt_parameter_spec[param_name] = hpt.IntegerParameterSpec(
                        min=param_config['min'],
                        max=param_config['max'],
                        scale='linear'
                    )
                else:
                    hpt_parameter_spec[param_name] = hpt.DoubleParameterSpec(
                        min=param_config['min'],
                        max=param_config['max'],
                        scale='linear'
                    )
        else:
            raise ValueError(f"Invalid parameter spec type for {param_name}: {type(param_config)}. "
                           f"Expected dict or ParameterSpec object.")
    
    # Serialize parameter specifications
    kfp_parameter_spec = hyperparameter_tuning_job.serialize_parameters(hpt_parameter_spec)
    
    # Serialize metrics
    metrics = hyperparameter_tuning_job.serialize_metrics(eval_metric)
    
    # Verify location is set correctly - critical for hyperparameter tuning
    # During pipeline compilation, constants["LOCATION"] is a PipelineParameterChannel (the 'region' parameter)
    # At runtime, it will be resolved to the actual string value (e.g., "us-east4")
    location_value = constants.get("LOCATION")
    
    # Check if location_value exists (it should be a PipelineParameterChannel during compilation)
    # PipelineParameterChannel objects are truthy, so we check for None explicitly
    if location_value is None:
        raise ValueError(f"❌ LOCATION is not set in constants! This will cause the hyperparameter tuning job to use the default 'us-central1' location.")
    
    # Try to get the value for printing (if it's a PipelineParameterChannel, try to get its name/identifier)
    # During compilation, we can't get the actual value, but we can verify it's set
    try:
        # If it's a PipelineParameterChannel, it should have attributes like .parameter_name
        if hasattr(location_value, 'parameter_name'):
            location_str = f"PipelineParameter({location_value.parameter_name})"
        elif hasattr(location_value, 'value'):
            location_str = str(location_value.value)
        else:
            location_str = str(location_value)
    except:
        location_str = "PipelineParameter(region)"
    print(f"✅ Hyperparameter tuning will use location: {location_str}")
    
    # Create hyperparameter tuning job
    # Note: max_failed_trial_count must be less than max_trial_count
    # We pass max_failed_trials directly - Vertex AI will validate this at runtime
    # Note: HyperparameterTuningJobRunOp doesn't support labels parameter
    # IMPORTANT: location must be explicitly set to avoid default 'us-central1'
    # Pass the location_value directly (it's a PipelineParameterChannel during compilation, which is correct)
    hp_tune = hyperparameter_tuning_job.HyperparameterTuningJobRunOp(
        display_name="hyperparameter-tuning",
        study_spec_metrics=metrics,
        study_spec_parameters=kfp_parameter_spec,
        max_trial_count=max_trials,
        parallel_trial_count=parallel_trials,
        max_failed_trial_count=max_failed_trials,  # Vertex AI validates this is < max_trial_count
        worker_pool_specs=worker_pool_specs,
        base_output_directory=f"{pipeline_root}/hp_tuning",
        encryption_spec_key_name=cmek_key,
        service_account=service_account,
        location=location_value,  # Explicitly set location to avoid default 'us-central1'
        project=project,
    )
    
    return hp_tune
