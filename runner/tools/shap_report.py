"""SHAP feature importance report with embedding vs. tabular breakdown.

Computes mean |SHAP| per feature and reports what proportion of the
top-K most important features are embeddings vs. tabular — the primary
diagnostic for deciding whether to pursue A_feature or A_ensemble after
a hybrid model keeps.

Python API:
    from runner.tools.shap_report import shap_report
    result = shap_report(fitted_model, X_val, feature_cols, embedding_features)

CLI (for Reviewer / A_diagnose rounds):
    python3 -m runner.tools.shap_report \\
        --model-path experiment_helpers/exp5/champion.cbm \\
        --model-type catboost \\
        --data-parquet campaigns/ip-commercial-new-te/.cache/new_te.parquet \\
        --embedding-prefix embedding_ \\
        --target-col ip6 \\
        --top-k 10 20 50 \\
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

from runner.tools._common import EXIT_OK, EXIT_USER_ERROR, emit_json


def shap_report(
    model: Any,
    X_eval: pd.DataFrame,
    feature_cols: list[str],
    embedding_features: list[str] | set[str],
    top_k_list: list[int] | None = None,
    max_samples: int = 2000,
    random_state: int = 42,
    model_name: str = "",
) -> dict[str, Any]:
    """Compute SHAP feature importance and embedding-vs-tabular breakdown.

    Supports CatBoost, XGBoost, LightGBM (TreeExplainer), LogisticRegression
    (LinearExplainer), and any predict_proba model (KernelExplainer fallback).

    Args:
        model: Fitted classifier with predict_proba().
        X_eval: Feature matrix to explain (val or test split).
        feature_cols: Ordered list of feature column names used by the model.
        embedding_features: Collection of column names that are embeddings.
        top_k_list: Cutoffs for embedding-proportion breakdown (default [10, 20, 50]).
        max_samples: Cap on rows passed to SHAP (speed vs. accuracy trade-off).
        random_state: Seed for sample selection and KernelExplainer background.
        model_name: Label for the model in the output dict.

    Returns dict with keys:
        model_name, shap_summary (list of {feature, mean_abs_shap, is_embedding, rank}),
        proportion_by_k (list of {top_k, n_embedding, prop_embedding, n_tabular, prop_tabular}),
        n_features, n_embedding_features, n_tabular_features, n_samples_used
    """
    import shap  # deferred — not all campaigns require shap

    if top_k_list is None:
        top_k_list = [10, 20, 50]

    X_eval = X_eval[feature_cols] if list(X_eval.columns) != feature_cols else X_eval
    X_sample = (
        X_eval.sample(n=max_samples, random_state=random_state)
        if len(X_eval) > max_samples
        else X_eval
    )

    model_type = type(model).__name__
    if model_type in ("CatBoostClassifier", "XGBClassifier", "LGBMClassifier"):
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
    elif model_type == "LogisticRegression":
        background = shap.sample(X_sample, min(100, len(X_sample)))
        explainer = shap.LinearExplainer(model, background)
        shap_values = explainer.shap_values(X_sample)
    else:
        background = shap.sample(X_sample, min(100, len(X_sample)))
        explainer = shap.KernelExplainer(model.predict_proba, background)
        shap_values = explainer.shap_values(X_sample)

    # Some model/version combos return [neg_class, pos_class]
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    mean_abs = np.abs(shap_values).mean(axis=0)
    emb_set = set(embedding_features)

    summary_df = (
        pd.DataFrame({
            "feature": feature_cols,
            "mean_abs_shap": mean_abs,
            "is_embedding": [f in emb_set for f in feature_cols],
        })
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    summary_df["rank"] = range(1, len(summary_df) + 1)

    proportion_by_k = []
    for k in top_k_list:
        k_actual = min(k, len(summary_df))
        top_k_df = summary_df.head(k_actual)
        n_emb = int(top_k_df["is_embedding"].sum())
        n_tab = k_actual - n_emb
        proportion_by_k.append({
            "top_k": k_actual,
            "n_embedding": n_emb,
            "prop_embedding": round(n_emb / k_actual, 4) if k_actual else 0.0,
            "n_tabular": n_tab,
            "prop_tabular": round(n_tab / k_actual, 4) if k_actual else 0.0,
        })

    return {
        "model_name": model_name or model_type,
        "shap_summary": summary_df[
            ["feature", "mean_abs_shap", "is_embedding", "rank"]
        ].to_dict(orient="records"),
        "proportion_by_k": proportion_by_k,
        "n_features": len(feature_cols),
        "n_embedding_features": len(emb_set & set(feature_cols)),
        "n_tabular_features": len(set(feature_cols) - emb_set),
        "n_samples_used": len(X_sample),
    }


def _load_model(model_path: str, model_type: str) -> Any:
    if model_type == "catboost":
        from catboost import CatBoostClassifier
        m = CatBoostClassifier()
        m.load_model(model_path)
        return m
    if model_type == "xgboost":
        import xgboost as xgb
        m = xgb.XGBClassifier()
        m.load_model(model_path)
        return m
    if model_type == "lightgbm":
        import lightgbm as lgb
        return lgb.Booster(model_file=model_path)
    if model_type == "pickle":
        import pickle
        with open(model_path, "rb") as fh:
            return pickle.load(fh)
    raise ValueError(f"Unknown model_type: {model_type!r}")


def _infer_feature_cols(
    df: pd.DataFrame,
    target_col: str,
    embedding_prefix: str,
    feature_set: str,
    extra_exclude: list[str],
) -> tuple[list[str], list[str]]:
    excluded = set(extra_exclude) | {target_col}
    all_cols = set(df.columns)
    emb = sorted(c for c in all_cols if c.startswith(embedding_prefix))
    tab = sorted(c for c in all_cols if c not in excluded and c not in emb)
    if feature_set == "embedding_only":
        return emb, emb
    if feature_set == "tabular_only":
        return tab, emb
    return tab + emb, emb  # hybrid


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SHAP feature importance report.")
    p.add_argument("--model-path", required=True)
    p.add_argument("--model-type", required=True,
                   choices=["catboost", "xgboost", "lightgbm", "pickle"])
    p.add_argument("--data-parquet", required=True)
    p.add_argument("--feature-set", default="hybrid",
                   choices=["tabular_only", "embedding_only", "hybrid"])
    p.add_argument("--embedding-prefix", default="embedding_")
    p.add_argument("--target-col", default="ip6")
    p.add_argument("--exclude-cols", default="[]",
                   help="JSON list of extra columns to exclude from features.")
    p.add_argument("--top-k", nargs="+", type=int, default=[10, 20, 50])
    p.add_argument("--max-samples", type=int, default=2000)
    p.add_argument("--output-path", default=None)
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    try:
        model = _load_model(args.model_path, args.model_type)
        df = pd.read_parquet(args.data_parquet)
        extra_exclude = json.loads(args.exclude_cols)
        feature_cols, embedding_features = _infer_feature_cols(
            df, args.target_col, args.embedding_prefix,
            args.feature_set, extra_exclude,
        )
        X_eval = df[feature_cols].fillna(0)
        result = shap_report(
            model=model,
            X_eval=X_eval,
            feature_cols=feature_cols,
            embedding_features=embedding_features,
            top_k_list=args.top_k,
            max_samples=args.max_samples,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    if args.output_path:
        Path(args.output_path).write_text(json.dumps(result, indent=2))

    if args.json_output:
        emit_json(result)
    else:
        print(f"Model: {result['model_name']}  |  "
              f"{result['n_embedding_features']} emb + {result['n_tabular_features']} tab features  |  "
              f"n_samples={result['n_samples_used']}")
        print("\nEmbedding proportion in top-K:")
        for row in result["proportion_by_k"]:
            print(f"  top-{row['top_k']:3d}: "
                  f"{row['n_embedding']:3d} emb ({row['prop_embedding']:.1%})  "
                  f"{row['n_tabular']:3d} tab ({row['prop_tabular']:.1%})")
        print("\nTop 20 by mean |SHAP|:")
        for r in result["shap_summary"][:20]:
            tag = "[emb]" if r["is_embedding"] else "[tab]"
            print(f"  {r['rank']:3d}. {tag} {r['feature']:<40s}  {r['mean_abs_shap']:.6f}")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
