# XGBoost Clinical Prediction Engine

## Quick Start
1. Create an endpoint branch: `git checkout -b endpoint/<your-endpoint>`
2. Run `/onboard` to configure project.yaml
3. Run `/train` to train a model
4. Run `/validate` to evaluate on holdout

## Branching Strategy

**`engine` branch** — this branch. Contains the generic XGBoost engine: feature cleaning,
training pipeline, skills, hooks, and docs. No project-specific config or data.

**Endpoint branches (`endpoint/<name>`)** are where all project work happens.
Create them off `engine`, e.g.:
- `endpoint/ckd4-progression`
- `endpoint/readmission-30day`

Merge `engine` into endpoint branches to pick up engine updates.

## Pipeline

Features and outcomes are pre-built by an external feature engineering module and
live in BigQuery. This engine pulls, cleans, selects, trains, and validates only.

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `scripts/1_pull_features.py` | Pull BQ feature + outcome tables → local Parquet |
| 2 | `scripts/2_clean_features.py` | Column pruning (nulls, near-constant) |
| 3 | `scripts/3_select_features.py` | XGBoost importance → top-N selection |
| 4 | `scripts/4_train_model.py` | Train final model on selected features |
| 5 | `scripts/5_validate_run.py` | Holdout evaluation: AUC, lift, SHAP |

## Quick Reference
| Key | Value |
|-----|-------|
| Config SSOT | `xgboost_model/config.py` + `project.yaml` |
| Run commands | `pipenv run python3 scripts/<script>` |
| Experiment log | `docs/EXPERIMENTATION.md` |

## Mandatory Rules

1. **Never** impute missing features with 0 — use forward-fill or leave as NaN (XGBoost handles natively)
2. Verify `scale_pos_weight` matches actual class ratio before training
3. Exclude leakage columns listed in `project.yaml` `features.exclude_patterns`
4. Log every experiment to `docs/EXPERIMENTATION.md`

## Response Style
- Default to brief: 1-2 sentences, no preambles or recaps
- After completing a task, print only the next step. Otherwise just "done"
- No summaries of what just changed — the user reads the diff
