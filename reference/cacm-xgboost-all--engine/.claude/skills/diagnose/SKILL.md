---
name: diagnose
description: >
  XGBoost Diagnose — identify and fix poor AUC, feature leakage, class imbalance,
  training failures, or data quality problems. Use when the user says "training crashed",
  "AUC not improving", "something is wrong", "/diagnose", "debug my run",
  "metrics look off", "model isn't working", or after any unexpected training result.
---

# XGBoost Diagnosis

## Step 1 — Identify the Symptom

Ask (or infer from context):

| Symptom | Jump to |
|---------|---------|
| Script crashed / ImportError | Step 2 |
| AUC < 0.55 (all-features model) | Steps 3, 4 |
| AUC suspiciously high (> 0.95) | Step 4 |
| Train/holdout AUC gap > 0.08 | Steps 4, 5 |
| Model converges but Brier is poor | Step 6 |
| GPU OOM | Step 7 |

## Step 2 — Data Pull Check

```bash
ls -lh output/data/<tag>/features.parquet 2>/dev/null || echo "MISSING"
```

If missing: re-run step 1.

Check row count and class balance:
```python
import pandas as pd
df = pd.read_parquet(f"output/data/<tag>/features.parquet")
outcome_col = "<outcome_column>"
n = len(df)
pos = df[outcome_col].sum()
print(f"Rows: {n:,}  Positives: {pos:,}  Rate: {pos/n:.3%}")
```

If positive rate is 0 or 100%: the outcome join in `project.yaml` is likely wrong.

## Step 3 — Feature Leakage Check

```bash
grep -iE "outcome|stage|progress|impute|label|target" \
    output/features/<tag>/selected_features*.txt
```

Any match is a leakage risk. Cross-check against `features.exclude_patterns` in `project.yaml`.

Also check for near-future data:
```bash
grep -iE "future|next|post_index|after_index" \
    output/features/<tag>/selected_features*.txt
```

## Step 4 — Class Balance

```python
import pandas as pd
from xgboost_model import config

df = pd.read_parquet(f"output/data/<tag>/features.parquet")
pos = df[config.OUTCOME_COLUMN].sum()
neg = len(df) - pos
print(f"scale_pos_weight should be: {neg/pos:.1f}")
```

Compare against `training.scale_pos_weight` in `project.yaml`. Mismatch → retrain.

## Step 5 — Feature Selection Output

```bash
wc -l output/features/<tag>/selected_features*.txt
head -20 output/features/<tag>/selected_features*.txt
```

If top-N AUC << all-features AUC (from step 3 log): the most informative features may not
be in the top-N. Check `features.top_n` in `project.yaml` and increase if needed.

## Step 6 — Model Convergence

Read training log:
```bash
grep -E "AUC|auc|val_error|best_ntree" output/logs/train_<tag>_*.log | tail -20
```

Early stopping should kick in well before `n_estimators`. If it stops at iteration 1–2:
learning rate may be too high or data has issues.

## Step 7 — GPU OOM

```bash
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader
```

If OOM during training:
- Set `device: cpu` in `project.yaml` `training` section, or
- Reduce `features.top_n` to shrink the feature matrix

## Step 8 — Summary

After working through relevant steps, print:

```
=== Diagnosis Summary ===
Symptom:   [what the user reported]
Root cause: [identified issue or "unclear"]
Fix:        [specific action to take]
Next step:  [script/skill to run, or "re-run /train --tag <tag>"]
```
