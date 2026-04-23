"""Invariant: review_finalize advises C3 when target_gap <= 2*bootstrap_se."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

PROBLEM_WITH_TARGET = PROBLEM_CONTRACT.replace(
    'success_criteria: ["val_pr_auc >= 0.5"]',
    'success_criteria: ["val_pr_auc >= 0.85"]',
)


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_WITH_TARGET)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_c3_advisory_emitted_when_gap_within_noise(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.844, "lift_at_10": 9.0, "macro_f1": 0.9, "val_f1": 0.8},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="xgboost",
        n_features=30,
        campaign_dir=str(campaign),
    )
    res = runner_driver.review_finalize(
        verdict="discard",
        commit="c2",
        metrics={"val_pr_auc": 0.840, "lift_at_10": 8.0, "macro_f1": 0.88, "val_f1": 0.78},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="xgboost",
        n_features=30,
        campaign_dir=str(campaign),
        bootstrap_se=0.035,
    )
    assert res.get("c3_advisory") is True
    reason = (res.get("c3_advisory_reason") or "").lower()
    assert "measurement" in reason or "cv" in reason


def test_no_c3_advisory_when_gap_large(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.60, "lift_at_10": 3.0, "macro_f1": 0.6, "val_f1": 0.5},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="logreg",
        n_features=30,
        campaign_dir=str(campaign),
    )
    res = runner_driver.review_finalize(
        verdict="discard",
        commit="c2",
        metrics={"val_pr_auc": 0.55, "lift_at_10": 2.0, "macro_f1": 0.5, "val_f1": 0.4},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="logreg",
        n_features=30,
        campaign_dir=str(campaign),
        bootstrap_se=0.035,
    )
    assert res.get("c3_advisory") is not True


def test_no_c3_advisory_when_se_not_provided(campaign: Path):
    """Backward compat: when bootstrap_se is omitted, no advisory."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.844, "lift_at_10": 9.0, "macro_f1": 0.9, "val_f1": 0.8},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="xgboost",
        n_features=30,
        campaign_dir=str(campaign),
    )
    res = runner_driver.review_finalize(
        verdict="discard",
        commit="c2",
        metrics={"val_pr_auc": 0.840, "lift_at_10": 8.0, "macro_f1": 0.88, "val_f1": 0.78},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="xgboost",
        n_features=30,
        campaign_dir=str(campaign),
    )
    assert res.get("c3_advisory") is not True
