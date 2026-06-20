---
schema_version: 2
campaign_id: "p0-fix-validation"
round: 1
planner_invocation_at: "2026-06-20T13:15:06Z"
action_type: "A_model"
hypothesis: "LightGBM with scale_pos_weight handles extreme class imbalance and provides a competitive baseline for credit card fraud PR-AUC (expected >= 0.75)"
expected_effect_size: 0.70
base_commit: "ac666955c3c9b89e9244a6afec1b63c38df9ee07"
model_family: "lgbm"
n_features: 30
touches_helpers: false
helpers_declared: []
assumptions_tested: []
escalation: null
---

## 1. Context

**Round:** 1 of 5  
**Budget used:** 0/5  
**Best so far:** None (no experiments run yet)  
**Last verdict:** N/A  
**Active dead-ends:** None  

No baseline exists. This is the first experiment in a 5-round validation campaign for the credit card fraud task. Extreme class imbalance (0.173% fraud, ~492/284807 positives).

## 2. Evidence from memory

### Summary

No prior results (results.tsv empty). No dead ends. PRIORS.md confirms LightGBM is competitive on this dataset after fixing is_unbalance bug, and scale_pos_weight alone is sufficient for tree models. EVAL_PROTOCOL.acceptance_threshold.baseline_family = "lgbm_balanced".

### UCB1 Scores (EXPERIMENT_TREE.json phase: diversify)

```
Candidate 1: A_model LightGBM balanced  (UCB1 = inf, untried — mandatory baseline)
Candidate 2: A_model XGBoost default    (UCB1 = inf, untried — second model family)
Candidate 3: A_hp Optuna on LightGBM   (UCB1 = N/A — no baseline to tune yet)
Selection: A_model LightGBM (baseline_family from EVAL_PROTOCOL, mandatory first)
```

### Rationalization table

| Candidate | Action | UCB1 | Expected Δ | Dead-end? | Assumption risk | Selection rationale |
|-----------|--------|------|------------|-----------|-----------------|---------------------|
| 1 | A_model (LightGBM balanced) | inf | +0.70 abs (first baseline) | No | None | Mandatory — no baseline; EVAL_PROTOCOL baseline_family=lgbm_balanced |
| 2 | A_model (XGBoost default) | inf | +0.70 abs (first baseline) | No | None | Skip: need LightGBM baseline per spec before comparing families |
| 3 | A_hp (Optuna LightGBM) | N/A — no baseline | +0.005 delta | No | Depends on champion | Skip: must establish baseline first |
| **Selected** | **A_model (LightGBM balanced)** | inf | | | | **Baseline_family from EVAL_PROTOCOL; mandatory first experiment in diversify phase** |

### Pre-selection reasoning

Evidence trigger: "No baseline exists" → establish one with default-parameter GBDT.  
PRIORS.md confirms LightGBM competitive on creditcard. EVAL_PROTOCOL baseline_family = "lgbm_balanced".  
scale_pos_weight = n_negative / n_positive ≈ 578 addresses extreme imbalance.  
No templates needed (lgbm baseline uses standard API directly).  
**ROI prior (STRATEGY_GUIDE §2):** A_model in early campaign with no prior baseline = mandatory; expected absolute val_pr_auc ≥ 0.75 per PROBLEM_CONTRACT.

### Historian context

- **Bottleneck diagnosis:** N/A — no STRATEGY_MEMO.md (first round)
- **Critical assumptions:** None flagged
- **Alignment:** First baseline; no divergence possible

## 3. Plan

1. Load `campaigns/p0-fix-validation/data/creditcard.csv`.
2. Split 60/20/20 stratified by Class, seed=42 (fixed per DATA_CONTRACT).
3. Features: all columns except Class → [Time, V1-V28, Amount] = 30 features.
4. Compute `scale_pos_weight = len(y_train[y_train==0]) / len(y_train[y_train==1])`.
5. Train LightGBM:
   - n_estimators=500, learning_rate=0.05, num_leaves=31
   - scale_pos_weight=computed, random_state=42, n_jobs=-1
6. Predict on val set; compute val_pr_auc (sklearn average_precision_score), lift_at_10, macro_f1, val_f1.
7. Save `artifacts/y_val_true.npy` and `artifacts/y_val_prob.npy`.
8. Print `METRICS: val_pr_auc=<v> lift_at_10=<v> macro_f1=<v> val_f1=<v>` for log parser.
9. Enforce 60s hard timeout via signal.alarm(60).

## 4. Helpers

None. `touches_helpers: false`.

## 5. How this differs

First experiment — no prior baseline to compare against. This establishes the floor for all subsequent rounds. Uses scale_pos_weight (not SMOTE) per PRIORS.md guidance and STRATEGY_GUIDE §3.4.

## 6. Escalation

No escalation. `escalation: null`. Budget is healthy (0/5 used). No plateau, no contract change needed.
