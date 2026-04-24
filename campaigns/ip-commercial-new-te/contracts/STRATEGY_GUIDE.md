---
schema_version: 2
campaign_id: "ip-commercial-new-te"
document_type: "strategy_guide"
scope: "planner_advisory"
binding: "advisory"
updated_at: "2026-04-24"
notes: >
  Advisory only. Planner SHOULD consult but MAY override with stated reasoning.
  Updated to reflect three-way feature-set comparison, mandatory feature selection,
  model family diversity, and val-only keep/discard with test/OOT for reporting.
---

# Strategy Guide — IP Commercial New TE Campaign

## 0. The strategic hierarchy

```
1. Feature-set comparison (embedding_only vs tabular_only vs hybrid)   ← highest ROI: answers the core question
2. Feature selection within each feature set                            ← reduce noise, enable faster HP search
3. HP search across model families (CatBoost, LightGBM, XGBoost, LR)  ← third: extract signal from best config
4. Ensemble / stacking                                                  ← last: marginal gains only
```

**Three-way comparison is mandatory before committing to HP tuning.**
An embedding_only model that beats tabular_only with default params changes the entire strategy.
Feature selection within each set is required before committing to HP search — it reduces dimensionality (256 embeddings is large) and prevents HP search from optimizing over noise features.

**Keep/discard rule:** val set (digit 8, in-time) only. Test (digit 9) and OOT are Reviewer-reported for generalization tracking — never used in the verdict.

---

## 1. Evidence-conditioned triggers

Check every condition below that is true. Earlier rows take precedence. The first unresolved implication is the default next move.

| Evidence condition | Strategic implication |
|---|---|
| No embedding_only baseline exists | A_validate: embedding_only with default CatBoost. Answers the standalone question. |
| No tabular_only baseline exists | A_validate: tabular_only with default CatBoost. Required floor. |
| No hybrid baseline exists | A_validate: hybrid with default CatBoost. Required ceiling before feature selection. |
| All 3 baselines exist; feature selection not done on best feature set | A_feature: run tools/feature_selection on the best feature set's best model. Get selected_features.json. |
| Feature selection done; no systematic HP search yet | A_hp: Optuna on the feature-selected config across wide HP range. |
| Only CatBoost tried; 2+ rounds done | A_model: try LightGBM (or XGBoost) with same feature set. Default-parameter comparison, one family at a time. |
| 2+ model families compared; Δ > 2× noise_floor between them | HP-tune the winner. Stop exploring families until winner is tuned. |
| 2+ model families within noise_floor of each other | Tune both briefly (1–2 rounds each) before committing. |
| 2+ A_hp rounds on same family+feature_set; Δ shrinking toward noise_floor | Move to A_feature (try different feature subset) or A_diagnose. |
| A_feature round discarded | Inspect SHAP before declaring dead-end. Check if features add signal masked by other changes. |
| consecutive_discards ≥ 3 | A_diagnose before any structural change. See §3.7. |
| Target gap ≤ 2× bootstrap_se | Measurement bottleneck. Trigger C3 to upgrade CV scheme. |
| Individually tuned, complementary models available | A_ensemble via tools/stacking (logistic meta-learner). |

### Pre-selection reasoning (required)

Before committing to an action type, enumerate 2–3 candidates, estimate expected Δ for each using PRIORS.md, results.tsv history, and §2 ROI priors. Record reasoning in NEXT_EXPERIMENT.md §2.

---

## 2. Expected Δ priors by action type

| Action type | Typical Δ (lift@1%) | When highest ROI | When low ROI |
|---|---|---|---|
| A_validate (any feature set baseline) | ~0 (establishes floor) | Before that feature set has been tested | Never skip |
| A_feature (feature selection) | 0.2–1.0 | After baselines; before HP search; large feature space (256+ dims) | After SHAP shows all features contribute |
| A_hp (Optuna) | 0.5–2.5 | First systematic tune; wide search space | After 2+ A_hp rounds with shrinking Δ |
| A_model (new family) | 0.3–1.5 | Only one family tried; early campaign | 3+ families tried, one clearly dominates |
| A_ensemble (stacking) | 0.2–0.8 | 2+ individually tuned, complementary families | One family leads by >2× noise_floor |
| A_diagnose | ~0 (resolves uncertainty) | After plateau; before structural changes | Never skip after C2 fires |
| A_imbalance | 0.0–0.3 | auto_class_weights behavior in doubt | Balanced already calibrated |

---

## 3. Decision heuristics

### 3.1 All three feature sets must be baselined first

- **Order:** embedding_only → tabular_only → hybrid (or any order, all three required before moving on).
- **Why:** Cannot choose which feature set to invest HP search in without all three baselines. Embedding_only vs tabular_only answers the standalone question; hybrid answers the ceiling question.
- **Known from rounds 1–2:** tabular_only=21.578, hybrid=22.213. Embedding_only still missing.

### 3.2 Feature selection is mandatory before HP search on large feature spaces

The campaign has 256 embedding dimensions + 534 tabular features. Not all contribute signal.

**When to run:** After all three baselines are established and the best feature set is identified.

**How:**
```python
from runner.tools.feature_selection import select_features
result = select_features(
    X_train, y_train, X_val, y_val,
    feature_cols=feature_cols, embedding_features=emb_features,
    method='permutation', top_k=100,   # or top_k=150 for hybrid
    model=champion_model,
)
# Save selected_features to experiment_helpers/<exp_id>/selected_features.json
```

