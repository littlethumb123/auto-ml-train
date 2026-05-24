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
