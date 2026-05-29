# Auto-Train Harness — Public Template Implementation Spec

> **Purpose:** This document is a self-contained implementation spec for building the
> public GitHub template repository from the auto-train harness. Hand this to a fresh
> AI agent in a new workspace and it will produce a working, forkable template.
>
> **Date:** 2026-05-01
> **Source repo:** The private `auto_train` repository (not published).

---

## 0. What You Are Building

A **GitHub template repository** that packages an autonomous ML experimentation harness.
Users fork it, create a campaign for their own data, and run experiments with any AI
coding tool (Claude Code, Codex CLI, Cursor, GitHub Copilot) as the agent runtime.

**The harness does NOT contain an agent loop.** The AI tool IS the loop. The harness
provides: role instructions, state management, contract validation, and analysis tools.

### Key design principles

1. **Campaign isolation** — `runner/` + `shared/` = infrastructure (never edit during experiments). `campaigns/` = user-owned (one folder per problem).
2. **Contract system** — G1 (Problem), G2 (Data), G3 (Eval Protocol) are frozen before experiments begin. Schema-validated by `runner/tools/schema.py`.
3. **Multi-role state machine** — Planner → Executor → Reviewer → (Historian on plateau). Each role is a fresh invocation with defined inputs/outputs.
4. **`prepare.py` firewall** — frozen evaluation harness per campaign that prevents the agent from gaming metrics.
5. **Producer ≠ Verifier** — Executor writes code, Reviewer judges it. No role reads another role's chat.
6. **Cross-tool compatibility** — `AGENTS.md` (Codex/Copilot), `.claude/agents/` (Claude Code), `.cursor/rules/` (Cursor).

---

## 1. Complete Directory Structure

```
auto-train/                          # repository root
├── AGENTS.md                        # Cross-tool AI entry point (NEW — rewritten)
├── AGENT_GUIDE.md                   # AI routing index (NEW)
├── CLAUDE.md                        # Claude Code entry point (NEW — rewritten)
├── README.md                        # Human-facing quickstart (NEW — rewritten)
├── .gitignore                       # (NEW — rewritten)
├── requirements.txt                 # Python dependencies (COPY from source)
├── log.py                           # Results logging utility (COPY from source)
│
├── .claude/
│   └── agents/
│       ├── planner.md               # Claude Code subagent (NEW)
│       ├── executor.md              # Claude Code subagent (NEW)
│       ├── reviewer.md              # Claude Code subagent (NEW)
│       └── historian.md             # Claude Code subagent (NEW)
│
├── .cursor/
│   └── rules/
│       └── harness.md               # Cursor project rules (NEW)
│
├── scripts/
│   ├── new-campaign.sh              # Campaign scaffold script (NEW)
│   ├── update-harness.sh            # Pull infrastructure updates (NEW)
│   └── download-example-data.sh     # Download creditcard.csv for _example (NEW)
│
├── data/
│   └── README.md                    # Instructions for example data (NEW)
│
├── runner/
│   ├── __init__.py                  # (COPY from source)
│   ├── runner_driver.py             # State machine driver (COPY from source)
│   ├── run_round.sh                 # CLI wrapper (COPY from source)
│   ├── RUNNER.md                    # Harness entry point (COPY from source)
│   ├── AGENTS.md                    # Fossil record (COPY from source)
│   ├── contracts/
│   │   └── STRATEGY_GUIDE.md        # Advisory ML heuristics (COPY from source)
│   ├── roles/
│   │   ├── planner.md               # (COPY from source)
│   │   ├── executor.md              # (COPY from source)
│   │   ├── reviewer.md              # (COPY from source)
│   │   └── historian.md             # (COPY from source)
│   └── tools/
│       ├── __init__.py              # (COPY from source)
│       ├── _common.py               # (COPY from source)
│       ├── schema.py                # Contract validators (COPY from source)
│       ├── anomaly.py               # (COPY from source)
│       ├── bootstrap_ci.py          # (COPY from source)
│       ├── baseline_runner.py       # (COPY from source)
│       ├── calibration.py           # (COPY from source)
│       ├── clustering_eval.py       # (COPY from source)
│       ├── contract_diff.py         # (COPY from source)
│       ├── cv_runner.py             # (COPY from source)
│       ├── data_profile.py          # (COPY from source)
│       ├── dead_ends_query.py       # (COPY from source)
│       ├── dimred_eval.py           # (COPY from source)
│       ├── explain_run.py           # (COPY from source)
│       ├── feature_selection.py     # (COPY from source)
│       ├── integrity_check.py       # (COPY from source)
│       ├── leakage_audit.py         # (COPY from source)
│       ├── multi_fidelity.py        # (COPY from source)
│       ├── optuna_search.py         # (COPY from source)
│       ├── paired_comparison.py     # (COPY from source)
│       ├── results_query.py         # (COPY from source)
│       ├── shap_report.py           # (COPY from source)
│       ├── stacking.py             # (COPY from source)
│       └── token_summary.py         # (COPY from source)
│
├── shared/
│   ├── __init__.py                  # (COPY from source)
│   ├── metrics.py                   # Metric computation (COPY from source)
│   └── bq_loader.py                # BigQuery loader — optional (COPY from source)
│
├── tests/                           # Full test suite (COPY from source)
│   ├── conftest.py
│   ├── __init__.py
│   ├── fixtures/
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── fixtures/
│   │   ├── test_schema.py
│   │   └── test_validators.py
│   ├── safety/
│   │   ├── __init__.py
│   │   ├── test_auto_c3_trigger.py
│   │   ├── test_commit_per_experiment.py
│   │   ├── test_executor_scope.py
│   │   ├── test_historian_after_c2.py
│   │   ├── test_mandatory_tools.py
│   │   ├── test_no_role_writes_contract.py
│   │   ├── test_repair_cap.py
│   │   └── test_write_scope.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_c1_anomaly.py
│   │   ├── test_happy_loop.py
│   │   └── test_run_round_shell.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── fixtures/
│   │   ├── test_anomaly.py
│   │   ├── test_baseline_runner.py
│   │   ├── test_bootstrap_ci.py
│   │   ├── test_clustering_eval.py
│   │   ├── test_common.py
│   │   ├── test_contract_diff.py
│   │   ├── test_cv_runner.py
│   │   ├── test_data_profile.py
│   │   ├── test_dead_ends_query.py
│   │   ├── test_explain_run.py
│   │   ├── test_feature_selection.py
│   │   ├── test_leakage_audit.py
│   │   ├── test_optuna_search.py
│   │   ├── test_paired_comparison.py
│   │   ├── test_results_query.py
│   │   ├── test_shap_report.py
│   │   ├── test_stacking.py
│   │   └── test_token_summary.py
│   ├── test_historian_driver.py
│   ├── test_log.py
│   └── test_runner_driver.py
│
├── campaigns/
│   ├── _template/                   # Pure skeleton (NEW — create from scratch)
│   │   ├── RUNNER.md
│   │   ├── prepare.py
│   │   ├── train.py
│   │   └── contracts/
│   │       ├── PROBLEM_CONTRACT.md
│   │       ├── DATA_CONTRACT.md
│   │       ├── EVAL_PROTOCOL.md
│   │       ├── PRIORS.md
│   │       └── STRATEGY_GUIDE.md    # symlink → ../../runner/contracts/STRATEGY_GUIDE.md
│   │
│   └── _example/                    # Working demo on creditcard.csv (NEW)
│       ├── RUNNER.md
│       ├── prepare.py               # Extracted evaluation harness
│       ├── train.py                 # Baseline LightGBM experiment
│       └── contracts/
│           ├── PROBLEM_CONTRACT.md
│           ├── DATA_CONTRACT.md
│           ├── EVAL_PROTOCOL.md
│           ├── PRIORS.md
│           └── STRATEGY_GUIDE.md    # symlink → ../../runner/contracts/STRATEGY_GUIDE.md
```

### Annotation key

- **COPY from source** — Copy verbatim from the private `auto_train` repository. The user will provide these files before you start. Do not modify them.
- **NEW** — You must create this file. Exact content is specified in this document.

---

## 2. Infrastructure Files Inventory (COPY from source — do not modify)

The user will copy these directories/files from the private source repository into the
new workspace before handing you this spec. **Do not create or modify these files.**

| Path | What it does |
|---|---|
| `runner/runner_driver.py` | State machine driver — 4 stages: `init`, `plan-check`, `execute-finalize`, `review-finalize`, plus `historian`, `historian-finalize`, `resolve-c2` |
| `runner/run_round.sh` | Thin bash CLI wrapper over `runner_driver.py` |
| `runner/RUNNER.md` | Harness entry point — orientation, role selection, hard invariants |
| `runner/AGENTS.md` | Fossil record — cross-campaign harness rules and lessons |
| `runner/contracts/STRATEGY_GUIDE.md` | Advisory ML experiment planning heuristics |
| `runner/roles/planner.md` | Planner role prompt — owns `NEXT_EXPERIMENT.md` |
| `runner/roles/executor.md` | Executor role prompt — owns `train.py` edits |
| `runner/roles/reviewer.md` | Reviewer role prompt — owns verdict + `REVIEW.md` |
| `runner/roles/historian.md` | Historian role prompt — owns `STRATEGY_MEMO.md`, `PATTERN_BOOK.md` |
| `runner/tools/*.py` | 20+ validation/analysis tools (schema, anomaly, bootstrap_ci, etc.) |
| `shared/metrics.py` | `compute_split_metrics()`, `lift_at_percentage()`, etc. |
| `shared/bq_loader.py` | BigQuery data loader (optional — only needed for BQ-backed campaigns) |
| `log.py` | `append_result()` — writes to `results.tsv` and updates `CAMPAIGN_STATE.json` |
| `tests/` | 159 tests across `schemas/`, `safety/`, `integration/`, `tools/` |
| `requirements.txt` | Fixed Python dependencies |

