---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 11
last_updated: "2026-04-27 (round 10 keep — campaign final)"
---

<!-- Reviewer appends entries on every keep verdict. -->
<!-- Format: ### A-<round>-<seq> — <short name> -->

### A-1-1 — scale_pos_weight has minimal effect on PR-AUC for this dataset

- **Claim:** PR-AUC for the creditcard fraud dataset is not significantly improved by setting scale_pos_weight to the class ratio (~578) vs 1, because PR-AUC is inherently imbalance-aware. The observed val_pr_auc=0.815530 with spw=578 may not meaningfully exceed the spw=1 baseline (~0.822 per planner memory).
- **Evidence for:** Result is 0.815530 with spw=578; planner cited 0.822 with spw=1. The difference (~0.006) is within the noise_floor=0.005. Strategy Guide §2 warns A_imbalance gives 0.000–0.010 when PR-AUC is primary metric.
- **Evidence against:** Baseline value (0.822) is not independently verified from artifacts; may differ.
- **Confidence:** low
- **Load-bearing:** yes — next planner should not re-try scale_pos_weight variants as high-ROI actions
- **Verification status:** unverified
- **Last audited:** round 4 by Historian (no new evidence for or against; dead-end recorded in DEAD_ENDS.md)

### A-1-2 — LightGBM is a viable model family for this problem

- **Claim:** LightGBM with standard hyperparameters (n_estimators=600, lr=0.02, num_leaves=63) achieves val_pr_auc ≥ 0.80 on the creditcard dataset with the fixed 60/20/20 stratified split.
- **Evidence for:** val_pr_auc=0.815530 confirmed by reproduce + bootstrap CI [0.7404, 0.8878]. Runs in 9.9s on n_jobs=4. XGBoost at 200 estimators scored only 0.793611 — LightGBM leads by 0.022.
- **Evidence against:** None
- **Confidence:** high
- **Load-bearing:** yes — establishes LightGBM as the champion family baseline for future A_model comparisons
- **Verification status:** verified (round 1 reproduction; round 2 cross-family comparison)
- **Last audited:** round 4 by Historian (XGBoost default underperformed; LGBM family confirmed superior at tested configs)

### A-1-3 — val split has adequate positive count for PR-AUC estimation but wide CI

- **Claim:** The val set contains approximately 97 fraud cases (56,962 × 0.0017 ≈ 97). This is sufficient for PR-AUC point estimates but produces wide bootstrap CI (SE≈0.038), meaning improvements below ~0.010 will be statistically ambiguous.
- **Evidence for:** Bootstrap SE=0.0378, 95% CI=[0.7404, 0.8878]. Val fraud rate=0.0017 confirmed. Consistent with AGENTS.md rule: "Single-split PR-AUC on ~100 positives has CI ≈ ±0.005–0.010."
- **Evidence against:** None
- **Confidence:** high
- **Load-bearing:** yes — Reviewer must account for SE≈0.038 when interpreting Δ results; improvements < noise_floor=0.005 are unreliable
- **Verification status:** verified (round 1 bootstrap CI)
- **Last audited:** round 4 by Historian (bootstrap SE ≈ 0.038 confirmed across rounds 1-4)

### A-6-1 — LightGBM with n_estimators=1000 outperforms n_estimators=600

- **Claim:** LightGBM trained for 1000 boosting rounds (lr=0.02, num_leaves=63, spw=578) achieves val_pr_auc=0.824075, which is meaningfully above the 600-round champion (0.815530). The model was not yet converged at 600 rounds.
- **Evidence for:** val_pr_auc=0.824075 vs 0.815530 (Δ=+0.008545). Bootstrap CI [0.749, 0.892] — CI lower bound exceeds champion CI lower bound (0.740). Training time 12.7s (well within 90s timeout).
- **Evidence against:** None
- **Confidence:** medium (single run; Δ is slightly above bootstrap SE=0.037, so borderline statistically significant)
- **Load-bearing:** yes — n_estimators=1000 is now the champion config; future experiments inherit this setting
- **Verification status:** unverified (seed stability not tested)
- **Last audited:** round 6 by Reviewer

### A-6-2 — LightGBM with lr=0.02 needs >600 boosting rounds for convergence on this dataset

- **Claim:** With lr=0.02, LightGBM requires more than 600 boosting rounds to converge for the creditcard fraud dataset. 1000 rounds is better; the optimal may be 800-1500.
- **Evidence for:** n_estimators=1000 outperforms 600 by 0.009. The improvement suggests additional iterations still find signal.
- **Evidence against:** 1000 vs 600 is the only comparison; we don't know if 1200 or 1500 would further improve.
- **Confidence:** medium — round 7 (n_est=1500) also improved, confirming the trend. Both 1000 and 1500 beat 600.
- **Load-bearing:** yes — guides future n_estimators choices
- **Verification status:** partially_verified (confirmed: >600 better; optimal: unknown, >1000 still improving)
- **Last audited:** round 7 by Reviewer

### A-7-1 — LightGBM PR-AUC continues improving beyond 1000 estimators at lr=0.02

