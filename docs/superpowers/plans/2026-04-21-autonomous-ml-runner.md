# Autonomous ML Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `runner/` greenfield subsystem + `log.py` + tests + migration from `abes_engine.py`, exactly matching the approved spec at `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md`.

**Architecture:** Three context-isolated agent roles (Planner/Executor/Reviewer) operate on disk artifacts governed by YAML frontmatter + fixed numbered H2 markdown sections. A thin orchestration driver (`runner/run_round.sh` → `runner/runner_driver.py`) validates artifacts, routes Executor stdout channels (`REVIEW_REQUIRED:` / `RUN_COMPLETE:` / `RUN_FAILED:`) and Reviewer verdicts, manages git commits/rollbacks, and appends to `results.tsv` via `log.py`. Tactical compute lives in `runner/tools/` as callable Python functions with `__main__` CLIs.

**Tech Stack:** Python 3 (pandas, numpy, scikit-learn, xgboost, lightgbm, catboost, optuna, imbalanced-learn, PyYAML), pytest for testing, git for experiment history.

**Terminology note:** "Driver" in this plan = `runner/runner_driver.py` (Python implementation) + `runner/run_round.sh` (shell CLI wrapper). The spec calls this collectively "the driver".

**Scope note:** The MVP does NOT include LLM orchestration — the agent (the person/system running the campaign) invokes Planner / Executor / Reviewer roles themselves by reading `runner/roles/<role>.md`. The driver is called between roles to validate + transition state. This matches how legacy `abes_engine.py` worked.

---

## Phase overview

| Phase | Tasks | Goal |
|-------|-------|------|
| **A. Foundations** | T1–T5 | Testing infra, tools package skeleton, schema validator (the internal keystone), `runner/` scaffold, `log.py`. |
| **B. Within-loop tools** | T6–T8 | Anomaly + memory queries (the tools the Reviewer runs every round). |
| **C. Gate-support tools** | T9–T11 | Data profile, leakage audit, baseline runner (used at G2/G3 and to assess campaign health). |
| **D. Statistical tools** | T12–T15 | cv_runner, bootstrap_ci, paired_comparison, optuna_search. |
| **E. Specialized tools** | T16–T18 | clustering_eval, explain_run, contract_diff. |
| **F. Driver & orchestration** | T19 | `runner_driver.py` + `run_round.sh` state machine. |
| **G. Integration & safety tests** | T20 | End-to-end stub-role tests + invariant tests. |
| **H. Roles & first campaign** | T21–T22 | Role prompt files + seed contracts (creditcard campaign). |
| **I. Migration** | T23 | Delete `abes_engine.py`, convert `program.md` / root `AGENTS.md` / `CLAUDE.md` to stubs. |
| **J. Smoke test** | T24 | Dry-run driver init + first Planner+Executor+Reviewer cycle on a stub. |

Total: 24 tasks. Each task is itself decomposed into 3–8 bite-sized steps.

---

# Phase A — Foundations

## Task 1: Test infrastructure + dependency additions

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/tiny_dataset.py`

- [ ] **Step 1: Add pytest and PyYAML to requirements.txt**

Append these two lines at the end of `requirements.txt`:

```
pytest>=7.0
PyYAML>=6.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install pytest PyYAML`
Expected: both packages resolve and install without errors.

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -ra -q --strict-markers
markers =
    integration: slow end-to-end tests (stub-role driven)
    safety: hard-invariant tests
```

- [ ] **Step 4: Create empty package marker**

```python
# tests/__init__.py
```

- [ ] **Step 5: Create `tests/conftest.py` with shared fixtures**

```python
"""Shared pytest fixtures for the runner test suite."""
from __future__ import annotations

import json
import os
import subprocess
import shutil
from pathlib import Path
import pytest


@pytest.fixture
def tmp_campaign_dir(tmp_path: Path) -> Path:
    """A temporary `runner/` workspace with the directory tree created and
    empty placeholder artifacts. Does NOT create valid contracts; individual
    tests populate what they need."""
    root = tmp_path / "runner"
    for sub in ("contracts", "state", "tools", "roles", "experiment_helpers"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    # Start with a valid, minimal results.tsv header so tools that parse it don't choke
    header = (
        "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
        "model_family\taction_type\thypothesis\tdescription\n"
    )
    (root / "state" / "results.tsv").write_text(header)
    return root


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """A temporary initialized git repo with an initial commit. Used by
    driver tests that exercise `git reset --hard HEAD~1`."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path
```

- [ ] **Step 6: Create tiny binary-classification dataset fixture**

```python
# tests/fixtures/__init__.py
```

```python
# tests/fixtures/tiny_dataset.py
"""A tiny, deterministic binary-classification dataset used by tool and
integration tests. 500 rows, 5 features, ~10% positive class, seed=42."""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_tiny_binary(n: int = 500, seed: int = 42) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    x4 = rng.uniform(size=n)
    x5 = rng.integers(0, 5, size=n).astype(float)
    # Linear signal with noise → easy to learn but not trivial
    logit = 0.8 * x1 - 0.6 * x2 + 0.3 * x3
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.uniform(size=n) < prob * 0.25).astype(int)  # ~10% positive
    X = pd.DataFrame(
        {"x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5}
    )
    return X, pd.Series(y, name="Class")
```

- [ ] **Step 7: Verify test infra works**

Run: `pytest --collect-only tests/ 2>&1 | head -20`
Expected: collects 0 tests (no test files yet), no errors, exits 5 (no tests collected). Treat a clean "no tests ran" message as success.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini tests/__init__.py tests/conftest.py tests/fixtures/__init__.py tests/fixtures/tiny_dataset.py
git commit -m "test: add pytest infrastructure and tiny-dataset fixture"
```

---

## Task 2: Tools package skeleton + common utilities

**Files:**
- Create: `runner/__init__.py`
- Create: `runner/tools/__init__.py`
- Create: `runner/tools/_common.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_common.py`

- [ ] **Step 1: Write failing test for exit codes**

```python
# tests/tools/__init__.py
```

```python
# tests/tools/test_common.py
"""Unit tests for runner.tools._common — exit codes, frontmatter parsing, CLI helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.tools import _common


def test_exit_codes_constants():
    assert _common.EXIT_OK == 0
    assert _common.EXIT_USER_ERROR == 2
    assert _common.EXIT_CONTRACT_VIOLATION == 3
    assert _common.EXIT_INTERNAL_ERROR == 4


def test_parse_frontmatter_happy(tmp_path: Path):
    path = tmp_path / "a.md"
    path.write_text("---\nkey: value\nnum: 3\n---\n\n## Body\n\ntext\n")
    fm, body = _common.parse_frontmatter(path)
    assert fm == {"key": "value", "num": 3}
    assert "## Body" in body


def test_parse_frontmatter_missing_delimiters_raises(tmp_path: Path):
    path = tmp_path / "b.md"
    path.write_text("no frontmatter here\n")
    with pytest.raises(_common.FrontmatterError):
        _common.parse_frontmatter(path)


def test_parse_frontmatter_invalid_yaml_raises(tmp_path: Path):
    path = tmp_path / "c.md"
    path.write_text("---\n: bad yaml :\n---\nbody\n")
    with pytest.raises(_common.FrontmatterError):
        _common.parse_frontmatter(path)


def test_emit_json_roundtrip(capsys):
    _common.emit_json({"a": 1, "b": [2, 3]})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"a": 1, "b": [2, 3]}
```

- [ ] **Step 2: Run tests — expect ModuleNotFoundError**

Run: `pytest tests/tools/test_common.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError: No module named 'runner'`.

- [ ] **Step 3: Create `runner/__init__.py` and `runner/tools/__init__.py`**

```python
# runner/__init__.py
```

```python
# runner/tools/__init__.py
```

- [ ] **Step 4: Implement `runner/tools/_common.py`**

```python
"""Shared utilities for runner.tools modules.

Contents:
  - Exit-code constants (spec §2.2).
  - YAML frontmatter parser used by schema validators and contract-diff tool.
  - JSON emitter for `--json` CLI switch.
  - argparse helpers (campaign_dir and json flags).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

EXIT_OK = 0
EXIT_USER_ERROR = 2
EXIT_CONTRACT_VIOLATION = 3
EXIT_INTERNAL_ERROR = 4


class FrontmatterError(Exception):
    """Raised when YAML frontmatter cannot be located or parsed."""


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Parse `---\\n<yaml>\\n---` from the top of a markdown file.

    Returns (frontmatter_dict, body_after_frontmatter).
    Raises FrontmatterError if delimiters are missing or YAML is invalid.
    """
    text = Path(path).read_text()
    if not text.startswith("---\n"):
        raise FrontmatterError(f"{path}: file does not begin with '---' delimiter")
    rest = text[4:]
    end = rest.find("\n---\n")
    if end < 0:
        # Accept trailing '---' with no newline too
        end_alt = rest.find("\n---")
        if end_alt < 0:
            raise FrontmatterError(f"{path}: no closing '---' delimiter found")
        fm_text = rest[:end_alt]
        body = rest[end_alt + 4 :]
    else:
        fm_text = rest[:end]
        body = rest[end + 5 :]
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"{path}: invalid YAML — {exc}") from exc
    if not isinstance(data, dict):
        raise FrontmatterError(f"{path}: frontmatter must be a YAML mapping, got {type(data).__name__}")
    return data, body


def emit_json(payload: Any) -> None:
    """Write payload as a single compact JSON line to stdout and flush."""
    json.dump(payload, sys.stdout, separators=(",", ":"), sort_keys=True)
    sys.stdout.write("\n")
    sys.stdout.flush()


def add_standard_args(parser: argparse.ArgumentParser) -> None:
    """Add --campaign-dir and --json to a tool's argparse parser."""
    parser.add_argument(
        "--campaign-dir",
        default="runner/",
        help="Path to the runner campaign directory (default: runner/).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit result as a single JSON line on stdout.",
    )
```

- [ ] **Step 5: Run tests — expect all pass**

Run: `pytest tests/tools/test_common.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add runner/__init__.py runner/tools/__init__.py runner/tools/_common.py tests/tools/__init__.py tests/tools/test_common.py
git commit -m "feat(runner): add tools package skeleton and shared utilities"
```

---

## Task 3: Schema validator for all artifacts (spec §5.2, §8.1 item 7)

**Files:**
- Create: `runner/tools/schema.py`
- Create: `tests/schemas/__init__.py`
- Create: `tests/schemas/test_validators.py`
- Create: `tests/schemas/fixtures/` (directory with golden-good artifact files)

The validator implements **Reviewer rejection rules** at the artifact level. Every required frontmatter field and every required numbered H2 section from spec §2.3 is enforced here.

- [ ] **Step 1: Write failing test for PROBLEM_CONTRACT validator (happy path)**

```python
# tests/schemas/__init__.py
```

```python
# tests/schemas/test_validators.py
"""Schema validation tests for all runner artifacts (spec §2.3 / §5.2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# PROBLEM_CONTRACT
# ---------------------------------------------------------------------------

def test_problem_contract_good(tmp_path: Path):
    path = FIXTURES / "problem_contract_good.md"
    errors = schema.validate_problem_contract(path)
    assert errors == []


def test_problem_contract_missing_task_type(tmp_path: Path):
    src = (FIXTURES / "problem_contract_good.md").read_text()
    # Remove the task_type line
    broken = "\n".join(line for line in src.splitlines() if not line.startswith("task_type:"))
    path = tmp_path / "pc.md"
    path.write_text(broken)
    errors = schema.validate_problem_contract(path)
    assert any("task_type" in e for e in errors)


def test_problem_contract_bad_task_type(tmp_path: Path):
    src = (FIXTURES / "problem_contract_good.md").read_text()
    broken = src.replace('task_type: "binary_classification"', 'task_type: "magic"')
    path = tmp_path / "pc.md"
    path.write_text(broken)
    errors = schema.validate_problem_contract(path)
    assert any("task_type" in e and "magic" in e for e in errors)


def test_problem_contract_missing_section(tmp_path: Path):
    src = (FIXTURES / "problem_contract_good.md").read_text()
    broken = src.replace("## 3. Success criteria (detail)", "## 3. Something else")
    path = tmp_path / "pc.md"
    path.write_text(broken)
    errors = schema.validate_problem_contract(path)
    assert any("section" in e.lower() and "3" in e for e in errors)


# ---------------------------------------------------------------------------
# NEXT_EXPERIMENT
# ---------------------------------------------------------------------------

def test_next_experiment_good():
    errors = schema.validate_next_experiment(FIXTURES / "next_experiment_good.md")
    assert errors == []


def test_next_experiment_bad_action_type(tmp_path: Path):
    src = (FIXTURES / "next_experiment_good.md").read_text()
    broken = src.replace('action_type: "A_hp"', 'action_type: "A_nonsense"')
    path = tmp_path / "ne.md"
    path.write_text(broken)
    allowed = ["A_hp", "A_model", "A_feature"]
    errors = schema.validate_next_experiment(path, allowed_action_types=allowed)
    assert any("action_type" in e for e in errors)


def test_next_experiment_helpers_declared_mismatch(tmp_path: Path):
    src = (FIXTURES / "next_experiment_good.md").read_text()
    broken = src.replace(
        "touches_helpers: false",
        "touches_helpers: true",
    )
    path = tmp_path / "ne.md"
    path.write_text(broken)
    errors = schema.validate_next_experiment(path)
    assert any("helpers_declared" in e for e in errors)


def test_next_experiment_escalation_without_section(tmp_path: Path):
    src = (FIXTURES / "next_experiment_good.md").read_text()
    broken = src.replace("escalation: null", 'escalation: "C2"')
    path = tmp_path / "ne.md"
    path.write_text(broken)
    errors = schema.validate_next_experiment(path)
    assert any("§6" in e or "Escalation" in e for e in errors)


# ---------------------------------------------------------------------------
# EVAL_PROTOCOL
# ---------------------------------------------------------------------------

def test_eval_protocol_good():
    errors = schema.validate_eval_protocol(FIXTURES / "eval_protocol_good.md")
    assert errors == []


def test_eval_protocol_bad_direction(tmp_path: Path):
    src = (FIXTURES / "eval_protocol_good.md").read_text()
    broken = src.replace('direction: "maximize"', 'direction: "sideways"')
    path = tmp_path / "ep.md"
    path.write_text(broken)
    errors = schema.validate_eval_protocol(path)
    assert any("direction" in e for e in errors)


# ---------------------------------------------------------------------------
# CAMPAIGN_STATE
# ---------------------------------------------------------------------------

def test_campaign_state_good():
    errors = schema.validate_campaign_state(FIXTURES / "campaign_state_good.json")
    assert errors == []


def test_campaign_state_bad_round_type(tmp_path: Path):
    import json as j
    data = j.loads((FIXTURES / "campaign_state_good.json").read_text())
    data["round"] = "seven"
    path = tmp_path / "cs.json"
    path.write_text(j.dumps(data))
    errors = schema.validate_campaign_state(path)
    assert any("round" in e for e in errors)
```

- [ ] **Step 2: Run tests — expect `ModuleNotFoundError` then missing-fixture errors**

Run: `pytest tests/schemas/test_validators.py -v 2>&1 | tail -20`
Expected: import error for `runner.tools.schema`.

- [ ] **Step 3: Create golden-good fixture files**

```markdown
<!-- tests/schemas/fixtures/problem_contract_good.md -->
---
schema_version: 1
campaign_id: "tiny-binary-test"
problem_title: "Tiny test binary classification"
task_type: "binary_classification"
unit_of_observation: "row"
target:
  name: "Class"
  positive_class: 1
  definition: "Synthetic positive class."
success_criteria:
  - "val_pr_auc >= 0.50"
constraints:
  - "Single-file train.py."
non_goals:
  - "No deployment."
approved_at: "2026-04-21"
approved_by: "test"
---

## 1. Task

Synthetic tiny binary classification.

## 2. Why the task matters

Test fixture.

## 3. Success criteria (detail)

Must beat 0.50.

## 4. Constraints (detail)

One file.

## 5. Non-goals (detail)

No deployment.
```

```markdown
<!-- tests/schemas/fixtures/next_experiment_good.md -->
---
schema_version: 1
campaign_id: "tiny-binary-test"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "Tighter depth range converges faster."
expected_effect_size: 0.005
base_commit: "abcdef012345"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary

Baseline at 0.65; Optuna explored wide range.

## 2. Evidence from memory

- results_query: top-5 shown below.
- dead_ends_query: no matches.
- NOTEBOOK observations: none relevant.

## 3. Plan

1. In `train.py`, narrow max_depth range.

## 4. Helpers

None.

## 5. How this differs from prior experiments

Prior experiments used the full range.

## 6. Escalation (only if `escalation` frontmatter is non-null)

N/A.
```

```markdown
<!-- tests/schemas/fixtures/eval_protocol_good.md -->
---
schema_version: 1
campaign_id: "tiny-binary-test"
primary_metric:
  name: "pr_auc"
  direction: "maximize"
  noise_floor: 0.005
acceptance_threshold:
  baseline_family: "logreg"
  min_improvement: 0.01
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: "Test fixture."
bootstrap_ci:
  enabled: true
  n_boot: 200
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools:
  - "tools/anomaly.py"
action_types:
  - "A_hp"
  - "A_model"
budgets:
  time_budget_s: 30
  hard_timeout_s: 60
  max_experiments: 5
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

Test fixture.

## 2. How keep/discard is decided

Δ > 0 AND no mandatory tool regression.

## 3. How plateau is handled

Planner emits C2.

## 4. Contract change policy

Use tools/contract_diff + human approval.
```

```json
// tests/schemas/fixtures/campaign_state_good.json
{
  "$schema_version": 1,
  "campaign_id": "tiny-binary-test",
  "round": 0,
  "exp_id_counter": 0,
  "last_commit": null,
  "last_verdict": null,
  "best_so_far": {
    "commit": null,
    "primary_metric": null
  },
  "consecutive_discards": 0,
  "budget_used": 0,
  "budget_total": 5,
  "created_at": "2026-04-21T12:00:00Z",
  "updated_at": "2026-04-21T12:00:00Z"
}
```

- [ ] **Step 4: Implement `runner/tools/schema.py`**

Create `runner/tools/schema.py`. This is the single source of truth for Reviewer rejection rules §8.3 items 1–4.

```python
"""Schema validators for all runner artifacts.

