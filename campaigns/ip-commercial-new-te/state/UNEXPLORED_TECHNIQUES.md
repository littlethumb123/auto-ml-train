---
schema_version: 2
campaign_id: "ip-commercial-new-te"
purpose: "Comprehensive ML technique toolkit — exhaustive catalog of strategies used by Kaggle grandmasters and experienced MLEs. Planner reads every round and must justify skipping any Unexplored class with Expected Δ > noise_floor when consecutive_discards ≥ 2."
last_updated: "2026-04-25 (rev2: added imbalanced-learn umbrella note, hill climbing implementation, diverse-base-model strategy principle, training-objectives diversity entry)"
sources: "Kaggle Grandmasters Playbook (NVIDIA), neptune.ai binary classification tips, MLAgentBench, standard MLE practice"
---

# Complete ML Technique Toolkit — ip-commercial-new-te

**Planner rule:** Before writing NEXT_EXPERIMENT.md, scan this file.
- If `consecutive_discards ≥ 2`: must choose from Unexplored OR write one sentence per class explaining why skipping.
- If `consecutive_discards ≥ 3` (post-C2): MUST select from Unexplored unless all are excluded with reasoning.
- When proposing from this file, update Status to `In-progress` in NEXT_EXPERIMENT.md §2.

**Status legend:**
- `Unexplored` — never tried in this campaign
- `Partial` — tried in limited form; full version untested
- `Done` — tried, result recorded in results.tsv
- `Dead-end` — tried and confirmed useless (see DEAD_ENDS.md for details)
- `Excluded` — decided against with stated reasoning

---

## A. Feature Engineering

### A1. Encoding Strategies

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Target encoding (smoothed mean of ip6 rate per category value) | **Unexplored** | 0.2–0.5 | county_cd, division, cust_segment_cd have meaningful IP6 rate variation by value. Cross-fold smoothing prevents leakage. Can replace current integer-code workaround. |
| Leave-one-out target encoding | **Unexplored** | 0.1–0.4 | Variant with stronger leakage prevention; encodes each row using target mean computed leaving that row out |
| Frequency encoding (count of each category value in training set) | **Unexplored** | 0.0–0.2 | Adds signal about rare vs. common geographic categories |
| WOE (Weight of Evidence) encoding | **Unexplored** | 0.1–0.3 | log(P(X|y=1)/P(X|y=0)) per category — classic in credit/healthcare risk |
| Binary / one-hot encoding for low-cardinality cats | **Unexplored** | 0.0–0.1 | drug_ind, vision_ind, mental_health_ind have few values; OHE may help tree models |
| Ordinal encoding with domain-sorted order | **Unexplored** | 0.0–0.1 | Some categoricals (age brackets, severity levels) have natural ordering |
| CatBoost native string categorical handling | **Unexplored** | 0.1–0.3 | Requires rebuilding split cache with original string values; CatBoost's internal target encoding with prior smoothing is superior to current integer codes |

### A2. Aggregation / Group-by Features

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| IP6 rate by county_cd (rolling estimate) | **Unexplored** | 0.1–0.3 | Geographic IP6 prevalence rate is a strong prior; add as a feature |
| Group-by statistics within fund category / product line | **Unexplored** | 0.1–0.3 | Mean/std/count of IP utilization by insurance product — plan type affects hospital access |
| MDC-specific IP rate per member-month bucket | **Unexplored** | 0.1–0.4 | Top-3 MDC codes × time window → high-dimensional risk signal |
| Rolling aggregation: 3mo/6mo/1yr trend slopes | **Unexplored** | 0.1–0.3 | Rate of change in IP utilization (velocity) — faster growth → higher risk |
| Percentile rank within age×gender group | **Unexplored** | 0.0–0.2 | A patient's IP6 risk relative to their demographic cohort |

