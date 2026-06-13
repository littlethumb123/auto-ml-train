"""Step 3: Feature selection — train XGBoost on all features, select top-N by importance.

Splits data into train/val/test (60/20/20) and saves member IDs per split to
output/features/<tag>/member_split.json — all downstream steps (3b, 3c, 4, 5) load
this file so every experiment shares the exact same holdout.

Trains on train (60%), evaluates feature quality on val (20%).
Test set (20%) is never loaded here — it's reserved for step 5.

Usage:
    pipenv run python3 scripts/3_select_features.py --tag v1
    pipenv run python3 scripts/3_select_features.py --tag v1 --top-n 500
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xgboost_model import config
from xgboost_model.data import load_parquet, prep_features
from xgboost_model.training import (
    split_data_three_way,
    save_split_ids,
    smoke_test,
    train_full_model,
    select_top_features,
    save_model,
    save_feature_list,
    save_importance,
)
from xgboost_model.evaluation import compute_auc, compute_lift_at_k, print_summary


def main():
    parser = argparse.ArgumentParser(description="Feature selection via XGBoost importance")
    parser.add_argument("--tag", required=True, help="Run tag")
    parser.add_argument("--top-n", type=int, default=None, help=f"Features to select (default: {config.TOP_N})")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip smoke test")
    args = parser.parse_args()

    top_n = args.top_n or config.TOP_N
    print(f"Step 3: Feature selection (tag={args.tag}, top_n={top_n})")

    # Load data from step 1
    parquet_path = config.DATA_DIR / args.tag / "features.parquet"
    if not parquet_path.exists():
        print(f"  ERROR: {parquet_path} not found — run step 1 first")
        sys.exit(1)
    df = load_parquet(config.DATA_DIR / args.tag)

    # Apply kept_columns filter from step 2 (if available)
    kept_path = config.FEATURES_DIR / args.tag / "kept_columns.json"
    if kept_path.exists():
        with open(kept_path) as f:
            kept = json.load(f).get("features", [])
        available = [c for c in kept if c in df.columns]
        df = df[available]
        print(f"  Applied kept_columns filter: {len(available)} columns")

    # Prep features (full df — we split AFTER so we can save member IDs per split)
    X, y, feature_names = prep_features(df, config.NON_FEATURE_COLUMNS, config.EXCLUDE_PATTERNS,
                                        config.OUTCOME_COLUMN)

    # Three-way stratified split — indices align with df so we can look up member IDs
    X_train, X_val, X_test, y_train, y_val, y_test = split_data_three_way(
        X, y, config.VAL_SIZE, config.TEST_SIZE, config.RANDOM_STATE,
    )

    # Persist split IDs — all downstream steps load this file for reproducible splits
    split_path = config.tag_path(config.FEATURES_DIR, args.tag, "member_split.json")
    save_split_ids(df, config.ID_COLUMN, X_train.index, X_val.index, X_test.index, split_path)

    # Smoke test on train set
    if not args.skip_smoke:
        smoke_test(X_train, y_train, config.xgb_params(), config.SMOKE_TEST_N)

    # Train on train (60%) for importance ranking
    print("\n  Training on all features for importance ranking (train set)...")
    model_all = train_full_model(X_train, y_train, config.xgb_params())

    # Evaluate on val (20%) — test set NEVER touched in this step
    preds_val = model_all.predict_proba(X_val)[:, 1]
    metrics_all = compute_auc(y_val, preds_val)
    lifts_all = compute_lift_at_k(y_val, preds_val)
    print_summary(metrics_all, lifts_all, "all features (val)")

    # Select top-N
    selected, importance = select_top_features(model_all, feature_names, top_n)

    # Save artifacts
    save_model(model_all, config.tag_path(config.MODELS_DIR, args.tag, "xgb_all_features.json"))
    save_feature_list(selected, config.tag_path(config.FEATURES_DIR, args.tag, f"selected_features_top{top_n}.txt"))
    save_importance(importance, config.tag_path(config.FEATURES_DIR, args.tag, "feature_importance_ranking.csv"))

    print(f"\nNext: pipenv run python3 scripts/4_train_model.py --tag {args.tag}")
    print(f"  Or HPO: pipenv run python3 scripts/3b_tune_hyperparams.py --tag {args.tag}")
    print(f"  Or RFE: pipenv run python3 scripts/3c_rfe.py --tag rfe_{args.tag} --source-tag {args.tag}")


if __name__ == "__main__":
    main()
