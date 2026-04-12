"""Model persistence, metadata capture, and Vertex AI Model Registry registration.

This module owns everything that happens *after* training and evaluation:

1. Build Vertex AI labels + rich JSON metadata from training state.
2. Save the booster as ``model.bst`` and upload to a dedicated GCS folder.
3. Stream ``model_metadata.json`` to the same GCS folder.
4. Optionally register the model (or a new version) in the Vertex AI Model Registry.

Public API
----------
``save_and_register_model(model, config, params, roc_auc, eval_metrics,
                           X_train, X_test, X_val)``
    End-to-end: build card → save → upload → register.
    Returns a small summary dict with the key GCS paths and label count.
"""

import datetime
import os
import pandas as pd
import xgboost as xgb
from google.cloud import aiplatform

# ── Add package root to path so relative imports work when run standalone ──
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import (
    upload_to_gcs,
    build_model_labels,
    save_model_metadata_to_gcs,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def save_and_register_model(
    model: xgb.Booster,
    config: dict,
    params: dict,
    roc_auc: float,
    eval_metrics: dict,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    X_val: pd.DataFrame,
) -> dict:
    """Save, document, and optionally register a trained XGBoost model.

    Steps performed
    ---------------
    1. Assemble Vertex AI labels (≤64 key/value pairs) and rich JSON metadata
       (includes full ``feature_names_in_order`` list).
    2. Save booster as ``model.bst`` locally, then upload to
       ``gs://<bucket>/<gcs_prefix>/model/model.bst``.
    3. Upload ``model_metadata.json`` to the same GCS folder.
    4. If ``config['model_registry']['display_name']`` and
       ``['serving_container_image_uri']`` are both set, upload the model to
       the Vertex AI Model Registry (new model or new version of an existing one).

    Args:
        model:        Trained ``xgb.Booster``.
        config:       Full training config dict (from ``create_config_from_args``).
        params:       Resolved XGBoost params dict used for training
                      (already merged with defaults).
        roc_auc:      ROC-AUC score on the held-out test set.
        eval_metrics: Dict returned by ``calculate_metrics()``
                      (keys: lift_N_perc, ppv_N_perc, sensitivity_N_perc, …).
        X_train:      Training feature DataFrame (after feature selection).
        X_test:       Test feature DataFrame.
        X_val:        Validation feature DataFrame.

    Returns:
        dict with keys:
            ``gcs_model_dir``      – ``gs://`` URI of the model artifact folder.
            ``gcs_metadata_blob``  – Full GCS URI of ``model_metadata.json``.
            ``model_labels``       – The labels dict attached to the registry entry.
            ``registered``         – ``True`` if the model was registered.
            ``registry_resource``  – Resource name of the registered model (or ``''``).
    """
    training_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    # ── Step A: Build labels & metadata ───────────────────────────────────
    model_labels = _build_labels(
        config, params, roc_auc, eval_metrics,
        X_train, X_test, X_val, training_timestamp,
    )
    model_metadata = _build_metadata(
        config, params, roc_auc, eval_metrics,
        X_train, X_test, X_val, training_timestamp,
    )

    print(f"\n  📊 Model labels assembled ({len(model_labels)} labels):")
    for k, v in model_labels.items():
        print(f"      {k} = {v}")

    # ── Step B: Save model.bst → GCS ──────────────────────────────────────
    print("\n── Step 13: Saving model ─────────────────────────────────────────")
    LOCAL_MODEL_NAME = 'model.bst'
    model.save_model(LOCAL_MODEL_NAME)
    print(f"  Model saved locally as : {LOCAL_MODEL_NAME}")

    bucket_name    = config['gcp']['bucket_name']
    gcs_prefix     = config['gcp']['gcs_destination_path']
    gcs_model_blob = f"{gcs_prefix}/model/{LOCAL_MODEL_NAME}"
    gcs_model_dir  = f"gs://{bucket_name}/{gcs_prefix}/model"

    upload_to_gcs(LOCAL_MODEL_NAME, bucket_name, gcs_model_blob)
    print(f"  GCS artifact directory : {gcs_model_dir}")

    # ── Step C: Upload model_metadata.json ────────────────────────────────
    model_metadata['training_gcs_artifact_dir'] = gcs_model_dir
    gcs_metadata_blob_path = f"{gcs_prefix}/model/model_metadata.json"
    save_model_metadata_to_gcs(model_metadata, bucket_name, gcs_metadata_blob_path)
    print(f"  Model metadata JSON    : gs://{bucket_name}/{gcs_metadata_blob_path}")

    # ── Step D: Register in Vertex AI Model Registry ──────────────────────
    registered, registry_resource = _register_model(
        config, gcs_model_dir, model_labels, model_metadata,
    )

    return {
        'gcs_model_dir':     gcs_model_dir,
        'gcs_metadata_blob': f"gs://{bucket_name}/{gcs_metadata_blob_path}",
        'model_labels':      model_labels,
        'registered':        registered,
        'registry_resource': registry_resource,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_labels(
    config, params, roc_auc, eval_metrics,
    X_train, X_test, X_val, training_timestamp,
) -> dict:
    """Delegate to ``utils.helpers.build_model_labels``."""
    return build_model_labels(
        config             = config,
        params             = params,
        roc_auc            = roc_auc,
        eval_metrics       = eval_metrics,
        n_train            = X_train.shape[0],
        n_test             = X_test.shape[0],
        n_val              = X_val.shape[0],
        n_features         = X_train.shape[1],
        training_timestamp = training_timestamp,
    )


def _build_metadata(
    config, params, roc_auc, eval_metrics,
    X_train, X_test, X_val, training_timestamp,
) -> dict:
    """Build the rich JSON metadata dict (includes full feature list)."""
    return {
        'training_timestamp':     training_timestamp,
        'model_type':             'XGBoost',
        'model_format':           'BST',
        'outcome_var':            config['data_processing']['outcome_var'],
        'bq_project':             config['gcp'].get('gcp_project', ''),
        'bq_dataset':             config['gcp'].get('gcp_db', ''),
        'roc_auc':                round(roc_auc, 6),
        'metrics':                {k: round(v, 4) for k, v in eval_metrics.items()},
        'xgboost_params':         params,
        'num_boost_round':        config['model']['num_boost_round'],
        'random_seed':            config['data_processing']['random_seed'],
        'test_size':              config['data_processing']['test_size'],
        'val_size':               config['data_processing']['val_size'],
        'train_rows':             X_train.shape[0],
        'test_rows':              X_test.shape[0],
        'val_rows':               X_val.shape[0],
        'num_features':           X_train.shape[1],
        # Full ordered list — positional order must match what Batch Prediction sends
        'feature_names_in_order': list(X_train.columns),
    }


def _build_serving_env(config: dict, model_metadata: dict) -> dict:
    """Build the environment variables dict to attach to the registered model.

    Sources (in priority order, later values overwrite earlier ones)
    -------
    1. All scalar fields from ``model_metadata`` – the same data written to
       ``model_metadata.json``.  Nested objects (metrics, xgboost_params,
       feature_names_in_order) are JSON-serialised so every field is a string.
    2. ``FEATURE_NAMES`` / ``MODEL_TIMESTAMP`` from ``os.environ`` if set by
       the notebook's EXTRA_ENV block (kept for backward compatibility).

    Why not ``config['environment_variables']``?
    At runtime the config dict is built from CLI args by
    ``create_config_from_args`` and never loads config.yaml, so the
    ``environment_variables`` key is absent — that's why 0 vars were attached.
    The metadata dict is built in memory and is always available.
    """
    import json as _json

    env: dict = {}

    # ── 1) Flatten model_metadata into env vars ────────────────────────────
    # Scalar values are stringified directly; nested dicts/lists are
    # JSON-serialised so they are recoverable by the serving container.
    _METADATA_KEY_MAP = {
        # metadata key            → env var name
        'training_timestamp':      'TRAINING_TIMESTAMP',
        'model_type':              'MODEL_TYPE',
        'model_format':            'MODEL_FORMAT',
        'outcome_var':             'OUTCOME_VAR',
        'bq_project':              'BQ_PROJECT',
        'bq_dataset':              'BQ_DATASET',
        'roc_auc':                 'ROC_AUC',
        'metrics':                 'METRICS',           # JSON
        'xgboost_params':          'XGBOOST_PARAMS',    # JSON
        'num_boost_round':         'NUM_BOOST_ROUND',
        'random_seed':             'RANDOM_SEED',
        'test_size':               'TEST_SIZE',
        'val_size':                'VAL_SIZE',
        'train_rows':              'TRAIN_ROWS',
        'test_rows':               'TEST_ROWS',
        'val_rows':                'VAL_ROWS',
        'num_features':            'NUM_FEATURES',
        'feature_names_in_order':  'FEATURE_NAMES',     # JSON array
        'training_gcs_artifact_dir': 'TRAINING_GCS_ARTIFACT_DIR',
    }
    for meta_key, env_key in _METADATA_KEY_MAP.items():
        val = model_metadata.get(meta_key)
        if val is None:
            continue
        if isinstance(val, (dict, list)):
            env[env_key] = _json.dumps(val)
        else:
            env[env_key] = str(val)

    # ── 2) Dynamic runtime vars injected by the notebook (override if set) ─
    for key in ('FEATURE_NAMES', 'MODEL_TIMESTAMP'):
        val = os.environ.get(key, '')
        if val:
            env[key] = val

    return env


def _register_model(config: dict, gcs_model_dir: str, model_labels: dict,
                    model_metadata: dict):
    """Register the model in Vertex AI Model Registry.

    Returns
    -------
    (registered: bool, resource_name: str)
        ``registered`` is ``False`` (and ``resource_name`` is ``''``) when
        either ``display_name`` or ``serving_container_image_uri`` is not set.
    """
    reg_cfg = config.get('model_registry') or {}
    display_name  = reg_cfg.get('display_name', '')
    container_uri = reg_cfg.get('serving_container_image_uri', '')

    if not (display_name and container_uri):
        print(
            "\n── Step 16: Model Registry skipped "
            "(set display_name and serving_container_image_uri in config to enable) ──"
        )
        return False, ''

    print(f"\n── Step 16: Registering model in Vertex AI Model Registry ──────────")

    location           = reg_cfg.get('location', 'us-east4')
    cmek_key           = reg_cfg.get('cmek_key', '') or None
    description        = reg_cfg.get('description', '')
    upload_to_existing = reg_cfg.get('upload_to_existing_model', False)
    existing_resource  = reg_cfg.get('existing_model_resource_name', '')

    if upload_to_existing and not existing_resource:
        print(
            "  ⚠️  upload_to_existing_model is True but existing_model_resource_name "
            "is empty — falling back to creating a new model."
        )
        upload_to_existing = False

    # aiplatform.init() does not accept a service_account parameter.
    # The service account is already established at the Vertex AI job level.
    aiplatform.init(project=config['gcp']['project'], location=location)

    # ── Build serving container env vars ─────────────────────────────────────
    serving_env = _build_serving_env(config, model_metadata)
    print(f"  Attaching {len(serving_env)} env vars to serving container:")
    for _k, _v in sorted(serving_env.items()):
        # Truncate long values (e.g. FEATURE_NAMES) for readability
        _display = _v if len(_v) <= 80 else _v[:77] + '...'
        print(f"      {_k} = {_display}")

    upload_kwargs = dict(
        display_name                            = display_name,
        artifact_uri                            = gcs_model_dir,
        serving_container_image_uri             = container_uri,
        serving_container_predict_route         = "/predict",
        serving_container_health_route          = "/health",
        serving_container_environment_variables = serving_env,
        encryption_spec_key_name                = cmek_key,
        labels                                  = model_labels,
    )

    if upload_to_existing and existing_resource:
        existing_obj = aiplatform.Model(existing_resource)
        upload_kwargs['parent_model']        = existing_obj.resource_name
        upload_kwargs['version_description'] = description
        print(f"  Uploading new version to existing model: {existing_resource}")
    else:
        upload_kwargs['description'] = description
        print(f"  Uploading as new model: {display_name}")

    registered_model = aiplatform.Model.upload(**upload_kwargs)
    registered_model.wait()
    print(f"  ✅ Model registered: {registered_model.resource_name}")

    return True, registered_model.resource_name

