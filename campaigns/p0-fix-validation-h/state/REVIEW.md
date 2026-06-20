---
schema_version: 1
campaign_id: "p0-fix-validation-h"
last_round: 4
last_verdict: keep
---

## Round 1 — 2026-06-20

### Independent Assessment (Phase 1 — before reading plan)

**Metrics from run.log:**
- val_pr_auc: 0.815530
- lift_at_10: 8.990215
- macro_f1: 0.920331
- val_f1: 0.999478
- training_seconds: 7.6s, total: 10.0s
- n_features: 30

**Anomaly check:** fired=false. val_pr_auc=0.8155 is well above anomaly floor=0.30. Clean.

**Bootstrap CI (n_boot=200, alpha=0.05):** metric=0.8155, CI=[0.747, 0.889], SE=0.038. CI is wide (expected for single holdout with ~96 positives), but result is stable.

**Reproduce check:** passed. All recomputed metrics match reported values within tolerance=0.001. No mismatches.

**Δ vs prior best:** No prior experiment — this is the baseline. Δ = 0.8155 (absolute, first result).

**Preliminary verdict: keep.** No anomaly fired, all mandatory tools passed, no prior to beat. The result is a well-calibrated LightGBM with strong PR-AUC.

### Plan Comparison (Phase 2)

**Hypothesis:** LightGBM n_est=600, lr=0.02, num_leaves=63, scale_pos_weight=computed reproduces val_pr_auc≈0.815.

**Expected Δ:** ~0.815 (absolute, baseline). **Actual:** 0.8155. **Confirmation: YES.** Hypothesis verified exactly. PRIORS.md prediction was accurate to 4 decimal places.

**Discrepancy analysis:** None. Expected and actual match within rounding (0.815 ≈ 0.8155).

### Verdict Rationalization

| Check | Result | Verdict implication |
|-------|--------|---------------------|
| Δ(primary_metric) | 0.8155 (baseline — no prior) | First experiment, exceeds noise_floor trivially |
| Anomaly check | fired=false, val_pr_auc=0.8155 >> floor=0.30 | Clean — no C1 |
| Mandatory tools ran | runner.tools.anomaly ✓, runner.tools.bootstrap_ci ✓ | All mandatory tools completed |
| Reproduce check | passed, 0 mismatches | Artifacts consistent |
| Bootstrap CI | [0.747, 0.889], SE=0.038 | Wide CI (expected), result usable |
| Phase 1 preliminary | keep | — |
| Hypothesis confirmed? | Yes — val_pr_auc=0.8155 ≈ PRIORS.md 0.815 | PRIORS.md baseline reproduced |
| **Final verdict** | **keep** | **Baseline established. All gates passed. No prior to beat.** |

**VERDICT: keep d20e21769bf720b89f011ba346644ea2d1d47063**

## Round 2 — 2026-06-20

### Independent Assessment (Phase 1 — before reading plan)

**Metrics from run.log:**
- val_pr_auc: 0.814426
- lift_at_10: 9.293256
- macro_f1: 0.926022
- val_f1: 0.999515
- training_seconds: 3.0s, total: 5.3s
- n_features: 30

**Anomaly check:** fired=false. val_pr_auc=0.8144 within range (threshold=0.408, well above floor=0.30). Clean.

**Bootstrap CI (n_boot=200, alpha=0.05):** metric=0.8144, CI=[0.749, 0.885], SE=0.038. Similar spread to round 1 LightGBM.

**Reproduce check:** passed. All metrics match within tolerance=0.001. No mismatches.

**Δ vs prior best (0.8155):** Δ = 0.8144 − 0.8155 = −0.0011. NEGATIVE. Below incumbent.

**Preliminary verdict: discard.** val_pr_auc < best_prior (0.8144 < 0.8155). Δ < 0. Primary metric decreases. Note: lift_at_10=9.293 > LightGBM's 8.990 — XGBoost ranks higher in top decile despite lower overall PR-AUC.

### Plan Comparison (Phase 2)

**Hypothesis:** XGBoost expected val_pr_auc in 0.80-0.82 range.

**Actual:** 0.8144. Within expected range. Hypothesis partially confirmed: XGBoost is competitive (within noise_floor) but does not beat LightGBM on primary metric. Two families are within noise_floor of each other (Δ=0.001).

**STRATEGY_GUIDE §1 implication:** "2+ families within noise_floor of each other → Tune both briefly before committing." Historian (firing now per historian_interval=2) should assess whether LightGBM or XGBoost is the better base for HP tuning.

### Verdict Rationalization

| Check | Result | Verdict implication |
|-------|--------|---------------------|
| Δ(primary_metric) | −0.0011 (0.8144 vs 0.8155) | Negative — below incumbent |
| Anomaly check | fired=false | Clean |
| Mandatory tools ran | anomaly ✓, bootstrap_ci ✓ | All passed |
| Reproduce check | passed | Consistent |
| Bootstrap CI | [0.749, 0.885], SE=0.038 | CIs overlap heavily with round 1 — within noise |
| Phase 1 preliminary | discard | — |
| Hypothesis confirmed? | Partially — within expected range, but Δ < 0 | XGBoost competitive, not better |
| **Final verdict** | **discard** | **Δ < 0 on primary metric. Not a dead-end — XGBoost within noise_floor.** |

**VERDICT: discard 032ef35633d2bea93cc1ca2f195932d27425cd6a**

## Round 3 — 2026-06-20

### Independent Assessment (Phase 1 — before reading plan)

