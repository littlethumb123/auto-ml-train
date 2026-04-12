# Auto-Train Mar30 Run — Post-Mortem & Reflection

**Date**: 2026-03-31
**Branch**: autotrain/mar30
**Run**: 20/20 experiments
**Best val_pr_auc**: 0.834870 (exp 14 — XGBoost + early stopping + feature eng)
**Honest best**: ~0.833714 (exp 5 — same setup without val leakage)

---

## I. Strategy Critique: How Was the Next Experiment Chosen?

The strategy was **reactive and intuition-driven**, not systematic. Here's the actual decision pattern:

| Exp | Selection Logic | Was It Informed by Prior Results? |
|-----|----------------|----------------------------------|
| 1 | Protocol: always run baseline first | — correct starting point |
| 2 | Strategy catalog: "try XGBoost first" | No — checklist, not hypothesis |
| 3 | "XGBoost worked, try another boosting lib" | Weakly — picked next-in-list |
| 4 | "XGBoost won, tune it" | Yes — but changed 7 params at once |
| 5 | "Model is good, add features" | Yes — reasonable progression |
| 6 | "Try class imbalance from catalog" | No — ignored that scale_pos_weight already handles this |
| 7 | "Try Optuna" — grabbed from catalog | No — kitchen-sink |
| 8–10 | XGBoost dominating, try alternatives | Panic mode — scattershot after 3 failures |
| 11 | "Too many features, try selection" | Weakly — arbitrary threshold |
| 12 | "Try stacking" from catalog | No — included LightGBM which had scored 0.036 (!) |
| 13 | "More features might help" | Contradicts exp 11 — incoherent |
| 14 | "Try early stopping" | Yes — best targeted idea in the run |
| 15–20 | Increasingly tight hyperparameter tweaks | No coherent strategy — random walks |

**Verdict**: A greedy hill-climb with no exploration plan. After experiments 2–5 established XGBoost + feature eng as the incumbent, all subsequent experiments were either (a) catalog items pulled without checking compatibility, or (b) random perturbations of hyperparameters. Zero systematic structure after experiment 5.

---

## II. Experiment-by-Experiment Critical Review

### Exp 1: Baseline LogisticRegression — 0.6807 ✅
No issues. Correct protocol — always establish anchor first.

---

### Exp 2: XGBoost with scale_pos_weight — 0.8143 ✅
Good first move, massive +0.134 gain. `max_depth=6, lr=0.1, n_estimators=300` are reasonable but arbitrary. No complaint here — the jump validated the model family choice.

---

### Exp 3: LightGBM with is_unbalance=True — 0.0367 ❌ **CRITICAL ERROR**

**The 0.036 score is almost certainly a bug, not evidence that LightGBM is bad.**

A model scoring *below random* (random on this dataset ≈ 0.0017 PR-AUC floor, but still) while LogisticRegression gets 0.68 means the probabilities are near-inverted or corrupted. Possible causes:
- `is_unbalance=True` may interact poorly with `predict_proba()` output in this LightGBM version
- LightGBM may have returned log-odds rather than probabilities
- Column alignment issue in the DataFrame
- `verbose=-1` suppressed warnings that would have explained the issue

**What I should have done instead**:
1. `print(model.predict_proba(X_val)[:, 1].describe())` — check if probabilities look sane
2. Try `1 - y_prob` — see if inversed probabilities recover the score
3. Try LightGBM with `scale_pos_weight` instead of `is_unbalance`
4. Check verbose output for [LightGBM] warnings

**This one failure dismissed LightGBM from the entire run.** LightGBM is typically competitive with or faster than XGBoost on tabular data. It received 1 try vs XGBoost's 12+. This is scientifically negligent.

---

### Exp 4: XGBoost tuned — 0.8278 ⚠️ CONFOUNDED
Changed **7 hyperparameters simultaneously**:
- n_estimators: 300 → 500
- max_depth: 6 → 5
- learning_rate: 0.1 → 0.05
- subsample: (new) 0.8
- colsample_bytree: (new) 0.8
- reg_alpha: (new) 1.0
- reg_lambda: (new) 1.0
- min_child_weight: (new) 5

The +0.013 gain cannot be attributed to any specific change. This violates controlled experimentation. Should have changed ONE parameter at a time.

---

### Exp 5: Feature engineering — 0.8337 ⚠️ NO ABLATION
Added 9 features in one shot:
- `log_Amount`, `Time_hour`, `Time_sin`, `Time_cos`
- `V1*V2`, `V1*V3`, `V3*V4`
- `Amount*V1`, `Amount*V2`

