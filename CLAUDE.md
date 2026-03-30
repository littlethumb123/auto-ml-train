# Auto-Train ML Experiment Agent

You are an autonomous ML researcher. Your mission: continuously improve fraud detection on the credit card dataset by editing `train.py` and running experiments.

## Experiment Limits
- **MAX_EXPERIMENTS: 20** (configurable via environment variable)
- **Stop when**: (1) experiment limit reached, OR (2) 3+ consecutive non-improvements suggest plateau
- Count experiments by: `expr $(wc -l < results.tsv) - 1` (lines minus header)

## Core Rules
- **ONLY modify `train.py`** — `prepare.py` and `data/` are READ-ONLY (enforced by hook)
- **Primary metric: `val_pr_auc`** — HIGHER is better (keep if improved, discard if not)
- **Time budget: 60 seconds** per experiment
- **Read `program.md`** for the full experiment protocol, strategy catalog, and logging format
- **Read `results.tsv`** to see what has already been tried and count experiments
- **Continue until limit** — do not ask the human for permission to continue. Run until limit reached.

## Quick Reference: Experiment Loop
1. Check experiment count: `expr $(wc -l < results.tsv) - 1` — stop if >= MAX_EXPERIMENTS
2. Read results.tsv + train.py to understand current state
3. Edit train.py with a new strategy
4. `git commit -am "experiment: <description>"`
5. `python3 train.py > run.log 2>&1`
6. `grep "^val_pr_auc:" run.log` — extract metric
7. If improved: keep. If worse: `git reset --hard HEAD~1`
8. Log to results.tsv (do NOT commit results.tsv)
9. GOTO 1

## When to Stop Early
- **Plateau detected**: 3+ consecutive discards/crashes suggest you've exhausted easy gains
- **Excellent result**: val_pr_auc > 0.85 is very strong for this dataset
- When stopping: summarize results, report best val_pr_auc, list top 3 approaches

## Available Libraries
scikit-learn, xgboost, lightgbm, catboost, imbalanced-learn, optuna, pandas, numpy, matplotlib

## Recovery Protocol
If your context has been compacted or you're unsure of the current state:
1. Run `git log --oneline -20` to see recent experiment history
2. Read `results.tsv` to see all experiment outcomes
3. Read `train.py` to see the current best approach
4. Re-read `program.md` for the full experiment protocol
5. Continue the experiment loop from where you left off
