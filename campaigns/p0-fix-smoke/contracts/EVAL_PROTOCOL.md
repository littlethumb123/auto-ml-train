---
schema_version: 1
campaign_id: "p0-fix-smoke"
primary_metric:
  name: "val_pr_auc"
  direction: "maximize"
  noise_floor: 0.005
acceptance_threshold:
  baseline_family: "lgbm_balanced"
  min_improvement: 0.1
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: "Smoke: fixed stratified split, seed=42."
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
  max_experiments: 3
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 5
verification_tools:
  - "runner.tools.substantive_diff"
  - "runner.tools.reproduce_check"
anomaly:
  floor: 0.50
  relative: 0.5
results_columns:
  - "val_pr_auc"
  - "lift_at_10"
  - "macro_f1"
  - "val_f1"
approved_at: "2026-06-19"
approved_by: "human"
---

## 1. Rationale

3-round smoke. `min_improvement: 0.1` is artificially high so any
follow-on round whose Δ is below 0.1 forces the noise-floor override
path, exercising F2's discard-verdict requirements.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff Δval_pr_auc > 0 AND tools/anomaly clean AND
tools/bootstrap_ci no regression. Driver-mechanically overridden to
`discard` when Δ < 0.005 (noise_floor) or Δ < 0.1 (min_improvement).

## 3. How plateau is handled

3 consecutive discards trigger Historian (won't fire in 3 rounds; manual
F1 assertion test in unit tests covers the historian_finalize gate).

## 4. Contract change policy

Sticky.
