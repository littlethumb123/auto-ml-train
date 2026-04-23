"""Data loading and preprocessing for the XGBoost model training pipeline."""
import re
import pandas as pd
from google.cloud import bigquery
from pandas.api.types import is_integer_dtype as is_integer
from pandas.api.types import is_float_dtype as is_float


# ---------------------------------------------------------------------------
# BigQuery helpers
# ---------------------------------------------------------------------------

def run_bq_query(sql: str, bq_client: bigquery.Client) -> pd.DataFrame:
    """Execute a BigQuery SQL string and return a DataFrame.

    Args:
        sql: SQL query string
        bq_client: Authenticated BigQuery client

    Returns:
        pandas DataFrame with query results
    """
    print(f"Executing query:\n{sql[:300]}{'...' if len(sql) > 300 else ''}\n")
    df = bq_client.query(sql).to_dataframe()
    print(f"  → Loaded {df.shape[0]:,} rows × {df.shape[1]} cols")
    return df


def load_model_data(config: dict, bq_client: bigquery.Client):
    """Load outcome, training features, and holdout features from BigQuery.

    The config['sql_queries'] dict must contain:
        - 'outcome_query'         : SELECT individual_id, <outcome_col>
        - 'train_features_query'  : SELECT * except(<outcome cols>) WHERE split <= threshold
        - 'holdout_features_query': SELECT * except(<outcome cols>) WHERE split > threshold

    Args:
        config: Configuration dictionary (from create_config_from_args)
        bq_client: Authenticated BigQuery client

    Returns:
        tuple: (outcome_df, train_features_df, holdout_features_df)
    """
    sql = config['sql_queries']

    print("── Loading outcome data ─────────────────────────────────────────")
    outcome_df = run_bq_query(sql['outcome_query'], bq_client)

    print("── Loading training features ────────────────────────────────────")
    train_features_df = run_bq_query(sql['train_features_query'], bq_client)

    print("── Loading holdout features ─────────────────────────────────────")
    holdout_features_df = run_bq_query(sql['holdout_features_query'], bq_client)

    return outcome_df, train_features_df, holdout_features_df


# Backward-compatibility alias
load_cancer_data = load_model_data


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def fill_missing_values(df: pd.DataFrame, embedding_pattern: str = r'emb[0-255]+') -> pd.DataFrame:
    """Fill missing values in a DataFrame.

    - Embedding columns (matched by *embedding_pattern*) → filled with 0
    - Numeric columns  → filled with 0
    - String/object columns → filled with ''
    - Date/timestamp columns → left untouched (logged as warning)

    Args:
        df: DataFrame to process
        embedding_pattern: Regex pattern to identify embedding columns

    Returns:
        DataFrame with missing values filled
    """
    emb_cols = [c for c in df.columns if re.match(embedding_pattern, c)]
    if emb_cols:
        df[emb_cols] = df[emb_cols].fillna(0)

    for col in df.columns:
        dtype = df[col].dtype
        if is_integer(dtype) or is_float(dtype):
            df[col] = df[col].fillna(0)
        else:
            try:
                df[col] = df[col].fillna('')
            except Exception:
                print(f"  ⚠  DATE VARIABLE FOUND – skipping fill for '{col}' (dtype={dtype})")

    return df


def merge_outcome_and_features(
    outcome_df: pd.DataFrame,
    features_df: pd.DataFrame,
    indexing_var: str,
    outcome_var: str,
) -> pd.DataFrame:
    """Set index and inner-join outcome onto features.

    Args:
        outcome_df: DataFrame with [indexing_var, outcome_var]
        features_df: DataFrame with features (includes indexing_var)
        indexing_var: Column name used as join key / index
        outcome_var: Column name of the target variable

    Returns:
        Merged DataFrame indexed by *indexing_var*, outcome column first
    """
    outcome_df = outcome_df.set_index(indexing_var)
    features_df = features_df.set_index(indexing_var)

    df = outcome_df[[outcome_var]].merge(features_df, left_index=True, right_index=True, how='inner')
    print(f"  Merged dataset: {df.shape[0]:,} rows × {df.shape[1]} cols")
    return df

