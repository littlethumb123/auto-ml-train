"""Step 1: Pull feature + outcome tables from BigQuery to local Parquet.

Reads project.yaml for:
  data.feature_tables  — list of fully-qualified BQ feature tables (joined on id_column)
  data.feature_table   — single BQ feature table (alternative to feature_tables)
  data.outcome_table   — fully-qualified BQ outcome table
  data.outcome_column  — outcome flag column name
  data.id_column       — member ID column (join key)

Output: output/data/<tag>/features.parquet

Usage:
    pipenv run python3 scripts/1_pull_features.py --tag v1
    pipenv run python3 scripts/1_pull_features.py --tag v1 --dry-run
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xgboost_model import config

from google.cloud import bigquery


def build_query(cfg) -> str:
    id_col = cfg.ID_COLUMN
    outcome_col = cfg.OUTCOME_COLUMN
    outcome_tbl = cfg.OUTCOME_TABLE
    tables = cfg.FEATURE_TABLES

    if len(tables) == 1:
        feature_tbl = tables[0]
        if outcome_tbl and outcome_tbl != feature_tbl:
            return (
                f"SELECT f.*, o.`{outcome_col}`\n"
                f"FROM `{feature_tbl}` f\n"
                f"LEFT JOIN `{outcome_tbl}` o ON f.`{id_col}` = o.`{id_col}`\n"
                f"WHERE o.`{outcome_col}` IS NOT NULL"
            )
        return (
            f"SELECT *\n"
            f"FROM `{feature_tbl}`\n"
            f"WHERE `{outcome_col}` IS NOT NULL"
        )

    # Multiple feature tables: LEFT JOIN all on id_col; subsequent tables contribute
    # all columns except the join key to avoid duplicates.
    extra_joins = "\n".join(
        f"LEFT JOIN `{tbl}` f{i+1} ON f0.`{id_col}` = f{i+1}.`{id_col}`"
        for i, tbl in enumerate(tables[1:])
    )
    extra_cols = "".join(
        f"\n, f{i+1}.* EXCEPT ({id_col})"
        for i in range(len(tables) - 1)
    )
    if outcome_tbl:
        outcome_join = f"\nLEFT JOIN `{outcome_tbl}` o ON f0.`{id_col}` = o.`{id_col}`"
        outcome_select = f"\n, o.`{outcome_col}`"
        where = f"\nWHERE o.`{outcome_col}` IS NOT NULL"
    else:
        outcome_join = ""
        outcome_select = ""
        where = f"\nWHERE f0.`{outcome_col}` IS NOT NULL"

    return (
        f"SELECT f0.*{extra_cols}{outcome_select}\n"
        f"FROM `{tables[0]}` f0\n"
        f"{extra_joins}{outcome_join}{where}"
    )


def main():
    parser = argparse.ArgumentParser(description="Pull BQ feature + outcome tables to local Parquet")
    parser.add_argument("--tag", required=True, help="Run tag (e.g. v1)")
    parser.add_argument("--dry-run", action="store_true", help="Print query without executing")
    args = parser.parse_args()

    print(f"Step 1: Pull features (tag={args.tag})")
    for i, tbl in enumerate(config.FEATURE_TABLES):
        label = "feature_table" if len(config.FEATURE_TABLES) == 1 else f"feature_tables[{i}]"
        print(f"  {label}: {tbl}")
    print(f"  outcome_table : {config.OUTCOME_TABLE or '(same as feature_table)'}")
    print(f"  outcome_column: {config.OUTCOME_COLUMN}")
    print(f"  id_column     : {config.ID_COLUMN}")

    if not config.FEATURE_TABLES:
        print("\n  ERROR: data.feature_table(s) not set in project.yaml")
        sys.exit(1)

    query = build_query(config)
    print(f"\n  Query:\n{query}\n")

    if args.dry_run:
        print("  [dry-run] No data pulled.")
        return

    out_dir = config.DATA_DIR / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "features.parquet"

    client = bigquery.Client(project=config.GCP_PROJECT)

    print(f"  Executing query...")
    t0 = time.time()
    df = client.query(query).to_dataframe(
        create_bqstorage_client=True,
        progress_bar_type=None,
    )
    elapsed = time.time() - t0
    print(f"  Fetched {len(df):,} rows x {len(df.columns)} cols in {elapsed:.0f}s")

    df.to_parquet(out_path, index=False)
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  Saved: {out_path}  ({size_mb:.1f} MB)")
    print(f"\nNext: pipenv run python3 scripts/2_clean_features.py --tag {args.tag}")


if __name__ == "__main__":
    main()
