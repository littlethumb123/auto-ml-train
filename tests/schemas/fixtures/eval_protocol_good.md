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
