---
schema_version: 1
campaign_id: "p0-fix-validation-h"
count: 2
last_updated: "2026-06-20"
---

<!-- Historian appends entries during periodic/C2 runs. -->
<!-- Format: ### P-<seq> — <pattern name> -->

### P-1 — Computed scale_pos_weight is robust across gradient-boosting families and HP configurations

- **Pattern:** On this dataset (creditcard.csv, seed=42, 60/20/20 split), computing scale_pos_weight as n_neg/n_pos (~578) produces well-calibrated probability outputs with no calibration failure across any tested gradient-boosting family or hyperparameter configuration.
- **Supporting evidence:** R1 (LGBM default HP, val_pr_auc=0.8155, no calibration failure); R2 (XGBoost default HP, 0.8144, no calibration failure); R3 (LGBM Optuna HP num_leaves=81, 0.8050, no calibration failure); R4 (LGBM n_est=2000, 0.8297, no calibration failure) — 4 consecutive rounds confirming.
- **Confidence:** high
- **Status:** active
- **Implication for Planner:** scale_pos_weight=computed (n_neg/n_pos) is safe to use as-is for any new LightGBM or XGBoost experiment on this dataset. No manual tuning or calibration post-processing needed. SMOTE+SPW double-count remains a dead-end per PRIORS.md.

### P-2 — n_estimators is the dominant HP lever for LightGBM val_pr_auc; other HP changes without n_est increase produce neutral-to-negative returns

- **Pattern:** On this dataset, increasing LightGBM n_estimators while holding lr/num_leaves/min_child_samples constant reliably improves val_pr_auc. Changing other HP (num_leaves, min_child_samples) via Optuna or grid search without controlling n_est produces performance degradation even at higher n_est values, because the proxy ranking at low n_est doesn't transfer to the final n_est configuration.
- **Supporting evidence:** R1 (n_est=600, default HP → 0.8155 baseline); R3 (n_est=1000 with Optuna-changed HP num_leaves=81 → 0.8050, Δ=−0.0105 vs baseline despite larger n_est); R4 (n_est=2000, default HP unchanged → 0.8297, Δ=+0.0142 vs baseline).
- **Confidence:** low
- **Status:** active
- **Implication for Planner:** If running A_hp on LightGBM, change n_estimators first as a single-variable experiment. Only tune lr/num_leaves once n_est ceiling is established. Avoid proxy-based Optuna search (proxy n_est << final n_est) — it produces misleading HP rankings on this dataset.
