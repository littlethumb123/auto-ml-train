# Auto-ML Experiment Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous, never-stop ML experimentation agent that continuously improves fraud detection on the credit card dataset — modeled after Karpathy's autoresearch pattern — running via GitHub Copilot CLI.

**Architecture:** Three-file system mirroring autoresearch: `prepare.py` (FROZEN evaluation contract with data loading, stratified splits, and PR-AUC metric), `train.py` (MUTABLE single file the agent edits — preprocessing, feature engineering, model selection, stacking), and `program.md` (agent instructions with experiment loop protocol). Git-as-state-machine for experiment tracking. Copilot CLI `agentStop` hook forces the never-stop loop.

**Tech Stack:** Python 3.10, scikit-learn 1.7.2, XGBoost 3.2.0, LightGBM 4.6.0, CatBoost 1.2.10, imbalanced-learn, Optuna 3.6.2, pandas, numpy. GitHub Copilot CLI (autopilot mode) as the agent runtime.

---

## Copilot CLI Limitation Mitigations

The system is specifically designed to compensate for Copilot CLI's limitations compared to Claude Code:

| Limitation | Impact | Mitigation in Design |
|---|---|---|
| **Context compaction at 95% token usage** | Agent loses earlier conversation context during long sessions | `results.tsv` serves as persistent memory; `program.md` includes recovery protocol; `AGENTS.md` re-loaded on every turn |
| **No Ralph Loop (persistent loop plugin)** | Agent may think the task is "complete" and stop | `agentStop` hook with `{"decision":"block"}` forces continuation; `AGENTS.md` and `program.md` both emphasize NEVER STOP |
| **`--yolo` may still pause (known issue #1652)** | Occasional confirmation prompts could block overnight runs | Combine `--yolo --no-ask-user`; `preToolUse` hook auto-allows critical tools |
| **Premium request costs per continuation** | Each agent "turn" costs premium requests | Efficient experiment design; agent analyzes results.tsv before proposing, avoiding blind exploration |
| **Default model may be less capable than Claude Opus** | Agent may struggle with complex ML reasoning | `program.md` includes explicit strategy catalog with code examples; train.py has clear structural template; decisions are simple (higher PR-AUC = keep) |
| **Session crashes/disconnects** | Long sessions can be interrupted | `copilot --continue` to resume; results.tsv and git log persist on disk; `program.md` has reconnection protocol |
| **No CLAUDE.md support** | Copilot uses different instruction files | Create both `AGENTS.md` (auto-loaded) and `.github/copilot-instructions.md` (auto-loaded) |
| **No native file streaming** | Can't watch training output in real-time | Redirect to run.log + grep, identical to autoresearch pattern |

---

## File Structure

```
auto_train/
├── prepare.py                          # CREATE: FROZEN evaluation contract
│                                       #   Data loading, stratified splits, PR-AUC evaluation
│                                       #   Constants (TIME_BUDGET, RANDOM_SEED, etc.)
│                                       #   ~180 lines
├── train.py                            # CREATE: MUTABLE experiment file (baseline)
│                                       #   LogisticRegression + StandardScaler baseline
│                                       #   Structured for agent to understand and modify
│                                       #   ~100 lines
├── program.md                          # CREATE: Agent instructions
│                                       #   Setup protocol, experiment loop, strategy catalog
│                                       #   Recovery protocol for context compaction
│                                       #   NEVER STOP directive
│                                       #   ~200 lines
├── requirements.txt                    # CREATE: Python dependencies
├── AGENTS.md                           # CREATE: Copilot CLI auto-loaded instructions
│                                       #   Compact version of program.md for persistent context
├── .github/
│   ├── copilot-instructions.md         # CREATE: Copilot CLI repo-level instructions
│   └── hooks/
│       ├── experiment-loop.json        # CREATE: Hook config for never-stop + auto-allow
│       └── scripts/
│           ├── force-continue.sh       # CREATE: agentStop hook — forces continuation
│           └── auto-allow.sh           # CREATE: preToolUse hook — auto-allows tools
├── analysis.ipynb                      # CREATE: Results visualization notebook
├── data/
│   └── creditcard.csv                  # EXISTS: Source dataset (read-only)
└── docs/
    └── ...                             # EXISTS
```

---

## Task 1: Create `requirements.txt`

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Create requirements.txt with all dependencies**

```txt
# Auto-ML Experiment Agent Dependencies
# These are FIXED — the agent cannot install new packages.
scikit-learn>=1.5
xgboost>=3.0
lightgbm>=4.0
catboost>=1.2
imbalanced-learn>=0.12
optuna>=3.6
pandas>=2.0
numpy>=1.26
matplotlib>=3.5
```

- [ ] **Step 2: Install imbalanced-learn (the only missing dependency)**

Run: `pip install imbalanced-learn`
Expected: Successful installation

- [ ] **Step 3: Verify all imports work**

Run:
```bash
python3 -c "
import sklearn, xgboost, lightgbm, catboost, imblearn, optuna, pandas, numpy, matplotlib
print('All imports OK')
print(f'sklearn={sklearn.__version__}, xgb={xgboost.__version__}, lgbm={lightgbm.__version__}')
print(f'catboost={catboost.__version__}, imblearn={imblearn.__version__}, optuna={optuna.__version__}')
print(f'matplotlib={matplotlib.__version__}')
"
```
Expected: `All imports OK` with version numbers

- [ ] **Step 4: Commit**

```bash
cd /home/jupyter/Thinkubator/auto_train
git init -b main
git add requirements.txt
git commit -m "feat: add requirements.txt with ML dependencies"
```

---

## Task 2: Create `prepare.py` (Frozen Evaluation Contract)

This is the most critical file — it defines the rules of the game. Once created, it must NEVER be modified by the agent.

**Files:**
- Create: `prepare.py`

- [ ] **Step 1: Create prepare.py with complete implementation**

```python
"""
Frozen evaluation and data infrastructure for auto_train experiments.

DO NOT MODIFY this file. It contains the fixed evaluation contract.
The agent may only read from this module — never write to it.

Provides:
    - Constants (TIME_BUDGET, RANDOM_SEED, splits, etc.)
    - load_data() — loads and cleans the credit card dataset
    - get_splits() — returns stratified train/val/test splits (fixed seed)
    - get_feature_names() — returns feature column names
    - evaluate(model, X_val, y_val) — computes PR-AUC + secondary metrics
    - print_summary(metrics, training_time, total_time, n_features, description)

Usage:
    from prepare import get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    f1_score,
    precision_score,
    recall_score,
)

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants (fixed, do not modify)
# ---------------------------------------------------------------------------

TIME_BUDGET = 60            # seconds per experiment
RANDOM_SEED = 42            # reproducibility seed for all splits
TEST_SIZE = 0.20            # fraction held out for final test
VAL_SIZE = 0.20             # fraction held out for validation (from remainder)
TARGET_COL = "Class"
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "creditcard.csv")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    """Load and clean the credit card fraud dataset.

    Returns a DataFrame with all columns. The target column is 'Class'
    (0 = legitimate, 1 = fraud). Rows with missing values are dropped.
    """
    df = pd.read_csv(DATA_PATH)
    df[TARGET_COL] = df[TARGET_COL].astype(float).astype(int)
    # Dataset has no missing values; dropna is a safety net
    df = df.dropna().reset_index(drop=True)
    return df


def get_feature_names():
    """Return the list of feature column names (everything except target)."""
    df = load_data()
    return [c for c in df.columns if c != TARGET_COL]


def get_splits():
    """Return stratified train/val/test splits with a fixed random seed.

    The splits are IDENTICAL across all experiments. This is the equivalent
    of autoresearch's pinned validation shard — every experiment is evaluated
    on the exact same validation and test data.

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
        (all as pandas DataFrames / Series)
    """
    df = load_data()
    X = df.drop(columns=[TARGET_COL])
    y = df[TARGET_COL]

    # Split 1: separate test set (20%)
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    # Split 2: separate validation from training (20% of remaining = 25% of temp)
    val_fraction = VAL_SIZE / (1.0 - TEST_SIZE)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_fraction,
        random_state=RANDOM_SEED,
        stratify=y_temp,
    )

    return X_train, X_val, X_test, y_train, y_val, y_test


# ---------------------------------------------------------------------------
# Evaluation (DO NOT CHANGE — this is the fixed metric)
# ---------------------------------------------------------------------------

def evaluate(model, X_val, y_val):
    """Compute evaluation metrics for a fitted model.

    Primary metric: val_pr_auc (Precision-Recall AUC / Average Precision)
    This is the ONLY metric used for keep/discard decisions.
    Secondary metrics are logged for analysis but do not affect decisions.

    The model must implement either predict_proba() or decision_function().

    Args:
        model: a fitted scikit-learn compatible estimator (or pipeline)
        X_val: validation feature matrix
        y_val: validation target vector

    Returns:
        dict with keys: val_pr_auc, val_roc_auc, val_f1, val_precision, val_recall
    """
    # predict_proba is preferred; decision_function works for ranking metrics
    # (PR-AUC and ROC-AUC are rank-based so raw scores are fine).
    # If using SVM or other models without predict_proba, consider wrapping
    # in CalibratedClassifierCV for better-calibrated probabilities.
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_val)[:, 1]
    elif hasattr(model, "decision_function"):
        y_prob = model.decision_function(X_val)
    else:
        raise ValueError(
            "Model must implement predict_proba() or decision_function(). "
            "Wrap it in CalibratedClassifierCV if needed."
        )

    y_pred = model.predict(X_val)

    return {
        "val_pr_auc": float(average_precision_score(y_val, y_prob)),
        "val_roc_auc": float(roc_auc_score(y_val, y_prob)),
        "val_f1": float(f1_score(y_val, y_pred, zero_division=0)),
        "val_precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "val_recall": float(recall_score(y_val, y_pred, zero_division=0)),
    }


def print_summary(metrics, training_time, total_time, n_features, description=""):
    """Print a structured summary block for machine parsing.

    This output format mirrors autoresearch's summary block.
    The agent extracts metrics using grep.
    """
    print("---")
    print(f"val_pr_auc:       {metrics['val_pr_auc']:.6f}")
    print(f"val_roc_auc:      {metrics['val_roc_auc']:.6f}")
    print(f"val_f1:           {metrics['val_f1']:.6f}")
    print(f"val_precision:    {metrics['val_precision']:.6f}")
    print(f"val_recall:       {metrics['val_recall']:.6f}")
    print(f"training_seconds: {training_time:.1f}")
    print(f"total_seconds:    {total_time:.1f}")
    print(f"n_features:       {n_features}")
    print(f"description:      {description}")
    print("---")


# ---------------------------------------------------------------------------
# Main (data verification)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Data path: {DATA_PATH}")
    df = load_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Target distribution:\n{df[TARGET_COL].value_counts().sort_index()}")
    print(f"Fraud rate: {df[TARGET_COL].mean():.4%}")
    print(f"Missing values: {df.isnull().sum().sum()}")

    X_train, X_val, X_test, y_train, y_val, y_test = get_splits()
    print(f"\nSplits:")
    print(f"  Train: {X_train.shape[0]:,} samples ({y_train.mean():.4%} fraud)")
    print(f"  Val:   {X_val.shape[0]:,} samples ({y_val.mean():.4%} fraud)")
    print(f"  Test:  {X_test.shape[0]:,} samples ({y_test.mean():.4%} fraud)")
    print(f"  Features: {X_train.shape[1]}")
    print("\nReady for experiments.")
```

- [ ] **Step 2: Run prepare.py to verify data loading and splits**

Run: `cd /home/jupyter/Thinkubator/auto_train && python3 prepare.py`

Expected output (approximate — exact numbers depend on current CSV size):
```
Dataset shape: (284807, 31)
Target distribution:
0    284315
1       492
Fraud rate: 0.1727%
Splits:
  Train: 182436 samples (0.1727% fraud)
  Val:   45610 samples (0.1727% fraud)
  Test:  56761 samples (0.1727% fraud)
  Features: 30
Ready for experiments.
```

- [ ] **Step 3: Verify evaluate() works with a dummy model**

Run:
```bash
cd /home/jupyter/Thinkubator/auto_train && python3 -c "
from prepare import get_splits, evaluate
from sklearn.linear_model import LogisticRegression
X_train, X_val, X_test, y_train, y_val, y_test = get_splits()
model = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
model.fit(X_train, y_train)
metrics = evaluate(model, X_val, y_val)
for k, v in metrics.items():
    print(f'{k}: {v:.6f}')
"
```
Expected: All metrics print without error, val_pr_auc should be > 0.5

- [ ] **Step 4: Commit**

```bash
git add prepare.py
git commit -m "feat: add prepare.py — frozen evaluation contract with PR-AUC metric"
```

---

## Task 3: Create Baseline `train.py` (Mutable Experiment File)

The baseline is intentionally simple — LogisticRegression with StandardScaler and class_weight='balanced'. This gives the agent a clear starting point and a structured template to modify.

**Files:**
- Create: `train.py`

- [ ] **Step 1: Create train.py with baseline implementation**

```python
"""
Auto-train experiment script. Single-file ML pipeline.
This is the ONLY file the agent edits.

Everything is fair game: preprocessing, feature engineering, model selection,
class imbalance handling, stacking, hyperparameters. The only constraint is
that the code runs without crashing within the 60-second time budget.

Usage: python3 train.py
"""

import os
import signal
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from prepare import (
    TIME_BUDGET,
    RANDOM_SEED,
    get_splits,
    evaluate,
    print_summary,
)

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# ---------------------------------------------------------------------------
# Time budget enforcement (hard kill if exceeded)
# ---------------------------------------------------------------------------

HARD_TIMEOUT = TIME_BUDGET + 30  # 90s hard limit (60s budget + 30s for eval/overhead)

def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)

if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ---------------------------------------------------------------------------
# Configuration (edit freely)
# ---------------------------------------------------------------------------

DESCRIPTION = "baseline: LogisticRegression + StandardScaler + balanced weights"

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_pipeline():
    """Build and return the ML pipeline.

    The agent can replace this entire function with any sklearn-compatible
    pipeline, ensemble, or custom model. The only requirement is that the
    returned object supports .fit(X, y) and .predict_proba(X) or
    .decision_function(X).
    """
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            random_state=RANDOM_SEED,
            max_iter=1000,
            class_weight="balanced",
        )),
    ])
    return pipeline

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

t_start = time.time()

# Load data (from frozen prepare.py)
X_train, X_val, X_test, y_train, y_val, y_test = get_splits()

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]}")
print(f"Fraud rate (train): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

# Build pipeline
pipeline = build_pipeline()

# Train
t_train_start = time.time()
pipeline.fit(X_train, y_train)
training_time = time.time() - t_train_start

# Soft check: warn if training alone exceeded budget
if training_time > TIME_BUDGET:
    print(f"WARNING: training took {training_time:.1f}s (budget: {TIME_BUDGET}s)")

# Evaluate on validation set (this is what determines keep/discard)
metrics = evaluate(pipeline, X_val, y_val)

total_time = time.time() - t_start

# Print structured summary (agent parses this via grep)
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
```

- [ ] **Step 2: Run baseline to establish initial metrics**

Run: `cd /home/jupyter/Thinkubator/auto_train && python3 train.py`

Expected: Completes in < 60s, prints structured summary with val_pr_auc

- [ ] **Step 3: Verify metrics can be extracted via grep (the agent's primary parsing method)**

Run:
```bash
cd /home/jupyter/Thinkubator/auto_train
python3 train.py > run.log 2>&1
grep "^val_pr_auc:\|^val_f1:\|^n_features:" run.log
```

Expected: Three lines showing val_pr_auc, val_f1, and n_features with numeric values. No test-set metrics should appear (test metrics are intentionally excluded from agent-visible output to prevent leakage).

- [ ] **Step 4: Commit**

```bash
git add train.py
git commit -m "feat: add train.py — baseline LogisticRegression pipeline"
```

---

## Task 4: Create `program.md` (Agent Instructions)

This is the "agent program" — the equivalent of Karpathy's program.md, adapted for classical ML and Copilot CLI. It must be self-contained because Copilot CLI's context compaction may lose earlier conversation history.

**Files:**
- Create: `program.md`

- [ ] **Step 1: Create program.md with complete agent instructions**

```markdown
# auto_train

This is an experiment to have an AI agent do autonomous ML research on fraud detection.

## Setup

To set up a new experiment session:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar22`). The branch `autotrain/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b autotrain/<tag>` from current main.
3. **Read the in-scope files**: The repo is small. Read these files for full context:
   - `program.md` — these instructions (you are reading this now).
   - `prepare.py` — fixed constants, data loading, evaluation. **Do not modify.**
   - `train.py` — the file you modify. Preprocessing, feature engineering, model, stacking.
4. **Verify data exists**: Check that `data/creditcard.csv` exists.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row.
6. **Confirm and go**: Confirm setup looks good, then start experimenting.

## The Dataset

Credit card fraud detection. ~285K rows, 30 features (Time, V1-V28 PCA components, Amount), binary target (Class: 0=legitimate, 1=fraud). Extreme class imbalance: ~0.17% fraud rate (492 fraud out of 284,807 transactions). 

Key properties:
- V1-V28 are already PCA-transformed (no original feature names available)
- Time is seconds elapsed from first transaction
- Amount is transaction amount
- Class is the target (0 or 1)

## Experimentation

Each experiment runs a Python ML pipeline. The training script runs within a **fixed time budget of 60 seconds**. You launch it as: `python3 train.py`.

**What you CAN do:**
- Modify `train.py` — this is the only file you edit. Everything is fair game: preprocessing, feature engineering, feature selection, dimensionality reduction, class imbalance handling, model selection, ensembling, stacking, hyperparameters, etc.

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It contains the fixed evaluation, data loading, splits, and constants.
- Modify `data/creditcard.csv`. It is read-only.
- Install new packages. You can only use what's in `requirements.txt`: scikit-learn, xgboost, lightgbm, catboost, imbalanced-learn, optuna, pandas, numpy.
- Modify the evaluation function. `evaluate()` in `prepare.py` is the ground truth metric.

**The goal is simple: get the highest val_pr_auc.** Since the time budget is fixed, everything is fair game: change the model, the preprocessing, the features, the class balancing strategy. The only constraints are that the code runs without crashing and finishes within the time budget.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement that adds ugly complexity is not worth it. Conversely, removing something and getting equal or better results is a great outcome — that's a simplification win. When evaluating whether to keep a change, weigh the complexity cost against the improvement magnitude. A 0.001 val_pr_auc improvement that adds 30 lines of hacky code? Probably not worth it. A 0.001 improvement from deleting code? Definitely keep. Equal performance with much simpler code? Keep.

**The first run**: Your very first run should always be to establish the baseline, so run train.py as-is.

## Output format

Once the script finishes it prints a summary like this:

```
---
val_pr_auc:       0.750000
val_roc_auc:      0.970000
val_f1:           0.800000
val_precision:    0.850000
val_recall:       0.750000
training_seconds: 5.2
total_seconds:    8.1
n_features:       30
description:      baseline: LogisticRegression + StandardScaler + balanced weights
```

Extract the key metric from the log file:

```
grep "^val_pr_auc:" run.log
```

## Logging results

When an experiment is done, log it to `results.tsv` (tab-separated, NOT comma-separated).

The TSV has a header row and 6 columns:

```
commit	val_pr_auc	val_f1	status	n_features	description
```

1. git commit hash (short, 7 chars)
2. val_pr_auc achieved (e.g. 0.750000) — use 0.000000 for crashes
3. val_f1 achieved (e.g. 0.800000) — use 0.000000 for crashes
4. status: `keep`, `discard`, or `crash`
5. n_features used (integer) — use 0 for crashes
6. short text description of what this experiment tried

Example:

```
commit	val_pr_auc	val_f1	status	n_features	description
a1b2c3d	0.750000	0.800000	keep	30	baseline: LogisticRegression + StandardScaler
b2c3d4e	0.780000	0.820000	keep	30	XGBoost with scale_pos_weight
c3d4e5f	0.770000	0.810000	discard	45	added polynomial features (no improvement)
d4e5f6g	0.000000	0.000000	crash	0	CatBoost OOM with 100 features
```

## The experiment loop

The experiment runs on a dedicated branch (e.g. `autotrain/mar22`).

LOOP FOREVER:

1. Look at `results.tsv` to see what has been tried and what worked.
2. Look at the current `train.py` to understand the current best approach.
3. Think about what to try next. Consult the **Strategy Catalog** below for ideas.
4. Edit `train.py` with your experimental idea.
5. `git commit -am "experiment: <brief description>"`
6. Run the experiment: `python3 train.py > run.log 2>&1`
7. Read out the results: `grep "^val_pr_auc:\|^val_f1:\|^n_features:" run.log`
8. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the Python stack trace and attempt a fix. If you can't fix it after 2 attempts, give up on this idea.
9. Record the results in results.tsv (do NOT commit results.tsv — leave it untracked by git)
10. If val_pr_auc improved (higher), you "advance" the branch, keeping the git commit.
11. If val_pr_auc is equal or worse, you git reset back to where you started: `git reset --hard HEAD~1`

## Strategy Catalog

Here are categories of strategies to explore, roughly ordered by expected impact:

### 1. Model Selection (try these first)
- XGBoost with `scale_pos_weight` = (n_neg / n_pos)
- LightGBM with `is_unbalance=True`
- CatBoost with `auto_class_weights='Balanced'`
- RandomForestClassifier with `class_weight='balanced'`
- GradientBoostingClassifier
- ExtraTreesClassifier
- SVM with RBF kernel (may be slow on ~285K rows — subsample if needed)

### 2. Class Imbalance Handling
- SMOTE (from imblearn) in a pipeline with `imblearn.pipeline.Pipeline`
- ADASYN oversampling
- RandomUnderSampler to downsample majority
- SMOTEENN (combined over+under sampling)
- Adjust class_weight or scale_pos_weight parameters
- Cost-sensitive learning (sample_weight in fit)

### 3. Feature Engineering
- Log-transform Amount: `np.log1p(Amount)`
- Bin Time into hour-of-day or time-windows
- Interaction features between top-importance V features
- Polynomial features on a subset of top features (careful with dimensionality)
- Statistical aggregations (rolling stats on Time-sorted data)

### 4. Feature Selection
- SelectKBest with mutual_info_classif
- Recursive Feature Elimination (RFE)
- L1-based feature selection (LogisticRegression with penalty='l1')
- Drop low-importance features from tree-based model's feature_importances_

### 5. Dimensionality Reduction
- PCA (note: V1-V28 are already PCA, but further reduction might help)
- Truncated SVD

### 6. Ensemble / Stacking
- VotingClassifier (soft voting) combining top 2-3 models
- StackingClassifier with diverse base learners
- BaggingClassifier wrapping the best single model
- Two-stage: first model filters, second model refines

### 7. Hyperparameter Tuning
- Use Optuna for Bayesian optimization within the time budget
- Grid search on a small parameter grid
- Random search on a broader grid
- Focus on: learning_rate, max_depth, n_estimators, subsample, colsample_bytree

### 8. Preprocessing Variations
- RobustScaler instead of StandardScaler (better with outliers)
- MinMaxScaler
- QuantileTransformer (Gaussian output)
- PowerTransformer (Yeo-Johnson)
- No scaling (tree models don't need it)

### 9. Advanced Strategies
- Calibrated probabilities: CalibratedClassifierCV
- Threshold optimization: find optimal decision threshold on validation set
- Two-stage pipeline: anomaly detection (IsolationForest) + classifier
- Custom sample weights based on Amount or Time

## Recovery Protocol

If you notice your context has been compacted or you're unsure of the current state:

1. Run `git log --oneline -20` to see recent experiment history
2. Read `results.tsv` to see all experiment outcomes
3. Read `train.py` to see the current best approach
4. Re-read `program.md` (this file) for the full experiment protocol
5. Continue the experiment loop from where you left off

## Timeout

Each experiment should take <60 seconds for training + a few seconds overhead. If a run exceeds 120 seconds total, kill it (`Ctrl+C` or timeout) and treat it as a crash.

## Crashes

If a run crashes (OOM, bug, import error, etc.), use your judgment:
- If it's a typo or easy fix, fix and re-run (up to 2 attempts).
- If the idea itself is broken (OOM, incompatible API, etc.), log as crash and move on.

## NEVER STOP

Once the experiment loop has begun, do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep or away. You are autonomous. If you run out of ideas, think harder — re-read the Strategy Catalog, try combining previous near-misses, try more radical approaches. The loop runs until the human interrupts you, period.

As an example: at ~60 seconds per experiment you can run ~60/hour, ~480 overnight. The user wakes up to a results.tsv full of experiments.
```

- [ ] **Step 2: Verify program.md is readable and complete**

Run: `wc -l /home/jupyter/Thinkubator/auto_train/program.md`
Expected: ~150-200 lines

- [ ] **Step 3: Commit**

```bash
git add program.md
git commit -m "feat: add program.md — agent instructions with experiment loop"
```

---

## Task 5: Create Copilot CLI Integration Files

These files make the system work specifically with GitHub Copilot CLI — the `agentStop` hook is the critical "never stop" mechanism.

**Files:**
- Create: `AGENTS.md`
- Create: `.github/copilot-instructions.md`
- Create: `.github/hooks/experiment-loop.json`
- Create: `.github/hooks/scripts/force-continue.sh`

- [ ] **Step 1: Create AGENTS.md (auto-loaded by Copilot CLI)**

This file is automatically loaded into every Copilot CLI prompt in this repo. It must be compact (stays in context even after compaction) and reinforce the core loop.

```markdown
# Auto-Train ML Experiment Agent

You are an autonomous ML researcher. Your mission: continuously improve fraud detection on the credit card dataset by editing `train.py` and running experiments.

## Core Rules
- **ONLY modify `train.py`** — `prepare.py` and `data/` are READ-ONLY
- **Primary metric: `val_pr_auc`** — HIGHER is better (keep if improved, discard if not)
- **Time budget: 60 seconds** per experiment
- **Read `program.md`** for the full experiment protocol, strategy catalog, and logging format
- **Read `results.tsv`** to see what has already been tried
- **NEVER STOP** — do not ask the human for permission to continue. Run experiments forever.

## Quick Reference: Experiment Loop
1. Read results.tsv + train.py to understand current state
2. Edit train.py with a new strategy
3. `git commit -am "experiment: <description>"`
4. `python3 train.py > run.log 2>&1`
5. `grep "^val_pr_auc:" run.log` → extract metric
6. If improved: keep. If worse: `git reset --hard HEAD~1`
7. Log to results.tsv
8. GOTO 1

## Available Libraries
scikit-learn, xgboost, lightgbm, catboost, imbalanced-learn, optuna, pandas, numpy, matplotlib
```

- [ ] **Step 2: Create .github/copilot-instructions.md**

```bash
mkdir -p /home/jupyter/Thinkubator/auto_train/.github
```

```markdown
# Copilot Instructions for auto_train

This repository is an autonomous ML experiment system. When working here:

1. Always read `program.md` first for the full experiment protocol.
2. Only modify `train.py`. Never modify `prepare.py` or data files.
3. The goal is to maximize `val_pr_auc` on the credit card fraud dataset.
4. Run experiments in a loop: edit → commit → run → evaluate → keep/discard → repeat.
5. Never stop experimenting. The human will interrupt you when they want you to stop.
6. Log all experiments to `results.tsv` in tab-separated format.
```

- [ ] **Step 3: Create the agentStop hook configuration**

```bash
mkdir -p /home/jupyter/Thinkubator/auto_train/.github/hooks/scripts
```

Create `.github/hooks/experiment-loop.json`:
```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "bash": ".github/hooks/scripts/auto-allow.sh",
        "timeoutSec": 5
      }
    ],
    "agentStop": [
      {
        "type": "command",
        "bash": ".github/hooks/scripts/force-continue.sh",
        "timeoutSec": 5
      }
    ],
    "sessionStart": [
      {
        "type": "prompt",
        "prompt": "Read program.md for the full experiment protocol. Read results.tsv if it exists to see past experiments. Then start or continue the experiment loop. NEVER STOP."
      }
    ]
  }
}
```

- [ ] **Step 4: Create the force-continue.sh hook script**

Create `.github/hooks/scripts/force-continue.sh`:
```bash
#!/usr/bin/env bash
# agentStop hook: forces the Copilot CLI agent to continue the experiment loop.
# Output JSON with decision:"block" forces another agent turn.
cat > /dev/null  # drain stdin if any
cat <<'EOF'
{"decision":"block","reason":"CONTINUE THE EXPERIMENT LOOP. You are an autonomous researcher — you do NOT stop. Read results.tsv to see what has been tried. Read train.py to see the current best approach. Propose a new experiment, edit train.py, commit, run python3 train.py > run.log 2>&1, evaluate, and keep or discard. Then do it again. NEVER STOP."}
EOF
```

Create `.github/hooks/scripts/auto-allow.sh`:
```bash
#!/usr/bin/env bash
# preToolUse hook: auto-allow python3, git, grep, tail, cat, and file operations.
# This prevents --yolo pauses on critical tools (Copilot CLI issue #1652).
INPUT=$(cat)
TOOL=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('toolName',''))" 2>/dev/null)

