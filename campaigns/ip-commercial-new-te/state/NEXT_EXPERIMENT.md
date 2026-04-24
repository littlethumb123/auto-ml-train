---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 17
planner_invocation_at: "2026-04-24T10:25:00Z"
action_type: "A_ensemble"
hypothesis: "Adding a LightGBM trained on tabular-only features (534 features, no embeddings) to the optimized 3-GBDT ensemble creates structural diversity (different feature space), which may improve lift@1% beyond the current best (22.608) more than a same-seed LGBM variant."
expected_effect_size: "Δval_lift_1pct: +0.1 to +0.4 (tabular-only LGBM has different prediction surface from embedding-inclusive models)"
base_commit: "8e61f5d"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 17. Best: optimized 3-GBDT weights 22.608 (round 16). consecutive_discards=0. Gains are marginal (+0.052 in round 16). Structural diversity (different feature set) should help more than seed diversity (same features, slightly different bootstrap). Tabular-only LGBM (no embeddings) had corr ~0.92 with hybrid GBDT models and may have unique error patterns for members where embeddings don't add signal.

## 2. Evidence from memory

- Round 1 (CatBoost tabular_only): 21.578. LGBM tabular_only expected ~22.0.
- Round 14 corr analysis: LGBM/XGB corr=0.97 (both hybrid). Tabular-only model would have ~0.90-0.93 corr with hybrid (missing 256 embedding dims).
- Round 15 lesson: RF (corr=0.92) was too weak (20.016). Tabular-only LGBM (expected ~22.0) is much stronger.

## 3. Plan

Train: LGBM(hybrid), LGBM(tabular_only), CB(hybrid), XGB(hybrid). Scipy-optimize 4 weights on val. The tabular_only LGBM is computed by filtering X_train/X_val to non-embedding columns only (no new cache needed).

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: add LGBM_tabular (on non-embedding subset of X_train) alongside the 3 hybrid models. Optimize 4 weights with scipy.

## 6. Escalation

### No escalation