### A3. Interaction / Polynomial Features

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Pairwise products of top SHAP features | **Unexplored** | 0.1–0.3 | Round 6 SHAP showed top features — their pairwise products may capture synergies |
| Age × comorbidity count interaction | **Unexplored** | 0.1–0.3 | Well-established in clinical risk: older patients with more comorbidities have super-additive risk |
| IP history × ER visits interaction | **Unexplored** | 0.1–0.4 | ER → IP pathway: members with both prior IP AND ER visits are highest risk |
| Polynomial features (degree-2) on eng_ip_score, eng_chronic_score | **Unexplored** | 0.0–0.2 | Quadratic risk: doubling IP count may more than double risk |
| Ratio features: 3mo/6mo, 6mo/1yr for MDC counts | **Unexplored** | 0.1–0.3 | Acceleration in utilization is more predictive than absolute level |

### A4. Domain-Specific Clinical Features

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Charlson Comorbidity Index (CCI) from condition flags | **Unexplored** | 0.2–0.5 | Gold standard in clinical risk — weighted sum of specific comorbidities. Can be computed from Heart_Failure, Diabetes_Mellitus, etc. |
| Elixhauser Comorbidity Score | **Unexplored** | 0.2–0.4 | Alternative to CCI; broader set of conditions; standard in claims analytics |
| DRG-based severity score from MDC codes | **Unexplored** | 0.1–0.3 | Map MDC codes to severity weights; high-acuity MDCs predict future IP better than count alone |
| Lab abnormality composite score (# of elevated labs) | Partial | 0.1–0.2 | eng_lab_score was a sum; weighted score by clinical severity of each abnormality may be better |
| Member months × IP rate = expected utilization | **Unexplored** | 0.1–0.3 | Controls for enrollment duration: normalizes IP count by months eligible |
| Time since last IP admission | **Unexplored** | 0.1–0.3 | Recency of last hospitalization is a strong predictor of near-term re-hospitalization |
| Condition count trajectory (increasing vs stable) | **Unexplored** | 0.1–0.3 | Members with increasing comorbidity count (1yr vs 2yr) are higher risk |

### A5. Dimensionality Reduction as Features

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| PCA on 256 embedding dimensions | **Unexplored** | 0.0–0.2 | Reduce 256 to 20-50 principal components; may denoise the embedding space |
| UMAP on embeddings (2-10 components) | **Unexplored** | 0.0–0.2 | Non-linear dimensionality reduction; captures manifold structure of embeddings |
| k-means cluster assignment on embeddings | **Unexplored** | 0.1–0.3 | Cluster membership as a categorical feature; identifies natural member risk profiles |
| Distance to cluster centroid | **Unexplored** | 0.0–0.2 | How atypical a member is within their embedding cluster |
| NMF on MDC utilization matrix | **Unexplored** | 0.1–0.2 | Non-negative matrix factorization on MDC count matrix; extracts IP utilization patterns |

---

## B. Data Preprocessing

### B1. Missing Value Strategies

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| KNN imputation for lab values | **Unexplored** | 0.0–0.1 | Lab columns have ~50% missing; KNN finds similar members to impute values |
| Model-based imputation (predict missing from present) | **Unexplored** | 0.0–0.1 | Train a model per column to impute; captures non-linear patterns |
| Missing indicator features | **Unexplored** | 0.1–0.2 | Whether a lab value is missing IS informative (labs only ordered when suspected abnormal) |
| Multiple imputation | **Unexplored** | 0.0–0.1 | Multiple imputed datasets → averaged predictions; reduces imputation uncertainty |

### B2. Transformations

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Log1p transform on skewed count features | **Unexplored** | 0.0–0.2 | IP counts, claim counts are right-skewed; log-transform improves GBDT split quality |
| Rank transform (convert to percentile) | **Unexplored** | 0.0–0.1 | Makes features scale-invariant; useful for outlier-sensitive models |
| Quantile transform (uniform or normal output) | **Unexplored** | 0.0–0.1 | Forces features to specific distribution; may help models with linear components |
| Yeo-Johnson power transform | **Unexplored** | 0.0–0.1 | Handles negative values unlike Box-Cox; normalizes skewed distributions |

### B3. Outlier Handling

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Winsorization (clip at 1st/99th percentile) | **Unexplored** | 0.0–0.1 | IP counts may have extreme outliers (e.g., 50+ admissions); clipping prevents undue influence |
| Isolation Forest for outlier detection | **Unexplored** | 0.0–0.1 | Flag statistical outliers as a feature; may identify data quality issues |

---

## C. Re-imbalancing (~0.77% positive rate)

> **Library:** All data-level techniques below are available in the `imbalanced-learn` package (`pip install imbalanced-learn`). Import pattern: `from imblearn.over_sampling import ADASYN, BorderlineSMOTE, SMOTENC` / `from imblearn.under_sampling import TomekLinks, NearMiss` / `from imblearn.combine import SMOTEENN, SMOTETomek`. Apply **after** `get_splits()` and **before** model training. Do NOT modify `prepare.py`.

### C1. Data-Level Oversampling

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| ADASYN (Adaptive Synthetic Sampling) | **Unexplored** | 0.1–0.5 | Generates synthetic positives weighted by difficulty — focuses on hard boundary cases near top-1% threshold. Secondary resampling in train.py after get_splits(); does NOT require changing prepare.py |
| SMOTE standalone (no additional class weight) | **Unexplored** | 0.0–0.3 | DEAD-END is SMOTE + scale_pos_weight together. SMOTE alone with Balanced class weights is untested |
| Borderline-SMOTE | **Unexplored** | 0.1–0.3 | Only synthesizes near decision boundary; better than vanilla SMOTE for hard cases |
| SMOTE-NC (handles mixed types) | **Unexplored** | 0.0–0.2 | Handles the 14 categorical columns natively during oversampling |
| Random oversampling with augmentation noise | **Unexplored** | 0.0–0.2 | Duplicate positives with small feature perturbations (Gaussian noise on float features) |

### C2. Data-Level Undersampling

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Different downsampling ratios (5:1, 3:1, 20:1) | **Unexplored** | 0.1–0.4 | Current 10:1 is arbitrary. 5:1 → fewer negatives, more weight on positives. 20:1 → more negatives, lower false positive rate. Override in train.py after get_splits() |
| Tomek Links undersampling | **Unexplored** | 0.0–0.2 | Removes borderline majority-class points that are closest neighbors of minority points |
| Cluster Centroids undersampling | **Unexplored** | 0.0–0.1 | Replaces clusters of negatives with their centroids; reduces noise in majority class |
| NearMiss undersampling | **Unexplored** | 0.0–0.2 | Selects majority samples closest to minority; focuses negative sampling on ambiguous cases |

### C3. Combination Methods

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| SMOTEENN (SMOTE + Edited Nearest Neighbors) | **Unexplored** | 0.1–0.3 | Oversamples minority AND cleans noisy majority; robust combination |
| SMOTETomek | **Unexplored** | 0.0–0.2 | SMOTE oversampling + Tomek link removal; standard imbalanced-learn combination |

### C4. Model-Level Rebalancing

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Focal loss (γ > 0 custom XGB/LGBM objective) | **Unexplored** | 0.1–0.5 | Reduces loss contribution of easy negatives (score far from 0.5); forces model to focus on hard near-boundary cases. Higher γ → more focus on hard cases. Custom objective in XGBoost |
| Custom class weights tuned for AUC-PR | **Unexplored** | 0.1–0.3 | Neither 1:1 nor 591:1 — systematically search for weight w that maximizes val AUC-PR specifically |
| scale_pos_weight search (XGBoost) | **Unexplored** | 0.05–0.2 | Only tried at fixed ratio=10; optimal value may be 2–50 |
| AUC-PR as explicit training objective | **Unexplored** | 0.1–0.4 | XGBoost custom objective: directly maximize average precision instead of log-loss |
| Asymmetric loss (higher penalty for FN vs FP) | **Unexplored** | 0.1–0.3 | Healthcare-relevant: missing a true IP6 case (FN) is worse than false alarm (FP) — encode this asymmetry in loss |

---

## D. Model Families

### D1. Neural Tabular (GPU required for speed; may be feasible without)

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| TabNet (attention-based feature selection) | **Unexplored** | 0.1–0.5 | End-to-end tabular DL with sequential attention; shown competitive with GBDTs on structured healthcare data |
| FT-Transformer (Feature Tokenizer + Transformer) | **Unexplored** | 0.1–0.5 | BERT-style attention over feature tokens; handles mixed tabular well |
| TabTransformer | **Unexplored** | 0.1–0.4 | Transformer on categorical embeddings + MLP on numerics |
| NODE (Neural Oblivious Decision Ensembles) | **Unexplored** | 0.1–0.3 | Differentiable decision trees; bridges GBDT and neural approaches |
| MLP with residual connections | **Unexplored** | 0.0–0.3 | Plain deep network; often underperforms GBDT on tabular but provides diversity |
| Wide & Deep (memorization + generalization) | **Unexplored** | 0.0–0.2 | Joint training of wide linear model + deep network; captures both memorized patterns and generalizations |

### D2. Tree-based (non-GBDT)

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| ExtraTreesClassifier (sklearn) | **Unexplored** | 0.0–0.2 | Extremely randomized trees; faster than RF, higher variance, good for diversity in ensemble |
| HistGradientBoostingClassifier (sklearn, fast) | **Unexplored** | 0.0–0.2 | sklearn's native GBDT with histogram binning; similar to LightGBM but different regularization |
| Balanced Random Forest (imbalanced-learn) | **Unexplored** | 0.0–0.3 | RF with balanced bootstrap sampling per tree; specifically designed for imbalance |

### D3. Linear / Probabilistic

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Logistic Regression with L1 (Lasso) | **Unexplored** | 0.0–0.1 | Strong L1 regularization gives sparse solution; interpretable subset of features |
| Logistic Regression with polynomial features | **Unexplored** | 0.0–0.1 | LR on degree-2 features; captures interactions linearly |
| Gaussian Naive Bayes | **Unexplored** | 0.0–0.0 | Rarely competitive; useful only for ensemble diversity |

---

## E. Hyperparameter Optimization

### E1. Different Optuna Strategies

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| CMA-ES sampler (evolution strategy) | **Unexplored** | 0.0–0.2 | More global search than TPE; good when function is smooth |
| NSGA-II multi-objective (AUC-PR + lift@1%) | **Unexplored** | 0.1–0.3 | Jointly optimize two metrics; finds Pareto-optimal configurations |
| Bayesian optimization with Gaussian Process | **Unexplored** | 0.0–0.2 | More principled than TPE; better sample efficiency on smooth landscapes |
| Hyperband / BOHB | **Unexplored** | 0.0–0.2 | Combines early stopping with BO; aggressive resource allocation to promising configs |

### E2. Proxy Metric Variants

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| AUC-ROC proxy for XGB → full model (DISCOVERED r25) | Done ✓ | +0.446 BREAKTHROUGH | The key discovery: AUC-ROC proxy finds ensemble-complementary HPs |
| AUC-PR as Optuna proxy | **Unexplored** | 0.1–0.3 | More directly related to lift@1% than AUC-ROC; may find HPs that improve precision-recall tradeoff |
| lift@5% as proxy (smoother than lift@1%) | **Unexplored** | 0.0–0.2 | lift@5% has lower SE than lift@1%; more reliable signal for 50-iter proxy |
| F1 at optimal threshold as proxy | **Unexplored** | 0.0–0.1 | If F1 is a business metric, optimizing for it directly |

### E3. Search Space Improvements

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Wider XGB depth range (3–15) | **Unexplored** | 0.0–0.2 | Current range 4–10 may miss very deep or very shallow optima |
| XGB reg_alpha + reg_lambda joint search | **Unexplored** | 0.0–0.2 | L1+L2 regularization joint search may find better regularization than separate |
| LGBM min_split_gain search | **Unexplored** | 0.0–0.1 | Controls minimum gain required to make a split; may reduce overfit |
| Warm-starting Optuna from PRIORS | **Unexplored** | 0.1–0.2 | Initialize TPE with known-good HPs from creditcard campaign as warm start |

---

## F. Ensemble Methods

### F1. Blending Strategies

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Hill climbing (greedy model addition) | **Unexplored** | 0.1–0.3 | Start with best single model; at each step, try adding each remaining model (with equal weights or re-optimized weights) and keep the addition only if val lift@1% improves; repeat until no model adds value. Implementation: score all 7 existing models individually, then greedily expand the ensemble. This selects a subset with diversity > marginal cost, often outperforming all-model ensembles. |
| Power averaging (geometric mean of probabilities) | **Unexplored** | 0.0–0.2 | p_ensemble = (p1 × p2 × ... × pN)^(1/N); better than arithmetic mean for calibrated probs |
| Rank averaging (average percentile ranks, not probabilities) | **Unexplored** | 0.0–0.2 | Robust to calibration differences between models; often used when models have different scales |
| Multiple seed averaging (same model, k different seeds) | **Unexplored** | 0.1–0.2 | Train same architecture with 5+ random seeds; average reduces variance without adding models |
| Differential evolution for blend weights | **Unexplored** | 0.0–0.1 | Global optimization of weights; may find better solution than Nelder-Mead |

### F2. Stacking Variants

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Proper k-fold OOF stacking (4 folds: digit-groups) | Partial | 0.2–0.8 | Round 24 was 50/50 — not true k-fold. True OOF: train on 3 digit-groups, meta-learn on 1; completely leak-free |
| Multi-level stacking (L2 meta on L1 meta) | **Unexplored** | 0.1–0.3 | Stack the stacker; Kaggle winning solutions often use 2-3 levels |
| Feature stacking (OOF predictions as new features) | **Unexplored** | 0.1–0.3 | Add base model OOF predictions as additional features alongside original features in a second-level model |
| Stacking with AUC-PR-optimized meta-learner | **Unexplored** | 0.1–0.2 | Current meta = logistic regression (log-loss); explicitly optimize for AUC-PR |
| Ridge regression meta-learner | **Unexplored** | 0.0–0.2 | More regularized than logistic; may generalize better with limited val data |

### F3. Diversity-Driven Ensemble

> **Principle:** Ensemble error = bias² + variance. Diversity (low pairwise prediction correlation) reduces variance. The three axes of diversity are: **data** (different subsets/windows), **architecture** (different model families and objectives), **features** (different views of the same data). Intentional diversity along all three axes produces ensembles that outperform any single model even when individual members are weaker.

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Diverse base model strategy (intentional multi-axis diversity) | **Unexplored** | 0.2–0.5 | Explicitly build models that differ across 3 axes: (1) architecture — CB/LGBM/XGB (different tree-split logic), (2) objective — log-loss vs focal loss vs AUC-PR, (3) training view — tabular-only vs hybrid vs embedding-only. Models that disagree on hard cases are the highest-value ensemble members. Measure pairwise prediction rank correlation (Spearman) — pairs with ρ < 0.85 are worth keeping together. |
| Model trained on different temporal windows | **Unexplored** | 0.1–0.3 | Train one model on 2024-11 to 2025-03, another on 2025-01 to 2025-06; temporal diversity |
| Model trained on different feature subsets (random) | **Unexplored** | 0.0–0.2 | Column subsampling at model level (not tree level); adds structural diversity |
| Models with different downsampling ratios in ensemble | **Unexplored** | 0.1–0.3 | One model at 5:1, one at 10:1, one at 20:1; different recall/precision tradeoffs |
| Models with different training objectives in ensemble | **Unexplored** | 0.1–0.4 | Ensemble one model trained with log-loss, one with focal loss (γ=2), one with AUC-PR objective; each finds a different region of the score space; their union covers more positives in top 1% |

---

## G. Validation Strategies

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| k-fold CV within training digits (C3 suggested) | **Unexplored** | Reduces SE from 0.50→0.25 | Natural 4-folds: digits (0-1),(2-3),(4-5),(6-7). Would make all improvements detectable. Requires C3 |
| Repeated k-fold (k=4, n_repeats=3, different shuffles) | **Unexplored** | SE reduction further | Averages across multiple fold assignments; more stable estimate |
| Adversarial validation (train vs OOT classifier) | **Unexplored** | diagnostic | Identify features that distinguish 2024-2025 training from 2025-07 OOT; features with high importance → temporal shift risk |
| GroupKFold by individual_id | **Unexplored** | SE reduction | Ensures same member never appears in both train and val folds; prevents member-level leakage |
| Monte Carlo cross-validation | **Unexplored** | 0.0–0.1 | Random train/val splits (not k-fold); more flexible but higher variance |

---

## H. Calibration & Post-processing

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Platt scaling (sigmoid fit on val predictions) | **Unexplored** | 0.0–0.1 | Improves probability calibration; may improve AUC-PR even if lift@1% unchanged |
| Isotonic regression calibration | **Unexplored** | 0.0–0.1 | Non-parametric calibration; more flexible than Platt |
| Temperature scaling | **Unexplored** | 0.0–0.1 | Single parameter T divides logits; simple, robust calibration |
| Venn-Abers calibration | **Unexplored** | 0.0–0.1 | Gives guaranteed valid prediction intervals; strongest theoretical calibration |
| Threshold optimization for F1 | **Unexplored** | n/a (F1 only) | Binary decision threshold that maximizes F1; does not affect ranking metrics |
| Threshold optimization for precision@1% | **Unexplored** | n/a (outreach only) | Optimize for precision in the top-1% flagged rather than lift ratio |
| Prediction smoothing (ensemble across nearby thresholds) | **Unexplored** | 0.0–0.1 | Average predictions at slightly different thresholds for stability |

---

## I. Generalization / Distribution Shift

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Pseudo-labeling on OOT (2025-07 to 2025-09) | **Unexplored** | 0.1–0.5 (uncertain) | Run champion model on OOT; high-confidence predictions (score > 0.9 → positive; score < 0.02 → negative) added to training. Risk: temporal shift may hurt. Validate on OOT before committing. |
| OOT-weighted training (recent months upweighted) | **Unexplored** | 0.0–0.3 | Give higher sample weight to 2025-05/06 training rows to match OOT distribution (2025-07) |
| Domain adaptation (reduce train-OOT gap) | **Unexplored** | 0.0–0.2 | Align train and OOT feature distributions via importance weighting |
| Monotonic constraints on clinical risk features | **Unexplored** | 0.05–0.2 | eng_ip_score, eng_chronic_score, er_clm_cnt_1yr should monotonically predict IP6. Enforcing this prevents counterintuitive splits and improves OOT generalization. XGBoost/LightGBM/CatBoost all support. |

---

## J. Feature Selection (beyond round 4)

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Permutation importance (model-agnostic, model-level) | **Unexplored** | 0.1–0.3 | Round 4 used native CatBoost importance (split-based); permutation is more reliable |
| Boruta algorithm (wrapper selection) | **Unexplored** | 0.1–0.3 | Shadow feature competition; identifies truly important features vs noise at statistical confidence |
| Recursive Feature Elimination (RFE) | **Unexplored** | 0.0–0.2 | Iteratively removes least important features; finds minimal predictive set |
| Stability selection | **Unexplored** | 0.0–0.2 | Runs feature selection on many data subsamples; keeps features selected consistently |
| SHAP-based selection on champion ensemble | **Unexplored** | 0.1–0.2 | Round 6 SHAP was on a single model; run on the 7-model ensemble to see aggregate feature importance |
| Mutual information feature ranking | **Unexplored** | 0.0–0.1 | Model-free; captures non-linear dependence between features and target |

---

## K. Semi-supervised / Label Efficiency

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Label propagation on member similarity graph | **Unexplored** | 0.0–0.2 | Members with similar features to confirmed IP6 cases may get soft positive labels |
| Self-training (iterative pseudo-labeling) | **Unexplored** | 0.1–0.3 | Multiple rounds of pseudo-labeling with progressively lower confidence threshold |
| Co-training (two views: tabular vs embedding) | **Unexplored** | 0.0–0.2 | Train two models (tabular-only, embedding-only); each labels unlabeled examples for the other |
| Consistency regularization (Mixup) | **Unexplored** | 0.0–0.2 | Linear interpolation between training pairs; augmentation that improves calibration and smoothness |

---

## L. Meta-learning / Multi-task

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Multi-task learning (jointly predict ip6 AND sum_ip6_admits) | **Unexplored** | 0.1–0.3 | Jointly predict the binary flag and count; shared representation may improve the binary task |
| Auxiliary loss (predict ip6 AND er_next_3mo) | **Unexplored** | 0.0–0.2 | ER in next 3 months is an easier-to-learn proxy; auxiliary task provides training signal |
| Transfer from creditcard campaign champion | **Unexplored** | 0.0–0.1 | Use creditcard campaign's best feature engineering patterns as inspiration; limited direct transfer |

---

## Already Explored (complete record)

| Technique | Status | Best result | Rounds |
|---|---|---|---|
| Feature set comparison (tab/emb/hybrid) | Done ✓ | hybrid best | R1-3 |
| CatBoost native importance feature selection | Done ✓ | +0.018 marginal | R4, R19 |
| HP search with lift@1% proxy (all families) | Done — Dead-end | Never beat defaults | R5,7,9,11,13 |
| HP search with AUC-ROC proxy (XGB seed=42) | Done ✓ BREAKTHROUGH | **+0.446 → 23.174** | R25 |
| HP search with AUC-ROC proxy (CB, LGBM) | Done | Both discarded | R26,27 |
| HP search with AUC-ROC proxy (XGB seed=7) | Done | Worse (22.762) | R28 |
| Model family comparison (CB/LGBM/XGB) | Done ✓ | LGBM best (22.316) | R8,12 |
| Equal-weight N-model mean ensemble | Done ✓ | 7-model=23.174 | R14-29 |
| Scipy-optimized N-model blend weights | Done ✓ | Same as equal-weight within noise | R16-29 |
| Domain feature engineering (5 IP/chronic/lab) | Done ✓ | +0.018 marginal | R19 |
| Additional eng features (ER, severity) | Done — Dead-end | Hurt performance | R20,21 |
| OOF weight optimization (50/50 holdout) | Done ✓ | Confirms in-sample ≈ OOF | R24 |
| SHAP analysis on single model | Done ✓ | 50/50 emb/tab split | R6,14 |
| RandomForest in ensemble | Done — Dead-end | Too weak (20.016), dragged ensemble down | R15 |

## Excluded by Reasoning

| Technique | Reason |
|---|---|
| LambdaRank / LambdaMART loss | User confirmed: classification problem; contradicts AUC-PR and F1 goals |
| Neural nets (TabNet etc.) without GPU | No GPU available; expected runtime 10–100× GBDT; within HARD_TIMEOUT only if very small |
| sklearn GBM (GradientBoostingClassifier) | DEAD_ENDS: exceeds 90s timeout at 100 trees |
| DART booster | DEAD_ENDS (creditcard): exceeds timeout at 500 trees |
| SMOTE + scale_pos_weight combined | DEAD_ENDS: double-counts imbalance, inverts calibration |
| tree_method=approx (XGBoost) | DEAD_ENDS: too slow on 170K+ rows |
