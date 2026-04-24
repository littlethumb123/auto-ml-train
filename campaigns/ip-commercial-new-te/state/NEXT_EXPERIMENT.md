---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 11
planner_invocation_at: "2026-04-24T09:05:00Z"
action_type: "A_hp"
hypothesis: "LightGBM Optuna search with constrained num_leaves (31-127) enables fast proxy (~8s/trial) giving 60+ trials in 500s, finding parameters that outperform the default LightGBM (22.316) and the stacking best (22.333)."
expected_effect_size: "Δval_lift_1pct: +0.3 to +1.5 (first adequate LightGBM HP search)"
base_commit: "e55014f"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 11. Best: stacking 22.333 (practical LightGBM 22.316, round 8). consecutive_discards=0. Round 9 A_hp LightGBM failed because num_leaves=351 made proxy 71s/trial (only 7 trials). Fix: num_leaves ≤ 127, 50-iter proxy with early_stopping=20 → ~8s/trial → 60+ trials in 500s.

## 2. Evidence from memory

- **Round 8**: LightGBM default (num_leaves=127, lr=0.05, early_stop@251) → 22.316
- **Round 9 failure**: num_leaves sampled up to 351 → 71s/trial, only 7 trials, found 22.179
- **Key insight**: num_leaves=127 is the default and gave the best result. Search below and around it.

## 3. Plan

Optuna on LightGBM, num_leaves constrained to 31-255, 50-iter proxy with early_stopping(20). Full model 2000 iter early_stopping(80).

## 4. Helpers

None.

## 5. How this differs from current train.py

Replace model block: LightGBM Optuna study with num_leaves 31-255, 50-iter proxy early_stop(20), full model 2000-iter early_stop(80).

## 6. Escalation

### No escalation

Normal A_hp progression after keep.
