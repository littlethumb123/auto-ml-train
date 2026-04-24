---
schema_version: 1
campaign_id: "ip-commercial-new-te"
primary_metric:
  name: "val_lift_1pct"
  direction: "maximize"
  noise_floor: 0.3
acceptance_threshold:
  baseline_family: "catboost_tabular_only"
  min_improvement: 0.3
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: "n/a"
  split_key: "ind_id_last_digit"
  notes: "Digit-8 members held out as val; digit-9 as test. Deterministic — same member always lands in same split."
bootstrap_ci:
  enabled: true
  n_boot: 1000
  alpha: 0.05
  metric: "lift_1pct"
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
  - "A_diagnose"
  - "A_validate"
  - "A_restart"
results_columns:
  - "val_lift_1pct"
  - "val_auc_roc"
  - "val_lift_5pct"
  - "val_lift_10pct"
  - "val_auc_pr"
budgets:
  time_budget_s: 90
  hard_timeout_s: 150
  max_experiments: 100
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 1.5
  relative: 0.5
approved_at: "2026-04-24"
approved_by: "Zhaopeng-Xing_cvsh"
---

## 1. Rationale

`val_lift_1pct` is the primary metric because care management outreach targets the top 1% of flagged members — lift at that threshold directly reflects business value (how many true IP6 cases are captured vs. random selection). AUC-ROC is logged as a secondary metric for stability comparison across rounds.

`noise_floor: 0.3` reflects that bootstrap SE on lift@1% is typically 0.3–0.6 units for this population size. Treat any Δ below 0.3 as within noise.

The bootstrap CI uses `metric: lift_1pct` to match the primary metric. The Reviewer passes `--bootstrap-se` to the driver so the C3 advisory fires if the target gap is within 2× SE.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff:
- Δval_lift_1pct > 0 (new model beats prior best on primary metric)
- `tools/anomaly` did not fire (no implausible metric drop)
- `tools/bootstrap_ci` CI_lo of new model ≥ 0 (no hard regression)

## 3. How plateau is handled

After 3 consecutive non-keep verdicts, the next Planner MUST run A_diagnose (per STRATEGY_GUIDE §3.7) before any structural change. Emit escalation: C2 only after A_diagnose has been run and did not identify a clear next structural move.

## 4. Contract change policy

Contracts are sticky. Any change (including updating success_criteria after baseline is established) requires a C3-gate Planner escalation with `tools/contract_diff` output and human approval. The first expected C3 is: update `val_lift_1pct >= 4.5` after round 1 reveals the true baseline.
