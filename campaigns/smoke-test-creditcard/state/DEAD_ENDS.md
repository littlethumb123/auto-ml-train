---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 1
last_updated: "2026-04-27"
---

<!-- Reviewer appends entries on discard when pattern is structurally new. -->

- **Round 2 (A_model: XGBoost default HP):** XGBoost (n_est=200, lr=0.05, max_depth=6, spw=578) scored val_pr_auc=0.793611 vs LGBM champion 0.815530. Δ=-0.022. Note: XGBoost was tested at lower n_estimators (200 vs 600 for LGBM) due to timeout concerns — not a fully controlled comparison. XGBoost may still be viable with more tuning but default-param XGBoost is a dead end.
