---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 24
planner_invocation_at: "2026-04-24T13:00:00Z"
action_type: "A_ensemble"
hypothesis: "Optimizing 7-model ensemble weights on a digit-6/7 holdout (separate from the digit-8 val set used for evaluation) gives weights that generalize better and avoids the in-sample bias that inflates round 22's 22.728 estimate."
expected_effect_size: "Δval_lift_1pct: +0.05 to -0.10 (may be lower than round 22 due to removing in-sample bias)"
base_commit: "eb62d51"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 24. Best: 22.728 (round 22, 7-model in-sample optimized). Rounds 20-23 all discard. The in-sample weight optimization uses the same val set for fitting AND evaluation — optimistic. Using digits 6-7 as a dedicated weight-fitting holdout gives honest weights.

## 2. Evidence from memory

- Round 22: scipy weights optimized on digit-8 val (752K rows). May overfit the val split.
- Digit-6-7 data is a subset of the training set in the current cache — need to load those rows.
- True generalization to digit-8 val with out-of-fold weights may be slightly different.

## 3. Plan

Load the hybrid eng-5 split cache. Extract digits 6-7 from X_train (before downsampling) as meta-train holdout. Train 7 base models on digits 0-5 only. Optimize weights on digits 6-7. Evaluate on digit-8 val. This is proper holdout stacking.

Note: this requires re-loading the data to get digits 6-7 (not in current cache). Load from the eng-5 npz cache and filter by original digit membership (need to reconstruct digit info from the data).

## 4. Helpers

None.

## 5. How this differs from current train.py

Major change to model block: train base models on a subset (simulated), optimize weights on a different holdout, evaluate on digit-8. But this requires digit information not in the cache.

Simpler approach: use 50% random subsample of val as weight-fitting, remaining 50% for evaluation. This avoids the full in-sample issue with minimal code change.

## 6. Escalation

### No escalation