Each validator returns a list of error strings. Empty list means valid.
The error messages are human-readable and include the field or section name
so the Reviewer / driver can surface them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runner.tools._common import FrontmatterError, parse_frontmatter


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

_ALLOWED_TASK_TYPES = {
    "binary_classification",
    "multiclass_classification",
    "regression",
    "clustering",
    "anomaly_detection",
}

_H2_NUMBERED = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)


def _required_keys(d: dict, keys: list[str], prefix: str = "") -> list[str]:
    errors = []
    for k in keys:
        if k not in d or d[k] is None:
            errors.append(f"missing required frontmatter field: {prefix}{k}")
    return errors


def _check_numbered_sections(body: str, expected: list[tuple[int, str]]) -> list[str]:
    """expected: list of (number, prefix-of-title). Section title must start
    with the given prefix (case-insensitive) so non-core wording can change."""
    found = {int(m.group(1)): m.group(2).strip() for m in _H2_NUMBERED.finditer(body)}
    errors = []
    for num, title_prefix in expected:
        if num not in found:
            errors.append(f"missing required section: ## {num}.")
            continue
        title = found[num].lower()
        if not title.startswith(title_prefix.lower()):
            errors.append(
                f"section ## {num}. has wrong title: expected prefix '{title_prefix}', "
                f"found '{found[num]}'"
            )
    return errors


# ---------------------------------------------------------------------------
# PROBLEM_CONTRACT
# ---------------------------------------------------------------------------

_PC_REQUIRED = [
    "schema_version", "campaign_id", "problem_title", "task_type",
    "unit_of_observation", "target", "success_criteria", "constraints",
    "non_goals",
]
_PC_SECTIONS = [
    (1, "Task"), (2, "Why"), (3, "Success"), (4, "Constraints"), (5, "Non-goals"),
]


def validate_problem_contract(path: Path) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _PC_REQUIRED)
    if fm.get("task_type") is not None and fm["task_type"] not in _ALLOWED_TASK_TYPES:
        errors.append(
            f"task_type {fm['task_type']!r} not in {sorted(_ALLOWED_TASK_TYPES)}"
        )
    tgt = fm.get("target") or {}
    if isinstance(tgt, dict):
        for k in ("name", "definition"):
            if k not in tgt or tgt[k] is None:
                errors.append(f"missing required frontmatter field: target.{k}")
    errors += _check_numbered_sections(body, _PC_SECTIONS)
    return errors


# ---------------------------------------------------------------------------
# DATA_CONTRACT
# ---------------------------------------------------------------------------

_DC_REQUIRED = [
    "schema_version", "campaign_id", "data_sources", "temporal",
    "columns", "leakage_audit", "splits",
]
_DC_SECTIONS = [
    (1, "Schema summary"), (2, "Availability"), (3, "Leakage"),
    (4, "Transformations"), (5, "Known data quality"),
]


def validate_data_contract(path: Path) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _DC_REQUIRED)
    la = fm.get("leakage_audit") or {}
    if isinstance(la, dict) and la.get("performed_at") in (None, ""):
        errors.append("leakage_audit.performed_at must be set before G2 sign-off")
    errors += _check_numbered_sections(body, _DC_SECTIONS)
    return errors


# ---------------------------------------------------------------------------
# EVAL_PROTOCOL
# ---------------------------------------------------------------------------

_EP_REQUIRED = [
    "schema_version", "campaign_id", "primary_metric", "acceptance_threshold",
    "cv_scheme", "bootstrap_ci", "paired_test", "mandatory_tools",
    "action_types", "budgets", "plateau_trigger", "anomaly",
]
_EP_SECTIONS = [
    (1, "Rationale"), (2, "How keep/discard"), (3, "How plateau"),
    (4, "Contract change"),
]
_ALLOWED_DIRECTIONS = {"maximize", "minimize"}


def validate_eval_protocol(path: Path) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _EP_REQUIRED)
    pm = fm.get("primary_metric") or {}
    if isinstance(pm, dict):
        if pm.get("direction") not in _ALLOWED_DIRECTIONS:
            errors.append(
                f"primary_metric.direction must be one of {sorted(_ALLOWED_DIRECTIONS)}"
            )
        if "name" not in pm:
            errors.append("missing required frontmatter field: primary_metric.name")
    budgets = fm.get("budgets") or {}
    if isinstance(budgets, dict):
        mra = budgets.get("max_repair_attempts")
        if mra is not None and (not isinstance(mra, int) or mra != 2):
            errors.append("budgets.max_repair_attempts is a hard invariant (must be 2)")
    errors += _check_numbered_sections(body, _EP_SECTIONS)
    return errors


# ---------------------------------------------------------------------------
# NEXT_EXPERIMENT
# ---------------------------------------------------------------------------

_NE_REQUIRED = [
    "schema_version", "campaign_id", "round", "planner_invocation_at",
    "action_type", "hypothesis", "expected_effect_size", "base_commit",
    "touches_helpers", "helpers_declared", "escalation",
]
_NE_SECTIONS = [
    (1, "Context"), (2, "Evidence"), (3, "Plan"),
    (4, "Helpers"), (5, "How this differs"), (6, "Escalation"),
]
_ALLOWED_ESCALATIONS = {None, "C2", "C3"}


def validate_next_experiment(
    path: Path,
    allowed_action_types: list[str] | None = None,
) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors: list[str] = []
    for k in _NE_REQUIRED:
        if k not in fm:
            errors.append(f"missing required frontmatter field: {k}")
    if allowed_action_types is not None and fm.get("action_type") not in allowed_action_types:
        errors.append(
            f"action_type {fm.get('action_type')!r} not in allowed {allowed_action_types}"
        )
    if fm.get("touches_helpers") is True and not (fm.get("helpers_declared") or []):
        errors.append("touches_helpers=true but helpers_declared is empty")
    esc = fm.get("escalation")
    if esc not in _ALLOWED_ESCALATIONS:
        errors.append(f"escalation must be null|'C2'|'C3', got {esc!r}")
    errors += _check_numbered_sections(body, _NE_SECTIONS)
    if esc in {"C2", "C3"}:
        # Must also have the detailed subsection header inside §6
        if "### For " not in body:
            errors.append(
                f"escalation={esc} set but §6 lacks '### For C2' or '### For C3' subsection"
            )
    return errors


# ---------------------------------------------------------------------------
# CAMPAIGN_STATE
# ---------------------------------------------------------------------------

_CS_REQUIRED_KEYS = [
    "$schema_version", "campaign_id", "round", "exp_id_counter",
    "last_commit", "last_verdict", "best_so_far", "consecutive_discards",
    "budget_used", "budget_total", "created_at", "updated_at",
]


def validate_campaign_state(path: Path) -> list[str]:
    try:
        data = json.loads(Path(path).read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return [f"cannot read campaign_state: {exc}"]
    errors: list[str] = []
    for k in _CS_REQUIRED_KEYS:
        if k not in data:
            errors.append(f"missing required key: {k}")
    for k in ("round", "exp_id_counter", "consecutive_discards", "budget_used", "budget_total"):
        if k in data and not isinstance(data[k], int):
            errors.append(f"{k} must be int, got {type(data[k]).__name__}")
    return errors


# ---------------------------------------------------------------------------
# REVIEW.md — lightweight (we only check frontmatter since the file accumulates)
# ---------------------------------------------------------------------------

_REVIEW_REQUIRED = ["schema_version", "campaign_id", "last_round", "last_verdict"]
_ALLOWED_VERDICTS = {"keep", "discard", "anomaly", "crash", "malformed"}


def validate_review(path: Path) -> list[str]:
    try:
        fm, _body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _REVIEW_REQUIRED)
    if fm.get("last_verdict") not in _ALLOWED_VERDICTS and fm.get("last_verdict") is not None:
        errors.append(
            f"last_verdict {fm.get('last_verdict')!r} not in {sorted(_ALLOWED_VERDICTS)}"
        )
    return errors
```

- [ ] **Step 5: Run tests — expect all pass**

Run: `pytest tests/schemas/ -v`
Expected: 11 passed (4 PROBLEM_CONTRACT + 4 NEXT_EXPERIMENT + 2 EVAL_PROTOCOL + 2 CAMPAIGN_STATE = 12; we have 11 — re-verify).

Actually running against what we wrote above: 4 PC + 4 NE + 2 EP + 2 CS = 12. Expected: **12 passed**. If count differs, the test file has a miscount — re-read and fix.

- [ ] **Step 6: Commit**

```bash
git add runner/tools/schema.py tests/schemas/__init__.py tests/schemas/test_validators.py tests/schemas/fixtures/
git commit -m "feat(runner): add artifact schema validators (PROBLEM/DATA/EVAL/NEXT_EXPERIMENT/CAMPAIGN_STATE/REVIEW)"
```

---

## Task 4: `runner/` directory scaffold with RUNNER.md and AGENTS.md

**Files:**
- Create: `runner/RUNNER.md`
- Create: `runner/AGENTS.md`
- Create: `runner/state/.gitkeep`
- Create: `runner/experiment_helpers/.gitkeep`
- Create: `runner/contracts/.gitkeep`
- Create: `runner/roles/.gitkeep`

- [ ] **Step 1: Write `runner/RUNNER.md`**

```markdown
# RUNNER.md — Autonomous ML Runner entry point

You are running an autonomous ML experiment campaign. **Read this file first, then follow pointers.**

## 0. Orientation

- Problem + success criteria: `runner/contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `runner/contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `runner/contracts/EVAL_PROTOCOL.md` (G3) — names mandatory tools, budgets
- Current state: `runner/state/CAMPAIGN_STATE.json`
- History: `runner/state/results.tsv`, `runner/state/REVIEW.md`
- Memory: `runner/state/DEAD_ENDS.md`, `runner/state/NOTEBOOK.md`
- Priors (cross-campaign): `runner/contracts/PRIORS.md`

## 1. Your role for this turn

Pick the role that matches the current state:

- **Planner** — invoked when state expects a new `NEXT_EXPERIMENT.md`. Read `runner/roles/planner.md`.
- **Executor** — invoked after Planner and driver validated the plan. Read `runner/roles/executor.md`.
- **Reviewer** — invoked after Executor run. Read `runner/roles/reviewer.md`.

The driver (`runner/run_round.sh`) tells you which role to play.

## 2. Hard invariants (never bypass)

1. G1–G3 signed before any experiment (driver refuses to init otherwise).
2. `runner/tools/anomaly.py` runs before any `keep` verdict.
3. Mandatory tools named in `EVAL_PROTOCOL.md §mandatory_tools` run before accepting small Δ.
4. One git commit per experiment — driver enforces.
5. Two repair attempts cap — Executor enforces.
6. Contracts are sticky — change only via C3 (approved diff).

## 3. Fossil record

Harness rules, lessons, and rules that apply across campaigns live in `runner/AGENTS.md`. Read it every role invocation.
```

- [ ] **Step 2: Write `runner/AGENTS.md`**

```markdown
# AGENTS.md — Harness fossil record (M4)

**Scope:** All campaigns, all problems. Human-curated (or agent+human via C3). Read every role invocation.

## Lessons that became rules

### Evaluation reliability (from mar30–apr03 campaigns, reflection §7)

- Single-split PR-AUC on ~100 positives has CI ≈ ±0.005–0.010. Treat any Δ below `EVAL_PROTOCOL.primary_metric.noise_floor` as noise.
- Prefer `tools/bootstrap_ci` or `tools/cv_runner` when `EVAL_PROTOCOL.cv_scheme.n_splits >= 5`.

### Reason strategically, compute tactically (reflection §4)

- Model-family choice, problem framing, diagnosis → LLM reasoning.
- HP numerical search, CI computation, permutation importance → `runner/tools/*`.
- Do not hand-pick HP values. Use `tools/optuna_search` or declare a space inside `train.py`.

### Artifact-first discipline

- Every decision lives on disk. Chat is ephemeral.
- Reviewer never reads Executor chat; it reads `train.py`, `run.log`, `NEXT_EXPERIMENT.md`, and tool outputs.

### Producer ≠ verifier

- Each role is a fresh invocation with ONLY its §2 Inputs files.

### Bounded repair

- Executor has 2 attempts (Stripe cap). Structural failures escalate immediately.

## Known dead-ends that generalize across problems

(None yet promoted. Planner reads `runner/state/DEAD_ENDS.md` for campaign-specific lines; only structurally reusable ones are promoted here by human.)

## Harness changes (when to update this file)

