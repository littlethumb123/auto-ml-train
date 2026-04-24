"""BigQuery Storage Read API loader — shared across auto_train campaigns.

Uses parallel gRPC Arrow streams for high-throughput reads (~50-100x faster
than the REST list_rows API). Avoids the "Response too large" error entirely
since data is streamed directly from managed storage.

Usage:
    from shared.bq_loader import load_bigquery_table_storage_api
    df = load_bigquery_table_storage_api("project.dataset.table")
"""
from __future__ import annotations

import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
import pyarrow as pa
from google.cloud import bigquery
from google.cloud.bigquery_storage import BigQueryReadClient, types
from tqdm.auto import tqdm


def _get_clients():
    """Return (bigquery.Client, BigQueryReadClient) using default credentials."""
    import google.auth
    credentials, project = google.auth.default()
    bq = bigquery.Client(credentials=credentials, project=project)
    bqs = BigQueryReadClient(credentials=credentials)
    return bq, bqs


def downcast_numeric_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce numeric memory footprint without changing semantic meaning."""
    float64_cols = df.select_dtypes(include=["float64"]).columns
    int64_cols = df.select_dtypes(include=["int64"]).columns
    if len(float64_cols):
        df[float64_cols] = df[float64_cols].apply(pd.to_numeric, downcast="float")
    if len(int64_cols):
        df[int64_cols] = df[int64_cols].apply(pd.to_numeric, downcast="integer")
    return df


def _read_stream_to_arrow(
    stream_name: str,
    read_session: types.ReadSession,
    bqstorage_client: BigQueryReadClient,
) -> pa.Table:
    """Read one BigQuery Storage stream into a PyArrow Table (thread-safe)."""
    reader = bqstorage_client.read_rows(stream_name)
    return reader.to_arrow(read_session)


def load_bigquery_table_storage_api(
    table_id: str,
    max_stream_count: int = 10,
    optimize_dtypes: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """Load a BigQuery table via the Storage Read API (gRPC + Arrow).

    Args:
        table_id: Fully-qualified BQ table path (project.dataset.table).
        max_stream_count: Max parallel gRPC streams (more = faster, more memory).
        optimize_dtypes: Downcast float64/int64 to halve memory usage.
        verbose: Print progress and size summary.

    Returns:
        DataFrame with all columns from the table.
    """
    bq_client, bqs_client = _get_clients()

    table_ref = bq_client.get_table(table_id)
    total_rows = table_ref.num_rows
    bq_table_path = (
        f"projects/{table_ref.project}"
        f"/datasets/{table_ref.dataset_id}"
        f"/tables/{table_ref.table_id}"
    )
    parent = f"projects/{table_ref.project}"

    session = bqs_client.create_read_session(
        parent=parent,
        read_session=types.ReadSession(
            table=bq_table_path,
            data_format=types.DataFormat.ARROW,
        ),
        max_stream_count=max_stream_count,
    )

    n_streams = len(session.streams)
    if verbose:
        print(f"  Storage API: {total_rows:,} rows, {n_streams} parallel streams")

    if n_streams == 0:
        return pd.DataFrame()

    arrow_tables: list[pa.Table] = []
    with ThreadPoolExecutor(max_workers=n_streams) as executor:
        futures = {
            executor.submit(_read_stream_to_arrow, s.name, session, bqs_client): i
            for i, s in enumerate(session.streams)
        }
        pbar = tqdm(
            total=total_rows,
            desc=f"Loading {table_id.split('.')[-1][:40]}",
            unit=" rows",
            unit_scale=True,
            disable=not verbose,
        )
        for future in as_completed(futures):
            tbl = future.result()
            arrow_tables.append(tbl)
            pbar.update(tbl.num_rows)
        pbar.close()

    combined = pa.concat_tables(arrow_tables)
    df = combined.to_pandas()
    del combined, arrow_tables
    gc.collect()

    if optimize_dtypes:
        df = downcast_numeric_dtypes(df)

    if verbose:
        mb = df.memory_usage(deep=True).sum() / (1024 ** 2)
        print(f"  Loaded {len(df):,} rows × {len(df.columns)} cols — {mb:.0f} MB")

    return df
