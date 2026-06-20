---
schema_version: 1
campaign_id: "p0-fix-validation"
count: 0
last_updated: ""
---

<!-- Reviewer appends entries on discard when pattern is structurally new. -->
<!-- Format: - **Round N (action_type: short label):** description -->

- **Round 1 (A_model: LightGBM+scale_pos_weight):** LightGBM with scale_pos_weight=578 gives PR-AUC=0.059 (anomaly) despite ROC-AUC=0.876 on this 60/20/20 split. Probability calibration failure — 915/56863 negatives score ≥0.5. Do NOT use LightGBM+scale_pos_weight on this dataset. XGBoost achieves PR-AUC=0.884 with identical approach. If using LightGBM, must use calibration or objective='binary' with no scale_pos_weight.