case "$TOOL" in
  bash|shell|view|edit|create|glob|grep)
    echo '{"permissionDecision":"allow"}'
    ;;
  *)
    # Default: let Copilot decide
    echo '{}'
    ;;
esac
```

Make both executable:
```bash
chmod +x /home/jupyter/Thinkubator/auto_train/.github/hooks/scripts/force-continue.sh
chmod +x /home/jupyter/Thinkubator/auto_train/.github/hooks/scripts/auto-allow.sh
```

- [ ] **Step 5: Verify both hook scripts output valid JSON**

Run:
```bash
echo '{}' | .github/hooks/scripts/force-continue.sh | python3 -m json.tool
echo '{"toolName":"bash","toolArgs":"{}"}' | .github/hooks/scripts/auto-allow.sh | python3 -m json.tool
```

Expected: force-continue outputs `decision: "block"`, auto-allow outputs `permissionDecision: "allow"`

- [ ] **Step 6: Verify Copilot CLI version supports agentStop hooks**

Run: `copilot version`

The `agentStop` hook with `decision:"block"` requires Copilot CLI GA (v1.0+, Feb 2026). If your version does not support `agentStop`, the hook will be silently ignored and the agent may stop. In that case, rely on `--max-autopilot-continues` set to a high number (e.g., 500) and the NEVER STOP directive in `AGENTS.md` / `program.md`. See: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#hooks-reference

- [ ] **Step 7: Create .gitignore**

```
# Auto-train experiment artifacts
run.log
results.tsv
__pycache__/
*.pyc
.github/hooks/logs/

