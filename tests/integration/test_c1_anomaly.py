"""Integration test: anomaly verdict pauses loop and does NOT rollback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.integration


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_anomaly_pauses_and_preserves_state(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))

    res = runner_driver.review_finalize(
        verdict="anomaly",
        commit="anom1",
        metrics={"val_pr_auc": 0.30, "lift_at_10": 1.0, "macro_f1": 0.4, "val_f1": 0.3},
        action_type="A_diagnose",
        hypothesis="suspicious low score",
        description="metric inverted?",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
    )
    assert res["pause_loop"] is True
    assert res["should_rollback"] is False

    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["last_verdict"] == "anomaly"
    assert state["consecutive_discards"] == 0
    assert state["best_so_far"]["commit"] is None

    tsv = (campaign / "state" / "results.tsv").read_text()
    assert "anom1" in tsv
    assert "anomaly" in tsv
