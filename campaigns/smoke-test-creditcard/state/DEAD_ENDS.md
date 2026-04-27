---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 3
last_updated: "2026-04-27"
---

<!-- Reviewer appends entries on discard when pattern is structurally new. -->

- **Round 2 (A_model: XGBoost default HP):** XGBoost (n_est=200, lr=0.05, max_depth=6, spw=578) scored val_pr_auc=0.793611 vs LGBM champion 0.815530. Δ=-0.022. Note: XGBoost was tested at lower n_estimators (200 vs 600 for LGBM) due to timeout concerns — not a fully controlled comparison. XGBoost may still be viable with more tuning but default-param XGBoost is a dead end.
- **Round 3 (A_hp: num_leaves=127):** LightGBM with num_leaves=127 scored val_pr_auc=0.813307 vs champion 0.815530 (Δ=-0.002). Increasing num_leaves beyond 63 does not help PR-AUC — likely due to overfitting on the small fraud class (only ~295 fraud samples in train). num_leaves tuning upward is a dead end without additional regularization.
- **Round 4 (A_feature: log1p(Amount)):** Adding log1p(Amount) as feature 31 alongside Amount caused val_pr_auc to drop to 0.780562 (Δ=-0.035 vs champion 0.815530). Amount-based feature engineering is a dead end — likely because V1-V28 PCA features dominate fraud signal and Amount adds noise relative to them.
