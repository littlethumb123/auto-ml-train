---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 27
planner_invocation_at: "2026-04-24T14:25:00Z"
action_type: "A_hp"
hypothesis: "Applying AUC-ROC Optuna to LGBM_hybrid (currently 0.046 weight in round 25 champion) — the same technique that gave +0.446 via XGB — may find LGBM HPs complementary to the tuned XGB, raising the ensemble further above 23.174."
expected_effect_size: "Δval_lift_1pct: +0.05 to +0.4 (same mechanism as round 25 if LGBM finds truly different AUC-ROC optimum)"
base_commit: "6ccd6eb"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 27. Best: 23.174 (round 25, tuned XGB AUC-ROC in 7-model ensemble). consecutive_discards=1. Round 26 showed that tuning ONE model for AUC-ROC at a time is the key. LGBM gets 0.046 weight in round 25 — nearly zero. AUC-ROC tuning may find an LGBM configuration that makes predictions complementary to the tuned XGB.

## 2. Evidence from memory

- Round 25: AUC-ROC tuned XGB standalone=22.127 (weaker) but gets 0.456 ensemble weight → +0.446 lift.
- Round 26: Tuning CB too → less diversity → discard.
- Rule: ONE AUC-ROC tuned model at a time. Keep all others as default.
- LGBM currently: default params (num_leaves=127, lr=0.05, early_stop@170) → 22.162 standalone.

## 3. Plan

Optuna LGBM with AUC-ROC proxy. Replace LGBM_hybrid in the 7-model ensemble. Keep tuned XGB from round 25 (same Optuna seed → same params found). Re-optimize 7 weights.

Search space: num_leaves 31-511, lr 0.01-0.2, min_child_samples 5-200, feature_fraction 0.5-1.0, bagging_fraction 0.5-1.0, lambda_l1 0-5, lambda_l2 0-5.

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace LGBM_hybrid (Model 1) with Optuna AUC-ROC tuned version. Keep XGB Optuna block from round 25. Import optuna/roc_auc_score at top of model block.

## 6. Escalation

### No escalation
