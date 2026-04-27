---
schema_version: 1
campaign_id: "smoke-test-creditcard"
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
  notes: "Fixed stratified 60/20/20 split in train.py. Smoke test uses single holdout."
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
approved_at: "2026-04-27"
approved_by: "human"
---

## 1. Rationale

Smoke test protocol: 10-round budget, historian_interval=5 (Historian fires at round 5 and on C2
plateau). Primary metric is PR-AUC for extreme imbalance (0.17% fraud). Mandatory tools:
anomaly detection and bootstrap CI. Results schema uses legacy 4-metric layout.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff Δval_pr_auc > 0 AND `tools/anomaly` did not fire AND
`tools/bootstrap_ci` did not report a regression (CI of new < CI_lo of best).

## 3. How plateau is handled

After `plateau_trigger.consecutive_discards` (3) consecutive non-keep verdicts, `review_finalize`
automatically sets `historian_trigger_pending = true`. Before the next Planner turn, the outer
loop invokes the Historian role (`run_round.sh historian --campaign-dir campaigns/smoke-test-creditcard`),
which produces `state/STRATEGY_MEMO.md`. After the Historian run, `historian-finalize` resets
`consecutive_discards = 0`. The Planner reads STRATEGY_MEMO.md as a required input.

The Planner does NOT need to emit `escalation: C2`. The `resolve_c2` command is available for
human manual override only.

## 4. Contract change policy

Contracts are sticky. Any change requires a C3-gate Planner escalation and human approval.
