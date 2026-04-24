---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 3
planner_invocation_at: "2026-04-24T04:42:00Z"
action_type: "A_hp"
hypothesis: "A wide Optuna search over CatBoost HPs on the hybrid feature set will find a configuration that outperforms the round-2 default-parameter baseline."
expected_effect_size: "Δval_lift_1pct: +0.5 to +2.0 (STRATEGY_GUIDE §2 A_hp first systematic tune)"
base_commit: "1e0c124"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 3. Best: hybrid CatBoost lift@1%=22.213 (round 2, defaults: depth=6, lr=0.05, 500 iter). STRATEGY_GUIDE §1: "Champion family selected; no systematic HP search → A_hp highest ROI layer." Feature set locked to hybrid.

## 2. Evidence from memory

- Round 2 (hybrid default): 22.213 lift@1%, 498s total. Data pipeline: ~320s (hybrid 822 cols).
- PRIORS known_good: CatBoost depth canonical 5-9 (broader than XGBoost 4-6).
- Infrastructure fixes in this round: parquet in-time filter (7.5M rows vs 10.3M), pre-fillna, HARD_TIMEOUT=1200.

**Candidate actions:**
1. **A_hp Optuna wide on hybrid** (chosen): First systematic search. STRATEGY_GUIDE §2 prior: Δ=+0.5–2.0. Highest ROI.
2. **A_feature**: SHAP not inspected; feature engineering premature before HP optimized.

## 3. Plan

Optuna TPE search, 200-iter proxy per trial, auto-budget based on elapsed data-load time. Full retraining with best params at 500 iter, od_wait=60. Also: parquet row filter (in-time only) + pre-fillna to reduce data pipeline from ~320s to ~80s.

## 4. Helpers

None.

## 5. How this differs from current train.py

- DESCRIPTION and FEATURE_SET updated.
- HARD_TIMEOUT=1200 (was 600).
- Parquet read adds `filters=[("index_dt", "<=", OOT_CUTOFF_DATE)]`.
- Pre-fillna block added before get_splits.
- Model block replaced with Optuna study + best-params full retraining.

## 6. Escalation

### No escalation
