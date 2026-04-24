---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 29
planner_invocation_at: "2026-04-24T15:30:00Z"
action_type: "A_diagnose"
hypothesis: "Reproducing round 25 champion (AUC-ROC tuned XGB in 7-model ensemble) verifies the 23.174 ceiling, computes updated bootstrap CI, and checks whether the target gap (24.0 - 23.174 = 0.826) is detectable given the SE (~0.5)."
expected_effect_size: "~0 (diagnostic — reproduces round 25 champion)"
base_commit: "1e15fe0"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 29. c2_pending_diagnose=True (mandatory after 3 consecutive discards rounds 26-28). Best: 23.174 (round 25). The 3 discards confirmed: AUC-ROC tuning of XGB is uniquely effective, and no other variant can match it.

## 2. Evidence from memory

- Round 25: bootstrap CI [22.09, 24.10], SE=0.503.
- Target gap = 24.0 - 23.174 = 0.826. 2×SE = 1.006. Gap < 2×SE → C3 advisory condition.
- This means measurement uncertainty makes it unreliable to distinguish 23.174 from 24.0.

## 3. Plan

Reproduce round 25 champion (AUC-ROC tuned XGB seed=42 in 7-model ensemble). Compute fresh bootstrap CI and target gap assessment. Document recommendation in REVIEW.md.

## 4. Helpers

None.

## 5. How this differs from current train.py

Description updated to A_diagnose. Otherwise identical to round 25 (XGB Optuna seed=42).

## 6. Escalation

### No escalation

A_diagnose per protocol. C3 advisory likely if target gap < 2×SE.
