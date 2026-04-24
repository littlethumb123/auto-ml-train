"""Tests for runner.tools.shap_report."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from runner.tools.shap_report import shap_report


@pytest.fixture
def tiny_model_and_data():
    """Logistic regression on tiny dataset — fast, no tree model needed."""
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(0)
    n, n_tab, n_emb = 300, 5, 3
    tab_cols = [f"tab_{i}" for i in range(n_tab)]
    emb_cols = [f"embedding_{i}" for i in range(n_emb)]
    feature_cols = tab_cols + emb_cols

    X = pd.DataFrame(rng.normal(size=(n, n_tab + n_emb)), columns=feature_cols)
    y = (X["tab_0"] + X["embedding_0"] + rng.normal(scale=0.5, size=n) > 0).astype(int)

    model = LogisticRegression(random_state=0)
    model.fit(X, y)
    return model, X, feature_cols, emb_cols


def test_shap_report_keys(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[5], max_samples=200)
    assert set(result.keys()) >= {
        "model_name", "shap_summary", "proportion_by_k",
        "n_features", "n_embedding_features", "n_tabular_features", "n_samples_used",
    }


def test_shap_report_summary_length(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[5], max_samples=200)
    assert len(result["shap_summary"]) == len(feature_cols)


def test_shap_report_ranks_are_unique_and_ordered(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[5], max_samples=200)
    ranks = [r["rank"] for r in result["shap_summary"]]
    assert ranks == list(range(1, len(feature_cols) + 1))
    shaps = [r["mean_abs_shap"] for r in result["shap_summary"]]
    assert shaps == sorted(shaps, reverse=True)


def test_shap_report_proportion_sums_to_one(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[5], max_samples=200)
    for row in result["proportion_by_k"]:
        assert abs(row["prop_embedding"] + row["prop_tabular"] - 1.0) < 1e-9


def test_shap_report_embedding_count(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[5], max_samples=200)
    assert result["n_embedding_features"] == len(emb_cols)
    assert result["n_tabular_features"] == len(feature_cols) - len(emb_cols)


def test_shap_report_max_samples_respected(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[3], max_samples=50)
    assert result["n_samples_used"] <= 50


def test_shap_report_is_embedding_flag(tiny_model_and_data):
    model, X, feature_cols, emb_cols = tiny_model_and_data
    emb_set = set(emb_cols)
    result = shap_report(model, X, feature_cols, emb_cols, top_k_list=[3], max_samples=200)
    for row in result["shap_summary"]:
        assert row["is_embedding"] == (row["feature"] in emb_set)
