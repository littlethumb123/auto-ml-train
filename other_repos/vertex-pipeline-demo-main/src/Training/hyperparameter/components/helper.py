from google.cloud.aiplatform import hyperparameter_tuning as hpt
import os
import subprocess
import sys
from pathlib import Path
from google.cloud import storage
import yaml
from datetime import datetime

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

# Package building functions
def load_config(config_path="config.yaml"):
    """Load configuration from YAML file"""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_package_version(config):
    """Get package version from config or generate timestamp-based version"""
    metadata = config.get("metadata", {})
    component_version = metadata.get("component_version", "0.1")
    return component_version


def build_package(training_dir="training", output_dir="dist"):
    """Build Python package as tar.gz"""
    training_path = Path(training_dir)
    if not training_path.exists():
        raise FileNotFoundError(f"Training directory not found: {training_dir}")
    
    # Create output directory (absolute path)
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Check if setup.py exists
    setup_py = training_path / "setup.py"
    if not setup_py.exists():
        raise FileNotFoundError(f"setup.py not found in {training_dir}")
    
    # Build the package using setup.py
    print(f"Building package from {training_dir}...")
    print(f"Output directory: {output_path}")
    
    # Use absolute path for dist-dir
    result = subprocess.run(
        [sys.executable, "setup.py", "sdist", "--dist-dir", str(output_path)],
        cwd=str(training_path.resolve()),
        capture_output=True,
        text=True
    )
    
    # Print stdout and stderr for debugging
    if result.stdout:
        print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        raise RuntimeError(f"Package build failed with return code {result.returncode}:\n{result.stderr}")
    
    # Check both the specified output_dir and the default 'dist' directory
    # Sometimes sdist creates files in training/dist even with --dist-dir
    possible_locations = [
        output_path,
        training_path / "dist",  # Default location
        Path("dist"),  # Current directory
    ]
    
    dist_files = []
    for location in possible_locations:
        if location.exists():
            found_files = list(location.glob("*.tar.gz"))
            if found_files:
                print(f"Found package in: {location}")
                dist_files.extend(found_files)
    
    if not dist_files:
        # List what files were actually created
        print(f"\nDebugging: Checking directories...")
        for location in possible_locations:
            if location.exists():
                print(f"  {location} exists, contents: {list(location.iterdir())}")
            else:
                print(f"  {location} does not exist")
        raise RuntimeError("No tar.gz file created. Check STDOUT/STDERR above for errors.")
    
    # Use the most recent file if multiple found
    package_file = max(dist_files, key=lambda p: p.stat().st_mtime)
    print(f"Package built: {package_file}")
    
    # If file is not in output_dir, move it there
    if package_file.parent != output_path:
        import shutil
        target = output_path / package_file.name
        shutil.move(str(package_file), str(target))
        package_file = target
        print(f"Moved package to: {package_file}")
    
    return package_file


def upload_to_gcs(package_file, gcs_path, project=None):
    """Upload package to GCS"""
    print(f"Uploading {package_file} to {gcs_path}...")
    
    # Parse GCS path
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path: {gcs_path}")
    
    path_parts = gcs_path.replace("gs://", "").split("/", 1)
    bucket_name = path_parts[0]
    blob_path = path_parts[1] if len(path_parts) > 1 else package_file.name
    
    # Upload to GCS
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    blob.upload_from_filename(str(package_file))
    print(f"Uploaded to: gs://{bucket_name}/{blob_path}")
    
    return f"gs://{bucket_name}/{blob_path}"


def update_config_with_package(config_path, package_uri, version=None):
    """Update config.yaml with package URI"""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Add package configuration if it doesn't exist
    if "package" not in config:
        config["package"] = {}
    
    config["package"]["uri"] = package_uri
    config["package"]["version"] = version or config.get("metadata", {}).get("component_version", "0.1")
    config["package"]["updated_at"] = datetime.now().isoformat()
    
    # Update metadata
    if "metadata" in config:
        config["metadata"]["component_version"] = version or config["metadata"].get("component_version", "0.1")
        config["metadata"]["package_uri"] = package_uri
    
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"Updated {config_path} with package URI: {package_uri}")


def build_and_upload_training_package(
    training_dir="training",
    config_path="config.yaml",
    output_dir="dist",
    gcs_path=None,
    auto_version=True,
    project=None,
    delete_local=True
):
    """
    Build training package and upload to GCS.
    
    Args:
        training_dir: Training directory path (default: "training")
        config_path: Config file path (default: "config.yaml")
        output_dir: Output directory for built packages (default: "dist")
        gcs_path: GCS path to upload (optional, auto-generated if None)
        auto_version: Auto-increment version with timestamp (default: True)
        project: GCP project ID (optional, uses config if None)
    
    Returns:
        tuple: (package_uri, version)
    """
    # Load config
    config = load_config(config_path)
    runtime = config.get("runtime", {})
    project = project or runtime.get("project")
    pipeline_root = runtime.get("pipeline_root", "")
    
    # Get version
    version = get_package_version(config)
    if auto_version:
        # Simple timestamp-based versioning
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        version = f"{version}.{timestamp}"
    
    # Build package
    package_file = build_package(training_dir, output_dir)
    
    # Determine GCS path
    if gcs_path:
        gcs_path_final = gcs_path
    else:
        # Auto-generate path from config
        package_name = package_file.stem.replace(".tar", "")  # Remove .tar from .tar.gz
        gcs_path_final = f"{pipeline_root}/packages/{package_name}.tar.gz"
    
    # Upload to GCS
    package_uri = upload_to_gcs(package_file, gcs_path_final, project)
    
    # Delete local file after successful upload
    if delete_local and package_file.exists():
        try:
            package_file.unlink()
            print(f"Deleted local file: {package_file}")
        except Exception as e:
            print(f"Warning: Could not delete local file {package_file}: {e}")
    
    # Update config
    update_config_with_package(config_path, package_uri, version)
    
    print(f"\n✓ Package built and uploaded successfully!")
    print(f"  Package URI: {package_uri}")
    print(f"  Version: {version}")
    
    return package_uri, version