"""Unit tests for runner.runner_driver (the state machine)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver

PROBLEM_CONTRACT = """---
schema_version: 1
campaign_id: "tiny"
problem_title: "Tiny"
task_type: "binary_classification"
unit_of_observation: "row"
target:
  name: "Class"
  positive_class: 1
  definition: "synthetic"
success_criteria: ["val_pr_auc >= 0.5"]
constraints: []
non_goals: []
approved_at: "2026-04-21"
approved_by: "test"
---

## 1. Task
x
## 2. Why the task matters
x
## 3. Success criteria (detail)
x
## 4. Constraints (detail)
x
## 5. Non-goals (detail)
x
"""

DATA_CONTRACT = """---
schema_version: 1
campaign_id: "tiny"
data_sources:
  - path: "tiny.csv"
    n_rows: 500
    n_cols: 6
    primary_key: "row"
temporal:
  is_temporal: false
  order_column: null
  prediction_time_column: null
columns: []
leakage_audit:
  performed_at: "2026-04-21"
  flagged_columns: []
  notes: ""
splits:
  train: "60%"
  val: "20%"
  test: "20%"
  random_seed: 42
approved_at: "2026-04-21"
approved_by: "test"
---

## 1. Schema summary
## 2. Availability table (narrative)
## 3. Leakage audit summary
## 4. Transformations applied pre-agent (if any)
## 5. Known data quality issues
"""

EVAL_PROTOCOL = """---
schema_version: 1
campaign_id: "tiny"
primary_metric:
  name: "val_pr_auc"
  direction: "maximize"
  noise_floor: 0.005
acceptance_threshold:
  baseline_family: "logreg"
  min_improvement: 0.01
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: ""
bootstrap_ci:
  enabled: false
  n_boot: 100
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools: ["tools/anomaly.py"]
action_types: ["A_hp", "A_model"]
budgets:
  time_budget_s: 60
  hard_timeout_s: 90
  max_experiments: 3
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 0.50
  relative: 0.5
approved_at: "2026-04-21"
approved_by: "test"
---

## 1. Rationale
## 2. How keep/discard is decided
## 3. How plateau is handled
## 4. Contract change policy
"""


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_init_creates_campaign_state_and_results_header(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["campaign_id"] == "tiny"
    assert state["round"] == 0
    assert state["budget_total"] == 3
    results = (campaign / "state" / "results.tsv").read_text()
    assert results.startswith("commit\tval_pr_auc\tlift_at_10")


def test_init_refuses_when_contracts_unsigned(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    src = PROBLEM_CONTRACT.replace('approved_at: "2026-04-21"', "approved_at: null")
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(src)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    with pytest.raises(runner_driver.GateError):
        runner_driver.init_campaign(campaign_dir=str(root))


def test_plan_check_rejects_malformed(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text("not a valid plan")
    status = runner_driver.plan_check(campaign_dir=str(campaign))
    assert status["status"] == "malformed"


def test_plan_check_c2_pauses(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    plan = """---
schema_version: 1
campaign_id: "tiny"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "switch families"
expected_effect_size: 0.0
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: "C2"
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
x
## 4. Helpers
None.
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)

### For C2 (plateau / family switch):
- Rationale: families exhausted.
- Proposed alternative: catboost.
- Signal: AUC > 0.8.
"""
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(plan)
    status = runner_driver.plan_check(campaign_dir=str(campaign))
    assert status["status"] == "pause_c2"


def test_review_finalize_keep_updates_state(campaign: Path, tmp_path: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.review_finalize(
        verdict="keep",
        commit="abc123",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="tighter range",
        description="initial lgbm",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["round"] == 1
    assert state["last_verdict"] == "keep"
    assert status["should_rollback"] is False


def test_review_finalize_discard_triggers_rollback(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.review_finalize(
        verdict="discard", commit="xyz", metrics={"val_pr_auc": 0.4, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=10,
        campaign_dir=str(campaign),
    )
    assert status["should_rollback"] is True


def test_review_finalize_two_consecutive_malformed_halts(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    r1 = runner_driver.review_finalize(
        verdict="malformed", commit="m1", metrics={"val_pr_auc": 0.0, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        action_type="A_hp", hypothesis="", description="", model_family="other", n_features=0,
        campaign_dir=str(campaign),
    )
    assert r1["halt_loop"] is False
    r2 = runner_driver.review_finalize(
        verdict="malformed", commit="m2", metrics={"val_pr_auc": 0.0, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        action_type="A_hp", hypothesis="", description="", model_family="other", n_features=0,
        campaign_dir=str(campaign),
    )
    assert r2["halt_loop"] is True


def test_review_finalize_anomaly_no_discard_bump_no_rollback(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.review_finalize(
        verdict="anomaly", commit="a1", metrics={"val_pr_auc": 0.40, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        action_type="A_diagnose", hypothesis="anom", description="d",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(campaign),
    )
    assert status["should_rollback"] is False
    assert status["pause_loop"] is True
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0


def test_execute_finalize_parses_run_complete(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
    )
    assert status["channel"] == "RUN_COMPLETE"
    assert status["commit"] == "abc123"
    assert status["synthetic_verdict"] is None


def test_execute_finalize_parses_review_required(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.execute_finalize(
        executor_stdout="REVIEW_REQUIRED: malformed_plan\n",
        campaign_dir=str(campaign),
    )
    assert status["channel"] == "REVIEW_REQUIRED"
    assert status["synthetic_verdict"] == "malformed"


def test_execute_finalize_parses_run_failed(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.execute_finalize(
        executor_stdout="RUN_FAILED: abc123 repair_cap_exceeded\n",
        campaign_dir=str(campaign),
    )
    assert status["channel"] == "RUN_FAILED"
    assert status["synthetic_verdict"] == "crash"


def test_init_creates_v2_state_fields(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["$schema_version"] == 2
    assert state["rounds_since_last_historian"] == 0
    assert "historian_interval" in state
    assert state["historian_interval"] >= 1
    assert state["historian_trigger_pending"] is False
    assert state["total_tokens"] == {"planner": 0, "executor": 0, "reviewer": 0, "historian": 0}
    assert "c2_pending_diagnose" not in state


def test_init_creates_assumption_register_skeleton(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    ar = (campaign / "state" / "ASSUMPTION_REGISTER.md")
    assert ar.exists()
    text = ar.read_text()
    assert "schema_version: 1" in text
    assert "count: 0" in text


def test_init_creates_pattern_book_skeleton(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    pb = (campaign / "state" / "PATTERN_BOOK.md")
    assert pb.exists()
    text = pb.read_text()
    assert "schema_version: 1" in text
    assert "count: 0" in text


def test_init_historian_interval_from_eval_protocol(tmp_path: Path):
    """When historian_interval is explicit in EVAL_PROTOCOL, use it."""
    ep_with_interval = EVAL_PROTOCOL.replace(
        "approved_at:", "historian_interval: 7\napproved_at:"
    )
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(ep_with_interval)
    runner_driver.init_campaign(campaign_dir=str(root))
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["historian_interval"] == 7


def test_init_historian_interval_default_for_small_budget(campaign: Path):
    """budget_total=3 < 50 → max(5, int(3 * 0.10)) = 5."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    # EVAL_PROTOCOL fixture has max_experiments: 3
    assert state["historian_interval"] == 5
