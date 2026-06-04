"""Tests for runner/tools/reproduce_check.py."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import numpy as np
import pytest
from runner.tools.reproduce_check import (
    reproduce_check,
    _parse_reported_metrics,
    _recompute_metrics,
    _validate_predictions,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def prediction_artifacts(tmp_path):
    """Create realistic prediction arrays."""
    rng = np.random.RandomState(42)
    n = 1000
    y_true = (rng.rand(n) > 0.9).astype(float)  # ~10% positive rate
    y_prob = np.clip(y_true * 0.7 + rng.rand(n) * 0.3, 0, 1)

    true_path = tmp_path / "y_val_true.npy"
    prob_path = tmp_path / "y_val_prob.npy"
    np.save(true_path, y_true)
    np.save(prob_path, y_prob)
    return true_path, prob_path, y_true, y_prob


@pytest.fixture
def run_log_matching(tmp_path, prediction_artifacts):
    """Create a run.log with metrics matching the prediction artifacts."""
    _, _, y_true, y_prob = prediction_artifacts
    metrics = _recompute_metrics(y_true, y_prob)
    lines = [f"{k}: {v:.6f}" for k, v in metrics.items()]
    log_path = tmp_path / "run.log"
    log_path.write_text("\n".join(lines) + "\n")
    return log_path


@pytest.fixture
def run_log_mismatched(tmp_path):
    """Create a run.log with fabricated metrics."""
    log_path = tmp_path / "run.log"
    log_path.write_text(textwrap.dedent("""\
        val_auc_pr: 0.999999
        val_auc_roc: 0.999999
        val_lift_10pct: 50.0
    """))
    return log_path


# ── Parse reported metrics ────────────────────────────────────────────

class TestParseReportedMetrics:
    def test_basic_parsing(self):
        text = "val_auc_pr: 0.85\nval_lift_10pct: 3.5\n"
        result = _parse_reported_metrics(text)
        assert result["val_auc_pr"] == pytest.approx(0.85)
        assert result["val_lift_10pct"] == pytest.approx(3.5)

    def test_ignores_non_metric_lines(self):
        text = "epoch 10 done\nval_auc_pr: 0.85\nTraining complete\n"
        result = _parse_reported_metrics(text)
        assert len(result) == 1
        assert "val_auc_pr" in result


# ── Prediction validation ────────────────────────────────────────────

class TestValidatePredictions:
    def test_valid_predictions(self, prediction_artifacts):
        _, _, y_true, y_prob = prediction_artifacts
        issues = _validate_predictions(y_true, y_prob)
        assert issues == []

    def test_shape_mismatch(self):
        issues = _validate_predictions(np.array([1, 0]), np.array([0.5]))
        assert any("shape" in i.lower() for i in issues)

    def test_nan_detected(self):
        y_true = np.array([1, 0, 1])
        y_prob = np.array([0.5, float("nan"), 0.8])
        issues = _validate_predictions(y_true, y_prob)
        assert any("nan" in i.lower() for i in issues)

    def test_out_of_range(self):
        y_true = np.array([1, 0])
        y_prob = np.array([1.5, -0.1])
        issues = _validate_predictions(y_true, y_prob)
        assert any("out of" in i.lower() for i in issues)

    def test_near_constant(self):
        y_true = np.array([1, 0, 1])
        y_prob = np.array([0.5, 0.5, 0.5])
        issues = _validate_predictions(y_true, y_prob)
        assert any("constant" in i.lower() for i in issues)

    def test_no_positives(self):
        y_true = np.zeros(10)
        y_prob = np.random.rand(10)
        issues = _validate_predictions(y_true, y_prob)
        assert any("0 positive" in i.lower() for i in issues)


# ── Full reproduce check ─────────────────────────────────────────────

class TestReproduceCheck:
    def test_matching_metrics_pass(self, prediction_artifacts, run_log_matching):
        true_path, prob_path, _, _ = prediction_artifacts
        result = reproduce_check(true_path, prob_path, run_log_matching, tolerance=0.001)
        assert result["artifacts_valid"] is True
        assert result["passed"] is True
        assert result["mismatches"] == []

    def test_mismatched_metrics_fail(self, prediction_artifacts, run_log_mismatched):
        true_path, prob_path, _, _ = prediction_artifacts
        result = reproduce_check(true_path, prob_path, run_log_mismatched, tolerance=0.001)
        assert result["artifacts_valid"] is True
        assert result["passed"] is False
        assert len(result["mismatches"]) > 0

    def test_no_run_log_still_passes(self, prediction_artifacts):
        true_path, prob_path, _, _ = prediction_artifacts
        result = reproduce_check(true_path, prob_path, run_log_path=None)
        assert result["artifacts_valid"] is True
        assert result["passed"] is True

    def test_invalid_artifacts_fail(self, tmp_path):
        y_true = np.zeros(10)  # 0 positives
        y_prob = np.random.rand(10)
        true_path = tmp_path / "y_true.npy"
        prob_path = tmp_path / "y_prob.npy"
        np.save(true_path, y_true)
        np.save(prob_path, y_prob)

        result = reproduce_check(true_path, prob_path)
        assert result["artifacts_valid"] is False
        assert result["passed"] is False


# ── CLI main ──────────────────────────────────────────────────────────

class TestMain:
    def test_main_pass(self, prediction_artifacts, run_log_matching):
        from runner.tools.reproduce_check import main
        true_path, prob_path, _, _ = prediction_artifacts
        rc = main([
            "--y-true", str(true_path),
            "--y-prob", str(prob_path),
            "--run-log", str(run_log_matching),
            "--json",
        ])
        assert rc == 0

    def test_main_fail(self, prediction_artifacts, run_log_mismatched):
        from runner.tools.reproduce_check import main
        true_path, prob_path, _, _ = prediction_artifacts
        rc = main([
            "--y-true", str(true_path),
            "--y-prob", str(prob_path),
            "--run-log", str(run_log_mismatched),
            "--json",
        ])
        assert rc == 1
