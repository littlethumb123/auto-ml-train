---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 12
planner_invocation_at: "2026-04-24T10:00:00Z"
action_type: "A_model"
hypothesis: "XGBoost default params on hybrid completes the three-family comparison (CatBoost 22.213, LightGBM 22.316). XGBoost uses histogram-based splitting like LightGBM but with different regularization, potentially finding a different optimum."
expected_effect_size: "Δval_lift_1pct: -1.0 to +1.0 (unknown — third family baseline)"
base_commit: "3f78e70"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 12. Best: stacking 22.333 (practical LightGBM 22.316). Consecutive_discards=1. Three-family comparison in progress: CatBoost(22.213), LightGBM(22.316). XGBoost is the third canonical GBDT family with different regularization (L1/L2 vs LightGBM's lambda).

## 2. Evidence from memory

- CatBoost default: 22.213 (symmetric trees, auto_class_weights)
- LightGBM default: 22.316 (leaf-wise, class_weight='balanced') — current champion
- XGBoost: histogram method, scale_pos_weight for imbalance, known depth canonical 5-7

## 3. Plan

XGBoost hist with default-equivalent params. scale_pos_weight = n_neg/n_pos ≈ 10 (matches the 10:1 downsampling ratio — effectively double-weighting positives, but standard for XGBoost imbalance). Use tree_method='hist' for speed.

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: swap LightGBM for XGBoost hist with scale_pos_weight=10.

## 6. Escalation

### No escalation
