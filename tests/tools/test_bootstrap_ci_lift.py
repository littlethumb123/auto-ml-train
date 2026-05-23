"""Verify bootstrap_ci's lift matches shared.metrics exactly."""
from __future__ import annotations

import numpy as np
import pytest

from runner.tools.bootstrap_ci import bootstrap_ci
from shared.metrics import lift_at_percentage


def test_bootstrap_lift10_matches_shared_metrics():
    """Point estimate from bootstrap_ci must equal shared.metrics.lift_at_percentage."""
    rng = np.random.default_rng(99)
    y_true = rng.integers(0, 2, size=500).astype(float)
    y_prob = rng.random(500)

    # bootstrap_ci point estimate
    result = bootstrap_ci(y_true, y_prob, metric="lift_10pct", n_boot=10)
    bc_point = result["metric"]

    # shared.metrics direct call
    sm_point = lift_at_percentage(y_true, y_prob, 0.10)

    assert bc_point == pytest.approx(sm_point, abs=1e-12), (
        f"bootstrap_ci lift={bc_point} != shared.metrics lift={sm_point}"
    )
