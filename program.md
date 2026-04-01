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
lift_at_10:       9.50
macro_f1:         0.912000
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

Extract key metrics from the log file:

```
grep "^val_pr_auc:\|^lift_at_10:\|^macro_f1:\|^val_f1:\|^n_features:" run.log
```

## Logging results

When an experiment is done, log it to `results.tsv` (tab-separated, NOT comma-separated).

The TSV has a header row and 10 columns:

```
commit	val_pr_auc	lift_at_10	macro_f1	val_f1	status	n_features	action_type	hypothesis	description
```

1. git commit hash (short, 7 chars)
2. val_pr_auc achieved (e.g. 0.750000) — use 0.000000 for crashes
3. lift_at_10 (float, e.g. 85.23) — use 0.00 for crashes
4. macro_f1 (float, e.g. 0.912000) — use 0.000000 for crashes
5. val_f1 achieved (e.g. 0.800000) — use 0.000000 for crashes
6. status: `keep`, `discard`, or `crash`
7. n_features used (integer) — use 0 for crashes
8. action_type: one of `A_model`, `A_feature`, `A_hp`, `A_imbalance`, `A_ensemble`, `A_diagnose`, `A_validate`
9. hypothesis: one sentence stating the single variable changed and predicted effect
10. short text description of what this experiment tried

Example:

