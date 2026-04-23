import argparse
import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, Any

# ML libraries
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score, precision_recall_curve

# Google Cloud libraries
from google.cloud import bigquery
from google.cloud import storage
import hypertune


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='XGBoost Training Script for Hyperparameter Tuning')
    
    # Data arguments
    parser.add_argument('--project', type=str, required=True, help='GCP project ID')
    parser.add_argument('--training_table', type=str, required=True, help='Training table name (already processed)')
    parser.add_argument('--test_table', type=str, help='Test table name (optional, if not provided will use train_test_split)')
    parser.add_argument('--target_column', type=str, default='y', help='Target column name')
    parser.add_argument('--id_columns', type=str, nargs='*', default=[], 
                       help='ID columns to exclude from features (space-separated)')
    
    # Model output arguments
    parser.add_argument('--model_dir', type=str, required=True, help='Model output directory (GCS path)')
    parser.add_argument('--job_dir', type=str, help='Job directory for outputs')
    
    # Hyperparameters (will be provided by Vertex AI Hyperparameter Tuning)
    parser.add_argument('--eta', type=float, default=0.01, help='Learning rate')
    parser.add_argument('--max_depth', type=int, default=4, help='Maximum tree depth')
    parser.add_argument('--subsample', type=float, default=0.5, help='Subsample ratio')
    parser.add_argument('--colsample_bytree', type=float, default=1.0, help='Column sampling ratio')
    parser.add_argument('--min_child_weight', type=int, default=1, help='Minimum child weight')
    parser.add_argument('--num_boost_round', type=int, default=1000, help='Number of boosting rounds')
    parser.add_argument('--reg_lambda', type=float, default=1.0, help='L2 regularization') 
    
    # Training arguments (only used if test_table is not provided)
    parser.add_argument('--test_size', type=float, default=0.3, help='Test set size ratio (only if test_table not provided)')
    parser.add_argument('--random_state', type=int, default=4321, help='Random state for reproducibility')
    parser.add_argument('--scale_pos_weight', type=float, default=1.0, help='Scale for positive class weight (for imbalanced data)')
    return parser.parse_args()


def load_data_from_bigquery(project: str, training_table: str) -> pd.DataFrame:
    """Load already processed data from BigQuery table."""
    
    sql = f"""
    SELECT *
    FROM `{training_table}`
    """
    
    import pandas_gbq
    import tqdm

    pd.set_option('mode.chained_assignment', None)
    pd.set_option('compute.use_bottleneck', True)
    pd.set_option('compute.use_numexpr', True)
    # The SQL query is the FIRST POSITIONAL argument, not query=
    df = pandas_gbq.read_gbq(
        sql,  # First argument - the SQL query
        project_id="anbc-dev-hcm-cm-de",
        use_bqstorage_api=True,  # CRITICAL for speed
        progress_bar_type='tqdm',
        configuration={
            'query': {
                'useQueryCache': False,
                'useLegacySql': False,
            }
        },
        dialect='standard',
        auth_local_webserver=False
    )
    
    print("Successfully read data from BigQuery...")
    return df


def get_feature_columns(df: pd.DataFrame, target_column: str, id_columns: list) -> list:
    """
    Get feature columns, excluding target, ID columns, and date/datetime columns.
    
    Args:
        df: DataFrame with all columns
        target_column: Name of the target column
        id_columns: List of ID column names to exclude
    
    Returns:
        List of feature column names
    """
    # Columns to exclude
    exclude_cols = [target_column] + id_columns
    
    # Get available columns (some might not exist in the dataset)
    available_exclude_cols = [col for col in exclude_cols if col in df.columns]
    
    # Also exclude date/datetime columns (XGBoost doesn't support them)
    date_columns = []
    for col in df.columns:
        if col not in available_exclude_cols:
            dtype = str(df[col].dtype).lower()
            # Check for date/datetime types
            if any(date_type in dtype for date_type in ['date', 'datetime', 'time', 'dbdate']):
                date_columns.append(col)
    
    all_exclude_cols = available_exclude_cols + date_columns
    feature_columns = [col for col in df.columns if col not in all_exclude_cols]
    
    print(f"Excluding ID columns: {available_exclude_cols}")
    print(f"Excluding date/datetime columns: {date_columns}")
    print(f"Feature columns selected: {len(feature_columns)}")
    
    return feature_columns


# In train_model function, replace the model saving section:


