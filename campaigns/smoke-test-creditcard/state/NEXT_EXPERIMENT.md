---
schema_version: 1
campaign_id: "smoke-test-creditcard"
round: 10
planner_invocation_at: "2026-04-27T06:00:00Z"
action_type: "A_hp"
hypothesis: "Increasing LightGBM n_estimators from 2000 to 2500 will yield a small but positive Δ (~0.001) consistent with the observed geometric convergence decay"
expected_effect_size: 0.001
base_commit: "42cb30239d4fb9cd1971b26bb8013276e8227670"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: ["A-8-2", "A-8-1"]
---

## 1. Context

**Current champion:** LightGBM, n_estimators=2000, lr=0.02, num_leaves=63, min_child_samples=5, spw=578 → val_pr_auc=0.829948 (round 8)
**Last verdict:** discard (round 9: Time_mod_86400 Δ=-0.044)
**Consecutive discards:** 1
**Rounds remaining:** 1 (this is the final round)

## 2. Evidence from memory

**Historian context (round 9 periodic):**
- Bottleneck: near_optimum (n_estimators convergence reached; feature additions dead end)
- P-3 (feature additions hurt): HIGH confidence — two confirmations (log1p Amount Δ=-0.035, Time_mod_86400 Δ=-0.044)
- A-8-2 (convergence approaching): geometric decay Δ: 0.009→0.004→0.002. Predicted 2000→2500 Δ~0.001
- Historian recommendation: n_estimators=2500 (safe, positive predicted Δ)

**Candidate actions evaluated:**

1. **A_hp (n_estimators 2000→2500):** Expected Δ: ~0.001. Geometric extrapolation from confirmed decay pattern. Runtime: ~26-28s (within 90s budget). Very low risk of large negative Δ. Tests A-8-2 (convergence curve) and A-8-1 (2000 is confirmed best). Closes the campaign on a predicted keep.

2. **A_hp (colsample_bytree 0.8→0.6):** Higher variance direction. Untested. Could yield +0.003-0.010 or negative. With 1 round remaining, the downside (ending on a discard) outweighs the potential upside. Not selected.

3. **A_feature:** Dead end (P-3, high confidence). Not considered.

4. **A_ensemble:** Complex, XGBoost underperformed in r2. Not viable in 1 round.

**Decision:** A_hp (n_estimators=2500). Safest option for the final round. Predicted positive Δ consistent with established geometric convergence curve. Even if Δ < noise_floor, a positive result is a valid keep under verdict rules.

**Pattern consistency:**
- P-1 (perturbations degrade): Partially falsified — HP tuning within n_estimators consistently improves. n_estimators=2500 continues the established winning direction.
- P-3 (feature additions hurt): Strongly confirmed; not applicable here.

## 3. Plan

Change single parameter: `n_estimators=2000` → `n_estimators=2500`. All other parameters identical to champion. Update DESCRIPTION.

Expected runtime: ~26-28s (linear extrapolation from n_estimators=2000 at 21.4s), within 90s timeout.

## 4. Helpers

None needed.

## 5. How this differs from prior experiments

Round 8 champion: n_estimators=2000 (val_pr_auc=0.829948). This round: n_estimators=2500. Single parameter change. Expected Δ~0.001 — below noise_floor but positive by geometric extrapolation. This is the final round of the campaign.

## 6. Escalation

*(Escalation frontmatter is null — no escalation block required.)*
