"""Data loading and preprocessing for the Feature Engineering pipeline.

Public API
----------
``load_training_and_test_data(config, constants)``
    Substitutes SQL placeholders, runs both queries against BigQuery via
    ``pandas_gbq``, and returns ``(df_train, df_test)``.

``fill_missing_values(df, embedding_pattern)``
    Fills NAs: embedding columns (matched by regex) and all other numerics → 0,
    string/object columns → ''. Date columns are skipped with a warning.

``filter_low_variance_features(df_train, df_test, variance_threshold, exclude_cols)``
    Computes per-column variance on the training set and drops columns below
    *variance_threshold* from both DataFrames. The target column and any other
    columns listed in *exclude_cols* are never dropped.

``prepare_features_and_target(df_train, df_test, target_column)``
    Splits each DataFrame into features (numeric columns only) and target,
    returning ``(X_train, y_train, X_test, y_test, predictors)``.
"""
import pandas as pd
import pandas_gbq
import re
from pandas.api.types import is_integer_dtype as is_integer
from pandas.api.types import is_float_dtype as is_float
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import process_sql_file, sanitize_column_names




def load_data_from_bigquery(sql_query, project_id, config):
    """Load data from BigQuery.
    
    Args:
        sql_query: SQL query string
        project_id: GCP project ID
        config: Configuration dictionary with bigquery_query settings
        
    Returns:
        pandas DataFrame: Loaded data
    """
    bq_config = config['bigquery_query']
    
    # Control progress bar based on config setting
    # Set progress_bar_enabled: false in config.yaml to reduce log noise
    # When enabled, progress bar updates frequently and can flood logs
    if bq_config.get('progress_bar_enabled', False):
        progress_bar_type = bq_config.get('progress_bar_type', 'tqdm')
    else:
        progress_bar_type = None  # Disabled to reduce log noise
    
    return pandas_gbq.read_gbq(
        sql_query,
        project_id=project_id,
        use_bqstorage_api=bq_config['use_bqstorage_api'],
        progress_bar_type=progress_bar_type,
        configuration={
            'query': {
                'useQueryCache': bq_config['use_query_cache'],
                'useLegacySql': bq_config['use_legacy_sql'],
            }
        },
        dialect=bq_config['dialect'],
        auth_local_webserver=bq_config['auth_local_webserver']
    )


def load_training_and_test_data(config, constants):
    """Load both training and test datasets from BigQuery.
    
    Args:
        config: Configuration dictionary
        constants: Constants dictionary for SQL processing
        
    Returns:
        tuple: (training_df, test_df)
    """
    sql_queries = config['sql_queries']
    
    # Process SQL queries
    sql_train = process_sql_file(sql_queries['training_query'], constants)
    sql_test = process_sql_file(sql_queries['test_query'], constants)
    
    print("Loading training data from BigQuery...")
    print(sql_train)
    df_train = load_data_from_bigquery(
        sql_train, 
        config['gcp']['project'], 
        config
    )
    print(f"Training data shape: {df_train.shape}")
    
    print("\nLoading test data from BigQuery...")
    print(sql_test)
    df_test = load_data_from_bigquery(
        sql_test, 
        config['gcp']['project'], 
        config
    )
    print(f"Test data shape: {df_test.shape}")
    
    return df_train, df_test


def fill_missing_values(df, embedding_pattern):
    """Fill missing values in dataframe.
    
    Args:
        df: DataFrame to process
        embedding_pattern: Regex pattern for embedding columns
        
    Returns:
        pandas DataFrame: DataFrame with filled missing values
    """
    # Fill embedding columns
    emb_col = [col for col in df.columns if re.match(embedding_pattern, col)]
    if emb_col:
        df[emb_col] = df[emb_col].fillna(0)
    
    # Fill other columns
    for c in df.columns:
        dt = df[c].dtype
        if is_integer(dt) or is_float(dt):
            df[c] = df[c].fillna(0)
        else:
            try:
                df[c] = df[c].fillna('')
            except Exception as e:
                print(f"ERROR - DATE VARIABLE FOUND: {c}, dtype: {dt}, error: {e}")
    
    return df


def filter_low_variance_features(df_train, df_test, variance_threshold, exclude_cols):
    """Filter out low variance features.
    
    Args:
        df_train: Training DataFrame
        df_test: Test DataFrame
        variance_threshold: Variance threshold for filtering
        exclude_cols: Columns to exclude from variance check
        
    Returns:
        tuple: (filtered_train_df, filtered_test_df, dropped_columns)
    """
    numeric_train_cols = [
        col for col in df_train.columns 
        if is_integer(df_train[col].dtype) or is_float(df_train[col].dtype)
    ]
    numeric_to_check = [col for col in numeric_train_cols if col not in exclude_cols]
    
    print(f"Checking variance on {len(numeric_to_check)} numeric features...")
    variance = df_train[numeric_to_check].var()
    low_variance_cols = variance[variance < variance_threshold].index.tolist()
    
    if low_variance_cols:
        print(f"Dropping {len(low_variance_cols)} columns with low variance")
        df_train = df_train.drop(columns=low_variance_cols)
        df_test = df_test.drop(columns=[col for col in low_variance_cols if col in df_test.columns])
        dropped_columns = low_variance_cols
    else:
        print("No low variance columns found")
        dropped_columns = []
    
    print(f"Training data shape after variance filter: {df_train.shape}")
    print(f"Test data shape after variance filter: {df_test.shape}")
    
    return df_train, df_test, dropped_columns


def prepare_features_and_target(df_train, df_test, target_column):
    """Prepare feature matrices and target vectors.
    
    Args:
        df_train: Training DataFrame
        df_test: Test DataFrame
        target_column: Name of target column
        
    Returns:
        tuple: (X_train, y_train, X_test, y_test, predictors)
    """
    numeric_cols = [
        col for col in df_train.columns 
        if is_integer(df_train[col].dtype) or is_float(df_train[col].dtype)
    ]
    predictors = [col for col in numeric_cols if col != target_column]
    
    X_train = df_train[predictors]
    y_train = df_train[target_column].astype('int')
    X_test = df_test[predictors]
    y_test = df_test[target_column].astype('int')
    
    return X_train, y_train, X_test, y_test, predictors