def train_model(args) -> Dict[str, Any]:
    """Train the XGBoost model with hyperparameter tuning."""
    print("Starting model training...")
    print(f"Training arguments: {vars(args)}")
    
    # Load training data
    df_train = load_data_from_bigquery(args.project, args.training_table)
    
    # Prepare features and target for training
    id_cols = args.id_columns if args.id_columns else []
    feature_columns = get_feature_columns(df_train, args.target_column, id_cols)
    
    # Keep original dataframe with all columns (including IDs) for later use
    # But only use feature columns for training
    X_train = df_train[feature_columns]
    y_train = df_train[args.target_column]
    
    print(f"Training features shape: {X_train.shape}")
    print(f"Training target shape: {y_train.shape}")
    
    # Load test data (separate table or split from training)
    if args.test_table:
        print(f"Loading separate test dataset from: {args.test_table}")
        df_test = load_data_from_bigquery(args.project, args.test_table)
        
        # Keep original test dataframe with all columns
        # Ensure test data has same feature columns as training
        X_test = df_test[feature_columns]
        y_test = df_test[args.target_column]
        
        print(f"Test features shape: {X_test.shape}")
        print(f"Test target shape: {y_test.shape}")
    else:
        print("No test table provided, splitting training data...")
        # Split data if no separate test table
        X_train, X_test, y_train, y_test = train_test_split(
            X_train, y_train, 
            test_size=args.test_size, 
            random_state=args.random_state,
            stratify=y_train
        )
        print(f"Train set: {X_train.shape}, Test set: {X_test.shape}")
    
    # Prepare XGBoost matrices
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)
    
    # Set up XGBoost parameters
    params = {
        'objective': 'binary:logistic',
        'tree_method': 'hist',
        'grow_policy': 'lossguide',
        
        # Hyperparameters (tuned)
        'eta': args.eta,
        'max_depth': args.max_depth,
        'subsample': args.subsample,
        'colsample_bytree': args.colsample_bytree,
        'min_child_weight': args.min_child_weight,
        'reg_lambda': args.reg_lambda,
        'scale_pos_weight': args.scale_pos_weight, 
        
        # Fixed parameters
        'random_state': 53,  # For reproducibility
        'verbosity': 1,
        'eval_metric': 'auc'
    }
    
    print(f"Training parameters: {params}")
    
    # Train the model
    bst = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=args.num_boost_round,
        evals=[(dtrain, 'train'), (dtest, 'eval')],
        early_stopping_rounds=50,
        verbose_eval=100
    )

    # Make predictions
    y_pred = bst.predict(dtest)
    y_pred_binary = (y_pred > 0.5).astype(int)
    
    # Calculate metrics
    roc_auc = roc_auc_score(y_test, y_pred)
    # Find optimal threshold for F1 score
    precision_curve, recall_curve, thresholds_pr = precision_recall_curve(y_test, y_pred)
    # Note: thresholds_pr has one less element than precision/recall curves
    f1_scores = 2 * (precision_curve[:-1] * recall_curve[:-1]) / (precision_curve[:-1] + recall_curve[:-1] + 1e-10)
    optimal_idx = np.argmax(f1_scores)
    optimal_threshold = thresholds_pr[optimal_idx] if len(thresholds_pr) > 0 else 0.5

    # Calculate metrics at optimal threshold
    y_pred_binary_optimal = (y_pred > optimal_threshold).astype(int)
    precision_optimal = precision_score(y_test, y_pred_binary_optimal, zero_division=0)
    recall_optimal = recall_score(y_test, y_pred_binary_optimal, zero_division=0)
    f1_optimal = f1_score(y_test, y_pred_binary_optimal, zero_division=0)
    accuracy_optimal = accuracy_score(y_test, y_pred_binary_optimal)  


    # Also calculate metrics at standard thresholds for comparison
    thresholds_to_test = [0.1, 0.2, 0.3, 0.4, 0.5]
    metrics_by_threshold = {}

    for threshold in thresholds_to_test:
        y_pred_binary = (y_pred > threshold).astype(int)
        metrics_by_threshold[threshold] = {
            'precision': precision_score(y_test, y_pred_binary, zero_division=0),
            'recall': recall_score(y_test, y_pred_binary, zero_division=0),
            'f1': f1_score(y_test, y_pred_binary, zero_division=0),
            'accuracy': accuracy_score(y_test, y_pred_binary)
        }
        # Print metrics at different thresholds
    for threshold, metrics in metrics_by_threshold.items():
        print(f"\nThreshold {threshold}: F1={metrics['f1']:.4f}, Precision={metrics['precision']:.4f}, Recall={metrics['recall']:.4f}")
    print("----------------------------------")
    print(f"ROC AUC: {roc_auc:.4f} (threshold-independent)")
    print(f"Optimal Threshold: {optimal_threshold:.4f}")
    print(f"F1 at Optimal Threshold: {f1_optimal:.4f}")
    print(f"Precision at Optimal: {precision_optimal:.4f}")
    print(f"Recall at Optimal: {recall_optimal:.4f}")
    print(f"Accuracy at Optimal: {accuracy_optimal:.4f}") 
    print("----------------------------------")

    # Save the model to GCS
    # Use AIP_MODEL_DIR from environment if available, otherwise use args.model_dir
    model_dir = os.getenv('AIP_MODEL_DIR', args.model_dir)
    
    # If model_dir still contains unresolved placeholder, try to construct from AIP_MODEL_DIR
    if '{{channel' in model_dir or not model_dir.startswith('gs://'):
        # Fallback to AIP_MODEL_DIR or construct from known paths
        model_dir = os.getenv('AIP_MODEL_DIR', '')
        if not model_dir:
            raise ValueError(f"Could not resolve model_dir. Got: {args.model_dir}")
    
    # Get trial ID for unique model naming
    trial_id = os.getenv('CLOUD_ML_TRIAL_ID', 'trial_0')
    
    # Process model directory and create output path
    model_dir = model_dir.rstrip('/')
    model_output_dir = f"{model_dir}/hp_model_output"
    
    # Create unique model filename with trial ID and hyperparameters
    model_filename = f"model_trial_{trial_id}_eta{args.eta}_depth{args.max_depth}_roc{roc_auc:.4f}.bst"
    
    local_model_path = 'model.bst'
    bst.save_model(local_model_path)
    
    client = storage.Client()
    bucket_name = model_output_dir.replace('gs://', '').split('/')[0]
    
    # Get the prefix (path after bucket name)
    prefix_parts = model_output_dir.replace('gs://', '').split('/')[1:]
    # Filter out empty strings to avoid double slashes
    prefix_parts = [p for p in prefix_parts if p]
    prefix = '/'.join(prefix_parts) if prefix_parts else ''
    
    # Construct full blob path
    if prefix:
        blob_path = f"{prefix}/{model_filename}"
    else:
        blob_path = model_filename
        
    # Save model
    model_blob = client.bucket(bucket_name).blob(blob_path)
    model_blob.upload_from_filename(local_model_path)
    
    full_model_path = f"{model_output_dir}/{model_filename}"
    print(f"Model saved to: {full_model_path}")
    print(f"Trial ID: {trial_id}")

    return {
    'roc_auc': roc_auc,
    'accuracy': accuracy_optimal,  # FIXED: was undefined
    'precision': precision_optimal,  # FIXED: was undefined
    'recall': recall_optimal,  # FIXED: was undefined
    'f1': f1_optimal,  # FIXED: was undefined
    'optimal_threshold': optimal_threshold,  # ADD: useful to track
    'metrics_by_threshold': metrics_by_threshold,  # ADD: for analysis
    'model': bst,
    'model_path': full_model_path
    }


if __name__ == '__main__':
    args = parse_arguments()
    print("Arguments received:", sys.argv)
    
    print("Starting XGBoost training with hyperparameter tuning...")
    print(f"Arguments: {vars(args)}")
    
    try:
        # Train the model
        results = train_model(args)
        
        # Report metrics to Vertex AI Hyperparameter Tuning
        hpt = hypertune.HyperTune()
        
        # Report all metrics (Vertex AI will optimize based on the primary metric)
        hpt.report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag='roc_auc',
            metric_value=results['roc_auc']
        )
        hpt.report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag='accuracy',
            metric_value=results['accuracy']
        )
        hpt.report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag='precision',
            metric_value=results['precision']
        )
        hpt.report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag='recall',
            metric_value=results['recall']
        )
        hpt.report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag='f1',
            metric_value=results['f1']
        )
        
        print(f"Training completed successfully!")
        print(f"Final ROC AUC: {results['roc_auc']:.4f}")
        print(f"Final Accuracy: {results['accuracy']:.4f}")
        
    except Exception as e:
        print(f"Training failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)