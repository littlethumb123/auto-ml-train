"""Smoke: `runner/run_round.sh` invokes driver from repo root."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.integration


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