Update when:
- A repeated surprise reveals a missing guardrail.
- Post-G4 review identifies a rule that applies to future campaigns.
- A contract mutation (C3) establishes a new invariant.
```

- [ ] **Step 3: Create directory placeholders**

```bash
mkdir -p runner/state runner/experiment_helpers runner/contracts runner/roles
touch runner/state/.gitkeep runner/experiment_helpers/.gitkeep runner/contracts/.gitkeep runner/roles/.gitkeep
```

- [ ] **Step 4: Verify tree**

Run: `find runner -type d | sort`
Expected output includes: `runner`, `runner/contracts`, `runner/experiment_helpers`, `runner/roles`, `runner/state`, `runner/tools`.

- [ ] **Step 5: Commit**

```bash
git add runner/RUNNER.md runner/AGENTS.md runner/state/.gitkeep runner/experiment_helpers/.gitkeep runner/contracts/.gitkeep runner/roles/.gitkeep
git commit -m "feat(runner): add RUNNER.md + AGENTS.md + directory scaffold"
```

---

## Task 5: `log.py` — results.tsv append + CAMPAIGN_STATE.json update

**Files:**
- Create: `log.py` (repo root)
- Create: `tests/test_log.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_log.py
"""Unit tests for log.py — results.tsv append + CAMPAIGN_STATE.json update."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import log


RESULTS_HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text(RESULTS_HEADER)
    (root / "state" / "CAMPAIGN_STATE.json").write_text(json.dumps({
        "$schema_version": 1,
        "campaign_id": "tiny",
        "round": 0,
        "exp_id_counter": 0,
        "last_commit": None,
        "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0,
        "budget_used": 0,
        "budget_total": 5,
        "created_at": "2026-04-21T12:00:00Z",
        "updated_at": "2026-04-21T12:00:00Z",
    }))
    return root


def test_append_result_keep_updates_best_and_resets_discards(campaign: Path):
    log.append_result(
        commit="abc123",
        metrics={"val_pr_auc": 0.71, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        status="keep",
        action_type="A_model",
        hypothesis="try lightgbm",
        description="baseline LGBM",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc",
        direction="maximize",
    )
    lines = (campaign / "state" / "results.tsv").read_text().splitlines()
    assert len(lines) == 2  # header + 1 row
    assert lines[1].startswith("abc123\t0.71\t5.0\t0.8\t0.7\tkeep")
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["round"] == 1
    assert state["last_commit"] == "abc123"
    assert state["last_verdict"] == "keep"
    assert state["best_so_far"]["primary_metric"] == 0.71
    assert state["best_so_far"]["commit"] == "abc123"
    assert state["consecutive_discards"] == 0
    assert state["budget_used"] == 1


def test_append_result_discard_increments_consecutive(campaign: Path):
    log.append_result(
        commit="aaa",
        metrics={"val_pr_auc": 0.6, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.5},
        status="keep",
        action_type="A_model", hypothesis="h", description="d",
        model_family="xgboost", n_features=8,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="maximize",
    )
    log.append_result(
        commit="bbb",
        metrics={"val_pr_auc": 0.55, "lift_at_10": 3.0, "macro_f1": 0.6, "val_f1": 0.4},
        status="discard",
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=8,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="maximize",
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 1
    assert state["best_so_far"]["primary_metric"] == 0.6  # unchanged
    assert state["round"] == 2


def test_append_result_anomaly_does_not_bump_discards(campaign: Path):
    log.append_result(
        commit="xyz",
        metrics={"val_pr_auc": 0.3, "lift_at_10": 2.0, "macro_f1": 0.4, "val_f1": 0.2},
        status="anomaly",
        action_type="A_diagnose", hypothesis="h", description="d",
        model_family="lightgbm", n_features=8,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="maximize",
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0
    assert state["last_verdict"] == "anomaly"


def test_append_result_minimize_direction(campaign: Path):
    log.append_result(
        commit="m1",
        metrics={"val_pr_auc": 0.20, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        status="keep",
        action_type="A_model", hypothesis="h", description="d",
        model_family="other", n_features=5,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="minimize",
    )
    log.append_result(
        commit="m2",
        metrics={"val_pr_auc": 0.30, "lift_at_10": 0.0, "macro_f1": 0.0, "val_f1": 0.0},
        status="keep",
        action_type="A_model", hypothesis="h", description="d",
        model_family="other", n_features=5,
        campaign_dir=str(campaign),
        primary_metric_name="val_pr_auc", direction="minimize",
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    # Minimize: 0.20 is better than 0.30 → best should stay at m1
    assert state["best_so_far"]["commit"] == "m1"
    assert state["best_so_far"]["primary_metric"] == 0.20
```

- [ ] **Step 2: Run tests — expect ModuleNotFoundError**

Run: `pytest tests/test_log.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError: No module named 'log'`.

- [ ] **Step 3: Implement `log.py`**

```python
"""log.py — results.tsv append + CAMPAIGN_STATE.json update.

Owned utility invoked by the runner driver after a Reviewer verdict. Kept
intentionally small (~100 LOC with docstrings) per spec §2.4 — preserves
the legacy abes_engine results.tsv schema exactly.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Literal

Verdict = Literal["keep", "discard", "anomaly", "crash", "malformed"]
Direction = Literal["maximize", "minimize"]

_RESULTS_HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_better(candidate: float, incumbent: float | None, direction: Direction) -> bool:
    if incumbent is None:
        return True
    if direction == "maximize":
        return candidate > incumbent
    return candidate < incumbent


def append_result(
    commit: str,
    metrics: dict,
    status: Verdict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
    primary_metric_name: str = "val_pr_auc",
    direction: Direction = "maximize",
) -> None:
    """Append one row to `<campaign_dir>/state/results.tsv` and update
    `<campaign_dir>/state/CAMPAIGN_STATE.json`.

    Safe to call with metrics set to zeros when status == "crash" or "malformed".
    """
    camp = Path(campaign_dir)
    results_path = camp / "state" / "results.tsv"
    state_path = camp / "state" / "CAMPAIGN_STATE.json"

    if not results_path.exists():
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(_RESULTS_HEADER)

    # Tab-safe escape: replace tabs and newlines in free-text fields
    def _clean(s: str) -> str:
        return str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")

    row = "\t".join([
        commit,
        f"{float(metrics.get('val_pr_auc', 0.0))}",
        f"{float(metrics.get('lift_at_10', 0.0))}",
        f"{float(metrics.get('macro_f1', 0.0))}",
        f"{float(metrics.get('val_f1', 0.0))}",
        status,
        str(int(n_features)),
        model_family,
        action_type,
        _clean(hypothesis),
        _clean(description),
    ]) + "\n"
    with results_path.open("a", encoding="utf-8") as fp:
        fp.write(row)

    # Update CAMPAIGN_STATE.json
    state = json.loads(state_path.read_text())
    primary = float(metrics.get(primary_metric_name, 0.0))

    state["round"] = int(state.get("round", 0)) + 1
    state["exp_id_counter"] = int(state.get("exp_id_counter", 0)) + 1
    state["last_commit"] = commit
    state["last_verdict"] = status
    state["budget_used"] = int(state.get("budget_used", 0)) + 1
    state["updated_at"] = _now_iso()

    # consecutive_discards semantics (spec §3.2 final bullet):
    #   keep    → reset
    #   discard | crash | malformed → increment
    #   anomaly → unchanged
    if status == "keep":
        state["consecutive_discards"] = 0
    elif status in ("discard", "crash", "malformed"):
        state["consecutive_discards"] = int(state.get("consecutive_discards", 0)) + 1
    # anomaly: leave unchanged

    # best_so_far — only on keep; anomaly/crash/malformed never update best
    if status == "keep":
        incumbent = (state.get("best_so_far") or {}).get("primary_metric")
        if _is_better(primary, incumbent, direction):
            state["best_so_far"] = {"commit": commit, "primary_metric": primary}

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/test_log.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add log.py tests/test_log.py
git commit -m "feat: add log.py (results.tsv append + CAMPAIGN_STATE.json update)"
```

---

# Phase B — Within-loop tools

## Task 6: `tools/anomaly.py`

**Files:**
- Create: `runner/tools/anomaly.py`
- Create: `tests/tools/test_anomaly.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_anomaly.py
from __future__ import annotations

import pytest

from runner.tools import anomaly


def test_anomaly_fires_below_floor():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.40, "status": "keep", "model_family": "lgb"},
        history=[],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is True
    assert "below" in res["reason"].lower()


def test_anomaly_fires_relative_to_best():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.30, "status": "keep", "model_family": "lgb"},
        history=[{"val_pr_auc": 0.80, "status": "keep"}],
        floor=0.10,
        primary_metric="val_pr_auc",
        relative=0.5,
    )
    # 0.30 < 0.5 * 0.80 = 0.40 → fires
    assert res["fired"] is True


def test_anomaly_does_not_fire_when_good():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.85, "status": "keep", "model_family": "xgb"},
        history=[{"val_pr_auc": 0.80, "status": "keep"}],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is False


def test_anomaly_skips_crash_rows():
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.0, "status": "crash", "model_family": "lgb"},
        history=[],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is False
    assert "crash" in res["reason"].lower()


def test_anomaly_determinism():
    args = dict(
        latest_row={"val_pr_auc": 0.40, "status": "keep", "model_family": "lgb"},
        history=[],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert anomaly.check_anomaly(**args) == anomaly.check_anomaly(**args)
```

- [ ] **Step 2: Run tests — expect module-not-found**

Run: `pytest tests/tools/test_anomaly.py -v 2>&1 | tail -10`
Expected: import error for `runner.tools.anomaly`.

- [ ] **Step 3: Implement `runner/tools/anomaly.py`**

```python
"""Anomaly detector (spec §2.2.2).

Simplified port of abes_engine.cmd_check's anomaly branch — ~30 lines of
logic. Fires when the latest non-crash result is implausibly low relative
to an absolute floor and/or to the running best.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from runner.tools._common import EXIT_OK, EXIT_USER_ERROR, emit_json


def check_anomaly(
    latest_row: dict[str, Any],
    history: list[dict[str, Any]],
    floor: float = 0.75,
    primary_metric: str = "val_pr_auc",
    relative: float = 0.5,
) -> dict[str, Any]:
    """Return {'fired': bool, 'reason': str, 'proposed_diagnostic': str}.

    Fires if `status != 'crash'` AND 0 < latest[primary_metric] < max(floor, relative * best_prior).
    """
    status = latest_row.get("status", "")
    if status == "crash":
        return {
            "fired": False,
            "reason": "skipped (status=crash)",
            "proposed_diagnostic": "",
        }
    try:
        value = float(latest_row.get(primary_metric, 0.0))
    except (TypeError, ValueError):
        return {
            "fired": False,
            "reason": f"skipped (cannot parse {primary_metric})",
            "proposed_diagnostic": "",
        }
    # Compute best prior from non-crash history
    best_prior = 0.0
    for row in history:
        if row.get("status") == "crash":
            continue
        try:
            best_prior = max(best_prior, float(row.get(primary_metric, 0.0)))
        except (TypeError, ValueError):
            continue
    threshold = max(floor, relative * best_prior) if best_prior > 0 else floor
    if 0 < value < threshold:
        family = latest_row.get("model_family", "unknown")
        return {
            "fired": True,
            "reason": f"{primary_metric}={value:.6f} below threshold={threshold:.6f} (floor={floor}, rel={relative}*best={best_prior:.6f})",
            "proposed_diagnostic": (
                f"Add `print(model.predict_proba(X_val[:5]))` to diagnose probability "
                f"inversion; do NOT dismiss {family} from one anomalous result."
            ),
        }
    return {
        "fired": False,
        "reason": f"{primary_metric}={value:.6f} within expected range (threshold={threshold:.6f})",
        "proposed_diagnostic": "",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Anomaly check for a single experiment result.")
    p.add_argument("--latest-json", required=True, help="JSON string or @path to file with the latest row dict.")
    p.add_argument("--history-json", default="[]", help="JSON string or @path with history list[dict].")
    p.add_argument("--floor", type=float, default=0.75)
    p.add_argument("--primary-metric", default="val_pr_auc")
    p.add_argument("--relative", type=float, default=0.5)
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    def _load(spec: str):
        if spec.startswith("@"):
            return json.loads(open(spec[1:]).read())
        return json.loads(spec)

    try:
        latest = _load(args.latest_json)
        history = _load(args.history_json)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    result = check_anomaly(
        latest_row=latest,
        history=history,
        floor=args.floor,
        primary_metric=args.primary_metric,
        relative=args.relative,
    )
    if args.json_output:
        emit_json(result)
    else:
        print(f"fired: {result['fired']}")
        print(f"reason: {result['reason']}")
        if result["proposed_diagnostic"]:
            print(f"proposed_diagnostic: {result['proposed_diagnostic']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_anomaly.py -v`
Expected: 5 passed.

- [ ] **Step 5: Smoke-test the CLI**

Run: `python3 runner/tools/anomaly.py --latest-json '{"val_pr_auc": 0.4, "status": "keep", "model_family": "xgb"}' --history-json '[]' --floor 0.75`
Expected output contains `fired: True`.

- [ ] **Step 6: Commit**

```bash
git add runner/tools/anomaly.py tests/tools/test_anomaly.py
git commit -m "feat(tools): add anomaly detector"
```

---

## Task 7: `tools/results_query.py`

**Files:**
- Create: `runner/tools/results_query.py`
- Create: `tests/tools/test_results_query.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_results_query.py
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import results_query


HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)
ROWS = [
    "a1\t0.80\t5.0\t0.8\t0.7\tkeep\t10\txgboost\tA_model\thyp\tdesc\n",
    "b2\t0.50\t2.0\t0.4\t0.3\tdiscard\t10\tlightgbm\tA_hp\thyp\tdesc\n",
    "c3\t0.00\t0.0\t0.0\t0.0\tcrash\t10\tlightgbm\tA_hp\thyp\tdesc\n",
    "d4\t0.85\t6.0\t0.85\t0.8\tkeep\t12\txgboost\tA_feature\thyp\tdesc\n",
]


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text(HEADER + "".join(ROWS))
    return root


def test_results_query_top_k_desc(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign), order_by="val_pr_auc", limit=2,
    )
    assert [r["commit"] for r in rows] == ["d4", "a1"]


def test_results_query_filter_excludes_crash(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign),
        filter_expr="status != 'crash'",
        limit=10,
    )
    assert "c3" not in [r["commit"] for r in rows]


def test_results_query_filter_by_family(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign),
        filter_expr="model_family == 'xgboost'",
        limit=5,
    )
    assert sorted(r["commit"] for r in rows) == ["a1", "d4"]


def test_results_query_returns_empty_on_no_match(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign),
        filter_expr="model_family == 'catboost'",
    )
    assert rows == []


def test_results_query_schema_mismatch_raises(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text("wrong\theader\n")
    with pytest.raises(results_query.SchemaMismatchError):
        results_query.results_query(campaign_dir=str(root))
```

- [ ] **Step 2: Run tests — expect module-not-found**

Run: `pytest tests/tools/test_results_query.py -v 2>&1 | tail -10`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/results_query.py`**

```python
"""Memory query over results.tsv (spec §2.2.3).

Returns top rows filtered + ordered. Schema mismatch raises
SchemaMismatchError, mapped to exit code 3 in the CLI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_OK,
    EXIT_USER_ERROR,
    emit_json,
)

EXPECTED_COLUMNS = [
    "commit", "val_pr_auc", "lift_at_10", "macro_f1", "val_f1",
    "status", "n_features", "model_family", "action_type",
    "hypothesis", "description",
]
_NUMERIC = {"val_pr_auc", "lift_at_10", "macro_f1", "val_f1", "n_features"}


class SchemaMismatchError(Exception):
    """results.tsv header does not match the expected schema."""


def results_query(
    filter_expr: str = "status != 'crash'",
    order_by: str = "val_pr_auc",
    limit: int = 10,
    campaign_dir: str = "runner/",
    ascending: bool = False,
) -> list[dict]:
    path = Path(campaign_dir) / "state" / "results.tsv"
    if not path.exists():
        return []
    df = pd.read_csv(path, sep="\t")
    if list(df.columns) != EXPECTED_COLUMNS:
        raise SchemaMismatchError(
            f"results.tsv columns do not match expected schema. "
            f"Expected {EXPECTED_COLUMNS}, got {list(df.columns)}"
        )
    for col in _NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if filter_expr:
        df = df.query(filter_expr)
    if order_by in df.columns:
        df = df.sort_values(by=order_by, ascending=ascending)
    if limit is not None and limit > 0:
        df = df.head(limit)
    return df.to_dict(orient="records")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Query runner/state/results.tsv.")
    p.add_argument("--filter", default="status != 'crash'", dest="filter_expr")
    p.add_argument("--order-by", default="val_pr_auc")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--ascending", action="store_true")
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    try:
        rows = results_query(
            filter_expr=args.filter_expr,
            order_by=args.order_by,
            limit=args.limit,
            campaign_dir=args.campaign_dir,
            ascending=args.ascending,
        )
    except SchemaMismatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    if args.json_output:
        emit_json(rows)
    else:
        if not rows:
            print("(no rows)")
        else:
            cols = ["commit", "val_pr_auc", "status", "model_family", "action_type"]
            for r in rows:
                print("  ".join(f"{r.get(c, ''):>12}" for c in cols))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_results_query.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/results_query.py tests/tools/test_results_query.py
git commit -m "feat(tools): add results_query over results.tsv"
```

---

## Task 8: `tools/dead_ends_query.py`

**Files:**
- Create: `runner/tools/dead_ends_query.py`
- Create: `tests/tools/test_dead_ends_query.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_dead_ends_query.py
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import dead_ends_query


