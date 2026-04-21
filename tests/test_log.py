"""Unit tests for log.py — results.tsv append + CAMPAIGN_STATE.json update."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import log

RESULTS_HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text(RESULTS_HEADER)
    (root / "state" / "CAMPAIGN_STATE.json").write_text(json.dumps({
        "$schema_version": 1,
        "campaign_id": "tiny",
        "round": 0,
        "exp_id_counter": 0,
        "last_commit": None,
        "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0,
        "budget_used": 0,
        "budget_total": 5,
        "created_at": "2026-04-21T12:00:00Z",
        "updated_at": "2026-04-21T12:00:00Z",
    }))
    return root


def test_append_result_keep_updates_best_and_resets_discards(campaign: Path):
    log.append_result(
        commit="abc123",
        metrics={"val_pr_auc": 0.71, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        status="keep",
        action_type="A_model",
        hypothesis="try lightgbm",
        description="baseline LGBM",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc",
        direction="maximize",
    )
    lines = (campaign / "state" / "results.tsv").read_text().splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("abc123\t0.71\t5.0\t0.8\t0.7\tkeep")
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["round"] == 1
    assert state["last_commit"] == "abc123"
    assert state["last_verdict"] == "keep"
    assert state["best_so_far"]["primary_metric"] == 0.71
    assert state["best_so_far"]["commit"] == "abc123"
    assert state["consecutive_discards"] == 0
    assert state["budget_used"] == 1


def test_append_result_discard_increments_consecutive(campaign: Path):
    log.append_result(
        commit="aaa",
        metrics={"val_pr_auc": 0.6, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.5},
        status="keep",
        action_type="A_model", hypothesis="h", description="d",
        model_family="xgboost", n_features=8,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="maximize",
    )
    log.append_result(
        commit="bbb",
        metrics={"val_pr_auc": 0.55, "lift_at_10": 3.0, "macro_f1": 0.6, "val_f1": 0.4},
        status="discard",
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=8,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="maximize",
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 1
    assert state["best_so_far"]["primary_metric"] == 0.6
    assert state["round"] == 2


def test_append_result_anomaly_does_not_bump_discards(campaign: Path):
    log.append_result(
        commit="xyz",
        metrics={"val_pr_auc": 0.3, "lift_at_10": 2.0, "macro_f1": 0.4, "val_f1": 0.2},
        status="anomaly",
        action_type="A_diagnose", hypothesis="h", description="d",
        model_family="lightgbm", n_features=8,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="maximize",
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0
    assert state["last_verdict"] == "anomaly"


def test_append_result_minimize_direction(campaign: Path):
    log.append_result(
        commit="m1",
        metrics={"val_pr_auc": 0.20, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        status="keep",
        action_type="A_model", hypothesis="h", description="d",
        model_family="other", n_features=5,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="minimize",
    )
    log.append_result(
        commit="m2",
        metrics={"val_pr_auc": 0.30, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        status="keep",
        action_type="A_model", hypothesis="h", description="d",
        model_family="other", n_features=5,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="minimize",
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["best_so_far"]["commit"] == "m1"
    assert state["best_so_far"]["primary_metric"] == 0.20
