"""Helper functions for the XGBoost model training pipeline notebook.

These functions handle package building, GCS uploading, and Vertex AI
custom training job creation.  Stakeholders don't need to modify these.
"""
import os
import sys
import json
import base64
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from google.cloud import storage
from google_cloud_pipeline_components.v1 import custom_job
from cytoolz.curried import merge


# ---------------------------------------------------------------------------
# Package build & upload
# ---------------------------------------------------------------------------

def build_package(training_dir: str = ".", output_dir: str = "dist") -> Path:
    """Build the Python package as a .tar.gz source distribution.

    Args:
        training_dir: Directory containing setup.py
        output_dir: Where to write the built archive

    Returns:
        Path to the created .tar.gz file
    """
    training_path = Path(training_dir)
    output_path   = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    setup_py = training_path / "setup.py"
    if not setup_py.exists():
        raise FileNotFoundError(f"setup.py not found in {training_dir}")

    print(f"Building package from {training_path.resolve()} ...")
    result = subprocess.run(
        [sys.executable, "setup.py", "sdist", "--dist-dir", str(output_path)],
        cwd=str(training_path.resolve()),
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print("STDOUT:", result.stdout)
    if result.stderr and result.returncode != 0:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"Package build failed:\n{result.stderr}")

    dist_files = list(output_path.glob("*.tar.gz"))
    if not dist_files:
        raise RuntimeError("No .tar.gz file was created by setup.py sdist")

    package_file = max(dist_files, key=lambda p: p.stat().st_mtime)
    print(f"✅ Package built: {package_file}")
    return package_file


def upload_file_to_gcs(local_path: str | Path, gcs_uri: str, project: str = None) -> str:
    """Upload a local file to a GCS URI.

    Args:
        local_path: Local filesystem path
        gcs_uri: Destination GCS URI (gs://bucket/path)
        project: GCP project for the GCS client

    Returns:
        Full GCS URI of the uploaded object
    """
    if not str(gcs_uri).startswith("gs://"):
        raise ValueError(f"Invalid GCS URI (must start with gs://): {gcs_uri}")

    parts      = str(gcs_uri).replace("gs://", "").split("/", 1)
    bucket_nm  = parts[0]
    blob_path  = parts[1] if len(parts) > 1 else Path(local_path).name

    print(f"Uploading {local_path} → {gcs_uri} ...")
    client = storage.Client(project=project)
    blob   = client.bucket(bucket_nm).blob(blob_path)
    blob.upload_from_filename(str(local_path))
    print(f"✅ Uploaded to: {gcs_uri}")
    return gcs_uri


def build_and_upload_package(
    training_dir: str = ".",
    output_dir:   str = "dist",
    project:      str = None,
    pipeline_root: str = None,
    gcs_path:     str = None,
) -> tuple:
    """Build the Python package and upload it to GCS.

    Args:
        training_dir: Directory containing setup.py
        output_dir: Local directory for the built archive
        project: GCP project ID
        pipeline_root: GCS pipeline root; package goes into /packages/<name>
        gcs_path: Explicit GCS destination URI (overrides pipeline_root)

    Returns:
        tuple: (package_uri, local_package_path)
    """
    package_file = build_package(training_dir, output_dir)

    if not gcs_path:
        if pipeline_root:
            gcs_path = f"{pipeline_root}/packages/{package_file.name}"
        else:
            gcs_path = f"gs://hcm-cm-de-code-hcb-dev/vertex-test/packages/{package_file.name}"

    package_uri = upload_file_to_gcs(package_file, gcs_path, project)
    return package_uri, package_file


# ---------------------------------------------------------------------------
# Vertex AI job helpers
# ---------------------------------------------------------------------------

def required_kf_info(constants: dict) -> tuple:
    """Extract project, service account, and CMEK key from constants."""
    project         = constants.get("COMPUTE_PROJECT") or constants["PROJECT"]
    service_account = constants.get("SERVICE_ACCOUNT_COMPUTE_PROJECT") or constants["SERVICE_ACCOUNT"]
    cmek_key        = constants.get("CMEK_KEY_COMPUTE_PROJECT") or constants["CMEK_KEY"]
    return project, service_account, cmek_key


