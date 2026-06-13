"""Step 4: Train final XGBoost model on selected features.

Trains on the combined train+val split (80%) using the member IDs saved by step 3.
Test set (20%) is never loaded here — all final metrics are in step 5.

Uses column-selective parquet reads to avoid OOM on wide feature tables:
only selected_features + metadata columns are loaded.

Usage:
    pipenv run python3 scripts/4_train_model.py --tag v1
    pipenv run python3 scripts/4_train_model.py --tag v1_rfe --source-tag v1 --feature-list output/features/v1_rfe/selected_features_rfe.txt
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xgboost_model import config
from xgboost_model.data import prep_features
from xgboost_model.training import load_split_ids, train_on_selected, save_model


def main():
    parser = argparse.ArgumentParser(description="Train XGBoost on selected features")
    parser.add_argument("--tag", required=True, help="Run tag (output goes here)")
    parser.add_argument("--source-tag", default=None,
                        help="Read parquet and split IDs from this tag (default: same as --tag)")
    parser.add_argument("--local-parquet", default=None, help="Override parquet data dir path")
    parser.add_argument("--feature-list", default=None,
                        help="Path to feature list file (default: selected_features_top<N>.txt)")
    args = parser.parse_args()

    data_tag = args.source_tag or args.tag
    print(f"Step 4: Train model (tag={args.tag}, data_tag={data_tag})")
    print(f"  Training on train+val (80%) — test set reserved for step 5")

    # Load selected features FIRST for column-selective parquet reads
    if args.feature_list:
        feature_list_path = Path(args.feature_list)
    else:
        feature_list_path = config.FEATURES_DIR / data_tag / f"selected_features_top{config.TOP_N}.txt"
    with open(feature_list_path) as f:
        selected_features = [line.strip() for line in f if line.strip()]
    print(f"  Loaded {len(selected_features)} selected features from {feature_list_path.name}")

    # Columns needed: selected features + metadata
    meta_cols = list(config.NON_FEATURE_COLUMNS) + [
        config.OUTCOME_COLUMN, config.ID_COLUMN, config.INDEX_DATE_COLUMN,
        "excluded_pre_index",
    ]

    # Get parquet schema to filter to available columns only
    parquet_dir = Path(args.local_parquet) if args.local_parquet else config.DATA_DIR / data_tag
    parquet_path = parquet_dir / "features.parquet"
    schema = pq.read_schema(parquet_path)
    available = set(schema.names)
    cols_to_load = list(dict.fromkeys(
        [c for c in selected_features + meta_cols if c in available]
    ))
    print(f"  Column-selective load: {len(cols_to_load)} cols "
          f"(of {len(schema.names)} in parquet)", flush=True)

    table = pq.read_table(parquet_path, columns=cols_to_load)
    for i in range(len(table.schema)):
        col = table.column(i)
        if pa.types.is_date(col.type) or pa.types.is_time(col.type):
            table = table.set_column(i, table.schema.field(i).name, col.cast(pa.string()))
    df = table.to_pandas()
    print(f"  Loaded {len(df):,} rows x {len(df.columns)} cols", flush=True)

    # Load split IDs — filter to trainval, never expose test
    split_path = config.FEATURES_DIR / data_tag / "member_split.json"
    if not split_path.exists():
        print(f"  ERROR: {split_path} not found — run step 3 first")
        sys.exit(1)
    split_ids = load_split_ids(split_path)
    trainval_ids = set(split_ids["train"]) | set(split_ids["val"])
    df_trainval = df[df[config.ID_COLUMN].isin(trainval_ids)].reset_index(drop=True)
    print(f"  Trainval rows: {len(df_trainval):,} of {len(df):,} total "
          f"(test={len(split_ids['test']):,} not loaded)")

    # Load HPO best params if step 3b was run
    train_params = config.xgb_params()
    best_params_path = config.FEATURES_DIR / args.tag / "best_params.json"
    if best_params_path.exists():
        with open(best_params_path) as f:
            best_params = json.load(f)
        train_params.update(best_params)
        print(f"  HPO params loaded: {best_params}")
    else:
        print(f"  Using config params (run 3b_tune_hyperparams.py for HPO)")

    X, y, _ = prep_features(df_trainval, config.NON_FEATURE_COLUMNS,
                             config.EXCLUDE_PATTERNS, config.OUTCOME_COLUMN)

    # Map selected features to sanitized column names in X
    available_x = set(X.columns)
    model_features = [f for f in selected_features if f in available_x]
    print(f"  Using {len(model_features)} features (of {len(selected_features)} selected)")

    t0 = time.time()
    model = train_on_selected(X, y, model_features, train_params)
    print(f"  Training done in {time.time() - t0:.0f}s")

    # Save model
    model_path = config.tag_path(config.MODELS_DIR, args.tag, "xgb.json")
    save_model(model, model_path)
    print(f"  Model saved: {model_path}")

    print(f"\nNext: pipenv run python3 scripts/5_validate_run.py --tag {args.tag}"
          + (f" --source-tag {data_tag}" if data_tag != args.tag else "")
          + (f" --feature-list {feature_list_path}" if args.feature_list else "")
          + " --shap")


if __name__ == "__main__":
    main()