**Apply to each feature set separately:**
- embedding_only: select top-K from 256 embeddings. Expected to drop 50-100 near-zero-importance embeddings.
- tabular_only: select top-K from 534 tabular. Expected to drop low-signal demographic and redundant counts.
- hybrid: select top-K from 790 combined. Tells you which embeddings add value beyond tabular.

**Keep/discard:** if selected feature set (fewer features) improves or is within noise_floor of full feature set → keep (simpler model with comparable performance). If it regresses > noise_floor → discard and note which features were critical.

### 3.3 Model family diversity

Do not commit all rounds to CatBoost. After CatBoost is baseline-validated, try:

| Family | When to try | Notes |
|---|---|---|
| **LightGBM** | Round 4–6, after CatBoost baselines | Fast, strong, often competitive with CatBoost on tabular. Use `auto_class_weights` equivalent = `class_weight='balanced'` |
| **XGBoost** | Round 5–7, after LightGBM compared | Canonical GBDT, different regularization profile |
| **LogisticRegression** | For embedding_only only | Linear baseline on embeddings — establishes linear separability of the embedding space |
| **Random Forest** (sklearn) | Optional | Rarely beats GBDT but useful for interpretability comparison |

**Avoid:** neural networks (no GPU, tabular data, GBDT usually wins), sklearn GBM (too slow — listed in PRIORS known_bad).

**Model family comparison rule:** Use the same feature set (e.g., hybrid + selected features) when comparing families. One variable at a time.

### 3.4 Hyperparameter search

- **Never hand-pick HP values.** Use `tools/optuna_search` or Optuna in train.py.
- **Proxy with fewer iterations, then promote to full.** The large dataset (508K train rows) makes each iteration ~0.3-0.5s — budget Optuna accordingly.
- **CatBoost canonical search space:** depth 5–9, lr 0.01–0.15, l2_leaf_reg 1–15, subsample 0.5–1.0, colsample_bylevel 0.5–1.0, min_data_in_leaf 5–50.
- **LightGBM search space:** num_leaves 31–255, lr 0.01–0.15, min_child_samples 10–100, feature_fraction 0.5–1.0, bagging_fraction 0.5–1.0.

### 3.5 Imbalance handling

- 10:1 downsampling is applied to training set in prepare.py (frozen).
- CatBoost: `auto_class_weights='Balanced'` is the default and should be kept.
- LightGBM: `class_weight='balanced'` or `is_unbalance=True` (but NOTE: `is_unbalance=True` is in PRIORS known_bad — inverts probabilities. Use `class_weight='balanced'` instead).
- Do not add SMOTE on top of 10:1 downsampling — double-correction.

### 3.6 Test and OOT reporting

The Reviewer MUST compute and record test and OOT metrics in REVIEW.md for every kept experiment, even though they don't affect the verdict.

**In train.py:** Executor should compute and print test metrics (X_test, y_test from get_splits). For OOT: load separately from parquet with `filters=[("index_dt", ">", OOT_CUTOFF_DATE)]`.

**What to track per round:**
- `val_lift_1pct`, `test_lift_1pct`, `oot_lift_1pct`
- `val_auc_roc`, `test_auc_roc`, `oot_auc_roc`
- Gap between val and OOT lift@1% — a large gap (>3 lift points) signals overfitting to the validation split.

### 3.7 Diagnose before any structural change (A_diagnose-first rule)

When C2 plateau fires (≥3 consecutive discards), the next plan MUST be A_diagnose:
1. SHAP feature importance via `tools/shap_report`: embedding vs. tabular proportion in top-K.
2. Error analysis: score distribution on val positives vs. negatives.
3. CI check: `tools/bootstrap_ci` — is bootstrap_se small enough that the target gap is detectable?

Outputs guide next action:
- High embedding proportion in SHAP top-10 → `A_feature` targeting tabular features the model ignores.
- Low embedding proportion → embeddings not contributing after feature selection; consider embedding_only HP tuning.
- SE > noise_floor / 2 → C3 to upgrade CV scheme before continuing.

---

## 4. Anti-patterns

- **Skipping embedding_only baseline:** Cannot answer the primary research question without it.
- **HP tuning before feature selection:** Optimizing HPs over 790 features (many noisy) wastes trials on noise. Select first.
- **Using test/OOT for keep/discard:** Test is only for reporting. Only val drives verdicts.
- **Only CatBoost for 100 rounds:** Model family comparison is required. LightGBM and XGBoost must be tried.
- **Ensembling when one family dominates:** If best model leads second by >2× noise_floor, stacking dilutes signal.
- **Using is_unbalance=True in LightGBM:** Known dead-end (inverts probabilities). Use class_weight='balanced' instead.
- **Changing feature set AND model family in same round:** One variable at a time.

---

## 5. Integration with campaign history

Priority order for planning:
1. **DEAD_ENDS.md** — Hard vetoes.
2. **results.tsv** (via `tools/results_query --order-by val_lift_1pct`) — Quantitative history.
3. **PRIORS.md** — Cross-campaign lessons.
4. **This strategy guide** — Apply §1 triggers, then §2 ROI priors, then §3 heuristics.
5. **NOTEBOOK.md** — Working observations and hypotheses.

**Current campaign state (as of round 2):**
- embedding_only: NOT YET TESTED ← primary open question
- tabular_only best: 21.578 (round 1, CatBoost default)
- hybrid best: 22.213 (round 2, CatBoost default)
- Feature selection: NOT YET DONE
- Model families tried: CatBoost only ← must diversify
