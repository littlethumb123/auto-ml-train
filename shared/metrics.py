"""ML evaluation metric functions — shared across auto_train campaigns.

Provides lift-at-percentile and a composite metric dict that matches the
ip-commercial-new-te EVAL_PROTOCOL results_columns schema.

Usage:
    from shared.metrics import compute_split_metrics
    metrics = compute_split_metrics(y_true, y_prob)
    # {'val_lift_1pct': 5.2, 'val_auc_roc': 0.83, ...}
"""
from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def lift_at_percentage(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    pct: float,
) -> float:
    """Lift = precision@top-k / baseline_prevalence."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    k = max(1, int(len(y_true) * pct))
    top_k = np.argsort(y_prob)[::-1][:k]
    precision_at_k = y_true[top_k].mean()
    baseline = y_true.mean()
    return float(precision_at_k / baseline) if baseline > 0 else 0.0


def precision_at_percentage(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    pct: float,
) -> float:
    """Precision (PPV) in top percentile of scored population."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    k = max(1, int(len(y_true) * pct))
    top_k = np.argsort(y_prob)[::-1][:k]
    return float(y_true[top_k].mean())


def true_positives_at_percentage(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    pct: float,
) -> int:
    """Count of true positives in the top-pct scored population."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    k = max(1, int(len(y_true) * pct))
    top_k = np.argsort(y_prob)[::-1][:k]
    return int(y_true[top_k].sum())


def compute_split_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    prefix: str = "val",
) -> Dict[str, float]:
    """Compute the full metric dict for one data split.

    Returns keys prefixed with `prefix` (default: 'val') so the same function
    works for val, test, and oot splits.

    Metrics:
        {prefix}_lift_1pct, {prefix}_auc_roc, {prefix}_lift_5pct,
        {prefix}_lift_10pct, {prefix}_auc_pr,
        {prefix}_precision_1pct, {prefix}_n_samples,
        {prefix}_n_positives, {prefix}_prevalence
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    return {
        f"{prefix}_lift_1pct":     lift_at_percentage(y_true, y_prob, 0.01),
        f"{prefix}_auc_roc":       float(roc_auc_score(y_true, y_prob)),
        f"{prefix}_lift_5pct":     lift_at_percentage(y_true, y_prob, 0.05),
        f"{prefix}_lift_10pct":    lift_at_percentage(y_true, y_prob, 0.10),
        f"{prefix}_auc_pr":        float(average_precision_score(y_true, y_prob)),
        f"{prefix}_precision_1pct": precision_at_percentage(y_true, y_prob, 0.01),
        f"{prefix}_n_samples":     int(len(y_true)),
        f"{prefix}_n_positives":   int(y_true.sum()),
        f"{prefix}_prevalence":    float(y_true.mean()),
    }
