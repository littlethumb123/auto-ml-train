from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from runner.tools import baseline_runner
from tests.fixtures.tiny_dataset import make_tiny_binary

EVAL_PROTOCOL = """---
schema_version: 1
campaign_id: "tiny"
primary_metric:
  name: "pr_auc"
  direction: "maximize"
  noise_floor: 0.005
acceptance_threshold:
  baseline_family: "logreg"
  min_improvement: 0.01
cv_scheme:
  type: "stratified_kfold"
  n_splits: 3
  random_state: 42
  notes: "tiny"
bootstrap_ci:
  enabled: false
  n_boot: 100
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools: []
action_types: ["A_model"]
budgets:
  time_budget_s: 30
  hard_timeout_s: 60
  max_experiments: 5
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 0.30
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
def eval_path(tmp_path: Path) -> Path:
    p = tmp_path / "EVAL.md"
    p.write_text(EVAL_PROTOCOL)
    return p


@pytest.fixture
def data_path(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    df = X.copy()
    df["Class"] = y
    p = tmp_path / "tiny.csv"
    df.to_csv(p, index=False)
    return p


def test_baseline_runner_logreg(eval_path: Path, data_path: Path, tmp_path: Path):
    out_path = tmp_path / "baseline.json"
    res = baseline_runner.baseline_runner(
        family="logreg",
        eval_protocol_path=str(eval_path),
        data_path=str(data_path),
        target_col="Class",
        output_path=str(out_path),
    )
    assert res["family"] == "logreg"
    assert res["metric_name"] == "pr_auc"
    assert 0.0 <= res["metric_value"] <= 1.0
    assert len(res["fold_scores"]) == 3
    assert out_path.exists()
    loaded = json.loads(out_path.read_text())
    assert loaded == res


def test_baseline_runner_unknown_family_raises(eval_path: Path, data_path: Path, tmp_path: Path):
    with pytest.raises(ValueError):
        baseline_runner.baseline_runner(
            family="made_up_family",
            eval_protocol_path=str(eval_path),
            data_path=str(data_path),
            target_col="Class",
            output_path=str(tmp_path / "x.json"),
        )
