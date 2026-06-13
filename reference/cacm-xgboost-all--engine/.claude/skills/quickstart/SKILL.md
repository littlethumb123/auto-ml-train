---
name: quickstart
description: >
  XGBoost Quickstart — guided 5-phase pipeline from zero to a validated model.
  Chains /onboard → feature pull → clean+select → /train → /validate → /log-exp.
  Use when the user says "/quickstart", "run the full pipeline", "start from scratch",
  "guided pipeline", "end to end", or after /onboard completes.
---

# XGBoost Quickstart

Five phases from zero to a validated model.

```
Phase 1  /onboard        Configure project.yaml           ~5 min (interactive)
Phase 2  pull            Fetch BQ features → Parquet      ~5–30 min (BQ query)
Phase 3  clean + select  Prune + rank features             ~10–20 min (local)
Phase 4  /train          Train final model → xgb.json       ~20–60 min (GPU)
Phase 5  /validate       Holdout evaluation + log          ~5–10 min
```

Accepts `--from <N>` to skip completed phases (e.g. `--from 3` to start at clean+select).

## Pre-check

```bash
git branch --show-current
```

If on `main` or `engine`: BLOCK — "Create an endpoint branch first: `git checkout -b endpoint/<name>`"

---

## Phase 1 — Onboard

If `project.yaml` is missing or `project.name` is empty:
- Invoke `/onboard`
- After completion, continue to Phase 2

If `project.yaml` already configured: print existing config and ask "Proceed with this config, or re-run `/onboard`?"

---

## Phase 2 — Pull Features

**Prerequisite check:**
```bash
pipenv run python -c "from xgboost_model import config; print('OK' if config.FEATURE_TABLE else 'NOT SET')"
```

If NOT SET: BLOCK — "Configure `data.feature_table` in project.yaml. Run Phase 1 first."

**Skip if parquet already exists:**
```bash
ls output/data/<tag>/features.parquet 2>/dev/null && echo "SKIP" || echo "RUN"
```

If RUN:
```bash
mkdir -p output/logs
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/1_pull_features.py --tag <tag> \
    2>&1 | tee output/logs/pull_<tag>_$(date +%Y%m%d_%H%M%S).log
```

**Phase 2 complete when:** `output/data/<tag>/features.parquet` exists.

---

## Phase 3 — Clean and Select Features

```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/2_clean_features.py --tag <tag> \
    2>&1 | tee output/logs/clean_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Then:
```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/3_select_features.py --tag <tag> \
    2>&1 | tee output/logs/select_<tag>_$(date +%Y%m%d_%H%M%S).log
```

Note the all-features AUC printed by `3_select_features.py`. If AUC < 0.55: WARN and offer to run `/diagnose` before proceeding to Phase 4.

**Phase 3 complete when:** `output/features/<tag>/selected_features_top*.txt` exists.

---

## Phase 4 — Train

Invoke `/train --tag <tag>` (skipping steps 1–3 since data and features are ready).

Or run directly:
```bash
PYTHONUNBUFFERED=1 pipenv run python3 -u scripts/4_train_model.py --tag <tag> \
    2>&1 | tee output/logs/train_<tag>_$(date +%Y%m%d_%H%M%S).log
```

**Phase 4 complete when:** `output/models/<tag>/*.json` files exist.

---

## Phase 5 — Validate and Log

Invoke `/validate --tag <tag>`.

After validation, invoke `/log-exp <tag>` to document the run.

---

## Completion

Print:
```
=== Quickstart Complete ===
Tag:     <tag>
Models:  output/models/<tag>/
Metrics: output/features/<tag>/threshold_metrics_<tag>.csv

Run '/validate --tag <tag>' to re-evaluate.
Run '/train' with a new tag to start a new experiment.
```