The +0.006 gain could come from 1 feature; the other 8 could be noise. The interaction features of PCA components (V1*V2 etc.) have no semantic meaning — they may be adding noise we got lucky to avoid.

No ablation ever ran. We never learned which features matter.

---

### Exp 6: SMOTE + XGBoost — 0.8106 ❌ CONCEPTUAL ERROR
**Redundant imbalance handling.** Used SMOTE (creates synthetic minority samples) alongside `scale_pos_weight` (multiplies minority loss by ~580). These solve the same problem. Combined they over-correct — the model sees a 50/50 class ratio from SMOTE AND a 580x loss multiplier.

Should have: Removed `scale_pos_weight` when adding SMOTE, or used `sampling_strategy=0.1` instead of full rebalancing.

This was not an empirical failure — it was a conceptual error caused by not thinking about what each technique does.

---

### Exp 7: Optuna 30s search — 0.8252 ❌ UNDER-RESOURCED
30 seconds for Bayesian optimization with 3-fold CV on 170K rows. Each trial ≈ 9s → ~3 trials completed. Bayesian optimization on 8 parameters with 3 trials is essentially random search with extra overhead.

Should have: (a) 2-fold CV, (b) subsample 20% of training data for search, (c) fix 5 parameters and search only the 2-3 most impactful, or (d) allocate 50s with fixed 1s/trial budget.

---

### Exp 8: VotingClassifier (XGB + RF + ET) — 0.8025 ⚠️ UNTUNED ENSEMBLE
Averaged a well-tuned XGBoost (600+ trees, tuned regularization) with two default-ish RandomForest and ExtraTrees. Soft voting weights all models equally, so two weak models dilute the strong one.

Should have: Either tuned each model separately first, or used `weights=[3,1,1]` in VotingClassifier to reflect XGBoost's superiority.

---

### Exp 9: Deep XGBoost (1000 trees, lr=0.02, depth=4) — 0.8229 ❌ TRIPLE CONSERVATISM
Simultaneously reduced depth (5→4), learning rate (0.1→0.02), AND increased regularization (reg_alpha 1→2, reg_lambda 1→2, added gamma). Each lever independently makes the model more conservative. Together: certain underfitting.

Should have changed ONE regularization dimension at a time.

---

### Exp 10: CatBoost — 0.7755 ❌ WRONG DEFAULTS + WRONG DOMAIN
Two separate issues:

1. **Wrong defaults**: CatBoost uses symmetric trees — `depth=6` means 64 leaf nodes, architecturally different from XGBoost's greedy trees at depth=5. `iterations=500` may be under-training for CatBoost's conservative boosting.

2. **Wrong domain**: CatBoost's main advantages are (a) ordered boosting to prevent target leakage, (b) native categorical feature handling. This dataset has NO categorical features (all continuous PCA components). CatBoost's core advantages don't apply here.

Dismissed after 1 attempt without trying CatBoost-idiomatic hyperparameters (`depth=4, l2_leaf_reg=3, bagging_temperature=1`).

---

### Exp 11: Feature importance selection — 0.8236 ⚠️ ARBITRARY THRESHOLD
Used `threshold=0.01` to drop 22/39 features. The threshold was pulled from thin air. The "quick" 100-tree XGBoost used for importance ranking may not reflect the full model's feature preferences.

Should have: Tried multiple thresholds (0.001, 0.005, 0.01, 0.02) as a sweep. Or used permutation importance, which is more reliable than gain-based importance for correlated features.

---

### Exp 12: StackingClassifier (XGB + LightGBM + ET → LogReg) — 0.7949 ❌ INCLUDED BROKEN MODEL
**Included LightGBM which scored 0.036 in experiment 3.** If LightGBM's probabilities are garbage (as exp 3 suggests), feeding them to a meta-learner contaminates the entire stack. This is a direct failure to learn from a prior result.

Also: 3-fold CV stacking on 170K rows is expensive (~18s of the 43s budget). LogisticRegression meta-learner cannot model non-linear interactions between base learner outputs.

---

### Exp 13: Richer features (48 total) + relaxed regularization — 0.8259 ❌ CONFOUNDED AGAIN
**Changed features AND model simultaneously**: added 9 features AND changed n_estimators (500→600), max_depth (5→6), reg_alpha (1.0→0.5), min_child_weight (5→3). Cannot tell if the regression came from bad features or bad hyperparameters.

Also contradicts exp 11's conclusion that fewer features help.

---

### Exp 14: Early stopping on val set — 0.8349 🚨 DATA LEAKAGE (current "best")

