"""Feature cleaning: column pruning (Pass 1 + Pass 2) and assembly SQL generation."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from google.cloud import bigquery

NUMERIC_TYPES = {"INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}
BOOL_TYPES = {"BOOLEAN", "BOOL"}


def get_table_schemas(
    client: bigquery.Client,
    tables: dict[str, str],
) -> dict[str, list]:
    """Fetch BQ schema (metadata only, no data scan) for each table."""
    schemas = {}
    for alias, table_ref in tables.items():
        table = client.get_table(table_ref)
        schemas[alias] = table.schema
    return schemas


def check_columns_fast(
    client: bigquery.Client,
    alias: str,
    table_ref: str,
    schema: list,
    join_keys: set[str],
    force_keep_patterns: list[str] | None = None,
) -> tuple[str, list[str], int]:
    """Pass 1: Drop all-null and all-zero columns via single LOGICAL_OR query.

    Returns (alias, kept_column_names, n_dropped).
    """
    force_keep_patterns = force_keep_patterns or []
    candidates = [f for f in schema if f.name not in join_keys]

    checks = []
    for f in candidates:
        safe = f"`{f.name}`"
        if f.field_type.upper() in NUMERIC_TYPES:
            checks.append(f"LOGICAL_OR({safe} IS NOT NULL AND {safe} != 0) AS `{f.name}__keep`")
        elif f.field_type.upper() in BOOL_TYPES:
            checks.append(f"LOGICAL_OR({safe} IS NOT NULL AND {safe} = TRUE) AS `{f.name}__keep`")
        else:
            checks.append(f"LOGICAL_OR({safe} IS NOT NULL) AS `{f.name}__keep`")

    query = "SELECT\n  " + ",\n  ".join(checks) + f"\nFROM `{table_ref}`"

    print(f"  [{alias}] Pass 1: {len(candidates)} columns, single query...", flush=True)
    t0 = time.time()
    row = list(client.query(query).result())[0]
    elapsed = time.time() - t0
    rdict = dict(row.items())

    def _force_kept(name: str) -> bool:
        return any(p in name.lower() for p in force_keep_patterns)

    drop = {
        f.name for f in candidates
        if not rdict.get(f"{f.name}__keep", False) and not _force_kept(f.name)
    }
    kept = [f.name for f in schema if f.name not in drop]

    force_count = sum(1 for f in candidates if not rdict.get(f"{f.name}__keep", False) and _force_kept(f.name))
    print(f"  [{alias}] done in {elapsed:.0f}s — kept {len(kept)}, dropped {len(drop)}"
          f"{f', force-kept {force_count}' if force_count else ''}", flush=True)

    return alias, kept, len(drop)


def get_useful_rates(
    client: bigquery.Client,
    alias: str,
    table_ref: str,
    schema: list,
    surviving_cols: list[str],
    join_keys: set[str],
) -> tuple[str, dict[str, float]]:
    """Pass 2: Compute useful_rate per surviving column."""
    schema_map = {f.name: f for f in schema}
    candidates = [c for c in surviving_cols if c not in join_keys]

    checks = []
    for col in candidates:
        f = schema_map[col]
        safe = f"`{col}`"
        if f.field_type.upper() in NUMERIC_TYPES:
            checks.append(f"COUNTIF({safe} IS NOT NULL AND {safe} != 0) AS `{col}__ct`")
        elif f.field_type.upper() in BOOL_TYPES:
            checks.append(f"COUNTIF({safe} = TRUE) AS `{col}__ct`")
        else:
            checks.append(f"COUNTIF({safe} IS NOT NULL) AS `{col}__ct`")

    query = "SELECT COUNT(*) AS __total,\n  " + ",\n  ".join(checks) + f"\nFROM `{table_ref}`"

    print(f"  [{alias}] Pass 2: scanning {len(candidates)} columns...", flush=True)
    t0 = time.time()
    row = list(client.query(query).result())[0]
    elapsed = time.time() - t0
    rdict = dict(row.items())
    total = rdict["__total"]

    rates = {}
    for col in candidates:
        ct = rdict.get(f"{col}__ct", 0) or 0
        rates[col] = ct / total if total > 0 else 0.0

    print(f"  [{alias}] done in {elapsed:.0f}s", flush=True)
    return alias, rates


def prune_columns(
    client: bigquery.Client,
    tables: dict[str, str],
    join_keys: set[str] | None = None,
    useful_threshold: float = 0.004,
    force_keep_patterns: list[str] | None = None,
    max_workers: int = 4,
) -> tuple[dict[str, list[str]], dict[str, dict[str, float]]]:
    """Run Pass 1 + Pass 2 pruning across all tables.

    Returns (kept_columns, useful_rates) dicts keyed by alias.
    """
    join_keys = join_keys or {"individual_id", "index_dt"}
    force_keep_patterns = force_keep_patterns or []

    schemas = get_table_schemas(client, tables)

    # Pass 1: drop all-null/zero
    kept_columns = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(check_columns_fast, client, alias, table_ref,
                        schemas[alias], join_keys, force_keep_patterns): alias
            for alias, table_ref in tables.items()
        }
        for future in as_completed(futures):
            alias, kept, _ = future.result()
            kept_columns[alias] = kept

    # Pass 2: near-constant filter
    useful_rates = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(get_useful_rates, client, alias, tables[alias],
                        schemas[alias], kept_columns[alias], join_keys): alias
            for alias in tables
        }
        for future in as_completed(futures):
            alias, rates = future.result()
            useful_rates[alias] = rates

    # Apply threshold
    total_cols = 0
    for alias in tables:
        pruned = [
            c for c in kept_columns[alias]
            if c in join_keys or useful_rates[alias].get(c, 1.0) >= useful_threshold
        ]
        n_extra = len(kept_columns[alias]) - len(pruned)
        kept_columns[alias] = pruned
        contrib = len(pruned) if alias == list(tables.keys())[0] else len([c for c in pruned if c not in join_keys])
        total_cols += contrib
        print(f"  [{alias}] Pass 2 dropped {n_extra:>4} more -> kept {len(pruned):>5}", flush=True)

    print(f"\n  Total columns after pruning: {total_cols:,}", flush=True)
    return kept_columns, useful_rates


def build_join_sql(
    tables: dict[str, str],
    kept_columns: dict[str, list[str]],
    join_keys: set[str] | None = None,
) -> str:
    """Build the final LEFT JOIN SQL across all pruned tables."""
    join_keys = join_keys or {"individual_id", "index_dt"}
    aliases = list(tables.keys())
    base_alias = aliases[0]

    def _subselect(alias: str, table_ref: str, cols: list[str], is_base: bool) -> str:
        if is_base:
            col_list = ",\n      ".join(f"`{c}`" for c in cols)
        else:
            non_key = [c for c in cols if c not in join_keys]
            col_list = ",\n      ".join(f"`{c}`" for c in list(join_keys) + non_key)
        return f"  (\n    SELECT\n      {col_list}\n    FROM `{table_ref}`\n  ) AS {alias}"

    base_sel = _subselect("b", tables[base_alias], kept_columns[base_alias], is_base=True)
    ts_parts = []
    ts_col_parts = []
    for i, alias in enumerate(aliases[1:], 1):
        tag = f"t{i}"
        ts_parts.append(
            f"LEFT JOIN\n{_subselect(tag, tables[alias], kept_columns[alias], is_base=False)}\n"
            + "  ON " + " AND ".join(f"b.{k} = {tag}.{k}" for k in join_keys)
        )
        non_key = [c for c in kept_columns[alias] if c not in join_keys]
        ts_col_parts.append(", ".join(f"{tag}.`{c}`" for c in non_key))

    select_cols = "  b.*"
    if ts_col_parts:
        select_cols += ",\n  " + ",\n  ".join(ts_col_parts)

    return f"SELECT\n{select_cols}\nFROM\n{base_sel}\n" + "\n".join(ts_parts)


def save_kept_columns(kept_columns: dict, path: Path) -> None:
    """Save kept_columns dict as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(kept_columns, f, indent=2)
    print(f"  Saved to {path}", flush=True)


def load_kept_columns(path: Path) -> dict:
    """Load kept_columns dict from JSON."""
    with open(path) as f:
        return json.load(f)
