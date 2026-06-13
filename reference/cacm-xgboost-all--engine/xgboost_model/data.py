"""Data loading: BQ export -> GCS -> Parquet -> DataFrame."""

import re
import time
from pathlib import Path

import pandas as pd
from google.cloud import bigquery


def export_bq_to_parquet(
    client: bigquery.Client,
    source_table: str,
    gcs_bucket: str,
    gcs_prefix: str,
    local_dir: Path,
) -> pd.DataFrame:
    """Export a BQ table to GCS Parquet shards, download, and load as DataFrame.

    Returns the combined DataFrame.
    """
    gcs_uri = f"gs://{gcs_bucket}/{gcs_prefix}/*.parquet"

    print(f"  Exporting {source_table} to {gcs_uri}...", flush=True)
    t0 = time.time()

    extract_job = client.extract_table(
        source_table,
        gcs_uri,
        job_config=bigquery.ExtractJobConfig(destination_format="PARQUET"),
    )
    extract_job.result()
    print(f"    Export done in {time.time() - t0:.0f}s", flush=True)

    local_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading Parquet shards to {local_dir}...", flush=True)

    from google.cloud import storage
    storage_client = storage.Client()
    bucket = storage_client.bucket(gcs_bucket)
    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    for blob in blobs:
        if blob.name.endswith(".parquet"):
            local_path = local_dir / Path(blob.name).name
            blob.download_to_filename(str(local_path))

    print(f"  Loading Parquet into DataFrame...", flush=True)
    df = pd.read_parquet(local_dir)
    print(f"    Loaded: {df.shape[0]:,} rows x {df.shape[1]:,} cols ({time.time() - t0:.0f}s total)", flush=True)
    return df


def load_parquet(path: Path) -> pd.DataFrame:
    """Load a local Parquet file, casting BQ date/time types to strings."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    print(f"  Loading {path}...", flush=True)
    table = pq.read_table(path)

    # BQ DATE/TIME columns land as dbdate/dbtime extension types; cast to str
    # so pandas can read them without db_dtypes dtype-mapping errors.
    new_cols = []
    for i in range(len(table.schema)):
        col = table.column(i)
        if pa.types.is_date(col.type) or pa.types.is_time(col.type):
            col = col.cast(pa.string())
        new_cols.append(col)
    table = pa.table(dict(zip(table.schema.names, new_cols)))

    df = table.to_pandas()
    print(f"    {df.shape[0]:,} rows x {df.shape[1]:,} cols", flush=True)
    return df


def sanitize_col_name(name: str) -> str:
    """Apply the same sanitization as prep_features column renaming.

    Needed when loading feature lists written by save_feature_list(), which strips
    the col_ numeric prefix for human readability. Re-applying this ensures feature
    names match the column names in X returned by prep_features().
    """
    clean = re.sub(r"[^\w]", "_", name)
    return f"col_{clean}" if clean[0].isdigit() else clean


def prep_features(
    df: pd.DataFrame,
    non_feature_columns: list[str],
    exclude_patterns: list[str] | None = None,
    target_column: str = "impute_outcome_flag",
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Prepare feature matrix and target from raw DataFrame.

    Returns (X, y, feature_names).
    """
    exclude_patterns = exclude_patterns or []

    # Filter to valid rows
    if "excluded_pre_index" in df.columns:
        df = df[df["excluded_pre_index"] == 0].copy()
    if target_column in df.columns:
        df = df[df[target_column].notna()].copy()

    # Identify feature columns
    all_cols = set(df.columns)
    drop_cols = set(non_feature_columns)
    for pattern in exclude_patterns:
        for col in all_cols:
            if re.search(pattern, col):
                drop_cols.add(col)

    # Drop non-numeric columns (XGBoost requires numeric input)
    object_cols = set(df.select_dtypes(include=["object", "category"]).columns)
    drop_cols |= object_cols

    feature_cols = sorted(all_cols - drop_cols - {target_column})

    X = df[feature_cols].copy()
    y = df[target_column].astype(int)

    # Sanitize column names (XGBoost doesn't like special chars)
    clean_names = {}
    for col in X.columns:
        clean = re.sub(r"[^\w]", "_", col)
        if clean[0].isdigit():
            clean = f"col_{clean}"
        clean_names[col] = clean
    X = X.rename(columns=clean_names)
    feature_cols = list(X.columns)

    print(f"  Features: {len(feature_cols):,}, Target: {target_column}", flush=True)
    print(f"  Positive rate: {y.mean():.4f} ({y.sum():,} / {len(y):,})", flush=True)
    return X, y, feature_cols
