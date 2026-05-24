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
