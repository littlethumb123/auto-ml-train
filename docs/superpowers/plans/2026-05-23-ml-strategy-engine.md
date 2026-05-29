# ML Strategy Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five capabilities to the auto_train harness: (1) validated code template library, (2) systematic error analysis protocol, (3) tree-search over solutions with UCB1 exploration/exploitation, (4) group aggregation feature templates, (5) temporal split validation.

**Architecture:** The implementation adds three new modules (`runner/strategy/`), extends the state machine in `runner_driver.py` with tree-tracking fields, updates two role prompts (`planner.md`, `reviewer.md`), and adds one new tool (`runner/tools/error_analysis.py`). The template library lives at `runner/strategy/templates.py` with pure functions that the Executor can copy-paste into `train.py`. The tree search state is a JSON file (`state/EXPERIMENT_TREE.json`) managed by `runner/strategy/tree_search.py`, with UCB1 scores computed and injected into the Planner's context.

**Tech Stack:** Python 3.10+, numpy, pandas, scikit-learn (already in requirements.txt). No new dependencies.

---

## Scope Decomposition

This plan covers five independent subsystems that integrate at the Planner/Reviewer role prompt level:

| Subsystem | Files | Integrates With |
|---|---|---|
| **S1: Template Library** | `runner/strategy/__init__.py`, `runner/strategy/templates.py`, `tests/strategy/test_templates.py` | Executor reads templates; Planner references catalog |
| **S2: Error Analysis** | `runner/tools/error_analysis.py`, `tests/tools/test_error_analysis.py` | Reviewer runs after each experiment; feeds into Planner |
| **S3: Tree Search + UCB1** | `runner/strategy/tree_search.py`, `tests/strategy/test_tree_search.py` | `runner_driver.py` manages tree state; Planner reads UCB1 scores |
| **S4: Group Aggregation Templates** | Part of `runner/strategy/templates.py` | Executor uses; Planner recommends |
| **S5: Temporal Split Validation** | `runner/tools/temporal_cv.py`, `tests/tools/test_temporal_cv.py` | Reviewer runs; Planner considers |

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `runner/strategy/__init__.py` | Package init (empty) |
| `runner/strategy/templates.py` | Validated, copy-pasteable code templates for common ML techniques |
| `runner/strategy/tree_search.py` | Tree state management + UCB1 scoring |
| `runner/tools/error_analysis.py` | Systematic error analysis: bucketized failure patterns |
| `runner/tools/temporal_cv.py` | Temporal (time-based) cross-validation splits |
| `tests/strategy/__init__.py` | Package init (empty) |
| `tests/strategy/test_templates.py` | Tests for template library |
| `tests/strategy/test_tree_search.py` | Tests for tree search + UCB1 |
| `tests/tools/test_error_analysis.py` | Tests for error analysis |
| `tests/tools/test_temporal_cv.py` | Tests for temporal CV |

### Modified Files

| File | Change |
|---|---|
| `runner/runner_driver.py` | `init_campaign()` creates `EXPERIMENT_TREE.json`; `review_finalize()` updates tree node + computes UCB1 scores |
| `runner/roles/planner.md` | Add §11: read UCB1 scores + template catalog |
| `runner/roles/reviewer.md` | Add error analysis to Phase 1 mandatory tool list |
| `runner/contracts/EVAL_PROTOCOL.md` | Add `temporal_cv` to optional tools; add `A_error_analysis` action type |

---

## Task 1: Template Library — Core Infrastructure

**Files:**
- Create: `runner/strategy/__init__.py`
- Create: `runner/strategy/templates.py`
- Create: `tests/strategy/__init__.py`
- Create: `tests/strategy/test_templates.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p runner/strategy tests/strategy
touch runner/strategy/__init__.py tests/strategy/__init__.py
```

- [ ] **Step 2: Write failing tests for template functions**

Create `tests/strategy/test_templates.py`:

```python
"""Tests for runner.strategy.templates — validated ML code templates."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from runner.strategy import templates


# --- Target encoding ---

class TestTargetEncode:
    def test_basic_smoothed_encoding(self):
        train = pd.DataFrame({"cat": ["a", "a", "b", "b", "c"], "y": [1, 0, 1, 1, 0]})
        val = pd.DataFrame({"cat": ["a", "b", "c", "d"]})
        result_train, result_val = templates.target_encode(
            train, val, columns=["cat"], target="y", min_samples=1, smoothing=1.0,
        )
        assert "cat_te" in result_train.columns
        assert "cat_te" in result_val.columns
        # 'd' is unseen — should get global mean
        global_mean = train["y"].mean()
        assert result_val.loc[result_val.index[3], "cat_te"] == pytest.approx(global_mean, abs=1e-6)

    def test_does_not_leak_target(self):
        """Target encoding must use only training data, not validation."""
        train = pd.DataFrame({"cat": ["a"] * 100, "y": [1] * 50 + [0] * 50})
        val = pd.DataFrame({"cat": ["a"] * 10})
        _, result_val = templates.target_encode(
            train, val, columns=["cat"], target="y", min_samples=1, smoothing=1.0,
        )
        # All 'a' in val should get the same value (from train stats only)
        assert result_val["cat_te"].nunique() == 1


class TestFrequencyEncode:
    def test_basic(self):
        train = pd.DataFrame({"cat": ["a", "a", "b", "c"]})
        val = pd.DataFrame({"cat": ["a", "b", "d"]})
        result_train, result_val = templates.frequency_encode(train, val, columns=["cat"])
        assert result_train.loc[0, "cat_freq"] == pytest.approx(0.5)
        assert result_train.loc[2, "cat_freq"] == pytest.approx(0.25)
        # 'd' unseen — should get 0
        assert result_val.loc[2, "cat_freq"] == pytest.approx(0.0)


# --- Group aggregation ---

class TestGroupAggFeatures:
    def test_creates_expected_columns(self):
        df = pd.DataFrame({
            "group": ["a", "a", "b", "b"],
            "val1": [10, 20, 30, 40],
            "val2": [1.0, 2.0, 3.0, 4.0],
        })
        result = templates.group_agg_features(
            df, group_col="group", agg_cols=["val1", "val2"], agg_funcs=["mean", "std"],
        )
        assert "val1_by_group_mean" in result.columns
        assert "val2_by_group_std" in result.columns
        # group 'a' mean of val1 = 15
        assert result.loc[0, "val1_by_group_mean"] == pytest.approx(15.0)

    def test_handles_unseen_groups_with_nan(self):
        train = pd.DataFrame({"group": ["a", "a"], "val": [10, 20]})
        val = pd.DataFrame({"group": ["a", "b"], "val": [15, 25]})
        agg_map = templates.fit_group_agg(train, group_col="group", agg_cols=["val"], agg_funcs=["mean"])
        result = templates.transform_group_agg(val, agg_map, group_col="group")
        assert "val_by_group_mean" in result.columns
        assert result.loc[0, "val_by_group_mean"] == pytest.approx(15.0)
        assert np.isnan(result.loc[1, "val_by_group_mean"])


# --- Outlier handling ---

class TestClipOutliers:
    def test_clips_at_percentiles(self):
        arr = np.array([1, 2, 3, 4, 5, 100])
        result = templates.clip_outliers(arr, lower_pct=0.05, upper_pct=0.95)
        assert result.max() < 100
        assert result.min() >= 1

    def test_no_change_when_no_outliers(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = templates.clip_outliers(arr, lower_pct=0.0, upper_pct=1.0)
        np.testing.assert_array_equal(arr, result)


# --- Missing value indicators ---

class TestMissingIndicators:
    def test_creates_indicator_columns(self):
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [np.nan, 2.0, 3.0]})
        result = templates.add_missing_indicators(df, columns=["a", "b"])
        assert "a_missing" in result.columns
        assert "b_missing" in result.columns
        assert result["a_missing"].tolist() == [0, 1, 0]
        assert result["b_missing"].tolist() == [1, 0, 0]


# --- Temporal split ---

class TestTemporalSplit:
    def test_basic_split(self):
        df = pd.DataFrame({
            "time": pd.date_range("2020-01-01", periods=100, freq="D"),
            "y": np.random.randint(0, 2, 100),
        })
        train, val = templates.temporal_split(
            df, time_col="time", train_end="2020-03-01", val_end="2020-04-10",
        )
        assert len(train) > 0
        assert len(val) > 0
        assert train["time"].max() < val["time"].min()


# --- Seed averaging ---

class TestSeedAverage:
    def test_averages_predictions(self):
        preds = [np.array([0.1, 0.2, 0.3]), np.array([0.3, 0.4, 0.5])]
        result = templates.seed_average(preds)
        np.testing.assert_array_almost_equal(result, [0.2, 0.3, 0.4])

    def test_single_seed(self):
        preds = [np.array([0.5, 0.6])]
        result = templates.seed_average(preds)
        np.testing.assert_array_almost_equal(result, [0.5, 0.6])


# --- Template catalog ---

class TestCatalog:
    def test_catalog_returns_list_of_dicts(self):
        catalog = templates.get_catalog()
        assert isinstance(catalog, list)
        assert len(catalog) > 0
        for entry in catalog:
            assert "name" in entry
            assert "category" in entry
            assert "description" in entry
            assert "usage" in entry

    def test_catalog_categories(self):
        catalog = templates.get_catalog()
        categories = {e["category"] for e in catalog}
        assert "encoding" in categories
        assert "aggregation" in categories
        assert "validation" in categories
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/strategy/test_templates.py -v 2>&1 | head -40
```

