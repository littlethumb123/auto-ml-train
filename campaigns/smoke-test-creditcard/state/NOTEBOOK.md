---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 3
last_updated: "2026-04-27"
---

<!-- Reviewer appends surprising-but-not-dead-end observations. -->

- **Round 1 (2026-04-26):** Setting scale_pos_weight=578 (correct class ratio) produced val_pr_auc=0.815530 — potentially lower than the spw=1 baseline cited by the Planner at 0.822. Since PR-AUC integrates over all thresholds and is inherently imbalance-aware, the class weighting may reduce probability calibration quality without helping ranking. This is not a dead-end for the model family, only for this specific imbalance-handling approach.

- **Round 2 (2026-04-27):** XGBoost with 200 estimators had lift_at_10=9.19 (slightly higher than LGBM's 8.99) despite lower PR-AUC (0.7936 vs 0.8155). This suggests XGBoost may rank extreme high-score transactions better even with a weaker overall probability estimate. Could be relevant if lift_at_10 were the primary metric, but PR-AUC is primary here.

- **Round 5 (2026-04-27):** min_child_samples=1 also showed lift_at_10=9.29 (highest in campaign) while PR-AUC dropped to 0.7938. Combined with round 2 (XGBoost lift_at_10=9.19, PR-AUC=0.7936), a pattern emerges: configurations that concentrate model attention on extreme scores (fewer samples per leaf, different family) improve lift_at_10 but hurt PR-AUC. The champion config (min_child_samples=5) appears to trade top-decile precision for better overall calibration.
