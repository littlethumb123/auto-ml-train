"""Integration tests for the orchestrator CLI stage-call chain.

Validates that the orchestrator's bash-invocable pipeline
(runner_driver + runner.orchestrator helpers) chains correctly.
No LLM calls — just deterministic driver + helper validation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from runner.orchestrator import (
    detect_stuck,
    determine_resume_phase,
    format_round_digest,
    infer_tools_ran,
    parse_metrics_from_log,
)
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.integration

VALID_NEXT_EXPERIMENT = """---
schema_version: 1
campaign_id: "tiny"
round: 1
planner_invocation_at: "2026-05-25T00:00:00Z"
action_type: "A_hp"
hypothesis: "tune learning rate"
expected_effect_size: 0.01
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary
First round.
## 2. Evidence from memory
None yet.
## 3. Plan
1. Set lr=0.01.
## 4. Helpers
None.
## 5. How this differs from prior experiments
First experiment.
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


# ── Test 1: Full round driver chain ──────────────────────────────────

def test_full_round_driver_chain(campaign: Path):
    """Simulate one full orchestrator round: init → status → historian check
    → stuck check → plan_check → execute_finalize → review_finalize → final status.
    """
    cd = str(campaign)

    # 1. Init
    runner_driver.init_campaign(campaign_dir=cd)

    # 2. Status: round=0, uninitialized-like state
    status = runner_driver.get_campaign_status(campaign_dir=cd)
    assert status["round"] == 0
    assert status["best_metric"] is None

    # 3. Historian check — should be False at start
    assert runner_driver.should_run_historian(campaign_dir=cd) is False

    # 4. Stuck check — no results yet, no warnings
    warnings = detect_stuck(campaign / "")
    assert warnings == []  # results.tsv has only header

    # 5. Write plan and plan_check
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(VALID_NEXT_EXPERIMENT)
    check = runner_driver.plan_check(campaign_dir=cd)
    assert check["status"] == "ok", check["errors"]

    # 5b. Emit receipts for the mandatory tools (F3 contract) and simulate
    # the Reviewer's required writes (F2 contract).
    import json as _json
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state_now = _json.loads(state_path.read_text())
    anchor_now = state_now["round_started_at"]
    new_round = int(state_now.get("round", 0)) + 1
    events = campaign / "state" / "driver_events.jsonl"
    rec = {
        "ts": anchor_now, "event": "tool_run", "name": "runner.tools.anomaly",
        "start_ts": anchor_now, "end_ts": anchor_now, "exit_code": 0,
        "args_hash": "0" * 16, "round": int(state_now.get("round", 0)),
        "campaign_dir": str(campaign),
    }
    with open(events, "a") as f:
        f.write(_json.dumps(rec, sort_keys=True) + "\n")
    from tests.conftest import simulate_reviewer_writes
    simulate_reviewer_writes(campaign, new_round=new_round, verdict="keep")

    # 6. Execute finalize
    exec_result = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: commit1\n",
        campaign_dir=cd,
    )
    assert exec_result["channel"] == "RUN_COMPLETE"
    assert exec_result["commit"] == "commit1"

    # 7. Review finalize
    metrics = {"val_pr_auc": 0.75, "lift_at_10": 4.5, "macro_f1": 0.72, "val_f1": 0.65}
    review_result = runner_driver.review_finalize(
        verdict="keep",
        commit="commit1",
        metrics=metrics,
        action_type="A_hp",
        hypothesis="tune learning rate",
        description="set lr=0.01",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=cd,
        tools_ran=["tools/anomaly.py"],
    )
    assert review_result["halt_loop"] is False
    assert review_result["should_rollback"] is False

    # 8. Final status: round=1, best_metric=0.75
    final_status = runner_driver.get_campaign_status(campaign_dir=cd)
    assert final_status["round"] == 1
    assert final_status["best_metric"] == 0.75
    assert final_status["last_verdict"] == "keep"


# ── Test 2: Stuck detection feeds into planning ──────────────────────

