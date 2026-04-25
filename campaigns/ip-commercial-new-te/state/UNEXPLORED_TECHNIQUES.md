---
schema_version: 1
campaign_id: "ip-commercial-new-te"
purpose: "Positive exploration frontier — counterpart to DEAD_ENDS.md. Tracks which technique CLASSES have and haven't been tried. Planner reads this every round and must justify skipping any Unexplored class with Expected Δ > noise_floor when consecutive_discards ≥ 2."
last_updated: "2026-04-25"
---

# Unexplored Techniques — ip-commercial-new-te

**Planner rule:** Before writing NEXT_EXPERIMENT.md, scan this file. If `consecutive_discards ≥ 2` AND any class is `Unexplored` with `Expected Δ > 0.3`, you MUST either: (a) choose that class, or (b) write one explicit sentence explaining why you're skipping it given the current evidence.

If `consecutive_discards ≥ 3` (C2 fires): you MUST select from an Unexplored class unless ALL have been tried or a specific dead-end reason exists.

---

## Re-imbalancing (data-level)

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| ADASYN (adaptive synthetic oversampling) | **Unexplored** | 0.1–0.5 | Secondary resampling in train.py after get_splits() — does NOT require changing prepare.py |
| Different downsampling ratios (5:1, 20:1) | **Unexplored** | 0.1–0.4 | Override the 10:1 in train.py by discarding more/fewer negatives after get_splits() |
| SMOTE standalone (no scale_pos_weight) | **Unexplored** | 0.0–0.3 | DEAD_END is SMOTE + scale_pos_weight together. SMOTE alone with balanced class weights is untested. |
| Tomek links / cluster centroid undersampling | **Unexplored** | 0.0–0.2 | Cleans noisy majority-class boundary cases |

## Re-imbalancing (model-level)

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Focal loss (γ > 0 custom XGB/LGBM objective) | **Unexplored** | 0.1–0.4 | Reduces weight of easy negatives; focuses training on hard boundary cases near the top-1% threshold |
| Custom class weights optimized for AUC-PR | **Unexplored** | 0.1–0.3 | Neither 1:1 Balanced nor 591:1 inverse frequency — tune the weight to maximize AUC-PR directly |
| Scale_pos_weight search (XGBoost) | **Unexplored** | 0.05–0.2 | Only tried at fixed ratio=10 matching downsampling; unexplored: ratio 2–50 as HP |

## Feature encoding

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Target encoding for categoricals | **Unexplored** | 0.1–0.4 | county_cd/division/cust_segment have meaningful IP6 rate variation by value; current integer codes waste this. Smoothed target encoding via cross-validation |
| CatBoost native string categorical handling | **Unexplored** | 0.1–0.3 | Currently integer-encoded workaround due to prepare.py constraint. Requires rebuilding split cache with string values |

## Ensemble / stacking

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Proper k-fold OOF stacking (4 folds on digits 0-7) | Partially explored | 0.2–0.8 | Round 24 used 50/50 holdout — not true k-fold. True OOF: train on 3 digit-groups, meta-learn on 1 |
| Stacking with AUC-PR as meta-learner objective | **Unexplored** | 0.1–0.3 | Current meta-learner (logistic regression) optimizes logistic loss; explicit AUC-PR optimization may give better calibrated ensemble |

## Regularization / structural

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Monotonic constraints on risk features | **Unexplored** | 0.05–0.2 | Domain knowledge: eng_ip_score, eng_chronic_score, er_clm_cnt_1yr should monotonically predict IP6. Enforcing this reduces val-set overfitting. |
| Adversarial validation (train vs OOT) | **Unexplored** | 0.1–0.3 | Identify features that distinguish train from OOT; drop or downweight them to improve generalization |

## Post-processing

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Calibration (Platt scaling / isotonic regression) | **Unexplored** | 0.0–0.1 | Adjusts probability outputs for better calibration; may improve lift at non-top-1% thresholds and AUC-PR |
| Threshold optimization for F1 | **Unexplored** | n/a (F1 only) | Find the decision boundary that maximizes F1; doesn't affect ranking metrics |

## Generalization / distribution shift

| Technique | Status | Expected Δ lift@1% | Notes |
|---|---|---|---|
| Pseudo-labeling on OOT (2025-07 to 2025-09) | **Unexplored** | 0.1–0.5 (uncertain) | High-confidence OOT predictions used as pseudo-labels added to training. Risk: temporal shift may hurt. |
| OOT-aware training (temporal weighting) | **Unexplored** | 0.0–0.3 | Up-weight recent training months to match OOT distribution shift |

## Already explored (for reference)

| Technique | Status | Best result | Round |
|---|---|---|---|
| Feature set comparison (tabular/emb/hybrid) | ✓ Done | hybrid=22.213 beats emb=18.162 | R1-3 |
| CatBoost native importance feature selection | ✓ Done | Marginal gain +0.018 | R4, R19 |
| HP search (Optuna, lift@1% proxy) | ✓ Done — DEAD-END | Never beat defaults | R5,7,9,11,13 |
| HP search (Optuna, AUC-ROC proxy) for XGB | ✓ Done — BREAKTHROUGH | +0.446 (23.174) | R25 |
| HP search (AUC-ROC proxy) for CB, LGBM | ✓ Done | Both discarded; XGB is unique | R26,27 |
| 3-family model comparison (CB/LGBM/XGB) | ✓ Done | LGBM best standalone (22.316) | R8,12 |
| N-model scipy-optimized ensemble | ✓ Done | 7-model=23.174 is ceiling | R14-29 |
| Domain feature engineering (5 features) | ✓ Done | +0.018, marginal | R19 |
| Adding more eng features | ✓ Done — DEAD-END | Adding features beyond 5 hurt | R20,21 |
| OOF weight optimization (50/50 holdout) | ✓ Done | Confirms in-sample ≈ OOF | R24 |

## Excluded by reasoning (not dead-ends, just lower priority)

| Technique | Reason for exclusion |
|---|---|
| LambdaRank/LambdaMART loss | User confirmed: classification problem; ranking loss contradicts AUC-PR and F1 goals |
| Neural networks / MLP | No GPU; tabular data; GBDTs consistently win in this setting |
| sklearn GBM | Known dead-end from creditcard campaign: exceeds 90s timeout at 100 trees |
