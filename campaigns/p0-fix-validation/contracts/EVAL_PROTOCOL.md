---
schema_version: 1
campaign_id: "p0-fix-validation"
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
  notes: "Validation: fixed stratified split, seed=42."
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
  max_experiments: 5
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 4
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
approved_at: "2026-06-20"
approved_by: "human"
---

## 1. Rationale

5-round campaign with `historian_interval: 4` so the Historian fires
naturally at round 4 (after the round-3 review_finalize sets
`historian_trigger_pending=true` because rounds_since_last_historian
reaches the interval). This validates the F1 natural-trigger chain
end-to-end through the autonomous orchestrator.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff Δval_pr_auc > 0 AND tools/anomaly clean AND
tools/bootstrap_ci no regression. Driver-mechanically overridden to
`discard` when Δ < 0.005 (noise_floor).

## 3. How plateau is handled

3 consecutive discards trigger Historian via the C2 path. Either way
(periodic or C2), Historian must produce a complete STRATEGY_MEMO.md per
F1 verification.

## 4. Contract change policy

Sticky.
