---
name: train
description: >
  XGBoost Train — run the full training pipeline with pre-flight checks and experiment
  logging. Covers pull → clean → select → train. Produces one model per tag.
  Use when the user says "train", "train a model", "/train", "run the pipeline",
  "fit model", "start training", or after /onboard completes.
---

# XGBoost Training

## Step 0 — Data Verify

Check that the data for this tag is ready before committing GPU time.

```bash
ls output/data/<tag>/features.parquet 2>/dev/null && echo "PASS" || echo "MISSING"
```

- **PASS** (parquet exists) → continue to Step 1
- **MISSING** (no parquet) → offer to run step 1 now, or BLOCK if `project.yaml` is not configured

Also check that `project.yaml` has `data.feature_table` set:
```bash
pipenv run python -c "from xgboost_model import config; print('feature_table:', config.FEATURE_TABLE or 'NOT SET')"
```

If `feature_table` is empty: BLOCK — "Configure `data.feature_table` in `project.yaml` first. Run `/onboard`."

## Step 1 — Pre-flight

1. Verify not on `main` or `engine` branch — BLOCK if so
2. Check GPU:
   ```bash
   nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader 2>/dev/null || echo "No GPU — will use CPU"
   ```
3. Check for zombie processes:
   ```bash
   ps aux | grep -E "4_train_model\.py|3_select_features\.py" | grep -v grep
   ```
   If found: warn and offer to kill

## Step 2 — Gather Parameters

Ask: "What tag for this run? (e.g. `v1`, `exp_001`)"

Suggest `v<N>` incrementing from the latest tag already in `output/models/`.

## Step 3 — Pull Features

Skip if `output/data/<tag>/features.parquet` already exists.

```bash
mkdir -p output/logs
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/1_pull_features.py --tag <tag> \
    2>&1 | tee output/logs/pull_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Expected time: ~5–30 min depending on table size. Watch for BQ auth errors.

## Step 4 — Clean Features

```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/2_clean_features.py --tag <tag> \
    2>&1 | tee -a output/logs/pull_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Expected: drops ~30–60% of columns. Watch output for unusually high drop rates.

## Step 5 — Select Features

```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/3_select_features.py --tag <tag> \
    2>&1 | tee output/logs/select_<tag>_$(date +%Y%m%d_%H%M%S).log
```

This step does the 60/20/20 train/val/test split and saves member IDs to
`output/features/<tag>/member_split.json`. **All downstream steps load this file —
the split is fixed here for the lifetime of the tag.**

Reports AUC on **val** (never test). This is a diagnostic baseline — test is reserved for step 7.

## Step 5b — Hyperparameter Tuning (optional)

If the user wants HPO, or if `tuning.n_trials` is set:

```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/3b_tune_hyperparams.py --tag <tag> \
    2>&1 | tee output/logs/hpo_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Cross-val runs within **train (60%) only**. Val sanity check printed at end.
Saves `output/features/<tag>/best_params.json` — picked up automatically by step 6.

For a parallel RFE experiment sharing the same data pull:
```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/3c_rfe.py --tag rfe_<tag> --source-tag <tag> \
    2>&1 | tee output/logs/rfe_<tag>_$(date +%Y%m%d_%H%M%S).log
```
RFECV also runs within **train (60%) only**. Uses the same member_split.json.

## Step 6 — Train Model

```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/4_train_model.py --tag <tag> \
    2>&1 | tee output/logs/train_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Trains on **train+val (80%)** — the full trainval set after test was carved off.
Saves `output/models/<tag>/xgb.json`. Expected time: ~20–60 min (GPU).

For experiments using a different feature list or data source (e.g. RFE experiment):
```bash
pipenv run python3 scripts/4_train_model.py --tag rfe_<tag> --source-tag <tag> \
    --feature-list output/features/rfe_<tag>/selected_features_rfe.txt
```

## Step 7 — Post-training

After training completes:
1. Run `/validate --tag <tag>` for final test-set evaluation + SHAP
2. The `log_experiment.sh` hook writes a stub to `docs/EXPERIMENTATION.md`
3. Run `/commit-exp <tag>` to stage and commit experiment artifacts

## Guardrails

- Never train on `main` or `engine` branch
- Always set `PYTHONUNBUFFERED=1` for real-time log output
- If AUC from all-features model (step 5) < 0.55, run `/diagnose` before proceeding
