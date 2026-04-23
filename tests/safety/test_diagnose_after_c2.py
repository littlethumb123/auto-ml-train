"""Invariant: after C2 resolve, the next plan must be A_diagnose."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

EVAL_WITH_DIAG_ACTIONS = EVAL_PROTOCOL.replace(
    'action_types: ["A_hp", "A_model"]',
    'action_types: ["A_hp", "A_model", "A_diagnose", "A_ensemble"]',
)


def _make_plan(action_type: str = "A_hp", round_n: int = 4) -> str:
    return f"""---
schema_version: 1
campaign_id: "tiny"
round: {round_n}
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "{action_type}"
hypothesis: "test hypothesis"
expected_effect_size: 0.001
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
1. noop.
## 4. Helpers
None.
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)
N/A.
"""


@pytest.fixture
def campaign_at_plateau(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_DIAG_ACTIONS)
    runner_driver.init_campaign(campaign_dir=str(root))

    for i in range(3):
        runner_driver.review_finalize(
            verdict="discard",
            commit=f"d{i}",
            metrics={"val_pr_auc": 0.4, "lift_at_10": 0, "macro_f1": 0, "val_f1": 0},
            action_type="A_hp",
            hypothesis="h",
            description="d",
            model_family="lightgbm",
            n_features=10,
            campaign_dir=str(root),
        )
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 3
    return root


def test_plan_check_rejects_non_diagnose_after_c2_resolve(campaign_at_plateau: Path):
    root = campaign_at_plateau
    runner_driver.resolve_c2(
        resolution="switching strategy",
        campaign_dir=str(root),
    )
    (root / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_ensemble", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(root))
    assert res["status"] == "malformed"
    assert any("A_diagnose" in e for e in res["errors"])


def test_plan_check_accepts_diagnose_after_c2_resolve(campaign_at_plateau: Path):
    root = campaign_at_plateau
    runner_driver.resolve_c2(
        resolution="switching strategy",
        campaign_dir=str(root),
    )
    (root / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_diagnose", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(root))
    assert res["status"] == "ok"


def test_c2_pending_cleared_after_diagnose_round(campaign_at_plateau: Path):
    root = campaign_at_plateau
    runner_driver.resolve_c2(
        resolution="switching strategy",
        campaign_dir=str(root),
    )
    runner_driver.review_finalize(
        verdict="discard",
        commit="diag1",
        metrics={"val_pr_auc": 0.4, "lift_at_10": 0, "macro_f1": 0, "val_f1": 0},
        action_type="A_diagnose",
        hypothesis="diagnose",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(root),
    )
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state.get("c2_pending_diagnose") is not True

    (root / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_model", round_n=5)
    )
    res = runner_driver.plan_check(campaign_dir=str(root))
    assert res["status"] == "ok"
