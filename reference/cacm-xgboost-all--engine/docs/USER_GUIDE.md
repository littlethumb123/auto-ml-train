# User Guide

> **This is an agent-first repository.** You should not need to edit any script, config file, or SQL by hand. Every step in this guide is accomplished by typing a slash command in Claude Code and responding to its questions. The manual fallback exists for emergencies — it is not the intended workflow.

**Validated with:** Claude Code · Sonnet 4.6 · High effort

---

## Before you start

You need two things before running anything:

1. **A BigQuery feature table.** The engine is designed for wide-format tables with one row per member and a binary outcome column. CACM coldstart tables (temporal features named `{feature}_TS{1..N}`) are the validated path. Non-coldstart tables can be used, but have not been tested — expect to work through edge cases with the agent.
2. **GCP authentication.** Run this once per session if you haven't already:
   ```bash
   gcloud auth application-default login
   ```

You do not need to install packages manually. After cloning the repo, run `pipenv install` once and the environment is ready.

---

## Where to start every session

Before anything else — including starting a new endpoint — run:

```
/session-init
```

If you are on the `engine` branch with no endpoint yet, the agent will print the current engine state and prompt you to create an endpoint branch. If you are returning to an existing endpoint, it shows your last experiment and recommends the next step. Either way, it orients you in under ten seconds and tells you exactly what to type next.

---

## Starting a new endpoint

Every clinical prediction target lives on its own git branch, created off `engine`. This keeps your config, data, models, and experiment history completely isolated from other endpoints.

After `/session-init` prompts you, create your branch:

```bash
git checkout -b endpoint/<your-endpoint-name>
```

Use a short, descriptive name — `endpoint/ckd4-progression`, `endpoint/readmission-30day`, `endpoint/cancer-treatment-se`. You will see this name in your git history and experiment logs.

Once on your branch, type:

```
/onboard
```

The agent will interview you about your endpoint: which BigQuery tables to use, which column is the outcome, which column is the member ID, and a few other settings. It writes everything to `project.yaml` — the single source of truth for this endpoint. You do not edit `project.yaml` directly after this point unless the agent prompts you to verify something.

When `/onboard` finishes, it will confirm the BQ table is accessible and tell you the next step.

---

## Training your first model

With `project.yaml` configured, training is one command:

```
/train
```

The agent runs the full pipeline in sequence:

1. **Pulls data** from BigQuery to local Parquet files, tagged with a version label (e.g., `v1`).
2. **Cleans features** — drops columns with too many nulls or near-zero variance.
3. **Selects features** — trains a preliminary XGBoost model to rank importance, keeps the top-N.
4. **Trains the final model** on the selected feature set.

The entire run is tagged (default `v1`; subsequent runs get `v2`, `v3`, etc.). All artifacts land in `output/<subdir>/<tag>/`. You will not be asked to name files or move anything.

If anything fails, the agent will explain what went wrong and offer to fix it. You do not need to read stack traces.

---

## Evaluating your model

After training, run:

```
/validate
```

The agent evaluates the tagged model on the held-out test set and produces:

- **AUC-ROC** and **PR-AUC** — overall discrimination
- **Brier score** — calibration quality
- **Lift at 1%, 5%, 10%** — how much better than random at the top of the score distribution
- **ROC and PR curves** saved to `output/figures/<tag>/`
- **SHAP importance plot** showing which features drove predictions

The agent will print a summary table and flag anything that looks off (e.g., suspiciously high AUC that may indicate leakage, or poor calibration relative to class balance).

---

## Logging and comparing experiments

After validating, log the run:

```
/log-exp
```

The agent writes a structured entry to `docs/EXPERIMENTATION.md` — purpose, config, feature count, and all metrics. This file is your running record of every experiment on this branch.

When you want to compare a new approach against a previous one, just train again with a new tag. The log lets you see at a glance what changed and what improved.

---

## Picking up a previous session

If you are returning to a branch after time away, start with:

```
/session-init
```

This prints a one-screen summary: current branch, project config, last experiment tag and metrics, and what artifacts exist. It ends with a recommended next step. Use it any time you are unsure where you left off — it is designed to orient you in under ten seconds.

---

## When something goes wrong

If a run fails or produces unexpected results, run:

```
/diagnose
```

The agent inspects the most recent run's logs and artifacts, explains the failure in plain terms, and proposes a fix. In most cases you can apply the fix by responding "yes" or "do it" — you will not need to edit a file yourself.

Common situations the agent can self-correct:
- BQ authentication errors
- Schema mismatches between feature and outcome tables
- Leakage columns that slipped through `exclude_patterns`
- `scale_pos_weight` drifting from the actual class ratio after a data refresh

---

## Keeping your endpoint up to date

The `engine` branch receives improvements over time — bug fixes, new validation metrics, updated skills. To pull those into your endpoint:

```bash
git merge engine
```

Run this from your endpoint branch. The merge will never touch your `project.yaml`, `output/`, or `docs/EXPERIMENTATION.md`.

---

## Appendix: Manual fallback (emergencies only)

If Claude Code is unavailable, the pipeline can be run manually. This is not the intended workflow and should only be used when the agent is inaccessible.

```bash
# 0. Authenticate
gcloud auth application-default login

# 1. Pull features
pipenv run python3 scripts/1_pull_features.py --tag v1

# 2. Clean features
pipenv run python3 scripts/2_clean_features.py --tag v1

# 3. Select features
pipenv run python3 scripts/3_select_features.py --tag v1

# 4. Train
pipenv run python3 scripts/4_train_model.py --tag v1

# 5. Validate
pipenv run python3 scripts/5_validate_run.py --tag v1 --shap
```

All outputs land in `output/<subdir>/<tag>/`. See [RUN_ORDER.md](RUN_ORDER.md) for the full CLI reference including optional flags.

**Things to check manually that the agent handles automatically:**
- `scale_pos_weight` in `project.yaml` must equal `neg_count / pos_count` for your cohort. A wrong value silently degrades calibration.
- Every column that encodes the outcome must appear in `features.exclude_patterns`. An outcome table JOIN may add suffixed variants (e.g., `outcome_flag_1`) that a pattern like `"outcome_flag"` will miss — inspect column names after pulling.
- Never fill missing values with 0. XGBoost handles NaN natively; filling with 0 creates false signal for lab and sparse indicator features.
