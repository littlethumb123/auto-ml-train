"""Configuration management for the XGBoost model training pipeline."""
import os
import json
import base64
import random
import numpy as np
import yaml
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from a YAML file.

    Searches multiple locations in priority order:
    1. Exact path supplied by caller
    2. Directory containing this module (package parent)
    3. Current working directory

    Args:
        config_path: Path to the YAML config file

    Returns:
        dict: Parsed configuration
    """
    search_paths = [
        Path(config_path),
        Path(__file__).parent.parent / "config.yaml",
        Path.cwd() / "config.yaml",
    ]

    for path in search_paths:
        if path.exists() and path.is_file():
            print(f"Loading config from: {path}")
            with open(path, "r") as f:
                return yaml.safe_load(f)

    raise FileNotFoundError(
        f"config.yaml not found. Tried: {[str(p) for p in search_paths]}\n"
        f"Current working directory: {Path.cwd()}"
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
    np.random.seed(config['data_processing']['random_seed'])


def _decode_json_arg(value):
    """Decode a JSON argument that may be base64-encoded.

    Args:
        value: String that may be 'base64:<encoded>' or plain JSON

    Returns:
        dict | list | None: Parsed JSON object, or None if empty/invalid
    """
    if not value:
        return None

    if value.startswith('base64:'):
        try:
            decoded = base64.b64decode(value[7:]).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            pass

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def create_config_from_args(args):
    """Build a unified configuration dict from parsed CLI arguments.

    Args:
        args: Namespace returned by argparse.parse_args()

    Returns:
        dict: Full configuration dictionary
    """
    sql_queries = _decode_json_arg(args.sql_queries) or {}
    model_params = _decode_json_arg(args.model_params) or {}
    output_config = _decode_json_arg(args.output_config) or {}
    bigquery_query_config = _decode_json_arg(args.bigquery_query_config) or {}
    categorical_config = _decode_json_arg(args.categorical_config) or {}

    gcp_bq_project = getattr(args, 'gcp_bq_project', '') or args.gcp_project

    config = {
        'gcp': {
            'project':              args.gcp_project,
            'gcp_project':          gcp_bq_project,
            'gcp_db':               getattr(args, 'gcp_db', ''),
            'location':             args.location,
            'bucket_name':          args.bucket_name,
            'gcs_destination_path': args.gcs_destination_path,
        },
        'bigquery_labels': {
            'owner':         args.owner,
            'costcenter':    args.costcenter,
            'unique_id':     args.unique_id,
            'pipeline_type': getattr(args, 'pipeline_type', 'model_training'),
            'lob':           args.lob,
            'expiration_days': args.expiration_days,
        },
        'sql_queries': sql_queries,
        'data_processing': {
            'random_seed': args.random_seed,
            'outcome_var': args.outcome_var,
            'indexing_var': args.indexing_var,
            'embedding_pattern': args.embedding_pattern,
            'test_size': args.test_size,
            'val_size': args.val_size,
        },
        'categorical': categorical_config,
        'model': {
            'params': model_params,
            'num_boost_round': args.num_boost_round,
            'verbose_eval': args.verbose_eval,
        },
        'metrics': {
            'percentiles': _decode_json_arg(args.percentiles) or [0.01, 0.10],
        },
        'output': output_config,
        'bigquery_query': bigquery_query_config,
        'model_registry': {
            'display_name':               getattr(args, 'model_registry_display_name', ''),
            'serving_container_image_uri': getattr(args, 'serving_container_image_uri', ''),
            'location':                   getattr(args, 'model_registry_location', 'us-east4'),
            'cmek_key':                   getattr(args, 'model_registry_cmek_key', ''),
            'service_account':            getattr(args, 'model_registry_service_account', ''),
            # --upload-to-existing-model is a string 'true'/'false' from CLI
            'upload_to_existing_model':   getattr(args, 'upload_to_existing_model', 'false').lower() == 'true',
            'existing_model_resource_name': getattr(args, 'existing_model_resource_name', ''),
            'description':                getattr(args, 'model_description', ''),
        },
        # ── Model identity / governance labels ──────────────────────────────
        # These are attached to the Vertex AI Model Registry entry.
        # Falls back to environment variables so they can also be injected
        # by the Vertex AI Pipelines runtime (or a Docker --env flag).
        'model_labels': {
            'model_name':
                getattr(args, 'model_name', '') or os.environ.get('MODEL_NAME', ''),
            'tenant':
                getattr(args, 'tenant', '') or os.environ.get('TENANT', ''),
            'self_serve':
                getattr(args, 'self_serve', '') or os.environ.get('SELF_SERVE', 'true'),
            'vertex_model_id':
                getattr(args, 'vertex_model_id', '') or os.environ.get('VERTEX_MODEL_ID', 'none'),
            'vertex_model_version_alias':
                getattr(args, 'vertex_model_version_alias', '') or os.environ.get('VERTEX_MODEL_ALIAS', 'none'),
            # Auto-populated by Vertex AI Pipelines; falls back to 'none' when
            # running outside a pipeline (e.g. local testing).
            'vertex_ai_pipelines_run_billing_id':
                os.environ.get('VERTEX_AI_PIPELINES_RUN_BILLING_ID', 'none'),
        },
    }

    return config

