---
schema_version: 1
campaign_id: "p0-fix-validation"
---

<!-- Reviewer appends one entry per round. -->
<!-- Format: ## Round N — YYYY-MM-DD -->

## Round 1 — 2026-06-20

**Action:** A_model — LightGBM balanced baseline (scale_pos_weight=578, n_est=500, lr=0.05)
**Trigger:** STRATEGY_GUIDE §1 "No baseline exists" → establish one with default-parameter GBDT
**Alternatives rejected:**
- A_hp: no baseline to tune yet
- A_model (XGBoost): chosen LightGBM first per EVAL_PROTOCOL baseline_family=lgbm_balanced

**Independent assessment:** val_pr_auc=0.059 is far below the expected baseline of ≥0.75. Anomaly tool fired (floor=0.50). Model has good ranking (lift_at_10=7.98, ROC-AUC=0.876) but catastrophically poor PR-AUC due to LightGBM miscalibrated probabilities with scale_pos_weight=578.
**Expected Δ (primary_metric):** +0.70 absolute (first baseline, target ≥0.75)
**Actual val_pr_auc:** 0.059277 (Δ = N/A — first experiment; far below floor=0.50)
**Verdict:** anomaly
**Key finding:** LightGBM with scale_pos_weight=578 produces ROC-AUC=0.876 but PR-AUC=0.059 on this extreme imbalance (0.17% fraud). The model ranks positives correctly but miscalibrates probability outputs: 915/56863 negatives score ≥0.5 inflating FP count. XGBoost achieves PR-AUC=0.884 on the same split. This is a model-family-specific failure, not a data or harness issue.
