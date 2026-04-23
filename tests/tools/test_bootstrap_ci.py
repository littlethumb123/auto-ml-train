from __future__ import annotations

import numpy as np
import pytest

from runner.tools import bootstrap_ci


def test_bootstrap_ci_pr_auc_contained_in_zero_one():
    rng = np.random.default_rng(0)
    n = 200
    y_true = (rng.uniform(size=n) < 0.1).astype(int)
    y_prob = rng.uniform(size=n)
    res = bootstrap_ci.bootstrap_ci(y_true, y_prob, metric="pr_auc", n_boot=200, random_state=0)
    assert 0.0 <= res["ci_lo"] <= res["metric"] <= res["ci_hi"] <= 1.0
    assert res["n_boot"] == 200


def test_bootstrap_ci_determinism():
    rng = np.random.default_rng(0)
    y = (rng.uniform(size=100) < 0.2).astype(int)
    p = rng.uniform(size=100)
    r1 = bootstrap_ci.bootstrap_ci(y, p, metric="pr_auc", n_boot=100, random_state=7)
    r2 = bootstrap_ci.bootstrap_ci(y, p, metric="pr_auc", n_boot=100, random_state=7)
    assert r1 == r2


def test_bootstrap_ci_unknown_metric_raises():
    with pytest.raises(ValueError):
        bootstrap_ci.bootstrap_ci([0, 1], [0.1, 0.9], metric="fake", n_boot=10)
