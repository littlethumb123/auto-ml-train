---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 16
planner_invocation_at: "2026-04-24T10:15:00Z"
action_type: "A_ensemble"
hypothesis: "Optimizing the three-GBDT blend weights (LGBM, CatBoost, XGBoost) via scipy.optimize to maximize lift@1% directly will outperform the equal-weight mean (22.556) since the models contribute differently at the top-1% threshold."
expected_effect_size: "Δval_lift_1pct: +0.1 to +0.5 (weight optimization over equal mean)"
base_commit: "339806a"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 16. Best: equal-weight LGBM+CB+XGB mean 22.556 (round 14). Round 14 showed unequal model quality: LGBM=22.316, CB=21.698, XGB=22.196. Equal weights give each model the same influence, but optimized weights should give more influence to LGBM and XGB (stronger at top-1%) and less to CB.

## 2. Evidence from memory

- Round 14: LGBM(22.316)+CB(21.698)+XGB(22.196) equal mean = 22.556.
- Optimized weights should upweight LGBM (strongest) and XGB (good diversity), downweight CB.
- scipy.optimize.minimize on neg_lift@1%: fast (< 5 seconds), 3-dimensional simplex.

## 3. Plan

Train LGBM + CatBoost + XGBoost (same configs as round 14). Use scipy.optimize (Nelder-Mead or SLSQP) to find weights w = [w1, w2, w3] (sum to 1) that maximize lift@1% on the val set.

Note: this is in-sample weight optimization on val (same as round 10 logistic stacking). The estimate will be optimistic. But with only 3 parameters, overfitting is minimal.

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: three GBDTs + scipy weight optimization on val set.

## 6. Escalation

### No escalation