**This is the most important issue in the entire run.**

Used `eval_set=[(X_val, y_val)]` where `X_val, y_val` is the **same validation set used by `evaluate()` to compute val_pr_auc**.

The model's training process (when to stop at iteration 559) was directly informed by the evaluation data. This is validation set contamination. The model was allowed to peek at the test it was graded on in order to decide when to stop training.

The improvement from exp 5 (0.8337) to exp 14 (0.8349) is +0.001 — plausibly entirely spurious. The "best" model in the run is not honestly the best.

**Correct approach**:
- Option A: Split val into val_stop (70%) + val_eval (30%). Use val_stop for early stopping, val_eval for evaluate().
- Option B: Use a different early stopping metric (logloss, which is smoother and less noisy than aucpr) while still evaluating on PR-AUC.
- Option C: Use early stopping to determine the optimal number of rounds, then retrain on full training data with that fixed count.

---

### Exp 15: depth=6, lr=0.03, early stop — 0.7182 ❌ NOISY STOPPING CRITERION
Stopped at iteration 72 out of 2000. The `aucpr` metric is highly non-monotonic — it can oscillate significantly over 50 rounds, causing premature stopping.

Should have used `logloss` as the early stopping signal (smooth, monotonically decreasing), while evaluating final performance on PR-AUC.

---

### Exp 16: QuantileTransformer + XGBoost — 0.8301 ❌ WRONG THEORY
**Conceptually invalid for tree models.** Decision trees split on rank order. QuantileTransformer is a monotonic transformation → it cannot change any tree split boundary. The slight degradation (-0.003) likely comes from the transformation being applied to interaction features (`QT(V1*V2) ≠ QT(V1)*QT(V2)`), breaking their information structure.

---

### Exp 17: Amount-weighted sample_weight — 0.7031 ❌ CONFLICTING SIGNALS
Two problems:
1. Called `get_splits()` a second time to retrieve original Amount — wasteful.
2. The sample weights (range 1.0–2.0) interacted with `scale_pos_weight` (~580). The class imbalance correction that was carefully tuned effectively collapsed.

Also: The justification ("high-amount fraud matters more") is a domain assumption. PR-AUC doesn't care about Amount — it treats all True Positives equally. The sample weights were optimizing for the wrong objective.

---

### Exp 18: Minimal features (log_Amount + V1*V2 + V1*V3) — 0.7139 ❌ INFORMED BY WRONG PRIOR
This experiment tried to strip everything out to find the minimum sufficient feature set. But it was done AFTER experiment 14 showed early stopping is fragile — removing features makes the validation curve noisier, triggering premature early stopping.

Stopped at a low iteration (similar to exp 15). The 0.714 score doesn't tell us whether minimal features are bad — it tells us early stopping fires too early on a noisy surface with few features.

---

### Exp 19: BaggingClassifier(XGBoost, 5) — 0.8205 ❌ REDUNDANT BAGGING
XGBoost already has `subsample=0.8` (row-level bootstrap resampling) and `colsample_bytree=0.8` (column-level bootstrap). Adding BaggingClassifier on top adds a third layer of row sampling — effectively training on X_train[bootstrap] of X_train[subsample=0.8], which under-samples an already tiny fraud class.

---

### Exp 20: XGBoost 600 trees, relaxed reg, no early stop — 0.8279 ❌ CONFOUNDED AGAIN
Changed 5 things simultaneously: removed early stop, n_estimators 2000→600, colsample_bytree 0.8→0.85, reg_alpha 1.0→0.5, reg_lambda 1.0→0.8, min_child_weight 5→3. No learning possible from this.

---

## III. Systemic Issues

### 1. Data Leakage in the "Best" Model
The final "best" (exp 14, 0.8349) uses the validation set for early stopping. Since `evaluate()` grades on that same val set, the model's training was contaminated. The honest best is likely exp 5 (0.8337) — just 9 engineered features + well-tuned XGBoost.

### 2. Zero Controlled Variable Testing
Of 20 experiments, **zero used a single-variable controlled design**. Every experiment changed 2–8 things at once. We spent 20 experiments and learned almost nothing about which individual factors drive performance on this dataset.

### 3. Confirmation Bias Toward XGBoost
| Model | Experiments | Config quality |
|-------|------------|---------------|
| XGBoost | 12+ | Carefully tuned, multiple configs |
| LightGBM | 1 | 1 buggy config, dismissed |
| CatBoost | 1 | Wrong defaults, dismissed |
| RandomForest | 0 (solo) | Only as ensemble member |
| SVM | 0 | Never tried |
| GradientBoosting | 0 | Never tried |

