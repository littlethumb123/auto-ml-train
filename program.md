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

The TSV has a header row and **11 columns**:

```
commit	val_pr_auc	lift_at_10	macro_f1	val_f1	status	n_features	model_family	action_type	hypothesis	description
```

Use `python3 abes_engine.py log` to append rows - do NOT manually edit `results.tsv`.

The `model_family` column is one of:
`xgboost`, `lightgbm`, `catboost`, `rf`, `gbm`, `et`, `ensemble`, `other`.

## The experiment loop

The experiment runs on a dedicated branch (e.g. `autotrain/apr03`).

LOOP:

1. `python3 abes_engine.py recommend` - read the recommended action type and suggestion
2. Look at the current `train.py` to understand the current best approach.
3. Edit `train.py` with the recommended action type (ONE controlled change)
4. `git commit -am "experiment: [action_type] - <hypothesis>"`
5. `python3 train.py > run.log 2>&1`
6. `grep "^val_pr_auc:\|^lift_at_10:\|^macro_f1:\|^val_f1:\|^n_features:" run.log` - extract metrics
7. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the stack trace.
8. `python3 abes_engine.py log <commit> <pr_auc> <lift> <macro_f1> <val_f1> <status> <n_features> <model_family> <action_type> "<hypothesis>" "<description>"`
9. `python3 abes_engine.py check` - read anomaly/Pareto/plateau output
10. If val_pr_auc improved: keep (advance branch). If worse: `git reset --hard HEAD~1`
11. GOTO 1

## ABES: Executable Decision Engine

Before each experiment, **run the engine** - do NOT select action types by intuition:

### Before Each Experiment
```
python3 abes_engine.py recommend
```

Read the output. It prints:
- Urgency scores for all 8 action types
- The RECOMMENDED action type
- A specific suggestion for what to try
- Hard constraint status (blocked types, plateau warnings)

**Follow the recommendation.** If you have a strong reason to deviate, state it explicitly in the hypothesis.

### After Each Experiment
```
python3 abes_engine.py log <commit> <pr_auc> <lift> <macro_f1> <val_f1> <status> <n_features> <model_family> <action_type> "<hypothesis>" "<description>"
python3 abes_engine.py check
```

The `check` command:
- Detects anomalies (score below floor -> flags for diagnosis)
- Updates the Pareto front (tracks val_pr_auc x lift@10 x macro_f1)
- Warns on plateau (5+ consecutive discards)
- Triggers A_restart if 8+ consecutive discards

### Recovery
If context is compacted:
```
python3 abes_engine.py status
```
This prints full state: experiment count, best metrics, action distribution, Pareto front, anomalies.

---

## Warm-Start: Prior Knowledge from mar30 + apr01

The ABES engine is pre-loaded with these priors (in `abes_state.json`).
Do not repeat known dead ends.

### Known Dead Ends - Do NOT Retry (printed by engine before each experiment)

| What | Why Dead End | Source |
|------|-------------|--------|
| SMOTE + scale_pos_weight | Double-counts imbalance correction | mar30 |
| QuantileTransformer on tree models | Monotonic transform can't change tree splits | mar30 |
| BaggingClassifier wrapping XGBoost | Redundant with subsample/colsample | mar30 |
| aucpr as early stopping metric | Too noisy for stopping; use logloss | mar30 |
| LightGBM is_unbalance=True | Inverts probabilities - use scale_pos_weight or class_weight | mar30+apr01 |
| DART booster | Exceeds 90s timeout even at 500 trees | apr01 |
| tree_method=approx | Exceeds 90s timeout on 170K rows | apr01 |
| sklearn GBM (GradientBoostingClassifier) | Exceeds 90s even at 100 trees - no histogram optimization | apr01 |

### Structural Learnings (Apply Immediately)

| Learning | Evidence | Action |
|----------|----------|--------|
| log_amount adds signal | apr01: removing it hurts by ~0.002 | Keep in default features |
| Amount*V1, Amount*V2 add signal | apr01: removing them hurts by ~0.016 | Keep in default features |
| v_interactions (V1*V2, V1*V3, V3*V4) are noise | apr01: removing improves by ~0.002 | Do not add |
| time_features are noise | apr01: removing improves by ~0.003 | Do not add |
| XGBoost is best single-model family | apr01: beat all 5 alternatives | Start with XGBoost |
| LightGBM is competitive (0.818-0.834) | apr01: after fixing is_unbalance bug | Worthy of fair HP tuning |
| CatBoost, RF, ET are 2-3% below XGBoost | apr01: consistent across feature sets | Lower priority |
| depth in {4,5,6} is optimal range for XGBoost | apr01: depth=4 and depth=6 both found optimal basins | Search within this range |
| Ensembles don't help (insufficient diversity) | apr01: 5 attempts, all worse than solo XGBoost | Low priority until diverse models found |

Feature groups for ablation (6 total):
1. `log_amount`: `log1p(Amount)` - **KNOWN GOOD**
2. `time_features`: `Time_hour`, `Time_sin`, `Time_cos` - **KNOWN BAD**
3. `v_interactions`: `V1*V2`, `V1*V3`, `V3*V4` - **KNOWN BAD**
4. `amount_interactions`: `Amount*V1`, `Amount*V2` - **KNOWN GOOD**
5. `magnitude_features`: `abs(V14)`, `abs(V17)`, `V14**2` - **UNTESTED**
6. `rank_features`: `Amount.rank(pct=True)`, `V14.rank(pct=True)` - **UNTESTED**

### HP Priors Are RESET
The engine starts with canonical XGBoost defaults (depth=5, lr=0.05, n_est=500).
This is intentional - the engine should rediscover the optimal basin independently
to avoid anchoring to the apr01 local optimum.

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