def generate_compute_environment(pipeline_root: str, constants: dict, env: dict = None) -> list:
    """Build the list of environment variables for the training job container.

    Args:
        pipeline_root: GCS path used as AIP_DIR
        constants: Pipeline constants dict
        env: Optional extra environment variables to merge in

    Returns:
        List of {name, value} dicts suitable for Vertex AI workerPoolSpecs
    """
    base_env = {
        "LOB":             constants["LOB"],
        "PROJECT":         constants["PROJECT"],
        "COMPUTE_PROJECT": str(constants.get("COMPUTE_PROJECT") or ""),
        "SHARED_PROJECT":  constants["SHARED_PROJECT"],
        "AIP_DIR":         pipeline_root,
        **{k.upper(): str(v) for k, v in constants["LABELS"].items()},
    }
    final_env = merge(base_env, env or {})
    return [{"name": k, "value": str(v)} for k, v in final_env.items() if v]


def _encode_json_args(args: list, json_arg_flags: set) -> list:
    """Base64-encode JSON values for flagged arguments.

    Prevents JSON escaping issues when the arg list is serialised into
    the Vertex AI job payload.

    Args:
        args: Flat list of [flag, value, flag, value, ...]
        json_arg_flags: Set of flag names whose values should be encoded

    Returns:
        Processed args list
    """
    out = []
    i = 0
    while i < len(args):
        flag = args[i]
        out.append(flag)

        if i + 1 < len(args) and flag in json_arg_flags:
            value = str(args[i + 1]).strip()
            if value.startswith("base64:"):
                out.append(value)
            elif value.startswith(("{", "[")):
                try:
                    parsed   = json.loads(value)
                    json_str = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                    encoded  = base64.b64encode(json_str.encode()).decode()
                    out.append(f"base64:{encoded}")
                except (json.JSONDecodeError, TypeError):
                    out.append(value)
            else:
                out.append(value)
            i += 2
        else:
            i += 1

    return out


# JSON argument flags for the model training task.py
# Values associated with these flags will be base64-encoded to avoid
# JSON escaping issues when serialised into the Vertex AI job payload.
_MODEL_JSON_FLAGS = {
    "--sql-queries",
    "--categorical-config",
    "--model-params",
    "--percentiles",
    "--output-config",
    "--bigquery-query-config",
    "--selected-features-list",
}


def create_model_training_job_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    package_uris: List[str],
    python_module: str = "trainer.task",
    display_name: str  = "model-training",
    env: Optional[dict] = None,
    args: Optional[List[str]] = None,
):
    """Create a Vertex AI Custom Training Job KFP component.

    Works for any model; all model-specific settings are passed via *args*.

    Args:
        pipeline_root: GCS pipeline root
        constants: Pipeline constants (PROJECT, LOCATION, LABELS, etc.)
        machine_type: Dict with machineType (and optional acceleratorType/Count)
        package_uris: List of GCS URIs for the Python package
        python_module: Python module entry point (default: trainer.task)
        display_name: Display name for the job
        env: Additional environment variables
        args: Flat argument list [flag, value, ...]

    Returns:
        KFP CustomTrainingJobOp component
    """
    project, service_account, cmek_key = required_kf_info(constants)
    ENV = generate_compute_environment(pipeline_root, constants, env)

    processed_args = _encode_json_args(args or [], _MODEL_JSON_FLAGS)

    component = custom_job.CustomTrainingJobOp(
        project=str(project),
        display_name=display_name,
        location=constants["LOCATION"],
        worker_pool_specs=[{
            "machineSpec": {**machine_type},
            "replicaCount": "1",
            "pythonPackageSpec": {
                "executorImageUri": constants["DOCKER_URI"],
                "packageUris": package_uris,
                "pythonModule": python_module,
                "args": processed_args,
            },
            "env": ENV,
        }],
        labels=constants["LABELS"],
        base_output_directory=os.getenv("AIP_MODEL_DIR", pipeline_root),
        service_account=service_account,
        encryption_spec_key_name=cmek_key,
    )
    component.set_display_name(display_name)
    return component


# Backward-compatibility alias (avoids breaking any existing callers)
create_cancer_training_job_component = create_model_training_job_component