**Metrics from run.log:**
- val_pr_auc: 0.804996
- lift_at_10: 8.586160
- macro_f1: 0.921494
- val_f1: 0.999473
- total_seconds: 52.5s (within 60s timeout)
- n_features: 30

**Anomaly check:** fired=false. val_pr_auc=0.8050 within range (threshold=0.408). Clean.

**Bootstrap CI (n_boot=200, alpha=0.05):** metric=0.8050, CI=[0.726, 0.887], SE=0.041. CI lower bound dropped vs round 1 (0.726 vs 0.747) — slightly more uncertain result.

**Reproduce check:** passed. All metrics match within tolerance=0.001.

**Δ vs prior best (0.8155):** Δ = 0.8050 − 0.8155 = −0.0105. Negative. Optuna-tuned model is worse than default baseline.

**Preliminary verdict: discard.** val_pr_auc < best_prior (0.8050 < 0.8155). Δ = −0.0105. Optuna HP search with proxy approach (n_est=200) found num_leaves=81, min_child_samples=10 — config that performs worse than baseline (num_leaves=63, min_child_samples=5) at n_est=1000.

**Key structural observation (pre-plan):** Proxy score was 0.769 (n_est=200) vs final score 0.805 (n_est=1000). The proxy did not reliably rank HP configurations for the final n_est=1000 model. This proxy-mismatch is the likely root cause.

### Plan Comparison (Phase 2)

**Hypothesis:** Optuna expected Δ +0.010-0.015 toward 0.830 ceiling.

**Actual:** Δ = −0.0105. Hypothesis falsified. Optuna search DEGRADED performance. The proxy approach was structurally flawed for this problem: n_est=200 with lr≈0.02, num_leaves=81 doesn't converge sufficiently to rank well vs n_est=600 baseline. The selected HP (num_leaves=81 vs baseline 63, min_child_samples=10 vs baseline 5) appear to slightly underfit at n_est=1000 with this lr.

### Verdict Rationalization

| Check | Result | Verdict implication |
|-------|--------|---------------------|
| Δ(primary_metric) | −0.0105 (0.8050 vs 0.8155) | Negative — below incumbent |
| Anomaly check | fired=false | Clean |
| Mandatory tools ran | anomaly ✓, bootstrap_ci ✓ | All passed |
| Reproduce check | passed | Consistent |
| Bootstrap CI | [0.726, 0.887], SE=0.041 | Slightly wider than baseline — noisier result |
| Phase 1 preliminary | discard | — |
| Hypothesis confirmed? | No — Δ = −0.0105, proxy approach failed to rank HP well | Proxy n_est=200 was too small to represent n_est=1000 optimization landscape |
| **Final verdict** | **discard** | **Δ = −0.0105 < 0. Proxy-search approach is a dead-end. Baseline n_est=600 remains champion.** |

**VERDICT: discard 4b0f4aa09839e67b64204c1c38371e3ed35baa52**

## Round 4 — 2026-06-20

### Independent Assessment (Phase 1 — before reading plan)

**Metrics from run.log:**
- val_pr_auc: 0.829680
- lift_at_10: 9.192242
- macro_f1: 0.926022
- val_f1: 0.999515
- training_seconds: 18.3s, total: 20.9s
- n_features: 30

**Anomaly check:** fired=false. val_pr_auc=0.8297 within expected range (threshold=0.408). Clean.

**Bootstrap CI (n_boot=200, alpha=0.05):** metric=0.8297, CI=[0.759, 0.898], SE=0.037. CI lower bound 0.759 vs baseline 0.747 — clear improvement in pessimistic tail.

**Reproduce check:** passed. All recomputed metrics match reported values within tolerance=0.001.

**Δ vs prior best (0.8155):** Δ = 0.8297 − 0.8155 = +0.0142. POSITIVE. Clear improvement.

**Preliminary verdict: keep.** Δ = +0.0142 >> noise_floor = 0.005. All mandatory tools passed. Anomaly clean. Single-variable change (n_est 600→2000) confirmed significant gain.

### Plan Comparison (Phase 2)

**Hypothesis:** n_est=2000 expected Δ +0.010-0.015 based on PRIORS.md (n_est=2500 → 0.830).

**Actual:** val_pr_auc=0.8297. Δ=+0.0142. Hypothesis CONFIRMED — PRIORS.md ceiling of 0.830 almost exactly matched at n_est=2000 (0.8297 ≈ 0.830). The geometric-decay convergence pattern (PRIORS.md note: "geometric-decay convergence") is confirmed: most of the gain from n_est=600→2500 is captured at n_est=2000.

### Verdict Rationalization

| Check | Result | Verdict implication |
|-------|--------|---------------------|
| Δ(primary_metric) | +0.0142 (0.8297 vs 0.8155) | Well above noise_floor (0.005) → keep-eligible |
| Anomaly check | fired=false | Clean |
| Mandatory tools ran | anomaly ✓, bootstrap_ci ✓ | All mandatory tools completed |
| Reproduce check | passed, 0 mismatches | Consistent |
| Bootstrap CI | [0.759, 0.898], SE=0.037 | Lower CI bound improved 0.747→0.759; genuine improvement |
| Phase 1 preliminary | keep | — |
| Hypothesis confirmed? | Yes — Δ=+0.0142 matches PRIORS.md prediction (n_est=2500→0.830) | PRIORS.md geometric-decay convergence confirmed |
| **Final verdict** | **keep** | **Δ = +0.0142 >> noise_floor=0.005. All gates passed. New champion.** |

**VERDICT: keep 2eeebcbe98963d5a36ce614d4c62f3efb456f97c**
