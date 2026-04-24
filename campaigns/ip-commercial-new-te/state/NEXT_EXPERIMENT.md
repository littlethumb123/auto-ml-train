---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 14
planner_invocation_at: "2026-04-24T11:00:00Z"
action_type: "A_diagnose"
hypothesis: "Comparing prediction correlations between LightGBM, CatBoost, and XGBoost will reveal whether a three-family mean ensemble is warranted (low correlation = complementary errors) or redundant (high correlation = no diversity benefit)."
expected_effect_size: "~0 (diagnostic only — informs three-family ensemble decision)"
base_commit: "a08ef58"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 14. c2_pending_diagnose=True (mandatory A_diagnose after second C2). HP search conclusively failed: LightGBM defaults are near-optimal. This A_diagnose quantifies prediction diversity across all three families to determine whether three-family mean ensemble adds real value.

## 2. Evidence from memory

- Round 6 A_diagnose: SHAP 50/50 emb/tab split. Val positives: mean_prob=0.687. Well-calibrated.
- Round 8 LightGBM: 22.316. Round 12 XGBoost: 22.196. Round 2 CatBoost: 22.213.
- Round 10 stacking (LGBM+CB): 22.333 (only +0.017 over LGBM alone — in-sample).

## 3. Plan

Train all three families (default params). Compute: (1) pairwise Pearson correlation of val predictions, (2) ensemble of three by simple mean, (3) ensemble of LGBM+CatBoost by mean. Compare to individual models. No Optuna, no stacking.

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: train LightGBM + CatBoost + XGBoost with defaults; compute pairwise correlations; take mean ensemble; report lift@1% for each model and ensemble.

## 6. Escalation

### No escalation

A_diagnose per C2 protocol. Decision after: if three-family mean ensemble > LGBM alone, proceed; else investigate feature engineering.
