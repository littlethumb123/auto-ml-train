---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 22
planner_invocation_at: "2026-04-24T12:30:00Z"
action_type: "A_ensemble"
hypothesis: "Adding tabular-only CB and XGB (2 more models) to the 5-model ensemble creates 7 models with more tabular diversity. The tabular LGBM already gets ~0.35 weight; adding tabular CB and XGB may capture different tabular patterns."
expected_effect_size: "Δval_lift_1pct: +0.01 to +0.05 (diminishing returns expected)"
base_commit: "b42916c"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 22. Best: 22.677 (round 19, 5 eng features + 5-model ensemble). Consecutive_discards=2. Feature engineering has reached ceiling. This is the last structural diversity experiment: adding tabular-only CB and XGB (in addition to existing tabular LGBM) to maximize tabular-family coverage.

## 2. Evidence from memory

- In rounds 16-21, LGBM_tabular consistently gets 0.25-0.43 weight — higher than LGBM_hybrid.
- Tabular signal is dominant in the ensemble. CB_tabular and XGB_tabular may add more tabular diversity.
- If this fails, accept 22.677 as the campaign ceiling and write FINAL_REPORT.

## 3. Plan

7-model ensemble: LGBM_hybrid + LGBM_tabular + LGBM_emb + CB_hybrid + CB_tabular (new) + XGB_hybrid + XGB_tabular (new). Scipy-optimize 7 weights. All on eng-5 feature set.

## 4. Helpers

None.

## 5. How this differs from current train.py

Add CB_tabular and XGB_tabular models to the model block; increase scipy optimization to 7 dimensions.

## 6. Escalation

### No escalation
