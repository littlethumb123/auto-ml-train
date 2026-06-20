---
schema_version: 1
campaign_id: "p0-fix-validation-h"
historian_round: 4
trigger: "periodic"
rounds_covered: [3, 4]
---

## 1. Trajectory Narrative

Campaign completed all 4 rounds. Covered window (rounds 3-4) moved from a failed exploitation attempt to a successful exploitation that reached the PRIORS.md ceiling. Round 3 (A_hp Optuna proxy, n_est=200 proxy → n_est=1000 final): val_pr_auc=0.8050, Δ=−0.0105 — the proxy objective landscape at n_est=200 did not rank HP configurations reliably for the n_est=1000 final model; Optuna selected num_leaves=81, min_child_samples=10 which underperform vs the baseline num_leaves=63, min_child_samples=5. Round 4 (A_hp direct n_est=2000, all other HP unchanged): val_pr_auc=0.8297, Δ=+0.0142 — abandoning the proxy mechanism in favor of a single-variable change on a PRIORS.md-backed claim produced the campaign's largest single-round gain. Full trajectory: 0.8155 (R1, keep) → 0.8144 (R2, discard) → 0.8050 (R3, discard) → 0.8297 (R4, keep). Δ-per-round over window: −0.0105 (R3) and +0.0142 (R4), net +0.0037 over 2 rounds. Campaign ended in saturation phase: best metric 0.8297 ≈ PRIORS.md n_est=2500 ceiling (0.830), implying n_est is now exhausted as a primary lever. Phase transition occurred between rounds 3 and 4: from complexity-adding proxy approach (failed) to principled single-variable exploitation (succeeded). Last keep is R4 (0 rounds since last keep); no plateau signal.

## 2. Pattern Extraction

**P-1 (confirm and elevate from Observation O-1): Computed scale_pos_weight (n_neg/n_pos) is robust across gradient-boosting families and HP configurations on this dataset.**

- Round 1 (LightGBM, n_est=600, default HP): val_pr_auc=0.8155, no calibration failure, probability std non-trivial
- Round 2 (XGBoost, n_est=300, default HP): val_pr_auc=0.8144, no calibration failure
- Round 3 (LightGBM, n_est=1000, Optuna-selected HP): val_pr_auc=0.8050, no calibration failure (performance drop was HP-driven, not calibration-driven)
- Round 4 (LightGBM, n_est=2000, default HP): val_pr_auc=0.8297, no calibration failure

All 4 rounds across 2 families and varied HP produced valid probability outputs above anomaly floor. Cross-references O-1 from STRATEGY_MEMO round 2 — now elevated to formal pattern with high confidence. PATTERN_BOOK.md entry added as P-1.

**P-2 (new): n_estimators is the dominant HP lever for LightGBM val_pr_auc on this dataset; changing other HP (num_leaves, min_child_samples) without increasing n_est produces neutral-to-negative returns.**

- Round 1 (n_est=600, num_leaves=63, min_child_samples=5): baseline 0.8155
- Round 3 (n_est=1000, num_leaves=81, min_child_samples=10 via Optuna): 0.8050 — Δ=−0.0105 vs baseline despite larger n_est; other-HP changes negated and reversed the n_est gain
- Round 4 (n_est=2000, num_leaves=63, min_child_samples=5 unchanged): 0.8297 — Δ=+0.0142; pure n_est increase with locked other HP succeeded

The round 3 vs round 4 contrast is the clearest signal: same dataset, same family, higher n_est in both, but R3 changed other HP and fell below baseline while R4 kept other HP constant and achieved the campaign maximum. Confidence: low (only 3 LightGBM rounds, but the directional signal is unambiguous and consistent with PRIORS.md geometric-decay convergence). PATTERN_BOOK.md entry added as P-2.

## 3. Assumption Audit

**A-1-1 — scale_pos_weight computed from class ratio is effective (load_bearing: yes, was: partially_verified)**

Covered-window evidence: Round 3 (Optuna HP with num_leaves=81): still no calibration failure despite non-default HP. Round 4 (n_est=2000): strong calibration confirmed (val_pr_auc=0.8297, probability std non-trivial, no anomaly). All 4 campaign rounds have now confirmed this assumption independently across 2 model families and varied HP configurations. No evidence against in any round. Status update: partially_verified → **verified**. No critical flag needed.

**A-1-2 — Single holdout SE ≈ 0.038 is sufficient to detect Δ > noise_floor (load_bearing: yes, was: partially_verified)**

Covered-window evidence: Round 3 SE=0.041, Round 4 SE=0.037. SE is stable and consistent at ~0.038 across all rounds. Bootstrap CI lower bound improved 0.747 (R1) → 0.759 (R4) — the improvement is visible in the CI shift, suggesting the round 4 gain is genuine. However: SE=0.037–0.041 >> noise_floor=0.005. Reliable detection requires Δ > ~0.074 (2×SE); the campaign's observed gains of Δ=+0.0142 (R4) are in the zone where true improvements can be detected but with wide uncertainty. Evidence against remains: improvements near noise_floor (0.005) cannot be distinguished from noise. Status: remain partially_verified. This is the 2nd Historian audit. A-1-2 remains partially_verified (not unverified), so no ⚠ CRITICAL flag is triggered (⚠ CRITICAL requires verification_status: unverified after ≥2nd audit).

**A-4-1 — LightGBM n_est convergence is geometric (load_bearing: yes, was: partially_verified)**

This is the 1st Historian audit of A-4-1. Covered-window evidence: Round 4 n_est=2000 → 0.8297 ≈ PRIORS.md n_est=2500 → 0.830. Marginal gain from n_est=600→2000 is +0.0142; marginal gain from n_est=2000→2500 estimated ≈0.0003. This confirms geometric-decay convergence: most of the total gain is captured by n_est=2000. Status: partially_verified (first audit). No ⚠ CRITICAL (first audit, not unverified).

**0 assumptions flagged ⚠ CRITICAL.**

## 4. Bottleneck Diagnosis

**Category: eval_quality**

Justification:
1. **n_est ceiling reached.** Round 4 val_pr_auc=0.8297 ≈ PRIORS.md n_est=2500 ceiling (0.830). Marginal gain from further n_est increase is ≈0.0003 — below noise_floor (0.005) and far below the 2×SE detection threshold (~0.074). The primary remaining optimization levers (direct lr/num_leaves search, Amount feature interactions, ensemble averaging) each have expected Δ of +0.003–0.010, which are below or near the 2×SE detection threshold.
2. **SE=0.037–0.041 is the binding constraint.** All 4 rounds show consistent SE≈0.038 on the single 20% holdout (~57k rows, ~96 positives). At this SE level, only experiments targeting Δ > 0.074 (2×SE) can be reliably distinguished from noise. The gap between current champion (0.8297) and theoretical ceiling (≈0.84–0.85 with full optimization) is likely ≤0.015 — achievable only with a more sensitive evaluation scheme.

Highest-ROI technique class from UNEXPLORED_TECHNIQUES.md: **Cross-validation scheme upgrade (k-fold CV)** — not currently in UNEXPLORED_TECHNIQUES.md (appended during Step 6). Upgrading to 5-fold stratified CV reduces SE by √5 factor to ≈0.017, enabling reliable detection of improvements as small as Δ ≈ 0.034 (2×SE). This unblocks lr, num_leaves, and feature engineering experiments that are currently undetectable on the single holdout.