# IDE
.vscode/
.idea/
*.swp
```

- [ ] **Step 8: Commit all Copilot CLI integration files**

```bash
git add AGENTS.md .github/ .gitignore
git commit -m "feat: add Copilot CLI integration — AGENTS.md, hooks, instructions"
```

---

## Task 6: Create `analysis.ipynb` (Results Visualization)

A simple notebook for the human to review experiment results.

**Files:**
- Create: `analysis.ipynb`

- [ ] **Step 1: Create analysis.ipynb with visualization code**

The notebook should contain these cells:

**Cell 1 (markdown):**
```markdown
# Auto-Train Experiment Results
Visualization of autonomous ML experiment outcomes.
```

**Cell 2 (code):**
```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("results.tsv", sep="\t")
print(f"Total experiments: {len(df)}")
print(f"Kept: {(df['status'] == 'keep').sum()}")
print(f"Discarded: {(df['status'] == 'discard').sum()}")
print(f"Crashed: {(df['status'] == 'crash').sum()}")
df.head(20)
```

**Cell 3 (code):**
```python
valid = df[df["status"] != "crash"].copy()
valid["experiment_num"] = range(len(valid))

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# PR-AUC over time
colors = valid["status"].map({"keep": "green", "discard": "red"}).fillna("gray")
axes[0].scatter(valid["experiment_num"], valid["val_pr_auc"], c=colors, alpha=0.7, s=30)
kept = valid[valid["status"] == "keep"]
axes[0].plot(kept["experiment_num"], kept["val_pr_auc"], "g-", alpha=0.5, label="kept trajectory")
axes[0].set_xlabel("Experiment #")
axes[0].set_ylabel("val_pr_auc")
axes[0].set_title("PR-AUC Over Experiments (green=keep, red=discard)")
axes[0].legend()