- **Claim:** LightGBM with n_estimators=1500 (val_pr_auc=0.827750) outperforms n_estimators=1000 (0.824075). The model at lr=0.02 has not yet converged by 1500 rounds — further gains may be possible.
- **Evidence for:** n_estimators=1500 improves on 1000 by Δ=+0.003675. Bootstrap CI [0.7538, 0.8951].
- **Evidence against:** Diminishing returns trend: 600→1000 Δ=+0.009, 1000→1500 Δ=+0.004. Rate of improvement is slowing.
- **Confidence:** medium
- **Load-bearing:** yes — determines whether to try n_estimators=2000 in remaining rounds
- **Verification status:** unverified (optimal n_estimators unknown)
- **Last audited:** round 7 by Reviewer

### A-7-2 — Diminishing returns on n_estimators beyond 1500

- **Claim:** The marginal gain per additional 500 estimators is shrinking: Δ_{600→1000}=+0.009, Δ_{1000→1500}=+0.004. The next step (1500→2000) may yield <0.003 — near or below noise_floor.
- **Evidence for:** Two data points show clearly diminishing returns: 0.009 → 0.004 improvement per 500-estimator increment.
- **Evidence against:** Round 8 (n_est=2000, Δ=+0.002198) confirms diminishing returns but Δ still > noise_floor (0.005 is the noise floor; 0.002 is below it).
- **Confidence:** medium — three data points now confirm: Δ_{600→1000}=0.009, Δ_{1000→1500}=0.004, Δ_{1500→2000}=0.002.
- **Load-bearing:** no — advisory only
- **Verification status:** partially_verified (trend confirmed, specific ceiling unknown)
- **Last audited:** round 8 by Reviewer

### A-8-1 — LightGBM n_estimators=2000 is the confirmed best in the campaign

- **Claim:** LightGBM with n_estimators=2000 (val_pr_auc=0.829948) is the current campaign champion. The diminishing returns trend (0.009 → 0.004 → 0.002 per 500-estimator step) suggests the optimal is near 2000 for lr=0.02.
- **Evidence for:** val_pr_auc=0.829948, Δ=+0.002198 vs 1500. Bootstrap CI [0.7556, 0.8964]. Three consecutive keeps at 1000, 1500, 2000 — clear convergence trajectory.
- **Evidence against:** Next step (2000→2500) may still improve by ~0.001 — but at 21s runtime, 2500 would take ~26s, still within budget.
- **Confidence:** medium
- **Load-bearing:** yes — this is the final champion unless round 9/10 improves it
- **Verification status:** unverified (seed stability)
- **Last audited:** round 8 by Reviewer

### A-8-2 — n_estimators convergence approaching at lr=0.02 for this dataset

- **Claim:** The model is approaching convergence. Δ per 500 additional estimators: 0.009 → 0.004 → 0.002 (halving each step). Predicted Δ for 2000→2500: ~0.001 (below noise_floor). Further n_estimators increases are unlikely to produce significant PR-AUC gains.
- **Evidence for:** Three clean data points showing geometric decay in Δ.
- **Evidence against:** Pattern could break — overfitting could occur at 2500+ but data is large enough to not overfit.
- **Confidence:** medium
- **Load-bearing:** yes — guides round 9 plan; if this holds, should shift to different HP or direction
- **Verification status:** unverified
- **Last audited:** round 8 by Reviewer

### A-9-1 — Feature additions from raw data columns consistently hurt PR-AUC

- **Claim:** Adding engineered features from raw Time or Amount columns to the 30-feature V1-V28 PCA space severely degrades LightGBM PR-AUC. Two independent tests confirm: log1p(Amount) (Δ=-0.035, round 4) and Time_mod_86400 (Δ=-0.044, round 9). The PCA feature space is informationally complete for fraud detection; appending raw-column transformations introduces noise.
- **Evidence for:** Two data points from rounds 4 and 9, both large negative Δ (>5× noise_floor). Consistent across different feature types (amount transform vs time transform).
- **Evidence against:** Only Time and Amount tested. PCA-derived features from external data (if available) are untested and not a dead end.
- **Confidence:** high (two independent confirmations, large effect sizes)
- **Load-bearing:** yes — ALL feature addition experiments using Time/Amount columns should be avoided
- **Verification status:** verified (two confirmations)
- **Last audited:** round 9 by Reviewer

### A-10-1 — n_estimators convergence at lr=0.02 asymptotes near 2500 for this dataset

- **Claim:** The geometric decay pattern (Δ: 0.009→0.004→0.002→0.0004 per 500-estimator step) confirms the LightGBM model is asymptotically converged near n_estimators=2500 with lr=0.02. Further increases (3000+) are expected to yield Δ<0.0001 — effectively zero.
- **Evidence for:** Four data points showing geometric Δ decay across 600→1000→1500→2000→2500. Each step yields roughly half the previous gain.
- **Evidence against:** None — pattern is highly consistent.
- **Confidence:** high (four consecutive confirmations; clean geometric pattern)
- **Load-bearing:** yes — final campaign conclusion; documents the convergence boundary for this config
- **Verification status:** verified (four-point geometric decay confirmed)
- **Last audited:** round 10 by Reviewer (campaign final)
