---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 18
planner_invocation_at: "2026-05-27T06:25:00Z"
action_type: "A_ensemble"
hypothesis: "3-model rank-percentile ensemble (CB+LGB+XGB) — XGB adds ranking diversity; rank averaging prevents weak model from dragging down"
expected_effect_size: 0.35
base_commit: "69fa263143fe2ffb7e9a781d5a03efdd3ee7336b"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: ["XGB at 500 iter gives >=22.35 individual lift", "3-model rank avg outperforms 2-model rank avg"]
---

## 1. Context summary

Round 18 of 50. Budget: 17/50. Best: 22.813929 (R17, CB+LGB rank ensemble). Target: 24.0.
Consecutive discards: 0. Need delta ≥ 0.3 → need ≥23.114.

**R17 breakthrough**: Rank-percentile averaging +0.069 over probability averaging (22.814 vs 22.745). This works because lift@1% is a rank metric — normalizing model probabilities to percentiles before combining removes calibration scale artifacts.

**Why XGB failed before (R14)**: XGB at 300 iterations was too weak (22.16), dragging down the 3-model *probability* average. With **rank averaging**, a weaker model's influence is bounded — it contributes its ranking diversity without being penalized for different probability scales.

**R18**: Add XGBoost with more iterations (500 iter) using rank averaging:
- CB: 22.35 (rank ~0.57 at top 1% threshold)
- LGB: 22.49 (rank ~0.59)
- XGB(500): expected 22.35-22.45 (rank ~0.57-0.58)
- 3-model rank average: expected 22.95-23.15

**Timing** (HARD_TIMEOUT=1800):
- CB(2000 iter): ~940s
- LGB(600 iter): ~120s
- XGB(500 iter, tree_method=hist, n_jobs=4): ~450s
- Total: ~1510s ✓

## 3. Plan

1. Edit train.py: same CB+LGB as R17 but add XGBoost(500 iter) + 3-model rank avg
2. Commit + run
3. Expected: val_lift ≈ 23.1, training ~1510s

## 4. Helpers

None.

## 5. How this differs from R14 (the failed 3-model ensemble)

R14 used probability averaging — XGB(300, 22.16) dragged the ensemble down to 22.59.
R18 uses rank averaging — XGB's weak probability scale is normalized to [0,1] before combining.

## 6. Escalation

If val_lift < 23.114: try 2nd LGB with different seed/colsample as third model (same total time, more similar strength to LGB).
