---
schema_version: 1
campaign_id: "smoke-test-creditcard"
last_verdict: discard
last_round: 2
---

<!-- Reviewer appends one block per round. -->

## Round 1 — 2026-04-26

**Commit:** 2023897d3a544060477463e9e9cc7af70d25dcaf
**Action type:** A_imbalance
**Description:** LightGBM scale_pos_weight=computed_ratio (~578) — n_estimators=600, lr=0.02, num_leaves=63

### §Independent Assessment (Phase 1 — before reading plan)

**Parsed metrics from run.log:**
- val_pr_auc: 0.815530
- lift_at_10: 8.988637
- macro_f1: 0.920331
- val_f1: 0.999478
- training_seconds: 7.6
- total_seconds: 9.9
- n_features: 30

**Mandatory tool outputs:**

`runner.tools.anomaly`: fired=False, within expected range.
`runner.tools.bootstrap_ci` (n_boot=500): metric=0.815530, ci_lo=0.7404, ci_hi=0.8878, SE=0.0378.

**Prior best:** None (round 1 — first experiment). Δ = N/A.
**Preliminary verdict:** KEEP

### §Plan Comparison

Hypothesis: scale_pos_weight=578 raises recall vs spw=1. Expected Δ=+0.020 vs baseline 0.822. Actual: 0.815530. Weakly falsified relative to plan's baseline but result is valid first champion.

### §Verdict: KEEP

**Tools ran:** ["runner.tools.anomaly", "runner.tools.bootstrap_ci"]

## Round 2 — 2026-04-27

**Commit:** d1bf79748b076cc10b293b83607b6f0b9774d9e2
**Action type:** A_model
**Description:** XGBoost n_estimators=200, lr=0.05, max_depth=6, scale_pos_weight=578, tree_method=hist

### §Independent Assessment (Phase 1 — before reading plan)

**Parsed metrics from run.log:**
- val_pr_auc: 0.793611
- lift_at_10: 9.190628
- macro_f1: 0.912659
- val_f1: 0.999434
- training_seconds: 2.4
- total_seconds: 4.8
- n_features: 30

**Mandatory tool outputs:**

`runner.tools.anomaly`: fired=False, val_pr_auc=0.793611 within expected range (threshold=0.750000).
`runner.tools.bootstrap_ci` (n_boot=500): metric=0.793611, ci_lo=0.7129, ci_hi=0.8674, SE=0.0392.

**Prior best:** 0.815530 (round 1, LightGBM). Δ = -0.021919.
**Preliminary verdict:** DISCARD — Δ < 0.

### §Plan Comparison

Hypothesis: XGBoost will match or exceed LightGBM val_pr_auc=0.815530. Expected Δ=+0.010.
Actual Δ=-0.022. Hypothesis falsified. XGBoost at n_est=200 undertrained vs LGBM n_est=600.
LightGBM leads by >2× noise_floor → Strategy Guide says commit to LightGBM as champion family.

### §Verdict: DISCARD

- Δ = -0.021919 < 0
- Anomaly: did not fire
- No tool regression

**Bootstrap SE:** 0.0392 (95% CI: [0.7129, 0.8674])
**Tools ran:** ["runner.tools.anomaly", "runner.tools.bootstrap_ci"]
