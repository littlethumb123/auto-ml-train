"""Tests for schema validators — historian_interval and ASSUMPTION_REGISTER."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# --- historian_interval in EVAL_PROTOCOL ---

_EP_VALID_BASE = """---
schema_version: 1
campaign_id: "t"
primary_metric:
  name: "val_pr_auc"
  direction: "maximize"
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
mandatory_tools: []
action_types: ["A_hp"]
budgets:
  max_experiments: 100
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 0.50
  relative: 0.5
approved_at: "2026-04-26"
approved_by: "test"
---

## 1. Rationale
## 2. How keep/discard is decided
## 3. How plateau is handled
## 4. Contract change policy
"""


def test_validate_eval_protocol_accepts_valid_historian_interval(tmp_path: Path):
    content = _EP_VALID_BASE.replace(
        "approved_at:", "historian_interval: 10\napproved_at:"
    )
    path = _write(tmp_path / "EVAL_PROTOCOL.md", content)
    errors = schema.validate_eval_protocol(path)
    assert errors == []


def test_validate_eval_protocol_rejects_non_int_historian_interval(tmp_path: Path):
    content = _EP_VALID_BASE.replace(
        "approved_at:", "historian_interval: 'ten'\napproved_at:"
    )
    path = _write(tmp_path / "EVAL_PROTOCOL.md", content)
    errors = schema.validate_eval_protocol(path)
    assert any("historian_interval" in e for e in errors)


def test_validate_eval_protocol_rejects_zero_historian_interval(tmp_path: Path):
    content = _EP_VALID_BASE.replace(
        "approved_at:", "historian_interval: 0\napproved_at:"
    )
    path = _write(tmp_path / "EVAL_PROTOCOL.md", content)
    errors = schema.validate_eval_protocol(path)
    assert any("historian_interval" in e for e in errors)


def test_validate_eval_protocol_absent_historian_interval_is_ok(tmp_path: Path):
    path = _write(tmp_path / "EVAL_PROTOCOL.md", _EP_VALID_BASE)
    errors = schema.validate_eval_protocol(path)
    assert errors == []


# --- validate_assumption_register ---

_AR_VALID = """---
schema_version: 1
campaign_id: "test"
count: 0
last_updated: ""
---

<!-- Reviewer appends entries on every keep verdict. -->
"""

_AR_WITH_ENTRY = """---
schema_version: 1
campaign_id: "test"
count: 1
last_updated: "2026-04-26"
---

### A-1-1 — optimizer_quality
- **Claim:** NM found the global optimum
- **Evidence for:** val_lift went up
- **Evidence against:** none
- **Confidence:** medium
- **Load-bearing:** yes
- **Verification status:** unverified
- **Last audited:** round 1 by Reviewer
"""


def test_validate_assumption_register_valid_empty(tmp_path: Path):
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", _AR_VALID)
    errors = schema.validate_assumption_register(path)
    assert errors == []


def test_validate_assumption_register_valid_with_entry(tmp_path: Path):
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", _AR_WITH_ENTRY)
    errors = schema.validate_assumption_register(path)
    assert errors == []


def test_validate_assumption_register_missing_required_field(tmp_path: Path):
    broken = _AR_VALID.replace("count: 0\n", "")
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", broken)
    errors = schema.validate_assumption_register(path)
    assert any("count" in e for e in errors)


def test_validate_assumption_register_non_int_count(tmp_path: Path):
    broken = _AR_VALID.replace("count: 0", "count: 'zero'")
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", broken)
    errors = schema.validate_assumption_register(path)
    assert any("count" in e for e in errors)
