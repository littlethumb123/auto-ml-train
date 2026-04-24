---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 28
planner_invocation_at: "2026-04-24T15:00:00Z"
action_type: "A_hp"
hypothesis: "XGB Optuna with different TPE seed (seed=7) explores a different region of the HP space than round 25 (seed=42), potentially finding XGB HPs that are even more complementary to the 6 default models."
expected_effect_size: "Δval_lift_1pct: -0.1 to +0.3 (exploratory — may find same or different optimum)"
base_commit: "2ea60de"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 28. Best: 23.174 (round 25). consecutive_discards=2. Rule: AUC-ROC tuning only helps the dominant ensemble member (XGB, 0.456 weight). Rounds 26-27 confirmed this. Round 28: explore different XGB HP space by changing TPE seed.

## 2. Evidence from memory

- Round 25/27: TPE seed=42 → depth/lr/subsample specific values → XGB standalone 22.127 → ensemble 23.174.
- Different seed explores different trajectory through HP space, may find XGB with higher complementarity.
- Keep all 6 other models as default.

## 3. Plan

Same as round 25 XGB Optuna block but with sampler seed=7. If result < 23.174, confirms the ceiling. If >, new best found.

## 4. Helpers

None.

## 5. How this differs from current train.py

Change XGB Optuna TPE sampler seed from RANDOM_SEED(42) to 7.

## 6. Escalation

### No escalation