### Critical: `runner_driver.py` campaign-dir support

The driver already supports `--campaign-dir` parameter. When passed (e.g., `--campaign-dir campaigns/_example`), all state/contract paths resolve relative to that directory. This is how campaign isolation works — the driver reads contracts from `<campaign-dir>/contracts/` and state from `<campaign-dir>/state/`.

### Critical: `log.py` dynamic results columns

`log.py` reads `results_columns` from the campaign's `EVAL_PROTOCOL.md` frontmatter. If present, the TSV header uses those columns. If absent, it falls back to the legacy 4-column schema (`val_pr_auc`, `lift_at_10`, `macro_f1`, `val_f1`).

### Critical: `shared/metrics.py` exports

```python
def lift_at_percentage(y_true, y_prob, pct) -> float
def precision_at_percentage(y_true, y_prob, pct) -> float
def true_positives_at_percentage(y_true, y_prob, pct) -> int
def compute_split_metrics(y_true, y_prob, prefix="val") -> Dict[str, float]
    # Returns: {prefix}_lift_1pct, {prefix}_auc_roc, {prefix}_lift_5pct,
    #          {prefix}_lift_10pct, {prefix}_auc_pr, {prefix}_precision_1pct,
    #          {prefix}_n_samples, {prefix}_n_positives, {prefix}_prevalence
```

### Critical: Schema validation required fields

The driver runs schema validation during `init` (G1/G2/G3 gate) and `plan-check`.
Every contract file must have YAML frontmatter with specific required fields.

**PROBLEM_CONTRACT required frontmatter:**
```yaml
schema_version, campaign_id, problem_title, task_type, unit_of_observation,
target (must have: name, definition), success_criteria, constraints, non_goals
```
Required body sections: `## 1. Task`, `## 2. Why`, `## 3. Success`, `## 4. Constraints`, `## 5. Non-goals`
`task_type` must be one of: `binary_classification`, `multiclass_classification`, `regression`, `clustering`, `anomaly_detection`

**DATA_CONTRACT required frontmatter:**
```yaml
schema_version, campaign_id, data_sources, temporal, columns,
leakage_audit (must have: performed_at), splits
```
Required body sections: `## 1. Schema`, `## 2. Availability`, `## 3. Leakage`, `## 4. Transformations`, `## 5. Known`

**EVAL_PROTOCOL required frontmatter:**
```yaml
schema_version, campaign_id, primary_metric (must have: name, direction),
acceptance_threshold, cv_scheme, bootstrap_ci, paired_test, mandatory_tools,
action_types, budgets (max_repair_attempts MUST be 2), plateau_trigger, anomaly
```
Required body sections: `## 1. Rationale`, `## 2. How keep/discard`, `## 3. How plateau`, `## 4. Contract change`
`primary_metric.direction` must be `maximize` or `minimize`
`historian_interval` must be a positive integer when present

**CAMPAIGN_STATE.json required fields:**
```json
["$schema_version", "campaign_id", "round", "exp_id_counter", "last_commit",
 "last_verdict", "best_so_far", "consecutive_discards", "budget_used",
 "budget_total", "created_at", "updated_at"]
```

**PRIORS required frontmatter:**
```yaml
schema_version, problem_id, last_campaign, updated_at
```
Required sections (NOT numbered): `## Known good`, `## Known bad`, `## Known ceilings`

**DEAD_ENDS / NOTEBOOK required frontmatter:**
```yaml
schema_version, campaign_id, count, last_updated
```
`count` must equal number of bullet entries in body.

**REVIEW required frontmatter:**
```yaml
schema_version, campaign_id, last_round, last_verdict
```
`last_verdict` must be one of: `keep`, `discard`, `anomaly`, `crash`, `malformed`

**NEXT_EXPERIMENT required frontmatter:**
```yaml
schema_version, campaign_id, round, planner_invocation_at, action_type,
hypothesis, expected_effect_size, base_commit, touches_helpers,
helpers_declared, escalation
```
Required sections: `## 1. Context`, `## 2. Evidence`, `## 3. Plan`, `## 4. Helpers`, `## 5. How this differs`, `## 6. Escalation`

---

## 3. Files to Create: `campaigns/_template/`

The template skeleton uses `<campaign_id>` as a placeholder. The `scripts/new-campaign.sh`
script replaces this placeholder with the actual campaign ID when scaffolding.

### 3.1 `campaigns/_template/contracts/PROBLEM_CONTRACT.md`

```markdown
---
schema_version: 1
campaign_id: "<campaign_id>"
problem_title: "TODO — Your problem title"
task_type: "binary_classification"
unit_of_observation: "TODO — e.g., patient, transaction, user"
target:
  name: "TODO_target_column"
  positive_class: 1
  definition: "TODO — what does a positive label mean?"
success_criteria:
  - "TODO — e.g., val_lift_1pct >= 5.0"
constraints:
  - "TODO — e.g., No leakage from post-outcome features"
  - "Fixed splits — do not re-split"
  - "Hard timeout: 90s per experiment"
non_goals:
  - "TODO — what this campaign is NOT trying to achieve"
approved_at: "TODO"
approved_by: "human"
---

## 1. Task

TODO — One paragraph describing the prediction task.

## 2. Why the task matters

TODO — Business context and motivation.

## 3. Success criteria (detail)

TODO — Elaborate on the primary metric target and why that threshold.

## 4. Constraints (detail)

TODO — Detail any data constraints, split requirements, time limits.

## 5. Non-goals (detail)

TODO — What this campaign will NOT attempt.
```

### 3.2 `campaigns/_template/contracts/DATA_CONTRACT.md`

```markdown
---
schema_version: 1
campaign_id: "<campaign_id>"
data_sources:
  - path: "TODO — e.g., data/your_dataset.csv"
    n_rows: 0
    n_cols: 0
    primary_key: "TODO"
temporal:
  is_temporal: false
  order_column: null
  prediction_time_column: null
columns:
  - name: "TODO_feature_1"
    dtype: "float64"
    description: "TODO"
  - name: "TODO_target"
    dtype: "int64"
    description: "TODO — target column"
leakage_audit:
  performed_at: "TODO — YYYY-MM-DD"
  flagged_columns: []
  notes: "TODO — explain why flagged columns are risky, or why none are flagged"
splits:
  train: "TODO — e.g., 60%"
  val: "TODO — e.g., 20%"
  test: "TODO — e.g., 20%"
  strategy: "TODO — e.g., stratified by target, seed=42"
approved_at: "TODO"
approved_by: "human"
---

## 1. Schema summary

TODO — List all columns with dtypes and brief descriptions.

## 2. Availability table (narrative)

TODO — Where the data lives, how to access it, any dependencies.

## 3. Leakage audit summary

TODO — Results of leakage audit. Which columns were flagged and why.

## 4. Transformations applied pre-agent (if any)

TODO — Any preprocessing done before the agent sees the data.

## 5. Known data quality issues

TODO — Missing values, class imbalance, outliers, etc.
```

### 3.3 `campaigns/_template/contracts/EVAL_PROTOCOL.md`

```markdown
---
schema_version: 1
campaign_id: "<campaign_id>"
primary_metric:
  name: "TODO_metric"
  direction: "maximize"
  noise_floor: 0.005
acceptance_threshold:
  baseline_family: "TODO — e.g., lgbm_default"
  min_improvement: 0.005
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: "TODO — describe your validation strategy"
bootstrap_ci:
  enabled: true
  n_boot: 500
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools:
  - "runner.tools.anomaly"
  - "runner.tools.bootstrap_ci"
action_types:
  - "A_model"
  - "A_feature"
  - "A_hp"
  - "A_imbalance"
  - "A_ensemble"
  - "A_validate"
budgets:
  time_budget_s: 60
  hard_timeout_s: 90
  max_experiments: 10
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 5
anomaly:
  floor: 0.50
  relative: 0.5
results_columns:
  - "TODO_metric_1"
  - "TODO_metric_2"
approved_at: "TODO"
approved_by: "human"
---

## 1. Rationale

TODO — Why this metric? Why this CV scheme? Why this budget?

## 2. How keep/discard is decided

TODO — Precise verdict rules. Example:
Reviewer verdict = `keep` iff delta > 0 AND `tools/anomaly` did not fire AND
`tools/bootstrap_ci` did not report a regression.

## 3. How plateau is handled

After `plateau_trigger.consecutive_discards` consecutive non-keep verdicts,
the driver automatically triggers the Historian role. The Historian produces
`state/STRATEGY_MEMO.md`. The Planner reads it before the next plan.

## 4. Contract change policy

Contracts are sticky. Any change requires a C3-gate Planner escalation and human approval.
```

### 3.4 `campaigns/_template/contracts/PRIORS.md`

```markdown
---
schema_version: 1
problem_id: "<campaign_id>"
last_campaign: "none"
updated_at: "TODO"
---

## Known good

(No prior knowledge yet. Updated as the campaign progresses.)

## Known bad

(No prior knowledge yet. Updated as the campaign progresses.)

## Known ceilings

(No prior knowledge yet. Updated as the campaign progresses.)

## Open questions

- TODO: What questions should this campaign answer?
```

