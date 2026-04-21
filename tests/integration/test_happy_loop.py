"""3-round happy-path integration test using stub role outputs."""
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


def _make_plan(round_n: int) -> str:
    return f"""---
schema_version: 1
campaign_id: "tiny"
round: {round_n}
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
round {round_n}
## 2. Evidence from memory
no deadends matched
## 3. Plan
1. noop.
## 4. Helpers
None.
## 5. How this differs from prior experiments
round {round_n}
## 6. Escalation (only if `escalation` frontmatter is non-null)
N/A.
"""


def test_happy_three_rounds(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))

    metrics_per_round = [
        {"val_pr_auc": 0.70, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.6},
        {"val_pr_auc": 0.72, "lift_at_10": 4.2, "macro_f1": 0.72, "val_f1": 0.61},
        {"val_pr_auc": 0.68, "lift_at_10": 3.5, "macro_f1": 0.68, "val_f1": 0.55},
    ]
    expected_verdicts = ["keep", "keep", "discard"]

    for i, (metrics, verdict) in enumerate(zip(metrics_per_round, expected_verdicts), start=1):
        (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(_make_plan(i))
        check = runner_driver.plan_check(campaign_dir=str(campaign))
        assert check["status"] == "ok", check["errors"]

        exec_status = runner_driver.execute_finalize(
            executor_stdout=f"RUN_COMPLETE: commit{i}\n",
            campaign_dir=str(campaign),
        )
        assert exec_status["channel"] == "RUN_COMPLETE"

        res = runner_driver.review_finalize(
            verdict=verdict,
            commit=f"commit{i}",
            metrics=metrics,
            action_type="A_hp",
            hypothesis=f"round {i}",
            description=f"round {i}",
            model_family="lightgbm",
            n_features=10,
            campaign_dir=str(campaign),
        )
        assert res["halt_loop"] is False or i == 3

    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["round"] == 3
    assert state["best_so_far"]["commit"] == "commit2"
    assert state["consecutive_discards"] == 1

    tsv = (campaign / "state" / "results.tsv").read_text().splitlines()
    assert len(tsv) == 4
