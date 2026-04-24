---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 21
planner_invocation_at: "2026-04-24T12:00:00Z"
action_type: "A_feature"
hypothesis: "Adding only ER utilization features (er_clm_cnt_1yr and er_clm_cnt_1yr × chronic_score) to the round-19 baseline (5 features) tests whether ER pathway is a net-positive signal without the noise from IP recency/severity features that hurt in round 20."
expected_effect_size: "Δval_lift_1pct: +0.02 to +0.15"
base_commit: "a17a4a3"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 21. Best: 22.677 (round 19, 5 eng features). Round 20 added 5 more features including ER but also noisy features (recency, severity) and discarded (-0.052). This round isolates ER features to test if they add net signal.

## 2. Evidence from memory

- Round 20: 10-feature set regressed (-0.052). ER features were bundled with noisy ones.
- ER visits are a well-established clinical precursor to IP admissions.
- `er_clm_cnt_1yr` exists in the column set.

## 3. Plan

Extend `_engineer()` to 7 features (5 from r19 + er_total + er_x_chronic). Keep IP days/recency/severity out.

## 4. Helpers

None.

## 5. How this differs from current train.py

Add only `eng_er_total` and `eng_er_x_chronic` to the `_engineer()` function (2 more, total 7). The rest unchanged.

## 6. Escalation

### No escalation
