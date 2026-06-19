"""Pressure tests — edge cases and boundary conditions (GAP 6).

These tests verify the driver handles unusual inputs gracefully:
- Budget exhaustion mid-round
- Missing artifacts
- Corrupted state files
- Simultaneous gate triggers
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.conftest import anchor_round_with_receipts as _anchor
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


class TestBudgetExhaustion:
    def test_halt_when_budget_exhausted_on_keep(self, campaign: Path):
        """Driver halts even on a keep verdict when budget is used up."""
        runner_driver.init_campaign(campaign_dir=str(campaign))
        _anchor(campaign, ["tools/anomaly.py"])
        # Budget is max_experiments=3 in the test EVAL_PROTOCOL
        for i in range(3):
            res = runner_driver.review_finalize(
                verdict="keep",
                commit=f"c{i}",
                metrics={"val_pr_auc": 0.80 + i * 0.01, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
                action_type="A_hp",
                hypothesis=f"h{i}",
                description=f"d{i}",
                model_family="lightgbm",
                n_features=10,
                campaign_dir=str(campaign),
                tools_ran=["tools/anomaly.py"],
            )
        assert res["halt_loop"] is True
        assert "budget" in res.get("halt_reason", "").lower()

    def test_halt_on_two_consecutive_malformed(self, campaign: Path):
        """Two consecutive malformed verdicts trigger halt (likely bug)."""
        runner_driver.init_campaign(campaign_dir=str(campaign))
        runner_driver.review_finalize(
            verdict="malformed", commit="c1",
            metrics={"val_pr_auc": 0.5, "lift_at_10": 1.0, "macro_f1": 0.5, "val_f1": 0.4},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(campaign), tools_ran=["tools/anomaly.py"],
        )
        res = runner_driver.review_finalize(
            verdict="malformed", commit="c2",
            metrics={"val_pr_auc": 0.5, "lift_at_10": 1.0, "macro_f1": 0.5, "val_f1": 0.4},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(campaign), tools_ran=["tools/anomaly.py"],
        )
        assert res["halt_loop"] is True
        assert "malformed" in res.get("halt_reason", "").lower()


class TestSimultaneousGates:
    def test_noise_floor_and_mandatory_tools_both_fire(self, campaign: Path):
        """When both gates would fire, mandatory tools takes priority (fires first)."""
        eval_with_both = EVAL_PROTOCOL.replace(
            'mandatory_tools: ["tools/anomaly.py"]',
            'mandatory_tools: ["runner.tools.anomaly", "runner.tools.bootstrap_ci"]',
        )
        (campaign / "contracts" / "EVAL_PROTOCOL.md").write_text(eval_with_both)
        runner_driver.init_campaign(campaign_dir=str(campaign))
        _anchor(campaign, ["runner.tools.anomaly", "runner.tools.bootstrap_ci"])

        # First experiment sets baseline
        runner_driver.review_finalize(
            verdict="keep", commit="c1",
            metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(campaign),
            tools_ran=["runner.tools.anomaly", "runner.tools.bootstrap_ci"],
        )

        # Second: keep verdict, tiny delta, AND missing mandatory tool
        res = runner_driver.review_finalize(
            verdict="keep", commit="c2",
            metrics={"val_pr_auc": 0.801, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(campaign),
            tools_ran=["runner.tools.anomaly"],  # missing bootstrap_ci
        )
        # Mandatory tool gate fires first → malformed (not discard from noise floor)
        assert res["verdict"] == "malformed"


class TestMissingArtifacts:
    def test_plan_check_missing_plan(self, campaign: Path):
        """plan_check handles missing NEXT_EXPERIMENT.md gracefully."""
        runner_driver.init_campaign(campaign_dir=str(campaign))
        res = runner_driver.plan_check(campaign_dir=str(campaign))
        assert res["status"] == "missing"

    def test_plan_check_missing_dead_ends(self, campaign: Path):
        """plan_check works when DEAD_ENDS.md doesn't exist (no dead-end check)."""
        runner_driver.init_campaign(campaign_dir=str(campaign))
        from tests.test_runner_driver import _make_valid_plan
        plan = _make_valid_plan(hypothesis="test something new")
        (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(plan)
        # DEAD_ENDS.md doesn't exist — should not crash
        res = runner_driver.plan_check(campaign_dir=str(campaign))
        assert res["status"] == "ok"


class TestStructuredEvents:
    def test_review_finalize_emits_event(self, campaign: Path):
        """GAP 11: review_finalize writes to driver_events.jsonl."""
        runner_driver.init_campaign(campaign_dir=str(campaign))
        _anchor(campaign, ["tools/anomaly.py"])
        runner_driver.review_finalize(
            verdict="keep", commit="c1",
            metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(campaign), tools_ran=["tools/anomaly.py"],
        )
        events_path = campaign / "state" / "driver_events.jsonl"
        assert events_path.exists()
        lines = events_path.read_text().strip().splitlines()
        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["event"] == "review_finalize"
        assert event["verdict"] == "keep"

    def test_plan_check_emits_event(self, campaign: Path):
        """GAP 11: plan_check writes to driver_events.jsonl."""
        runner_driver.init_campaign(campaign_dir=str(campaign))
        from tests.test_runner_driver import _make_valid_plan
        plan = _make_valid_plan()
        (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(plan)
        runner_driver.plan_check(campaign_dir=str(campaign))
        events_path = campaign / "state" / "driver_events.jsonl"
        assert events_path.exists()
        event = json.loads(events_path.read_text().strip().splitlines()[-1])
        assert event["event"] == "plan_check"
        assert event["status"] == "ok"
