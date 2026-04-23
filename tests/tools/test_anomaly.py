from __future__ import annotations

import pytest

from runner.tools import anomaly


def test_anomaly_fires_below_floor():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.40, "status": "keep", "model_family": "lgb"},
        history=[],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is True
    assert "below" in res["reason"].lower()


def test_anomaly_fires_relative_to_best():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.30, "status": "keep", "model_family": "lgb"},
        history=[{"val_pr_auc": 0.80, "status": "keep"}],
        floor=0.10,
        primary_metric="val_pr_auc",
        relative=0.5,
    )
    assert res["fired"] is True


def test_anomaly_does_not_fire_when_good():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.85, "status": "keep", "model_family": "xgb"},
        history=[{"val_pr_auc": 0.80, "status": "keep"}],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is False


def test_anomaly_skips_crash_rows():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.0, "status": "crash", "model_family": "lgb"},
        history=[],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is False
    assert "crash" in res["reason"].lower()


def test_anomaly_determinism():
    args = dict(
        latest_row={"val_pr_auc": 0.40, "status": "keep", "model_family": "lgb"},
        history=[],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert anomaly.check_anomaly(**args) == anomaly.check_anomaly(**args)
