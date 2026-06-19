"""Shared pytest fixtures for the runner test suite."""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path

import pytest


def anchor_round_with_receipts(campaign: Path, tools: list[str]) -> str:
    """Stamp round_started_at and emit tool_run receipts (F3 test helper).

    Tests that exercise review_finalize with verdict=keep need to satisfy the
    F3 receipt cross-check. This helper:
      1. Stamps state.round_started_at to "now".
      2. Appends one tool_run event per named tool to driver_events.jsonl with
         exit_code=0 and start_ts/end_ts at "now".

    Returns the anchor timestamp.
    """
    from runner import runner_driver  # local import to avoid pytest collection cycles

    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    anchor = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["round_started_at"] = anchor
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    events = campaign / "state" / "driver_events.jsonl"
    with open(events, "a") as f:
        for t in tools:
            rec = {
                "ts": anchor,
                "event": "tool_run",
                "name": runner_driver._normalize_mandatory_tool_name(t),
                "start_ts": anchor,
                "end_ts": anchor,
                "exit_code": 0,
                "args_hash": "deadbeefdeadbeef",
                "round": int(state.get("round", 0)),
                "campaign_dir": str(campaign),
            }
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    return anchor


@pytest.fixture
def tmp_campaign_dir(tmp_path: Path) -> Path:
    """A temporary `runner/` workspace with the directory tree created and
    empty placeholder artifacts. Does NOT create valid contracts; individual
    tests populate what they need."""
    root = tmp_path / "runner"
    for sub in ("contracts", "state", "tools", "roles", "experiment_helpers"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    header = (
        "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
        "model_family\taction_type\thypothesis\tdescription\n"
    )
    (root / "state" / "results.tsv").write_text(header)
    return root


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """A temporary initialized git repo with an initial commit. Used by
    driver tests that exercise `git reset --hard HEAD~1`."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path
