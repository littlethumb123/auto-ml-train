from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import contract_diff

ORIG = """---
schema_version: 1
campaign_id: "x"
primary_metric:
  name: "pr_auc"
  direction: "maximize"
  noise_floor: 0.005
budgets:
  time_budget_s: 60
  max_experiments: 100
  max_repair_attempts: 2
  hard_timeout_s: 90
acceptance_threshold:
  baseline_family: "logreg"
  min_improvement: 0.01
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: ""
bootstrap_ci:
  enabled: true
  n_boot: 1000
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools: []
action_types: ["A_hp"]
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 0.75
  relative: 0.5
approved_at: "2026-04-21"
approved_by: "x"
---

## 1. Rationale
## 2. How keep/discard is decided
## 3. How plateau is handled
## 4. Contract change policy
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    runner = tmp_path / "runner"
    contracts = runner / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "EVAL_PROTOCOL.md").write_text(ORIG)
    return runner


def test_contract_diff_noise_floor_change(workspace: Path, tmp_path: Path):
    proposed = ORIG.replace("noise_floor: 0.005", "noise_floor: 0.001")
    prop_path = tmp_path / "proposed.md"
    prop_path.write_text(proposed)
    res = contract_diff.contract_diff(
        contract_name="EVAL",
        proposed_path=str(prop_path),
        campaign_dir=str(workspace),
    )
    assert res["contract"] == "EVAL"
    changed = [c["field"] for c in res["changes"]]
    assert "primary_metric.noise_floor" in changed


def test_contract_diff_hard_invariant_change_is_high_risk(workspace: Path, tmp_path: Path):
    proposed = ORIG.replace("max_repair_attempts: 2", "max_repair_attempts: 5")
    prop_path = tmp_path / "proposed.md"
    prop_path.write_text(proposed)
    res = contract_diff.contract_diff(
        contract_name="EVAL",
        proposed_path=str(prop_path),
        campaign_dir=str(workspace),
    )
    assert res["risk_level"] == "high"


def test_contract_diff_missing_current_raises(tmp_path: Path):
    runner = tmp_path / "runner"
    (runner / "contracts").mkdir(parents=True)
    prop = tmp_path / "p.md"
    prop.write_text(ORIG)
    with pytest.raises(FileNotFoundError):
        contract_diff.contract_diff(
            contract_name="EVAL",
            proposed_path=str(prop),
            campaign_dir=str(runner),
        )
