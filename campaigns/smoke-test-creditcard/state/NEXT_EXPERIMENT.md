---
schema_version: 1
campaign_id: "smoke-test-creditcard"
round: 7
planner_invocation_at: "2026-04-27T05:45:00Z"
action_type: "A_hp"
hypothesis: "Increasing LightGBM n_estimators from 1000 to 1500 will further improve val_pr_auc as the model has not yet converged with lr=0.02"
expected_effect_size: 0.005
base_commit: "4752849eab444deacb61a7b0a18ebbfdb9ec0380"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: ["A-6-2"]
---

## 1. Context

**Current champion:** LightGBM, n_estimators=1000, lr=0.02, num_leaves=63, min_child_samples=5, spw=578 → val_pr_auc=0.824075 (round 6)
**Last verdict:** keep (round 6: n_estimators=1000, Δ=+0.009)
**Consecutive discards:** 0
**Rounds remaining:** 4 (including this one)

## 2. Evidence from memory

**Historian context (STRATEGY_MEMO.md §4):**
- Bottleneck: optimizer_quality — confirmed by round 6 result. n_estimators=600 was undertrained; 1000 improved.
- A-6-2 (lr=0.02 needs >600 rounds): partially verified — 1000 > 600 confirmed improvement. Unknown if 1500 > 1000.

**Strategy Guide trigger:** "2+ A_hp rounds on same family; Δ shrinking toward noise_floor → HP space likely saturated." Counter: only 1 A_hp keep round so far (round 6); Δ=+0.009 is still well above noise_floor=0.005. Continue A_hp.

**Candidate actions evaluated:**

1. **A_hp (n_estimators 1000→1500):** Expected Δ: 0.003–0.007. A-6-2 assumption: lr=0.02 needs >600 rounds, likely needs >1000. 1500 rounds adds 50% more iterations. Runtime estimate: 12.7s × (1500/1000) ≈ 19s — within 90s timeout. Directly tests A-6-2.

2. **A_hp (learning_rate 0.02→0.01, n_estimators=1000):** Expected Δ: 0.002–0.006. Two-variable change (lr + implicitly more iterations needed). Not valid as single-variable test unless keeping n_estimators fixed.

3. **A_hp (colsample_bytree 0.8→0.6):** Expected Δ: 0.001–0.004. Less promising; colsample has not been identified as a bottleneck.

**Decision:** A_hp (n_estimators=1500). Directly tests A-6-2 assumption and follows the convergence trajectory established in round 6.

**Pattern consistency:**
- P-1 (simple perturbations degrade): Round 6 falsified this pattern for n_estimators direction. n_estimators=1000 kept at Δ=+0.009. This experiment continues in the same direction.
- P-2 (Amount FE hurts): Not applicable.

**Dead-ends:** num_leaves=127, min_child_samples=1, log1p Amount, XGBoost default. None apply.

## 3. Plan

Change single parameter: `n_estimators=1000` → `n_estimators=1500`. All other parameters identical to champion. Update DESCRIPTION.

Expected runtime: ~19-20s, well within 90s timeout.

## 4. Helpers

None needed.

## 5. How this differs from prior experiments

Round 6 champion: n_estimators=1000. This round: n_estimators=1500. Single parameter change. All other HP and evaluation code identical.

## 6. Escalation

*(Escalation frontmatter is null — no escalation block required.)*
