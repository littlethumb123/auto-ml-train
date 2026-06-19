"""Smoke: `runner/run_round.sh` invokes driver from repo root."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.integration


def test_run_round_review_finalize_bootstrap_se_via_shell(tmp_path: Path):
    """review-finalize passes bootstrap_se through the shell wrapper."""
    root = tmp_path / "campaign"
    runner = root / "runner"
    (runner / "contracts").mkdir(parents=True)
    (runner / "state").mkdir()
    (runner / "contracts" / "PROBLEM_CONTRACT.md").write_text(
        PROBLEM_CONTRACT.replace(
            'success_criteria: ["val_pr_auc >= 0.5"]',
            'success_criteria: ["val_pr_auc >= 0.90"]',
        )
    )
    (runner / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (runner / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)

    repo_root = Path(__file__).resolve().parents[2]
    sh = repo_root / "runner" / "run_round.sh"
    subprocess.run(
        [str(sh), "init", "--campaign-dir", str(runner)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    # F3+F2: stamp round_started_at, emit a tool_run receipt, and simulate
    # the Reviewer's mandatory writes for round 1 (no plan_check called in
    # this shell-flow test).
    import datetime as _dt
    from tests.conftest import anchor_round_with_receipts as _anchor
    _anchor(runner, ["tools/anomaly.py"])  # round 1 (keep)

    subprocess.run(
        [
            str(sh),
            "review-finalize",
            "--verdict",
            "keep",
            "--commit",
            "abc111",
            "--metrics-json",
            '{"val_pr_auc":0.85,"lift_at_10":5.0,"macro_f1":0.8,"val_f1":0.7}',
            "--action-type",
            "A_hp",
            "--hypothesis",
            "h",
            "--description",
            "d",
            "--model-family",
            "lgb",
            "--n-features",
            "10",
            "--bootstrap-se",
            "0.04",
            "--tools-ran",
            '["tools/anomaly.py"]',
            "--campaign-dir",
            str(runner),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    # F3+F2: re-anchor for round 2 (the upcoming discard).
    _anchor(runner, ["tools/anomaly.py"], verdict_for_writes="discard")
    out2 = subprocess.run(
        [
            str(sh),
            "review-finalize",
            "--verdict",
            "discard",
            "--commit",
            "abc222",
            "--metrics-json",
            '{"val_pr_auc":0.84,"lift_at_10":4.0,"macro_f1":0.7,"val_f1":0.6}',
            "--action-type",
            "A_hp",
            "--hypothesis",
            "h2",
            "--description",
            "d2",
            "--model-family",
            "lgb",
            "--n-features",
            "10",
            "--bootstrap-se",
            "0.04",
            "--campaign-dir",
            str(runner),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(out2.stdout)
    assert payload.get("c3_advisory") is True
    assert "target_gap" in payload.get("c3_advisory_reason", "")


def test_run_round_init_via_shell(tmp_path: Path):
    root = tmp_path / "campaign"
    runner = root / "runner"
    (runner / "contracts").mkdir(parents=True)
    (runner / "state").mkdir()
    (runner / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (runner / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (runner / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)

    repo_root = Path(__file__).resolve().parents[2]
    sh = repo_root / "runner" / "run_round.sh"
    out = subprocess.run(
        [str(sh), "init", "--campaign-dir", str(runner)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    state = json.loads(out.stdout)
    assert state["campaign_id"] == "tiny"
    assert state["round"] == 0
    assert state["budget_total"] == 3
