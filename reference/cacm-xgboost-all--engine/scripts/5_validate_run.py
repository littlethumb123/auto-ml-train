"""Step 5: Holdout validation — AUC, lift, calibration, SHAP for trained model.

Uses ONLY the test split (20%) that was set aside in step 3 and never touched since.
Uses column-selective parquet reads to avoid OOM on wide feature tables.
Loads member IDs from output/features/<data_tag>/member_split.json.

Usage:
    pipenv run python3 scripts/5_validate_run.py --tag v1
    pipenv run python3 scripts/5_validate_run.py --tag v1 --shap
    pipenv run python3 scripts/5_validate_run.py --tag v1_rfe --source-tag v1 --feature-list output/features/v1_rfe/selected_features_rfe.txt --shap
"""

import argparse
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xgboost_model import config
from xgboost_model.data import prep_features
from xgboost_model.training import load_split_ids
from xgboost_model.evaluation import (
    compute_auc,
    compute_lift_at_k,
    compute_threshold_metrics,
    compute_calibration,
    plot_roc_pr,
    run_shap_analysis,
    print_summary,
)


def main():
    parser = argparse.ArgumentParser(description="Validate trained XGBoost model")
    parser.add_argument("--tag", required=True, help="Run tag (where model is saved)")
    parser.add_argument("--source-tag", default=None,
                        help="Read parquet and split IDs from this tag (default: same as --tag)")
    parser.add_argument("--local-parquet", default=None, help="Override parquet data dir path")
    parser.add_argument("--feature-list", default=None,
                        help="Path to feature list file (default: selected_features_top<N>.txt)")
    parser.add_argument("--shap", action="store_true", help="Run SHAP analysis")
    args = parser.parse_args()

    data_tag = args.source_tag or args.tag
    print(f"Step 5: Validate (tag={args.tag}, data_tag={data_tag})")
    print(f"  Evaluating on test split (20%) only — held out since step 3")

    # Load selected features FIRST for column-selective parquet read
    if args.feature_list:
        feature_list_path = Path(args.feature_list)
    else:
        feature_list_path = config.FEATURES_DIR / data_tag / f"selected_features_top{config.TOP_N}.txt"
    with open(feature_list_path) as f:
        selected_features = [line.strip() for line in f if line.strip()]
    print(f"  Loaded {len(selected_features)} selected features from {feature_list_path.name}")

    # Load only needed columns
    meta_cols = list(config.NON_FEATURE_COLUMNS) + [
        config.OUTCOME_COLUMN, config.ID_COLUMN, config.INDEX_DATE_COLUMN,
        "excluded_pre_index",
    ]
    parquet_dir = Path(args.local_parquet) if args.local_parquet else config.DATA_DIR / data_tag
    parquet_path = parquet_dir / "features.parquet"
    schema = pq.read_schema(parquet_path)
    available_cols = set(schema.names)
    cols_to_load = list(dict.fromkeys(
        [c for c in selected_features + meta_cols if c in available_cols]
    ))
    print(f"  Column-selective load: {len(cols_to_load)} cols", flush=True)

    table = pq.read_table(parquet_path, columns=cols_to_load)
    for i in range(len(table.schema)):
        col = table.column(i)
        if pa.types.is_date(col.type) or pa.types.is_time(col.type):
            table = table.set_column(i, table.schema.field(i).name, col.cast(pa.string()))
    df = table.to_pandas()

    # Load split IDs and filter to test set only
    split_path = config.FEATURES_DIR / data_tag / "member_split.json"
    if not split_path.exists():
        print(f"  ERROR: {split_path} not found — run step 3 first")
        sys.exit(1)
    split_ids = load_split_ids(split_path)
    test_id_set = set(split_ids["test"])
    df_test = df[df[config.ID_COLUMN].isin(test_id_set)].reset_index(drop=True)
    print(f"  Test rows: {len(df_test):,} of {len(df):,} total")

    # Prep features on test set
    X_test, y_test, _ = prep_features(
        df_test, config.NON_FEATURE_COLUMNS, config.EXCLUDE_PATTERNS, config.OUTCOME_COLUMN,
    )

    available_x = set(X_test.columns)
    selected_features = [f for f in selected_features if f in available_x]
    X_test_sel = X_test[selected_features]
    print(f"  Test: {len(X_test_sel):,} rows x {len(selected_features)} features")
    print(f"  Positive rate: {y_test.mean():.4f} ({y_test.sum():,} / {len(y_test):,})")

    # Load model
    model_path = config.MODELS_DIR / args.tag / "xgb.json"
    if not model_path.exists():
        print(f"  No model found at {model_path}. Run step 4 first.")
        return

    model = XGBClassifier()
    model.load_model(str(model_path))

    preds = model.predict_proba(X_test_sel)[:, 1]

    metrics = compute_auc(y_test, preds)
    lifts = compute_lift_at_k(y_test, preds)
    print_summary(metrics, lifts, args.tag)

    thresh_df = compute_threshold_metrics(y_test.values, preds)
    thresh_path = config.tag_path(config.FEATURES_DIR, args.tag, f"threshold_metrics_{args.tag}.csv")
    thresh_df.to_csv(thresh_path, index=False)
    print(f"  Threshold metrics: {thresh_path}")

    cal = compute_calibration(y_test.values, preds)
    print(f"\n  Calibration by decile:")
    print(cal.to_string(index=False))

    plot_roc_pr(y_test.values, preds,
                config.tag_path(config.FIGURES_DIR, args.tag, f"validation_roc_pr_{args.tag}.png"))

    if args.shap:
        print(f"\n  Running SHAP analysis...")
        run_shap_analysis(
            model, X_test_sel, top_n=20,
            save_dir=str(config.FIGURES_DIR / args.tag),
        )

    print("\nValidation complete.")
    print(f"Next: /log-exp {args.tag}")


if __name__ == "__main__":
    main()
