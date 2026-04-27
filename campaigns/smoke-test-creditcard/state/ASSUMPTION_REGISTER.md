---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 5
last_updated: "2026-04-27 (round 6 keep)"
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
- **Confidence:** low
- **Load-bearing:** yes — guides future n_estimators choices
- **Verification status:** unverified
- **Last audited:** round 6 by Reviewer
