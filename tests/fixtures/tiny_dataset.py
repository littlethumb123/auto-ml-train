"""A tiny, deterministic binary-classification dataset used by tool and
integration tests. 500 rows, 5 features, ~10% positive class, seed=42."""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_tiny_binary(n: int = 500, seed: int = 42) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    x4 = rng.uniform(size=n)
    x5 = rng.integers(0, 5, size=n).astype(float)
    logit = 0.8 * x1 - 0.6 * x2 + 0.3 * x3
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.uniform(size=n) < prob * 0.25).astype(int)
    X = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5})
    return X, pd.Series(y, name="Class")
