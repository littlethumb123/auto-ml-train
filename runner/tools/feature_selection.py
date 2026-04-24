"""Feature selection before hyperparameter tuning.

Ranks features by importance and returns the top-K subset, reducing the
feature space before Optuna HP search (fewer features = faster training =
more trials within the time budget).

Two methods:
  'permutation' — shuffle each feature column; measure AUC-ROC drop.
                  Requires a fitted model (or fits a fast default CatBoost).
  'variance'    — drop near-zero variance features; no model needed.
                  Use as a fast pre-filter before permutation.

Typical A_feature workflow in train.py:
    from runner.tools.feature_selection import select_features
    selected = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols,
        embedding_features=emb_features,
        method='permutation',
        top_k=80,
        model=champion_model,   # provide fitted model, or None to fit a fast default
    )
    # Save and use in next A_hp round:
    X_train_sel = X_train[selected['selected_features']]
    X_val_sel   = X_val[selected['selected_features']]

CLI (Planner / Reviewer inspection):
    python3 -m runner.tools.feature_selection \\
        --data-parquet campaigns/ip-commercial-new-te/.cache/new_te.parquet \\
        --feature-set hybrid \\
        --method permutation \\
        --top-k 80 \\
        --output-json runner/state/selected_features.json \\
        --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from runner.tools._common import EXIT_OK, EXIT_USER_ERROR, emit_json


def select_features(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    feature_cols: list[str],
    embedding_features: list[str] | set[str] | None = None,
    method: str = "permutation",
    top_k: int | None = None,
    variance_threshold: float = 1e-6,
    model: Any = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Select the most important features before HP tuning.

    Args:
        X_train, y_train: Training data (model fitting or variance computation).
        X_val, y_val: Validation data (permutation importance evaluation).
        feature_cols: Candidate feature columns (must exist in X_train/X_val).
        embedding_features: Which columns are embeddings (for breakdown reporting).
        method: 'permutation' | 'variance'.
        top_k: Keep this many top features. None = keep all above threshold.
        variance_threshold: Drop columns with variance below this (variance pre-filter).
        model: Pre-fitted model for permutation importance. Fits a fast default
               CatBoost if None (100 iterations, depth 5).
        random_state: Seed for default model and permutation shuffling.

    Returns:
        {
            'selected_features': [...],   # ordered by importance, descending
            'dropped_features': [...],
            'importances': {feature: score, ...},
            'method': str,
            'n_selected': int,
            'n_dropped': int,
            'n_embedding_selected': int,
            'n_tabular_selected': int,
        }
    """
    X_tr = X_train[feature_cols].copy()
    X_vl = X_val[feature_cols].copy()
    emb_set = set(embedding_features or [])

    # --- Variance pre-filter (always applied first) ---
    variances = X_tr.var(numeric_only=True)
    low_var = set(variances[variances <= variance_threshold].index.tolist())
    candidate_cols = [c for c in feature_cols if c not in low_var]

    importances: dict[str, float] = {c: 0.0 for c in feature_cols}
    for c in low_var:
        importances[c] = 0.0  # explicitly zero for dropped low-variance features

    if method == "variance":
        # Sort by variance as the importance proxy
        for c in candidate_cols:
            importances[c] = float(variances.get(c, 0.0))
    elif method == "permutation":
        # Fit a fast default model if none provided
        if model is None:
            from catboost import CatBoostClassifier, Pool
            fast_model = CatBoostClassifier(
                iterations=100,
                depth=5,
                learning_rate=0.1,
                auto_class_weights="Balanced",
                random_seed=random_state,
                verbose=0,
            )
            fast_model.fit(
                X_tr[candidate_cols], y_train,
                eval_set=Pool(X_vl[candidate_cols], y_val),
            )
        else:
            fast_model = model

        # Baseline AUC on val
        y_prob_base = fast_model.predict_proba(X_vl[candidate_cols])[:, 1]
        baseline_auc = float(roc_auc_score(y_val, y_prob_base))

        rng = np.random.default_rng(random_state)
        for col in candidate_cols:
            X_perm = X_vl[candidate_cols].copy()
            X_perm[col] = rng.permutation(X_perm[col].values)
            y_prob_perm = fast_model.predict_proba(X_perm)[:, 1]
            perm_auc = float(roc_auc_score(y_val, y_prob_perm))
            importances[col] = max(0.0, baseline_auc - perm_auc)  # AUC drop = importance
    else:
        raise ValueError(f"method must be 'permutation' or 'variance', got {method!r}")

    # Sort candidate_cols by importance descending
    ranked = sorted(candidate_cols, key=lambda c: importances[c], reverse=True)

    if top_k is not None:
        selected = ranked[:top_k]
    else:
        selected = ranked  # keep all non-zero-variance features

    dropped = [c for c in feature_cols if c not in set(selected)]
    n_emb_sel = sum(1 for c in selected if c in emb_set)
    n_tab_sel = len(selected) - n_emb_sel

    return {
        "selected_features": selected,
        "dropped_features": dropped,
        "importances": {c: round(importances[c], 8) for c in feature_cols},
        "method": method,
        "n_selected": len(selected),
        "n_dropped": len(dropped),
        "n_embedding_selected": n_emb_sel,
        "n_tabular_selected": n_tab_sel,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Feature selection before HP tuning.")
    p.add_argument("--data-parquet", required=True)
    p.add_argument("--feature-set", default="hybrid",
                   choices=["tabular_only", "embedding_only", "hybrid"])
    p.add_argument("--embedding-prefix", default="embedding_")
    p.add_argument("--target-col", default="ip6")
    p.add_argument("--oot-cutoff", default="2025-06-30",
                   help="In-time upper bound date (YYYY-MM-DD).")
    p.add_argument("--method", default="permutation",
                   choices=["permutation", "variance"])
    p.add_argument("--top-k", type=int, default=None)
    p.add_argument("--variance-threshold", type=float, default=1e-6)
    p.add_argument("--model-path", default=None)
    p.add_argument("--model-type", default="catboost",
                   choices=["catboost", "xgboost", "lightgbm", "pickle"])
    p.add_argument("--output-json", default=None,
                   help="Write selected_features list to this JSON file.")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    try:
        df = pd.read_parquet(args.data_parquet)
        df["_index_dt"] = pd.to_datetime(df["index_dt"])
        oot_cutoff = pd.to_datetime(args.oot_cutoff)
        in_time = df[df["_index_dt"] <= oot_cutoff]

        all_cols = set(in_time.columns)
        emb = sorted(c for c in all_cols if c.startswith(args.embedding_prefix))
        tab = sorted(c for c in all_cols
                     if not c.startswith(args.embedding_prefix)
                     and c != args.target_col
                     and not c.startswith("_"))
        if args.feature_set == "embedding_only":
            feature_cols = emb
        elif args.feature_set == "tabular_only":
            feature_cols = tab
        else:
            feature_cols = tab + emb

        train_mask = in_time["ind_id_last_digit"].isin([0, 1, 2, 3, 4, 5, 6, 7])
        val_mask = in_time["ind_id_last_digit"] == 8
        X_train = in_time.loc[train_mask, feature_cols].fillna(0)
        y_train = in_time.loc[train_mask, args.target_col].astype(int)
        X_val   = in_time.loc[val_mask, feature_cols].fillna(0)
        y_val   = in_time.loc[val_mask, args.target_col].astype(int)

        model = None
        if args.model_path:
            from runner.tools.shap_report import _load_model
            model = _load_model(args.model_path, args.model_type)

        result = select_features(
            X_train, y_train, X_val, y_val,
            feature_cols=feature_cols,
            embedding_features=emb,
            method=args.method,
            top_k=args.top_k,
            variance_threshold=args.variance_threshold,
            model=model,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(result["selected_features"], indent=2)
        )

    if args.json_output:
        emit_json(result)
    else:
        print(f"Method: {result['method']}  |  "
              f"selected {result['n_selected']} / {result['n_selected'] + result['n_dropped']}  "
              f"({result['n_embedding_selected']} emb, {result['n_tabular_selected']} tab)")
        top_show = sorted(
            result["importances"].items(), key=lambda x: x[1], reverse=True
        )[:20]
        print("\nTop 20 by importance:")
        for i, (feat, score) in enumerate(top_show, 1):
            print(f"  {i:3d}. {feat:<45s}  {score:.6f}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
