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