DEAD_ENDS = """---
schema_version: 1
campaign_id: "tiny-binary-test"
count: 3
last_updated: "2026-04-21"
---

# Dead ends — do NOT retry

- SMOTE + scale_pos_weight — double-counts imbalance (mar30)
- QuantileTransformer on tree models — monotonic transform can't change splits (mar30)
- LightGBM is_unbalance=True — inverts probabilities (mar30+apr01)
"""


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "DEAD_ENDS.md").write_text(DEAD_ENDS)
    return root


def test_dead_ends_query_all(campaign: Path):
    items = dead_ends_query.dead_ends_query(campaign_dir=str(campaign))
    assert len(items) == 3
    assert any("SMOTE" in item for item in items)


def test_dead_ends_query_substring(campaign: Path):
    items = dead_ends_query.dead_ends_query(pattern="SMOTE", campaign_dir=str(campaign))
    assert len(items) == 1
    assert "SMOTE" in items[0]


def test_dead_ends_query_regex(campaign: Path):
    items = dead_ends_query.dead_ends_query(pattern=r"LightGBM|Quantile", campaign_dir=str(campaign))
    assert len(items) == 2


def test_dead_ends_query_missing_file(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    items = dead_ends_query.dead_ends_query(campaign_dir=str(root))
    assert items == []
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_dead_ends_query.py -v 2>&1 | tail -5`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `runner/tools/dead_ends_query.py`**

```python
"""Dead-ends query (spec §2.2.3)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from runner.tools._common import EXIT_OK, emit_json

_BULLET = re.compile(r"^\s*-\s+(.*\S)\s*$", re.MULTILINE)


def dead_ends_query(
    pattern: str | None = None,
    campaign_dir: str = "runner/",
) -> list[str]:
    path = Path(campaign_dir) / "state" / "DEAD_ENDS.md"
    if not path.exists():
        return []
    text = path.read_text()
    # Strip frontmatter if present
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5 :]
    bullets = [m.group(1).strip() for m in _BULLET.finditer(text)]
    if pattern is None:
        return bullets
    regex = re.compile(pattern)
    return [b for b in bullets if regex.search(b)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Query runner/state/DEAD_ENDS.md.")
    p.add_argument("--pattern", default=None, help="Substring or regex.")
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    items = dead_ends_query(pattern=args.pattern, campaign_dir=args.campaign_dir)
    if args.json_output:
        emit_json(items)
    else:
        for item in items:
            print(f"- {item}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_dead_ends_query.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/dead_ends_query.py tests/tools/test_dead_ends_query.py
git commit -m "feat(tools): add dead_ends_query over DEAD_ENDS.md"
```

---

# Phase C — Gate-support tools

## Task 9: `tools/data_profile.py`

**Files:**
- Create: `runner/tools/data_profile.py`
- Create: `tests/tools/test_data_profile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_data_profile.py
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from runner.tools import data_profile
from tests.fixtures.tiny_dataset import make_tiny_binary


@pytest.fixture
def tiny_csv(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    df = X.copy()
    df["Class"] = y
    path = tmp_path / "tiny.csv"
    df.to_csv(path, index=False)
    return path


def test_data_profile_returns_expected_keys(tiny_csv: Path, tmp_path: Path):
    out_md = tmp_path / "profile.md"
    res = data_profile.data_profile(
        data_path=str(tiny_csv), target_col="Class", output_md=str(out_md),
    )
    assert res["n_rows"] == 500
    assert res["n_cols"] == 6
    assert "target_distribution" in res
    assert out_md.exists()
    assert "# Data profile" in out_md.read_text()


def test_data_profile_missing_target_raises(tiny_csv: Path, tmp_path: Path):
    out_md = tmp_path / "profile.md"
    with pytest.raises(ValueError):
        data_profile.data_profile(
            data_path=str(tiny_csv), target_col="nonexistent", output_md=str(out_md),
        )


def test_data_profile_missing_file_raises(tmp_path: Path):
    out_md = tmp_path / "profile.md"
    with pytest.raises(FileNotFoundError):
        data_profile.data_profile(
            data_path=str(tmp_path / "nope.csv"), target_col="Class", output_md=str(out_md),
        )


def test_data_profile_determinism(tiny_csv: Path, tmp_path: Path):
    r1 = data_profile.data_profile(str(tiny_csv), "Class", str(tmp_path / "a.md"))
    r2 = data_profile.data_profile(str(tiny_csv), "Class", str(tmp_path / "b.md"))
    assert r1 == r2
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_data_profile.py -v 2>&1 | tail -5`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `runner/tools/data_profile.py`**

```python
"""Data profiler (spec §2.2.1) — G2 support tool."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from runner.tools._common import EXIT_INTERNAL_ERROR, EXIT_OK, EXIT_USER_ERROR, emit_json


def data_profile(
    data_path: str,
    target_col: str,
    output_md: str = "runner/contracts/_data_profile.md",
) -> dict:
    p = Path(data_path)
    if not p.exists():
        raise FileNotFoundError(f"data file not found: {data_path}")
    df = pd.read_csv(p)
    if target_col not in df.columns:
        raise ValueError(f"target_col {target_col!r} not in columns: {list(df.columns)}")

    n_rows, n_cols = df.shape
    missingness = df.isna().sum().to_dict()
    target = df[target_col]
    target_dist = target.value_counts().to_dict()
    target_dist = {int(k) if isinstance(k, (int, float)) else str(k): int(v) for k, v in target_dist.items()}

    numeric_cols = [c for c in df.columns if c != target_col and pd.api.types.is_numeric_dtype(df[c])]
    numeric_stats = {}
    for c in numeric_cols:
        desc = df[c].describe()
        numeric_stats[c] = {
            "mean": float(desc["mean"]),
            "std": float(desc["std"]) if desc["count"] > 1 else 0.0,
            "min": float(desc["min"]),
            "q25": float(desc["25%"]),
            "q50": float(desc["50%"]),
            "q75": float(desc["75%"]),
            "max": float(desc["max"]),
        }

    result = {
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "missingness": {c: int(v) for c, v in missingness.items()},
        "target_col": target_col,
        "target_distribution": target_dist,
        "numeric_stats": numeric_stats,
    }

    out = Path(output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render_md(result))
    return result


def _render_md(res: dict) -> str:
    lines = [
        "# Data profile",
        "",
        f"- n_rows: {res['n_rows']}",
        f"- n_cols: {res['n_cols']}",
        f"- target_col: `{res['target_col']}`",
        f"- target_distribution: {res['target_distribution']}",
        "",
        "## Columns and dtypes",
        "",
    ]
    for c in res["columns"]:
        miss = res["missingness"][c]
        lines.append(f"- `{c}` — {res['dtypes'][c]} (missing: {miss})")
    lines.append("")
    lines.append("## Numeric statistics")
    lines.append("")
    for c, stats in res["numeric_stats"].items():
        lines.append(
            f"- `{c}` — mean={stats['mean']:.3f} std={stats['std']:.3f} "
            f"q[25/50/75]=({stats['q25']:.3f}/{stats['q50']:.3f}/{stats['q75']:.3f}) "
            f"range=[{stats['min']:.3f}, {stats['max']:.3f}]"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Data profile for a CSV.")
    p.add_argument("--data-path", required=True)
    p.add_argument("--target-col", required=True)
    p.add_argument("--output-md", default="runner/contracts/_data_profile.md")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = data_profile(args.data_path, args.target_col, args.output_md)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"INTERNAL ERROR: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.json_output:
        emit_json(res)
    else:
        print(f"Wrote profile to {args.output_md} (n_rows={res['n_rows']}, n_cols={res['n_cols']})")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_data_profile.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/data_profile.py tests/tools/test_data_profile.py
git commit -m "feat(tools): add data_profile (G2 gate support)"
```

---

## Task 10: `tools/leakage_audit.py`

**Files:**
- Create: `runner/tools/leakage_audit.py`
- Create: `tests/tools/test_leakage_audit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_leakage_audit.py
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from runner.tools import leakage_audit
from tests.fixtures.tiny_dataset import make_tiny_binary


DATA_CONTRACT_SIMPLE = """---
schema_version: 1
campaign_id: "tiny"
data_sources:
  - path: "data/tiny.csv"
    n_rows: 500
    n_cols: 6
    primary_key: "row"
temporal:
  is_temporal: false
  order_column: null
  prediction_time_column: null
columns:
  - name: "x1"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x2"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x3"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x4"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x5"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "Class"
    dtype: "int64"
    role: "target"
    available_at_prediction: false
leakage_audit:
  performed_at: null
  flagged_columns: []
  notes: ""
splits:
  train: "60%"
  val: "20%"
  test: "20%"
  random_seed: 42
---

## 1. Schema summary
## 2. Availability table (narrative)
## 3. Leakage audit summary
## 4. Transformations applied pre-agent (if any)
## 5. Known data quality issues
"""


@pytest.fixture
def clean_csv(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    df = X.copy()
    df["Class"] = y
    path = tmp_path / "tiny.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def leaky_csv(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    # Inject a leaky feature: y plus tiny noise
    rng = np.random.default_rng(0)
    X = X.copy()
    X["leaky"] = y.values + rng.normal(0, 0.001, size=len(y))
    df = X.copy()
    df["Class"] = y
    path = tmp_path / "leaky.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def contract_path(tmp_path: Path) -> Path:
    p = tmp_path / "DATA_CONTRACT.md"
    p.write_text(DATA_CONTRACT_SIMPLE)
    return p


def test_leakage_audit_clean(clean_csv: Path, contract_path: Path):
    res = leakage_audit.leakage_audit(
        data_contract_path=str(contract_path),
        data_path=str(clean_csv),
        target_col="Class",
    )
    assert res["flagged"] == []


def test_leakage_audit_catches_leaky_feature(leaky_csv: Path, contract_path: Path):
    # Contract does not list 'leaky' column — audit should still flag it when encountered
    # Update contract to include 'leaky' as feature
    src = contract_path.read_text()
    src = src.replace(
        '  - name: "Class"',
        '  - name: "leaky"\n    dtype: "float64"\n    role: "feature"\n    available_at_prediction: true\n  - name: "Class"',
    )
    contract_path.write_text(src)
    res = leakage_audit.leakage_audit(
        data_contract_path=str(contract_path),
        data_path=str(leaky_csv),
        target_col="Class",
    )
    assert "leaky" in res["flagged"]


def test_leakage_audit_constant_column_flagged(clean_csv: Path, contract_path: Path, tmp_path: Path):
    df = pd.read_csv(clean_csv)
    df["constant"] = 7.0
    new_csv = tmp_path / "with_const.csv"
    df.to_csv(new_csv, index=False)
    src = contract_path.read_text().replace(
        '  - name: "Class"',
        '  - name: "constant"\n    dtype: "float64"\n    role: "feature"\n    available_at_prediction: true\n  - name: "Class"',
    )
    contract_path.write_text(src)
    res = leakage_audit.leakage_audit(
        data_contract_path=str(contract_path),
        data_path=str(new_csv),
        target_col="Class",
    )
    assert "constant" in res["flagged"]
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_leakage_audit.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/leakage_audit.py`**

```python
"""Leakage audit (spec §2.2.1) — G2 support tool."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_USER_ERROR,
    FrontmatterError,
    emit_json,
    parse_frontmatter,
)


def leakage_audit(
    data_contract_path: str,
    data_path: str,
    target_col: str,
) -> dict[str, Any]:
    fm, _ = parse_frontmatter(Path(data_contract_path))
    temporal = fm.get("temporal") or {}
    columns_spec = fm.get("columns") or []
    availability = {
        col.get("name"): bool(col.get("available_at_prediction", False))
        for col in columns_spec
        if isinstance(col, dict)
    }

    df = pd.read_csv(data_path)
    if target_col not in df.columns:
        raise ValueError(f"target_col {target_col!r} not in data columns")
    y = df[target_col]
    features = [c for c in df.columns if c != target_col]

    flagged: list[str] = []
    notes: list[str] = []
    passed: list[str] = []

    # Check 1: target-adjacent (|corr| > 0.95 or AUC(col->target) > 0.98)
    for col in features:
        if not pd.api.types.is_numeric_dtype(df[col]):
            passed.append(col)
            continue
        series = df[col].astype(float)
        if series.nunique(dropna=True) <= 1:
            flagged.append(col)
            notes.append(f"{col}: constant/single-value column")
            continue
        try:
            corr = series.corr(y.astype(float))
        except Exception:  # noqa: BLE001
            corr = 0.0
        try:
            auc = roc_auc_score(y, series)
        except Exception:  # noqa: BLE001
            auc = 0.5
        if abs(corr) > 0.95 or abs(auc - 0.5) > 0.48:  # auc > 0.98 or auc < 0.02
            flagged.append(col)
            notes.append(f"{col}: |corr|={abs(corr):.3f} auc={auc:.3f} — target-adjacent")
        else:
            passed.append(col)

    # Check 2: temporal leakage
    if temporal.get("is_temporal"):
        pred_time_col = temporal.get("prediction_time_column")
        if pred_time_col is None:
            raise _ContractViolation("temporal.is_temporal=true but prediction_time_column is null")
        for col in features:
            if availability.get(col) is False and col not in flagged:
                flagged.append(col)
                notes.append(f"{col}: available_at_prediction=false but temporal")

    return {
        "flagged": flagged,
        "passed": passed,
        "notes": notes,
    }


class _ContractViolation(Exception):
    """Internal sentinel for contract-violation exit code."""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leakage audit over data contract + CSV.")
    p.add_argument("--data-contract-path", required=True)
    p.add_argument("--data-path", required=True)
    p.add_argument("--target-col", required=True)
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = leakage_audit(args.data_contract_path, args.data_path, args.target_col)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except (FrontmatterError, _ContractViolation) as exc:
        print(f"CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except Exception as exc:  # noqa: BLE001
        print(f"INTERNAL ERROR: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.json_output:
        emit_json(res)
    else:
        print(f"flagged: {res['flagged']}")
        for note in res["notes"]:
            print(f"  - {note}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_leakage_audit.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/leakage_audit.py tests/tools/test_leakage_audit.py
git commit -m "feat(tools): add leakage_audit (G2 gate support)"
```

---

## Task 11: `tools/baseline_runner.py`

**Files:**
- Create: `runner/tools/baseline_runner.py`
- Create: `tests/tools/test_baseline_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_baseline_runner.py
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
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_baseline_runner.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/baseline_runner.py`**

```python
"""Baseline runner (spec §2.2.1) — G3 support tool.

Runs a minimal baseline with the metric + CV scheme from EVAL_PROTOCOL.md.
Supported families for MVP: logreg, xgboost, rf, kmeans (clustering). This
is NOT a search — just a sanity baseline.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, KFold

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_USER_ERROR,
    FrontmatterError,
    emit_json,
    parse_frontmatter,
)


_METRIC_FNS = {
    "pr_auc": lambda y_true, y_score: float(average_precision_score(y_true, y_score)),
    "roc_auc": lambda y_true, y_score: float(roc_auc_score(y_true, y_score)),
}


def _build_model(family: str):
    if family == "logreg":
        return LogisticRegression(max_iter=500, class_weight="balanced", solver="liblinear")
    if family == "rf":
        return RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, class_weight="balanced")
    if family == "xgboost":
        import xgboost as xgb  # local import to avoid mandatory dep at import time
        return xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", random_state=42, n_jobs=-1,
        )
    raise ValueError(f"unsupported family: {family!r}")


