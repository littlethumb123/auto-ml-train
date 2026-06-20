---
schema_version: 1
campaign_id: "p0-fix-validation"
count: 0
last_updated: ""
---

<!-- Reviewer appends surprising-but-not-dead-end observations. -->
<!-- Format: - **Round N (YYYY-MM-DD):** description -->

- **Round 1 (2026-06-20):** LightGBM with scale_pos_weight=578 gets ROC-AUC=0.876 but PR-AUC=0.059 — the metric that matters for this campaign. XGBoost with identical hyperparameters gets PR-AUC=0.884, and even V14 alone gets PR-AUC=0.614. This is a calibration mismatch: LightGBM assigns high probabilities to ~1% of negatives (915 cases), while XGBoost is selective. For future LightGBM attempts: try without scale_pos_weight (gets PR-AUC=0.346 but at least not anomalous), or add `predict_proba` calibration (CalibratedClassifierCV) after fitting.