```
commit	val_pr_auc	lift_at_10	macro_f1	val_f1	status	n_features	action_type	hypothesis	description
a1b2c3d	0.750000	12.50	0.856000	0.800000	keep	30	A_model	LogReg baseline establishes floor	baseline: LogisticRegression + StandardScaler
b2c3d4e	0.780000	95.30	0.912000	0.820000	keep	30	A_model	XGBoost with scale_pos_weight should beat LogReg	XGBoost with scale_pos_weight
c3d4e5f	0.770000	88.10	0.900000	0.810000	discard	45	A_feature	polynomial features may add signal	added polynomial features (no improvement)
d4e5f6g	0.000000	0.00	0.000000	0.000000	crash	0	A_model	CatBoost may fit faster than XGBoost	CatBoost OOM with 100 features
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
7. Read out the results: `grep "^val_pr_auc:\|^lift_at_10:\|^macro_f1:\|^val_f1:\|^n_features:" run.log`
8. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the Python stack trace and attempt a fix. If you can't fix it after 2 attempts, give up on this idea.
9. Record the results in results.tsv (do NOT commit results.tsv — leave it untracked by git)
10. If val_pr_auc improved (higher), you "advance" the branch, keeping the git commit.
11. If val_pr_auc is equal or worse, you git reset back to where you started: `git reset --hard HEAD~1`

## ABES: Adaptive Experiment Selection

Before proposing each experiment, run this 4-step meta-decision to ensure you explore the search space efficiently rather than hill-climbing on one model family.

### Step 1 — Compute Urgency for Each Action Type

From results.tsv and current state, score each action type (0.0–1.0):

| Action Type | Urgency Rule |
|-------------|-------------|
| `A_model`   | (count of model families with fewer than 2 completed trials, including untried ones with 0) ÷ 6 |
| `A_feature` | 1 − (feature groups ablated ÷ 4 total groups) |
| `A_hp`      | 1 ÷ (1 + count of A_hp experiments in last 5 rows of results.tsv) |
| `A_diagnose`| min(1.0, 0.5 × count of undiagnosed anomalies), where anomaly = score < max(0.5×best, 0.68) |
| `A_ensemble`| 0.3 if ≥2 models are within 5% of best; 0.0 otherwise |
| `A_validate`| max(0, (t÷T − 0.8) × 5) — ramps up only in the final 20% of budget |

Model families to track: `xgboost`, `lightgbm`, `catboost`, `rf`, `gbm`, `et`

Feature groups for ablation (4 total):
1. `log_amount`: `log1p(Amount)`
2. `time_features`: `Time_hour`, `Time_sin`, `Time_cos`
3. `v_interactions`: `V1*V2`, `V1*V3`, `V3*V4`
4. `amount_interactions`: `Amount*V1`, `Amount*V2`

### Step 2 — Select Action Type

Pick the highest-urgency action type. Break ties by:
- Prefer `A_model` early (experiment t < T×0.4)
- Prefer `A_feature` in the middle range (T×0.4 ≤ t ≤ T×0.7)
- Prefer `A_hp` late (experiment t > T×0.7)
- Prioritize `A_diagnose` if urgency > 0, but limit to at most 2 consecutive diagnosis experiments before returning to normal selection

### Step 3 — Propose ONE Controlled Experiment

Within the selected action type:
- **A_model**: Try the untried/under-tried model family with its canonical config
- **A_feature**: Add or remove ONE feature group; keep all else equal
- **A_hp**: Change ONE hyperparameter; keep all else equal
- **A_diagnose**: Re-run the anomalous config, print `model.predict_proba(X_val[:5])` to check for probability inversion
- **A_ensemble**: Stack top-2 competitive models with equal weights
- **A_validate**: Apply proper hold-out early stopping (reserve 20% of train as stop set, separate from val)

**Single-variable rule**: ONE variable changed per experiment. Commit message must state both the action type and hypothesis:
```
experiment: [action_type] — [hypothesis]
# Example: experiment: A_model — LightGBM with scale_pos_weight (fair trial, fixes is_unbalance bug)
```

### Step 4 — Anomaly Detection

After each run, check for anomalies:
- If `val_pr_auc < max(0.5 × current_best, 0.68)` → **FLAG as anomaly**
  - Print `model.predict_proba(X_val[:5])` — check if fraud probabilities are near 0 (inversion bug)
  - Log this result as-is, set action_type = `A_diagnose` for the **next** experiment
  - Do NOT conclude the model family is bad from one anomalous result

---

## Warm-Start: Prior Knowledge from mar30

Apply these lessons before selecting your first experiment. Do not repeat known dead ends.

### Known Dead Ends — Do NOT Repeat

| What | Why Dead End |
|------|-------------|
| SMOTE + scale_pos_weight | Double-counts imbalance correction; SMOTE alone also worse |
| QuantileTransformer on tree models | Monotonic transforms cannot change tree splits — no effect |
| BaggingClassifier wrapping XGBoost | XGBoost has subsample/colsample built-in; bagging is redundant |
| `eval_metric="aucpr"` for early stopping | PR-AUC is noisy/non-monotonic as early-stopping signal; use `logloss` for stopping. (OK as internal eval when early stopping is disabled.) |
| LightGBM with `is_unbalance=True` | **BUG**: inverted probabilities → score 0.036 is meaningless, not real performance |

### Untried / Unfairly Tried — High Priority

| Family | Status | Canonical Config to Try |
|--------|--------|------------------------|
| LightGBM | 1 trial (BUGGY) | `LGBMClassifier(scale_pos_weight=ratio, n_estimators=500, num_leaves=63, learning_rate=0.05, n_jobs=-1)` |
| CatBoost | 1 trial (wrong defaults) | `CatBoostClassifier(depth=4, l2_leaf_reg=3, auto_class_weights='SqrtBalanced', iterations=500, verbose=0)` |
| RandomForest | 0 trials | `RandomForestClassifier(n_estimators=500, class_weight='balanced', n_jobs=-1)` |
| Extra Trees | 0 trials | `ExtraTreesClassifier(n_estimators=500, class_weight='balanced', n_jobs=-1)` |
| GBM | 0 trials | `GradientBoostingClassifier(n_estimators=300, subsample=0.8, max_depth=5, learning_rate=0.05)` |

### Best Known Config (Honest, val_pr_auc ≈ 0.8337)

```python
XGBClassifier(
    n_estimators=500, max_depth=5, learning_rate=0.05,
    scale_pos_weight=n_neg/n_pos,  # ~578
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=1.0, reg_lambda=1.0, min_child_weight=5,
    eval_metric="aucpr", tree_method="hist", n_jobs=-1
)
# + 9 engineered features:
#   log1p(Amount), Time_hour, Time_sin, Time_cos,
#   V1*V2, V1*V3, V3*V4, Amount*V1, Amount*V2
```

---

## Strategy Catalog

Here are categories of strategies to explore, roughly ordered by expected impact:

### 1. Model Selection (try these first)
- XGBoost with `scale_pos_weight` = (n_neg / n_pos)
- LightGBM with `scale_pos_weight` = (n_neg / n_pos) — do NOT use `is_unbalance=True` (known bug: inverts probabilities)
- CatBoost with `auto_class_weights='SqrtBalanced'` and `depth=4, l2_leaf_reg=3`
- RandomForestClassifier with `class_weight='balanced'`
- GradientBoostingClassifier
- ExtraTreesClassifier
- SVM with RBF kernel (may be slow on ~285K rows — subsample if needed)

### 2. Class Imbalance Handling
- SMOTE (from imblearn) in a pipeline with `imblearn.pipeline.Pipeline` — **do NOT combine with scale_pos_weight** (double-counts imbalance)
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
- ~~BaggingClassifier wrapping the best single model~~ — dead end for XGBoost (redundant with subsample/colsample)
- Two-stage: first model filters, second model refines

### 7. Hyperparameter Tuning
- Use Optuna for Bayesian optimization within the time budget
- Grid search on a small parameter grid
- Random search on a broader grid
- Focus on: learning_rate, max_depth, n_estimators, subsample, colsample_bytree

### 8. Preprocessing Variations
- RobustScaler instead of StandardScaler (better with outliers)
- MinMaxScaler
- ~~QuantileTransformer (Gaussian output)~~ — dead end for tree models (monotonic transform can't change splits)
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

## Experiment Limits & Stopping Conditions

**MAX_EXPERIMENTS = 20** (configurable via environment variable `MAX_EXPERIMENTS`)

The experiment loop runs until ONE of these conditions is met:

1. **Experiment limit reached**: Count experiments via `expr $(wc -l < results.tsv) - 1`. Stop when >= MAX_EXPERIMENTS.
2. **Plateau detected**: 3+ consecutive discards/crashes suggest you've exhausted easy improvements. Consider stopping or trying radically different approaches.
3. **Excellent result achieved**: val_pr_auc > 0.85 is very strong for this imbalanced dataset — you may choose to stop early.

**Do NOT ask the human** for permission to continue or stop. Check the limit yourself and proceed autonomously.

## When You Stop

When you reach a stopping condition:

1. Read `results.tsv` to see all experiment outcomes
2. Report the **best val_pr_auc** achieved and which experiment it was
3. List the **top 3 approaches** by val_pr_auc
4. Summarize key learnings: what worked, what didn't, what you'd try next
5. The final `train.py` should contain the best-performing approach
