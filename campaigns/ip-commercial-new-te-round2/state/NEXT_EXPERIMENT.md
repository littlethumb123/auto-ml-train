---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 17
planner_invocation_at: "2026-05-27T05:20:00Z"
action_type: "A_ensemble"
hypothesis: "CB(2000)+LGB(63) rank-percentile ensemble — rank averaging aligns better with lift@1% (a rank metric) than probability averaging"
expected_effect_size: 0.1
base_commit: "05422c4f164e6e69c65d4ad58fcedf3ed6056982"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: ["rank averaging outperforms probability averaging for top-k rank metrics"]
---

## 1. Context summary

Round 17 of 50. Budget: 17/50. Best: 22.487771. Consecutive discards: 8.

**Dead ends confirmed**: feature selection (top-300 hurts both CB and LGB), XGB(300 iter) too weak, LGB(127 leaves) overfits. The 2-model CB(2000)+LGB(63) ensemble peaked at 22.745 (R13) with probability averaging — 0.043 below the 22.788 noise floor.

**Single variable change from R13**: Replace probability averaging with rank-percentile averaging:
- Old: y_prob = (y_prob_cb + y_prob_lgb) / 2.0
- New: y_prob = (rank(y_prob_cb)/n + rank(y_prob_lgb)/n) / 2.0

**Rationale**: lift@1% is a purely rank-based metric. When CatBoost and LightGBM have different probability calibrations (different scales/distributions), probability averaging distorts their relative rankings. Rank averaging normalizes both to [0,1] percentiles before combining, potentially better preserving the signal in the top 1% of ranked scores.

**Diagnostic info printed**: probability-averaged ensemble lift also printed for comparison.

**Timing**: same as R13 (~1060s).

## 3. Plan

1. Edit train.py: same CB(2000)+LGB(63) as R13, replace final average with rank averaging
2. Commit + run
3. If rank > prob: validates hypothesis, likely clears noise floor
4. If rank ≈ prob: calibrations are similar, averaging method doesn't matter much

## 6. Escalation

If still below 22.788: next is CB(3000 iter) + prob averaging — testing whether more CB iterations provide the final +0.043.