Expected: All tests FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 4: Implement templates.py**

Create `runner/strategy/templates.py`:

```python
"""Validated ML code templates — copy-pasteable building blocks.

Each function is a self-contained, tested transformation that the Executor
can adapt into train.py.  Functions operate on numpy arrays and pandas
DataFrames; they never touch disk or global state.

Usage by Executor:
    from runner.strategy.templates import target_encode, group_agg_features
    # Then adapt the call into train.py's feature engineering section.

Usage by Planner:
    catalog = templates.get_catalog()
    # Returns list of {"name", "category", "description", "usage"} dicts.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Encoding templates
# ---------------------------------------------------------------------------

def target_encode(
    train: pd.DataFrame,
    val: pd.DataFrame,
    columns: list[str],
    target: str,
    min_samples: int = 10,
    smoothing: float = 5.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Smoothed target encoding fit on train, applied to train+val.

    Smoothing formula:
        weight = count / (count + smoothing)
        encoded = weight * category_mean + (1 - weight) * global_mean

    Unseen categories in val get the global mean.

    Args:
        train: Training DataFrame (must contain target column).
        val: Validation DataFrame (same columns minus target).
        columns: Categorical columns to encode.
        target: Name of the binary target column.
        min_samples: Minimum samples for a category to use its own mean.
        smoothing: Smoothing factor (higher = more regularization).

    Returns:
        (train_encoded, val_encoded) with new columns named '{col}_te'.
    """
    train_out = train.copy()
    val_out = val.copy()
    global_mean = train[target].mean()

    for col in columns:
        stats = train.groupby(col)[target].agg(["mean", "count"])
        # Apply smoothing
        weight = stats["count"] / (stats["count"] + smoothing)
        smoothed = weight * stats["mean"] + (1 - weight) * global_mean
        # Mask categories with too few samples
        smoothed[stats["count"] < min_samples] = global_mean
        mapping = smoothed.to_dict()

        new_col = f"{col}_te"
        train_out[new_col] = train[col].map(mapping).fillna(global_mean)
        val_out[new_col] = val[col].map(mapping).fillna(global_mean)

    return train_out, val_out


def frequency_encode(
    train: pd.DataFrame,
    val: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Frequency encoding: replace category with its proportion in training data.

    Unseen categories in val get 0.

    Args:
        train: Training DataFrame.
        val: Validation DataFrame.
        columns: Columns to encode.

    Returns:
        (train_encoded, val_encoded) with new columns named '{col}_freq'.
    """
    train_out = train.copy()
    val_out = val.copy()

    for col in columns:
        freq = train[col].value_counts(normalize=True)
        mapping = freq.to_dict()
        new_col = f"{col}_freq"
        train_out[new_col] = train[col].map(mapping).fillna(0.0)
        val_out[new_col] = val[col].map(mapping).fillna(0.0)

    return train_out, val_out


# ---------------------------------------------------------------------------
# Group aggregation templates
# ---------------------------------------------------------------------------

def group_agg_features(
    df: pd.DataFrame,
    group_col: str,
    agg_cols: list[str],
    agg_funcs: list[str] | None = None,
) -> pd.DataFrame:
    """Add group-level aggregation features (in-place, single DataFrame).

    For train/val split scenarios, use fit_group_agg + transform_group_agg instead.

    Args:
        df: Input DataFrame.
        group_col: Column to group by.
        agg_cols: Numeric columns to aggregate.
        agg_funcs: Aggregation functions (default: ["mean", "std"]).

    Returns:
        DataFrame with new columns named '{agg_col}_by_{group_col}_{func}'.
    """
    if agg_funcs is None:
        agg_funcs = ["mean", "std"]

    result = df.copy()
    for col in agg_cols:
        for func in agg_funcs:
            new_col = f"{col}_by_{group_col}_{func}"
            result[new_col] = result.groupby(group_col)[col].transform(func)
    return result


def fit_group_agg(
    train: pd.DataFrame,
    group_col: str,
    agg_cols: list[str],
    agg_funcs: list[str] | None = None,
) -> dict:
    """Fit group aggregation statistics on training data only.

    Returns a mapping dict to apply with transform_group_agg.
    """
    if agg_funcs is None:
        agg_funcs = ["mean", "std"]

    agg_map: dict = {"group_col": group_col, "mappings": {}}
    for col in agg_cols:
        for func in agg_funcs:
            key = f"{col}_by_{group_col}_{func}"
            stats = train.groupby(group_col)[col].agg(func)
            agg_map["mappings"][key] = {"col": col, "func": func, "values": stats.to_dict()}
    return agg_map


def transform_group_agg(
    df: pd.DataFrame,
    agg_map: dict,
    group_col: str,
) -> pd.DataFrame:
    """Apply pre-fit group aggregation to a new DataFrame.

    Unseen groups get NaN.
    """
    result = df.copy()
    for key, info in agg_map["mappings"].items():
        result[key] = df[group_col].map(info["values"])
    return result


# ---------------------------------------------------------------------------
# Outlier handling
# ---------------------------------------------------------------------------

def clip_outliers(
    arr: np.ndarray,
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> np.ndarray:
    """Clip values to percentile bounds (winsorize).

    Args:
        arr: 1-D numeric array.
        lower_pct: Lower percentile (0-1).
        upper_pct: Upper percentile (0-1).

    Returns:
        Clipped array.
    """
    lo = np.percentile(arr, lower_pct * 100)
    hi = np.percentile(arr, upper_pct * 100)
    return np.clip(arr, lo, hi)


# ---------------------------------------------------------------------------
# Missing value indicators
# ---------------------------------------------------------------------------

def add_missing_indicators(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Add binary indicator columns for missingness.

    Args:
        df: Input DataFrame.
        columns: Columns to create indicators for.

    Returns:
        DataFrame with new '{col}_missing' columns (1=missing, 0=present).
    """
    result = df.copy()
    for col in columns:
        result[f"{col}_missing"] = df[col].isna().astype(int)
    return result


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def temporal_split(
    df: pd.DataFrame,
    time_col: str,
    train_end: str,
    val_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split DataFrame by time column into train and validation.

    Args:
        df: Input DataFrame with a datetime-like column.
        time_col: Name of the time column.
        train_end: Cutoff date string for training (exclusive).
        val_end: End date for validation (inclusive).

    Returns:
        (train, val) DataFrames.
    """
    ts = pd.to_datetime(df[time_col])
    train_mask = ts < pd.Timestamp(train_end)
    val_mask = (ts >= pd.Timestamp(train_end)) & (ts <= pd.Timestamp(val_end))
    return df[train_mask].copy(), df[val_mask].copy()


# ---------------------------------------------------------------------------
# Seed averaging
# ---------------------------------------------------------------------------

def seed_average(predictions: list[np.ndarray]) -> np.ndarray:
    """Average predictions from multiple random seeds.

    Args:
        predictions: List of prediction arrays (same shape).

    Returns:
        Element-wise mean of all prediction arrays.
    """
    return np.mean(np.stack(predictions), axis=0)


# ---------------------------------------------------------------------------
# Catalog — machine-readable index of available templates
# ---------------------------------------------------------------------------

def get_catalog() -> list[dict]:
    """Return a list of all available templates with metadata.

    Each entry: {"name", "category", "description", "usage"}.
    The Planner reads this to know what templates the Executor can use.
    """
    return [
        {
            "name": "target_encode",
            "category": "encoding",
            "description": "Smoothed target encoding with regularization. Prevents leakage via train-only fitting.",
            "usage": "train_enc, val_enc = templates.target_encode(train, val, columns=['cat_col'], target='y')",
        },
        {
            "name": "frequency_encode",
            "category": "encoding",
            "description": "Replace categories with their frequency proportion in training data.",
            "usage": "train_enc, val_enc = templates.frequency_encode(train, val, columns=['cat_col'])",
        },
        {
            "name": "group_agg_features",
            "category": "aggregation",
            "description": "Group-by aggregation features (mean, std, etc.). Core Kaggle winner pattern.",
            "usage": "df = templates.group_agg_features(df, group_col='entity', agg_cols=['amount'], agg_funcs=['mean','std'])",
        },
        {
            "name": "fit_group_agg / transform_group_agg",
            "category": "aggregation",
            "description": "Train/val safe group aggregation: fit on train, transform val (unseen groups get NaN).",
            "usage": "agg_map = templates.fit_group_agg(train, ...); val = templates.transform_group_agg(val, agg_map, ...)",
        },
        {
            "name": "clip_outliers",
            "category": "preprocessing",
            "description": "Winsorize outliers to percentile bounds.",
            "usage": "arr = templates.clip_outliers(arr, lower_pct=0.01, upper_pct=0.99)",
        },
        {
            "name": "add_missing_indicators",
            "category": "preprocessing",
            "description": "Binary indicator columns for missing values. Often adds signal for tree models.",
            "usage": "df = templates.add_missing_indicators(df, columns=['col_a', 'col_b'])",
        },
        {
            "name": "temporal_split",
            "category": "validation",
            "description": "Time-based train/val split. Production standard for temporal data.",
            "usage": "train, val = templates.temporal_split(df, time_col='date', train_end='2024-01-01', val_end='2024-06-01')",
        },
        {
            "name": "seed_average",
            "category": "ensemble",
            "description": "Average predictions from N random seeds. Reduces variance with zero complexity.",
            "usage": "avg_preds = templates.seed_average([preds_seed1, preds_seed2, preds_seed3])",
        },
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/strategy/test_templates.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/strategy/__init__.py runner/strategy/templates.py tests/strategy/__init__.py tests/strategy/test_templates.py
git commit -m "feat(strategy): add validated ML code template library with tests"
```

