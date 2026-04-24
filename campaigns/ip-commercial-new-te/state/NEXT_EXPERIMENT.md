---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 1
planner_invocation_at: "2026-04-24T03:20:00Z"
action_type: "A_validate"
hypothesis: "Default-parameter CatBoost on tabular_only features establishes the lift@1% floor for this campaign."
expected_effect_size: "n/a — baseline round; no prior to compare against"
base_commit: "0c0e393f129e16f5adc18fb353f2072bee5b1437"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 1. Campaign state: no experiments run, no results.tsv rows. The first mandatory action per STRATEGY_GUIDE §1 trigger ("No baseline exists") is A_validate with the simplest default-parameter model on the `tabular_only` feature set. This establishes:
1. The tabular-only lift@1% floor — the reference point for every future experiment.
2. Whether the CatBoost default configuration is within the 90s time budget.
3. Prevalence and split sizes for this cohort (10.3M rows, digit-based splits).

## 2. Evidence from memory

- **results.tsv**: empty — no prior experiments.
- **DEAD_ENDS.md**: no entries.
- **PRIORS.md**: CatBoost with `auto_class_weights='Balanced'` is a strong default for imbalanced IP prediction (known good). No baseline for this embedding source yet.
- **STRATEGY_GUIDE §1**: trigger "No baseline exists" → A_validate with simple default. Cannot choose A_hp or A_ensemble before knowing the floor.

**Candidate actions considered:**
1. **A_validate tabular_only** (chosen): Δ = establishes floor. Required before any other action. Lowest expected Δ but highest information value.
2. **A_hp on tabular_only**: Would not know what HP baseline to beat. Premature — no floor yet.
3. **A_validate hybrid**: Can't attribute embedding lift without tabular-only reference. Must come second.

Chosen: A_validate tabular_only — the only valid first move per STRATEGY_GUIDE §1.

## 3. Plan

**One change from current train.py:** no structural change — train.py already implements the A_validate tabular_only template. Executor confirms `FEATURE_SET = 'tabular_only'` and the default CatBoost config (2500 iter, depth 7, lr 0.025, auto_class_weights='Balanced') are in place. No other changes.

**Expected output from run.log:**
- `val_lift_1pct`: expected range 3.0–6.0 based on IP hospitalization prediction norms
- `val_auc_roc`: expected 0.75–0.85
- `training_seconds`: expected 20–60s (CatBoost with early stopping)
- `total_seconds`: expected 25–70s (parquet cache loaded, no BQ download)

**Keep/discard logic:** This is round 1 — any non-crash result is implicitly kept as the first baseline (best_so_far will be null, so any positive metric beats it).

## 4. Helpers

No experiment_helpers files needed for this round.

## 5. How this differs from the current train.py

No code change required. The current train.py already implements:
- `FEATURE_SET = 'tabular_only'`
- `DESCRIPTION = "A_validate: CatBoost default params, tabular_only — establish floor"`
- Default CatBoost config matching PRIORS.md known-good parameters

Executor verifies these are correct and commits without modification (or with a cosmetic description update if needed).

## 6. Escalation

### No escalation

No escalation warranted. Round 1 baseline — proceed normally.
