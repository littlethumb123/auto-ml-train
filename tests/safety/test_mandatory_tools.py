"""Invariant: review_finalize rejects keep when mandatory tools are missing."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

EVAL_WITH_MANDATORY = EVAL_PROTOCOL.replace(
    'mandatory_tools: ["tools/anomaly.py"]',
    'mandatory_tools: ["runner.tools.anomaly", "runner.tools.bootstrap_ci"]',
)


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_MANDATORY)
    return root


def test_keep_rejected_when_mandatory_tool_missing(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["runner.tools.anomaly"],  # missing bootstrap_ci
    )
    assert res["verdict"] == "malformed"
    assert "mandatory_tools" in res.get("halt_reason", "") or res["verdict"] == "malformed"


def test_keep_accepted_when_all_mandatory_tools_present(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["runner.tools.anomaly", "runner.tools.bootstrap_ci"],
    )
    assert res["verdict"] == "keep"


def test_keep_accepts_normalized_path_style_tools_ran(campaign: Path):
    """Contract lists dotted modules; tools_ran may use tools/*.py paths."""
    eval_mixed = EVAL_WITH_MANDATORY.replace(
        'mandatory_tools: ["runner.tools.anomaly", "runner.tools.bootstrap_ci"]',
        'mandatory_tools: ["tools/anomaly.py", "runner.tools.bootstrap_ci"]',
    )
    (campaign / "contracts" / "EVAL_PROTOCOL.md").write_text(eval_mixed)
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py", "runner/tools/bootstrap_ci.py"],
    )
    assert res["verdict"] == "keep"


def test_discard_not_overridden_when_tools_missing(campaign: Path):
    """Discard/crash/malformed verdicts are not upgraded to malformed by missing tools."""
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
        tools_ran=[],
    )
    assert res["verdict"] == "discard"


def test_tools_ran_defaults_to_none_for_backward_compat(campaign: Path):
    """Callers that omit tools_ran don't break (backward compat)."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        # tools_ran intentionally omitted
    )
    # When tools_ran is None, the driver cannot verify → should pass through unchanged
    assert res["verdict"] == "keep"