### 3.5 `campaigns/_template/contracts/STRATEGY_GUIDE.md`

Create a **symlink** (not a copy):

```bash
cd campaigns/_template/contracts/
ln -s ../../../runner/contracts/STRATEGY_GUIDE.md STRATEGY_GUIDE.md
```

This keeps a single source of truth. If symlinks cause issues on Windows, copy the file
from `runner/contracts/STRATEGY_GUIDE.md` instead.

### 3.6 `campaigns/_template/prepare.py`

```python
"""
Frozen evaluation and data infrastructure for the <campaign_id> campaign.

DO NOT MODIFY this file. It is the fixed evaluation contract for this campaign.
The Executor may only read from this module — never write to it.

Data source: TODO — describe your data source here
             TODO — note caching strategy if applicable

Provides:
    - Constants: TIME_BUDGET, RANDOM_SEED, TARGET_COL
    - load_data()              — loads dataset from file/database
    - get_splits(feature_set)  — returns train/val/test splits
    - evaluate(model, X_val, y_val)  — computes primary + secondary metrics
    - print_summary(metrics, ...)    — structured stdout block for log parsing

Usage:
    from prepare import get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
"""

import os
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants (frozen — do not modify after campaign starts)
# ---------------------------------------------------------------------------

TIME_BUDGET = 90            # TODO: seconds per experiment (model training only)
RANDOM_SEED = 42
TARGET_COL = "TODO_target"  # TODO: replace with your target column name

_CAMPAIGN_DIR = Path(__file__).parent
_REPO_ROOT = _CAMPAIGN_DIR.parent.parent

# TODO: set the path to your dataset
# Option A: local file
# DATA_PATH = _REPO_ROOT / "data" / "your_dataset.csv"
# Option B: parquet cache with BigQuery fallback
# CACHE_PATH = _CAMPAIGN_DIR / ".cache" / "your_data.parquet"

# ---------------------------------------------------------------------------
# Columns to exclude from features (leakage, identifiers, target)
# ---------------------------------------------------------------------------

EXCLUDE_COLUMNS = frozenset([
    # TODO: add identifier columns (e.g., "user_id", "record_id")
    # TODO: add target and target-derived columns
    # TODO: add any columns flagged in DATA_CONTRACT leakage audit
])

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Load the dataset.

    TODO: implement data loading logic.
    Options:
      - pd.read_csv(DATA_PATH)
      - pd.read_parquet(CACHE_PATH) with database fallback
      - Any other data source

    Must return a DataFrame with all features + target column.
    """
    raise NotImplementedError("TODO: implement load_data()")


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------

def get_splits(
    feature_set: str = "all",
    df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series, pd.Series, pd.Series]:
    """Return train/val/test splits.

    TODO: implement splitting logic matching your DATA_CONTRACT.
    Options:
      - Stratified random split (for i.i.d. data)
      - Temporal split (for time-series data)
      - Group split (for clustered data)

    Args:
        feature_set: which features to include (campaign-specific)
        df: optional pre-loaded DataFrame (skips load_data if provided)

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
    """
    raise NotImplementedError("TODO: implement get_splits()")


# ---------------------------------------------------------------------------
# Evaluation (DO NOT CHANGE after campaign starts — this is the fixed metric)
# ---------------------------------------------------------------------------

def evaluate(model, X_val: pd.DataFrame, y_val: pd.Series) -> Dict[str, float]:
    """Compute evaluation metrics for a fitted model on the validation split.

    TODO: implement metrics matching your EVAL_PROTOCOL.results_columns.
    Must return a dict with keys matching EVAL_PROTOCOL.results_columns.
    The model must implement predict_proba() or predict().

    Example return:
        {"val_pr_auc": 0.85, "lift_at_10": 5.2, "macro_f1": 0.72}
    """
    raise NotImplementedError("TODO: implement evaluate()")


def print_summary(
    metrics: Dict[str, float],
    training_time: float,
    total_time: float,
    n_features: int,
    description: str = "",
) -> None:
    """Print a structured summary block for machine parsing.

    The Reviewer parses this block from run.log using grep.
    Key format: '<key>: <value>' with fixed keys matching results_columns.

    TODO: update the print statements below to match your
    EVAL_PROTOCOL.results_columns.
    """
    print("---")
    # TODO: print each metric from your results_columns, e.g.:
    # print(f"val_pr_auc:       {metrics.get('val_pr_auc', 0.0):.6f}")
    # print(f"lift_at_10:       {metrics.get('lift_at_10', 0.0):.6f}")
    print(f"training_seconds: {training_time:.1f}")
    print(f"total_seconds:    {total_time:.1f}")
    print(f"n_features:       {n_features}")
    print(f"description:      {description}")
    print("---")


# ---------------------------------------------------------------------------
# Main (data verification — run to validate your setup)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = load_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Target distribution:\n{df[TARGET_COL].value_counts().sort_index()}")
    print(f"Target rate: {df[TARGET_COL].mean():.4%}")

    X_train, X_val, X_test, y_train, y_val, y_test = get_splits(df=df)
    print(f"\nSplits:")
    print(f"  Train: {X_train.shape[0]:,} samples ({y_train.mean():.4%})")
    print(f"  Val:   {X_val.shape[0]:,} samples ({y_val.mean():.4%})")
    print(f"  Test:  {X_test.shape[0]:,} samples ({y_test.mean():.4%})")
    print(f"  Features: {X_train.shape[1]}")
    print("\nReady for experiments.")
```

### 3.7 `campaigns/_template/train.py`

```python
"""
Auto-train experiment script for campaign: <campaign_id>
Single-file ML pipeline — the ONLY file the Executor edits.

Data: TODO — describe your dataset
Primary metric: TODO — from EVAL_PROTOCOL

Run from repo root:
    PYTHONPATH=. python3 campaigns/<campaign_id>/train.py \
        > campaigns/<campaign_id>/run.log 2>&1
"""

import os
import signal
import time
import warnings

import numpy as np
import pandas as pd

from prepare import (
    get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
)

warnings.filterwarnings("ignore")

HARD_TIMEOUT = 90  # TODO: match EVAL_PROTOCOL.budgets.hard_timeout_s


def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)


if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# --- Experiment config — Executor edits ONLY this section ----------------
DESCRIPTION = "TODO: baseline description"
FEATURE_SET = "all"  # TODO: match prepare.py's feature_set options
# -------------------------------------------------------------------------

t_start = time.time()

X_train, X_val, X_test, y_train, y_val, y_test = get_splits(FEATURE_SET)

t_train_start = time.time()

# TODO: implement your baseline model
# Example:
#   import lightgbm as lgb
#   model = lgb.LGBMClassifier(random_state=RANDOM_SEED, verbose=-1)
#   model.fit(X_train, y_train)

raise NotImplementedError("TODO: implement baseline model training")

training_time = time.time() - t_train_start
metrics = evaluate(model, X_val, y_val)
total_time = time.time() - t_start

for k, v in metrics.items():
    print(f"{k}: {v:.6f}")

print_summary(
    metrics=metrics,
    training_time=training_time,
    total_time=total_time,
    n_features=X_train.shape[1],
    description=DESCRIPTION,
)
```

### 3.8 `campaigns/_template/RUNNER.md`

```markdown
# RUNNER.md — <campaign_id> Campaign Entry Point

You are running an autonomous ML experiment campaign. **Read this file first, then follow pointers.**

## 0. Orientation

- Problem + success criteria: `contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `contracts/EVAL_PROTOCOL.md` (G3)
- Current state: `state/CAMPAIGN_STATE.json`
- History: `state/results.tsv`, `state/REVIEW.md`
- Memory: `state/DEAD_ENDS.md`, `state/NOTEBOOK.md`
- Retrospective: `state/CAMPAIGN_JOURNAL.md`
- Exploration frontier: `state/UNEXPLORED_TECHNIQUES.md`
- Priors: `contracts/PRIORS.md`

**Primary metric:** See EVAL_PROTOCOL.md.
**Campaign dir flag:** `--campaign-dir campaigns/<campaign_id>` (pass to all `run_round.sh` calls).

## 1. Your role for this turn

Pick the role that matches the current state:

- **Planner** — invoked when state expects a new `NEXT_EXPERIMENT.md`. Read `runner/roles/planner.md`.
- **Executor** — invoked after Planner and driver validated the plan. Read `runner/roles/executor.md`.
- **Reviewer** — invoked after Executor run. Read `runner/roles/reviewer.md`.
- **Historian** — invoked when `historian_trigger_pending` is true. Read `runner/roles/historian.md`.

The driver tells you which role: `./runner/run_round.sh <stage> --campaign-dir campaigns/<campaign_id>`

**Path substitution note:** Wherever `runner/roles/*.md` says `runner/contracts/` or `runner/state/`, substitute `campaigns/<campaign_id>/contracts/` and `campaigns/<campaign_id>/state/` respectively.

## 2. Hard invariants (never bypass)

1. G1-G3 signed before any experiment (driver refuses to init otherwise).
2. `runner/tools/anomaly.py` runs before any `keep` verdict.
3. Both mandatory tools from EVAL_PROTOCOL.md run before `keep`.
4. One git commit per experiment — driver enforces.
5. **Campaign branch:** `campaign/<campaign_id>`. All experiment commits on this branch.
6. Two repair attempts cap — Executor enforces.
7. Contracts are sticky — change only via C3 (approved diff).
8. **Executor write scope:** Only `campaigns/<campaign_id>/train.py` and any declared `experiment_helpers/<exp_id>/` files.

