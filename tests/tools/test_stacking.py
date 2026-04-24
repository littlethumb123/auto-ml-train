"""Tests for runner.tools.stacking."""
from __future__ import annotations

import numpy as np
import pytest

from runner.tools.stacking import fit_stack, predict_stack, stack_and_evaluate


@pytest.fixture
def binary_preds():
    """Two base model prediction arrays + binary labels."""
    rng = np.random.default_rng(7)
    n = 200
    y = rng.integers(0, 2, size=n)
    p1 = np.clip(y * 0.7 + rng.normal(scale=0.2, size=n), 0.01, 0.99)
    p2 = np.clip(y * 0.6 + rng.normal(scale=0.3, size=n), 0.01, 0.99)
    return [p1, p2], y


def test_fit_stack_mean_no_meta_model(binary_preds):
    base_preds, y = binary_preds
    result = fit_stack(base_preds, y, method="mean")
    assert result["meta_model"] is None
    assert result["method"] == "mean"
    assert len(result["weights"]) == len(base_preds)


def test_fit_stack_logistic_has_meta_model(binary_preds):
    base_preds, y = binary_preds
    result = fit_stack(base_preds, y, method="logistic")
    assert result["meta_model"] is not None
    assert result["method"] == "logistic"


def test_fit_stack_ridge_has_meta_model(binary_preds):
    base_preds, y = binary_preds
    result = fit_stack(base_preds, y, method="ridge")
    assert result["meta_model"] is not None


def test_predict_stack_mean_is_average(binary_preds):
    base_preds, y = binary_preds
    stacked = predict_stack(None, base_preds, method="mean")
    expected = np.mean(base_preds, axis=0)
    np.testing.assert_allclose(stacked, expected)


def test_predict_stack_logistic_in_zero_one(binary_preds):
    base_preds, y = binary_preds
    result = fit_stack(base_preds, y, method="logistic")
    stacked = predict_stack(result["meta_model"], base_preds, method="logistic")
    assert np.all(stacked >= 0.0) and np.all(stacked <= 1.0)


def test_predict_stack_ridge_in_zero_one(binary_preds):
    base_preds, y = binary_preds
    result = fit_stack(base_preds, y, method="ridge")
    stacked = predict_stack(result["meta_model"], base_preds, method="ridge")
    assert np.all(stacked >= 0.0) and np.all(stacked <= 1.0)


def test_stack_and_evaluate_returns_eval_metrics(binary_preds):
    base_preds, y = binary_preds
    # Use same data for meta and eval (not realistic — just tests the interface)
    result = stack_and_evaluate(base_preds, y, base_preds, y, method="logistic")
    assert "eval_metrics" in result
    assert "lift_1pct" in result["eval_metrics"]
    assert "auc_roc" in result["eval_metrics"]
    assert result["eval_metrics"]["auc_roc"] > 0.5   # should beat random on this data


def test_stack_and_evaluate_base_metrics_present(binary_preds):
    base_preds, y = binary_preds
    result = stack_and_evaluate(
        base_preds, y, base_preds, y,
        method="mean", model_names=["model_a", "model_b"],
    )
    assert "model_a" in result["base_model_eval_metrics"]
    assert "model_b" in result["base_model_eval_metrics"]


def test_fit_stack_invalid_method_raises(binary_preds):
    base_preds, y = binary_preds
    with pytest.raises(ValueError, match="method"):
        fit_stack(base_preds, y, method="unknown")


def test_meta_train_metrics_present(binary_preds):
    base_preds, y = binary_preds
    result = fit_stack(base_preds, y, method="logistic")
    assert "meta_train_metrics" in result
    assert "auc_roc" in result["meta_train_metrics"]
