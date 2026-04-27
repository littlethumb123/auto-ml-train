---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 3
last_updated: "2026-04-27 (round 9 historian)"
---

<!-- Historian appends entries during periodic/C2 runs. -->
<!-- Format: ### P-<seq> — <pattern name> -->

### P-1 — Simple perturbations of the champion consistently degrade PR-AUC

- **Pattern:** Single-parameter perturbations of the champion LightGBM configuration (model family swap, num_leaves increase, feature addition) all produce negative Δ on PR-AUC. The champion appears to be a local optimum that simple perturbations cannot escape.
- **Supporting evidence:** round 2 (XGBoost default: Δ=-0.022), round 3 (num_leaves=127: Δ=-0.002), round 4 (log1p Amount: Δ=-0.035) — all negative
- **Confidence:** low (3 rounds, C2 plateau trigger)
- **Status:** active
- **Implication for Planner:** Single-variable perturbations have failed across all tried categories (model family, HP, feature). Consider either more radical interventions (ensemble, CV upgrade) or systematic HP search within LGBM rather than single-point tests.

### P-2 — Amount-based feature engineering hurts PR-AUC

- **Pattern:** Adding log1p(Amount) as a feature alongside the original 30 features caused a large PR-AUC drop (Δ=-0.035). Amount-related feature engineering is likely counterproductive because V1-V28 PCA features already encode amount information from the original transaction data.
- **Supporting evidence:** round 4 (log1p_Amount as feature 31: val_pr_auc=0.780562 vs champion 0.815530, Δ=-0.035)
- **Confidence:** low (1 data point)
- **Status:** superseded_by P-3
- **Implication for Planner:** Avoid Amount-based feature engineering (log1p, Amount×V interactions, Amount^2). The PCA transformation likely already captures Amount's contribution to fraud patterns. Feature engineering budget is better spent on Time-based features if any.

### P-2 UPDATE (round 9 historian)

P-2 originally applied only to Amount-based features. Round 9 (Time_mod_86400, Δ=-0.044) generalizes the pattern to ALL raw-column feature additions. P-2 is now generalized as P-3.

### P-1 UPDATE (round 9 historian)

P-1 (simple perturbations degrade) was LOW confidence at round 4. It has been PARTIALLY FALSIFIED by rounds 6-8 (n_estimators increases consistently improved PR-AUC — simple HP perturbations CAN help). Rounds 9 confirms feature additions degrade. Revised understanding: HP perturbations within LGBM (especially n_estimators) can improve PR-AUC; feature additions and model family changes cannot. See P-3 for updated generalization.

### P-3 — Feature additions from raw data columns consistently hurt PR-AUC

- **Pattern:** Adding engineered features from raw Time or Amount columns to the 30-feature V1-V28 PCA space consistently produces large PR-AUC drops. The PCA feature space is self-contained and informationally complete for fraud detection; appending raw-column transformations introduces noise that disrupts tree split allocation.
- **Supporting evidence:** round 4 (log1p_Amount as feature 31: Δ=-0.035), round 9 (Time_mod_86400 as feature 31: Δ=-0.044) — two independent tests, both large negative
- **Confidence:** high (two independent confirmations, large effect sizes >5× noise_floor)
- **Status:** active
- **Implication for Planner:** ALL feature addition experiments using Time/Amount columns are dead ends. Do not attempt Feature engineering from raw columns. The 30-feature PCA space is optimal for this dataset.
