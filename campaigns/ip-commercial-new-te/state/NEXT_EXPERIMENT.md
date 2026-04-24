---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 8
planner_invocation_at: "2026-04-24T08:15:00Z"
action_type: "A_model"
hypothesis: "LightGBM default params on hybrid features will establish a second family baseline and potentially outperform CatBoost's 22.213 lift@1% due to different inductive bias and faster training (enabling more iterations within budget)."
expected_effect_size: "Δval_lift_1pct: -1.0 to +1.5 (STRATEGY_GUIDE §2 A_model prior: 0.3-1.5 when early campaign)"
base_commit: "5690f74"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 8. Best: hybrid CatBoost default 22.213 (round 2). consecutive_discards=2 (rounds 6-7 both informative/noise). STRATEGY_GUIDE §1: "Only CatBoost tried; 2+ rounds → A_model: try LightGBM." CatBoost HP search showed default params are near-optimal for CatBoost; LightGBM may find a different optimum with its leaf-wise growth strategy.

## 2. Evidence from memory

- **rounds 5,7**: CatBoost HP search (7 and 54 trials) couldn't beat 22.213 default. Proxy unreliable.
- **PRIORS known_bad**: `is_unbalance=True` inverts probabilities — use `class_weight='balanced'` instead.
- **STRATEGY_GUIDE §3.1**: Try ≥1 alternative family before investing in tuning.
- **Split cache**: 27s load. LightGBM trains ~5× faster per iteration than CatBoost on tabular data.

## 3. Plan

Replace CatBoost with LightGBM default-parameter model. Same feature set (hybrid 789 features from split cache). Use `class_weight='balanced'` (NOT is_unbalance=True). Cat columns are integer-encoded in cache — treat as ordinal numeric for simplicity (LightGBM categorical handling requires values < 32 which may not hold for all cat columns).

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace the model block: swap CatBoostClassifier/Pool for LightGBMClassifier. Load split cache as before.

## 6. Escalation

### No escalation
