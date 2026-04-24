---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 13
planner_invocation_at: "2026-04-24T10:30:00Z"
action_type: "A_hp"
hypothesis: "Using AUC-ROC as the Optuna proxy metric (instead of lift@1%) produces a smoother, more reliable signal at 50 iterations, enabling TPE to find LightGBM HPs that outperform the default-param best (22.316)."
expected_effect_size: "Δval_lift_1pct: +0.3 to +1.5 (first reliable HP search for LightGBM)"
base_commit: "3f6fb53"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 13. Best: stacking 22.333 (practical LightGBM 22.316). consecutive_discards=2. Root cause of all previous HP failures: lift@1% is too noisy as Optuna proxy at low iterations (50-iter proxy estimate differs from full model by 0.26+ lift pts). AUC-ROC is smooth, deterministic, and reliable at 50 iterations.

## 2. Evidence from memory

- Rounds 5,7,9,11: Optuna with lift@1% proxy — all discarded. Proxy overestimates/underestimates by 0.26+ pts.
- Round 8: LightGBM default: 22.316. Default params: num_leaves=127, lr=0.05, early_stop@251.
- Fix: proxy uses AUC-ROC (roc_auc_score) → full model evaluated on lift@1%.

## 3. Plan

LightGBM Optuna with AUC-ROC proxy. num_leaves 31-255, 50-iter proxy early_stop(20). Full model 2000-iter early_stop(80). After finding best params by AUC-ROC proxy, full model evaluated on lift@1%.

## 4. Helpers

None.

## 5. How this differs from current train.py

Model block: LightGBM Optuna study. Proxy metric: roc_auc_score (not lift_at_percentage).

## 6. Escalation

### No escalation
