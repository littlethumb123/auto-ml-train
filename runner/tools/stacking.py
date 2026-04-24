"""Model stacking — train a meta-learner on base model predictions.

Implements holdout stacking: base models are trained on the full training
set (digits 0-7), predictions are generated on a meta-training holdout
(typically a subset of training digits held back for this purpose), the
meta-learner is fitted on those predictions, and final performance is
reported on the val set (digit 8).

Recommended split for stacking in the IP campaign:
  - Base model training:    digits 0–5  (downsampled)
  - Meta-learner training:  digits 6–7  (not downsampled — small, clean)
  - Evaluation:             digit  8    (standard val)
  - OOT check:              index_dt > 2025-06-30

Three meta-learner methods:
  'mean'     — unweighted average; no training needed; fast baseline
  'logistic' — LogisticRegression on stacked probability matrix
  'ridge'    — Ridge regression on stacked probabilities (clipped to [0,1])

Python API (used in train.py for A_ensemble rounds):
    from runner.tools.stacking import fit_stack, predict_stack

    # Train meta-learner on meta-train predictions
    result = fit_stack(
        base_preds_meta=[y_prob_model1_meta, y_prob_model2_meta],
        y_meta=y_meta,
        method='logistic',
    )
    meta_model = result['meta_model']

    # Generate val predictions
    val_preds = predict_stack(
        meta_model=meta_model,
        base_preds_eval=[y_prob_model1_val, y_prob_model2_val],
        method='logistic',
    )

CLI (Reviewer evaluation):
    python3 -m runner.tools.stacking \\
        --base-preds-json '[{"name":"cb_tab","y_prob":[...]},{"name":"cb_hyb","y_prob":[...]}]' \\
        --y-true-json '[0,1,0,...]' \\
        --method logistic \\
        --eval-preds-json '[{"name":"cb_tab","y_prob":[...]},...]' \\
        --y-eval-json '[0,1,...]' \\
        --json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from runner.tools._common import EXIT_OK, EXIT_USER_ERROR, emit_json


def _lift_at_pct(y_true: np.ndarray, y_prob: np.ndarray, pct: float) -> float:
    k = max(1, int(len(y_true) * pct))
    top_k = np.argsort(y_prob)[::-1][:k]
    base = y_true.mean()
    return float(y_true[top_k].mean() / base) if base > 0 else 0.0


def _eval_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    return {
        "lift_1pct": _lift_at_pct(y_true, y_prob, 0.01),
        "auc_roc":   float(roc_auc_score(y_true, y_prob)),
        "auc_pr":    float(average_precision_score(y_true, y_prob)),
        "lift_5pct": _lift_at_pct(y_true, y_prob, 0.05),
        "lift_10pct": _lift_at_pct(y_true, y_prob, 0.10),
    }


def fit_stack(
    base_preds_meta: list[np.ndarray],
    y_meta: np.ndarray,
    method: str = "logistic",
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit a meta-learner on base model predictions.

    Args:
        base_preds_meta: List of 1-D probability arrays from base models,
            evaluated on the meta-training holdout set.
        y_meta: True labels for the meta-training holdout set.
        method: 'mean' | 'logistic' | 'ridge'.
        random_state: Seed for logistic/ridge fitting.

    Returns:
        {
            'meta_model': fitted sklearn model (None for 'mean'),
            'method': str,
            'weights': {model_idx: weight, ...},  # from logistic coef_
            'meta_train_metrics': {lift_1pct, auc_roc, auc_pr, ...},
        }
    """
    y_meta = np.asarray(y_meta)
    preds_matrix = np.column_stack([np.asarray(p) for p in base_preds_meta])

    if method == "mean":
        y_stacked = preds_matrix.mean(axis=1)
        weights = {i: round(1.0 / len(base_preds_meta), 4) for i in range(len(base_preds_meta))}
        return {
            "meta_model": None,
            "method": method,
            "weights": weights,
            "meta_train_metrics": _eval_metrics(y_meta, y_stacked),
        }

    if method == "logistic":
        from sklearn.linear_model import LogisticRegression
        meta = LogisticRegression(C=1.0, max_iter=500, random_state=random_state)
        meta.fit(preds_matrix, y_meta)
        y_stacked = meta.predict_proba(preds_matrix)[:, 1]
        weights = {i: round(float(w), 6) for i, w in enumerate(meta.coef_[0])}
        return {
            "meta_model": meta,
            "method": method,
            "weights": weights,
            "meta_train_metrics": _eval_metrics(y_meta, y_stacked),
        }

    if method == "ridge":
        from sklearn.linear_model import Ridge
        meta = Ridge(alpha=1.0, random_state=random_state)
        meta.fit(preds_matrix, y_meta)
        y_stacked = np.clip(meta.predict(preds_matrix), 0.0, 1.0)
        weights = {i: round(float(w), 6) for i, w in enumerate(meta.coef_)}
        return {
            "meta_model": meta,
            "method": method,
            "weights": weights,
            "meta_train_metrics": _eval_metrics(y_meta, y_stacked),
        }

    raise ValueError(f"method must be 'mean'|'logistic'|'ridge', got {method!r}")


