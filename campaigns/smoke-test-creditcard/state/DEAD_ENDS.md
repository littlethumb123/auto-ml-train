---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 5
last_updated: "2026-04-27 (round 9 discard)"
---

<!-- Reviewer appends entries on discard when pattern is structurally new. -->

- **Round 2 (A_model: XGBoost default HP):** XGBoost (n_est=200, lr=0.05, max_depth=6, spw=578) scored val_pr_auc=0.793611 vs LGBM champion 0.815530. Δ=-0.022. Note: XGBoost was tested at lower n_estimators (200 vs 600 for LGBM) due to timeout concerns — not a fully controlled comparison. XGBoost may still be viable with more tuning but default-param XGBoost is a dead end.
- **Round 3 (A_hp: num_leaves=127):** LightGBM with num_leaves=127 scored val_pr_auc=0.813307 vs champion 0.815530 (Δ=-0.002). Increasing num_leaves beyond 63 does not help PR-AUC — likely due to overfitting on the small fraud class (only ~295 fraud samples in train). num_leaves tuning upward is a dead end without additional regularization.
- **Round 4 (A_feature: log1p(Amount)):** Adding log1p(Amount) as feature 31 alongside Amount caused val_pr_auc to drop to 0.780562 (Δ=-0.035 vs champion 0.815530). Amount-based feature engineering is a dead end — likely because V1-V28 PCA features dominate fraud signal and Amount adds noise relative to them.
- **Round 5 (A_hp: min_child_samples=1):** Reducing min_child_samples from 5 to 1 scored val_pr_auc=0.793780 (Δ=-0.022). While lift_at_10 improved (9.29 vs 8.99), PR-AUC dropped significantly. min_child_samples reduction is a dead end for PR-AUC optimization.
- **Round 9 (A_feature: Time_mod_86400):** Adding Time_mod_86400 (Time % 86400, time-of-day proxy) as feature 31 caused val_pr_auc to drop from 0.829948 to 0.786073 (Δ=-0.044). This is the second feature addition to catastrophically hurt PR-AUC (cf. round 4 log1p(Amount) Δ=-0.035). The 30-feature V1-V28 PCA space is self-contained; adding raw time/amount features introduces noise. ALL feature additions from raw data columns are a dead end for this dataset.
