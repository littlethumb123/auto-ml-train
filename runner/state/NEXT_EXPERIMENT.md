---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
round: 10
planner_invocation_at: "2026-04-22T05:22:00Z"
action_type: "A_ensemble"
hypothesis: "A weighted XGBoost + LightGBM ensemble can beat the current single-model XGBoost incumbent."
expected_effect_size: 0.003
base_commit: "8894daf"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary

Best so far remains Round 6 at `val_pr_auc=0.844197` with XGBoost hist. The required C2 plateau check has already fired, so this final round should use the structural change proposed in that escalation rather than another single-model tweak.

## 2. Evidence from memory

- The C2 plan-check paused successfully, confirming the plateau path is active in the new design.
- LightGBM and XGBoost are the two families that produced keeps in this campaign.
- XGBoost is the best current model, so it should stay as the dominant ensemble member.
- The budget still has room for one extra model fit on top of the current XGBoost pipeline.

## 3. Plan

1. Keep the current XGBoost search as the primary model path.
2. Add a fixed LightGBM companion on the same engineered features and search a small blend-weight grid on validation.
3. Emit reviewer telemetry from the blended probabilities and compare the ensemble against the Round 6 incumbent.

## 4. Helpers

None.

## 5. How this differs from prior experiments

Rounds 7, 8, and 9 triggered the plateau gate. Round 10 is the first post-C2 structural move: a cross-family ensemble instead of another single-model refinement.

## 6. Escalation (only if `escalation` frontmatter is non-null)

N/A.