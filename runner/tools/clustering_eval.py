"""Clustering evaluator (spec §2.2.5). Used only when task_type == 'clustering'."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)


def clustering_eval(
    X,
    labels,
    metrics: tuple = ("silhouette", "davies_bouldin", "calinski_harabasz"),
    random_state: int = 42,
) -> dict[str, Any]:
    X_arr = np.asarray(X)
    lbl = np.asarray(labels)
    out: dict[str, float] = {}
    n_clusters = len(np.unique(lbl))
    for m in metrics:
        try:
            if m == "silhouette":
                if n_clusters < 2 or n_clusters >= len(lbl):
                    out[m] = math.nan
                else:
                    out[m] = float(silhouette_score(X_arr, lbl, random_state=random_state))
            elif m == "davies_bouldin":
                if n_clusters < 2:
                    out[m] = math.nan
                else:
                    out[m] = float(davies_bouldin_score(X_arr, lbl))
            elif m == "calinski_harabasz":
                if n_clusters < 2:
                    out[m] = math.nan
                else:
                    out[m] = float(calinski_harabasz_score(X_arr, lbl))
            else:
                raise ValueError(f"unknown clustering metric: {m!r}")
        except ValueError:
            out[m] = math.nan
    return out
