from __future__ import annotations

import math

import numpy as np

from runner.tools import clustering_eval


def test_clustering_eval_returns_all_metrics():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    labels = np.repeat([0, 1, 2], 20)
    res = clustering_eval.clustering_eval(X, labels)
    assert set(res.keys()) >= {"silhouette", "davies_bouldin", "calinski_harabasz"}


def test_clustering_eval_single_cluster_returns_nan_silhouette():
    X = np.ones((20, 2))
    labels = np.zeros(20, dtype=int)
    res = clustering_eval.clustering_eval(X, labels)
    assert math.isnan(res["silhouette"])
