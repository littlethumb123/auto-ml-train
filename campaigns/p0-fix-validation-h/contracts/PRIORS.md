---
schema_version: 1
problem_id: "creditcard-fraud"
last_campaign: "smoke-test-creditcard"
updated_at: "2026-06-20"
---

## Known good

- **LightGBM `n_estimators=600, lr=0.02, num_leaves=63, min_child_samples=5,
  scale_pos_weight=computed_class_ratio (~578)`** — round-1 baseline of the
  smoke-test-creditcard campaign produced **val_pr_auc ≈ 0.815, lift_at_10 ≈ 8.89,
  bootstrap CI [0.747, 0.889], SE=0.038**. This config is the canonical baseline
  for the credit-card fraud task.
- LightGBM `n_estimators=2500` in smoke-test-creditcard pushed val_pr_auc to
  0.830 (geometric-decay convergence pattern).
- XGBoost depth in [4, 6] is the canonical range for single-model runs.

## Known bad

- **LightGBM with `lr=0.05` + `n_estimators<=500` + `scale_pos_weight=578`**
  produces severe calibration failure (val_pr_auc < 0.10 despite ROC-AUC > 0.85).
  This combination is a confirmed dead-end across two campaigns
  (p0-fix-smoke initial attempt + p0-fix-validation round 1).
- **LightGBM with `n_estimators=100`** at `lr=0.02` is undertrained
  (val_pr_auc = 0.722 vs 0.816 baseline).
- `time_features` (Time_hour, Time_sin, Time_cos) are noise.
- SMOTE + scale_pos_weight double-counts imbalance.

## Known ceilings

- Single-holdout PR-AUC plateaus around 0.83 on the smoke-test split.
- Above this, CV-with-CI is needed to trust Δ.

## Recommended starting config (round 1)

For a fresh campaign on this dataset, start with the proven baseline above
(LightGBM n_est=600, lr=0.02). It establishes a strong calibrated baseline
that downstream rounds can iterate on.

## Open questions

- Does Historian's bottleneck diagnosis at round 2 (with historian_interval=2)
  correctly identify "convergence depth" vs "feature engineering" as the
  highest-ROI next direction?
