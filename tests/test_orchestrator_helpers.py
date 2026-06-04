"""Unit tests for runner/orchestrator.py helper functions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import orchestrator
from runner import runner_driver

# Import test contracts from the driver test module
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "campaign"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    (root / "train.py").write_text("# placeholder\n")
    return root


# ── Stuck detection ───────────────────────────────────────────────────

class TestStuckDetection:
    def test_no_warnings_on_empty(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        assert orchestrator.detect_stuck(campaign) == []

    def test_warns_on_3_same_action_types(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        results_path = campaign / "state" / "results.tsv"
        header = results_path.read_text().splitlines()[0]
        col_names = header.split("\t")
        at_idx = col_names.index("action_type")
        n_cols = len(col_names)

        rows = []
        for i in range(3):
            row = [""] * n_cols
            row[0] = f"c{i}"
            row[at_idx] = "A_hp"
            rows.append("\t".join(row))
        results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

        warnings = orchestrator.detect_stuck(campaign)
        assert len(warnings) >= 1
        assert any("STUCK" in w for w in warnings)

    def test_warns_on_abab_alternation(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        results_path = campaign / "state" / "results.tsv"
        header = results_path.read_text().splitlines()[0]
        col_names = header.split("\t")
        at_idx = col_names.index("action_type")
        n_cols = len(col_names)

        rows = []
        for i, at in enumerate(["A_hp", "A_model", "A_hp", "A_model"]):
            row = [""] * n_cols
            row[0] = f"c{i}"
            row[at_idx] = at
            rows.append("\t".join(row))
        results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

        warnings = orchestrator.detect_stuck(campaign)
        assert any("alternation" in w.lower() or "A-B-A-B" in w for w in warnings)

    def test_no_warning_on_varied_types(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        results_path = campaign / "state" / "results.tsv"
        header = results_path.read_text().splitlines()[0]
        col_names = header.split("\t")
        at_idx = col_names.index("action_type")
        n_cols = len(col_names)

        rows = []
        for i, at in enumerate(["A_hp", "A_model", "A_feature"]):
            row = [""] * n_cols
            row[0] = f"c{i}"
            row[at_idx] = at
            rows.append("\t".join(row))
        results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

        assert orchestrator.detect_stuck(campaign) == []


# ── Metrics parsing ───────────────────────────────────────────────────

class TestMetricsParsing:
    def test_parses_val_lines(self, tmp_path: Path):
        log = tmp_path / "run.log"
        log.write_text("val_pr_auc: 0.875\nval_f1: 0.62\nother line\n")
        metrics = orchestrator.parse_metrics_from_log(log)
        assert metrics["val_pr_auc"] == pytest.approx(0.875)
        assert metrics["val_f1"] == pytest.approx(0.62)

    def test_parses_delimited_block(self, tmp_path: Path):
        log = tmp_path / "run.log"
        log.write_text("---\nval_pr_auc: 0.9\nlift_at_10: 4.2\n---\n")
        metrics = orchestrator.parse_metrics_from_log(log)
        assert metrics["val_pr_auc"] == pytest.approx(0.9)

    def test_empty_log(self, tmp_path: Path):
        log = tmp_path / "run.log"
        log.write_text("")
        assert orchestrator.parse_metrics_from_log(log) == {}

    def test_missing_log(self, tmp_path: Path):
        log = tmp_path / "nonexistent.log"
        assert orchestrator.parse_metrics_from_log(log) == {}


# ── Resume phase detection ────────────────────────────────────────────

class TestResumePhase:
    def test_planner_when_nothing_present(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        assert orchestrator.determine_resume_phase(campaign, state) == "planner"

    def test_executor_when_plan_exists(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        (campaign / "state" / "NEXT_EXPERIMENT.md").write_text("some plan\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "executor"

    def test_reviewer_when_run_log_exists(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        (campaign / "run.log").write_text("RUN_COMPLETE: abc123\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "reviewer"

    def test_historian_when_journal_complete_and_pending(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        state["historian_trigger_pending"] = True
        (campaign / "state" / "CAMPAIGN_JOURNAL.md").write_text("## Round 5\nDone.\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "historian"

    def test_next_round_when_journal_complete_no_trigger(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        state["historian_trigger_pending"] = False
        (campaign / "state" / "CAMPAIGN_JOURNAL.md").write_text("## Round 5\nDone.\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "next_round"


# ── Round digest ──────────────────────────────────────────────────────

class TestRoundDigest:
    def test_format_round_digest(self):
        digest = orchestrator.format_round_digest(
            round_num=3,
            verdict="keep",
            action_type="A_feature",
            hypothesis="add county encoding",
            primary_metric_value=0.875,
            primary_metric_name="val_pr_auc",
        )
        assert "Round 3" in digest
        assert "keep" in digest
        assert "A_feature" in digest
        assert "0.875" in digest


# ── Tools-ran inference ───────────────────────────────────────────────

class TestToolsRanInference:
    def test_infers_from_text(self):
        text = "I ran anomaly detection and bootstrap_ci confidence intervals."
        tools = orchestrator.infer_tools_ran(text)
        assert "runner.tools.anomaly" in tools
        assert "runner.tools.bootstrap_ci" in tools

    def test_empty_text(self):
        assert orchestrator.infer_tools_ran("") == []
