"""Helper functions for the Feature Engineering pipeline notebook.

These functions handle package building, GCS uploading, and Vertex AI
custom training job creation. Stakeholders don't need to modify these —
they are called automatically by ``feature_engineering.ipynb``.

Public API
----------
``build_package(training_dir, output_dir)``
    Runs ``python setup.py sdist`` to create a ``.tar.gz`` source
    distribution of the ``trainer`` package.

``upload_to_gcs(package_file, gcs_path, project)``
    Uploads a local file to the given ``gs://`` URI.

``build_and_upload_package(training_dir, output_dir, gcs_path, project, pipeline_root)``
    Convenience wrapper that builds and uploads in one call. Derives the
    GCS destination from *pipeline_root* when *gcs_path* is not supplied.

``create_custom_training_job_component(pipeline_root, constants, machine_type, package_uris, python_module, display_name, env, args)``
    Creates a KFP ``CustomTrainingJobOp`` component that runs
    ``trainer.task`` inside the prebuilt XGBoost Vertex AI image.
    JSON-valued args (``--sql-queries``, ``--model-config``, etc.) are
    automatically base64-encoded to prevent payload escaping issues.

``generate_compute_environment(pipeline_root, constants, env)``
    Builds the list of ``{name, value}`` dicts injected as environment
    variables into the Vertex AI training container.

``required_kf_info(constants)``
    Extracts the correct project, service account, and CMEK key from the
    constants dict (prefers compute-project variants when present).
"""
import os
import sys
import subprocess
from pathlib import Path
from google.cloud import storage
from google_cloud_pipeline_components.v1 import custom_job
from typing import Optional, List, Dict
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

    # Create the custom training job component
    custom_job_component = custom_job.CustomTrainingJobOp(
        project=str(project),
        display_name=display_name,
        location=constants["LOCATION"],
        worker_pool_specs=[
            {
                "machineSpec": {**machine_type},
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

