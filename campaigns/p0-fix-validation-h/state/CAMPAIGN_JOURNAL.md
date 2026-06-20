---
schema_version: 1
campaign_id: "p0-fix-validation-h"
---

<!-- Reviewer appends one entry per round. -->
<!-- Format: ## Round N — YYYY-MM-DD -->

## Round 1 — 2026-06-20

**Action:** A_model — LightGBM n_est=600, lr=0.02, num_leaves=63, scale_pos_weight=computed (PRIORS.md baseline)
**Trigger:** STRATEGY_GUIDE §1 "No baseline exists" — first trigger, highest precedence
**Alternatives rejected:**
- A_hp: Premature without incumbent baseline to tune from
- A_feature: Premature without floor to measure gain against

**Independent assessment:** LightGBM baseline ran in 10s, produced val_pr_auc=0.8155, lift_at_10=8.99. Anomaly check clean. Bootstrap CI [0.747, 0.889], SE=0.038.
**Expected Δ (primary_metric):** n/a — baseline (target ~0.815 from PRIORS.md)
**Actual val_pr_auc:** 0.8155 (Δ = +0.8155 vs prior best of null)
**Verdict:** keep
**Key finding:** PRIORS.md prediction (0.815) was accurate to 4 decimal places. Proven baseline reproduced exactly. SE=0.038 means noise_floor=0.005 is reachable but tight — future experiments need clear signal.

## Round 2 — 2026-06-20

**Action:** A_model — XGBoost max_depth=5, n_est=300, lr=0.05, scale_pos_weight=computed (alternative family comparison)
**Trigger:** STRATEGY_GUIDE §1 "Fewer than 2 distinct model families → try alternative family"
**Alternatives rejected:**
- A_hp: STRATEGY_GUIDE says "alternative family before tuning"
- A_feature: Champion not yet locked; STRATEGY_GUIDE defers FE

**Independent assessment:** XGBoost val_pr_auc=0.8144 < LightGBM 0.8155. Δ=−0.0011. Anomaly clean. lift_at_10=9.293 (higher than LightGBM 8.990). Both families within noise_floor.
**Expected Δ (primary_metric):** 0.000–0.010 (competitive range)
**Actual val_pr_auc:** 0.8144 (Δ = −0.0011 vs prior best 0.8155)
**Verdict:** discard
**Key finding:** XGBoost and LightGBM are within noise_floor of each other (Δ=0.001). XGBoost has better lift_at_10 (9.29 vs 8.99) despite lower PR-AUC. Historian should assess: LightGBM vs XGBoost preference, and whether HP tuning one or ensembling both is the higher-ROI next step.

## Round 3 — 2026-06-20

**Action:** A_hp — Optuna LightGBM lr/num_leaves/min_child_samples (proxy n_est=200, final n_est=1000)
**Trigger:** STRATEGY_GUIDE §1 "Champion family selected; no systematic HP search yet → A_hp next highest-ROI." Historian STRATEGY_MEMO §4 confirmed bottleneck=optimizer_quality.
**Alternatives rejected:**
- A_ensemble: Requires individually tuned models; LightGBM not yet tuned
- A_feature: STRATEGY_GUIDE defers FE until champion tuned

**Independent assessment:** Optuna selected lr=0.02, num_leaves=81, min_child_samples=10. Final n_est=1000 model val_pr_auc=0.8050 < baseline 0.8155. Proxy score (0.769) failed to represent n_est=1000 performance.
**Expected Δ (primary_metric):** +0.010–0.015
**Actual val_pr_auc:** 0.804996 (Δ = −0.0105 vs prior best 0.8155)
**Verdict:** discard
**Key finding:** Proxy approach (n_est=200 proxy → n_est=1000 final) structurally unreliable. Optuna selected num_leaves=81, min_child_samples=10 which performs worse at n_est=1000 than baseline num_leaves=63, min_child_samples=5. The proxy ranking doesn't transfer. For round 4, if A_hp is retried, use direct search without proxy (fixed n_est=600, tune lr/num_leaves only).

## Round 4 — 2026-06-20

**Action:** A_hp — LightGBM n_est=2000 (single-variable increase; lr=0.02, num_leaves=63, all HP unchanged from baseline)
**Trigger:** STRATEGY_GUIDE exploit phase (final round). Historian STRATEGY_MEMO §4: bottleneck=optimizer_quality. PRIORS.md: n_est=2500 → 0.830. Consecutive_discards=2 → assumption-aware novelty check passed (no ⚠ CRITICAL assumptions).
**Alternatives rejected:**
- A_ensemble: Building blocks not individually tuned per STRATEGY_GUIDE §3.5; expected Δ +0.002–0.007 < A_hp
- A_feature: Champion not yet tuned; expected Δ +0.003–0.008; lower ROI than direct n_est increase

**Independent assessment:** LightGBM n_est=2000 produced val_pr_auc=0.8297. Δ=+0.0142 vs prior best 0.8155. Anomaly check clean. Bootstrap CI [0.759, 0.898], SE=0.037. Reproduce passed.
**Expected Δ (primary_metric):** +0.010–0.015 (PRIORS.md evidence-backed)
**Actual val_pr_auc:** 0.829680 (Δ = +0.0142 vs prior best 0.8155)
**Verdict:** keep
**Key finding:** PRIORS.md ceiling 0.830 confirmed at n_est=2000 (0.8297). Geometric-decay convergence: ~93% of n_est=600→2500 gain captured at n_est=2000. Single-variable experiment validated the most impactful HP on this dataset. New campaign champion established.