# F1 over time
axes[1].scatter(valid["experiment_num"], valid["val_f1"], c=colors, alpha=0.7, s=30)
axes[1].plot(kept["experiment_num"], kept["val_f1"], "g-", alpha=0.5, label="kept trajectory")
axes[1].set_xlabel("Experiment #")
axes[1].set_ylabel("val_f1")
axes[1].set_title("F1 Over Experiments")
axes[1].legend()

plt.tight_layout()
plt.savefig("progress.png", dpi=150, bbox_inches="tight")
plt.show()
```

**Cell 4 (code):**
```python
# Best results
print("=== TOP 10 EXPERIMENTS BY PR-AUC ===")
top = valid.nlargest(10, "val_pr_auc")[["commit", "val_pr_auc", "val_f1", "n_features", "description"]]
print(top.to_string(index=False))
```

- [ ] **Step 2: Commit**

```bash
git add analysis.ipynb
git commit -m "feat: add analysis.ipynb for experiment result visualization"
```

---

## Task 7: End-to-End Verification

Run the complete system end-to-end to verify everything works before handing off to the agent.

**Files:**
- No new files

- [ ] **Step 1: Run prepare.py to verify data infrastructure**

Run: `cd /home/jupyter/Thinkubator/auto_train && python3 prepare.py`

Expected: Dataset stats printed, splits verified, no errors.

- [ ] **Step 2: Run baseline train.py and capture output**

Run: `cd /home/jupyter/Thinkubator/auto_train && python3 train.py > run.log 2>&1 && cat run.log`

Expected: Structured summary with val_pr_auc > 0.

- [ ] **Step 3: Verify metric extraction via grep**

Run: `grep "^val_pr_auc:" run.log`

Expected: Single line like `val_pr_auc:       0.XXXXXX`

- [ ] **Step 4: Verify agentStop hook outputs valid JSON**

Run: `.github/hooks/scripts/force-continue.sh | python3 -m json.tool`

Expected: Valid JSON with decision and reason fields.

- [ ] **Step 5: Simulate the git workflow**

```bash
cd /home/jupyter/Thinkubator/auto_train
git checkout -b autotrain/test
echo -e "commit\tval_pr_auc\tval_f1\tstatus\tn_features\tdescription" > results.tsv
BASELINE_PR_AUC=$(grep "^val_pr_auc:" run.log | awk '{print $2}')
BASELINE_F1=$(grep "^val_f1:" run.log | awk '{print $2}')
COMMIT=$(git rev-parse --short HEAD)
echo -e "${COMMIT}\t${BASELINE_PR_AUC}\t${BASELINE_F1}\tkeep\t30\tbaseline" >> results.tsv
cat results.tsv
git checkout main
git branch -D autotrain/test
```

Expected: results.tsv has header + baseline row with actual metrics.

- [ ] **Step 6: Final commit of any remaining files**

```bash
git add -A
git status
# If there are uncommitted files:
git commit -m "feat: complete auto-train experiment system setup"
```

---

## Task 8: Launch Instructions

These are the commands to actually start the autonomous agent. NOT part of the implementation — this is documentation for the human operator.

**Files:**
- No new files (instructions only)

- [ ] **Step 1: Document the launch commands**

### Launching with GitHub Copilot CLI

**Prerequisites:**
```bash
# Install Copilot CLI (if not already installed)
npm install -g @github/copilot

