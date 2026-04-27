---
schema_version: 2
campaign_id: "apr21-creditcard-fraud"
document_type: "strategy_guide"
scope: "planner_advisory"
binding: "advisory"
updated_at: "2026-04-26"
notes: >
  This document is ADVISORY, not contractual. The Planner SHOULD consult it
  when selecting hypotheses, but MAY override any heuristic with stated reasoning.
  Heuristics are drawn from ML engineering best practice and prior campaign lessons.
  schema_version 2: replaced phase table and budget rule with evidence-conditioned
  triggers; added pre-selection reasoning requirement.
  2026-04-26: removed A_diagnose-first mandate; plateau diagnosis now handled
  automatically by the Historian role (see §3.7 for Planner guidance).
---

# Strategy Guide — ML Experiment Planning Heuristics

## 0. The strategic hierarchy

Every ML campaign has the same ROI structure across layers. Higher layers have
higher expected gain *when untapped*; lower layers only extract what the layer
above has already unlocked.

```
1. Data / feature representation   ← highest ROI when untapped
2. Model family capacity            ← second; pick the right inductive bias
3. HP search within best family     ← third; extract signal from good tool
4. Ensemble / calibration           ← last; marginal gains only
```

**This is not a fixed sequence.** Use the evidence-conditioned triggers in §1 to
determine where you currently are. You may skip layers when evidence rules them
out — but state why when you do.

**Why the order holds:** An ensemble of poorly tuned models is worse than one
well-tuned model. HP search on the wrong family cannot overcome inductive-bias
mismatch. Feature engineering on a model that ignores half the feature space is
uninformative. Respect the hierarchy unless you have evidence it doesn't apply.

---

## 1. Evidence-conditioned triggers

Do not determine your next action from budget consumed or round count.
Determine it from what the data actually shows.

Check every condition below that is true for the current campaign state.
Earlier rows take precedence when multiple match. The first unresolved
implication is your default next move.

| Evidence condition | Strategic implication |
|---|---|
| No baseline exists | Establish one. A_model with simple default (logistic regression or default GBDT). One round, no tuning. Goal: set a comparison floor. |
| Fewer than 2 distinct model families in results.tsv | Try ≥ 1 alternative family before investing in tuning. Default-parameter rankings can reverse after tuning; cheap comparison now saves wasted HP rounds later. |
| 2+ families tried; best leads by > 2× noise_floor | Family search is done. Commit to the winner. Further family exploration has low expected Δ. |
| 2+ families within noise_floor of each other | Tune both briefly (1–2 rounds each) before committing. The winner after tuning often differs from the default-parameter ranking. |
| Champion family selected; no systematic HP search yet | A_hp is the next highest-ROI layer. Run Optuna with a wide search space before moving to features or ensemble. |
| 2+ A_hp rounds on same family; Δ shrinking toward noise_floor | HP space likely saturated. Move to A_feature or A_model — more HP search on the same family has low expected Δ. |
| A_feature round discarded; feature importance not inspected | Do not declare FE a dead end yet. Inspect permutation importance on the champion. The features may add signal that other concurrent changes masked. |
| consecutive_discards ≥ 3 (C2 plateau fires) | driver auto-triggers Historian; read `state/STRATEGY_MEMO.md` before next plan. |
| Considering A_ensemble | Verify each candidate is individually tuned AND that their feature importance profiles differ. If one family leads the other by > 2× noise_floor, blending dilutes signal — see §4 anti-patterns. |
| Target gap ≤ 2× bootstrap_se (from tools/bootstrap_ci) | The bottleneck is measurement, not modeling. More experiments will not reliably close this gap. Trigger C3 to upgrade the CV scheme before continuing. |

### Pre-selection reasoning (required before writing the plan)

Before committing to an action type, the Planner MUST:

1. Enumerate 2–3 candidate actions that the evidence-conditioned triggers suggest.
2. For each candidate, estimate expected Δ using `PRIORS.md` known ceilings,
   `results.tsv` history, and this guide's ROI priors (§2).
3. Choose the candidate with the highest expected Δ that is not ruled out by
   `DEAD_ENDS.md` or the conditions above.
4. Record the alternatives and why the chosen action is expected to outperform
   them in `NEXT_EXPERIMENT.md §2 Evidence from memory`.

