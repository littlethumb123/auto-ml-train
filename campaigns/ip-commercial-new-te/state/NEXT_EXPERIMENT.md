---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 48
planner_invocation_at: "2026-04-26T04:00:00Z"
action_type: "A_diagnose"
hypothesis: "scipy.optimize.differential_evolution (global optimizer) tests whether 23.174 is the global weight optimum or just one of several local optima. R47 proved multi-modal landscape — different Nelder-Mead starting points find different optima (22.865 vs 23.174). DE explores the full simplex without starting-point dependence."
expected_effect_size: "~0 to +0.3 (if global optimum > 23.174); 0.0 confirms ceiling"
base_commit: "0f2f99e"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 48. consecutive_discards=2 (rounds 46-47). Budget: 53 remaining (47/100 used). Best: 23.174 (round 25, reproduced 6 times). R47 discovered that the scipy weight landscape has multiple local optima — Nelder-Mead with different rng states finds 22.865 vs 23.174.

## 2. Evidence from memory

- R47: rank blending 22.780, prob blending with wrong rng 22.865, r25's rng(42) finds 23.174.
- The Nelder-Mead multi-restart approach (30 restarts from Dirichlet-sampled starting points) is local-optimization dependent.
- `scipy.optimize.differential_evolution` is a global optimizer that does NOT depend on starting points.
- If DE finds 23.174: weight optimization space is fully explored, 23.174 is the global ceiling.
- If DE finds something higher: there's headroom in the weight space that local optimization missed.

## 3. Plan

Replace the 30-restart Nelder-Mead section with:
1. Run `scipy.optimize.differential_evolution` on the 7-model weight space (bounded [0,1]^7, normalized).
2. Also run original 30-restart Nelder-Mead (rng(42)) as comparison.
3. Report both results. Use the better one as val_lift_1pct.

## 4. Helpers

None.

## 5. How this differs from current train.py

Lines 274-293: replace scipy weight optimization section. All 7 base models trained identically to r25. Only the weight optimization step changes — `differential_evolution` added alongside Nelder-Mead.

## 6. Escalation

### No escalation

If DE confirms 23.174 is global optimum AND consecutive_discards reaches 3, C2 fires → A_diagnose required. At that point, the campaign should seriously consider accepting 23.174 as the ceiling and running A_validate on the test set.
