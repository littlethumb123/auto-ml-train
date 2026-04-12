"""Feature engineering for the XGBoost model training pipeline.

Handles:
  - Binary label mappings  (gender_cd M/F → 1/0, drug_ind Y/N → 1/0)
  - One-hot encoding of region via pd.get_dummies
  - Column alignment between train and holdout sets after OHE
  - Loading the pre-selected feature list from a file or GCS
"""
import io
import pandas as pd
from google.cloud import storage


# ---------------------------------------------------------------------------
# Categorical / binary mappings
# ---------------------------------------------------------------------------

DEFAULT_CATEGORICAL_CONFIG = {
    'gender_cd': {'mapping': {'M': 1, 'F': 0}, 'fill_na': -1},
    'drug_ind':  {'mapping': {'Y': 1, 'N': 0}, 'fill_na': -1},
    'region':    {'type': 'one_hot'},
}


def apply_binary_mappings(df: pd.DataFrame, categorical_config: dict) -> list:
    """Apply Y/N and M/F style binary mappings in-place.

    Returns the list of column names that should be one-hot encoded
    (i.e. those whose type == 'one_hot').

    Args:
        df: DataFrame to transform in-place
        categorical_config: Dict of {col_name: {mapping: {}, fill_na: val}}
                            or {col_name: {type: 'one_hot'}}

    Returns:
        list of column names requiring one-hot encoding
    """
    ohe_cols = []
    for col, cfg in categorical_config.items():
        if col not in df.columns:
            print(f"  ⚠  Column '{col}' not found – skipping")
            continue
        if cfg.get('type') == 'one_hot':
            ohe_cols.append(col)
            continue
        mapping = cfg.get('mapping', {})
        fill_na = cfg.get('fill_na', -1)
        df[col] = df[col].map(mapping).fillna(fill_na)
    return ohe_cols


def apply_one_hot_encoding(
    df_train: pd.DataFrame,
    df_holdout: pd.DataFrame,
    ohe_columns: list,
) -> tuple:
    """One-hot encode columns and align holdout to training column set.

    Uses pd.get_dummies on each column, then reindexes the holdout
    DataFrame so both share exactly the same feature columns.

    Args:
        df_train: Training DataFrame
        df_holdout: Holdout / final-validation DataFrame
        ohe_columns: Column names to one-hot encode

    Returns:
        tuple: (df_train_encoded, df_holdout_encoded)
    """
    if not ohe_columns:
        return df_train, df_holdout

    df_train = pd.get_dummies(df_train, columns=ohe_columns)
    df_holdout = pd.get_dummies(df_holdout, columns=ohe_columns)

    # Align: add missing dummy cols as 0, drop extras from holdout
    train_cols = set(df_train.columns)
    holdout_cols = set(df_holdout.columns)

    for col in train_cols - holdout_cols:
        df_holdout[col] = 0
    df_holdout = df_holdout[df_train.columns]  # same column order

    print(f"  After OHE – train: {df_train.shape}, holdout: {df_holdout.shape}")
    return df_train, df_holdout


# ---------------------------------------------------------------------------
# Selected features
# ---------------------------------------------------------------------------

def load_selected_features(features_path: str, gcs_bucket: str = None) -> list:
    """Load the pre-selected feature list from a local file or GCS.

    The file is expected to have one feature name per line.

    Args:
        features_path: Local file path or GCS object path
                       (e.g. 'vertex-test/ss-models/selected_features.txt')
        gcs_bucket: GCS bucket name.  If provided, *features_path* is
                    treated as a GCS object path inside this bucket.

    Returns:
        list of feature names
    """
    if gcs_bucket:
        client = storage.Client()
        bucket = client.bucket(gcs_bucket)
        blob = bucket.blob(features_path)
        content = blob.download_as_text()
        features = [line.strip() for line in content.splitlines() if line.strip()]
        print(f"  Loaded {len(features)} features from gs://{gcs_bucket}/{features_path}")
    else:
        with open(features_path, 'r') as f:
            features = [line.strip() for line in f.readlines() if line.strip()]
        print(f"  Loaded {len(features)} features from {features_path}")

    return features


def filter_to_selected_features(
    df_train: pd.DataFrame,
    df_holdout: pd.DataFrame,
    selected_features: list,
) -> tuple:
    """Subset both DataFrames to the pre-selected feature columns.

    Features missing from either DataFrame are logged as warnings and
    silently dropped from the final feature list.

    Args:
        df_train: Training feature DataFrame
        df_holdout: Holdout feature DataFrame
        selected_features: Ordered list of desired feature names

    Returns:
        tuple: (df_train_filtered, df_holdout_filtered, valid_features)
    """
    available_train   = set(df_train.columns)
    available_holdout = set(df_holdout.columns)

    valid = [f for f in selected_features if f in available_train and f in available_holdout]
    missing = [f for f in selected_features if f not in available_train or f not in available_holdout]

    if missing:
        print(f"  ⚠  {len(missing)} selected features not found in data and will be skipped:")
        for m in missing[:10]:
            print(f"       – {m}")
        if len(missing) > 10:
            print(f"       … and {len(missing) - 10} more")

    print(f"  Using {len(valid)} / {len(selected_features)} selected features")
    return df_train[valid], df_holdout[valid], valid

