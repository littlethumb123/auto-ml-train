"""Step 2: Column pruning — remove all-null/zero and near-constant columns.

Reads output/data/<tag>/features.parquet from step 1.
Saves output/features/<tag>/kept_columns.json with columns that pass both passes.

Usage:
    pipenv run python3 scripts/2_clean_features.py --tag v1
    pipenv run python3 scripts/2_clean_features.py --tag v1 --threshold 0.004
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xgboost_model import config


def prune_parquet(parquet_path: Path, threshold: float, force_keep: list, join_keys: set) -> list:
    import pandas as pd

    print(f"  Loading {parquet_path} ...")
    t0 = time.time()
    df = pd.read_parquet(parquet_path)
    print(f"  Loaded {len(df):,} rows x {len(df.columns)} cols in {time.time() - t0:.0f}s")

    def _force_kept(name: str) -> bool:
        return any(p in name.lower() for p in force_keep)

    # Pass 1: drop all-null / all-zero columns
    t0 = time.time()
    keep_p1 = []
    for col in df.columns:
        if col in join_keys or _force_kept(col):
            keep_p1.append(col)
            continue
        s = df[col]
        if s.dtype.kind in ("f", "i", "u"):
            if (s.notna() & (s != 0)).any():
                keep_p1.append(col)
        elif s.dtype == bool:
            if s.any():
                keep_p1.append(col)
        else:
            if s.notna().any():
                keep_p1.append(col)
    dropped_p1 = len(df.columns) - len(keep_p1)
    print(f"  Pass 1: dropped {dropped_p1} all-null/zero cols in {time.time() - t0:.0f}s -> {len(keep_p1)} remaining")

    # Pass 2: near-constant filter (useful_rate < threshold)
    t0 = time.time()
    n = len(df)
    keep_p2 = []
    for col in keep_p1:
        if col in join_keys or _force_kept(col):
            keep_p2.append(col)
            continue
        s = df[col]
        if s.dtype.kind in ("f", "i", "u"):
            useful_rate = (s.notna() & (s != 0)).sum() / n
        elif s.dtype == bool:
            useful_rate = s.sum() / n
        else:
            useful_rate = s.notna().sum() / n
        if useful_rate >= threshold:
            keep_p2.append(col)
    dropped_p2 = len(keep_p1) - len(keep_p2)
    print(f"  Pass 2: dropped {dropped_p2} near-constant cols (threshold={threshold}) in {time.time() - t0:.0f}s -> {len(keep_p2)} remaining")

    return keep_p2


def main():
    parser = argparse.ArgumentParser(description="Clean feature columns (prune nulls + near-constant)")
    parser.add_argument("--tag", required=True, help="Run tag")
    parser.add_argument("--threshold", type=float, default=None,
                        help=f"Useful rate threshold (default: {config.USEFUL_THRESHOLD})")
    args = parser.parse_args()

    threshold = args.threshold if args.threshold is not None else config.USEFUL_THRESHOLD
    print(f"Step 2: Clean features (tag={args.tag}, threshold={threshold})")

    parquet_path = config.DATA_DIR / args.tag / "features.parquet"
    if not parquet_path.exists():
        print(f"  ERROR: {parquet_path} not found — run step 1 first")
        sys.exit(1)

    join_keys = {config.ID_COLUMN, config.INDEX_DATE_COLUMN}
    kept = prune_parquet(parquet_path, threshold, config.FORCE_KEEP_PATTERNS, join_keys)

    out_path = config.tag_path(config.FEATURES_DIR, args.tag, "kept_columns.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"features": kept}, f, indent=2)
    print(f"  Saved: {out_path}")
    print(f"\nNext: pipenv run python3 scripts/3_select_features.py --tag {args.tag}")


if __name__ == "__main__":
    main()