After XGBoost won early, every alternative got 1 chance. This is not a fair tournament.

### 4. No Investigation of Failures
When experiments scored anomalously low (LightGBM 0.036, Amount-weighted 0.703), they were logged as "bad idea" without asking WHY. The 0.036 score is a bug that a 2-minute investigation would have resolved, potentially unlocking LightGBM as a strong competitor.

### 5. Strategy Catalog as Checklist
The catalog in `program.md` was treated as a menu to order from, not a framework for hypothesis generation. The right approach:
- "Data is PCA-transformed → interactions of V-features have no semantic meaning; likely noise"
- "580:1 imbalance → scale_pos_weight handles it; SMOTE on top = double-correction error"
- "LightGBM ≈ XGBoost in algorithm → 0.036 score means a bug, not a model quality issue"

### 6. No Feature Importance Analysis
Never ran `model.feature_importances_` on the winning model to understand what was actually being used. This would directly inform which feature engineering directions to pursue.

---

## IV. What to Improve Next Run

### Process Changes

1. **One variable at a time.** Each experiment changes exactly ONE thing. Two experiments instead of one if two things are interesting.

2. **Investigate anomalous failures.** Any score worse than baseline → check `y_prob.describe()` before logging as discard.

3. **Run feature importance analysis between major stages.** After model selection, before feature engineering. After feature engineering, before tuning.

4. **Ablation after compound experiments.** If exp N adds 5 features and improves, exp N+1 through N+5 each remove one feature to find the minimal sufficient set.

5. **Pre-register hypotheses.** Before each experiment: "I predict this will change PR-AUC by ±X because Y." If the prediction is wrong, investigate.

6. **Log the WHY, not just the WHAT.** Add `hypothesis` and `learning` columns to results.tsv.

### Technical Changes

1. **Fix the early stopping leakage.** Use a separate hold-out subset for early stopping, or use `logloss` as stopping criterion and `aucpr` only for final evaluation.

2. **Fair model tournament first.** Before tuning: give each model family (XGBoost, LightGBM, CatBoost, RF, GBM) 3 config attempts to find its competitive range, then crown a winner.

3. **On anomalous LightGBM score.** The correct fix: `LGBMClassifier(scale_pos_weight=ratio)` mirrors XGBoost's interface exactly. `is_unbalance=True` is a flag that may interact differently with probability calibration.

4. **Optuna with proper budget.** Use 20% subsample of training data for CV during search, 2-fold CV, search only 3 params at a time. This gives ~15 meaningful trials in 30s instead of 3.

5. **Results file schema expansion.**
   ```
   commit | val_pr_auc | val_f1 | status | n_features | hypothesis | changed_from_prev | learning
   ```

### Experiment Ordering Strategy (Proposed)

```
Phase 1: Model tournament (8 experiments)
  - Each model: XGBoost, LightGBM, CatBoost, RF, ET, GBM
  - 1 canonical config per model (same class balancing, no feature eng)
  - Crown winner

Phase 2: Feature engineering ablation (4 experiments)
  - Start from raw features, add one category at a time
  - Measure marginal contribution of each feature group

Phase 3: Hyperparameter tuning (4 experiments)
  - Winner model + best feature set
  - One HP dimension at a time: depth, lr, regularization, sampling

Phase 4: Advanced methods (4 experiments)
  - Early stopping (with proper hold-out)
  - Best ensemble (winner + runner-up, properly tuned)
  - Any domain-specific tricks
```

---

## V. Final Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| Model diversity | 2/10 | XGBoost dominated; LightGBM/CatBoost not fairly evaluated |
| Controlled experimentation | 0/10 | Zero single-variable experiments |
| Failure investigation | 1/10 | Never investigated LightGBM 0.036 bug |
| Feature understanding | 2/10 | No ablation, no importance analysis |
| Data integrity | 6/10 | One val leakage issue in final model |
| Exploration breadth | 3/10 | Heavy XGBoost bias, ~5 model families untried |
| Improvement from baseline | 9/10 | 0.681 → 0.835 (+22.6%) is meaningful |
| Strategy coherence | 3/10 | Reasonable phases 1–5, then reactive and incoherent |

**Overall**: The run found a strong model (+22.6% over baseline) but likely left 2–5 PR-AUC points on the table from premature LightGBM dismissal, no fair CatBoost tuning, and compounded confounding throughout.

The honest best model is exp 5 (0.8337): well-tuned XGBoost + 9 engineered features + no val leakage.