## 3. Key operational notes

- **Run command:** `PYTHONPATH=. python3 campaigns/<campaign_id>/train.py > campaigns/<campaign_id>/run.log 2>&1`
- **Metrics in run.log:** The Reviewer must parse metrics from the `---` block.

## 4. Fossil record

Read `runner/AGENTS.md` every role invocation for cross-campaign harness rules.
Campaign-specific lessons are in `state/NOTEBOOK.md` and `DEAD_ENDS.md`.
```

---

## 4. Files to Create: `campaigns/_example/`

The example campaign demonstrates a working end-to-end setup using the
[Kaggle Credit Card Fraud Detection dataset](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
(`data/creditcard.csv`, 284,807 rows, 31 columns, target: `Class`, fraud rate ~0.173%).

### 4.1 `campaigns/_example/contracts/PROBLEM_CONTRACT.md`

```markdown
---
schema_version: 1
campaign_id: "_example"
problem_title: "Credit Card Fraud Detection — Example Campaign"
task_type: "binary_classification"
unit_of_observation: "transaction"
target:
  name: "Class"
  positive_class: 1
  definition: "1 = fraudulent transaction, 0 = legitimate"
success_criteria:
  - "val_pr_auc >= 0.75"
constraints:
  - "No leakage: do not use Class or any derived fraud label as a feature"
  - "Fixed splits: stratified 60/20/20, seed=42 — do not re-split"
  - "Hard timeout: 90s per experiment"
non_goals:
  - "Production deployment"
  - "Full hyperparameter search"
approved_at: "2026-05-01"
approved_by: "human"
---

## 1. Task

Binary classification: predict whether a credit card transaction is fraudulent (Class=1).

## 2. Why the task matters

Example campaign for the auto-train harness. The goal is to demonstrate the harness
end-to-end, not to achieve production-grade fraud detection.

## 3. Success criteria (detail)

`val_pr_auc >= 0.75` on the fixed val split. PR-AUC is the correct primary metric for
extreme class imbalance (~0.17% fraud rate). A random classifier scores ~0.0017; a basic
LightGBM baseline scores ~0.75-0.85.

## 4. Constraints (detail)

Stratified splits are fixed by seed=42 in prepare.py. The Executor must not change split
logic. The 90s hard timeout is enforced via SIGALRM in train.py.

## 5. Non-goals (detail)

This campaign has a 10-round budget. Deep hyperparameter optimization and ensemble stacking
are out of scope.
```

### 4.2 `campaigns/_example/contracts/DATA_CONTRACT.md`

```markdown
---
schema_version: 1
campaign_id: "_example"
data_sources:
  - path: "data/creditcard.csv"
    n_rows: 284807
    n_cols: 31
    primary_key: "row_index"
temporal:
  is_temporal: false
  order_column: "Time"
  prediction_time_column: null
columns:
  - name: "Time"
    dtype: "float64"
    description: "Seconds elapsed since first transaction in dataset"
  - name: "V1-V28"
    dtype: "float64"
    description: "PCA-transformed features (original columns inaccessible)"
  - name: "Amount"
    dtype: "float64"
    description: "Transaction amount in currency units"
  - name: "Class"
    dtype: "int64"
    description: "Target: 1=fraud, 0=legitimate. Positive rate ~0.173%"
leakage_audit:
  performed_at: "2026-05-01"
  flagged_columns: []
  notes: "No leakage risk. V1-V28 are PCA-transformed; original features inaccessible. Time is raw elapsed seconds with no future info."
splits:
  train: "60%"
  val: "20%"
  test: "20%"
  strategy: "stratified by Class, seed=42, fixed in prepare.py"
approved_at: "2026-05-01"
approved_by: "human"
---

## 1. Schema summary

31 columns: Time, V1-V28 (28 PCA features), Amount, Class (target).
All float64 except Class (int64). No missing values.

## 2. Availability table (narrative)

Single CSV file at `data/creditcard.csv`. Download with `scripts/download-example-data.sh`.
No external dependencies.

## 3. Leakage audit summary

Leakage audit performed 2026-05-01. Zero flagged columns. V1-V28 are PCA-transformed at
source. `Time` is raw elapsed seconds — not a leakage risk.

## 4. Transformations applied pre-agent (if any)

None. prepare.py loads the raw CSV and performs all transformations inline.

## 5. Known data quality issues

Extreme class imbalance: 492 fraud cases out of 284,807 (0.173%). All models must
account for this via scale_pos_weight, class_weight, or resampling.
```

### 4.3 `campaigns/_example/contracts/EVAL_PROTOCOL.md`

```markdown
---
schema_version: 1
campaign_id: "_example"
primary_metric:
  name: "val_pr_auc"
  direction: "maximize"
  noise_floor: 0.005
acceptance_threshold:
  baseline_family: "lgbm_balanced"
  min_improvement: 0.005
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: "Fixed stratified 60/20/20 split in prepare.py."
bootstrap_ci:
  enabled: true
  n_boot: 500
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools:
  - "runner.tools.anomaly"
  - "runner.tools.bootstrap_ci"
action_types:
  - "A_model"
  - "A_feature"
  - "A_hp"
  - "A_imbalance"
  - "A_ensemble"
  - "A_validate"
budgets:
  time_budget_s: 60
  hard_timeout_s: 90
  max_experiments: 10
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 5
anomaly:
  floor: 0.50
  relative: 0.5
results_columns:
  - "val_pr_auc"
  - "lift_at_10"
  - "macro_f1"
  - "val_f1"
approved_at: "2026-05-01"
approved_by: "human"
---

## 1. Rationale

Example campaign: 10-round budget, single holdout. Primary metric is PR-AUC for extreme
imbalance (0.17% fraud). Mandatory tools: anomaly detection and bootstrap CI.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff delta_val_pr_auc > 0 AND `tools/anomaly` did not fire AND
`tools/bootstrap_ci` did not report a regression (CI of new < CI_lo of best).

## 3. How plateau is handled

After `plateau_trigger.consecutive_discards` (3) consecutive non-keep verdicts,
`review_finalize` automatically sets `historian_trigger_pending = true`. The Historian
produces `state/STRATEGY_MEMO.md`. The Planner reads it before the next plan.

## 4. Contract change policy

Contracts are sticky. Any change requires a C3-gate Planner escalation and human approval.
```

### 4.4 `campaigns/_example/contracts/PRIORS.md`

```markdown
---
schema_version: 1
problem_id: "_example"
last_campaign: "none"
updated_at: "2026-05-01"
---

## Known good

- LightGBM with `scale_pos_weight` is a strong baseline for imbalanced fraud detection.
- `np.log1p(Amount)` adds signal.

## Known bad

- SMOTE + scale_pos_weight double-counts imbalance.
- Sklearn GradientBoostingClassifier exceeds 90s timeout on 170K rows.

## Known ceilings

- Single-holdout PR-AUC plateaus around 0.85 on this dataset/split.

## Open questions

- Does XGBoost outperform LightGBM on this dataset?
- Do Amount interactions (Amount * V1, Amount * V2) add signal?
```

### 4.5 `campaigns/_example/contracts/STRATEGY_GUIDE.md`

Symlink, same as template:
```bash
cd campaigns/_example/contracts/
ln -s ../../../runner/contracts/STRATEGY_GUIDE.md STRATEGY_GUIDE.md
```

### 4.6 `campaigns/_example/prepare.py`

```python
"""
Frozen evaluation and data infrastructure for the _example campaign.

DO NOT MODIFY this file. It is the fixed evaluation contract for this campaign.
The Executor may only read from this module — never write to it.

Data source: data/creditcard.csv (284,807 transactions, 31 columns)

Provides:
    - Constants: TIME_BUDGET, RANDOM_SEED, TARGET_COL
    - load_data()          — loads creditcard.csv
    - get_splits()         — stratified 60/20/20 train/val/test splits
    - evaluate(model, X_val, y_val)  — computes val_pr_auc + secondary metrics
    - print_summary(metrics, ...)    — structured stdout block for log parsing

Usage:
    from prepare import get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
"""

import os
import warnings
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants (frozen — do not modify)
# ---------------------------------------------------------------------------

TIME_BUDGET = 60
RANDOM_SEED = 42
TARGET_COL = "Class"

_CAMPAIGN_DIR = Path(__file__).parent
_REPO_ROOT = _CAMPAIGN_DIR.parent.parent
DATA_PATH = _REPO_ROOT / "data" / "creditcard.csv"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Load the credit card fraud dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Data file not found at {DATA_PATH}.\n"
            f"Run: scripts/download-example-data.sh"
        )
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df):,} rows from {DATA_PATH.name}")
    return df


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------

