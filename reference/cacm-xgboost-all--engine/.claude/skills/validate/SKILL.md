---
name: validate
description: >
  XGBoost Validate — evaluate a trained model on the holdout set. Reads AUC, PR-AUC,
  Brier, and lift metrics, generates ROC/PR curves and SHAP importance plot, and offers
  to log the run to EXPERIMENTATION.md. Use when the user says "validate", "evaluate",
  "run holdout", "/validate", "check metrics", "how did it do", or after /train completes.
---

# XGBoost Validation

## Step 1 — Check Artifacts

Verify model artifact exists for the given tag:
```bash
ls output/models/<tag>/xgb.json 2>/dev/null || echo "No model found"
```

If missing: BLOCK — "No trained model found for tag `<tag>`. Run `/train` first."

Ask user for `--tag` if not provided, or detect the latest tag:
```bash
ls -td output/models/*/ 2>/dev/null | head -1 | xargs basename
```

## Step 2 — Run Validation

```bash
mkdir -p output/logs
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/5_validate_run.py --tag <tag> --shap \
    2>&1 | tee output/logs/validate_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Omit `--shap` if the user wants a faster run (SHAP adds ~5 min).

For an RFE experiment that shares a source tag's data pull:
```bash
pipenv run python3 scripts/5_validate_run.py --tag <tag>_rfe --source-tag <tag> \
    --feature-list output/features/<tag>_rfe/selected_features_rfe.txt --shap
```

## Step 3 — Report Metrics

Read from `output/features/<tag>/threshold_metrics_<tag>.csv`:
```python
import pandas as pd
df = pd.read_csv(f"output/features/{tag}/threshold_metrics_{tag}.csv")
print(df.to_string(index=False))
```

Key output metrics:
```
AUC-ROC:  0.XXXX
AUC-PR:   0.XXXX
Brier:    0.XXX
Lift@1%:  XX.Xx
Lift@10%: X.Xx
```

Output files written to `output/figures/<tag>/`:
- `validation_roc_pr_<tag>.png` — ROC and PR curves
- `shap_importance.png` — top-20 features by mean |SHAP value|

## Step 4 — Interpretation Guide

| Metric | Concern threshold |
|--------|-------------------|
| AUC-ROC | < 0.65 — poor discrimination |
| PR-AUC  | < 2× prevalence — model barely beats random |
| Brier   | > 0.20 — poor calibration |
| Lift@1% | < 5× — top decile not actionable |
| Train/test AUC gap | > 0.08 — overfitting |

If AUC is unexpectedly high vs prior experiments, check for feature leakage:
```bash
grep -iE "outcome|stage|progress|impute" output/features/<tag>/selected_features*.txt
```

## Step 5 — Compare with Prior Experiments

Read the last 3 entries from `docs/EXPERIMENTATION.md` and note any delta in AUC-ROC.

## Step 6 — Offer to Log

Ask: "Log this run to EXPERIMENTATION.md? (runs `/log-exp <tag>`)"
- Yes → invoke `/log-exp <tag>`
- No → print "Run `/log-exp <tag>` when ready to document this experiment."
