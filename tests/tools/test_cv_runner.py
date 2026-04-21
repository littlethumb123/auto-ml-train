from __future__ import annotations

import pytest
from sklearn.linear_model import LogisticRegression

from runner.tools import cv_runner
from tests.fixtures.tiny_dataset import make_tiny_binary


def _factory():
    return LogisticRegression(max_iter=500, solver="liblinear", class_weight="balanced")


def test_cv_runner_stratified_kfold_has_positives_per_fold():
    X, y = make_tiny_binary()
    result = cv_runner.cv_runner(
        estimator_factory=_factory,
        X=X, y=y,
        scheme="stratified_kfold",
        n_splits=5,
        primary_metric="pr_auc",
        random_state=42,
    )
    assert len(result["fold_scores"]) == 5
    assert all(0.0 <= s <= 1.0 for s in result["fold_scores"])
    assert "mean" in result and "std" in result and "ci95" in result


def test_cv_runner_invalid_scheme_raises():
    X, y = make_tiny_binary()
    with pytest.raises(ValueError):
        cv_runner.cv_runner(
            estimator_factory=_factory,
            X=X, y=y,
            scheme="not_a_real_scheme",
            n_splits=3,
            primary_metric="pr_auc",
            random_state=42,
        )


def test_cv_runner_determinism():
    X, y = make_tiny_binary()
    r1 = cv_runner.cv_runner(_factory, X, y, "stratified_kfold", 3, "pr_auc", 42)
    r2 = cv_runner.cv_runner(_factory, X, y, "stratified_kfold", 3, "pr_auc", 42)
    assert r1["fold_scores"] == r2["fold_scores"]