# Authenticate
copilot login

# Install missing dependency
cd /home/jupyter/Thinkubator/auto_train
pip install imbalanced-learn
```

**Option A — Fully Autonomous (Recommended for Overnight Runs):**
```bash
cd /home/jupyter/Thinkubator/auto_train
copilot --autopilot \
        --yolo \
        --no-ask-user \
        -p "Read program.md and start the autonomous ML experiment loop. Do the setup first (create branch, run baseline, initialize results.tsv), then loop forever."
```

**Option B — Interactive Start, Then Autopilot:**
```bash
cd /home/jupyter/Thinkubator/auto_train
copilot --yolo
```
Then in the interactive session:
1. Type: `Read program.md and let's set up a new experiment run`
2. After setup completes, press `Shift+Tab` to switch to autopilot mode
3. Type: `Start the experiment loop. NEVER STOP.`
4. Walk away

**Option C — With Continuation Limit (Safer):**
```bash
cd /home/jupyter/Thinkubator/auto_train
copilot --autopilot \
        --yolo \
        --no-ask-user \
        --max-autopilot-continues 500 \
        -p "Read program.md and start the autonomous ML experiment loop."
```

**Resuming After Interruption:**
```bash
copilot --continue
```

### Launching with Cursor IDE

Open the `auto_train/` folder in Cursor, switch to Agent mode, and prompt:
```
Read @program.md and start the autonomous ML experiment loop.
Do the setup first (create branch, run baseline, initialize results.tsv),
then loop forever editing @train.py to maximize val_pr_auc.
```

