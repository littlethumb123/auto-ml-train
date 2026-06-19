"""Invariant: review_finalize overrides keep→discard when delta < noise_floor."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner import runner_driver
from tests.conftest import anchor_round_with_receipts as _anchor
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_keep_overridden_when_delta_below_noise_floor(campaign: Path):
    """GAP 7: If delta < noise_floor, reviewer 'keep' is mechanically overridden to 'discard'."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    _anchor(campaign, ["tools/anomaly.py"])  # round 1 anchor + writes

    # First experiment establishes a baseline
    res1 = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="baseline",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert res1["verdict"] == "keep"

    # Second experiment: improvement = 0.002, below noise_floor=0.005
    # Note: the driver flips this to discard; F2 still requires journal entry
    # for the discard. Re-anchor for round 2 — discard variant.
    _anchor(campaign, ["tools/anomaly.py"], verdict_for_writes="discard")
    res2 = runner_driver.review_finalize(
        verdict="keep",
        commit="c2",
        metrics={"val_pr_auc": 0.802, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="tiny improvement",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert res2["verdict"] == "discard"
    assert "noise_floor_gate" in res2.get("noise_floor_override", "")


def test_keep_allowed_when_delta_above_noise_floor(campaign: Path):
    """Keep should not be overridden when delta >= noise_floor."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    _anchor(campaign, ["tools/anomaly.py"])  # round 1

    res1 = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="baseline",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert res1["verdict"] == "keep"

    # Second experiment: improvement = 0.01, above noise_floor=0.005
    _anchor(campaign, ["tools/anomaly.py"])  # round 2 anchor + writes
    res2 = runner_driver.review_finalize(
        verdict="keep",
        commit="c2",
        metrics={"val_pr_auc": 0.81, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="real improvement",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert res2["verdict"] == "keep"
    assert "noise_floor_override" not in res2


def test_discard_verdict_not_touched_by_noise_floor(campaign: Path):
    """Noise-floor gate only overrides 'keep', never changes 'discard'."""
    runner_driver.init_campaign(campaign_dir=str(campaign))

    res = runner_driver.review_finalize(
        verdict="discard",
        commit="c1",
        metrics={"val_pr_auc": 0.50, "lift_at_10": 1.0, "macro_f1": 0.5, "val_f1": 0.4},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert res["verdict"] == "discard"
    assert "noise_floor_override" not in res


def test_first_experiment_keeps_without_noise_floor_gate(campaign: Path):
    """First experiment has no best_so_far, so noise-floor gate should not fire."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    _anchor(campaign, ["tools/anomaly.py"])

    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.50, "lift_at_10": 1.0, "macro_f1": 0.5, "val_f1": 0.4},
        action_type="A_hp",
        hypothesis="h",
        description="first experiment",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert res["verdict"] == "keep"
    assert "noise_floor_override" not in res
