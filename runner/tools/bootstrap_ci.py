"""Bootstrap CI (spec §2.2.2)."""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    roc_auc_score,
)


def _lift_at_pct(pct: float):
    def fn(y, s):
        k = max(1, int(len(y) * pct))
        top_k = np.argsort(np.asarray(s))[::-1][:k]
        base = np.asarray(y).mean()
        return float(np.asarray(y)[top_k].mean() / base) if base > 0 else 0.0
    return fn


def _metric_fn(name: str):
    if name == "pr_auc":
        return lambda y, s: float(average_precision_score(y, s))
    if name == "roc_auc":
        return lambda y, s: float(roc_auc_score(y, s))
    if name == "f1":
        return lambda y, s: float(f1_score(y, (np.asarray(s) >= 0.5).astype(int), zero_division=0))
    if name == "lift_1pct":
        return _lift_at_pct(0.01)
    if name == "lift_5pct":
        return _lift_at_pct(0.05)
    if name == "lift_10pct":
        return _lift_at_pct(0.10)
    raise ValueError(f"unknown metric: {name!r}")


def bootstrap_ci(
    y_true,
    y_prob_or_pred,
    metric: str,
    n_boot: int = 1000,
    random_state: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    fn = _metric_fn(metric)
    y = np.asarray(y_true)
    s = np.asarray(y_prob_or_pred)
    if len(y) != len(s):
        raise ValueError("length mismatch y_true vs scores")
    rng = np.random.default_rng(random_state)
    point = fn(y, s)
    scores = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, len(y), size=len(y))
        try:
            scores[i] = fn(y[idx], s[idx])
        except (ValueError, ZeroDivisionError):
            scores[i] = np.nan
    scores = scores[~np.isnan(scores)]
    lo = float(np.quantile(scores, alpha / 2))
    hi = float(np.quantile(scores, 1 - alpha / 2))
    se = float(np.std(scores, ddof=1))
    return {
        "metric": point,
        "ci_lo": lo,
        "ci_hi": hi,
        "se": se,
        "n_boot": int(n_boot),
    }