def test_stuck_detection_feeds_into_planning(campaign: Path):
    """Init campaign, populate results.tsv with 4 rows all A_hp,
    verify detect_stuck returns warnings mentioning 'A_hp'.
    """
    cd = str(campaign)
    runner_driver.init_campaign(campaign_dir=cd)

    # Simulate 4 consecutive A_hp experiments via review_finalize
    for i in range(1, 5):
        runner_driver.review_finalize(
            verdict="discard",
            commit=f"commit{i}",
            metrics={"val_pr_auc": 0.60, "lift_at_10": 3.0, "macro_f1": 0.55, "val_f1": 0.50},
            action_type="A_hp",
            hypothesis=f"hp tune {i}",
            description=f"attempt {i}",
            model_family="lightgbm",
            n_features=10,
            campaign_dir=cd,
            tools_ran=[],
        )

    warnings = detect_stuck(campaign)
    assert len(warnings) >= 1
    assert any("A_hp" in w for w in warnings)


# ── Test 3: Resume phase detection ───────────────────────────────────

def test_resume_phase_detection(campaign: Path):
    """Test all 4 resume scenarios."""
    cd = str(campaign)
    runner_driver.init_campaign(campaign_dir=cd)
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"

    # ── Scenario A: No artifacts → planner
    state = json.loads(state_path.read_text())
    phase = determine_resume_phase(campaign, state)
    assert phase == "planner"

    # ── Scenario B: NEXT_EXPERIMENT.md exists → executor
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(VALID_NEXT_EXPERIMENT)
    phase = determine_resume_phase(campaign, state)
    assert phase == "executor"

    # Clean up NEXT_EXPERIMENT.md for next scenario
    (campaign / "state" / "NEXT_EXPERIMENT.md").unlink()

    # ── Scenario C: run.log with sentinel → reviewer
    (campaign / "run.log").write_text("training...\nRUN_COMPLETE: abc123\n")
    phase = determine_resume_phase(campaign, state)
    assert phase == "reviewer"

    # Clean up run.log
    (campaign / "run.log").unlink()

    # ── Scenario D: Journal entry exists + historian_trigger_pending → historian
    state["round"] = 1
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2))
    (campaign / "state" / "CAMPAIGN_JOURNAL.md").write_text("## Round 1\nKeep.\n")
    phase = determine_resume_phase(campaign, state)
    assert phase == "historian"

    # ── Scenario E: Journal entry exists + no trigger → next_round
    state["historian_trigger_pending"] = False
    state_path.write_text(json.dumps(state, indent=2))
    phase = determine_resume_phase(campaign, state)
    assert phase == "next_round"


# ── Test 4: Metrics parsing and tools inference ──────────────────────

def test_metrics_parsing_and_tools_inference(tmp_path: Path):
    """Verify infer_tools_ran and parse_metrics_from_log work as called
    from the orchestrator prompt.
    """
    # ── parse_metrics_from_log: val_<metric> lines
    log_file = tmp_path / "run.log"
    log_file.write_text(
        "epoch 1 done\n"
        "val_pr_auc: 0.812\n"
        "val_f1: 0.73\n"
        "val_loss: 0.321\n"
        "---\n"
        "lift_at_10: 5.2\n"
        "macro_f1: 0.68\n"
        "---\n"
        "RUN_COMPLETE: abc123\n"
    )
    metrics = parse_metrics_from_log(log_file)
    assert metrics["val_pr_auc"] == pytest.approx(0.812)
    assert metrics["val_f1"] == pytest.approx(0.73)
    assert metrics["val_loss"] == pytest.approx(0.321)
    assert metrics["lift_at_10"] == pytest.approx(5.2)
    assert metrics["macro_f1"] == pytest.approx(0.68)

    # ── parse_metrics_from_log: missing file returns empty
    missing = parse_metrics_from_log(tmp_path / "nonexistent.log")
    assert missing == {}

    # ── infer_tools_ran: keyword matching
    reviewer_text = (
        "I ran the anomaly detection tool and checked the confusion matrix. "
        "The calibration curve looks good. Bootstrap CI was not needed."
    )
    tools = infer_tools_ran(reviewer_text)
    assert "runner.tools.anomaly" in tools
    assert "runner.tools.confusion_matrix" in tools
    assert "runner.tools.calibration" in tools
    assert "runner.tools.bootstrap_ci" in tools

    # ── infer_tools_ran: empty text → no tools
    assert infer_tools_ran("") == []

    # ── format_round_digest: verify compact format
    digest = format_round_digest(
        round_num=3,
        verdict="keep",
        action_type="A_model",
        hypothesis="switch to catboost",
        primary_metric_value=0.8123,
        primary_metric_name="val_pr_auc",
    )
    assert "Round 3" in digest
    assert "keep" in digest
    assert "A_model" in digest
    assert "0.8123" in digest