### Launching with Claude Code CLI

```bash
cd /home/jupyter/Thinkubator/auto_train
claude --dangerously-skip-permissions \
  -p "Read program.md and start the autonomous ML experiment loop. NEVER STOP."
```

### Monitoring Progress (While Agent Runs)

From a separate terminal:
```bash
# Watch experiment count
watch -n 60 'wc -l results.tsv'

# See latest results
tail -20 results.tsv | column -t -s $'\t'

# See best result so far
sort -t$'\t' -k2 -rn results.tsv | head -5 | column -t -s $'\t'

# See git history
git log --oneline -20
```

---

## Summary of Key Design Decisions for Copilot CLI

| Design Element | Why It Compensates for Copilot CLI Limitations |
|---|---|
| **`agentStop` hook with `decision:"block"`** | Forces continuation when agent thinks it's done — equivalent of autoresearch's "NEVER STOP" but enforced at the runtime level |
| **`sessionStart` hook with prompt injection** | Re-orients the agent on session start/resume to read program.md and continue |
| **`AGENTS.md` (compact, auto-loaded)** | Survives context compaction — always in the agent's context window |
| **`program.md` (detailed, referenced)** | Full strategy catalog the agent reads when it needs ideas |
| **`results.tsv` as persistent memory** | Survives context compaction, session crashes, and restarts — the agent's long-term memory |
| **Structured grep-able output** | Simple metric extraction that works with any model capability level |
| **Git log as experiment audit trail** | `git log --oneline` provides compressed history of all attempts |
| **Recovery protocol in program.md** | Explicit instructions for what to do after context compaction or session resume |
| **Strategy catalog with code hints** | Compensates for potentially weaker model reasoning compared to Claude Opus |
| **Simple keep/discard logic (higher = keep)** | Trivial decision — no complex reasoning required |
