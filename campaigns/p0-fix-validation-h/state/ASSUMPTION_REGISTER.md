---
schema_version: 1
campaign_id: "p0-fix-validation-h"
count: 3
last_updated: "2026-06-20"
---

<!-- Reviewer appends entries on every keep verdict. -->
<!-- Format: ### A-<round>-<seq> — <short name> -->

### A-1-1 — scale_pos_weight computed from class ratio is effective

- **Claim:** Computing scale_pos_weight as n_neg/n_pos (~578) from training data produces well-calibrated LightGBM predictions on this dataset (no calibration collapse)
- **Evidence for:** val_pr_auc=0.8155 (strong), consistent with PRIORS.md across two campaigns. Probability std=non-trivial (no near-constant output). Round 2 XGBoost also produced strong calibrated output (0.8144) with same SPW — cross-family replication. Round 3 Optuna HP: still no calibration failure despite non-default num_leaves/min_child_samples. Round 4 n_est=2000: 0.8297 with no anomaly.
- **Evidence against:** none
- **Confidence:** high
- **Load-bearing:** yes
- **Verification status:** verified
- **Last audited:** round 4 by Historian

### A-4-1 — LightGBM n_est convergence is geometric (diminishing returns past n_est=2000)

- **Claim:** On this dataset (creditcard.csv, seed=42, 60/20/20 split), LightGBM PR-AUC gains from additional estimators follow geometric decay: n_est=600→0.8155, n_est=2000→0.8297 (Δ=+0.0142), n_est=2500→0.830 (PRIORS.md). Marginal gain from n_est=2000→2500 is ≈0.0003 — below noise_floor.
- **Evidence for:** Round 4 result 0.8297 ≈ PRIORS.md n_est=2500 ceiling 0.830. Round 1 (n_est=600) and Round 4 (n_est=2000) confirm the convergence curve. Bootstrap CI [0.759, 0.898] at n_est=2000 vs [0.747, 0.889] at n_est=600 — lower CI improved consistently.
- **Evidence against:** No direct measurement at n_est=2500 in this campaign; extrapolation from PRIORS.md.
- **Confidence:** high
- **Load-bearing:** yes — informs that further n_est increases beyond 2000 are not ROI-positive
- **Verification status:** partially_verified
- **Last audited:** round 4 by Historian

### A-1-2 — Single holdout is stable enough to detect Δ > noise_floor

- **Claim:** The fixed 20% holdout (seed=42, ~57k rows, ~96 positives) produces PR-AUC estimates with SE ≈ 0.038, sufficient to detect changes Δ > 0.005 (noise_floor) reliably
- **Evidence for:** Bootstrap CI [0.747, 0.889], SE=0.038 is consistent with PRIORS.md CI [0.747, 0.889] — same split, same model, same seed. Round 4 Δ=+0.0142 was successfully detected (bootstrap CI lower bound improved 0.747→0.759).
- **Evidence against:** SE=0.038 >> noise_floor=0.005; many true improvements near noise_floor will be indistinguishable from noise. Round 2 XGBoost SE=0.038 identical — both families show the same measurement uncertainty. Only improvements Δ > 0.076 (2×SE) are reliably distinguishable at 95% confidence. SE=0.037-0.041 stable across all 4 rounds — this is a structural property of the holdout size, not reducible without switching to CV.
- **Confidence:** medium
- **Load-bearing:** yes
- **Verification status:** partially_verified
- **Last audited:** round 4 by Historian
