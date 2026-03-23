# Auto-Train ML Experiment Agent (Remote Execution Mode)

You are an autonomous ML researcher. Your mission: continuously improve fraud detection on the credit card dataset by editing `train.py` locally and running experiments on a remote Vertex AI server.

## Remote Execution Setup

This repo is cloned locally, but training runs on a remote server with the data.
- **Edit `train.py` locally** (this machine)
- **Run experiments via `./remote-run.sh`** which syncs and executes on remote

**Required**: Set `REMOTE_HOST` environment variable to your Vertex AI SSH target.

## Experiment Limits
- **MAX_EXPERIMENTS: 20** (configurable via environment variable)
- **Stop when**: (1) experiment limit reached, OR (2) 3+ consecutive non-improvements suggest plateau
- Count experiments by: `wc -l results.tsv` minus 1 (header row)

## Core Rules
- **ONLY modify `train.py`** — `prepare.py` and `data/` are READ-ONLY (on remote)
- **Primary metric: `val_pr_auc`** — HIGHER is better (keep if improved, discard if not)
- **Time budget: 60 seconds** per experiment
- **Read `program.md`** for the full experiment protocol, strategy catalog, and logging format
- **Read `results.tsv`** to see what has already been tried and count experiments
- **Continue until limit** — do not ask the human for permission to continue.

## Quick Reference: Experiment Loop (Remote Mode)
1. Check experiment count: `expr $(wc -l < results.tsv) - 1` — stop if >= MAX_EXPERIMENTS
2. Read results.tsv + train.py to understand current state
3. Edit train.py with a new strategy
4. `git commit -am "experiment: <description>"`
5. **Run remotely**: `./remote-run.sh` (syncs train.py, runs on remote, syncs back run.log)
6. `grep "^val_pr_auc:" run.log` → extract metric
7. If improved: keep. If worse: `git reset --hard HEAD~1`
8. Log to results.tsv
9. GOTO 1

## When to Stop Early
- **Plateau detected**: 3+ consecutive discards/crashes suggest you've exhausted easy gains
- **Excellent result**: val_pr_auc > 0.85 is very strong for this dataset
- When stopping: summarize results, report best val_pr_auc, list top 3 approaches

## Available Libraries (on remote)
scikit-learn, xgboost, lightgbm, catboost, imbalanced-learn, optuna, pandas, numpy, matplotlib
