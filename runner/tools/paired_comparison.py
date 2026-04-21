"""Paired comparison (spec §2.2.2)."""
from __future__ import annotations

import numpy as np
from scipy import stats


def paired_comparison(
    a_scores,
    b_scores,
    test: str = "wilcoxon",
) -> dict:
    a = np.asarray(a_scores, dtype=float)
    b = np.asarray(b_scores, dtype=float)
    if a.shape != b.shape:
        raise ValueError("a_scores and b_scores must have same shape")
    diff = a - b
    if np.allclose(diff, 0):
        return {"p_value": 1.0, "effect_size": 0.0, "direction": "tie"}

    if test == "wilcoxon":
        try:
            stat, p = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
            p = float(p)
        except ValueError:
            p = 1.0
    elif test == "t":
        _, p = stats.ttest_rel(a, b)
        p = float(p)
    else:
        raise ValueError(f"unknown test: {test!r}")

    effect_size = float(np.mean(a) - np.mean(b))
    if effect_size > 0:
        direction = "a>b"
    elif effect_size < 0:
        direction = "b>a"
    else:
        direction = "tie"
    return {"p_value": p, "effect_size": effect_size, "direction": direction}
