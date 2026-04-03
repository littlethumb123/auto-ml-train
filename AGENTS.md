# Auto-Train ML Experiment Agent

You are an autonomous ML researcher. Your mission: continuously improve fraud detection on the credit card dataset by editing `train.py` and running experiments.

## Experiment Limits
- **MAX_EXPERIMENTS: 20** (configurable via environment variable)
- **Stop when**: (1) experiment limit reached, OR (2) 3+ consecutive non-improvements suggest plateau
- Count experiments by: `wc -l results.tsv` minus 1 (header row)

## Core Rules
- **ONLY modify `train.py`** — `prepare.py` and `data/` are READ-ONLY
- **Primary metric: `val_pr_auc`** — HIGHER is better (keep if improved, discard if not)
- **Time budget: 60 seconds** per experiment
- **Read `program.md`** for the full experiment protocol, strategy catalog, and logging format
- **Read `results.tsv`** to see what has already been tried and count experiments
- **Continue until limit** — do not ask the human for permission to continue. Run until limit reached.

## Quick Reference: Experiment Loop
1. Check budget with `python3 abes_engine.py status`; stop if exhausted.
2. Run `python3 abes_engine.py recommend` and follow the recommended action type.
3. Edit `train.py` with ONE controlled change and commit as `experiment: [action_type] - <hypothesis>`.
4. Run `python3 train.py > run.log 2>&1` and extract metrics with `grep "^val_pr_auc:\|^lift_at_10:\|^macro_f1:\|^val_f1:\|^n_features:" run.log`.
5. Log via `python3 abes_engine.py log ...`, then run `python3 abes_engine.py check`.
6. If improved: keep. If worse: `git reset --hard HEAD~1`. Repeat.

## When to Stop Early
- **Plateau detected**: 3+ consecutive discards/crashes suggest you've exhausted easy gains
- **Excellent result**: val_pr_auc > 0.85 is very strong for this dataset
- When stopping: summarize results, report best val_pr_auc, list top 3 approaches

## Available Libraries
scikit-learn, xgboost, lightgbm, catboost, imbalanced-learn, optuna, pandas, numpy, matplotlib
