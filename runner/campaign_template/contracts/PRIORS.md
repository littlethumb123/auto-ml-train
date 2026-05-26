---
schema_version: 1
problem_id: "creditcard-fraud"
last_campaign: "apr03"
updated_at: "2026-04-21"
---

## Known good

- `np.log1p(Amount)` adds signal (confirmed mar30, apr01).
- `Amount * V1` and `Amount * V2` interactions add signal.
- XGBoost depth in [4, 6] is the canonical range for single-model runs.
- LightGBM is competitive after fixing the is_unbalance bug.

## Known bad

- `v_interactions` (V1*V2, V1*V3, V3*V4) are noise.
- `time_features` (Time_hour, Time_sin, Time_cos) are noise.
- SMOTE + scale_pos_weight double-counts imbalance.
- DART booster exceeds 90s timeout at 500 trees.
- `tree_method=approx` exceeds 90s timeout on 170K rows.
- Sklearn GBM (GradientBoostingClassifier) exceeds 90s at 100 trees.

## Known ceilings

- Single-holdout PR-AUC plateaus around 0.846 on the fixed apr03 split.
- Above this, CV-with-CI is needed to trust Δ (reflection §7).

## Open questions (for next campaign)

- Does 5-fold stratified CV raise the observed ceiling or confirm it is structural?
- Do stacked ensembles help after tuning individual members with Optuna?
