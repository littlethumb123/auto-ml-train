---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 15
planner_invocation_at: "2026-04-24T09:55:00Z"
action_type: "A_ensemble"
hypothesis: "Adding a RandomForest (bagging — fundamentally different inductive bias from GBDT boosting) to the LGBM+XGB mean will reduce prediction correlation and improve lift@1% beyond the current best (22.556), since RF makes systematically different errors."
expected_effect_size: "Δval_lift_1pct: +0.1 to +0.5 (RF as diversity source: different bias family)"
base_commit: "f394912"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 15. Best: three-family GBDT mean 22.556 (round 14). consecutive_discards=0. Round 14 showed GBDT families all correlate at 0.97+. RandomForest (sklearn) uses bagging and majority vote — not residual boosting — producing structurally different errors. May add more diversity to the ensemble than a fourth GBDT.

## 2. Evidence from memory

- Round 14: LGBM corr w/XGB=0.974, LGBM corr w/CB=0.965. All GBDTs very similar.
- LGBM+XGB mean: 22.453. LGBM+CB+XGB: 22.556. CB adds value only in three-way (not pairwise).
- RF uses bootstrapped subsets + random feature selection → structurally lower correlation with GBDT.
- RF alone will likely underperform LGBM (22.316 is the GBDT floor), but as ensemble component it adds diversity.

## 3. Plan

Train: LGBM (default) + XGBoost (default) + RandomForestClassifier (sklearn, class_weight='balanced', n_estimators=300). Mean ensemble of all three. Compare against round 14 three-GBDT mean (22.556).

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: LGBM + XGB + RF default, compute individual lifts + mean ensemble.

## 6. Escalation

### No escalation

Normal A_ensemble progression.
