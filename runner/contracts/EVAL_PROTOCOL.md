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
  - "runner.tools.anomaly"
  - "runner.tools.bootstrap_ci"
action_types:
  - "A_model"
  - "A_feature"
  - "A_hp"
  - "A_imbalance"
  - "A_ensemble"
  - "A_validate"
  - "A_restart"
budgets:
  time_budget_s: 60
  hard_timeout_s: 90
  max_experiments: 100
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
historian_interval: 10
anomaly:
  floor: 0.75
  relative: 0.5
approved_at: "2026-04-22"
approved_by: "copilot"
---

## 1. Rationale

These choices reproduce the legacy `abes_engine.py` / `program.md` defaults while making evaluation reliability explicit. The `noise_floor` of 0.005 reflects the reflection §7 analysis that Δ < 0.005 is within the bootstrap SE for this positive count.

## 2. How keep/discard is decided

Reviewer verdict = `keep` iff Δ > 0 AND `tools/anomaly` did not fire AND `tools/bootstrap_ci` did not report a regression (CI of new < CI_lo of best).

## 3. How plateau is handled

After `plateau_trigger.consecutive_discards` consecutive non-keep verdicts, `review_finalize`
automatically sets `historian_trigger_pending = true`. Before the next Planner turn, the
outer loop invokes the Historian role (`run_round.sh historian`), which produces
`state/STRATEGY_MEMO.md` with trajectory analysis, pattern extraction, assumption audit,
and bottleneck diagnosis. After the Historian run, `historian-finalize` resets
`consecutive_discards = 0`. The Planner then reads `STRATEGY_MEMO.md` as a required input
and plans the next experiment with full trajectory context.

The Planner does NOT need to emit `escalation: C2` — the driver manages the Historian trigger
automatically. The `resolve_c2` shell command is available for human manual override only.

## 4. Contract change policy

Contracts are sticky. Any change requires a C3-gate Planner escalation with `tools/contract_diff` output and human approval.
