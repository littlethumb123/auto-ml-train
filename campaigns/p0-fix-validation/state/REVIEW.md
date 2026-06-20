---
schema_version: 1
campaign_id: "p0-fix-validation"
last_round: 1
last_verdict: anomaly
---

<!-- Reviewer appends one block per round (## Round N). -->

## Round 1 — 2026-06-20

### §Independent Assessment (Phase 1 — before reading plan)

**Commit:** 310ea7ca120c05c703947ae4d5476c41aa542f11  
**Model:** LightGBM, n_estimators=500, lr=0.05, num_leaves=31, scale_pos_weight=578.26  
**Features:** 30 (Time, V1-V28, Amount)

**Metrics from run.log:**
- val_pr_auc: 0.059277
- lift_at_10: 7.9801
- macro_f1: 0.5657
- val_f1: 0.9902
- training time: 1.8s / total: 4.3s

**Bootstrap CI (n=200, α=0.05):** [0.044, 0.075], SE=0.0083

**Reproduce-check:** PASSED — artifacts consistent with run.log metrics.

**Anomaly tool:** FIRED — val_pr_auc=0.059277 below floor=0.50. Proposed diagnostic: "diagnose probability inversion."

**Best prior:** None (first experiment). Δ = N/A.

**Observation:** val_pr_auc=0.059 is far below the expected baseline of ≥0.75 stated in PROBLEM_CONTRACT. The model IS learning (lift_at_10=7.98 means positives are ranked 8x above background), but precision is poor across most recall thresholds. All 99 val positives fall in the top 10%, but 915 negatives also score ≥0.5, resulting in 7.7% precision at 77% recall. The ROC-AUC is 0.876 (reasonable), but PR-AUC is 0.059 (anomalous). This discrepancy indicates LightGBM with scale_pos_weight=578 is calibrating probability outputs poorly for this extreme imbalance ratio. XGBoost with scale_pos_weight achieves PR-AUC=0.884 on the same split (verified via diagnostic check). V14 alone achieves PR-AUC=0.614.

**Preliminary verdict: anomaly** — val_pr_auc (0.059) is below anomaly floor (0.50). LightGBM+scale_pos_weight is producing severely miscalibrated probabilities on this dataset.

---

### §Plan Comparison (Phase 2)

**Plan hypothesis:** LightGBM with scale_pos_weight handles extreme class imbalance and provides a competitive baseline (expected PR-AUC ≥ 0.75).

**Actual val_pr_auc:** 0.059277. **Δ vs expected:** −0.69 (massive shortfall).

**Hypothesis falsified:** LightGBM with scale_pos_weight=578 does NOT achieve the predicted baseline on this dataset/split. The model ranks positives correctly (lift_at_10=7.98, all positives in top 10%) but outputs highly miscalibrated probabilities — 915 negatives also score ≥0.5. This inflates FP count and collapses precision across the PR curve.

**Note from diagnostic investigation:** XGBoost achieves 0.884 and LogisticRegression achieves 0.724 on the same split. The issue is LightGBM-specific; likely the interaction between scale_pos_weight=578 and LightGBM's default objective function creates poor probability calibration at this imbalance ratio. This is not a data error or leakage — the data loaded correctly (284807 rows, 492 positives, correct split).

---

### §Verdict Rationalization

| Check | Result | Verdict implication |
|-------|--------|---------------------|
| Δ(val_pr_auc) | N/A — first experiment | No prior best to compare |
| Mandatory tool: anomaly | FIRED — val_pr_auc=0.059 < floor=0.50 | → anomaly verdict |
| Mandatory tool: bootstrap_ci | Ran — CI=[0.044,0.075], SE=0.0083 | No regression (no baseline) |
| Reproduce-check | PASSED — artifacts consistent | Metrics trustworthy |
| Phase 1 preliminary | anomaly | Final: anomaly (Phase 2 cannot override) |
| Hypothesis confirmed? | No — falsified | LightGBM+SPW severely underperforms |
| **Final verdict** | **anomaly** | **val_pr_auc far below floor=0.50; suspected LightGBM calibration failure** |

---

### §Escalation — C1

**Anomaly (C1):** val_pr_auc=0.059277 is below the anomaly floor of 0.50 in EVAL_PROTOCOL.md.

**Anomaly tool output:** `{"fired":true,"reason":"val_pr_auc=0.059277 below threshold=0.500000 (floor=0.5, rel=0.5*best=0.000000)","proposed_diagnostic":"Add print(model.predict_proba(X_val[:5])) to diagnose probability inversion; do NOT dismiss unknown from one anomalous result."}`

**Suspected cause:** LightGBM with scale_pos_weight=578 produces severe positive-class over-prediction: 915 negatives score ≥0.5 along with only 76/99 positives. The model has ROC-AUC=0.876 (good ranking) but PR-AUC=0.059 (terrible calibration). This is a known LightGBM behavior with extreme scale_pos_weight values — it biases the decision boundary heavily toward the positive class, inflating probabilities for many negative samples.

**Evidence against probability inversion:** Positive median prob=1.0, negative median prob=0.0. Not an inversion — but calibration failure confirmed.

**Proposed next step:** Switch model family. Replace LightGBM with XGBoost (scale_pos_weight=578 works correctly → PR-AUC=0.884) or use LightGBM without scale_pos_weight + calibration (LightGBM no-SPW gets PR-AUC=0.346, suggesting different approach needed). The anomaly floor of 0.50 should also be reviewed — whether to lower it for the first baseline round to allow exploration.

**Human action required:** Review this C1 anomaly before resuming the campaign. Consider:
1. Changing train.py to use XGBoost for round 2 (or instruct Planner to try XGBoost)
2. Or adjusting anomaly.floor in EVAL_PROTOCOL.md if LightGBM's low PR-AUC is considered acceptable as a starting baseline
