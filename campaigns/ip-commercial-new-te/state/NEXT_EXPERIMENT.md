---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 25
planner_invocation_at: "2026-04-24T13:15:00Z"
action_type: "A_hp"
hypothesis: "Optuna HP search on XGBoost (AUC-ROC proxy, 25 trials) will find a stronger XGB configuration that, when substituted into the 7-model ensemble as XGB_hybrid, raises the ceiling above 22.728."
expected_effect_size: "Δval_lift_1pct: +0.1 to +0.5 (XGB gets 0.535 ensemble weight — tuning it propagates directly)"
base_commit: "7a4b183"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 25. Best: 7-model ensemble 22.728 (round 22). consecutive_discards=2. XGB dominates the ensemble (XGB_h=0.262 + XGB_t=0.273 = 0.535 total). Tuning XGBoost directly should have the highest leverage of any remaining HP experiment. Using AUC-ROC proxy (smoother than lift@1% at low iterations).

## 2. Evidence from memory

- Round 22: default XGB (depth=6, lr=0.05, scale_pos_weight=10) → 22.247 standalone, gets 0.262 weight.
- Round 12: XGBoost default on hybrid → 22.195 (without eng features).
- XGBoost HP search in creditcard campaign: depth [4,6] was canonical. For this data, deeper trees may help.
- AUC-ROC proxy fixes the noisy lift@1% proxy issue that plagued CatBoost/LGBM rounds.

## 3. Plan

Optuna XGBoost search:
- Proxy: 50-iter XGB, early stopping 20, AUC-ROC metric (~8-15s/trial)
- Full model: 2000-iter, early stopping 80
- Search space: max_depth 4-10, learning_rate 0.01-0.3 (log), subsample 0.6-1.0, colsample_bytree 0.5-1.0, min_child_weight 1-50 (log), gamma 0.0-5.0, scale_pos_weight 5-20

After finding best XGB, plug into 7-model ensemble (replacing default XGB_hybrid), re-optimize scipy weights.

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: add Optuna XGB search, then use tuned XGB_hybrid in 7-model ensemble alongside 6 existing models.

## 6. Escalation

### No escalation