def predict_stack(
    meta_model: Any,
    base_preds_eval: list[np.ndarray],
    method: str = "logistic",
) -> np.ndarray:
    """Generate stacked predictions using a fitted meta-learner.

    Args:
        meta_model: Fitted sklearn model (from fit_stack); None for 'mean'.
        base_preds_eval: Base model prediction arrays for the evaluation set.
        method: Must match the method used in fit_stack.

    Returns:
        1-D array of stacked probabilities.
    """
    preds_matrix = np.column_stack([np.asarray(p) for p in base_preds_eval])
    if method == "mean" or meta_model is None:
        return preds_matrix.mean(axis=1)
    if method == "logistic":
        return meta_model.predict_proba(preds_matrix)[:, 1]
    if method == "ridge":
        return np.clip(meta_model.predict(preds_matrix), 0.0, 1.0)
    raise ValueError(f"Unknown method: {method!r}")


def stack_and_evaluate(
    base_preds_meta: list[np.ndarray],
    y_meta: np.ndarray,
    base_preds_eval: list[np.ndarray],
    y_eval: np.ndarray,
    method: str = "logistic",
    model_names: list[str] | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit meta-learner and evaluate on a held-out evaluation set.

    Convenience wrapper for A_ensemble rounds in train.py.

    Args:
        base_preds_meta: Base model probs on meta-train holdout (digits 6–7).
        y_meta: True labels for meta-train holdout.
        base_preds_eval: Base model probs on val/test set (digit 8 or 9).
        y_eval: True labels for val/test set.
        method: 'mean' | 'logistic' | 'ridge'.
        model_names: Optional names for each base model (for reporting).
        random_state: Seed.

    Returns dict with:
        meta_model, method, weights, meta_train_metrics,
        eval_metrics, y_prob_stacked, base_model_eval_metrics
    """
    fit_result = fit_stack(base_preds_meta, y_meta, method=method,
                           random_state=random_state)
    y_stacked = predict_stack(fit_result["meta_model"], base_preds_eval, method=method)
    eval_metrics = _eval_metrics(np.asarray(y_eval), y_stacked)

    names = model_names or [f"model_{i}" for i in range(len(base_preds_eval))]
    base_eval = {
        name: _eval_metrics(np.asarray(y_eval), np.asarray(p))
        for name, p in zip(names, base_preds_eval)
    }

    return {
        **fit_result,
        "eval_metrics": eval_metrics,
        "y_prob_stacked": y_stacked.tolist(),
        "base_model_eval_metrics": base_eval,
        "model_names": names,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stacking ensemble meta-learner.")
    p.add_argument(
        "--base-preds-json", required=True,
        help='JSON: [{"name":"m1","y_prob":[0.1,0.9,...]}, ...] for meta-learner training.',
    )
    p.add_argument("--y-true-json", required=True, help="JSON list of true labels (meta-train).")
    p.add_argument("--method", default="logistic", choices=["mean", "logistic", "ridge"])
    p.add_argument(
        "--eval-preds-json", default=None,
        help='JSON: same format, but on the evaluation (val/test) set.',
    )
    p.add_argument("--y-eval-json", default=None, help="JSON list of true labels (eval set).")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    try:
        meta_entries = json.loads(args.base_preds_json)
        y_meta = np.asarray(json.loads(args.y_true_json))
        base_preds_meta = [np.asarray(e["y_prob"]) for e in meta_entries]
        names = [e.get("name", f"model_{i}") for i, e in enumerate(meta_entries)]

        if args.eval_preds_json and args.y_eval_json:
            eval_entries = json.loads(args.eval_preds_json)
            y_eval = np.asarray(json.loads(args.y_eval_json))
            base_preds_eval = [np.asarray(e["y_prob"]) for e in eval_entries]
            result = stack_and_evaluate(
                base_preds_meta, y_meta,
                base_preds_eval, y_eval,
                method=args.method, model_names=names,
            )
            # Don't serialize the sklearn model object or the full stacked array
            output = {k: v for k, v in result.items()
                      if k not in ("meta_model", "y_prob_stacked")}
        else:
            fit_result = fit_stack(base_preds_meta, y_meta, method=args.method)
            output = {k: v for k, v in fit_result.items() if k != "meta_model"}

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    if args.json_output:
        emit_json(output)
    else:
        print(f"Method: {output['method']}")
        print(f"Weights: {output['weights']}")
        print(f"Meta-train metrics: {output['meta_train_metrics']}")
        if "eval_metrics" in output:
            print(f"Eval metrics:       {output['eval_metrics']}")
            print("\nBase model eval metrics:")
            for name, m in output.get("base_model_eval_metrics", {}).items():
                print(f"  {name}: lift@1%={m['lift_1pct']:.3f}  auc_roc={m['auc_roc']:.4f}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
