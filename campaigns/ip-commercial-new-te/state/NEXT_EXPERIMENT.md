---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 9
planner_invocation_at: "2026-04-24T08:45:00Z"
action_type: "A_hp"
hypothesis: "Optuna HP search on LightGBM will outperform the default-param LightGBM (22.316) by finding a better combination of num_leaves, learning_rate, and regularization. LightGBM's fast training enables many more reliable proxy trials than CatBoost."
expected_effect_size: "Δval_lift_1pct: +0.3 to +1.5 (first systematic tune of new champion family)"
base_commit: "fa7411b"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 9. Best: LightGBM default 22.316 (round 8). consecutive_discards=0. STRATEGY_GUIDE: "Champion family selected; no systematic HP search → A_hp highest ROI." LightGBM trains much faster than CatBoost — a 50-iter proxy takes ~2-5s/trial vs 17s, enabling 100+ Optuna trials in 500s.

## 2. Evidence from memory

- **Round 8**: LightGBM default (num_leaves=127, lr=0.05, 1000 iter early-stop@251) → 22.316.
- **PRIORS known_bad**: is_unbalance=True inverts probs. Use class_weight='balanced'.
- **Round 7 lesson**: CatBoost 50-iter proxy unreliable (proxy and full model uncorrelated). For LightGBM, training is much faster so proxy iterations need not be as reduced.

## 3. Plan

Optuna TPE on LightGBM. Proxy: 200-iter with early stopping (fast for LGBM). Full model: 2000 iter with early stopping. Search space:
- num_leaves: 31–511 (log)
- learning_rate: 0.01–0.3 (log)
- min_child_samples: 10–200 (log)
- feature_fraction: 0.5–1.0
- bagging_fraction: 0.5–1.0
- lambda_l1: 0.0–10.0
- lambda_l2: 0.0–10.0

## 4. Helpers

None.

## 5. How this differs

Replace model block with LightGBM Optuna study (proxy 200-iter + full 2000-iter).

## 6. Escalation

### No escalation