def baseline_runner(
    family: str,
    eval_protocol_path: str,
    data_path: str,
    target_col: str,
    output_path: str = "runner/state/_baseline.json",
) -> dict[str, Any]:
    fm, _ = parse_frontmatter(Path(eval_protocol_path))
    metric_name = (fm.get("primary_metric") or {}).get("name", "pr_auc")
    if metric_name not in _METRIC_FNS:
        raise _ProtocolError(f"metric {metric_name!r} not supported by baseline_runner MVP")
    metric_fn = _METRIC_FNS[metric_name]
    cv = fm.get("cv_scheme") or {}
    scheme = cv.get("type", "single_holdout")
    n_splits = int(cv.get("n_splits", 1))
    random_state = int(cv.get("random_state", 42))

    df = pd.read_csv(data_path)
    if target_col not in df.columns:
        raise ValueError(f"target_col {target_col!r} not in data")
    X = df.drop(columns=[target_col])
    y = df[target_col].astype(int)

    fold_scores: list[float] = []
    t0 = time.time()
    if scheme == "single_holdout":
        from sklearn.model_selection import train_test_split
        X_tr, X_va, y_tr, y_va = train_test_split(X, y, test_size=0.2, stratify=y, random_state=random_state)
        model = _build_model(family)
        model.fit(X_tr, y_tr)
        y_score = model.predict_proba(X_va)[:, 1]
        fold_scores.append(metric_fn(y_va, y_score))
    else:
        if scheme == "stratified_kfold":
            splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        elif scheme == "kfold":
            splitter = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        else:
            raise _ProtocolError(f"unsupported cv_scheme.type: {scheme!r}")
        for tr_idx, va_idx in splitter.split(X, y):
            model = _build_model(family)
            model.fit(X.iloc[tr_idx], y.iloc[tr_idx])
            y_score = model.predict_proba(X.iloc[va_idx])[:, 1]
            fold_scores.append(metric_fn(y.iloc[va_idx], y_score))
    runtime_s = time.time() - t0
    mean = float(np.mean(fold_scores))
    std = float(np.std(fold_scores, ddof=1)) if len(fold_scores) > 1 else 0.0
    result = {
        "family": family,
        "metric_name": metric_name,
        "metric_value": mean,
        "metric_ci": [mean - 1.96 * std / max(1, len(fold_scores)) ** 0.5,
                      mean + 1.96 * std / max(1, len(fold_scores)) ** 0.5],
        "fold_scores": fold_scores,
        "runtime_s": runtime_s,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    return result


class _ProtocolError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Baseline family runner (G3 support).")
    p.add_argument("--family", required=True, choices=["logreg", "rf", "xgboost"])
    p.add_argument("--eval-protocol-path", required=True)
    p.add_argument("--data-path", required=True)
    p.add_argument("--target-col", required=True)
    p.add_argument("--output-path", default="runner/state/_baseline.json")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = baseline_runner(
            family=args.family,
            eval_protocol_path=args.eval_protocol_path,
            data_path=args.data_path,
            target_col=args.target_col,
            output_path=args.output_path,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except (FrontmatterError, _ProtocolError) as exc:
        print(f"CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except Exception as exc:  # noqa: BLE001
        print(f"INTERNAL ERROR: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.json_output:
        emit_json(res)
    else:
        print(f"{res['family']} {res['metric_name']}={res['metric_value']:.4f} ({res['runtime_s']:.1f}s)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_baseline_runner.py -v`
Expected: 2 passed (may take ~5s).

- [ ] **Step 5: Commit**

```bash
git add runner/tools/baseline_runner.py tests/tools/test_baseline_runner.py
git commit -m "feat(tools): add baseline_runner (G3 gate support)"
```

---

# Phase D — Statistical tools

## Task 12: `tools/cv_runner.py`

**Files:**
- Create: `runner/tools/cv_runner.py`
- Create: `tests/tools/test_cv_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_cv_runner.py
from __future__ import annotations

import pytest
from sklearn.linear_model import LogisticRegression

from runner.tools import cv_runner
from tests.fixtures.tiny_dataset import make_tiny_binary


def _factory():
    return LogisticRegression(max_iter=500, solver="liblinear", class_weight="balanced")


def test_cv_runner_stratified_kfold_has_positives_per_fold():
    X, y = make_tiny_binary()
    result = cv_runner.cv_runner(
        estimator_factory=_factory,
        X=X, y=y,
        scheme="stratified_kfold",
        n_splits=5,
        primary_metric="pr_auc",
        random_state=42,
    )
    assert len(result["fold_scores"]) == 5
    assert all(0.0 <= s <= 1.0 for s in result["fold_scores"])
    assert "mean" in result and "std" in result and "ci95" in result


def test_cv_runner_invalid_scheme_raises():
    X, y = make_tiny_binary()
    with pytest.raises(ValueError):
        cv_runner.cv_runner(
            estimator_factory=_factory,
            X=X, y=y,
            scheme="not_a_real_scheme",
            n_splits=3,
            primary_metric="pr_auc",
            random_state=42,
        )


def test_cv_runner_determinism():
    X, y = make_tiny_binary()
    r1 = cv_runner.cv_runner(_factory, X, y, "stratified_kfold", 3, "pr_auc", 42)
    r2 = cv_runner.cv_runner(_factory, X, y, "stratified_kfold", 3, "pr_auc", 42)
    assert r1["fold_scores"] == r2["fold_scores"]
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_cv_runner.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/cv_runner.py`**

```python
"""CV runner (spec §2.2.2)."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, mean_squared_error, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold


_METRICS = {
    "pr_auc": ("proba", lambda y, s: float(average_precision_score(y, s))),
    "roc_auc": ("proba", lambda y, s: float(roc_auc_score(y, s))),
    "rmse": ("pred", lambda y, p: float(np.sqrt(mean_squared_error(y, p)))),
}


def cv_runner(
    estimator_factory: Callable[[], Any],
    X: pd.DataFrame,
    y: pd.Series,
    scheme: str,
    n_splits: int,
    primary_metric: str,
    random_state: int,
    groups: pd.Series | None = None,
) -> dict[str, Any]:
    if primary_metric not in _METRICS:
        raise ValueError(f"unknown primary_metric: {primary_metric!r}")
    target_type, metric_fn = _METRICS[primary_metric]

    if scheme == "stratified_kfold":
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_args = (X, y)
    elif scheme == "kfold":
        splitter = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_args = (X, y)
    elif scheme == "group_kfold":
        if groups is None:
            raise ValueError("group_kfold requires groups")
        splitter = GroupKFold(n_splits=n_splits)
        split_args = (X, y, groups)
    else:
        raise ValueError(f"unknown scheme: {scheme!r}")

    scores: list[float] = []
    for fold_idx, split in enumerate(splitter.split(*split_args)):
        tr, va = split[0], split[1]
        model = estimator_factory()
        model.fit(X.iloc[tr], y.iloc[tr])
        if target_type == "proba":
            score = model.predict_proba(X.iloc[va])[:, 1]
        else:
            score = model.predict(X.iloc[va])
        scores.append(metric_fn(y.iloc[va], score))
    mean = float(np.mean(scores))
    std = float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
    if len(scores) > 1:
        tcrit = stats.t.ppf(0.975, len(scores) - 1)
        half = tcrit * std / (len(scores) ** 0.5)
    else:
        half = 0.0
    return {
        "fold_scores": scores,
        "mean": mean,
        "std": std,
        "ci95": [mean - half, mean + half],
    }
```

(No CLI for cv_runner because it takes a Python callable; the CLI variant for config-file usage is Phase 2.)

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_cv_runner.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/cv_runner.py tests/tools/test_cv_runner.py
git commit -m "feat(tools): add cv_runner (Python API only in MVP)"
```

---

## Task 13: `tools/bootstrap_ci.py`

**Files:**
- Create: `runner/tools/bootstrap_ci.py`
- Create: `tests/tools/test_bootstrap_ci.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_bootstrap_ci.py
from __future__ import annotations

import numpy as np
import pytest

from runner.tools import bootstrap_ci


def test_bootstrap_ci_pr_auc_contained_in_zero_one():
    rng = np.random.default_rng(0)
    n = 200
    y_true = (rng.uniform(size=n) < 0.1).astype(int)
    y_prob = rng.uniform(size=n)
    res = bootstrap_ci.bootstrap_ci(y_true, y_prob, metric="pr_auc", n_boot=200, random_state=0)
    assert 0.0 <= res["ci_lo"] <= res["metric"] <= res["ci_hi"] <= 1.0
    assert res["n_boot"] == 200


def test_bootstrap_ci_determinism():
    rng = np.random.default_rng(0)
    y = (rng.uniform(size=100) < 0.2).astype(int)
    p = rng.uniform(size=100)
    r1 = bootstrap_ci.bootstrap_ci(y, p, metric="pr_auc", n_boot=100, random_state=7)
    r2 = bootstrap_ci.bootstrap_ci(y, p, metric="pr_auc", n_boot=100, random_state=7)
    assert r1 == r2


def test_bootstrap_ci_unknown_metric_raises():
    with pytest.raises(ValueError):
        bootstrap_ci.bootstrap_ci([0, 1], [0.1, 0.9], metric="fake", n_boot=10)
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_bootstrap_ci.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/bootstrap_ci.py`**

```python
"""Bootstrap CI (spec §2.2.2)."""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    roc_auc_score,
)


def _metric_fn(name: str):
    if name == "pr_auc":
        return lambda y, s: float(average_precision_score(y, s))
    if name == "roc_auc":
        return lambda y, s: float(roc_auc_score(y, s))
    if name == "f1":
        return lambda y, s: float(f1_score(y, (np.asarray(s) >= 0.5).astype(int), zero_division=0))
    raise ValueError(f"unknown metric: {name!r}")


def bootstrap_ci(
    y_true,
    y_prob_or_pred,
    metric: str,
    n_boot: int = 1000,
    random_state: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    fn = _metric_fn(metric)
    y = np.asarray(y_true)
    s = np.asarray(y_prob_or_pred)
    if len(y) != len(s):
        raise ValueError("length mismatch y_true vs scores")
    rng = np.random.default_rng(random_state)
    point = fn(y, s)
    scores = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, len(y), size=len(y))
        try:
            scores[i] = fn(y[idx], s[idx])
        except (ValueError, ZeroDivisionError):
            scores[i] = np.nan
    scores = scores[~np.isnan(scores)]
    lo = float(np.quantile(scores, alpha / 2))
    hi = float(np.quantile(scores, 1 - alpha / 2))
    se = float(np.std(scores, ddof=1))
    return {
        "metric": point,
        "ci_lo": lo,
        "ci_hi": hi,
        "se": se,
        "n_boot": int(n_boot),
    }
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_bootstrap_ci.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/bootstrap_ci.py tests/tools/test_bootstrap_ci.py
git commit -m "feat(tools): add bootstrap_ci"
```

---

## Task 14: `tools/paired_comparison.py`

**Files:**
- Create: `runner/tools/paired_comparison.py`
- Create: `tests/tools/test_paired_comparison.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_paired_comparison.py
from __future__ import annotations

import pytest

from runner.tools import paired_comparison


def test_paired_comparison_a_better_wilcoxon():
    a = [0.85, 0.84, 0.86, 0.83, 0.87]
    b = [0.80, 0.79, 0.81, 0.78, 0.82]
    res = paired_comparison.paired_comparison(a, b, test="wilcoxon")
    assert res["direction"] == "a>b"
    assert res["p_value"] < 0.1


def test_paired_comparison_tie():
    a = [0.80, 0.81, 0.79]
    b = [0.80, 0.81, 0.79]
    res = paired_comparison.paired_comparison(a, b, test="wilcoxon")
    assert res["direction"] == "tie"


def test_paired_comparison_unknown_test_raises():
    with pytest.raises(ValueError):
        paired_comparison.paired_comparison([1.0, 2.0], [0.5, 1.5], test="magic")
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_paired_comparison.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/paired_comparison.py`**

```python
"""Paired comparison (spec §2.2.2)."""
from __future__ import annotations

import numpy as np
from scipy import stats


def paired_comparison(
    a_scores,
    b_scores,
    test: str = "wilcoxon",
) -> dict:
    a = np.asarray(a_scores, dtype=float)
    b = np.asarray(b_scores, dtype=float)
    if a.shape != b.shape:
        raise ValueError("a_scores and b_scores must have same shape")
    diff = a - b
    if np.allclose(diff, 0):
        return {"p_value": 1.0, "effect_size": 0.0, "direction": "tie"}

    if test == "wilcoxon":
        try:
            stat, p = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
            p = float(p)
        except ValueError:
            # Happens when all diffs are zero post-zero-removal
            p = 1.0
    elif test == "t":
        _, p = stats.ttest_rel(a, b)
        p = float(p)
    else:
        raise ValueError(f"unknown test: {test!r}")

    effect_size = float(np.mean(a) - np.mean(b))
    if effect_size > 0:
        direction = "a>b"
    elif effect_size < 0:
        direction = "b>a"
    else:
        direction = "tie"
    return {"p_value": p, "effect_size": effect_size, "direction": direction}
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_paired_comparison.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/paired_comparison.py tests/tools/test_paired_comparison.py
git commit -m "feat(tools): add paired_comparison (wilcoxon/t)"
```

---

## Task 15: `tools/optuna_search.py`

**Files:**
- Create: `runner/tools/optuna_search.py`
- Create: `tests/tools/test_optuna_search.py`
- Create: `tests/tools/fixtures/optuna_objective.py` (tiny deterministic objective)

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/fixtures/optuna_objective.py
"""Tiny Optuna objective for tests — parabola with known optimum at x=0.5."""
import optuna


def objective(trial: optuna.trial.Trial) -> float:
    x = trial.suggest_float("x", 0.0, 1.0)
    return -((x - 0.5) ** 2)  # maximum at x=0.5
```

```python
# tests/tools/test_optuna_search.py
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import optuna_search


OBJECTIVE_FILE = Path(__file__).parent / "fixtures" / "optuna_objective.py"


def test_optuna_search_finds_parabola_peak():
    res = optuna_search.optuna_search(
        objective_py_path=str(OBJECTIVE_FILE),
        n_trials=30,
        timeout_s=10,
        direction="maximize",
        seed=42,
    )
    assert res["n_completed"] >= 1
    assert abs(res["best_params"]["x"] - 0.5) < 0.2
    assert res["best_value"] < 0  # since we return negative parabola


def test_optuna_search_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        optuna_search.optuna_search(
            objective_py_path=str(tmp_path / "nope.py"),
            n_trials=5,
            timeout_s=5,
        )
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_optuna_search.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/optuna_search.py`**

```python
"""Optuna search wrapper (spec §2.2.2)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import optuna


def _load_objective(py_path: str):
    path = Path(py_path)
    if not path.exists():
        raise FileNotFoundError(f"objective file not found: {py_path}")
    spec = importlib.util.spec_from_file_location("runner_objective", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if not hasattr(module, "objective"):
        raise ValueError(f"{py_path} does not define `objective(trial)`")
    return module.objective


def optuna_search(
    objective_py_path: str,
    n_trials: int,
    timeout_s: int,
    direction: str = "maximize",
    study_name: str | None = None,
    seed: int = 13,
) -> dict[str, Any]:
    objective = _load_objective(objective_py_path)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction=direction, sampler=sampler, study_name=study_name)
    study.optimize(objective, n_trials=n_trials, timeout=timeout_s)
    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    pruned = [t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]
    return {
        "best_params": dict(study.best_params) if completed else {},
        "best_value": float(study.best_value) if completed else float("nan"),
        "n_completed": len(completed),
        "pruned": len(pruned),
    }
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_optuna_search.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/optuna_search.py tests/tools/test_optuna_search.py tests/tools/fixtures/optuna_objective.py
git commit -m "feat(tools): add optuna_search wrapper"
```

---

# Phase E — Specialized tools

## Task 16: `tools/clustering_eval.py`

**Files:**
- Create: `runner/tools/clustering_eval.py`
- Create: `tests/tools/test_clustering_eval.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_clustering_eval.py
from __future__ import annotations

import numpy as np
import pytest

from runner.tools import clustering_eval


def test_clustering_eval_returns_all_metrics():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    labels = np.repeat([0, 1, 2], 20)
    res = clustering_eval.clustering_eval(X, labels)
    assert set(res.keys()) >= {"silhouette", "davies_bouldin", "calinski_harabasz"}


def test_clustering_eval_single_cluster_returns_nan_silhouette():
    X = np.ones((20, 2))
    labels = np.zeros(20, dtype=int)
    res = clustering_eval.clustering_eval(X, labels)
    import math
    assert math.isnan(res["silhouette"])
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_clustering_eval.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/clustering_eval.py`**

```python
"""Clustering evaluator (spec §2.2.5). Used only when task_type == 'clustering'."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)


def clustering_eval(
    X,
    labels,
    metrics: tuple = ("silhouette", "davies_bouldin", "calinski_harabasz"),
    random_state: int = 42,
) -> dict[str, Any]:
    X_arr = np.asarray(X)
    lbl = np.asarray(labels)
    out: dict[str, float] = {}
    n_clusters = len(np.unique(lbl))
    for m in metrics:
        try:
            if m == "silhouette":
                if n_clusters < 2 or n_clusters >= len(lbl):
                    out[m] = math.nan
                else:
                    out[m] = float(silhouette_score(X_arr, lbl, random_state=random_state))
            elif m == "davies_bouldin":
                if n_clusters < 2:
                    out[m] = math.nan
                else:
                    out[m] = float(davies_bouldin_score(X_arr, lbl))
            elif m == "calinski_harabasz":
                if n_clusters < 2:
                    out[m] = math.nan
                else:
                    out[m] = float(calinski_harabasz_score(X_arr, lbl))
            else:
                raise ValueError(f"unknown clustering metric: {m!r}")
        except ValueError:
            out[m] = math.nan
    return out
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_clustering_eval.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/clustering_eval.py tests/tools/test_clustering_eval.py
git commit -m "feat(tools): add clustering_eval (unsupervised support)"
```

---

## Task 17: `tools/explain_run.py`

**Files:**
- Create: `runner/tools/explain_run.py`
- Create: `tests/tools/test_explain_run.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_explain_run.py
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import explain_run


HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)
ROW = "deadbeef\t0.80\t5.0\t0.8\t0.7\tkeep\t10\txgboost\tA_model\ttry xgb\tbaseline\n"


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text(HEADER + ROW)
    return root


def test_explain_run_writes_card(campaign: Path):
    out = campaign / "state" / "run_card.md"
    path = explain_run.explain_run(commit="deadbeef", output_path=str(out), campaign_dir=str(campaign))
    assert Path(path).exists()
    text = Path(path).read_text()
    assert "deadbeef" in text
    assert "try xgb" in text
    assert "## Metrics" in text


def test_explain_run_missing_commit_raises(campaign: Path):
    with pytest.raises(LookupError):
        explain_run.explain_run(commit="nope", output_path=str(campaign / "state" / "x.md"), campaign_dir=str(campaign))
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_explain_run.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/explain_run.py`**

```python
"""Run card builder (spec §2.2.3) — on-demand."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_OK,
    EXIT_USER_ERROR,
    emit_json,
)


def explain_run(
    commit: str,
    output_path: str = "runner/state/run_card.md",
    campaign_dir: str = "runner/",
) -> str:
    camp = Path(campaign_dir)
    results = camp / "state" / "results.tsv"
    if not results.exists():
        raise FileNotFoundError(f"results.tsv not found at {results}")
    df = pd.read_csv(results, sep="\t")
    rows = df[df["commit"].astype(str) == commit]
    if rows.empty:
        raise LookupError(f"commit {commit!r} not found in results.tsv")
    row = rows.iloc[-1].to_dict()

    next_exp = camp / "state" / "NEXT_EXPERIMENT.md"
    next_exp_excerpt = ""
    if next_exp.exists():
        next_exp_excerpt = next_exp.read_text()[:2000]

    lines = [
        f"# Run card — {commit}",
        "",
        f"- action_type: `{row.get('action_type', '?')}`",
        f"- model_family: `{row.get('model_family', '?')}`",
        f"- status: `{row.get('status', '?')}`",
        f"- hypothesis: {row.get('hypothesis', '')}",
        f"- description: {row.get('description', '')}",
        "",
        "## Metrics",
        "",
        f"- val_pr_auc: {row.get('val_pr_auc', '?')}",
        f"- lift_at_10: {row.get('lift_at_10', '?')}",
        f"- macro_f1: {row.get('macro_f1', '?')}",
        f"- val_f1: {row.get('val_f1', '?')}",
        f"- n_features: {row.get('n_features', '?')}",
        "",
    ]
    if next_exp_excerpt:
        lines += ["## NEXT_EXPERIMENT.md (at time of run)", "", "```", next_exp_excerpt, "```", ""]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    return str(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate a run card for a commit.")
    p.add_argument("--commit", required=True)
    p.add_argument("--output-path", default="runner/state/run_card.md")
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        path = explain_run(args.commit, args.output_path, args.campaign_dir)
    except LookupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    if args.json_output:
        emit_json({"path": path})
    else:
        print(path)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_explain_run.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/explain_run.py tests/tools/test_explain_run.py
git commit -m "feat(tools): add explain_run (on-demand run card)"
```

---

## Task 18: `tools/contract_diff.py`

**Files:**
- Create: `runner/tools/contract_diff.py`
- Create: `tests/tools/test_contract_diff.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_contract_diff.py
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
```

- [ ] **Step 2: Run — expect import error**

Run: `pytest tests/tools/test_contract_diff.py -v 2>&1 | tail -5`
Expected: import error.

- [ ] **Step 3: Implement `runner/tools/contract_diff.py`**

```python
"""Contract diff (spec §2.2.4) — C3 governance."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_OK,
    EXIT_USER_ERROR,
    FrontmatterError,
    emit_json,
    parse_frontmatter,
)


_CONTRACT_FILES = {
    "PROBLEM": "PROBLEM_CONTRACT.md",
    "DATA": "DATA_CONTRACT.md",
    "EVAL": "EVAL_PROTOCOL.md",
}


# Fields whose change is a hard invariant (spec §4 / EVAL_PROTOCOL schema)
_HIGH_RISK_FIELDS = {
    "budgets.max_repair_attempts",
    "primary_metric.name",
    "primary_metric.direction",
    "cv_scheme.type",
}


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten(v, key))
    else:
        out[prefix] = d
    return out


def contract_diff(
    contract_name: str,
    proposed_path: str,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    if contract_name not in _CONTRACT_FILES:
        raise ValueError(f"contract_name must be one of {list(_CONTRACT_FILES)}")
    current_path = Path(campaign_dir) / "contracts" / _CONTRACT_FILES[contract_name]
    if not current_path.exists():
        raise FileNotFoundError(f"current contract not found: {current_path}")
    cur_fm, _ = parse_frontmatter(current_path)
    new_fm, _ = parse_frontmatter(Path(proposed_path))

    cur_flat = _flatten(cur_fm)
    new_flat = _flatten(new_fm)
    all_keys = sorted(set(cur_flat) | set(new_flat))

    changes = []
    for k in all_keys:
        before = cur_flat.get(k)
        after = new_flat.get(k)
        if before != after:
            changes.append({"field": k, "before": before, "after": after})

    risk = "low"
    if any(c["field"] in _HIGH_RISK_FIELDS for c in changes):
        risk = "high"
    elif len(changes) > 5:
        risk = "medium"

    return {
        "contract": contract_name,
        "changes": changes,
        "risk_level": risk,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Structured contract diff (C3).")
    p.add_argument("--contract-name", required=True, choices=list(_CONTRACT_FILES))
    p.add_argument("--proposed-path", required=True)
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = contract_diff(args.contract_name, args.proposed_path, args.campaign_dir)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except FrontmatterError as exc:
        print(f"CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    if args.json_output:
        emit_json(res)
    else:
        print(f"contract={res['contract']} risk={res['risk_level']} changes={len(res['changes'])}")
        for c in res["changes"]:
            print(f"  {c['field']}: {c['before']!r} -> {c['after']!r}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `pytest tests/tools/test_contract_diff.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/contract_diff.py tests/tools/test_contract_diff.py
git commit -m "feat(tools): add contract_diff (C3 governance)"
```

---

# Phase F — Driver & orchestration

## Task 19: `runner_driver.py` + `run_round.sh`

This is the biggest task. The driver is split into three stages (`plan-check`, `execute-finalize`, `review-finalize`), each invoked by the `run_round.sh` CLI, plus an `init` stage that bootstraps `CAMPAIGN_STATE.json`.

**Files:**
- Create: `runner/runner_driver.py`
- Create: `runner/run_round.sh`
- Create: `tests/test_runner_driver.py`

- [ ] **Step 1: Write failing tests for `init`**

```python
# tests/test_runner_driver.py
"""Unit tests for runner.runner_driver (the state machine)."""
from __future__ import annotations

import json
import os
import subprocess
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
    # Write a valid plan with escalation=C2
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
    # Minimal REVIEW.md and run.log exist elsewhere; review_finalize takes
    # the parsed verdict directly (the shell wrapper parses stdout and
    # passes it in).
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
```

- [ ] **Step 2: Run tests — expect module-not-found**

Run: `pytest tests/test_runner_driver.py -v 2>&1 | tail -10`
Expected: import error for `runner.runner_driver`.

- [ ] **Step 3: Implement `runner/runner_driver.py`**

```python
"""Runner driver (spec §3.2) — state machine for the autonomous loop.

Split into four stages, each invoked by `runner/run_round.sh <stage>`:

  1. init              — bootstrap CAMPAIGN_STATE.json from approved contracts
  2. plan-check        — validate NEXT_EXPERIMENT.md and branch on escalation
  3. execute-finalize  — parse Executor stdout into a {channel, synthetic_verdict}
  4. review-finalize   — apply verdict: update state, decide rollback/pause/halt

The driver is intentionally stateless between stages. State lives in
runner/state/CAMPAIGN_STATE.json and on disk in the other artifacts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

import log
from runner.tools import schema
from runner.tools._common import FrontmatterError, parse_frontmatter


Channel = Literal["RUN_COMPLETE", "RUN_FAILED", "REVIEW_REQUIRED"]
Verdict = Literal["keep", "discard", "anomaly", "crash", "malformed"]


class GateError(Exception):
    """Raised when G1/G2/G3 are not signed at init."""


class DriverError(Exception):
    """Raised on structural driver failures (missing state, schema drift)."""


_STDOUT_RE = re.compile(
    r"^(?P<channel>RUN_COMPLETE|RUN_FAILED|REVIEW_REQUIRED):\s*(?P<rest>.*)$",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def init_campaign(campaign_dir: str = "runner/") -> dict[str, Any]:
    camp = Path(campaign_dir)
    contracts = {
        "PROBLEM_CONTRACT.md": schema.validate_problem_contract,
        "DATA_CONTRACT.md": schema.validate_data_contract,
        "EVAL_PROTOCOL.md": schema.validate_eval_protocol,
    }
    for fname, validator in contracts.items():
        path = camp / "contracts" / fname
        if not path.exists():
            raise GateError(f"{fname} is missing (G1/G2/G3 unsigned)")
        errors = validator(path)
        if errors:
            raise GateError(f"{fname} schema errors: {errors}")
        fm, _ = parse_frontmatter(path)
        if fm.get("approved_at") in (None, ""):
            raise GateError(f"{fname}.approved_at is null — human sign-off missing")

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    budgets = eval_fm.get("budgets") or {}
    problem_fm, _ = parse_frontmatter(camp / "contracts" / "PROBLEM_CONTRACT.md")

    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = {
        "$schema_version": 1,
        "campaign_id": problem_fm.get("campaign_id"),
        "round": 0,
        "exp_id_counter": 0,
        "last_commit": None,
        "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0,
        "budget_used": 0,
        "budget_total": int(budgets.get("max_experiments", 100)),
        "created_at": now,
        "updated_at": now,
    }
    state_dir = camp / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "CAMPAIGN_STATE.json").write_text(json.dumps(state, indent=2) + "\n")

    results = state_dir / "results.tsv"
    if not results.exists():
        results.write_text(
            "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
            "model_family\taction_type\thypothesis\tdescription\n"
        )
    return state


# ---------------------------------------------------------------------------
# plan-check
# ---------------------------------------------------------------------------

def plan_check(campaign_dir: str = "runner/") -> dict[str, Any]:
    camp = Path(campaign_dir)
    plan_path = camp / "state" / "NEXT_EXPERIMENT.md"
    if not plan_path.exists():
        return {"status": "missing", "errors": ["NEXT_EXPERIMENT.md not found"]}

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    allowed = list(eval_fm.get("action_types") or [])
    errors = schema.validate_next_experiment(plan_path, allowed_action_types=allowed)

    # Guardrail rule (spec §8.3 item 5): ≥3 consecutive discards + escalation!=C2
    state = json.loads((camp / "state" / "CAMPAIGN_STATE.json").read_text())
    trigger = int((eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3))
    try:
        fm, _ = parse_frontmatter(plan_path)
        escalation = fm.get("escalation")
    except FrontmatterError:
        escalation = None
    if state.get("consecutive_discards", 0) >= trigger and escalation != "C2":
        errors.append(
            f"consecutive_discards={state['consecutive_discards']} >= trigger={trigger} "
            f"but escalation!=C2 (required per spec §8.3 item 5)"
        )

    if errors:
        return {"status": "malformed", "errors": errors}
    if escalation == "C2":
        return {"status": "pause_c2", "errors": []}
    if escalation == "C3":
        return {"status": "pause_c3", "errors": []}
    return {"status": "ok", "errors": []}


# ---------------------------------------------------------------------------
# execute-finalize
# ---------------------------------------------------------------------------

def execute_finalize(
    executor_stdout: str,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    matches = list(_STDOUT_RE.finditer(executor_stdout))
    if not matches:
        return {
            "channel": None,
            "commit": None,
            "synthetic_verdict": "malformed",
            "reason": "Executor emitted no recognized channel line",
        }
    m = matches[-1]  # use the last emitted line
    channel = m.group("channel")
    rest = m.group("rest").strip()

    if channel == "RUN_COMPLETE":
        commit = rest.split()[0] if rest else None
        return {"channel": channel, "commit": commit, "synthetic_verdict": None, "reason": ""}
    if channel == "RUN_FAILED":
        parts = rest.split(maxsplit=1)
        commit = parts[0] if parts else None
        reason = parts[1] if len(parts) > 1 else ""
        return {"channel": channel, "commit": commit, "synthetic_verdict": "crash", "reason": reason}
    if channel == "REVIEW_REQUIRED":
        return {"channel": channel, "commit": None, "synthetic_verdict": "malformed", "reason": rest}
    raise DriverError(f"unhandled channel: {channel}")


# ---------------------------------------------------------------------------
# review-finalize
# ---------------------------------------------------------------------------

def review_finalize(
    verdict: Verdict,
    commit: str,
    metrics: dict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    prior_verdict = state.get("last_verdict")
    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    pm = (eval_fm.get("primary_metric") or {})
    metric_name = pm.get("name", "val_pr_auc")
    direction = pm.get("direction", "maximize")

    # Append to results.tsv + update CAMPAIGN_STATE.json
    log.append_result(
        commit=commit if commit else "none",
        metrics=metrics,
        status=verdict,
        action_type=action_type,
        hypothesis=hypothesis,
        description=description,
        model_family=model_family,
        n_features=n_features,
        campaign_dir=str(camp),
        primary_metric_name=metric_name,
        direction=direction,
    )
    state_after = json.loads(state_path.read_text())

    should_rollback = verdict in {"discard", "crash", "malformed"}
    pause_loop = verdict == "anomaly"

    # Halt detection: two consecutive malformed
    halt_loop = False
    halt_reason = ""
    if verdict == "malformed" and prior_verdict == "malformed":
        halt_loop = True
        halt_reason = "two consecutive malformed verdicts — BUG: role producing malformed artifacts"
    if state_after.get("round", 0) >= state_after.get("budget_total", 0):
        halt_loop = True
        halt_reason = halt_reason or "budget_exhausted"

    return {
        "verdict": verdict,
        "should_rollback": should_rollback,
        "pause_loop": pause_loop,
        "halt_loop": halt_loop,
        "halt_reason": halt_reason,
    }
```

- [ ] **Step 4: Run driver tests — expect all pass**

Run: `pytest tests/test_runner_driver.py -v`
Expected: 10 passed.

- [ ] **Step 5: Create `runner/run_round.sh`**

```bash
#!/usr/bin/env bash
# runner/run_round.sh — thin CLI wrapper over runner_driver.py.
#
# Usage:
#   runner/run_round.sh init [--campaign-dir DIR]
#   runner/run_round.sh plan-check [--campaign-dir DIR]
#   runner/run_round.sh execute-finalize --stdout-file FILE [--campaign-dir DIR]
#   runner/run_round.sh review-finalize --verdict X --commit C --metrics-json J \
#                                       --action-type A --hypothesis H \
#                                       --description D --model-family M \
#                                       --n-features N [--campaign-dir DIR]
#
# This is the exact CLI the campaign operator invokes between role invocations.
# The stages are ordered: init → plan-check → (agent writes NEXT_EXPERIMENT.md) →
# plan-check again → (Executor runs train.py, stdout captured to a file) →
# execute-finalize → (Reviewer writes REVIEW.md, verdict on its stdout) →
# review-finalize → repeat.

set -euo pipefail

STAGE=${1:?"stage required: init|plan-check|execute-finalize|review-finalize"}
shift || true

# All additional arguments are passed through to the Python driver as a dict.
python3 -c '
import json, sys
from runner import runner_driver

stage = sys.argv[1]
args = {}
i = 2
while i < len(sys.argv):
    k = sys.argv[i].lstrip("-").replace("-", "_")
    v = sys.argv[i+1] if i+1 < len(sys.argv) else ""
    args[k] = v
    i += 2

if stage == "init":
    state = runner_driver.init_campaign(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(state, indent=2))
elif stage == "plan-check":
    res = runner_driver.plan_check(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res))
elif stage == "execute-finalize":
    stdout_file = args["stdout_file"]
    text = open(stdout_file).read()
    res = runner_driver.execute_finalize(text, campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res))
elif stage == "review-finalize":
    metrics = json.loads(args["metrics_json"])
    res = runner_driver.review_finalize(
        verdict=args["verdict"],
        commit=args["commit"],
        metrics=metrics,
        action_type=args["action_type"],
        hypothesis=args["hypothesis"],
        description=args["description"],
        model_family=args["model_family"],
        n_features=int(args["n_features"]),
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps(res))
else:
    print(f"unknown stage: {stage}", file=sys.stderr)
    sys.exit(2)
' "$STAGE" "$@"
```

- [ ] **Step 6: Make shell script executable**

Run: `chmod +x runner/run_round.sh`
Expected: no output; verify with `ls -l runner/run_round.sh` showing `-rwxr-xr-x`.

- [ ] **Step 7: Smoke-test the shell wrapper via a fixture campaign**

Run:
```bash
rm -rf /tmp/smoke && mkdir -p /tmp/smoke/runner/contracts /tmp/smoke/runner/state
# Copy the three EP/PC/DC from the test file inline:
python3 -c "
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL
import pathlib
d = pathlib.Path('/tmp/smoke/runner/contracts')
(d/'PROBLEM_CONTRACT.md').write_text(PROBLEM_CONTRACT)
(d/'DATA_CONTRACT.md').write_text(DATA_CONTRACT)
(d/'EVAL_PROTOCOL.md').write_text(EVAL_PROTOCOL)
"
./runner/run_round.sh init --campaign-dir /tmp/smoke/runner/
```
Expected: prints JSON CAMPAIGN_STATE with `"round": 0`, `"budget_total": 3`.

- [ ] **Step 8: Commit**

```bash
git add runner/runner_driver.py runner/run_round.sh tests/test_runner_driver.py
git commit -m "feat(runner): add runner_driver (init/plan-check/execute-finalize/review-finalize) + shell CLI"
```

---

# Phase G — Integration & safety tests

## Task 20: Integration tests + safety tests

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_happy_loop.py`
- Create: `tests/integration/test_c1_anomaly.py`
- Create: `tests/safety/__init__.py`
- Create: `tests/safety/test_no_role_writes_contract.py`
- Create: `tests/safety/test_commit_per_experiment.py`
- Create: `tests/safety/test_repair_cap.py`
- Create: `tests/safety/test_executor_scope.py`

The integration tests use **stub role outputs** (just write fixed files) rather than invoking LLMs. The driver is the real object under test.

- [ ] **Step 1: Write `tests/integration/test_happy_loop.py`**

```python
# tests/integration/__init__.py
```

```python
# tests/integration/test_happy_loop.py
"""3-round happy-path integration test using stub role outputs."""
from __future__ import annotations

import json
import subprocess
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
        {"val_pr_auc": 0.70, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.6},  # keep
        {"val_pr_auc": 0.72, "lift_at_10": 4.2, "macro_f1": 0.72, "val_f1": 0.61},  # keep
        {"val_pr_auc": 0.68, "lift_at_10": 3.5, "macro_f1": 0.68, "val_f1": 0.55},  # discard (< best)
    ]
    expected_verdicts = ["keep", "keep", "discard"]

    for i, (metrics, verdict) in enumerate(zip(metrics_per_round, expected_verdicts), start=1):
        # Stub Planner: write a plan
        (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(_make_plan(i))
        check = runner_driver.plan_check(campaign_dir=str(campaign))
        assert check["status"] == "ok", check["errors"]

        # Stub Executor: emit RUN_COMPLETE
        exec_status = runner_driver.execute_finalize(
            executor_stdout=f"RUN_COMPLETE: commit{i}\n",
            campaign_dir=str(campaign),
        )
        assert exec_status["channel"] == "RUN_COMPLETE"

        # Stub Reviewer: verdict
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
        assert res["halt_loop"] is False or i == 3  # budget_total=3 exhausts at round 3

    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["round"] == 3
    assert state["best_so_far"]["commit"] == "commit2"  # 0.72 beats 0.70
    assert state["consecutive_discards"] == 1  # last round was discard

    # results.tsv should have header + 3 rows
    tsv = (campaign / "state" / "results.tsv").read_text().splitlines()
    assert len(tsv) == 4
```

- [ ] **Step 2: Write `tests/integration/test_c1_anomaly.py`**

```python
# tests/integration/test_c1_anomaly.py
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
    assert state["consecutive_discards"] == 0  # unchanged
    assert state["best_so_far"]["commit"] is None  # anomaly does not update best

    tsv = (campaign / "state" / "results.tsv").read_text()
    assert "anom1" in tsv
    assert "anomaly" in tsv
```

- [ ] **Step 3: Write safety tests**

```python
# tests/safety/__init__.py
```

```python
# tests/safety/test_no_role_writes_contract.py
"""Invariant: no role is allowed to mutate runner/contracts/*.md (spec §1 Executor write scope)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL


pytestmark = pytest.mark.safety


def test_driver_never_writes_contracts(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    for name, text in (
        ("PROBLEM_CONTRACT.md", PROBLEM_CONTRACT),
        ("DATA_CONTRACT.md", DATA_CONTRACT),
        ("EVAL_PROTOCOL.md", EVAL_PROTOCOL),
    ):
        (root / "contracts" / name).write_text(text)

    orig_mtimes = {p.name: p.stat().st_mtime_ns for p in (root / "contracts").iterdir()}

    runner_driver.init_campaign(campaign_dir=str(root))
    runner_driver.review_finalize(
        verdict="keep", commit="c1",
        metrics={"val_pr_auc": 0.7, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.6},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(root),
    )

    for p in (root / "contracts").iterdir():
        assert p.stat().st_mtime_ns == orig_mtimes[p.name], f"{p} was mutated by driver"
```

```python
# tests/safety/test_repair_cap.py
"""Invariant: EVAL_PROTOCOL.budgets.max_repair_attempts must be exactly 2 (hard invariant)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema
from tests.test_runner_driver import EVAL_PROTOCOL


pytestmark = pytest.mark.safety


def test_schema_rejects_non_two_repair_cap(tmp_path: Path):
    src = EVAL_PROTOCOL.replace("max_repair_attempts: 2", "max_repair_attempts: 5")
    p = tmp_path / "EP.md"
    p.write_text(src)
    errors = schema.validate_eval_protocol(p)
    assert any("max_repair_attempts" in e for e in errors)


def test_schema_accepts_two_repair_cap(tmp_path: Path):
    p = tmp_path / "EP.md"
    p.write_text(EVAL_PROTOCOL)
    errors = schema.validate_eval_protocol(p)
    assert not any("max_repair_attempts" in e for e in errors)
```

```python
# tests/safety/test_commit_per_experiment.py
"""Invariant: every row in results.tsv corresponds to exactly one verdict. Budget
is about work attempted, not kept, so len(tsv)-1 == state.budget_used (spec §3.2)."""
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
        ("keep",     0.70),
        ("discard",  0.50),
        ("crash",    0.00),
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
```

```python
# tests/safety/test_executor_scope.py
"""Invariant: a plan that declares touches_helpers must list helpers_declared (schema enforces)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema


pytestmark = pytest.mark.safety


PLAN_BAD = """---
schema_version: 1
campaign_id: "x"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "h"
expected_effect_size: 0.0
base_commit: "HEAD"
touches_helpers: true
helpers_declared: []
escalation: null
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
x
## 4. Helpers
x
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)
x
"""


def test_touches_helpers_without_declaration_is_rejected(tmp_path: Path):
    p = tmp_path / "ne.md"
    p.write_text(PLAN_BAD)
    errors = schema.validate_next_experiment(p)
    assert any("helpers_declared" in e for e in errors)
```

- [ ] **Step 4: Run integration + safety tests — expect all pass**

Run: `pytest tests/integration/ tests/safety/ -v`
Expected: 2 (integration) + 4 (safety files with 1 test each in 3 files, 2 in another = 5 tests total) = 7 passed. Recount from tests above:
- `test_happy_loop.py`: 1
- `test_c1_anomaly.py`: 1
- `test_no_role_writes_contract.py`: 1
- `test_repair_cap.py`: 2
- `test_commit_per_experiment.py`: 1
- `test_executor_scope.py`: 1

Total: 7. Expected: **7 passed**.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest -v 2>&1 | tail -30`
Expected: all tests pass (count ≈ 55–60 depending on exact enumeration). No failures.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/ tests/safety/
git commit -m "test: add integration (happy_loop, c1_anomaly) and safety invariants"
```

---

# Phase H — Roles & first-campaign seed

## Task 21: Role prompt files (Planner, Executor, Reviewer)

Copy the role skeletons from spec §2.1 verbatim into `runner/roles/*.md`, substituting `<campaign_id>` placeholders with a literal placeholder token the campaign operator replaces at G1.

**Files:**
- Create: `runner/roles/planner.md`
- Create: `runner/roles/executor.md`
- Create: `runner/roles/reviewer.md`

- [ ] **Step 1: Copy Planner prompt from spec §2.1.1**

Open `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md` §2.1.1 and copy the markdown block between the fenced `\`\`\`markdown` delimiters into `runner/roles/planner.md` verbatim. No modifications except:
- Keep the literal `<campaign_id>` token (campaign operator replaces).
- Ensure the §2 Inputs paths use relative paths `runner/...`.

- [ ] **Step 2: Copy Executor prompt from spec §2.1.2**

Same procedure for `runner/roles/executor.md`.

- [ ] **Step 3: Copy Reviewer prompt from spec §2.1.3**

Same procedure for `runner/roles/reviewer.md`. In §3 Required procedure step 1, update the cross-reference to `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md §8.3 items 1–8` so the role has an absolute path to the rejection list.

- [ ] **Step 4: Verify the three files exist and are non-empty**

Run: `wc -l runner/roles/*.md`
Expected: three files, each ≥ 20 lines.

- [ ] **Step 5: Commit**

```bash
git add runner/roles/planner.md runner/roles/executor.md runner/roles/reviewer.md
git commit -m "feat(runner): add role prompt files (Planner/Executor/Reviewer skeletons from spec §2.1)"
```

---

## Task 22: Seed first-campaign artifacts for creditcard problem

Seed the contracts, DEAD_ENDS, NOTEBOOK, and PRIORS for campaign `apr21-creditcard-fraud` using the values from legacy `abes_engine.py` + `program.md` + reflection doc.

**Files:**
- Create: `runner/contracts/PROBLEM_CONTRACT.md`
- Create: `runner/contracts/DATA_CONTRACT.md`
- Create: `runner/contracts/EVAL_PROTOCOL.md`
- Create: `runner/contracts/PRIORS.md`
- Create: `runner/state/DEAD_ENDS.md`
- Create: `runner/state/NOTEBOOK.md`

- [ ] **Step 1: Write `runner/contracts/PROBLEM_CONTRACT.md`**

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
problem_title: "Credit-card fraud detection"
task_type: "binary_classification"
unit_of_observation: "transaction"
target:
  name: "Class"
  positive_class: 1
  definition: "1 if labeled fraud by issuer, 0 otherwise."
success_criteria:
  - "val_pr_auc >= 0.85 on held-out validation"
  - "lift_at_10 >= 8.0"
constraints:
  - "No third-party data integration."
  - "Total campaign compute <= 60s per experiment."
  - "Do not modify prepare.py or data/."
non_goals:
  - "No deployment / inference service."
  - "No fairness / subgroup analysis in this campaign."
approved_at: null
approved_by: null
---

## 1. Task

Predict whether a credit-card transaction is fraudulent given a PCA-transformed feature set. The dataset is extremely imbalanced (~0.17% positive rate).

## 2. Why the task matters

This dataset is the canonical benchmark used in `auto_train` campaigns; establishing a reproducible runner MVP on it validates the greenfield architecture against historical results (mar30, apr01, apr03).

## 3. Success criteria (detail)

- Primary: val_pr_auc >= 0.85 on the fixed validation split defined by prepare.py.
- Secondary: lift_at_10 >= 8.0 at the 10% flagging threshold.

## 4. Constraints (detail)

- 60s per experiment (hard timeout 90s).
- Libraries fixed to requirements.txt; no new installs.
- prepare.py and data/ are read-only (workspace rule).

## 5. Non-goals (detail)

- Production service, deployment, or calibration for a specific business threshold.
- Fairness / subgroup analyses (future campaign).
- Novel model architecture research.
```

- [ ] **Step 2: Write `runner/contracts/DATA_CONTRACT.md`**

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
data_sources:
  - path: "data/creditcard.csv"
    n_rows: 284807
    n_cols: 31
    primary_key: "implicit row index"
temporal:
  is_temporal: false
  order_column: null
  prediction_time_column: null
columns:
  - name: "Time"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
    notes: "Seconds since first observation."
  - name: "Amount"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V1"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V2"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V3"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V4"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V5"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V6"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V7"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V8"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V9"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V10"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V11"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V12"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V13"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V14"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V15"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V16"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V17"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V18"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V19"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V20"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V21"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V22"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V23"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V24"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V25"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V26"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V27"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V28"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "Class"
    dtype: "int64"
    role: "target"
    available_at_prediction: false
leakage_audit:
  performed_at: null
  flagged_columns: []
  notes: "Run tools/leakage_audit and fill performed_at before G2 sign-off."
splits:
  train: "stratified 60% of data (per prepare.py)"
  val: "stratified 20% of data (per prepare.py)"
  test: "stratified 20% of data (per prepare.py)"
  random_seed: 42
approved_at: null
approved_by: null
---

## 1. Schema summary

284,807 rows × 31 columns. Target `Class` is binary (0=legit, 1=fraud, ~0.17% positive). V1–V28 are PCA-transformed at source; Amount and Time are raw.

## 2. Availability table (narrative)

All features are synchronous with the transaction record — available at prediction time by construction. Time is elapsed seconds since the first observation in the dataset, not clock time.

## 3. Leakage audit summary

Run `python3 runner/tools/leakage_audit.py --data-contract-path runner/contracts/DATA_CONTRACT.md --data-path data/creditcard.csv --target-col Class` before G2 sign-off. No historical audit flagged features (legacy campaigns relied on the fixed prepare.py split).

## 4. Transformations applied pre-agent (if any)

V1–V28 were produced by PCA at data generation time; original columns are not accessible.

## 5. Known data quality issues

None known. Dataset loads cleanly in prepare.py.
```

- [ ] **Step 3: Write `runner/contracts/EVAL_PROTOCOL.md`**

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
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
  notes: "Preserving prepare.py splits for MVP; upgrade to stratified_kfold in Phase 2 per reflection §7."
bootstrap_ci:
  enabled: true
  n_boot: 1000
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools:
  - "tools/anomaly.py"
  - "tools/bootstrap_ci.py"
action_types:
  - "A_model"
  - "A_feature"
  - "A_hp"
  - "A_imbalance"
  - "A_ensemble"
  - "A_diagnose"
  - "A_validate"
  - "A_restart"
budgets:
  time_budget_s: 60
  hard_timeout_s: 90
  max_experiments: 100
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 0.75
  relative: 0.5
approved_at: null
approved_by: null
---

## 1. Rationale

These choices reproduce the legacy `abes_engine.py` / `program.md` defaults while making evaluation reliability explicit. The `noise_floor` of 0.005 reflects the reflection §7 analysis that Δ < 0.005 is within the bootstrap SE for this positive count.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff Δ > 0 AND `tools/anomaly` did not fire AND `tools/bootstrap_ci` did not report a regression (CI of new < CI_lo of best).

## 3. How plateau is handled

After 3 consecutive non-keep verdicts, the next Planner MUST emit a plan with `escalation: "C2"` (plateau/family switch proposal).

## 4. Contract change policy

Contracts are sticky. Any change requires a C3-gate Planner escalation with `tools/contract_diff` output and human approval.
```

- [ ] **Step 4: Write `runner/contracts/PRIORS.md`**

```markdown
---
schema_version: 1
problem_id: "creditcard-fraud"
last_campaign: "apr03"
updated_at: "2026-04-21"
---

## Known good

- `np.log1p(Amount)` adds signal (confirmed mar30, apr01).
- `Amount * V1` and `Amount * V2` interactions add signal.
- XGBoost depth in [4, 6] is the canonical range for single-model runs.
- LightGBM is competitive after fixing the is_unbalance bug.

## Known bad

- `v_interactions` (V1*V2, V1*V3, V3*V4) are noise.
- `time_features` (Time_hour, Time_sin, Time_cos) are noise.
- SMOTE + scale_pos_weight double-counts imbalance.
- DART booster exceeds 90s timeout at 500 trees.
- `tree_method=approx` exceeds 90s timeout on 170K rows.
- Sklearn GBM (GradientBoostingClassifier) exceeds 90s at 100 trees.

## Known ceilings

- Single-holdout PR-AUC plateaus around 0.846 on the fixed apr03 split.
- Above this, CV-with-CI is needed to trust Δ (reflection §7).

## Open questions (for next campaign)

- Does 5-fold stratified CV raise the observed ceiling or confirm it is structural?
- Do stacked ensembles help after tuning individual members with Optuna?
```

- [ ] **Step 5: Write `runner/state/DEAD_ENDS.md`**

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
count: 8
last_updated: "2026-04-21"
---

# Dead ends — do NOT retry

- SMOTE + scale_pos_weight — double-counts imbalance (mar30)
- QuantileTransformer on tree models — monotonic transform can't change splits (mar30)
- BaggingClassifier wrapping XGBoost — redundant with subsample/colsample (mar30)
- `aucpr` as early stopping metric — too noisy; use logloss (mar30)
- LightGBM `is_unbalance=True` — inverts probabilities (mar30+apr01)
- DART booster — exceeds 90s timeout at 500 trees (apr01)
- `tree_method=approx` — exceeds 90s timeout on 170K rows (apr01)
- sklearn GBM (GradientBoostingClassifier) — exceeds 90s at 100 trees (apr01)
```

- [ ] **Step 6: Write `runner/state/NOTEBOOK.md`**

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
count: 3
last_updated: "2026-04-21"
---

# Observations worth remembering (non-dead-end)

- XGBoost depth=4 and depth=6 both found independent optima in apr01 — basin is not a single point.
- Removing `time_features` improved by ~0.003 AND simplified the pipeline in apr01.
- `lift_at_10` is ~3× more stable across seeds than `val_pr_auc` on this split (reflection §7).
```

- [ ] **Step 7: Validate all seeded artifacts**

Run:
```bash
python3 -c "
from runner.tools import schema
from pathlib import Path
errors_all = []
for fname, fn in [
    ('PROBLEM_CONTRACT.md', schema.validate_problem_contract),
    ('DATA_CONTRACT.md', schema.validate_data_contract),
    ('EVAL_PROTOCOL.md', schema.validate_eval_protocol),
]:
    errs = fn(Path('runner/contracts') / fname)
    errors_all.append((fname, errs))
for name, errs in errors_all:
    print(f'{name}: {errs}')
"
```
Expected: Each prints `<name>: []` (empty error list). Note: `approved_at` and `approved_by` are NOT in any `_X_REQUIRED` list in `schema.py` (Task 3), so `approved_at: null` passes schema validation. Gate sign-off is a separate invariant enforced by `init_campaign` (Task 19), not by the schema validator — this separation is intentional. Task 24 Step 1 simulates the human sign-off before calling `init`.

- [ ] **Step 8: Commit**

```bash
git add runner/contracts/PROBLEM_CONTRACT.md runner/contracts/DATA_CONTRACT.md runner/contracts/EVAL_PROTOCOL.md runner/contracts/PRIORS.md runner/state/DEAD_ENDS.md runner/state/NOTEBOOK.md
git commit -m "feat(runner): seed creditcard campaign (contracts + DEAD_ENDS/NOTEBOOK/PRIORS from legacy)"
```

---

# Phase I — Migration

## Task 23: Delete `abes_engine.py` + convert root docs to stubs

**Files:**
- Delete: `abes_engine.py`
- Delete: `abes_state.json`
- Modify: `program.md` (replace contents with stub)
- Modify: `AGENTS.md` (repo root — replace with stub)
- Modify: `CLAUDE.md` (repo root — replace with stub)

- [ ] **Step 1: Delete abes_engine.py and abes_state.json; archive legacy results.tsv + run.log**

```bash
rm abes_engine.py abes_state.json
mkdir -p docs/legacy
git mv results.tsv docs/legacy/results.tsv.pre-runner 2>/dev/null || mv results.tsv docs/legacy/results.tsv.pre-runner
git mv run.log docs/legacy/run.log.pre-runner 2>/dev/null || mv run.log docs/legacy/run.log.pre-runner
```

Expected: root `abes_engine.py`, `abes_state.json`, `results.tsv`, `run.log` are gone. `docs/legacy/` contains the archived files.

- [ ] **Step 2: Replace `program.md` with a stub**

```markdown
# program.md — REDIRECT

This file is superseded by `runner/RUNNER.md`. See that file for the lean agent entry point.

Historical `program.md` content is preserved in git history (pre-2026-04-21).

## Quick pointers

- Campaign orientation: `runner/RUNNER.md`
- Role prompts: `runner/roles/{planner,executor,reviewer}.md`
- Current contracts: `runner/contracts/`
- Current state: `runner/state/`
- Available tools: `runner/tools/`
- Driver CLI: `runner/run_round.sh`

This stub will be removed at the end of the first successful MVP campaign.
```

- [ ] **Step 3: Replace root `AGENTS.md` with a stub that preserves hard invariants**

The workspace-rule loader reads `AGENTS.md` at the repo root. The stub must preserve the hard invariants so agents not going through the runner still respect them.

```markdown
# AGENTS.md — REDIRECT

This repository is now orchestrated by the runner at `runner/`. **Read `runner/RUNNER.md` first.** Role-specific prompts: `runner/roles/{planner,executor,reviewer}.md`. Harness fossil record: `runner/AGENTS.md`.

## Hard invariants (preserved from pre-runner era)

1. **Only `train.py` may be modified by the Executor role** during an experiment. `prepare.py`, `data/`, and `runner/contracts/*` are read-only.
2. **Primary metric is defined in `runner/contracts/EVAL_PROTOCOL.md`** — do not hand-pick one.
3. **Every experiment is one git commit.** Discards roll back with `git reset --hard HEAD~1`.
4. **Budgets** (per-experiment time and total experiment count) are defined in `EVAL_PROTOCOL.budgets`.
5. **Contracts are sticky** — change only via C3 (approved `tools/contract_diff` output).

Historical root `AGENTS.md` content is preserved in git history (pre-2026-04-21).
```

- [ ] **Step 4: Replace root `CLAUDE.md` with a stub that preserves hard invariants**

```markdown
# CLAUDE.md — REDIRECT

See `AGENTS.md` (same content — both files mirror each other so any tool that reads either entry point finds the same invariants).

Entry point: `runner/RUNNER.md`. Role prompts: `runner/roles/`. Fossil record: `runner/AGENTS.md`.

## Hard invariants

1. Only `train.py` is modified by Executor during experiments.
2. `prepare.py`, `data/`, `runner/contracts/*` are read-only.
3. One git commit per experiment.
4. Primary metric + budgets live in `runner/contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky; change via C3 + `tools/contract_diff` + human approval.

Historical root `CLAUDE.md` content is preserved in git history (pre-2026-04-21).
```

- [ ] **Step 5: Verify the tree is clean**

Run:
```bash
ls abes_engine.py 2>&1 || echo "deleted ok"
ls runner/ && ls runner/tools/ | wc -l
```
Expected: `deleted ok`; `runner/` listing shows the 6 subdirs + RUNNER.md + AGENTS.md; `runner/tools/` has 12+ files (11 MVP tools + `_common.py` + `schema.py` + `__init__.py`).

- [ ] **Step 6: Run full test suite to confirm no regression from migration**

Run: `pytest -v 2>&1 | tail -10`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A   # picks up deletions (abes_*, results.tsv, run.log) + renames to docs/legacy/ + stub edits
git commit -m "chore: remove abes_engine+abes_state, archive legacy results.tsv+run.log, redirect program.md/AGENTS.md/CLAUDE.md to runner/"
```

---

# Phase J — Smoke test

## Task 24: End-to-end smoke test with seeded creditcard campaign

This is a **manual smoke test**, not an automated pytest — its purpose is to validate that the real `runner/run_round.sh` CLI works against the real seeded contracts before the first human sign-off. No LLM invocations; we hand-simulate the three roles with fixed files.

- [ ] **Step 1: Human G1/G2/G3 sign-off simulation**

Edit each contract to set `approved_at` and `approved_by`:

```bash
python3 -c "
from pathlib import Path
today = '2026-04-21'
for fname in ('PROBLEM_CONTRACT.md', 'DATA_CONTRACT.md', 'EVAL_PROTOCOL.md'):
    p = Path('runner/contracts') / fname
    text = p.read_text()
    text = text.replace('approved_at: null', f'approved_at: \"{today}\"', 1)
    text = text.replace('approved_by: null', 'approved_by: \"smoke-test-operator\"', 1)
    p.write_text(text)
print('signed')
"
```

Also fill `leakage_audit.performed_at` (simulating a G2 leakage-audit pass):

```bash
python3 -c "
from pathlib import Path
p = Path('runner/contracts/DATA_CONTRACT.md')
p.write_text(p.read_text().replace('performed_at: null', 'performed_at: \"2026-04-21\"', 1))
print('leakage audit stamped')
"
```

- [ ] **Step 2: Run `init`**

Run: `./runner/run_round.sh init --campaign-dir runner/`
Expected: prints JSON CAMPAIGN_STATE with `"campaign_id": "apr21-creditcard-fraud"`, `"round": 0`, `"budget_total": 100`. Creates `runner/state/CAMPAIGN_STATE.json` and header-only `runner/state/results.tsv`.

- [ ] **Step 3: Write a stub `NEXT_EXPERIMENT.md` (simulating Planner output)**

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
round: 1
planner_invocation_at: "2026-04-21T19:00:00Z"
action_type: "A_hp"
hypothesis: "Baseline LightGBM as smoke test."
expected_effect_size: 0.0
base_commit: "smoke0001"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary

Smoke test of driver pipeline with seeded creditcard campaign.

## 2. Evidence from memory

- results_query: no rows yet.
- dead_ends_query: no matches.
- NOTEBOOK: XGBoost basin lives in depth [4,6].

## 3. Plan

1. Use current `train.py` as-is (baseline).

## 4. Helpers

None.

## 5. How this differs from prior experiments

First round — no prior to differ from.

## 6. Escalation (only if `escalation` frontmatter is non-null)

N/A.
```

Save this as `runner/state/NEXT_EXPERIMENT.md`.

- [ ] **Step 4: Run `plan-check`**

Run: `./runner/run_round.sh plan-check --campaign-dir runner/`
Expected: prints `{"status": "ok", "errors": []}`.

- [ ] **Step 5: Simulate Executor output**

Run:
```bash
echo "RUN_COMPLETE: smoke0001" > /tmp/executor_stdout.txt
./runner/run_round.sh execute-finalize --stdout-file /tmp/executor_stdout.txt --campaign-dir runner/
```
Expected: prints JSON `{"channel": "RUN_COMPLETE", "commit": "smoke0001", "synthetic_verdict": null, "reason": ""}`.

- [ ] **Step 6: Simulate Reviewer verdict**

Run:
```bash
./runner/run_round.sh review-finalize \
  --verdict keep \
  --commit smoke0001 \
  --metrics-json '{"val_pr_auc":0.80,"lift_at_10":5.0,"macro_f1":0.8,"val_f1":0.7}' \
  --action-type A_hp \
  --hypothesis "smoke baseline" \
  --description "smoke test" \
  --model-family lightgbm \
  --n-features 30 \
  --campaign-dir runner/
```
Expected: prints JSON `{"verdict": "keep", "should_rollback": false, "pause_loop": false, "halt_loop": false, ...}`.

- [ ] **Step 7: Verify state transitions**

Run:
```bash
cat runner/state/CAMPAIGN_STATE.json | python3 -m json.tool
cat runner/state/results.tsv
```
Expected:
- `CAMPAIGN_STATE.json` shows `"round": 1`, `"best_so_far": {"commit": "smoke0001", "primary_metric": 0.8}`, `"consecutive_discards": 0`, `"budget_used": 1`.
- `results.tsv` has the header + 1 data row starting with `smoke0001\t0.80\t5.0\t0.8\t0.7\tkeep`.

- [ ] **Step 8: Reset smoke state (do not commit the smoke run)**

```bash
# Reset CAMPAIGN_STATE and results.tsv to pristine init
rm runner/state/CAMPAIGN_STATE.json runner/state/NEXT_EXPERIMENT.md
python3 -c "
from pathlib import Path
Path('runner/state/results.tsv').write_text(
    'commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t'
    'model_family\taction_type\thypothesis\tdescription\n'
)
"
./runner/run_round.sh init --campaign-dir runner/
```

Expected: fresh state with `round: 0`.

- [ ] **Step 9: Commit the signed contracts (sign-off is an intentional artifact)**

```bash
git add runner/contracts/PROBLEM_CONTRACT.md runner/contracts/DATA_CONTRACT.md runner/contracts/EVAL_PROTOCOL.md runner/state/CAMPAIGN_STATE.json runner/state/results.tsv
git commit -m "chore(runner): G1/G2/G3 sign-off + init campaign apr21-creditcard-fraud"
```

- [ ] **Step 10: Final test pass**

Run: `pytest -v 2>&1 | tail -10`
Expected: all tests pass — MVP is complete.

---

# Summary

After all 24 tasks complete:

- **11 MVP tools** + internal schema validator in `runner/tools/`, each with 3+ unit tests.
- **10 artifact schemas** enforced by `schema.py`; validated fixtures in `tests/schemas/fixtures/`.
- **Driver state machine** (`runner_driver.py` + `run_round.sh`) covering init, plan-check, execute-finalize, review-finalize — 10 unit tests + 2 integration tests + 4 safety invariants.
- **Role prompt files** for Planner / Executor / Reviewer.
- **Seeded first campaign** for creditcard fraud (contracts, PRIORS, DEAD_ENDS, NOTEBOOK) with G1/G2/G3 signed during smoke test.
- **Legacy `abes_engine.py` removed** and root docs redirect to `runner/`.
- **~60 passing tests** total.

Next real actions (outside this plan):
1. Operator invokes Planner role → writes real NEXT_EXPERIMENT.md.
2. Operator invokes Executor role → edits `train.py`, runs it, captures stdout.
3. Operator invokes Reviewer role → writes REVIEW.md, emits verdict.
4. `./runner/run_round.sh review-finalize …` records the verdict and loops.

---

*End of implementation plan.*
