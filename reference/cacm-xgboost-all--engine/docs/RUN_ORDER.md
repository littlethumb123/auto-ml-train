# Run Order

## Prerequisites
- `project.yaml` configured (run `/onboard` or copy from `project.example.yaml`)
- BQ feature and outcome tables pre-built by the external feature engineering module
- GCP authentication: `gcloud auth application-default login`

## Pipeline

```bash
# 1. Pull features + outcomes from BQ to local Parquet
pipenv run python3 scripts/1_pull_features.py --tag v1
pipenv run python3 scripts/1_pull_features.py --tag v1 --dry-run  # preview query only

# 2. Clean features (column pruning: nulls + near-constant)
pipenv run python3 scripts/2_clean_features.py --tag v1
pipenv run python3 scripts/2_clean_features.py --tag v1 --write-table  # write to BQ

# 3. Feature selection (XGBoost importance -> top-N)
pipenv run python3 scripts/3_select_features.py --tag v1

# 4. Train final model(s) per censoring method
pipenv run python3 scripts/4_train_model.py --tag v1                    # all methods
pipenv run python3 scripts/4_train_model.py --tag v1 --method naive     # single method

# 5. Holdout validation
pipenv run python3 scripts/5_validate_run.py --tag v1
pipenv run python3 scripts/5_validate_run.py --tag v1 --shap            # with SHAP
```

## Output Artifacts

All outputs land in `output/<subdir>/<tag>/`:

| Directory | Contents |
|-----------|----------|
| `output/data/` | Parquet exports from BQ |
| `output/models/` | XGBoost `.json` model files |
| `output/features/` | Feature lists, importance CSVs, calibration |
| `output/figures/` | ROC/PR curves, SHAP plots |
