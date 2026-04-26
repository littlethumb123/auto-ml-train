"""Safety invariant: consecutive_discards >= plateau_trigger sets historian_trigger_pending.

Replaces tests/safety/test_diagnose_after_c2.py (the c2_pending_diagnose → A_diagnose protocol
is removed; the Historian now handles C2 plateau synthesis).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

EVAL_WITH_HISTORIAN = EVAL_PROTOCOL.replace(
    "approved_at:", "historian_interval: 5\napproved_at:"
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
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_HISTORIAN)
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


def test_three_discards_set_historian_trigger(campaign_at_plateau: Path):
    state = json.loads((campaign_at_plateau / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["historian_trigger_pending"] is True
    assert "c2_pending_diagnose" not in state


def test_historian_finalize_c2_resets_consecutive_discards(campaign_at_plateau: Path):
    runner_driver.historian_finalize(
        campaign_dir=str(campaign_at_plateau),
        trigger="c2",
        tokens_used=0,
    )
    state = json.loads((campaign_at_plateau / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0
    assert state["historian_trigger_pending"] is False


def test_plan_check_does_not_require_diagnose_after_c2(campaign_at_plateau: Path):
    """Old protocol forced A_diagnose after C2 resolve. New protocol allows any valid action."""
    runner_driver.historian_finalize(
        campaign_dir=str(campaign_at_plateau),
        trigger="c2",
    )
    # A_model should be accepted — no forced A_diagnose gate
    (campaign_at_plateau / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_model", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(campaign_at_plateau))
    assert res["status"] == "ok", res["errors"]


def test_plan_check_no_longer_enforces_c2_escalation_on_discards(campaign_at_plateau: Path):
    """Old protocol required escalation: C2 when consecutive_discards >= 3.
    New protocol does not enforce this — historian_trigger_pending handles it."""
    # Write a plan WITHOUT escalation: C2 even though consecutive_discards >= 3
    (campaign_at_plateau / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_hp", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(campaign_at_plateau))
    # Should NOT get an error about missing C2 escalation
    assert not any("C2" in e and "consecutive_discards" in e for e in res.get("errors", []))


def test_resolve_c2_manual_override_sets_historian_trigger(campaign_at_plateau: Path):
    """resolve_c2 is kept for manual override and now sets historian_trigger_pending."""
    runner_driver.resolve_c2(
        resolution="switching strategy",
        campaign_dir=str(campaign_at_plateau),
    )
    state = json.loads((campaign_at_plateau / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0
    assert state.get("historian_trigger_pending") is True
    assert "c2_pending_diagnose" not in state