def get_splits(
    feature_set: str = "all",
    df=None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series, pd.Series, pd.Series]:
    """Return stratified 60/20/20 train/val/test splits.

    Args:
        feature_set: ignored for this campaign (all 30 features used)
        df: optional pre-loaded DataFrame

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
    """
    if df is None:
        df = load_data()

    X = df.drop(columns=[TARGET_COL])
    y = df[TARGET_COL]

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, stratify=y_trainval,
        random_state=RANDOM_SEED,
    )

    for name, split_y in [("train", y_train), ("val", y_val), ("test", y_test)]:
        prev = split_y.mean() * 100
        print(f"  {name}: {len(split_y):,} rows, "
              f"{int(split_y.sum())} positives ({prev:.2f}%)")
    print(f"  Features: {X_train.shape[1]}")

    return (
        X_train.reset_index(drop=True),
        X_val.reset_index(drop=True),
        X_test.reset_index(drop=True),
        y_train.reset_index(drop=True),
        y_val.reset_index(drop=True),
        y_test.reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# Evaluation (DO NOT CHANGE — this is the fixed metric)
# ---------------------------------------------------------------------------

def evaluate(model, X_val: pd.DataFrame, y_val: pd.Series) -> Dict[str, float]:
    """Compute evaluation metrics for a fitted model.

    Primary metric: val_pr_auc
    Secondary:      lift_at_10, macro_f1, val_f1

    The model must implement predict_proba().
    """
    if not hasattr(model, "predict_proba"):
        raise ValueError("Model must implement predict_proba().")

    y_val_arr = np.asarray(y_val)
    y_prob = model.predict_proba(X_val)[:, 1]

    val_pr_auc = float(average_precision_score(y_val_arr, y_prob))

    # Lift at top 10%
    thresh = np.percentile(y_prob, 90.0)
    flagged = y_prob >= thresh
    if flagged.sum() > 0:
        lift_at_10 = float(y_val_arr[flagged].mean() / (y_val_arr.mean() + 1e-12))
    else:
        lift_at_10 = 0.0

    # F1 at PR-optimal threshold
    _prec, _rec, _thr = precision_recall_curve(y_val_arr, y_prob)
    _f1s = 2 * _prec * _rec / (_prec + _rec + 1e-10)
    _best_thr = float(_thr[np.argmax(_f1s[:-1])]) if len(_thr) > 0 else 0.5
    y_pred = (y_prob >= _best_thr).astype(int)
    macro_f1 = float(f1_score(y_val_arr, y_pred, average="macro", zero_division=0))
    val_f1 = float(f1_score(y_val_arr, y_pred, average="weighted", zero_division=0))

    return {
        "val_pr_auc": val_pr_auc,
        "lift_at_10": lift_at_10,
        "macro_f1": macro_f1,
        "val_f1": val_f1,
    }


def print_summary(
    metrics: Dict[str, float],
    training_time: float,
    total_time: float,
    n_features: int,
    description: str = "",
) -> None:
    """Print a structured summary block for machine parsing."""
    print("---")
    print(f"val_pr_auc:       {metrics.get('val_pr_auc', 0.0):.6f}")
    print(f"lift_at_10:       {metrics.get('lift_at_10', 0.0):.6f}")
    print(f"macro_f1:         {metrics.get('macro_f1', 0.0):.6f}")
    print(f"val_f1:           {metrics.get('val_f1', 0.0):.6f}")
    print(f"training_seconds: {training_time:.1f}")
    print(f"total_seconds:    {total_time:.1f}")
    print(f"n_features:       {n_features}")
    print(f"description:      {description}")
    print("---")


# ---------------------------------------------------------------------------
# Main (data verification)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = load_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Target distribution:\n{df[TARGET_COL].value_counts().sort_index()}")
    print(f"Fraud rate: {df[TARGET_COL].mean():.4%}")

    X_train, X_val, X_test, y_train, y_val, y_test = get_splits(df=df)
    print(f"\nSplits:")
    print(f"  Train: {X_train.shape[0]:,} ({y_train.mean():.4%} fraud)")
    print(f"  Val:   {X_val.shape[0]:,} ({y_val.mean():.4%} fraud)")
    print(f"  Test:  {X_test.shape[0]:,} ({y_test.mean():.4%} fraud)")
    print(f"  Features: {X_train.shape[1]}")
    print("\nReady for experiments.")
```

### 4.7 `campaigns/_example/train.py`

```python
"""
Auto-train experiment script for campaign: _example
Single-file ML pipeline — the ONLY file the Executor edits.

Data: data/creditcard.csv (284,807 rows x 31 cols, target: Class)
Primary metric: val_pr_auc (Average Precision Score / PR-AUC)

Run from repo root:
    PYTHONPATH=. python3 campaigns/_example/train.py \
        > campaigns/_example/run.log 2>&1
"""

import os
import signal
import time
import warnings

import numpy as np
import pandas as pd

from prepare import (
    get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
)

warnings.filterwarnings("ignore")

HARD_TIMEOUT = 90


def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)


if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# --- Experiment config — Executor edits ONLY this section ----------------
DESCRIPTION = "baseline: LightGBM with scale_pos_weight, default params"
FEATURE_SET = "all"
# -------------------------------------------------------------------------

t_start = time.time()

X_train, X_val, X_test, y_train, y_val, y_test = get_splits(FEATURE_SET)

n_pos = int(y_train.sum())
n_neg = len(y_train) - n_pos
scale_pw = round(n_neg / n_pos, 2)
print(f"scale_pos_weight: {scale_pw}")

t_train_start = time.time()

import lightgbm as lgb

model = lgb.LGBMClassifier(
    n_estimators=1000,
    learning_rate=0.05,
    num_leaves=31,
    scale_pos_weight=scale_pw,
    random_state=RANDOM_SEED,
    n_jobs=4,
    verbose=-1,
)
model.fit(X_train, y_train)
print(f"LGBM trained ({time.time()-t_start:.1f}s)")

training_time = time.time() - t_train_start
metrics = evaluate(model, X_val, y_val)
total_time = time.time() - t_start

for k, v in metrics.items():
    print(f"{k}: {v:.6f}")

print_summary(
    metrics=metrics,
    training_time=training_time,
    total_time=total_time,
    n_features=X_train.shape[1],
    description=DESCRIPTION,
)
```

### 4.8 `campaigns/_example/RUNNER.md`

```markdown
# RUNNER.md — _example Campaign Entry Point

You are running the example credit card fraud detection campaign.
**Read this file first, then follow pointers.**

## 0. Orientation

