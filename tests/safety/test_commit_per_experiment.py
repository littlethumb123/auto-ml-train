"""Invariant: every row in results.tsv corresponds to exactly one verdict."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_results_tsv_row_count_matches_budget_used(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    for i, (verdict, metric) in enumerate([
        ("keep", 0.70),
        ("discard", 0.50),
        ("crash", 0.00),
    ], start=1):
        runner_driver.review_finalize(
            verdict=verdict, commit=f"c{i}",
            metrics={"val_pr_auc": metric, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(campaign),
        )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    lines = (campaign / "state" / "results.tsv").read_text().splitlines()
    assert len(lines) - 1 == state["budget_used"]
