"""Tests for historian_run() and historian_finalize() in runner_driver."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.conftest import write_valid_strategy_memo as _memo
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
    _memo(campaign_v2, round_num=int(state.get("round", 0)), trigger="periodic")

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
    state = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    _memo(campaign_v2, round_num=int(state.get("round", 0)), trigger="periodic")
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
    _memo(campaign_v2, round_num=int(state.get("round", 0)), trigger="c2")

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
    _memo(campaign_v2, round_num=int(state.get("round", 0)), trigger="periodic")

    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    state_after = json.loads(state_path.read_text())
    assert state_after["consecutive_discards"] == 2  # unchanged for periodic-only


# --- F1: historian_finalize STRATEGY_MEMO.md assertion tests ---


def test_historian_finalize_rejects_missing_memo(campaign_v2: Path):
    """F1: no STRATEGY_MEMO.md on disk → rejected, trigger stays pending."""
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    res = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    assert res["status"] == "rejected"
    assert "missing" in res["reason"].lower()
    state_after = json.loads(state_path.read_text())
    assert state_after["historian_trigger_pending"] is True


def test_historian_finalize_rejects_stale_memo(campaign_v2: Path):
    """F1: STRATEGY_MEMO.md mtime older than round_started_at → rejected."""
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    # Stamp a future-anchored round_started_at so the freshly-written memo
    # appears stale relative to the anchor.
    import datetime as _dt
    future = (
        _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["round_started_at"] = future
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    _memo(campaign_v2, round_num=int(state.get("round", 0)), trigger="periodic")

    res = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    assert res["status"] == "rejected"
    assert "mtime" in res["reason"].lower()


def test_historian_finalize_rejects_wrong_round_in_frontmatter(campaign_v2: Path):
    """F1: memo's historian_round != state.round → rejected."""
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["round"] = 5
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    _memo(campaign_v2, round_num=4, trigger="periodic")  # wrong round

    res = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    assert res["status"] == "rejected"
    assert "historian_round" in res["reason"].lower() or "round" in res["reason"].lower()


def test_historian_finalize_rejects_missing_section(campaign_v2: Path):
    """F1: memo body missing one of the four required sections → rejected."""
    state = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    memo_path = campaign_v2 / "state" / "STRATEGY_MEMO.md"
    memo_path.write_text(
        f"---\nschema_version: 1\nhistorian_round: {int(state.get('round', 0))}\n"
        f'trigger: "periodic"\n---\n\n'
        "## 1. Trajectory Narrative\nA bunch of words that exceeds eighty chars "
        "easily so this section is not too short to count for the F1 check.\n\n"
        "## 2. Pattern Extraction\nMore than eighty characters of pattern text "
        "to clear the minimum length floor that F1 verification enforces.\n\n"
        "## 3. Assumption Audit\nLong audit text well past the eighty character "
        "lower bound that F1 enforces for non-placeholder content.\n\n"
        # Section 4 missing.
    )
    res = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    assert res["status"] == "rejected"
    assert "Bottleneck Diagnosis" in res["reason"]


def test_historian_finalize_rejects_placeholder_section(campaign_v2: Path):
    """F1: memo section that is just 'TBD' → rejected via length floor."""
    state = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    memo_path = campaign_v2 / "state" / "STRATEGY_MEMO.md"
    memo_path.write_text(
        f"---\nschema_version: 1\nhistorian_round: {int(state.get('round', 0))}\n"
        f'trigger: "periodic"\n---\n\n'
        "## 1. Trajectory Narrative\nTBD\n\n"
        "## 2. Pattern Extraction\nLong enough pattern text to clear the eighty "
        "character minimum for non-placeholder content checks.\n\n"
        "## 3. Assumption Audit\nLong enough assumption text to clear the eighty "
        "character minimum for non-placeholder content checks.\n\n"
        "## 4. Bottleneck Diagnosis\nLong enough bottleneck text to clear the "
        "eighty character minimum for non-placeholder content checks.\n"
    )
    res = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    assert res["status"] == "rejected"
    # Either length-floor or placeholder-regex catches this.
    assert "Trajectory Narrative" in res["reason"]


def test_historian_finalize_accepts_complete_memo(campaign_v2: Path):
    """F1: all four sections with non-placeholder content + matching round → accepted."""
    state = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    state["historian_trigger_pending"] = True
    (campaign_v2 / "state" / "CAMPAIGN_STATE.json").write_text(
        json.dumps(state, indent=2) + "\n"
    )
    _memo(campaign_v2, round_num=int(state.get("round", 0)), trigger="periodic")

    res = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        patterns_added=2,
        assumptions_flagged=1,
        tokens_used=10_000,
    )
    assert res["status"] == "ok"
    state_after = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state_after["historian_trigger_pending"] is False

    # historian_finalize event with verified=True must be present.
    events = (campaign_v2 / "state" / "driver_events.jsonl").read_text().splitlines()
    finalize_events = [
        json.loads(e) for e in events if json.loads(e).get("event") == "historian_finalize"
    ]
    assert len(finalize_events) == 1
    assert finalize_events[0]["verified"] is True


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