---

## Task 2: Error Analysis Tool

**Files:**
- Create: `runner/tools/error_analysis.py`
- Create: `tests/tools/test_error_analysis.py`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_error_analysis.py`:

```python
"""Tests for runner.tools.error_analysis — systematic model error analysis."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest

from runner.tools.error_analysis import analyze_errors


class TestAnalyzeErrors:
    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        n = 500
        y_true = np.array([0] * 400 + [1] * 100)
        y_prob = np.random.beta(2, 5, n)
        # Make positive cases have higher probs on average
        y_prob[y_true == 1] += 0.3
        y_prob = np.clip(y_prob, 0, 1)
        features = pd.DataFrame({
            "amount": np.random.exponential(100, n),
            "category": np.random.choice(["A", "B", "C"], n),
        })
        return y_true, y_prob, features

    def test_returns_required_keys(self, sample_data):
        y_true, y_prob, features = sample_data
        result = analyze_errors(y_true, y_prob, features, threshold=0.5)
        assert "fp_analysis" in result
        assert "fn_analysis" in result
        assert "summary" in result

    def test_fp_analysis_has_feature_distributions(self, sample_data):
        y_true, y_prob, features = sample_data
        result = analyze_errors(y_true, y_prob, features, threshold=0.5)
        fp = result["fp_analysis"]
        assert "count" in fp
        assert "feature_patterns" in fp

    def test_fn_analysis_has_feature_distributions(self, sample_data):
        y_true, y_prob, features = sample_data
        result = analyze_errors(y_true, y_prob, features, threshold=0.5)
        fn = result["fn_analysis"]
        assert "count" in fn
        assert "feature_patterns" in fn

    def test_summary_has_recommendations(self, sample_data):
        y_true, y_prob, features = sample_data
        result = analyze_errors(y_true, y_prob, features, threshold=0.5)
        assert "recommendations" in result["summary"]
        assert isinstance(result["summary"]["recommendations"], list)

    def test_bucketized_error_rates(self, sample_data):
        y_true, y_prob, features = sample_data
        result = analyze_errors(y_true, y_prob, features, threshold=0.5)
        assert "prob_calibration_buckets" in result["summary"]
        buckets = result["summary"]["prob_calibration_buckets"]
        assert len(buckets) > 0
        for b in buckets:
            assert "bucket" in b
            assert "n_samples" in b
            assert "actual_positive_rate" in b

    def test_handles_no_errors(self):
        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.9])
        features = pd.DataFrame({"x": [1, 2, 3, 4]})
        result = analyze_errors(y_true, y_prob, features, threshold=0.5)
        assert result["fp_analysis"]["count"] == 0
        assert result["fn_analysis"]["count"] == 0

    def test_cli_interface(self, tmp_path, sample_data):
        """CLI should accept npy/csv paths and output JSON."""
        y_true, y_prob, features = sample_data
        np.save(tmp_path / "y_true.npy", y_true)
        np.save(tmp_path / "y_prob.npy", y_prob)
        features.to_csv(tmp_path / "features.csv", index=False)

        import subprocess
        result = subprocess.run(
            [
                "python", "-m", "runner.tools.error_analysis",
                "--y-true", str(tmp_path / "y_true.npy"),
                "--y-prob", str(tmp_path / "y_prob.npy"),
                "--features", str(tmp_path / "features.csv"),
                "--threshold", "0.5",
            ],
            capture_output=True, text=True,
            cwd="/home/jupyter/Thinkubator/auto_train",
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "fp_analysis" in output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/tools/test_error_analysis.py -v 2>&1 | head -20
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement error_analysis.py**

Create `runner/tools/error_analysis.py`:

```python
"""Systematic error analysis — bucketize model failures into actionable patterns.

Given y_true, y_prob, and a feature DataFrame, identifies:
1. False positives: what do FP cases look like? (feature distributions)
2. False negatives: what do FN cases look like?
3. Probability calibration: are predicted probabilities well-calibrated?
4. Recommendations: specific feature engineering or model changes to address patterns.

Usage:
    python -m runner.tools.error_analysis \\
        --y-true artifacts/y_val_true.npy \\
        --y-prob artifacts/y_val_prob.npy \\
        --features artifacts/X_val.csv \\
        --threshold 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import numpy as np
import pandas as pd


def _describe_numeric(series: pd.Series) -> dict:
    """Compact numeric summary."""
    return {
        "mean": float(series.mean()),
        "median": float(series.median()),
        "std": float(series.std()) if len(series) > 1 else 0.0,
        "min": float(series.min()),
        "max": float(series.max()),
    }


