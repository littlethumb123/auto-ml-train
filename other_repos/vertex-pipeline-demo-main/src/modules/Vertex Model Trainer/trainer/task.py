"""Main entry point for the XGBoost model training on Vertex AI.

This script is designed to be submitted as a Vertex AI Custom Training Job
and works for any binary-classification use-case.  All model-specific settings
(outcome variable, SQL queries, hyperparameters, feature list …) are supplied
via command-line arguments so no code changes are needed between models.

Pipeline steps
--------------
1.  Parse CLI arguments (all complex configs passed as JSON strings)
2.  Setup GCP environment + random seeds
3.  Load outcome, training features, and holdout features from BigQuery
4.  Fill missing values
5.  Apply categorical encodings (binary mappings + optional OHE)
6.  Merge outcome onto features; set indexing_var as index
7.  Train / test / val split (stratified)
8.  Load pre-selected feature list from GCS or inline JSON
9.  Filter to selected features
10. Create XGBoost DMatrix objects (from numpy arrays – NO feature names stored)
11. Train model with xgb.train()
12. Evaluate on test set (ROC-AUC, Lift, PPV, Sensitivity)
13. Save model as model.bst → upload to dedicated GCS folder (model artifact dir)
14. Predict on holdout set
15. Upload holdout predictions to BigQuery
16. Register model in Vertex AI Model Registry (if display_name + container URI supplied)
17. Trigger Vertex AI Batch Prediction job on test/holdout dataset (if enabled)
"""

import sys
import os
import argparse
import datetime
import json
import pandas as pd
from google.cloud import bigquery

