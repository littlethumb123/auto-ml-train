---
name: onboard
description: >
  XGBoost Onboard — configure project.yaml for a new clinical endpoint by interviewing
  the user about their BQ tables, outcome column, ID column, and split fractions.
  Validates BQ table access after writing. Links into /quickstart after completion.
  Use when the user says "new endpoint", "configure project.yaml", "/onboard",
  "set up my endpoint", "I have a new project", or when project.yaml is missing or empty.
---

# XGBoost Onboarding

Configure `project.yaml` for a new clinical endpoint.

## Step 1 — Check Branch

```bash
git branch --show-current
```

If on `main` or `engine`, BLOCK:
```
You're on the '<branch>' branch. Create an endpoint branch first:
  git checkout -b endpoint/<your-endpoint-slug>
The endpoint/ prefix is required.
```

## Step 2 — Check Existing Config

Read `project.yaml` if it exists. If `project.name` is non-empty, ask:
"project.yaml already configured for `<name>`. Update it or start fresh?"

## Step 3 — Interview

Ask these questions (skip any already clear from context):

1. **Endpoint name**: "What clinical outcome are you predicting?" → `project.name`
2. **Prefix**: "Short artifact prefix for output file names (e.g. `xgb_ckd4`, `xgb_readmit`):" → `project.prefix`
3. **Owner**: "Your NTID (for experiment logs):" → `project.owner`
4. **GCP project**: "GCP project?" (default: `anbc-hcb-dev`) → `data.gcp_project`
5. **Feature table**: "Fully-qualified BQ feature table? (`project.dataset.table`)" → `data.feature_table`
6. **Outcome table**: "Is the outcome column in the feature table, or a separate outcome table?"
   - Same table → set `data.outcome_table` same as `data.feature_table`
   - Separate → "Outcome table FQN?" → `data.outcome_table`
7. **Outcome column**: "Binary outcome column name?" (default: `outcome_flag`) → `data.outcome_column`
8. **ID column**: "Member/patient ID column?" (default: `individual_id`) → `data.id_column`
9. **Train/val/test split fractions**: "What train/val/test split do you want? Default is 60/20/20."
   - Confirm or accept defaults: `test_size: 0.2` (held out until step 5), `val_size: 0.2` (used during feature selection and HPO)
   - Explain: "The test set is never touched until step 5 — it's your final sanity check. The val set is used to evaluate feature selection and HPO quality during development."
   - → `training.test_size`, `training.val_size`
10. **Leakage columns**: "Any columns to exclude from model features? (e.g. columns that encode the outcome). Press Enter to use defaults." → append to `features.exclude_patterns`

## Step 4 — Write project.yaml

Copy `project.example.yaml` as template and populate with user's answers. Write to `project.yaml`.

## Step 5 — Verify BQ Table Access

```python
from google.cloud import bigquery
from xgboost_model import config

client = bigquery.Client(project=config.GCP_PROJECT)

print("Checking feature table...")
r = next(client.query(f"SELECT COUNT(*) as n FROM `{config.FEATURE_TABLE}` LIMIT 1").result())
print(f"  Feature table: {r.n:,} rows — OK")

if config.OUTCOME_TABLE != config.FEATURE_TABLE:
    print("Checking outcome table...")
    r2 = next(client.query(f"SELECT COUNT(*) as n FROM `{config.OUTCOME_TABLE}` LIMIT 1").result())
    print(f"  Outcome table: {r2.n:,} rows — OK")

print("Checking outcome column...")
r3 = next(client.query(
    f"SELECT COUNTIF(`{config.OUTCOME_COLUMN}` IS NOT NULL) as n FROM `{config.OUTCOME_TABLE}` LIMIT 1"
).result())
print(f"  Outcome column accessible — OK")
```

If a table fails:
- Permission error → suggest `gcloud auth application-default login` then retry
- Table not found → ask user to verify the FQN

## Step 6 — Summary

Print:
```
Endpoint configured: [name]
Branch:    [current branch]

Data:
  Feature table:  [table] — [N] rows
  Outcome table:  [table]
  Outcome column: [column]

Split:  train=[1-test-val]% / val=[val]% / test=[test]%
```

## Step 7 — Suggest Next Step

Ask: "Run `/quickstart` for the full guided pipeline, or run step 1 manually?"
- `/quickstart` → invoke it
- Manual → print "Run: `pipenv run python3 scripts/1_pull_features.py --tag v1`"
