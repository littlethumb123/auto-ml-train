"""Step 3c: Feature selection via Recursive Feature Elimination with Cross-Validation (RFECV).

Fast mode (default): starts from the importance-ranked top-N list produced by step 3,
then runs RFECV to find the minimal subset that maximizes AUC-ROC. This is ~10x faster
than starting from all cleaned features.

Runs RFECV on the train split (60%) only. Reports val AUC (20%) after selection.
Test set (20%) is never loaded here.

Loads member_split.json from source_tag's features dir to share the same split as step 3.

Output:
  output/features/<tag>/selected_features_rfe.txt  — feature list (compatible with step 4)
  output/features/<tag>/rfe_support.csv            — per-feature ranking
  output/features/<tag>/rfe_cv_scores.csv          — CV AUC curve vs feature count

Usage:
    pipenv run python3 scripts/3c_rfe.py --tag v1_rfe --source-tag v1
    pipenv run python3 scripts/3c_rfe.py --tag v1_rfe --source-tag v1 --step 10 --cv-folds 3
    pipenv run python3 scripts/3c_rfe.py --tag v1_rfe --source-tag v1 --no-fast
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from sklearn.feature_selection import RFECV
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xgboost_model import config
from xgboost_model.data import prep_features
from xgboost_model.training import load_split_ids


def main():
    parser = argparse.ArgumentParser(description="RFECV feature selection")
    parser.add_argument("--tag", required=True, help="Output tag for this experiment")
    parser.add_argument("--source-tag", required=True,
                        help="Tag to read parquet and split from (must have member_split.json)")
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--step", default="0.05",
                        help="Features to remove per iteration: float = fraction, int = count (default: 0.05)")
    parser.add_argument("--min-features", type=int, default=10)
    parser.add_argument("--no-fast", action="store_true",
                        help="Start from all cleaned features instead of importance top-N")
    args = parser.parse_args()

    step = int(args.step) if args.step.isdigit() else float(args.step)

    print(f"Step 3c: RFECV feature selection")
    print(f"  tag={args.tag}  source={args.source_tag}  cv={args.cv_folds}  step={step}")
    print(f"  RFECV on train split (60%) only — val used for sanity check")

    parquet_path = config.DATA_DIR / args.source_tag / "features.parquet"
    if not parquet_path.exists():
        print(f"  ERROR: {parquet_path} not found — run steps 1-2 on tag '{args.source_tag}' first")
        sys.exit(1)

    # Load split IDs — same split as step 3 and 3b
    split_path = config.FEATURES_DIR / args.source_tag / "member_split.json"
    if not split_path.exists():
        print(f"  ERROR: {split_path} not found — run step 3 on '{args.source_tag}' first")
        sys.exit(1)
    split_ids = load_split_ids(split_path)
    train_id_set = set(split_ids["train"])
    val_id_set = set(split_ids["val"])
    print(f"  Split: train={len(train_id_set):,}  val={len(val_id_set):,}  "
          f"test={len(split_ids['test']):,} (test not loaded)")

    # Fast mode: read feature list BEFORE loading parquet so we only pull needed columns.
    import pyarrow.parquet as pq
    import pyarrow as pa
    cols_to_load = None
    if not args.no_fast:
        feat_path = config.FEATURES_DIR / args.source_tag / f"selected_features_top{config.TOP_N}.txt"
        if feat_path.exists():
            with open(feat_path) as f:
                importance_features = [line.strip() for line in f if line.strip()]
            cols_to_load = importance_features + [config.OUTCOME_COLUMN, config.ID_COLUMN,
                                                   config.INDEX_DATE_COLUMN]
            print(f"  Fast mode: loading {len(importance_features)} importance-ranked columns "
                  f"(from {feat_path.name})")
        else:
            print(f"  WARN: {feat_path} not found — falling back to full column load")
    else:
        print(f"  Full mode: loading all cleaned features")

    print(f"  Loading parquet...", flush=True)
    table = pq.read_table(parquet_path, columns=cols_to_load)
    for i in range(len(table.schema)):
        col = table.column(i)
        if pa.types.is_date(col.type) or pa.types.is_time(col.type):
            table = table.set_column(i, table.schema.field(i).name, col.cast(pa.string()))
    df = table.to_pandas()
    print(f"    {len(df):,} rows x {len(df.columns)} cols loaded", flush=True)

    # Filter to train and val — never load test
    df_train = df[df[config.ID_COLUMN].isin(train_id_set)].reset_index(drop=True)
    df_val = df[df[config.ID_COLUMN].isin(val_id_set)].reset_index(drop=True)
    print(f"  Train rows: {len(df_train):,}  Val rows: {len(df_val):,}")

    X_train, y_train, _ = prep_features(df_train, config.NON_FEATURE_COLUMNS,
                                        config.EXCLUDE_PATTERNS, config.OUTCOME_COLUMN)
    print(f"  RFECV input: {len(X_train.columns)} features | positives: {y_train.sum():,} ({y_train.mean():.2%})")

    # Auto scale_pos_weight from train split
    spw = config.SCALE_POS_WEIGHT
    if spw is None:
        neg = (y_train == 0).sum()
        pos = (y_train == 1).sum()
        spw = float(neg) / float(pos) if pos > 0 else 1.0
        print(f"  Auto scale_pos_weight: {spw:.1f}")

    # Estimator — CPU forced to avoid GPU contention across parallel CV folds
    estimator = XGBClassifier(
        n_estimators=100,
        max_depth=config.MAX_DEPTH,
        learning_rate=config.LEARNING_RATE,
        subsample=config.SUBSAMPLE,
        colsample_bytree=config.COLSAMPLE_BYTREE,
        tree_method="hist",
        device="cpu",
        scale_pos_weight=spw,
        random_state=config.RANDOM_STATE,
        n_jobs=1,
        verbosity=0,
    )

    cv = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=config.RANDOM_STATE)

    n_features = len(X_train.columns)
    est_iters = int(1 / step) if isinstance(step, float) else (n_features // step)
    print(f"\n  Starting RFECV: {n_features} features, ~{est_iters} iterations ...")
    print(f"  (CPU, {args.cv_folds}-fold CV — expect 1–4 hours)")

    t0 = time.time()
    rfecv = RFECV(
        estimator=estimator,
        step=step,
        cv=cv,
        scoring="roc_auc",
        min_features_to_select=args.min_features,
        n_jobs=-1,
    )
    rfecv.fit(X_train.values, y_train.values)
    elapsed = time.time() - t0

    selected = [col for col, supported in zip(X_train.columns, rfecv.support_) if supported]
    best_cv_auc = rfecv.cv_results_["mean_test_score"].max()

    print(f"\n  Done in {elapsed/60:.1f} min")
    print(f"  Optimal features: {rfecv.n_features_} of {n_features}")
    print(f"  Best CV AUC (train): {best_cv_auc:.4f}")

    # Val sanity check
    X_val, y_val, _ = prep_features(df_val, config.NON_FEATURE_COLUMNS,
                                    config.EXCLUDE_PATTERNS, config.OUTCOME_COLUMN)
    available_val = [c for c in selected if c in X_val.columns]
    if available_val:
        from sklearn.metrics import roc_auc_score
        val_estimator = XGBClassifier(
            n_estimators=100,
            max_depth=config.MAX_DEPTH,
            learning_rate=config.LEARNING_RATE,
            subsample=config.SUBSAMPLE,
            colsample_bytree=config.COLSAMPLE_BYTREE,
            tree_method="hist",
            device="cpu",
            scale_pos_weight=spw,
            random_state=config.RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        )
        val_estimator.fit(X_train[available_val].values, y_train.values)
        val_preds = val_estimator.predict_proba(X_val[available_val].values)[:, 1]
        val_auc = roc_auc_score(y_val.values, val_preds)
        print(f"  Val AUC (sanity check): {val_auc:.4f}")

    # Save outputs
    out_dir = config.FEATURES_DIR / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    feat_out = out_dir / "selected_features_rfe.txt"
    with open(feat_out, "w") as f:
        f.write("\n".join(selected))
    print(f"  Feature list: {feat_out}")

    support_df = pd.DataFrame({
        "feature": X_train.columns,
        "selected": rfecv.support_,
        "ranking": rfecv.ranking_,
    }).sort_values("ranking")
    support_df.to_csv(out_dir / "rfe_support.csv", index=False)

    cv_df = pd.DataFrame({
        "mean_test_score": rfecv.cv_results_["mean_test_score"],
        "std_test_score": rfecv.cv_results_["std_test_score"],
    })
    if "n_features" in rfecv.cv_results_:
        cv_df.insert(0, "n_features", rfecv.cv_results_["n_features"])
    cv_df.to_csv(out_dir / "rfe_cv_scores.csv", index=False)
    print(f"  CV curve: {out_dir}/rfe_cv_scores.csv")

    feat_out_str = str(feat_out)
    print(f"\nNext: pipenv run python3 scripts/3b_tune_hyperparams.py "
          f"--tag {args.tag} --source-tag {args.source_tag} --feature-list {feat_out_str}")


if __name__ == "__main__":
    main()
