---
schema_version: 2
campaign_id: "ip-commercial-new-te"
document_type: "strategy_guide"
scope: "planner_advisory"
binding: "advisory"
updated_at: "2026-04-24"
notes: >
  Advisory only. Planner SHOULD consult but MAY override with stated reasoning.
  Feature set (tabular_only / hybrid / embedding_only) is a first-class experiment
  dimension in this campaign, distinct from model family or HP search.
---

# Strategy Guide — IP Commercial New TE Campaign

## 0. The strategic hierarchy

```
1. Feature set choice (tabular_only vs hybrid)   ← highest ROI; test early
2. Model family capacity                          ← second; CatBoost is the default
3. HP search within best family + feature set     ← third
4. Ensemble / calibration                         ← last; marginal gains only
```

**Uniqueness of this campaign:** The feature set dimension (`tabular_only`, `embedding_only`, `hybrid`) must be explored before committing to HP search. An HP-optimized tabular model might lose to a default hybrid model. Establish both baselines first.

---

## 1. Evidence-conditioned triggers

| Evidence condition | Strategic implication |
|---|---|
| No baseline exists | A_validate: CatBoost default params on tabular_only. Sets floor in one round. |
| tabular_only baseline exists; no hybrid baseline | A_validate: same model on hybrid. Measures embedding lift directly. |
| hybrid Δ over tabular_only established (positive or negative) | Commit to the winning feature set. HP search on that set. |
| hybrid and tabular_only within noise_floor of each other | Tune both briefly (1–2 rounds each) before committing. |
| Champion feature set + family selected; no systematic HP search yet | A_hp: Optuna with wide search space. Do not hand-pick HP values. |
| 2+ A_hp rounds on same family/feature_set; Δ shrinking toward noise_floor | Move to A_feature or A_diagnose. |
| consecutive_discards ≥ 3 | Run A_diagnose before any structural change. See §3.7. |
| Target gap ≤ 2× bootstrap_se | Bottleneck is measurement. Trigger C3 to upgrade CV scheme. |

### Pre-selection reasoning (required)

Before committing to an action type, enumerate 2–3 candidates, estimate expected Δ for each using PRIORS.md and results.tsv history, and choose the candidate with highest expected Δ. Record the reasoning in NEXT_EXPERIMENT.md §2.

---

## 2. Expected Δ priors by action type

| Action type | Typical Δ (lift@1%) | When highest ROI | When low ROI |
|---|---|---|---|
| A_validate (tabular baseline) | ~0 (establishes floor) | Round 1 — no baseline exists | Never skip |
| A_validate (hybrid) | 0.3–1.5 | Round 2 — tabular baseline exists | After hybrid tested |
| A_hp | 0.2–0.8 | Champion family + feature set confirmed | After 2+ A_hp rounds with shrinking Δ |
| A_feature | 0.1–0.5 | SHAP shows low-importance features; domain feature ideas untested | PCA-style embedding space with no raw clinical features to engineer |
| A_ensemble | 0.1–0.3 | Two individually tuned, complementary models | One model leads by > 2× noise_floor |
| A_diagnose | ~0 (resolves uncertainty) | After plateau; before structural changes | Never skip after C2 fires |
| A_imbalance | 0.0–0.3 | Downsampling ratio not yet explored | scale_pos_weight already searched |

---

## 3. Decision heuristics

### 3.1 Feature set first

- **Rounds 1–2:** Always run tabular_only then hybrid with identical model configs. The Δ between these two rounds is the cleanest measure of embedding value.
- **After establishing Δ(hybrid − tabular):** If positive and > noise_floor, commit to hybrid for all future rounds. If negative, commit to tabular_only and check PRIORS.md.
- **embedding_only:** Run only for diagnostic purposes (e.g., to understand standalone embedding power). Not a primary experiment target.

### 3.2 Hyperparameter search

- **Never hand-pick HP values.** Use `tools/optuna_search` or declare a search space inside `train.py` using Optuna.
- **CatBoost canonical ranges:** depth 5–9, learning_rate 0.01–0.05, iterations 1000–3000 with od_wait 60–120. Start wide, narrow after first Optuna round.
- **auto_class_weights='Balanced'** is the default imbalance correction. Try `scale_pos_weight` as an alternative only if Balanced underperforms.

### 3.3 Feature engineering

- Embedding features are dense vectors — do not interact them with each other (too many dimensions, no interpretable basis).
- Tabular feature engineering: interactions between Amount-equivalent raw clinical features (e.g., total claim count × chronic flag) may add signal. Domain knowledge required.
- Test one feature group per round.

### 3.4 Imbalance handling

- The training set uses 10:1 negative downsampling (fixed in prepare.py).
- `auto_class_weights='Balanced'` in CatBoost adds a second layer of correction. This compound is the default; test removing one layer if AUC-PR looks miscalibrated.
- Do not add SMOTE — redundant with downsampling and distorts calibration.

### 3.5 Ensembling

- Only ensemble after ≥ 2 individually tuned models.
- Verify complementarity: SHAP profiles of tabular-only and hybrid models may overlap heavily. If they do, blending adds noise. Run A_diagnose first.

### 3.6 Diagnosing stalls

- Run `tools/bootstrap_ci` on the current best. If SE > 0.3 (noise_floor), room exists but measurement is noisy.
- SHAP: what fraction of top-10 features are embeddings vs. tabular? If embeddings dominate, tabular engineering has low ROI.

### 3.7 Diagnose before structural change

When C2 plateau fires (≥3 consecutive discards), the next plan MUST be A_diagnose. It must produce:
1. SHAP feature importance: embedding vs. tabular proportion in top-K features
2. Error analysis: where does the champion fail? Score distribution on val positives vs. negatives.
3. CI check: is bootstrap_se small enough that target gap is detectable?

---

## 4. Anti-patterns

- **Skipping tabular_only baseline:** Without a tabular-only reference, the embedding lift cannot be attributed. Always round 1.
- **HP tuning before feature set is decided:** Optimal HPs on tabular_only and hybrid may differ substantially. Commit to a feature set first.
- **Ensembling when one feature set dominates:** If hybrid leads tabular_only by > 2× noise_floor, blending the two dilutes signal.
- **Changing multiple things at once:** One controlled change per round (feature_set OR model OR HPs — not two at once).

---

## 5. Integration with campaign history

When planning, synthesize in this priority order:
1. **DEAD_ENDS.md** — Hard vetoes.
2. **results.tsv** (via `tools/results_query --order-by val_lift_1pct`) — Quantitative history.
3. **PRIORS.md** — Cross-campaign lessons.
4. **This strategy guide** — Apply §1 triggers first, then §2 ROI priors.
5. **NOTEBOOK.md** — Working observations.