This reasoning step is auditable: if the estimate is wrong, the Reviewer can
update PRIORS.md or NOTEBOOK.md with the corrected expectation.

---

## 2. Expected Δ priors by action type

These are directional priors, not guarantees. Update them as the campaign
produces evidence that contradicts them.

| Action type | Typical Δ range | When highest ROI | When low ROI |
|---|---|---|---|
| A_feature | 0.005–0.020 | Champion model trained and tuned; feature coverage not inspected | PCA-only feature space already saturated (V1–V28 dominate importance) |
| A_model | 0.005–0.015 | Early campaign; alternative families not yet compared | 2+ families compared and one clearly dominates |
| A_hp | 0.001–0.008 | First systematic tune of a new champion family | After 2+ A_hp rounds on same family with shrinking Δ |
| A_ensemble | 0.001–0.005 | 2+ individually tuned, complementary families | One family leads by > 2× noise_floor; families share feature coverage |
| A_imbalance | 0.000–0.010 | Calibration is visibly off; lift_at_10 lags val_pr_auc | scale_pos_weight already searched; metric is PR-AUC (naturally imbalance-aware) |

**How to use:** For each candidate action in the pre-selection step, look up its
typical Δ range and check whether the "highest ROI" condition holds for the
current campaign state. Prefer the action whose conditions are most favorable.

---

## 3. Decision heuristics (directional, not prescriptive)

These are conditional suggestions. Apply the ones whose conditions match your
state. They supplement the triggers in §1, not replace them.

### 3.1 Model family selection

- **If no baseline exists:** Start with logistic regression or default-parameter
  GBDT. Gives a floor in one round.
- **If only one model family tried and it scored well:** Try at least two
  alternative family before investing in tuning. Different families have
  different inductive biases — you might find a better starting point cheaply.
- **If ≥ 3 families tried and one clearly dominates (Δ > 2× noise_floor):**
  Invest in tuning the winner. Diminishing returns on family search.
- **If two families are close (Δ < noise_floor):** Tune both briefly (10–20% of the total
  rounds each) before committing. The winner after tuning may differ from
  default-parameter rankings.

### 3.2 Hyperparameter search

- **Never hand-pick HP values.** Use Optuna (or equivalent) with a declared
  search space inside `train.py`. LLM intuition about numeric HP values is
  unreliable.
- **Start with wide ranges, then narrow.** First Optuna run: broad (e.g., depth
  3–10, lr 0.01–0.3). If the optimum is interior, keep it. If it's at a
  boundary, expand that direction.
- **Proxy with fewer trees/iterations for speed,** then retrain the final model
  with more. Lets Optuna explore more trials within the time budget.
- **Check for interaction effects.** If one HP (e.g., max_depth) dominates,
  its optimal value may depend on another (e.g., learning_rate). Include both
  in the Optuna space.

### 3.3 Feature engineering

- **Prefer features motivated by domain knowledge or EDA,** not random
  combinations. For tabular data with PCA features (like V1–V28), interactions
  with raw features (Amount, Time) are more likely to help than V-to-V
  interactions.
- **Test one feature group per round.** Adding 10 features at once makes it
  hard to attribute signal. Add a coherent group (e.g., "amount interactions")
  and measure.
- **If feature engineering round is discarded, check feature importance** before
  declaring it a dead end. The features might add signal that other concurrent
  changes masked.

### 3.4 Imbalance handling

- **Never combine two imbalance corrections** (e.g., SMOTE + scale_pos_weight).
  They compound and distort calibration.
- **For tree models on imbalanced data, `scale_pos_weight` is usually
  sufficient.** SMOTE is a second-line option if scale_pos_weight doesn't close
  the gap.
- **Check if the metric is imbalance-sensitive.** PR-AUC is naturally
  imbalance-aware. Adding aggressive resampling may not help and can hurt.

### 3.5 Ensembling

- **Building blocks must be individually strong.** An ensemble of bad models is
  a bad model. Only ensemble after you have ≥ 2 individually tuned models.
- **Verify complementarity before blending.** If the two families' feature
  importance profiles overlap heavily, blending adds noise, not signal. Check
  `state/STRATEGY_MEMO.md` (Historian output after C2 plateau) for a
  complementarity assessment before committing to an ensemble.
