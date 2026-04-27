---
schema_version: 1
campaign_id: "smoke-test-creditcard"
round: 8
planner_invocation_at: "2026-04-27T06:00:00Z"
action_type: "A_hp"
hypothesis: "Increasing LightGBM n_estimators from 1500 to 2000 will further improve val_pr_auc, though with diminishing returns"
expected_effect_size: 0.003
base_commit: "fb7aad4a052d24cadb1fbe05d7257d5333d08d7b"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: ["A-7-1", "A-7-2"]
---

## 1. Context

**Current champion:** LightGBM, n_estimators=1500, lr=0.02, num_leaves=63, min_child_samples=5, spw=578 → val_pr_auc=0.827750 (round 7)
**Last verdict:** keep (round 7: n_estimators=1500, Δ=+0.004)
**Consecutive discards:** 0
**Rounds remaining:** 3 (including this one)

## 2. Evidence from memory

**Historian context:**
- Bottleneck: optimizer_quality (confirmed; convergence search ongoing)
- A-7-1: model still improving at 1500; further gains possible
- A-7-2: diminishing returns evident (Δ_{600→1000}=0.009, Δ_{1000→1500}=0.004)

**Candidate actions evaluated:**

1. **A_hp (n_estimators 1500→2000):** Expected Δ: 0.001–0.004. Diminishing returns suggest ~0.002-0.003. Tests A-7-1 and A-7-2. Runtime: ~25s. Single variable.

2. **A_validate (n_estimators convergence plot):** Would require re-training many models — not feasible in single run within 90s.

3. **A_ensemble (LGBM 1500 + XGBoost):** Complex; XGBoost underperformed on its own. Low priority with 3 rounds remaining.

**Decision:** A_hp (n_estimators=2000). Continue testing convergence. Even if Δ<0.005 (near noise_floor), confirms whether 1500 is near-optimal or further gains exist. With 3 rounds remaining, this is the most informative next step.

**Pattern consistency:**
- P-1 (simple perturbations degrade): Falsified by rounds 6 and 7. n_estimators increases consistently improve. Not applicable here.
- P-2 (Amount FE hurts): Not applicable.

## 3. Plan

Change single parameter: `n_estimators=1500` → `n_estimators=2000`. All other parameters identical to champion. Update DESCRIPTION.

Expected runtime: ~24-26s (1500→2000 trees), within 90s timeout.

## 4. Helpers

None needed.

## 5. How this differs from prior experiments

Round 7 champion: n_estimators=1500. This round: n_estimators=2000. Single parameter change.

## 6. Escalation

*(Escalation frontmatter is null — no escalation block required.)*