- Problem + success criteria: `contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `contracts/EVAL_PROTOCOL.md` (G3)
- Current state: `state/CAMPAIGN_STATE.json`
- History: `state/results.tsv`, `state/REVIEW.md`
- Memory: `state/DEAD_ENDS.md`, `state/NOTEBOOK.md`
- Retrospective: `state/CAMPAIGN_JOURNAL.md`
- Exploration frontier: `state/UNEXPLORED_TECHNIQUES.md`
- Priors: `contracts/PRIORS.md`

**Primary metric:** `val_pr_auc` (PR-AUC for fraud detection).
**Campaign dir flag:** `--campaign-dir campaigns/_example`

## 1. Your role for this turn

- **Planner** — read `runner/roles/planner.md`
- **Executor** — read `runner/roles/executor.md`
- **Reviewer** — read `runner/roles/reviewer.md`
- **Historian** — read `runner/roles/historian.md`

The driver tells you which role:
`./runner/run_round.sh <stage> --campaign-dir campaigns/_example`

**Path substitution note:** Wherever `runner/roles/*.md` says `runner/contracts/` or
`runner/state/`, substitute `campaigns/_example/contracts/` and
`campaigns/_example/state/` respectively.

## 2. Hard invariants (never bypass)

1. G1-G3 signed before any experiment.
2. `runner/tools/anomaly.py` + `runner/tools/bootstrap_ci` before any `keep`.
3. One git commit per experiment.
4. **Campaign branch:** `campaign/_example`.
5. Two repair attempts cap.
6. Contracts are sticky.
7. **Executor write scope:** Only `campaigns/_example/train.py`.

## 3. Key operational notes

- **Data:** Run `scripts/download-example-data.sh` to get `data/creditcard.csv`.
- **Run command:** `PYTHONPATH=. python3 campaigns/_example/train.py > campaigns/_example/run.log 2>&1`
- **Metrics:** Parse `val_pr_auc`, `lift_at_10`, `macro_f1`, `val_f1` from `---` block.
- **bootstrap_ci metric:** Use `metric="pr_auc"` (matches primary metric).

## 4. Fossil record

Read `runner/AGENTS.md` every role invocation.
```

---

## 5. Files to Create: `scripts/`

### 5.1 `scripts/new-campaign.sh`

```bash
#!/usr/bin/env bash
# Creates a new campaign from the _template skeleton.
# Usage: scripts/new-campaign.sh <campaign-id>
set -euo pipefail

CAMPAIGN_ID=${1:?"Usage: scripts/new-campaign.sh <campaign-id>"}

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/campaigns/_template"
TARGET_DIR="$REPO_ROOT/campaigns/$CAMPAIGN_ID"

if [ -d "$TARGET_DIR" ]; then
    echo "Error: campaign directory already exists: $TARGET_DIR"
    exit 1
fi

if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "Error: template directory not found: $TEMPLATE_DIR"
    exit 1
fi

echo "Creating campaign: $CAMPAIGN_ID"

# Copy template
cp -r "$TEMPLATE_DIR" "$TARGET_DIR"

# Create state directory with skeleton files
mkdir -p "$TARGET_DIR/state"

cat > "$TARGET_DIR/state/DEAD_ENDS.md" << EOF
---
schema_version: 1
campaign_id: "$CAMPAIGN_ID"
count: 0
last_updated: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

(No dead ends recorded yet.)
EOF

cat > "$TARGET_DIR/state/NOTEBOOK.md" << EOF
---
schema_version: 1
campaign_id: "$CAMPAIGN_ID"
count: 0
last_updated: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

(No observations recorded yet.)
EOF

cat > "$TARGET_DIR/state/UNEXPLORED_TECHNIQUES.md" << 'EOF'
# Unexplored Techniques

Technique classes not yet tried. Planner reads this every round.
Mandatory check when consecutive_discards >= 2.

(Populated by Planner and Reviewer during the campaign.)
EOF

cat > "$TARGET_DIR/state/ASSUMPTION_REGISTER.md" << EOF
---
schema_version: 1
campaign_id: "$CAMPAIGN_ID"
count: 0
last_updated: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

(No assumptions recorded yet.)
EOF

cat > "$TARGET_DIR/state/CAMPAIGN_JOURNAL.md" << 'EOF'
# Campaign Journal

Planned reasoning vs actual outcome per round. Reviewer-owned.

(Entries added by Reviewer after each experiment.)
EOF

cat > "$TARGET_DIR/state/PATTERN_BOOK.md" << EOF
---
schema_version: 1
campaign_id: "$CAMPAIGN_ID"
count: 0
last_updated: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

(No patterns recorded yet. Historian adds entries after periodic analysis.)
EOF

# Replace <campaign_id> placeholder in all text files
find "$TARGET_DIR" -type f \( -name "*.md" -o -name "*.py" \) \
    -exec sed -i "s/<campaign_id>/$CAMPAIGN_ID/g" {} +

echo ""
echo "Campaign created at: $TARGET_DIR"
echo ""
echo "Next steps:"
echo "  1. Fill in contracts:"
echo "     - $TARGET_DIR/contracts/PROBLEM_CONTRACT.md"
echo "     - $TARGET_DIR/contracts/DATA_CONTRACT.md"
echo "     - $TARGET_DIR/contracts/EVAL_PROTOCOL.md"
echo "     - $TARGET_DIR/contracts/PRIORS.md"
echo "  2. Implement the evaluation harness:"
echo "     - $TARGET_DIR/prepare.py"
echo "  3. Set up the baseline in:"
echo "     - $TARGET_DIR/train.py"
echo "  4. Initialize the campaign:"
echo "     ./runner/run_round.sh init --campaign-dir campaigns/$CAMPAIGN_ID"
echo ""
echo "See README.md for the full quickstart guide."
```

**Make executable:** `chmod +x scripts/new-campaign.sh`

### 5.2 `scripts/update-harness.sh`

```bash
#!/usr/bin/env bash
# Pull infrastructure updates from upstream without touching campaigns/.
# Usage: scripts/update-harness.sh <upstream-remote>
#
# First-time setup:
#   git remote add upstream https://github.com/<owner>/auto-train.git
#
# Then:
#   scripts/update-harness.sh upstream
set -euo pipefail

UPSTREAM=${1:?"Usage: scripts/update-harness.sh <upstream-remote>"}

echo "Fetching from $UPSTREAM..."
git fetch "$UPSTREAM" main

echo "Updating infrastructure files..."
git checkout "$UPSTREAM/main" -- \
    runner/ \
    shared/ \
    log.py \
    .claude/agents/ \
    .cursor/rules/ \
    scripts/ \
    AGENT_GUIDE.md \
    AGENTS.md \
    requirements.txt

echo ""
echo "Updated infrastructure from $UPSTREAM/main."
echo "Your campaigns/ directory is untouched."
echo ""
echo "Review changes with:  git diff --cached"
echo "Commit with:          git commit -m 'chore: update harness from upstream'"
```

**Make executable:** `chmod +x scripts/update-harness.sh`

### 5.3 `scripts/download-example-data.sh`

```bash
#!/usr/bin/env bash
# Download the credit card fraud dataset for the _example campaign.
# Source: Kaggle (via direct mirror)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
DATA_FILE="$DATA_DIR/creditcard.csv"

if [ -f "$DATA_FILE" ]; then
    echo "Data already exists: $DATA_FILE"
    exit 0
fi

mkdir -p "$DATA_DIR"

echo "Downloading creditcard.csv..."
echo ""
echo "Option 1: If you have kaggle CLI installed:"
echo "  kaggle datasets download -d mlg-ulb/creditcardfraud -p $DATA_DIR --unzip"
echo ""
echo "Option 2: Download manually from:"
echo "  https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud"
echo "  and place creditcard.csv in $DATA_DIR/"
echo ""

# Attempt kaggle CLI download
if command -v kaggle &> /dev/null; then
    kaggle datasets download -d mlg-ulb/creditcardfraud -p "$DATA_DIR" --unzip
    echo "Downloaded successfully to $DATA_FILE"
else
    echo "kaggle CLI not found. Please download manually."
    exit 1
fi
```

**Make executable:** `chmod +x scripts/download-example-data.sh`

---

## 6. Files to Create: AI Routing Layer

### 6.1 `AGENT_GUIDE.md`

```markdown
# AGENT_GUIDE.md — AI Routing Index

**For AI agents reading this repo.** Humans: see [README.md](README.md).

This file tells you where to find what you need, based on your role.

## Quick routing

| If you are the... | Read these files first |
|---|---|
| **Planner** | `runner/roles/planner.md`, then your campaign's `contracts/`, `state/CAMPAIGN_STATE.json`, `state/results.tsv`, `state/DEAD_ENDS.md` |
| **Executor** | `runner/roles/executor.md`, then your campaign's `state/NEXT_EXPERIMENT.md`, `train.py`, contracts |
| **Reviewer** | `runner/roles/reviewer.md`, then your campaign's `run.log`, `train.py`, `state/NEXT_EXPERIMENT.md`, contracts |
| **Historian** | `runner/roles/historian.md`, then your campaign's `state/CAMPAIGN_JOURNAL.md`, `state/results.tsv`, `state/PATTERN_BOOK.md` |

## Artifact ownership

| File | Written by | Read by |
|---|---|---|
| `campaigns/<id>/contracts/*` | Human (at setup) | All roles |
| `campaigns/<id>/prepare.py` | Human (at setup) | Executor (read-only) |
| `campaigns/<id>/train.py` | Executor | Reviewer, Planner |
| `campaigns/<id>/run.log` | Executor (stdout redirect) | Reviewer |
| `campaigns/<id>/state/NEXT_EXPERIMENT.md` | Planner | Executor, Reviewer |
| `campaigns/<id>/state/REVIEW.md` | Reviewer (via driver) | Planner |
| `campaigns/<id>/state/CAMPAIGN_STATE.json` | Driver (`run_round.sh`) | All roles |
| `campaigns/<id>/state/results.tsv` | Driver (via `log.py`) | All roles |
| `campaigns/<id>/state/DEAD_ENDS.md` | Reviewer | Planner |
| `campaigns/<id>/state/NOTEBOOK.md` | Reviewer | Planner |
| `campaigns/<id>/state/CAMPAIGN_JOURNAL.md` | Reviewer | Planner, Historian |
| `campaigns/<id>/state/ASSUMPTION_REGISTER.md` | Reviewer, Historian | Planner, Historian |
| `campaigns/<id>/state/PATTERN_BOOK.md` | Historian | Planner |
| `campaigns/<id>/state/STRATEGY_MEMO.md` | Historian | Planner |
| `campaigns/<id>/state/UNEXPLORED_TECHNIQUES.md` | Planner, Reviewer | Planner |
| `campaigns/<id>/state/TOKEN_SUMMARY.txt` | Driver | Planner |

## Campaign discovery

Active campaigns live under `campaigns/`. Each campaign has:
- `RUNNER.md` — campaign entry point (read this first)
- `contracts/` — frozen problem, data, and evaluation contracts
- `state/` — mutable experiment state
- `prepare.py` — frozen evaluation harness
- `train.py` — mutable experiment script

To find the active campaign, check the git branch: `campaign/<campaign-id>`.

## Infrastructure (never modify during experiments)

- `runner/runner_driver.py` — state machine driver
- `runner/roles/` — role prompt definitions (single source of truth)
- `runner/tools/` — validation and analysis tools
- `runner/run_round.sh` — CLI wrapper for the driver
- `shared/` — shared utilities (metrics, data loading)
- `log.py` — results logging

## State machine flow

```
init → [Planner writes NEXT_EXPERIMENT.md]
     → plan-check (validates plan, checks escalation)
     → [Executor edits train.py, runs it]
     → execute-finalize (parses stdout, extracts channel)
     → [Reviewer reads run.log, runs mandatory tools, writes verdict]
     → review-finalize (applies verdict, updates state)
     → [if historian_trigger_pending: Historian runs]
     → historian-finalize (resets trigger, records output)
     → (loop back to Planner)
```

## Hard invariants

1. Only `campaigns/<id>/train.py` is modified by Executor during experiments.
2. `campaigns/<id>/prepare.py`, contracts, `runner/`, `shared/` are read-only.
3. One git commit per experiment.
4. Primary metric + budgets live in `campaigns/<id>/contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky; change via C3 + `tools/contract_diff` + human approval.
6. Two repair attempts max per experiment.

## Running experiments

```bash
# Initialize campaign (validates G1/G2/G3 contracts)
./runner/run_round.sh init --campaign-dir campaigns/<id>

# After Planner writes NEXT_EXPERIMENT.md:
./runner/run_round.sh plan-check --campaign-dir campaigns/<id>

# After Executor runs train.py:
./runner/run_round.sh execute-finalize \
    --campaign-dir campaigns/<id> \
    --stdout-file campaigns/<id>/executor_stdout.txt

# After Reviewer issues verdict:
./runner/run_round.sh review-finalize \
    --campaign-dir campaigns/<id> \
    --verdict keep \
    --commit <sha> \
    --metrics-json '{"val_pr_auc": 0.85}' \
    --action-type A_hp \
    --hypothesis "tune learning rate" \
    --description "LightGBM lr=0.01" \
    --model-family lgbm \
    --n-features 30 \
    --tools-ran '["runner.tools.anomaly", "runner.tools.bootstrap_ci"]'
```
```

### 6.2 `.claude/agents/planner.md`

```markdown
---
name: planner
model: opus
description: "ML experiment planner — reads campaign state and writes NEXT_EXPERIMENT.md"
---

You are the Planner role for an autonomous ML experiment campaign.

**Read and follow the instructions in `runner/roles/planner.md` exactly.** That file
is your complete role definition.

Before starting, also read:
- The campaign's `RUNNER.md` for campaign-specific context and path substitution rules
- `runner/AGENTS.md` for cross-campaign harness rules

**Path substitution:** Wherever `runner/roles/planner.md` references `runner/contracts/`
or `runner/state/`, substitute the campaign-specific paths:
- `runner/contracts/` → `campaigns/<campaign_id>/contracts/`
- `runner/state/` → `campaigns/<campaign_id>/state/`

The campaign directory is specified via `--campaign-dir` when invoking `run_round.sh`.
```

### 6.3 `.claude/agents/executor.md`

```markdown
---
name: executor
model: sonnet
description: "ML experiment executor — implements the plan in train.py and runs it"
---

You are the Executor role for an autonomous ML experiment campaign.

**Read and follow the instructions in `runner/roles/executor.md` exactly.** That file
is your complete role definition.

Before starting, also read:
- The campaign's `RUNNER.md` for campaign-specific context and path substitution rules
- `runner/AGENTS.md` for cross-campaign harness rules

**Critical paths for this campaign:**
- Edit ONLY: `campaigns/<campaign_id>/train.py`
- Run command: `PYTHONPATH=. python3 campaigns/<campaign_id>/train.py > campaigns/<campaign_id>/run.log 2>&1`
- NEVER modify: `campaigns/<campaign_id>/prepare.py`, any contracts, `runner/`, `shared/`
```

### 6.4 `.claude/agents/reviewer.md`

```markdown
---
name: reviewer
model: sonnet
description: "ML experiment reviewer — evaluates results and issues keep/discard verdict"
---

You are the Reviewer role for an autonomous ML experiment campaign.

**Read and follow the instructions in `runner/roles/reviewer.md` exactly.** That file
is your complete role definition.

Before starting, also read:
- The campaign's `RUNNER.md` for campaign-specific context and path substitution rules
- `runner/AGENTS.md` for cross-campaign harness rules

**Path substitution:** Wherever `runner/roles/reviewer.md` references `runner/contracts/`
or `runner/state/`, substitute the campaign-specific paths:
- `runner/contracts/` → `campaigns/<campaign_id>/contracts/`
- `runner/state/` → `campaigns/<campaign_id>/state/`
```

### 6.5 `.claude/agents/historian.md`

```markdown
---
name: historian
model: opus
description: "Campaign historian — analyzes trajectory, extracts patterns, audits assumptions"
---

You are the Historian role for an autonomous ML experiment campaign.

**Read and follow the instructions in `runner/roles/historian.md` exactly.** That file
is your complete role definition.

Before starting, also read:
- The campaign's `RUNNER.md` for campaign-specific context and path substitution rules
- `runner/AGENTS.md` for cross-campaign harness rules

**Path substitution:** Wherever `runner/roles/historian.md` references `runner/contracts/`
or `runner/state/`, substitute the campaign-specific paths:
- `runner/contracts/` → `campaigns/<campaign_id>/contracts/`
- `runner/state/` → `campaigns/<campaign_id>/state/`
```

### 6.6 `.cursor/rules/harness.md`

```markdown
# Auto-Train Harness Rules

This repository is an autonomous ML experimentation harness. Read `AGENT_GUIDE.md`
for detailed routing.

## Hard invariants

1. Only `campaigns/<id>/train.py` is modified by the Executor during experiments.
2. `campaigns/<id>/prepare.py`, contracts, `runner/`, `shared/` are read-only.
3. One git commit per experiment.
4. Primary metric + budgets are in `campaigns/<id>/contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky — change via C3 + `tools/contract_diff` + human approval.
6. Two repair attempts max per experiment.

## Role routing

- Planner: read `runner/roles/planner.md`
- Executor: read `runner/roles/executor.md`
- Reviewer: read `runner/roles/reviewer.md`
- Historian: read `runner/roles/historian.md`

## Campaign structure

Each campaign lives in `campaigns/<id>/` with:
- `RUNNER.md` — entry point
- `contracts/` — frozen G1/G2/G3 contracts
- `state/` — mutable experiment state
- `prepare.py` — frozen evaluation harness
- `train.py` — mutable experiment script

## Running

```bash
./runner/run_round.sh init --campaign-dir campaigns/<id>
./runner/run_round.sh plan-check --campaign-dir campaigns/<id>
./runner/run_round.sh execute-finalize --campaign-dir campaigns/<id> --stdout-file ...
./runner/run_round.sh review-finalize --campaign-dir campaigns/<id> --verdict ...
```
```

---

## 7. Files to Create: Root-Level

### 7.1 `AGENTS.md` (root — rewrite)

```markdown
# AGENTS.md — Auto-Train Harness

> Read by: Claude Code, Codex CLI, GitHub Copilot, Cursor, and other AI coding tools.
> For detailed routing, see [AGENT_GUIDE.md](AGENT_GUIDE.md).
> For humans, see [README.md](README.md).

## Entry point

Start at the campaign's `RUNNER.md`:
- Each campaign lives in `campaigns/<id>/`
- The campaign `RUNNER.md` tells you which role to play
- Role definitions are in `runner/roles/`

## Hard invariants

1. **Only `campaigns/<id>/train.py` may be modified by the Executor** during an
   experiment. `prepare.py`, contracts, `runner/`, `shared/` are read-only.
2. **Primary metric** is defined in `campaigns/<id>/contracts/EVAL_PROTOCOL.md`.
3. **Every experiment is one git commit.** Discards roll back with `git reset --hard HEAD~1`.
4. **Budgets** (time + experiment count) are in `EVAL_PROTOCOL.budgets`.
5. **Contracts are sticky** — change only via C3 (`tools/contract_diff` + human approval).
6. **Two repair attempts** max per experiment (Executor enforces).

## File index

| Path | Purpose |
|---|---|
| `AGENT_GUIDE.md` | AI routing index (roles → files) |
| `runner/RUNNER.md` | Harness architecture + entry point |
| `runner/AGENTS.md` | Fossil record (cross-campaign lessons) |
| `runner/roles/*.md` | Role prompts (Planner, Executor, Reviewer, Historian) |
| `runner/tools/` | Validation + analysis tools |
| `runner/runner_driver.py` | State machine driver |
| `runner/run_round.sh` | CLI wrapper |
| `shared/metrics.py` | Metric computation |
| `log.py` | Results logging |
| `campaigns/_template/` | Skeleton for new campaigns |
| `campaigns/_example/` | Working demo (credit card fraud) |
| `scripts/new-campaign.sh` | Scaffold a new campaign |
```

### 7.2 `CLAUDE.md` (root — rewrite)

```markdown
# CLAUDE.md — Auto-Train Harness

Entry point: campaign's `RUNNER.md` → `runner/roles/*.md`.
AI routing: `AGENT_GUIDE.md`. Fossil record: `runner/AGENTS.md`.

## Hard invariants

1. Only `campaigns/<id>/train.py` is modified by Executor during experiments.
2. `campaigns/<id>/prepare.py`, contracts, `runner/`, `shared/` are read-only.
3. One git commit per experiment.
4. Primary metric + budgets live in `campaigns/<id>/contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky; change via C3 + `tools/contract_diff` + human approval.
6. Two repair attempts max per experiment.
```

### 7.3 `README.md` (root — rewrite)

````markdown
# Auto-Train: Autonomous ML Experiment Harness

An AI-native harness for running autonomous ML experiments. Fork this template,
bring your own data, and let any AI coding tool (Claude Code, Codex CLI, Cursor,
GitHub Copilot) run structured experiments with built-in safety guardrails.

## How it works

The harness orchestrates a multi-role experiment loop:

1. **Planner** designs a hypothesis and writes an experiment plan
2. **Executor** implements the plan in `train.py` and runs it
3. **Reviewer** evaluates results and issues a keep/discard verdict
4. **Historian** (periodic) analyzes trajectory and extracts patterns

Each role is a fresh AI invocation with defined inputs/outputs. The harness
provides contracts, state management, and 20+ analysis tools. The AI tool
you use (Claude Code, Cursor, etc.) IS the agent loop.

## 5-Minute Quickstart

### 1. Fork this repo

Click "Use this template" on GitHub, then clone your fork:

```bash
git clone https://github.com/<you>/auto-train.git
cd auto-train
pip install -r requirements.txt
```

### 2. Try the example campaign

```bash
# Download the example dataset (credit card fraud)
scripts/download-example-data.sh

# Initialize the example campaign
./runner/run_round.sh init --campaign-dir campaigns/_example
```

Then open the repo in your AI coding tool and say:
> "Read campaigns/_example/RUNNER.md and run the Planner role."

### 3. Create your own campaign

```bash
scripts/new-campaign.sh my-problem
```

This creates `campaigns/my-problem/` with skeleton files. Fill in:

1. **Contracts** (`contracts/PROBLEM_CONTRACT.md`, `DATA_CONTRACT.md`, `EVAL_PROTOCOL.md`)
   — Define your problem, data, and evaluation rules
2. **Evaluation harness** (`prepare.py`)
   — Load data, create splits, compute metrics
3. **Baseline** (`train.py`)
   — First experiment for the Executor to run

Then initialize and start experimenting:

```bash
./runner/run_round.sh init --campaign-dir campaigns/my-problem
```

## Architecture

```
campaigns/my-problem/          # Your campaign (one per problem)
├── contracts/                 # Frozen rules (human-approved)
│   ├── PROBLEM_CONTRACT.md    # What to predict and why
│   ├── DATA_CONTRACT.md       # Data schema + leakage audit
│   └── EVAL_PROTOCOL.md      # Metrics, budgets, verdict rules
├── state/                     # Mutable experiment state
├── prepare.py                 # Frozen eval harness (agent can't edit)
└── train.py                   # The ONE file the agent edits

runner/                        # Harness infrastructure (never edit)
├── roles/                     # Role prompts (Planner, Executor, etc.)
├── tools/                     # 20+ analysis tools
├── runner_driver.py           # State machine driver
└── run_round.sh               # CLI wrapper
```

## Safety guardrails

- **Contract system** — G1/G2/G3 gates validated before experiments begin
- **Write scope enforcement** — Executor can only modify `train.py`
- **Anomaly detection** — Catches suspiciously high/low metrics
- **Bootstrap CI** — Statistical significance testing
- **Repair cap** — Max 2 fix attempts per experiment
- **Plateau detection** — Auto-triggers Historian after 3 consecutive discards

## AI tool compatibility

| Tool | Entry point |
|---|---|
| Claude Code | `CLAUDE.md` → `.claude/agents/` |
| Codex CLI / GitHub Copilot | `AGENTS.md` |
| Cursor | `.cursor/rules/harness.md` |
| Any other AI tool | `AGENT_GUIDE.md` |

## Updating the harness

To pull infrastructure updates from the template:

```bash
git remote add upstream https://github.com/<owner>/auto-train.git
scripts/update-harness.sh upstream
```

This updates `runner/`, `shared/`, and tools without touching your `campaigns/`.

## License

[TODO: Choose a license]
````

### 7.4 `.gitignore` (rewrite)

```
# Experiment artifacts
campaigns/*/run.log
campaigns/*/executor_stdout.txt
campaigns/*/.cache/
campaigns/*/catboost_info/
catboost_info/

# Data (too large for git)
data/*.csv
data/*.parquet

# Python
__pycache__/
*.pyc
*.pyo
.cache/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
```

### 7.5 `data/README.md`

```markdown
# Data Directory

This directory holds datasets for campaigns. Data files are excluded from git
(see `.gitignore`).

## Example campaign data

The `_example` campaign uses the credit card fraud detection dataset:

```bash
scripts/download-example-data.sh
```

Or download manually from:
https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud

Place `creditcard.csv` in this directory.

## Your own data

For your campaigns, either:
1. Place data files here (they won't be committed to git)
2. Use a database/API and implement loading in your campaign's `prepare.py`
```

### 7.6 `requirements.txt`

```
# Auto-Train Harness Dependencies
# These are FIXED — the agent cannot install new packages.
scikit-learn>=1.5
xgboost>=3.0
lightgbm>=4.0
catboost>=1.2
imbalanced-learn>=0.12
optuna>=3.6
pandas>=2.0
numpy>=1.26
matplotlib>=3.5
pytest>=7.0
PyYAML>=6.0
scipy>=1.11
xxhash>=3.4
shap>=0.45
```

---

## 8. Verification Checklist

After creating all files, run these checks:

### 8.1 Test suite

```bash
python3 -m pytest tests/ -q
```

All tests should pass. The test suite validates schema validators, safety invariants,
tool correctness, and integration flows.

### 8.2 Campaign scaffold script

```bash
scripts/new-campaign.sh test-verify
```

Verify the scaffold:
- `campaigns/test-verify/` exists with all expected files
- `<campaign_id>` is replaced with `test-verify` everywhere
- `state/` directory has all skeleton files (DEAD_ENDS.md, NOTEBOOK.md, etc.)
- Contract templates have valid YAML frontmatter structure

Then clean up:
```bash
rm -rf campaigns/test-verify/
```

### 8.3 Example campaign init

```bash
# Download data first
scripts/download-example-data.sh

# This should succeed if contracts are schema-valid
./runner/run_round.sh init --campaign-dir campaigns/_example
```

Verify `campaigns/_example/state/CAMPAIGN_STATE.json` was created with round=0.

### 8.4 Example campaign train.py runs

```bash
PYTHONPATH=. python3 campaigns/_example/train.py
```

Should produce output with a `---` block containing `val_pr_auc`, `lift_at_10`, etc.

### 8.5 Symlinks

```bash
ls -la campaigns/_template/contracts/STRATEGY_GUIDE.md
ls -la campaigns/_example/contracts/STRATEGY_GUIDE.md
```

Both should be symlinks to `../../../runner/contracts/STRATEGY_GUIDE.md`.

### 8.6 File permissions

```bash
ls -la scripts/new-campaign.sh
ls -la scripts/update-harness.sh
ls -la scripts/download-example-data.sh
ls -la runner/run_round.sh
```

All should be executable (`-rwxr-xr-x`).

### 8.7 AI entry point check

Verify these files exist and are non-empty:
- `AGENTS.md`
- `CLAUDE.md`
- `AGENT_GUIDE.md`
- `.claude/agents/planner.md`
- `.claude/agents/executor.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/historian.md`
- `.cursor/rules/harness.md`

### 8.8 Git readiness

```bash
git init
git add -A
git status
```

Verify `data/*.csv` and `campaigns/*/.cache/` are properly excluded by `.gitignore`.

---

## 9. Implementation Order

Execute in this order to minimize backtracking:

1. **Copy infrastructure** from source repo: `runner/`, `shared/`, `tests/`, `log.py`
2. **Create root files**: `.gitignore`, `requirements.txt`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `AGENT_GUIDE.md`
3. **Create `data/README.md`**
4. **Create `scripts/`**: `new-campaign.sh`, `update-harness.sh`, `download-example-data.sh`
5. **Create `campaigns/_template/`**: all contracts, `prepare.py`, `train.py`, `RUNNER.md`, STRATEGY_GUIDE symlink
6. **Create `campaigns/_example/`**: all contracts, `prepare.py`, `train.py`, `RUNNER.md`, STRATEGY_GUIDE symlink
7. **Create `.claude/agents/`**: `planner.md`, `executor.md`, `reviewer.md`, `historian.md`
8. **Create `.cursor/rules/`**: `harness.md`
9. **Run verification checklist** (Section 8)

---

## 10. User Onboarding Flow

When a user forks this template, their journey is:

```
Fork repo → pip install → download example data → init example campaign
→ run a few experiment rounds to see the harness in action
→ scripts/new-campaign.sh my-problem
→ fill in contracts (PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL)
→ write prepare.py (load data, create splits, compute metrics)
→ write baseline train.py
→ git checkout -b campaign/my-problem
→ ./runner/run_round.sh init --campaign-dir campaigns/my-problem
→ start the Planner → Executor → Reviewer loop
```

The AI tool reads `AGENTS.md` (or `CLAUDE.md` or `.cursor/rules/`) on startup,
which routes it to `AGENT_GUIDE.md`, which routes it to the campaign's `RUNNER.md`,
which tells it which role to play and what files to read.

---

## 11. Critical Design Decisions

### Why `prepare.py` is per-campaign, not shared

Each problem has different data loading, splitting, and evaluation logic. Making
`prepare.py` campaign-specific means:
- The Executor cannot game metrics by modifying the evaluation function
- Different campaigns can use different metrics, splits, and data sources
- The `prepare.py` firewall is the strongest safety mechanism in the harness

### Why `train.py` imports from `prepare.py` using bare imports

When running `PYTHONPATH=. python3 campaigns/<id>/train.py`:
- Python auto-adds the script's directory to `sys.path` → `from prepare import ...` finds `campaigns/<id>/prepare.py`
- `PYTHONPATH=.` adds the repo root to `sys.path` → `import shared.metrics` works

This is intentional. The Executor edits `train.py` but can never import a different
`prepare.py` — Python always resolves the one in the same directory first.

### Why `.claude/agents/` files are thin wrappers

The agent files in `.claude/agents/` do NOT duplicate role prompt content. They
point to `runner/roles/*.md` as the single source of truth. This means:
- `scripts/update-harness.sh` updates role prompts without needing to sync two copies
- The same role definitions work for Claude Code, Codex CLI, and Cursor

### Why the state machine has no agent loop

The harness is tool-agnostic by design. Claude Code, Codex CLI, Cursor, and Copilot
all have different invocation models. The harness provides:
- Instructions (role prompts)
- Validation (schema checks, write-scope enforcement)
- State management (CAMPAIGN_STATE.json, results.tsv)

The AI tool provides the reasoning loop. This means the harness works with any
tool that can read files and run shell commands.
