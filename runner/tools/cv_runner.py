"""CV runner (spec §2.2.2)."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, mean_squared_error, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold

_METRICS = {
    "pr_auc": ("proba", lambda y, s: float(average_precision_score(y, s))),
    "roc_auc": ("proba", lambda y, s: float(roc_auc_score(y, s))),
    "rmse": ("pred", lambda y, p: float(np.sqrt(mean_squared_error(y, p)))),
}


def cv_runner(
    estimator_factory: Callable[[], Any],
    X: pd.DataFrame,
    y: pd.Series,
    scheme: str,
    n_splits: int,
    primary_metric: str,
    random_state: int,
    groups: pd.Series | None = None,
) -> dict[str, Any]:
    if primary_metric not in _METRICS:
        raise ValueError(f"unknown primary_metric: {primary_metric!r}")
    target_type, metric_fn = _METRICS[primary_metric]

    if scheme == "stratified_kfold":
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_args = (X, y)
    elif scheme == "kfold":
        splitter = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_args = (X, y)
    elif scheme == "group_kfold":
        if groups is None:
            raise ValueError("group_kfold requires groups")
        splitter = GroupKFold(n_splits=n_splits)
        split_args = (X, y, groups)
    else:
        raise ValueError(f"unknown scheme: {scheme!r}")

    scores: list[float] = []
    for split in splitter.split(*split_args):
        tr, va = split[0], split[1]
        model = estimator_factory()
        model.fit(X.iloc[tr], y.iloc[tr])
        if target_type == "proba":
            score = model.predict_proba(X.iloc[va])[:, 1]
        else:
            score = model.predict(X.iloc[va])
        scores.append(metric_fn(y.iloc[va], score))
    mean = float(np.mean(scores))
    std = float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
    if len(scores) > 1:
        tcrit = stats.t.ppf(0.975, len(scores) - 1)
        half = tcrit * std / (len(scores) ** 0.5)
    else:
        half = 0.0
    return {
        "fold_scores": scores,
        "mean": mean,
        "std": std,
        "ci95": [mean - half, mean + half],
    }
