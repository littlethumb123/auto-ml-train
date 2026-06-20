---
schema_version: 1
campaign_id: "p0-fix-validation-h"
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
  notes: "F1-focused validation: fixed split."
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
  max_experiments: 4
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 2
verification_tools:
  - "runner.tools.substantive_diff"
  - "runner.tools.reproduce_check"
anomaly:
  floor: 0.30
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

4-round campaign with `historian_interval: 2` so Historian fires after
round 2 (the agent must autonomously run the Historian role and write
STRATEGY_MEMO.md before round 3). `anomaly.floor: 0.30` is more permissive
than the validation campaign so reasonable LGBM baselines pass.

## 2. How keep/discard is decided

Reviewer verdict path: anomaly clean + Δ > noise_floor → keep.

## 3. How plateau is handled

3 consecutive discards trigger Historian via C2. With historian_interval=2,
the periodic trigger fires first; F1 gate must accept the memo.

## 4. Contract change policy

Sticky.
