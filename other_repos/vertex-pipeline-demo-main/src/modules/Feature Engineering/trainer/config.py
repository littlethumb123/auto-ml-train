"""Configuration management for the Feature Engineering pipeline.

Responsibilities
----------------
- ``load_config``            : Locate and parse ``config.yaml`` from several
                               candidate paths (caller-supplied, package parent,
                               current working directory, installed package).
- ``setup_environment``      : Set GCP environment variables and random seeds.
- ``get_constants_from_config``: Build a flat constants dict used for SQL
                               variable substitution (``{GCP_PROJECT}``, etc.).
- ``_decode_json_arg``       : Decode a CLI value that may be plain JSON or
                               ``base64:<encoded>`` JSON.
- ``create_config_from_args``: Assemble the unified config dict from the
                               argparse ``Namespace`` returned by ``task.py``.
"""
import os
import yaml
import json
import base64
import random
import numpy as np
from pathlib import Path


def load_config(config_path="config.yaml"):
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    # Try multiple locations for config.yaml
    # Priority: 1) User-specified path, 2) Parent directory (where notebook is), 3) Current working directory
    possible_paths = [
        config_path,  # User-specified path
        Path(config_path),  # As Path object
        Path(__file__).parent.parent / "config.yaml",  # In package parent directory (where notebook is)
        Path.cwd() / "config.yaml",  # Current working directory
        Path("/config/config.yaml"),  # If installed via data_files
    ]
    
    # Also try to find config.yaml in installed package
    try:
        import pkg_resources
        package_config = pkg_resources.resource_filename('trainer', '../config.yaml')
        possible_paths.append(Path(package_config))
    except:
        pass
    
    # Try each path
    for path in possible_paths:
        path_obj = Path(path) if not isinstance(path, Path) else path
        if path_obj.exists() and path_obj.is_file():
            print(f"Loading config from: {path_obj}")
            with open(path_obj, "r") as f:
                return yaml.safe_load(f)
    
    # If not found, raise error with helpful message
    raise FileNotFoundError(
        f"config.yaml not found. Tried paths: {[str(p) for p in possible_paths]}\n"
        f"Current working directory: {Path.cwd()}\n"
        f"Please ensure config.yaml is in the package or provide full path as argument."
    )


def setup_environment(config):
    """Set up environment variables and random seeds.
    
    Args:
        config: Configuration dictionary
    """
    gcp_config = config['gcp']
    os.environ['GOOGLE_CLOUD_PROJECT'] = gcp_config['project']
    os.environ['GCLOUD_PROJECT'] = gcp_config['project']
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    
    random.seed(config['data_processing']['random_seed'])
    np.random.seed(config['data_processing']['numpy_seed'])


def get_constants_from_config(config):
    """Extract constants dictionary from config for SQL processing.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        dict: Constants dictionary for SQL variable substitution
    """
    gcp = config['gcp']
    return {
        "GCP_PROJECT": gcp['gcp_project'],
        "GCP_DB": gcp['gcp_db'],
        "PREFIX": gcp['prefix'],
        "DEFAULT_EXP": gcp['default_exp'],
        "ST": f"{gcp['gcp_project']}.{gcp['gcp_db']}.{gcp['prefix']}_st",
        "SDOH_YEAR": gcp['sdoh_year'],
        "OWNER": config['bigquery_labels']['owner'],
        "COSTCENTER": config['bigquery_labels']['costcenter']
    }


def _decode_json_arg(value):
    """Decode a JSON argument that may be base64 encoded.
    
    Args:
        value: String that may be base64 encoded JSON or plain JSON
        
    Returns:
        dict or list: Parsed JSON object
    """
    if not value:
        return {}
    
    # Check if it's base64 encoded (prefixed with 'base64:')
    if value.startswith('base64:'):
        try:
            encoded = value[7:]  # Remove 'base64:' prefix
            decoded = base64.b64decode(encoded).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            # If decoding fails, try parsing as regular JSON
            return json.loads(value) if value else {}
    else:
        # Try parsing as regular JSON
        try:
            return json.loads(value) if value else {}
        except json.JSONDecodeError:
            return {}


def create_config_from_args(args):
    """Create configuration dictionary from command-line arguments.
    
    Args:
        args: Parsed arguments from argparse
        
    Returns:
        dict: Configuration dictionary
    """
    # Parse JSON strings for complex nested structures (may be base64 encoded)
    sql_queries = _decode_json_arg(args.sql_queries) if args.sql_queries else {}
    feature_classification = _decode_json_arg(args.feature_classification) if args.feature_classification else {}
    model_config = _decode_json_arg(args.model_config) if args.model_config else {}
    undersampling_config = _decode_json_arg(args.undersampling_config) if args.undersampling_config else {}
    rfecv_config = _decode_json_arg(args.rfecv_config) if args.rfecv_config else {}
    metrics_config = _decode_json_arg(args.metrics_config) if args.metrics_config else {}
    output_config = _decode_json_arg(args.output_config) if args.output_config else {}
    bigquery_query_config = _decode_json_arg(args.bigquery_query_config) if args.bigquery_query_config else {}
    
    config = {
        'gcp': {
            'project': args.gcp_project,
            'gcp_project': args.gcp_gcp_project,
            'gcp_db': args.gcp_db,
            'prefix': args.prefix,
            'default_exp': args.default_exp,
            'sdoh_year': args.sdoh_year,
            'location': args.location,
            'bucket_name': args.bucket_name,
            'gcs_destination_path': args.gcs_destination_path
        },
        'bigquery_labels': {
            'owner': args.owner,
            'costcenter': args.costcenter,
            'unique_id': args.unique_id,
            'pipeline_type': args.pipeline_type,
            'lob': args.lob,
            'expiration_days': args.expiration_days
        },
        'sql_queries': sql_queries,
        'data_processing': {
            'random_seed': args.random_seed,
            'numpy_seed': args.numpy_seed,
            'embedding_pattern': args.embedding_pattern,
            'variance_threshold': args.variance_threshold,
            'target_column': args.target_column,
            'exclude_for_variance': _decode_json_arg(args.exclude_for_variance) if args.exclude_for_variance else [],
            'exclude_for_classification': _decode_json_arg(args.exclude_for_classification) if args.exclude_for_classification else []
        },
        'feature_classification': feature_classification,
        'one_hot_encoding': {
            'min_occurrence': args.min_occurrence
        },
        'model': model_config,
        'undersampling': undersampling_config,
        'rfecv': rfecv_config,
        'metrics': metrics_config,
        'output': output_config,
        'bigquery_query': bigquery_query_config
    }
    
    return config