def _describe_categorical(series: pd.Series, top_n: int = 5) -> dict:
    """Top-N value counts for categorical column."""
    vc = series.value_counts().head(top_n)
    return {
        "top_values": {str(k): int(v) for k, v in vc.items()},
        "n_unique": int(series.nunique()),
    }


def _feature_patterns(
    subset: pd.DataFrame,
    baseline: pd.DataFrame,
) -> list[dict]:
    """Compare feature distributions between an error subset and the full dataset."""
    patterns = []
    for col in subset.columns:
        entry: dict[str, Any] = {"feature": col}
        if pd.api.types.is_numeric_dtype(subset[col]):
            entry["type"] = "numeric"
            entry["error_subset"] = _describe_numeric(subset[col].dropna())
            entry["baseline"] = _describe_numeric(baseline[col].dropna())
            # Flag if error subset mean differs from baseline by >1 std
            base_std = baseline[col].std()
            if base_std > 0:
                diff = abs(
                    subset[col].mean() - baseline[col].mean()
                ) / base_std
                entry["z_diff"] = round(float(diff), 3)
            else:
                entry["z_diff"] = 0.0
        else:
            entry["type"] = "categorical"
            entry["error_subset"] = _describe_categorical(subset[col])
            entry["baseline"] = _describe_categorical(baseline[col])
            entry["z_diff"] = 0.0  # categorical — no z-score
        patterns.append(entry)

    # Sort by magnitude of difference (numeric features)
    patterns.sort(key=lambda x: abs(x.get("z_diff", 0)), reverse=True)
    return patterns


