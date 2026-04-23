"""Main entry point for Vertex AI custom training."""
import sys
import os
import argparse
import datetime
import gc
import json
import pandas as pd
from google.cloud import bigquery
from google.cloud import storage

from trainer.config import load_config, setup_environment, get_constants_from_config, create_config_from_args
from trainer.data_loader import (
    load_training_and_test_data,
    fill_missing_values,
    filter_low_variance_features,
    prepare_features_and_target
)
from trainer.feature_engineering import (
    auto_classify_features,
    fit_one_hot_encoders,
    apply_one_hot_encoding
)
from trainer.model_training import (
    train_baseline_model,
    calculate_metrics,
    run_undersampling_experiments,
    save_undersampling_results,
    run_rfecv,
    plot_rfecv_results
)
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import sanitize_column_names, check_label_distribution


def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """Upload a file to Google Cloud Storage.
    
    Args:
        bucket_name: Name of the GCS bucket
        source_file_name: Local file path to upload
        destination_blob_name: Destination path in GCS
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}")


def add_table_labels_and_expiry(bq_client, table_name, labels, expiration_days):
    """Add labels and expiration to a BigQuery table.
    
    Args:
        bq_client: BigQuery client
        table_name: Full table name (project.dataset.table)
        labels: Dictionary of labels
        expiration_days: Number of days until expiration
    """
    query = f"""
    ALTER TABLE `{table_name}` 
    SET OPTIONS (
        labels=[
            ("owner", "{labels['owner']}"), 
            ("cost_center", "{labels['costcenter']}"), 
            ("unique_id", "{labels['unique_id']}"),
            ("pipeline_type", "{labels['pipeline_type']}"),
            ("lob", "{labels['lob']}")
        ],
        expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {expiration_days} DAY)
    )
    """
    query_job = bq_client.query(query)
    query_job.result()
    print(f"✅ Added labels and {expiration_days}-day expiry to {table_name}")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Feature Engineering Pipeline')
    
    # GCP Configuration
    parser.add_argument('--gcp-project', type=str, required=True, help='GCP project ID')
    parser.add_argument('--gcp-gcp-project', type=str, required=True, help='GCP project for BigQuery queries')
    parser.add_argument('--gcp-db', type=str, required=True, help='BigQuery dataset name')
    parser.add_argument('--prefix', type=str, required=True, help='Table prefix')
    parser.add_argument('--default-exp', type=str, default='INTERVAL 2 DAY', help='Default expiration')
    parser.add_argument('--sdoh-year', type=str, required=True, help='SDOH year')
    parser.add_argument('--location', type=str, default='US', help='GCP location')
    parser.add_argument('--bucket-name', type=str, required=True, help='GCS bucket name')
    parser.add_argument('--gcs-destination-path', type=str, required=True, help='GCS destination path')
    
    # BigQuery Labels
    parser.add_argument('--owner', type=str, required=True, help='Owner email')
    parser.add_argument('--costcenter', type=str, required=True, help='Cost center')
    parser.add_argument('--unique-id', type=str, required=True, help='Unique ID')
    parser.add_argument('--pipeline-type', type=str, default='feature_engineering', help='Pipeline type')
    parser.add_argument('--lob', type=str, required=True, help='Line of business')
    parser.add_argument('--expiration-days', type=int, default=7, help='Table expiration days')
    
    # SQL Queries (as JSON string)
    parser.add_argument('--sql-queries', type=str, required=True, help='SQL queries as JSON string')
    
    # Data Processing
    parser.add_argument('--random-seed', type=int, default=35, help='Random seed')
    parser.add_argument('--numpy-seed', type=int, default=35, help='NumPy seed')
    parser.add_argument('--embedding-pattern', type=str, default='emb[0-255]+', help='Embedding pattern regex')
    parser.add_argument('--variance-threshold', type=float, default=0.001, help='Variance threshold')
    parser.add_argument('--target-column', type=str, required=True, help='Target column name')
    parser.add_argument('--exclude-for-variance', type=str, default='[]', help='Columns to exclude from variance check (JSON array)')
    parser.add_argument('--exclude-for-classification', type=str, default='[]', help='Columns to exclude from classification (JSON array)')
    
    # Feature Classification (as JSON string)
    parser.add_argument('--feature-classification', type=str, required=True, help='Feature classification config as JSON string')
    
    # One-Hot Encoding
    parser.add_argument('--min-occurrence', type=int, default=2000, help='Minimum occurrence for one-hot encoding')
    
    # Model Configuration (as JSON string)
    parser.add_argument('--model-config', type=str, required=True, help='Model configuration as JSON string')
    
    # Undersampling Configuration (as JSON string)
    parser.add_argument('--undersampling-config', type=str, required=True, help='Undersampling configuration as JSON string')
    
    # RFECV Configuration (as JSON string)
    parser.add_argument('--rfecv-config', type=str, required=True, help='RFECV configuration as JSON string')
    
    # Metrics Configuration (as JSON string)
    parser.add_argument('--metrics-config', type=str, required=True, help='Metrics configuration as JSON string')
    
    # Output Configuration (as JSON string)
    parser.add_argument('--output-config', type=str, required=True, help='Output configuration as JSON string')
    
    # BigQuery Query Configuration (as JSON string)
    parser.add_argument('--bigquery-query-config', type=str, required=True, help='BigQuery query configuration as JSON string')
    
    return parser.parse_args()


def main():
    """Main execution function for Vertex AI training."""
    # Parse arguments
    args = parse_arguments()
    
    # Create config from arguments
    config = create_config_from_args(args)
    
    print("✅ Configuration created from command-line arguments")
    
    # Setup environment
    setup_environment(config)
    pd.set_option('mode.chained_assignment', None)
    pd.set_option('compute.use_bottleneck', True)
    pd.set_option('compute.use_numexpr', True)
    
    # Get constants
    constants = get_constants_from_config(config)
    
    # Initialize BigQuery client
    bq_client = bigquery.Client(project=config['gcp']['project'])
    
    # Load data
    df_train, df_test = load_training_and_test_data(config, constants)
    
    # Preprocessing
    data_proc = config['data_processing']
    df_train = fill_missing_values(df_train, data_proc['embedding_pattern'])
    df_test = fill_missing_values(df_test, data_proc['embedding_pattern'])
    
    df_train, df_test, _ = filter_low_variance_features(
        df_train, df_test, 
        data_proc['variance_threshold'],
        data_proc['exclude_for_variance']
    )
    
    # Feature engineering
    feat_class = config['feature_classification']
    nem_to_type = auto_classify_features(
        df_train,
        unique_threshold_binary=feat_class['unique_threshold_binary'],
        unique_threshold_categorical=feat_class['unique_threshold_categorical'],
        exclude_cols=data_proc.get('exclude_for_classification', []),
        sample_size=feat_class['sample_size'],
        manual_overrides=feat_class.get('manual_overrides', {}),
        verbose=feat_class['verbose']
    )
    
    categorical_features = [f for f in nem_to_type if nem_to_type[f] == 0]
    
    encoders, categories_to_keep = fit_one_hot_encoders(
        df_train, categorical_features, config['one_hot_encoding']['min_occurrence']
    )
    
    df_train = apply_one_hot_encoding(df_train, categorical_features, encoders, categories_to_keep)
    df_test = apply_one_hot_encoding(df_test, categorical_features, encoders, categories_to_keep)
    
    df_train = sanitize_column_names(df_train)
    df_test = sanitize_column_names(df_test)
    
    # Prepare features
    target_col = data_proc['target_column']
    X_train, y_train, X_test, y_test, predictors = prepare_features_and_target(
        df_train, df_test, target_col
    )
    
    # Training
    model = train_baseline_model(X_train, y_train, config['model']['initial_model'])
    roc, metrics_results = calculate_metrics(model, X_test, y_test, config['metrics']['percentiles'])
    print("ROC: ", roc)
    for key, value in metrics_results.items():
        print(f"{key}: {value}")
    
    # Undersampling experiments
    results = run_undersampling_experiments(X_train, y_train, X_test, y_test, config)
    save_undersampling_results(results, config)
    
    # Label distribution
    print("Training Set:")
    check_label_distribution(y_train)
    print("\nTest Set:")
    check_label_distribution(y_test)
    
    # RFECV
    gc.collect()
    rfecv = run_rfecv(X_train, y_train, config)
    X_test_selected = rfecv.transform(X_test)
    plot_rfecv_results(rfecv)
    
    # Save features
    selected_features = X_train.columns[rfecv.support_]
    timestamp = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
    local_filename = f"{config['output']['features_file_prefix']}{timestamp}.txt"
    
    with open(local_filename, 'w') as f:
        f.write('\n'.join(selected_features))
    
    bucket_name = config['gcp']['bucket_name']
    destination_path = f"{config['gcp']['gcs_destination_path']}/{local_filename}"
    upload_to_gcs(bucket_name, local_filename, destination_path)
    
    # Upload to BigQuery with FIXED table names (no timestamp)
    # This allows hyperparameter tuning to reuse these tables
    train_df_selected = df_train[selected_features.tolist() + [target_col]].copy()
    test_df_selected = df_test[selected_features.tolist() + [target_col]].copy()
    
    gcp = config['gcp']
    bq_labels = config['bigquery_labels']
    
    # Get output table names from config (format with prefix)
    training_table_name = config['output']['training_table_name'].format(PREFIX=gcp['prefix'])
    test_table_name = config['output']['test_table_name'].format(PREFIX=gcp['prefix'])
    
    # Build full table names
    destination_table_train = f"{gcp['gcp_project']}.{gcp['gcp_db']}.{training_table_name}"
    destination_table_test = f"{gcp['gcp_project']}.{gcp['gcp_db']}.{test_table_name}"
    
    print(f"📊 Saving processed data to BigQuery:")
    print(f"   Training table: {destination_table_train}")
    print(f"   Test table: {destination_table_test}")
    
    train_df_selected.to_gbq(
        destination_table=destination_table_train,
        project_id=gcp['gcp_project'],
        if_exists='replace',
        location=gcp['location']
    )
    add_table_labels_and_expiry(bq_client, destination_table_train, bq_labels, bq_labels['expiration_days'])
    
    test_df_selected.to_gbq(
        destination_table=destination_table_test,
        project_id=gcp['gcp_project'],
        if_exists='replace',
        location=gcp['location']
    )
    add_table_labels_and_expiry(bq_client, destination_table_test, bq_labels, bq_labels['expiration_days'])
    
    # Write output table names to a JSON file for the next pipeline step (hyperparameter tuning)
    # Save with timestamp for tracking, but table names are fixed (no timestamp)
    output_info = {
        'training_table': destination_table_train,
        'test_table': destination_table_test,
        'target_column': target_col,
        'timestamp': timestamp,
        'features_file': destination_path,
        'gcp_project': gcp['gcp_project']
    }
    
    output_info_file = f"output_tables_info.json"  # Fixed name for pipeline output
    with open(output_info_file, 'w') as f:
        json.dump(output_info, f, indent=2)
    
    # Upload output info to GCS (for pipeline artifact)
    output_info_path = f"{config['gcp']['gcs_destination_path']}/output_tables_info.json"
    upload_to_gcs(bucket_name, output_info_file, output_info_path)
    
    print("✅ Feature engineering pipeline completed successfully!")
    print(f"📊 Output tables (FIXED NAMES - can be reused):")
    print(f"   Training: {destination_table_train}")
    print(f"   Test: {destination_table_test}")
    print(f"   Info file: {output_info_path}")
    print(f"")
    print(f"💡 To reuse these tables in hyperparameter tuning:")
    print(f"   Set in config.yaml:")
    print(f"   hyperparameter_tuning:")
    print(f"     training_table: \"{destination_table_train}\"")
    print(f"     test_table: \"{destination_table_test}\"")


if __name__ == "__main__":
    main()

