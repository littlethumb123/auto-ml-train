"""Invariant: execute_finalize rejects commits that touch read-only paths."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

PLAN_NO_HELPERS = """---
schema_version: 1
campaign_id: "tiny"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "tighter range"
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
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_rejects_commit_touching_prepare_py(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(PLAN_NO_HELPERS)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py", "prepare.py"],
    )
    assert res["synthetic_verdict"] == "malformed"
    assert "prepare.py" in res.get("reason", "")


def test_rejects_commit_touching_contracts(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(PLAN_NO_HELPERS)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py", "runner/contracts/EVAL_PROTOCOL.md"],
    )
    assert res["synthetic_verdict"] == "malformed"


def test_accepts_commit_touching_only_train_py(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(PLAN_NO_HELPERS)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py"],
    )
    assert res["synthetic_verdict"] is None
    assert res["channel"] == "RUN_COMPLETE"


def test_accepts_declared_helpers(campaign: Path):
    plan_with_helpers = PLAN_NO_HELPERS.replace(
        "touches_helpers: false", "touches_helpers: true"
    ).replace(
        "helpers_declared: []",
        'helpers_declared: ["runner/experiment_helpers/abc123/custom.py"]',
    )
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(plan_with_helpers)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py", "runner/experiment_helpers/abc123/custom.py"],
    )
    assert res["synthetic_verdict"] is None


def test_no_diff_files_skips_check(campaign: Path):
    """Backward compat: when commit_diff_files is not provided, skip the check."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
    )
    assert res["channel"] == "RUN_COMPLETE"
    assert res["synthetic_verdict"] is None