- **Prefer simple averaging or stacking over complex schemes.** Blending /
  averaging is easy to debug. Stacking with a meta-learner is the next step if
  averaging plateaus.
- **Watch the time budget.** Ensembles multiply training time. Estimate combined
  runtime before committing.

### 3.6 Diagnosing stalls

- **If 3+ rounds are discarded consecutively,** the problem is likely
  structural, not parametric. Structural causes: wrong loss function, data
  leakage, feature leakage, hitting the Bayes rate.
- **Run bootstrap_ci on the current best.** If CI is tight (se ≤ 0.002), you
  are near the ceiling. If wide (se ≥ 0.010), room exists but measurement is
  noisy.
- **Review what changed between the last keep and the discards.** Narrow the
  root cause before trying another experiment.

### §3.7 Plateau diagnosis (formerly A_diagnose)

The `A_diagnose` action type has been removed. When `consecutive_discards >= plateau_trigger`,
the driver automatically triggers the Historian role before the next Planner turn.
The Historian produces `state/STRATEGY_MEMO.md` with:
- Trajectory narrative and phase classification
- Pattern extraction from CAMPAIGN_JOURNAL.md
- Assumption audit (flags critical unverified assumptions)
- Bottleneck diagnosis with highest-ROI technique recommendation

The Planner reads STRATEGY_MEMO.md as a required input. To propose a targeted verification
experiment, use `action_type: A_validate` with `assumptions_tested: [A-N-N]` in frontmatter.

**How to use the Historian outputs:**

- If champion ignores several features → A_feature targeting those features.
- If two candidate families use meaningfully different feature subsets → A_ensemble
  is warranted (complementarity confirmed by STRATEGY_MEMO.md).
- If bootstrap_se > target_gap / 2 → C3 to upgrade the CV scheme before
  continuing. More experiments on the current split will not produce reliable
  decisions.
- If all features used, no obvious failure pattern, CI adequate → A_model with
  a structurally different approach.

---

## 4. Anti-patterns (general knowledge)

These supplement the problem-specific dead-ends in `DEAD_ENDS.md`. Add to
that file when a dead-end is campaign-specific; add here when it generalizes.

- **Ensembling when one family dominates:** If the best model leads the second
  by > 2× noise_floor on the primary metric, blending dilutes its signal rather
  than complementing it. The weaker model adds noise. Only ensemble when
  families are within noise_floor of each other *and* their feature importance
  profiles differ.
- **Overfitting to validation set:** If you tune for 50+ Optuna trials on one
  holdout, the best trial may overfit the split. Use bootstrap_ci to check
  stability.
- **Ignoring time budget:** Fancy models that timeout produce zero information.
  Estimate runtime before committing.
- **Changing multiple things at once:** Hard to attribute improvement or
  regression. Prefer single-variable experiments.
- **Upgrading model complexity without evidence:** Don't jump to neural nets or
  stacking before exhausting simpler models. Tabular data usually favors GBDTs.
- **Re-trying dead ends with minor tweaks:** If SMOTE didn't work with default
  params, SMOTE with different params also won't work. The mechanism is flawed,
  not the settings.
- **Exploring new families when measurement is the bottleneck:** If target gap
  ≤ 2× bootstrap_se, trying a new model family cannot reliably confirm whether
  it beats the incumbent. Fix the evaluation scheme first (C3), then experiment.

---

## 5. Integration with campaign history

When planning, synthesize these sources in this priority order:

1. **DEAD_ENDS.md** — Hard vetoes. Never retry these patterns.
2. **results.tsv** (via `tools/results_query`) — Quantitative history. What
   worked, what didn't, and by how much.
3. **PRIORS.md** — Cross-campaign lessons. Prior winners/losers that transfer.
4. **This strategy guide** — Directional heuristics. Apply §1 triggers first,
   then §2 ROI priors for pre-selection reasoning, then §3 heuristics.
5. **NOTEBOOK.md** — Working observations. May contain hypotheses worth testing.

Spend ~30% of planning reasoning on history synthesis, ~70% on forward planning.
The pre-selection reasoning step in §1 is the bridge between the two.
