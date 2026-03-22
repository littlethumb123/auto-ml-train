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
