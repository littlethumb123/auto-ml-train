"""Tests for runner.tools.feature_selection."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from runner.tools.feature_selection import select_features


@pytest.fixture
def tiny_data():
    """Small dataset: 3 informative tabular features, 2 embedding noise features."""
    rng = np.random.default_rng(42)
    n = 500
    tab_cols = ["tab_signal_0", "tab_signal_1", "tab_signal_2", "tab_noise"]
    emb_cols = ["embedding_0", "embedding_1"]
    all_cols = tab_cols + emb_cols

    X = pd.DataFrame(rng.normal(size=(n, len(all_cols))), columns=all_cols)
    y = (X["tab_signal_0"] * 2 + X["tab_signal_1"] + rng.normal(scale=0.3, size=n) > 0).astype(int)

    X_train, X_val = X.iloc[:400], X.iloc[400:]
    y_train, y_val = y.iloc[:400], y.iloc[400:]
    return X_train, y_train, X_val, y_val, all_cols, emb_cols


def test_select_features_variance_returns_subset(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    result = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols, embedding_features=emb_cols,
        method="variance",
    )
    assert set(result["selected_features"]).issubset(set(feature_cols))
    assert result["n_selected"] + result["n_dropped"] == len(feature_cols)


def test_select_features_top_k_respected(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    result = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols, embedding_features=emb_cols,
        method="variance", top_k=3,
    )
    assert result["n_selected"] == 3
    assert len(result["selected_features"]) == 3


def test_select_features_permutation_returns_subset(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    result = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols, embedding_features=emb_cols,
        method="permutation",
    )
    assert set(result["selected_features"]).issubset(set(feature_cols))


def test_select_features_permutation_top_k(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    result = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols, embedding_features=emb_cols,
        method="permutation", top_k=2,
    )
    assert result["n_selected"] == 2


def test_select_features_importances_nonnegative(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    result = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols, embedding_features=emb_cols,
        method="permutation",
    )
    for score in result["importances"].values():
        assert score >= 0.0


def test_select_features_embedding_count_in_output(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    result = select_features(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols, embedding_features=emb_cols,
        method="variance",
    )
    actual_emb_sel = sum(1 for f in result["selected_features"] if f.startswith("embedding_"))
    assert result["n_embedding_selected"] == actual_emb_sel


def test_select_features_invalid_method_raises(tiny_data):
    X_train, y_train, X_val, y_val, feature_cols, emb_cols = tiny_data
    with pytest.raises(ValueError, match="method"):
        select_features(
            X_train, y_train, X_val, y_val,
            feature_cols=feature_cols, embedding_features=emb_cols,
            method="unknown_method",
        )