def _calibration_buckets(y_true: np.ndarray, y_prob: np.ndarray, n_buckets: int = 10) -> list[dict]:
    """Bucketize predictions and compare predicted vs actual positive rate."""
    buckets = []
    edges = np.linspace(0, 1, n_buckets + 1)
    for i in range(n_buckets):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi) if i < n_buckets - 1 else (y_prob >= lo) & (y_prob <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        actual_rate = float(y_true[mask].mean())
        pred_mean = float(y_prob[mask].mean())
        buckets.append({
            "bucket": f"[{lo:.1f}, {hi:.1f})",
            "n_samples": n,
            "predicted_mean": round(pred_mean, 4),
            "actual_positive_rate": round(actual_rate, 4),
            "calibration_gap": round(abs(pred_mean - actual_rate), 4),
        })
    return buckets


def _generate_recommendations(
    fp_patterns: list[dict],
    fn_patterns: list[dict],
    fp_count: int,
    fn_count: int,
    calibration: list[dict],
) -> list[str]:
    """Generate actionable recommendations from error analysis."""
    recs = []

    # Find features with high z_diff in FP/FN subsets
    fp_top = [p for p in fp_patterns if p.get("z_diff", 0) > 1.5 and p["type"] == "numeric"]
    fn_top = [p for p in fn_patterns if p.get("z_diff", 0) > 1.5 and p["type"] == "numeric"]

    if fp_top:
        names = [p["feature"] for p in fp_top[:3]]
        recs.append(
            f"FP concentration: features {names} differ significantly in FP subset. "
            f"Consider interaction features or binning to help model distinguish."
        )

    if fn_top:
        names = [p["feature"] for p in fn_top[:3]]
        recs.append(
            f"FN concentration: features {names} differ significantly in FN subset. "
            f"Consider adding derived features or group-by aggregations on these."
        )

    if fp_count > 0 and fn_count > 0:
        ratio = fp_count / max(fn_count, 1)
        if ratio > 3:
            recs.append(
                f"FP/FN ratio = {ratio:.1f}: model is over-predicting positives. "
                f"Consider raising threshold or adjusting class weights."
            )
        elif ratio < 0.33:
            recs.append(
                f"FP/FN ratio = {ratio:.1f}: model is missing positives. "
                f"Consider lowering threshold or adjusting class weights."
            )

    # Check calibration
    worst_cal = max(calibration, key=lambda x: x["calibration_gap"], default=None)
    if worst_cal and worst_cal["calibration_gap"] > 0.15:
        recs.append(
            f"Calibration gap of {worst_cal['calibration_gap']:.2f} in bucket {worst_cal['bucket']}. "
            f"Consider Platt scaling or isotonic regression."
        )

    if not recs:
        recs.append("No strong error patterns detected. Consider ensemble or HP tuning.")

    return recs


def analyze_errors(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    features: pd.DataFrame,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Run systematic error analysis on model predictions.

    Args:
        y_true: Ground truth labels (0/1).
        y_prob: Predicted probabilities.
        features: Feature DataFrame (same rows as y_true/y_prob).
        threshold: Classification threshold.

    Returns:
        Dict with 'fp_analysis', 'fn_analysis', 'summary' keys.
    """
    y_pred = (y_prob >= threshold).astype(int)

    fp_mask = (y_pred == 1) & (y_true == 0)
    fn_mask = (y_pred == 0) & (y_true == 1)
    tp_mask = (y_pred == 1) & (y_true == 1)
    tn_mask = (y_pred == 0) & (y_true == 0)

    fp_count = int(fp_mask.sum())
    fn_count = int(fn_mask.sum())

    fp_patterns = _feature_patterns(features[fp_mask], features) if fp_count > 0 else []
    fn_patterns = _feature_patterns(features[fn_mask], features) if fn_count > 0 else []

    calibration = _calibration_buckets(y_true, y_prob)
    recommendations = _generate_recommendations(
        fp_patterns, fn_patterns, fp_count, fn_count, calibration,
    )

    return {
        "fp_analysis": {
            "count": fp_count,
            "feature_patterns": fp_patterns[:10],  # Top 10 by z_diff
        },
        "fn_analysis": {
            "count": fn_count,
            "feature_patterns": fn_patterns[:10],
        },
        "summary": {
            "total_samples": len(y_true),
            "positives": int(y_true.sum()),
            "negatives": int((1 - y_true).sum()),
            "tp": int(tp_mask.sum()),
            "fp": fp_count,
            "fn": fn_count,
            "tn": int(tn_mask.sum()),
            "threshold": threshold,
            "prob_calibration_buckets": calibration,
            "recommendations": recommendations,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Systematic error analysis")
    parser.add_argument("--y-true", required=True, help="Path to y_true .npy file")
    parser.add_argument("--y-prob", required=True, help="Path to y_prob .npy file")
    parser.add_argument("--features", required=True, help="Path to features CSV")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    y_true = np.load(args.y_true)
    y_prob = np.load(args.y_prob)
    features = pd.read_csv(args.features)

    result = analyze_errors(y_true, y_prob, features, threshold=args.threshold)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/tools/test_error_analysis.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/tools/error_analysis.py tests/tools/test_error_analysis.py
git commit -m "feat(tools): add systematic error analysis tool with FP/FN pattern detection"
```

---

## Task 3: Tree Search with UCB1

**Files:**
- Create: `runner/strategy/tree_search.py`
- Create: `tests/strategy/test_tree_search.py`
- Modify: `runner/runner_driver.py`
- Modify: `tests/test_runner_driver.py`

- [ ] **Step 1: Write failing tests for tree_search module**

Create `tests/strategy/test_tree_search.py`:

```python
"""Tests for runner.strategy.tree_search — experiment tree + UCB1 scoring."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from runner.strategy.tree_search import (
    ExperimentTree,
    STRATEGY_CLASSES,
)


class TestExperimentTree:
    def test_init_creates_root(self):
        tree = ExperimentTree()
        assert tree.root is not None
        assert tree.root["commit"] == "ROOT"
        assert tree.root["children"] == []

    def test_add_experiment_to_root(self):
        tree = ExperimentTree()
        tree.add_experiment(
            commit="abc123",
            parent_commit="ROOT",
            strategy_class="A_model",
            metric_value=0.82,
            verdict="keep",
        )
        assert len(tree.root["children"]) == 1
        child = tree.get_node("abc123")
        assert child is not None
        assert child["strategy_class"] == "A_model"
        assert child["metric_value"] == 0.82

    def test_add_experiment_to_non_root_parent(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        node_b = tree.get_node("b")
        assert node_b is not None
        assert node_b["parent_commit"] == "a"

    def test_branching_from_same_parent(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "a", "A_feature", 0.83, "keep")
        node_a = tree.get_node("a")
        assert len(node_a["children"]) == 2

    def test_get_strategy_class_stats(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.845, "keep")
        tree.add_experiment("d", "c", "A_feature", 0.83, "discard")
        stats = tree.get_strategy_stats()
        assert stats["A_model"]["n_attempts"] == 1
        assert stats["A_hp"]["n_attempts"] == 2
        assert stats["A_feature"]["n_attempts"] == 1

    def test_compute_ucb1_scores(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.841, "keep")
        scores = tree.compute_ucb1(exploration_constant=1.0)
        # A_model tried 1x, A_hp tried 2x
        # Untried classes should have highest score (infinity)
        for cls in STRATEGY_CLASSES:
            assert cls in scores
        # A_feature never tried → score should be inf
        assert scores["A_feature"] == float("inf")
        # A_hp tried 2x → finite score
        assert math.isfinite(scores["A_hp"])

    def test_ucb1_untried_classes_are_infinite(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        scores = tree.compute_ucb1()
        untried = [c for c in STRATEGY_CLASSES if c != "A_model"]
        for cls in untried:
            assert scores[cls] == float("inf"), f"{cls} should be inf (untried)"

    def test_diminishing_returns_flag(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_hp", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.821, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.8215, "discard")
        dr = tree.detect_diminishing_returns(epsilon=0.005)
        assert "A_hp" in dr

    def test_no_diminishing_returns_when_improving(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_hp", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.86, "keep")
        dr = tree.detect_diminishing_returns(epsilon=0.005)
        assert "A_hp" not in dr

    def test_get_best_branch_point(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.841, "discard")
        # Best branch point should be 'b' (highest metric with keep verdict)
        best = tree.get_best_branch_point()
        assert best == "b"

    def test_get_phase(self):
        tree = ExperimentTree()
        assert tree.get_phase(budget_total=20, budget_used=0) == "diversify"
        assert tree.get_phase(budget_total=20, budget_used=5) == "diversify"
        assert tree.get_phase(budget_total=20, budget_used=7) == "deepen"
        assert tree.get_phase(budget_total=20, budget_used=15) == "exploit"

    def test_serialize_deserialize(self, tmp_path):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")

        path = tmp_path / "tree.json"
        tree.save(path)
        assert path.exists()

        loaded = ExperimentTree.load(path)
        assert loaded.get_node("a") is not None
        assert loaded.get_node("b") is not None
        assert loaded.get_node("b")["parent_commit"] == "a"

    def test_get_planner_context(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        ctx = tree.get_planner_context(budget_total=20, budget_used=2, noise_floor=0.005)
        assert "phase" in ctx
        assert "ucb1_scores" in ctx
        assert "diminishing_returns" in ctx
        assert "best_branch_point" in ctx
        assert "strategy_stats" in ctx
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/strategy/test_tree_search.py -v 2>&1 | head -20
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement tree_search.py**

Create `runner/strategy/tree_search.py`:

```python
"""Experiment tree with UCB1 exploration/exploitation scoring.

Maintains a tree of experiments where each node tracks:
- Which experiment (commit) it represents
- Its parent (which state it branched from)
- Its strategy class (A_model, A_hp, A_feature, etc.)
- Its metric value and verdict

The tree supports:
- UCB1 scoring per strategy class (guides Planner's next choice)
- Diminishing returns detection (prune exhausted directions)
- Phase detection (diversify → deepen → exploit)
- Best branch point identification (where to branch from for new directions)
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

STRATEGY_CLASSES = [
    "A_model",
    "A_feature",
    "A_hp",
    "A_imbalance",
    "A_ensemble",
    "A_validate",
    "A_error_analysis",
]

# Phase thresholds as fraction of total budget
_DIVERSIFY_END = 0.30
_DEEPEN_END = 0.70


def _make_node(
    commit: str,
    parent_commit: str | None,
    strategy_class: str | None = None,
    metric_value: float | None = None,
    verdict: str | None = None,
) -> dict:
    return {
        "commit": commit,
        "parent_commit": parent_commit,
        "strategy_class": strategy_class,
        "metric_value": metric_value,
        "verdict": verdict,
        "children": [],
    }


class ExperimentTree:
    """Tree of experiments with UCB1-guided strategy selection."""

    def __init__(self):
        self.root = _make_node(commit="ROOT", parent_commit=None)
        self._index: dict[str, dict] = {"ROOT": self.root}

    def add_experiment(
        self,
        commit: str,
        parent_commit: str,
        strategy_class: str,
        metric_value: float | None,
        verdict: str,
    ) -> None:
        """Add a new experiment node to the tree."""
        node = _make_node(
            commit=commit,
            parent_commit=parent_commit,
            strategy_class=strategy_class,
            metric_value=metric_value,
            verdict=verdict,
        )
        self._index[commit] = node

        parent = self._index.get(parent_commit)
        if parent is not None:
            parent["children"].append(commit)

    def get_node(self, commit: str) -> dict | None:
        return self._index.get(commit)

    def get_all_experiments(self) -> list[dict]:
        """Return all non-ROOT nodes."""
        return [n for c, n in self._index.items() if c != "ROOT"]

    def get_strategy_stats(self) -> dict[str, dict]:
        """Compute per-strategy-class statistics.

        Returns dict of {strategy_class: {n_attempts, n_keeps, deltas, mean_delta}}.
        """
        stats: dict[str, dict] = {}
        for cls in STRATEGY_CLASSES:
            stats[cls] = {"n_attempts": 0, "n_keeps": 0, "deltas": []}

        experiments = self.get_all_experiments()
        for exp in experiments:
            cls = exp.get("strategy_class")
            if cls not in stats:
                stats[cls] = {"n_attempts": 0, "n_keeps": 0, "deltas": []}

            stats[cls]["n_attempts"] += 1
            if exp.get("verdict") == "keep":
                stats[cls]["n_keeps"] += 1

            # Compute delta from parent
            parent = self._index.get(exp.get("parent_commit", ""))
            if (
                parent is not None
                and parent.get("metric_value") is not None
                and exp.get("metric_value") is not None
            ):
                delta = exp["metric_value"] - parent["metric_value"]
                stats[cls]["deltas"].append(delta)

        for cls in stats:
            deltas = stats[cls]["deltas"]
            stats[cls]["mean_delta"] = float(sum(deltas) / len(deltas)) if deltas else 0.0

        return stats

    def compute_ucb1(self, exploration_constant: float = 1.414) -> dict[str, float]:
        """Compute UCB1 score for each strategy class.

        UCB1_i = mean_delta_i + c * sqrt(ln(N) / n_i)

        Untried classes get score = inf (must be tried first).
        """
        stats = self.get_strategy_stats()
        total_n = sum(s["n_attempts"] for s in stats.values())

        scores: dict[str, float] = {}
        for cls in STRATEGY_CLASSES:
            s = stats.get(cls, {"n_attempts": 0, "mean_delta": 0.0})
            n_i = s["n_attempts"]
            if n_i == 0:
                scores[cls] = float("inf")
            elif total_n == 0:
                scores[cls] = float("inf")
            else:
                mean_d = s["mean_delta"]
                exploration_bonus = exploration_constant * math.sqrt(
                    math.log(total_n) / n_i
                )
                scores[cls] = mean_d + exploration_bonus

        return scores

    def detect_diminishing_returns(self, epsilon: float = 0.005) -> list[str]:
        """Return strategy classes where the last 2+ experiments all improved by < epsilon.

        These classes are candidates for pruning (stop deepening this branch).
        """
        stats = self.get_strategy_stats()
        flagged = []
        for cls, s in stats.items():
            deltas = s["deltas"]
            if len(deltas) >= 2 and all(abs(d) < epsilon for d in deltas[-2:]):
                flagged.append(cls)
        return flagged

    def get_best_branch_point(self) -> str:
        """Return the commit of the experiment with the highest metric among keeps.

        This is where the agent should branch from to try a new direction.
        """
        best_commit = "ROOT"
        best_metric = float("-inf")
        for exp in self.get_all_experiments():
            if exp.get("verdict") == "keep" and exp.get("metric_value") is not None:
                if exp["metric_value"] > best_metric:
                    best_metric = exp["metric_value"]
                    best_commit = exp["commit"]
        return best_commit

    def get_phase(self, budget_total: int, budget_used: int) -> str:
        """Determine current exploration/exploitation phase.

        Returns one of: "diversify", "deepen", "exploit".
        """
        if budget_total <= 0:
            return "exploit"
        frac = budget_used / budget_total
        if frac <= _DIVERSIFY_END:
            return "diversify"
        elif frac <= _DEEPEN_END:
            return "deepen"
        else:
            return "exploit"

    def get_planner_context(
        self,
        budget_total: int,
        budget_used: int,
        noise_floor: float = 0.005,
    ) -> dict[str, Any]:
        """Generate the full context block that gets injected into the Planner prompt.

        Returns a dict with all the information the Planner needs for strategy selection.
        """
        phase = self.get_phase(budget_total, budget_used)
        ucb1 = self.compute_ucb1()
        dr = self.detect_diminishing_returns(epsilon=noise_floor)
        best_bp = self.get_best_branch_point()
        stats = self.get_strategy_stats()

        # Penalize diminishing-returns classes
        for cls in dr:
            if cls in ucb1 and math.isfinite(ucb1[cls]):
                ucb1[cls] *= 0.5  # Halve score for exhausted classes

        # Sort by UCB1 score descending
        ranked = sorted(ucb1.items(), key=lambda x: x[1], reverse=True)

        return {
            "phase": phase,
            "phase_description": {
                "diversify": "MANDATORY DIVERSIFICATION: Try at least one experiment from each untried strategy class before deepening any.",
                "deepen": "UCB1-GUIDED DEEPENING: Select the strategy class with the highest UCB1 score. Refine promising directions.",
                "exploit": "EXPLOITATION: Ensemble, stack, final HP tune. Reserve 1-2 experiments for a moonshot.",
            }[phase],
            "ucb1_scores": {cls: round(s, 4) if math.isfinite(s) else "inf (must try)" for cls, s in ranked},
            "diminishing_returns": dr,
            "best_branch_point": best_bp,
            "strategy_stats": {
                cls: {
                    "n_attempts": s["n_attempts"],
                    "n_keeps": s["n_keeps"],
                    "mean_delta": round(s["mean_delta"], 6),
                }
                for cls, s in stats.items()
                if s["n_attempts"] > 0
            },
            "budget_remaining": budget_total - budget_used,
            "budget_fraction_used": round(budget_used / max(budget_total, 1), 2),
        }

    def save(self, path: Path) -> None:
        """Serialize tree to JSON file."""
        data = {
            "schema_version": 1,
            "nodes": {commit: node for commit, node in self._index.items()},
        }
        path.write_text(json.dumps(data, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> ExperimentTree:
        """Deserialize tree from JSON file."""
        data = json.loads(path.read_text())
        tree = cls.__new__(cls)
        tree._index = {}

        nodes = data.get("nodes", {})
        for commit, node_data in nodes.items():
            tree._index[commit] = node_data

        tree.root = tree._index.get("ROOT", _make_node("ROOT", None))
        return tree
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/strategy/test_tree_search.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/strategy/tree_search.py tests/strategy/test_tree_search.py
git commit -m "feat(strategy): add experiment tree with UCB1 exploration/exploitation scoring"
```

---

## Task 4: Integrate Tree Search into Runner Driver

**Files:**
- Modify: `runner/runner_driver.py`
- Modify: `tests/test_runner_driver.py`

- [ ] **Step 1: Write failing tests for tree integration**

Append to `tests/test_runner_driver.py`:

```python
# --- Tree search integration tests ---

def test_init_creates_experiment_tree(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    tree_path = campaign / "state" / "EXPERIMENT_TREE.json"
    assert tree_path.exists()
    data = json.loads(tree_path.read_text())
    assert "nodes" in data
    assert "ROOT" in data["nodes"]


def test_review_finalize_keep_updates_experiment_tree(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    runner_driver.review_finalize(
        verdict="keep",
        commit="abc123",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="tighter range",
        description="initial lgbm",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    tree_path = campaign / "state" / "EXPERIMENT_TREE.json"
    data = json.loads(tree_path.read_text())
    assert "abc123" in data["nodes"]
    node = data["nodes"]["abc123"]
    assert node["strategy_class"] == "A_hp"
    assert node["metric_value"] == 0.80
    assert node["verdict"] == "keep"


def test_review_finalize_discard_updates_experiment_tree(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    # First: a keep to establish baseline
    runner_driver.review_finalize(
        verdict="keep", commit="base",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_model", hypothesis="base", description="base",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(campaign), tools_ran=["tools/anomaly.py"],
    )
    # Second: a discard
    runner_driver.review_finalize(
        verdict="discard", commit="bad",
        metrics={"val_pr_auc": 0.75, "lift_at_10": 3.0, "macro_f1": 0.7, "val_f1": 0.6},
        action_type="A_hp", hypothesis="bad hp", description="bad",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(campaign),
    )
    tree_path = campaign / "state" / "EXPERIMENT_TREE.json"
    data = json.loads(tree_path.read_text())
    assert "bad" in data["nodes"]
    assert data["nodes"]["bad"]["verdict"] == "discard"


def test_review_finalize_tree_parent_is_best_so_far(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    # Keep 'a' as baseline
    runner_driver.review_finalize(
        verdict="keep", commit="a",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_model", hypothesis="a", description="a",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(campaign), tools_ran=["tools/anomaly.py"],
    )
    # Keep 'b' as improvement
    runner_driver.review_finalize(
        verdict="keep", commit="b",
        metrics={"val_pr_auc": 0.85, "lift_at_10": 6.0, "macro_f1": 0.85, "val_f1": 0.8},
        action_type="A_hp", hypothesis="b", description="b",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(campaign), tools_ran=["tools/anomaly.py"],
    )
    tree_path = campaign / "state" / "EXPERIMENT_TREE.json"
    data = json.loads(tree_path.read_text())
    # 'b' should be a child of 'a' (best_so_far at time of 'b')
    assert data["nodes"]["b"]["parent_commit"] == "a"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/test_runner_driver.py::test_init_creates_experiment_tree -v 2>&1 | head -20
```

Expected: FAIL (EXPERIMENT_TREE.json not created).

- [ ] **Step 3: Modify runner_driver.py — init_campaign**

In `runner/runner_driver.py`, add the tree creation to `init_campaign()`.

Add import at top of file (after existing imports):

```python
from runner.strategy.tree_search import ExperimentTree
```

Add tree creation inside `init_campaign()`, after the PATTERN_BOOK skeleton creation (after line ~258):

```python
    # Create experiment tree for tree-search exploration/exploitation
    tree_path = state_dir / "EXPERIMENT_TREE.json"
    if not tree_path.exists():
        tree = ExperimentTree()
        tree.save(tree_path)
```

- [ ] **Step 4: Modify runner_driver.py — review_finalize**

In `review_finalize()`, add tree update logic after the `log.append_result(...)` call and before `state_after = json.loads(state_path.read_text())`:

```python
    # Update experiment tree
    tree_path = camp / "state" / "EXPERIMENT_TREE.json"
    if tree_path.exists():
        tree = ExperimentTree.load(tree_path)
        # Parent is the best_so_far commit at time of this experiment
        parent_commit = (state.get("best_so_far") or {}).get("commit") or "ROOT"
        pm_value = metrics.get(metric_name)
        tree.add_experiment(
            commit=commit or "unknown",
            parent_commit=parent_commit,
            strategy_class=action_type,
            metric_value=float(pm_value) if pm_value is not None else None,
            verdict=verdict,
        )
        tree.save(tree_path)
```

- [ ] **Step 5: Run all runner_driver tests to verify everything passes**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/test_runner_driver.py -v
```

Expected: All existing tests PASS + new tree tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/runner_driver.py tests/test_runner_driver.py
git commit -m "feat(driver): integrate experiment tree into init_campaign and review_finalize"
```

---

## Task 5: Temporal Cross-Validation Tool

**Files:**
- Create: `runner/tools/temporal_cv.py`
- Create: `tests/tools/test_temporal_cv.py`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_temporal_cv.py`:

```python
"""Tests for runner.tools.temporal_cv — time-based cross-validation."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest

from runner.tools.temporal_cv import temporal_cv_splits, temporal_cv_evaluate


class TestTemporalCvSplits:
    def test_basic_splits(self):
        n = 1000
        dates = pd.date_range("2020-01-01", periods=n, freq="D")
        splits = temporal_cv_splits(
            dates,
            n_splits=3,
            train_ratio=0.6,
            gap_days=0,
        )
        assert len(splits) == 3
        for train_idx, val_idx in splits:
            assert len(train_idx) > 0
            assert len(val_idx) > 0
            # Train must be strictly before val
            assert dates[train_idx].max() < dates[val_idx].min()

    def test_gap_between_train_and_val(self):
        n = 1000
        dates = pd.date_range("2020-01-01", periods=n, freq="D")
        splits = temporal_cv_splits(dates, n_splits=2, train_ratio=0.5, gap_days=30)
        for train_idx, val_idx in splits:
            gap = (dates[val_idx].min() - dates[train_idx].max()).days
            assert gap >= 30

    def test_expanding_window(self):
        """Later splits should have more training data."""
        n = 1000
        dates = pd.date_range("2020-01-01", periods=n, freq="D")
        splits = temporal_cv_splits(dates, n_splits=3, train_ratio=0.5, gap_days=0)
        train_sizes = [len(t) for t, _ in splits]
        # Each successive split should have >= the previous training data
        for i in range(1, len(train_sizes)):
            assert train_sizes[i] >= train_sizes[i - 1]

    def test_no_overlap(self):
        n = 500
        dates = pd.date_range("2020-01-01", periods=n, freq="D")
        splits = temporal_cv_splits(dates, n_splits=3, train_ratio=0.5, gap_days=0)
        for train_idx, val_idx in splits:
            overlap = set(train_idx) & set(val_idx)
            assert len(overlap) == 0


class TestTemporalCvEvaluate:
    def test_returns_per_fold_and_aggregate_metrics(self):
        np.random.seed(42)
        n = 500
        X = pd.DataFrame({"f1": np.random.randn(n), "f2": np.random.randn(n)})
        y = (X["f1"] + np.random.randn(n) * 0.5 > 0).astype(int)
        dates = pd.date_range("2020-01-01", periods=n, freq="D")

        result = temporal_cv_evaluate(
            X, y, dates,
            n_splits=2,
            train_ratio=0.5,
            gap_days=0,
            metric_fn=lambda yt, yp: float(np.mean((yp > 0.5) == yt)),
            model_factory=lambda: __import__("sklearn.linear_model", fromlist=["LogisticRegression"]).LogisticRegression(max_iter=200),
        )
        assert "fold_metrics" in result
        assert "mean_metric" in result
        assert "std_metric" in result
        assert len(result["fold_metrics"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/tools/test_temporal_cv.py -v 2>&1 | head -20
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement temporal_cv.py**

Create `runner/tools/temporal_cv.py`:

```python
"""Temporal (time-based) cross-validation — production-standard validation for time-series.

Splits data chronologically with expanding training windows and optional gap periods
to prevent leakage from adjacent time periods.

Usage:
    python -m runner.tools.temporal_cv \\
        --dates-col time \\
        --n-splits 3 \\
        --train-ratio 0.6 \\
        --gap-days 30
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

import numpy as np
import pandas as pd


def temporal_cv_splits(
    dates: pd.DatetimeIndex | pd.Series,
    n_splits: int = 3,
    train_ratio: float = 0.6,
    gap_days: int = 0,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Generate temporal cross-validation split indices.

    Uses expanding window: each successive fold has more training data.
    Validation window slides forward in time.

    Args:
        dates: DatetimeIndex or Series of timestamps (one per row).
        n_splits: Number of CV folds.
        train_ratio: Minimum fraction of data for the first training fold.
        gap_days: Number of days gap between train end and val start (prevent leakage).

    Returns:
        List of (train_indices, val_indices) tuples.
    """
    if not isinstance(dates, pd.DatetimeIndex):
        dates = pd.DatetimeIndex(dates)

    sorted_idx = np.argsort(dates)
    sorted_dates = dates[sorted_idx]
    n = len(sorted_dates)

    # Calculate fold boundaries
    min_train = int(n * train_ratio)
    remaining = n - min_train
    val_size = remaining // (n_splits)

    if val_size < 1:
        val_size = 1

    splits = []
    for i in range(n_splits):
        # Expanding training window
        train_end_idx = min_train + i * val_size
        val_start_idx = train_end_idx
        val_end_idx = min(train_end_idx + val_size, n)

        if val_start_idx >= n or val_end_idx <= val_start_idx:
            break

        # Apply gap
        if gap_days > 0:
            train_end_date = sorted_dates[train_end_idx - 1]
            gap_cutoff = train_end_date + pd.Timedelta(days=gap_days)
            # Find first val index after gap
            gap_mask = sorted_dates[val_start_idx:val_end_idx] >= gap_cutoff
            if not gap_mask.any():
                continue  # Gap too large for this fold
            gap_offset = np.argmax(gap_mask.values)
            val_start_idx = val_start_idx + gap_offset

        if val_start_idx >= val_end_idx:
            continue

        train_indices = sorted_idx[:train_end_idx]
        val_indices = sorted_idx[val_start_idx:val_end_idx]

        splits.append((train_indices, val_indices))

    return splits


def temporal_cv_evaluate(
    X: pd.DataFrame,
    y: np.ndarray | pd.Series,
    dates: pd.DatetimeIndex | pd.Series,
    n_splits: int = 3,
    train_ratio: float = 0.6,
    gap_days: int = 0,
    metric_fn: Callable[[np.ndarray, np.ndarray], float] | None = None,
    model_factory: Callable | None = None,
) -> dict[str, Any]:
    """Run temporal CV and collect per-fold metrics.

    Args:
        X: Feature DataFrame.
        y: Target array/Series.
        dates: Timestamps for temporal ordering.
        n_splits: Number of folds.
        train_ratio: Minimum training fraction.
        gap_days: Gap between train/val.
        metric_fn: Function(y_true, y_prob) -> float. Defaults to average_precision_score.
        model_factory: Callable that returns a fresh sklearn-compatible model.

    Returns:
        {"fold_metrics": [...], "mean_metric": float, "std_metric": float}
    """
    if metric_fn is None:
        from sklearn.metrics import average_precision_score
        metric_fn = average_precision_score

    if model_factory is None:
        from sklearn.linear_model import LogisticRegression
        model_factory = lambda: LogisticRegression(max_iter=200)

    y_arr = np.asarray(y)
    splits = temporal_cv_splits(dates, n_splits, train_ratio, gap_days)

    fold_metrics = []
    for i, (train_idx, val_idx) in enumerate(splits):
        X_train = X.iloc[train_idx] if isinstance(X, pd.DataFrame) else X[train_idx]
        X_val = X.iloc[val_idx] if isinstance(X, pd.DataFrame) else X[val_idx]
        y_train = y_arr[train_idx]
        y_val = y_arr[val_idx]

        model = model_factory()
        model.fit(X_train, y_train)

        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_val)[:, 1]
        else:
            y_prob = model.predict(X_val)

        score = metric_fn(y_val, y_prob)
        fold_metrics.append(float(score))

    return {
        "fold_metrics": fold_metrics,
        "mean_metric": float(np.mean(fold_metrics)) if fold_metrics else 0.0,
        "std_metric": float(np.std(fold_metrics)) if fold_metrics else 0.0,
        "n_splits_used": len(fold_metrics),
    }


def main():
    parser = argparse.ArgumentParser(description="Temporal cross-validation splits")
    parser.add_argument("--n-splits", type=int, default=3)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--gap-days", type=int, default=0)
    parser.add_argument("--dates-col", default="time")
    args = parser.parse_args()

    config = {
        "n_splits": args.n_splits,
        "train_ratio": args.train_ratio,
        "gap_days": args.gap_days,
        "dates_col": args.dates_col,
    }
    json.dump(config, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/tools/test_temporal_cv.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/tools/temporal_cv.py tests/tools/test_temporal_cv.py
git commit -m "feat(tools): add temporal cross-validation with expanding window and gap support"
```

---

## Task 6: Update Planner Role Prompt

**Files:**
- Modify: `runner/roles/planner.md`

- [ ] **Step 1: Add UCB1 context and template catalog to Planner inputs**

Append a new input entry after the existing `TOKEN_SUMMARY` line in the Planner's input list section:

```markdown
- `state/EXPERIMENT_TREE.json` (via tree search context — see §11)
```

- [ ] **Step 2: Add Step 11 — UCB1-Guided Strategy Selection**

Append after Step 10 in the Planner's procedure:

```markdown
### Step 11 — UCB1-guided strategy selection (NEW)

Read the tree search context from `state/EXPERIMENT_TREE.json` (the driver computes UCB1 scores and phase automatically). The context contains:

- **phase**: One of `diversify`, `deepen`, `exploit`.
  - `diversify` (first ~30% of budget): MUST try at least one experiment from each strategy class that has UCB1 = inf (never tried). Do NOT deepen any single direction until all major classes have been sampled.
  - `deepen` (middle ~40%): Select the strategy class with the **highest UCB1 score**. If that class has a diminishing-returns flag, skip to the next highest.
  - `exploit` (last ~30%): Ensemble, stack, or final HP tune the champion. Reserve 1-2 experiments for one high-risk moonshot.

- **ucb1_scores**: Per-strategy-class scores. Higher = explore this more.
  - `inf` means untried — MUST be tried before any class with a finite score.
  - Diminishing-returns classes have halved scores.

- **diminishing_returns**: Strategy classes where the last 2+ experiments improved by < noise_floor. Avoid deepening these further.

- **best_branch_point**: Commit to branch from if trying a new direction (not necessarily HEAD — may be an earlier experiment).

- **strategy_stats**: Per-class attempt counts, keep rates, and mean deltas.

**Integration with Step 6 (pre-selection reasoning):**
When enumerating 2-3 candidates in Step 6, the UCB1 scores MUST be cited. Format:

```
Candidate 1: A_feature (UCB1 = 0.31, 2 attempts, mean Δ = +0.004)
Candidate 2: A_ensemble (UCB1 = inf, untried — mandatory diversification)
Candidate 3: A_hp (UCB1 = 0.18, diminishing returns flagged — skip)

Selection: A_ensemble (mandatory diversification — never tried)
```

### Step 12 — Template catalog check (NEW)

Before writing §3 Plan in NEXT_EXPERIMENT.md, check `runner/strategy/templates.py` catalog:

```python
from runner.strategy.templates import get_catalog
catalog = get_catalog()  # Returns list of available template names + usage
```

If the chosen technique has a matching template (e.g., `target_encode`, `group_agg_features`, `temporal_split`), reference it in §3 Plan so the Executor knows to use validated code:

```
§3 Plan:
1. Use `templates.target_encode(train, val, columns=['county_cd'], target='y')` from runner/strategy/templates.py
2. Add the encoded columns to the feature matrix
3. Retrain champion model with the new features
```
```

- [ ] **Step 3: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/roles/planner.md
git commit -m "feat(roles): add UCB1-guided strategy selection and template catalog to Planner"
```

---

## Task 7: Update Reviewer Role Prompt

**Files:**
- Modify: `runner/roles/reviewer.md`

- [ ] **Step 1: Add error analysis to Reviewer Phase 1**

In `runner/roles/reviewer.md`, add error analysis as a new step in Phase 1, after the existing anomaly check (step 4) and mandatory tools run (step 5):

```markdown
### Step 5b — Error analysis (NEW, optional but recommended)

If artifacts/y_val_true.npy and artifacts/y_val_prob.npy exist, and the feature DataFrame is available:

```bash
python -m runner.tools.error_analysis \
    --y-true artifacts/y_val_true.npy \
    --y-prob artifacts/y_val_prob.npy \
    --features artifacts/X_val.csv \
    --threshold 0.5
```

Record the output in REVIEW.md §Independent Assessment under "Error Analysis":
- Number of FP and FN cases
- Top 3 features with highest z_diff in FP/FN subsets
- Calibration gap summary
- Recommendations (verbatim from tool output)

The Planner reads these recommendations in the next round to guide feature engineering.
```

- [ ] **Step 2: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git add runner/roles/reviewer.md
git commit -m "feat(roles): add error analysis tool to Reviewer Phase 1"
```

---

## Task 8: Run Full Test Suite

**Files:** None (validation only).

- [ ] **Step 1: Run all tests**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All existing tests PASS. All new tests PASS. No regressions.

- [ ] **Step 2: Run a quick smoke test of the template catalog**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -c "
from runner.strategy.templates import get_catalog
catalog = get_catalog()
print(f'Template catalog: {len(catalog)} entries')
for entry in catalog:
    print(f'  {entry[\"category\"]}/{entry[\"name\"]}: {entry[\"description\"][:60]}')
"
```

Expected: 8 entries printed with category/name/description.

- [ ] **Step 3: Run a quick smoke test of tree search**

```bash
cd /home/jupyter/Thinkubator/auto_train && python -c "
from runner.strategy.tree_search import ExperimentTree
tree = ExperimentTree()
tree.add_experiment('a', 'ROOT', 'A_model', 0.82, 'keep')
tree.add_experiment('b', 'a', 'A_hp', 0.84, 'keep')
tree.add_experiment('c', 'b', 'A_feature', 0.835, 'discard')
ctx = tree.get_planner_context(budget_total=20, budget_used=3, noise_floor=0.005)
import json
print(json.dumps(ctx, indent=2))
"
```

Expected: JSON output with phase='diversify', UCB1 scores (inf for untried classes), strategy stats.

- [ ] **Step 4: Final commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git log --oneline -6
```

Expected: 6 commits from this plan:
1. `feat(strategy): add validated ML code template library with tests`
2. `feat(tools): add systematic error analysis tool with FP/FN pattern detection`
3. `feat(strategy): add experiment tree with UCB1 exploration/exploitation scoring`
4. `feat(driver): integrate experiment tree into init_campaign and review_finalize`
5. `feat(tools): add temporal cross-validation with expanding window and gap support`
6. `feat(roles): add UCB1-guided strategy selection and template catalog to Planner`

---

## Verification Checklist

| Requirement | Task | Test |
|---|---|---|
| Validated code template library (like AutoKaggle) | Task 1 | `test_templates.py` — 10 tests |
| Group aggregation feature templates | Task 1 (included) | `TestGroupAggFeatures` — 2 tests |
| Systematic error analysis protocol | Task 2 | `test_error_analysis.py` — 7 tests |
| Tree search over solutions with UCB1 | Task 3 + 4 | `test_tree_search.py` — 13 tests + 4 driver integration tests |
| Temporal split validation | Task 5 | `test_temporal_cv.py` — 5 tests |
| Planner uses UCB1 scores | Task 6 | Role prompt update (manual verification) |
| Reviewer runs error analysis | Task 7 | Role prompt update (manual verification) |
