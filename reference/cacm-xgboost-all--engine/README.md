# XGBoost Clinical Prediction Engine

> **Agent-first.** You describe the endpoint; Claude Code handles the rest. No script editing required.

**Validated with:** Claude Code · Sonnet 4.6 · High effort

---

## What this is

A reusable XGBoost pipeline for binary clinical prediction. You bring a BigQuery feature table and an outcome column — the engine pulls the data, selects features, trains a model, and evaluates it on a holdout set. All of that happens through four slash commands in Claude Code. You never need to open a script.

Each clinical endpoint lives on its own git branch, keeping configs, artifacts, and experiment logs fully isolated. Picking up a new endpoint is as simple as creating a branch and running `/onboard`.

For the full walkthrough — including what each command does under the hood and how to handle common situations — read the **[User Guide](docs/USER_GUIDE.md)**.

---

## Normal workflow

```
/session-init    →    /onboard    →    /train    →    /validate    →    /log-exp
```

| Command | What it does |
|---------|-------------|
| `/session-init` | Start here every session — shows project state and recommended next step |
| `/onboard` | Interviews you about your BQ tables and outcome, writes `project.yaml` |
| `/train` | Pulls data, cleans features, selects top-N, trains XGBoost, tags the run |
| `/validate` | Evaluates the tagged model on holdout — AUC, PR-AUC, lift, SHAP |
| `/log-exp` | Writes a structured entry to `docs/EXPERIMENTATION.md` |
| `/diagnose` | Inspects a failed run and explains what went wrong |

---

## Setup

```bash
git clone <repo-url>
cd cacm-xgboost-all-
pipenv install

git checkout engine   # all endpoint branches are created off engine
```

Open Claude Code and type `/session-init` — it will show the current state and prompt you to create an endpoint branch. Then `/onboard` configures your endpoint and you are ready to train.

---

## One branch per endpoint

Each clinical prediction target lives on its own branch:

```bash
git checkout -b endpoint/ckd4-progression
git checkout -b endpoint/readmission-30day
git checkout -b endpoint/cancer-treatment-se
```

Config, data artifacts, models, and experiment logs all live on the branch. To pick up engine improvements, run `git merge engine` from your endpoint branch.

---

## Data requirements

This engine expects a **wide-format BigQuery table** produced by the CACM coldstart pipeline:
- Temporal features named `{feature}_TS{1..N}` (one column per time step)
- Static features (no `_TS` suffix)
- A binary outcome column and a member ID column

Feature engineering happens upstream. This engine only trains and evaluates.

---

## Alternative methods and why they exist (naive only validated approach at this time)

Standard XGBoost binary classification treats every negative label the same, regardless of how long that member was actually observed. A member labeled `outcome=0` after 4 months is far less reliable evidence than one observed for 20 months. This engine exposes four approaches for handling that:

| Method | Approach | Trade-off |
|--------|----------|-----------|
| Naive binary | Ignore follow-up length | Simple but biased |
| Negative restriction | Exclude short-follow-up negatives | Loses sample size |
| Discrete-time survival | Person-period format (1 row/month) | Cleanest; ~18× more rows |
| IPCW | Weight by censoring probability | Full cohort; needs censoring model |

---

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | Full narrative guide — start here if you're new |
| [Quickstart](docs/QUICKSTART.md) | Condensed command reference |
| [Run Order](docs/RUN_ORDER.md) | Manual CLI reference (fallback) |
| [Pitfalls](docs/PITFALLS.md) | Common mistakes and how to avoid them |
| [Experiment Log](docs/EXPERIMENTATION.md) | Auto-populated run history |