# ── Ensure the package root is on PYTHONPATH when run as a script ──────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trainer.config import setup_environment, create_config_from_args
from trainer.data_loader import (
    load_model_data,
    fill_missing_values,
    merge_outcome_and_features,
)
from trainer.feature_engineering import (
    apply_binary_mappings,
    apply_one_hot_encoding,
    load_selected_features,
    filter_to_selected_features,
    DEFAULT_CATEGORICAL_CONFIG,
)
from trainer.model_training import (
    make_dmatrix,
    train_xgb_model,
    calculate_metrics,
    predict_holdout,
    DEFAULT_XGB_PARAMS,
    DEFAULT_NUM_BOOST_ROUND,
)
from trainer.model_card import save_and_register_model
from trainer.batch_predict import run_batch_prediction
from utils.helpers import (
    check_label_distribution,
    sanitize_column_names,
    upload_to_gcs,
    upload_predictions_to_bq,
)
from sklearn.model_selection import train_test_split


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_arguments():
    """Define and parse all CLI arguments."""
    parser = argparse.ArgumentParser(
        description='XGBoost model training pipeline for Vertex AI'
    )

    # ── GCP / environment ──────────────────────────────────────────────────
    parser.add_argument('--gcp-project',          type=str, required=True,
                        help='GCP project ID (used for Vertex AI and BQ client)')
    parser.add_argument('--gcp-bq-project',       type=str, default='',
                        help='GCP project ID used for BigQuery queries (may differ from --gcp-project)')
    parser.add_argument('--gcp-db',               type=str, default='',
                        help='BigQuery dataset / database name')
    parser.add_argument('--location',             type=str, default='US',
                        help='BigQuery / GCS location')
    parser.add_argument('--bucket-name',          type=str, required=True,
                        help='GCS bucket for model and feature artifacts')
    parser.add_argument('--gcs-destination-path', type=str, required=True,
                        help='GCS prefix for uploaded artifacts, e.g. "vertex-test/ss-models"')

    # ── BigQuery labels ────────────────────────────────────────────────────
    parser.add_argument('--owner',           type=str, required=True,
                        help='Owner label for BigQuery tables (e.g. user_aetna_com)')
    parser.add_argument('--costcenter',      type=str, required=True,
                        help='Cost-centre label')
    parser.add_argument('--unique-id',       type=str, required=True,
                        help='Unique pipeline / project identifier')
    parser.add_argument('--lob',             type=str, required=True,
                        help='Line-of-business label')
    parser.add_argument('--pipeline-type',   type=str, default='model_training',
                        help='Pipeline type label for BigQuery tables (default: model_training)')
    parser.add_argument('--expiration-days', type=int, default=7,
                        help='Days until prediction table expires (default: 7)')

    # ── SQL queries (JSON string) ──────────────────────────────────────────
    # Expected keys: outcome_query, train_features_query, holdout_features_query
    parser.add_argument('--sql-queries', type=str, required=True,
                        help=(
                            'JSON dict with keys: outcome_query, '
                            'train_features_query, holdout_features_query. '
                            'May be base64-encoded with "base64:" prefix.'
                        ))

    # ── BigQuery query settings ────────────────────────────────────────────
    # Optional fine-grained BQ read settings; defaults are sensible for Vertex AI
    parser.add_argument('--bigquery-query-config', type=str, default='{}',
                        help='JSON dict of pandas_gbq read settings (optional)')

    # ── Data processing ────────────────────────────────────────────────────
    parser.add_argument('--random-seed',        type=int,   default=53,
                        help='Random seed for reproducibility (default: 53)')
    parser.add_argument('--outcome-var',        type=str,   default='cancer_case',
                        help='Name of the target / outcome column')
    parser.add_argument('--indexing-var',       type=str,   default='individual_id',
                        help='Name of the member ID column used as the DataFrame index')
    parser.add_argument('--embedding-pattern',  type=str,   default=r'emb[0-255]+',
                        help='Regex pattern identifying embedding columns')
    parser.add_argument('--test-size',          type=float, default=0.2,
                        help='Fraction of training data held out for test+val (default: 0.2)')
    parser.add_argument('--val-size',           type=float, default=0.5,
                        help='Fraction of the test split further held out for validation (default: 0.5)')

    # ── Categorical encoding ───────────────────────────────────────────────
    # JSON dict matching DEFAULT_CATEGORICAL_CONFIG structure
    parser.add_argument('--categorical-config', type=str, default='',
                        help=(
                            'JSON dict describing categorical columns. '
                            'Keys are column names; values describe the encoding. '
                            'Defaults to gender_cd (M/F), drug_ind (Y/N) binary + region OHE.'
                        ))

    # ── Selected features ──────────────────────────────────────────────────
    parser.add_argument('--selected-features-path', type=str, default='',
                        help=(
                            'Path to a newline-delimited .txt file with pre-selected '
                            'feature names. Provide a local path or a GCS object path '
                            '(combined with --bucket-name).'
                        ))
    parser.add_argument('--selected-features-list', type=str, default='',
                        help=(
                            'JSON array of pre-selected feature names. '
                            'Takes precedence over --selected-features-path when provided. '
                            'May be base64-encoded with "base64:" prefix.'
                        ))

    # ── Model hyperparameters ──────────────────────────────────────────────
    parser.add_argument('--model-params', type=str, default='',
                        help=(
                            'JSON dict of xgboost.train() params. '
                            'Merges with built-in defaults when supplied; '
                            'only the keys you specify are overridden.'
                        ))
    parser.add_argument('--num-boost-round', type=int, default=DEFAULT_NUM_BOOST_ROUND,
                        help=f'Number of boosting rounds (default: {DEFAULT_NUM_BOOST_ROUND})')
    parser.add_argument('--verbose-eval',    type=int, default=100,
                        help='Print eval metric every N rounds (0 = silent, default: 100)')

    # ── Metrics ────────────────────────────────────────────────────────────
    parser.add_argument('--percentiles', type=str, default='[0.01, 0.10]',
                        help='JSON array of top-N percentiles for lift/PPV metrics')

    # ── Output ─────────────────────────────────────────────────────────────
    parser.add_argument('--output-config', type=str, default='',
                        help=(
                            'JSON dict with output settings. Supported keys: '
                            '"predictions_table" (full BQ table id for holdout preds). '
                            'Model is always saved as model.bst.'
                        ))

    # ── Model identity / governance labels ────────────────────────────────
    # Attached to the Vertex AI Model Registry entry.
    # Empty string → label is omitted.
    parser.add_argument('--model-name',                    type=str, default='',
                        help='Human-readable model name label (e.g. my-model-hcm-cm-de-model)')
    parser.add_argument('--tenant',                        type=str, default='',
                        help='Tenant label (e.g. hcm-cm-de)')
    parser.add_argument('--self-serve',                    type=str, default='true',
                        help='"true" or "false" self-serve flag label (default: true)')
    parser.add_argument('--vertex-model-id',               type=str, default='none',
                        help='Vertex AI model resource ID (filled after first registration)')
    parser.add_argument('--vertex-model-version-alias',    type=str, default='none',
                        help='Vertex AI model version alias (filled after first registration)')

    # ── Vertex AI Model Registry ───────────────────────────────────────────
    parser.add_argument('--model-registry-display-name', type=str, default='',
                        help='Display name for the model in Vertex AI Model Registry. '
                             'Leave empty to skip registration.')
    parser.add_argument('--serving-container-image-uri', type=str, default='',
                        help='URI of the serving container image for the Model Registry entry. '
                             'Required when --model-registry-display-name is set.')
    parser.add_argument('--model-registry-location', type=str, default='us-east4',
                        help='Vertex AI region for the Model Registry (default: us-east4)')
    parser.add_argument('--model-registry-cmek-key', type=str, default='',
                        help='CMEK encryption key resource name for the registered model.')
    parser.add_argument('--model-registry-service-account', type=str, default='',
                        help='Service account used when calling aiplatform.init() for registry.')
    parser.add_argument('--upload-to-existing-model', type=str, default='false',
                        choices=['true', 'false'],
                        help='If "true", upload as a new version to an existing model '
                             '(requires --existing-model-resource-name). Default: false.')
    parser.add_argument('--existing-model-resource-name', type=str, default='',
                        help='Full resource name of the existing Vertex AI model when '
                             '--upload-to-existing-model is "true".')
    parser.add_argument('--model-description', type=str, default='',
                        help='Description / version description for the registered model.')

    # ── Batch prediction ───────────────────────────────────────────────────
    parser.add_argument('--batch-predict-config', type=str, default='',
                        help=(
                            'JSON dict of batch prediction settings. Supported keys: '
                            'enable (bool), output_table, compute_dataset, '
                            'machine_type, starting_replica_count, max_replica_count, '
                            'batch_size, expiration_days. '
                            'Input is always the X_test split from the current training run. '
                            'Overrides the batch_prediction section in config.yaml when set. '
                            'May be base64-encoded with "base64:" prefix.'
                        ))

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Run the full XGBoost model training pipeline."""

    # ── 1. Parse arguments ─────────────────────────────────────────────────
    args = parse_arguments()
    config = create_config_from_args(args)
    print("✅ Configuration loaded")

    # ── 2. Environment setup ───────────────────────────────────────────────
    setup_environment(config)
    pd.set_option('mode.chained_assignment', None)
    print("✅ Environment configured")

    # ── 3. BigQuery client ─────────────────────────────────────────────────
    bq_client = bigquery.Client(project=config['gcp']['project'])

    # ── 4. Load data ───────────────────────────────────────────────────────
    print("\n── Step 4: Loading data from BigQuery ───────────────────────────")
    outcome_df, train_features_df, holdout_features_df = load_model_data(config, bq_client)

    # ── 5. Fill missing values ─────────────────────────────────────────────
    print("\n── Step 5: Filling missing values ───────────────────────────────")
    emb_pattern = config['data_processing']['embedding_pattern']
    train_features_df  = fill_missing_values(train_features_df,  emb_pattern)
    holdout_features_df = fill_missing_values(holdout_features_df, emb_pattern)

    # ── 6. Categorical feature engineering ────────────────────────────────
    print("\n── Step 6: Categorical feature engineering ──────────────────────")
    cat_cfg = config.get('categorical') or DEFAULT_CATEGORICAL_CONFIG

    # Apply binary mappings to BOTH train and holdout
    ohe_cols = apply_binary_mappings(train_features_df,  cat_cfg)
    _        = apply_binary_mappings(holdout_features_df, cat_cfg)

    # One-hot encode & align
    train_features_df, holdout_features_df = apply_one_hot_encoding(
        train_features_df, holdout_features_df, ohe_cols
    )

    # Sanitise column names (XGBoost / BQ safe)
    train_features_df  = sanitize_column_names(train_features_df)
    holdout_features_df = sanitize_column_names(holdout_features_df)

    # ── 7. Merge outcome + features; set index ─────────────────────────────
    print("\n── Step 7: Merging outcome and features ─────────────────────────")
    data_cfg  = config['data_processing']
    indexing  = data_cfg['indexing_var']
    outcome_v = data_cfg['outcome_var']

    df = merge_outcome_and_features(outcome_df, train_features_df, indexing, outcome_v)
    holdout_features_df.index.name = indexing   # preserve index name for later

    # ── 8. Train / test / val split ────────────────────────────────────────
    print("\n── Step 8: Creating train / test / val splits ───────────────────")
    feature_cols = [c for c in df.columns if c != outcome_v]

    X_train, X_test, y_train, y_test = train_test_split(
        df[feature_cols],
        df[outcome_v],
        test_size=data_cfg['test_size'],
        random_state=data_cfg['random_seed'],
        stratify=df[outcome_v],
    )
    X_test, X_val, y_test, y_val = train_test_split(
        X_test, y_test,
        test_size=data_cfg['val_size'],
        random_state=data_cfg['random_seed'],
        stratify=y_test,
    )

    y_train = y_train.astype('int')
    y_test  = y_test.astype('int')
    y_val   = y_val.astype('int')

    print(f"  Train : {X_train.shape[0]:,} rows  |  "
          f"Test : {X_test.shape[0]:,}  |  Val : {X_val.shape[0]:,}")
    print("Training set:"); check_label_distribution(y_train)
    print("Test set:");     check_label_distribution(y_test)

    # ── 9. Load selected features ──────────────────────────────────────────
    features_list_arg = args.selected_features_list
    features_path     = args.selected_features_path

    if features_list_arg:
        # Inline JSON array takes precedence over file path
        from trainer.config import _decode_json_arg
        decoded = _decode_json_arg(features_list_arg)
        selected_features = decoded if isinstance(decoded, list) else json.loads(features_list_arg)
        print(f"\n── Step 9: Using inline selected-features list ({len(selected_features)} features) ──")

        X_train, X_holdout_feat, selected_features = filter_to_selected_features(
            X_train, holdout_features_df, selected_features
        )
        X_test  = X_test[selected_features]
        X_val   = X_val[selected_features]
    elif features_path:
        print(f"\n── Step 9: Loading selected features from {features_path} ──")
        # Strip gs://bucket/ prefix if user passed full GCS URI
        gcs_bucket = None
        if features_path.startswith('gs://'):
            parts = features_path[5:].split('/', 1)
            gcs_bucket    = parts[0]
            features_path = parts[1]

        selected_features = load_selected_features(features_path, gcs_bucket)

        X_train, X_holdout_feat, selected_features = filter_to_selected_features(
            X_train, holdout_features_df, selected_features
        )
        X_test  = X_test[selected_features]
        X_val   = X_val[selected_features]
    else:
        print("\n── Step 9: No selected-features provided – using all features ──")
        X_holdout_feat = holdout_features_df[X_train.columns]

    # ── 10. Create DMatrix objects ─────────────────────────────────────────
    # make_dmatrix converts DataFrames to float32 numpy arrays before building
    # DMatrix, so the saved booster has NO embedded feature names.
    # This is required for Vertex AI Batch Prediction which sends raw numeric
    # arrays without column-name metadata.
    print("\n── Step 10: Creating DMatrix objects (numpy, no feature names) ──")
    dtrain = make_dmatrix(X_train, y_train)
    dtest  = make_dmatrix(X_test,  y_test)
    dval   = make_dmatrix(X_val,   y_val)
    print(f"  Feature order ({len(X_train.columns)} cols): {list(X_train.columns[:5])} …")

    # ── 11. Train model ────────────────────────────────────────────────────
    print("\n── Step 11: Training XGBoost model ──────────────────────────────")
    model_params = config['model']['params'] or DEFAULT_XGB_PARAMS
    # Merge defaults so user only needs to override what they change
    params = {**DEFAULT_XGB_PARAMS, **model_params}

    model = train_xgb_model(
        dtrain=dtrain,
        dval=dval,
        params=params,
        num_boost_round=config['model']['num_boost_round'],
        verbose_eval=config['model']['verbose_eval'],
    )

    # ── 12. Evaluate ───────────────────────────────────────────────────────
    print("\n── Step 12: Evaluating on test set ──────────────────────────────")
    roc_auc, metrics = calculate_metrics(
        model, dtest, y_test,
        percentiles=config['metrics']['percentiles'],
    )
    print(f"\n  Final ROC-AUC (test): {roc_auc:.4f}")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    # ── 12b → 16. Save, document & register the model ─────────────────────
    # (all logic lives in trainer/model_card.py)
    model_card_result = save_and_register_model(
        model        = model,
        config       = config,
        params       = params,
        roc_auc      = roc_auc,
        eval_metrics = metrics,
        X_train      = X_train,
        X_test       = X_test,
        X_val        = X_val,
    )

    # ── 17. Batch Prediction ───────────────────────────────────────────────
    # Merge any CLI-supplied batch predict overrides on top of config.yaml values.
    _bp_cli_raw = getattr(args, 'batch_predict_config', '') or ''
    if _bp_cli_raw:
        from trainer.config import _decode_json_arg
        _bp_override = _decode_json_arg(_bp_cli_raw)
        if isinstance(_bp_override, dict):
            config.setdefault('batch_prediction', {}).update(_bp_override)

    run_batch_prediction(
        config               = config,
        model_resource_name  = model_card_result.get('registry_resource', ''),
        X_test               = X_test,   # same test split used for evaluation
        y_test               = y_test,   # actual labels for comparison in output
    )

    print("\n✅ Model training pipeline completed successfully!")


if __name__ == '__main__':
    main()

