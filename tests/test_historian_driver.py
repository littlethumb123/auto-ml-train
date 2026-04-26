"""Tests for historian_run() and historian_finalize() in runner_driver."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

EVAL_WITH_HISTORIAN_INTERVAL = EVAL_PROTOCOL.replace(
    "approved_at:", "historian_interval: 5\napproved_at:"
)


@pytest.fixture
def campaign_v2(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_HISTORIAN_INTERVAL)
    runner_driver.init_campaign(campaign_dir=str(root))
    return root


@pytest.fixture
def campaign_v1(tmp_path: Path) -> Path:
    """Campaign with manually-written v1 state (simulates pre-upgrade campaign)."""
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_HISTORIAN_INTERVAL)
    v1_state = {
        "$schema_version": 1,
        "campaign_id": "tiny",
        "round": 5,
        "exp_id_counter": 5,
        "last_commit": "abc",
        "last_verdict": "keep",
        "best_so_far": {"commit": "abc", "primary_metric": 0.8},
        "consecutive_discards": 0,
        "c2_pending_diagnose": False,
        "budget_used": 5,
        "budget_total": 3,
        "created_at": "2026-04-21T00:00:00Z",
        "updated_at": "2026-04-21T00:00:00Z",
    }
    (root / "state" / "CAMPAIGN_STATE.json").write_text(json.dumps(v1_state, indent=2) + "\n")
    return root


def test_historian_run_returns_periodic_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    # Force rounds_since to reach interval
    state["rounds_since_last_historian"] = state["historian_interval"]
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["status"] == "ok"
    assert result["trigger"] == "periodic"


def test_historian_run_returns_c2_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 3  # plateau_trigger in fixture
    state["rounds_since_last_historian"] = 0  # periodic not yet reached
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["status"] == "ok"
    assert result["trigger"] == "c2"


def test_historian_run_returns_combined_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 3
    state["rounds_since_last_historian"] = state["historian_interval"]
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["trigger"] == "periodic+c2"


def test_historian_run_includes_rounds_covered(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["last_historian_round"] = 3
    state["round"] = 8
    state["rounds_since_last_historian"] = 5
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["rounds_covered"] == [4, 8]


def test_historian_finalize_resets_rounds_and_clears_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["rounds_since_last_historian"] = 5
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        patterns_added=2,
        assumptions_flagged=1,
        tokens_used=50_000,
    )
    assert result["status"] == "ok"

    state_after = json.loads(state_path.read_text())
    assert state_after["rounds_since_last_historian"] == 0
    assert state_after["historian_trigger_pending"] is False
    assert state_after["last_historian_round"] == state_after["round"]


def test_historian_finalize_stores_pending_tokens(campaign_v2: Path):
    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=75_000,
    )
    state = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state.get("pending_historian_tokens") == 75_000
    assert state["total_tokens"]["historian"] == 75_000


def test_historian_finalize_c2_resets_consecutive_discards(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 5
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="c2",
        tokens_used=0,
    )
    state_after = json.loads(state_path.read_text())
    assert state_after["consecutive_discards"] == 0


def test_historian_finalize_periodic_only_does_not_reset_discards(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 2
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    state_after = json.loads(state_path.read_text())
    assert state_after["consecutive_discards"] == 2  # unchanged for periodic-only


def test_historian_run_migrates_v1_state(campaign_v1: Path):
    state_path = campaign_v1 / "state" / "CAMPAIGN_STATE.json"
    # Force a c2 trigger so the return value includes trigger type; migration runs because schema_version=1
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 3
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.historian_run(campaign_dir=str(campaign_v1))

    state_after = json.loads(state_path.read_text())
    assert state_after["$schema_version"] == 2
    assert "rounds_since_last_historian" in state_after
    assert "historian_interval" in state_after
    assert "total_tokens" in state_after
    assert "c2_pending_diagnose" not in state_after
