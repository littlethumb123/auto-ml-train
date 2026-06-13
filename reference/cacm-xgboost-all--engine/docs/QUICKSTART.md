# Quickstart

## 1. Setup

```bash
git clone <repo-url>
cd cacm-xgboost-all-
pipenv install
```

## 2. Create endpoint branch

```bash
git checkout -b endpoint/<your-endpoint>
```

## 3. Configure

**Option A — Claude Code (recommended):**
```
/onboard
```

**Option B — Manual:**
```bash
cp project.example.yaml project.yaml
# Edit project.yaml with your endpoint's BQ tables and outcome column
```

## 4. Train

```bash
# With Claude Code:
/train

# Manual: run scripts 1-5 in order (see RUN_ORDER.md)
```

## 5. Validate

```bash
/validate
# or
pipenv run python3 scripts/5_validate_run.py --tag v1 --shap
```

## Key Concepts

- **project.yaml** is the single source of truth for project-specific config
- **`--tag`** on every script names the run (e.g., `v1`, `exp_001`)
- **Censoring methods** are configured in `project.yaml` under `censoring.methods`
- **Endpoint branches** keep projects isolated; merge `engine` to pick up updates
- **Features and outcomes** are pre-built upstream — this engine only trains and validates
