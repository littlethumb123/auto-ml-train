---
schema_version: 1
campaign_id: "p0-fix-validation-c1"
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
  notes: "C1 anomaly path validation."
bootstrap_ci:
  enabled: true
  n_boot: 200
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
  hard_timeout_s: 60
  max_experiments: 1
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 10
verification_tools:
  - "runner.tools.substantive_diff"
  - "runner.tools.reproduce_check"
anomaly:
  floor: 0.95
  relative: 0.5
results_columns:
  - "val_pr_auc"
  - "lift_at_10"
  - "macro_f1"
  - "val_f1"
approved_at: "2026-06-20"
approved_by: "human"
---

## 1. Rationale

1-round campaign for C1 anomaly path validation. `anomaly.floor: 0.95`
ensures the leakage-driven near-perfect val_pr_auc fires the anomaly tool.

## 2. How keep/discard is decided

Anomaly path: tools/anomaly fires → verdict=anomaly → orchestrator pauses.

## 3. How plateau is handled

Not applicable — 1-round campaign.

## 4. Contract change policy

Sticky.
