# Critical Analysis: 100 Experiments vs. the ABES Strategy Document

## 1. Overall Budget Allocation: Theory vs. Reality

The strategy document (Section VII, ABES) prescribed a **contextual bandit** with Thompson Sampling, urgency scores, and opportunity scores to dynamically allocate effort. Here's what actually happened:

| Action Type | Actual Count | Actual % | ABES Predicted Behavior |
|---|---|---|---|
| `A_hp` | **55** | **55%** | Should dominate late, but not this heavily |
| `A_feature` | 18 | 18% | Should be ~20-25% at T=100 |
| `A_model` | 12 | 12% | Should be ~15-20% at T=100 |
| `A_ensemble` | 5 | 5% | Reasonable — low urgency unless >=2 competitive |
| `A_validate` | 4 | 4% | Should ramp in last 20% (exp 81-100) |
| `A_imbalance` | 3 | 3% | Reasonable — limited options |
| `A_diagnose` | 3 | 3% | Reasonable — only 3 anomalies |

**Verdict: The agent was massively biased toward A_hp.** The strategy document explicitly warned against this as the mar30 failure mode: "excessive exploitation, zero exploration." While the apr01 run was *better* than mar30 (which was ~80% exploitation), 55% A_hp is still far above what ABES's urgency scores would select.

### Phase-by-Phase Breakdown

| Phase | A_hp | A_model | A_feature | Other |
|---|---|---|---|---|
| Exp 1-30 (early) | 33% | **30%** | 17% | 20% |
| Exp 31-60 (mid) | **57%** | 7% | 13% | 23% |
| Exp 61-100 (late) | **70%** | 2.5% | 22.5% | 5% |

**ABES prescribed**: Early = heavy A_model (urgency high from untried families), then gradual shift to A_hp. The agent did follow this in the first 30 experiments (30% A_model is reasonable), but then collapsed into near-pure A_hp from experiment 31 onward.

## 2. Decision-by-Decision ABES Compliance Audit

### Phase 1: Experiments 1-12 — EXCELLENT ABES compliance

These experiments closely followed the algorithm:

- **Exp 1**: A_model (LogReg baseline) — Correct. ABES urgency(A_model) = 6/6 = 1.0 (all families untried).
- **Exp 2-3**: A_diagnose on LightGBM anomaly — Correct. Score 0.026 triggered anomaly detection (< 0.5 × 0.68 = 0.34). The agent diagnosed probability inversion and fixed it. **This is exactly what the strategy document's anomaly detection was designed for.**
- **Exp 4**: A_model (XGBoost) — Correct. urgency(A_model) = 4/6 = 0.67.
- **Exp 5-8**: A_model (CatBoost, RF, GBM, ET) — Correct. Completing the model tournament. urgency(A_model) decreased from 0.67→0.50→0.33→0.17.
- **Exp 9**: A_feature (add all 4 feature groups) — **Violation of single-variable rule.** ABES Step 3 says "add or remove ONE feature group." Adding all 4 simultaneously is a 4-variable experiment. However, this was justified by warm-start priors from mar30 — the agent knew all 4 helped.
- **Exp 10-12**: A_feature ablation — Correct. One group removed at a time. Found v_interactions and time_features hurt.

**Grade: A-** (one single-variable violation, otherwise textbook ABES)

### Phase 2: Experiments 13-25 — GOOD but starting to over-exploit

- **Exp 13-14**: A_model re-trials (CatBoost, RF on 33 features) — Correct. ABES urgency(A_model) was still nonzero since families had <2 trials on the refined feature set.
- **Exp 15**: A_feature ablation (remove amount_interactions) — Correct.
- **Exp 16-17**: A_hp (max_depth=6, then 7) — Correct. urgency(A_hp) was 1.0 since no A_hp in last 5.
- **Exp 18**: A_model (ExtraTrees re-trial) — Correct.
- **Exp 19**: A_hp (colsample=0.6) — OK.
- **Exp 20**: A_ensemble (XGB+LGBM) — Correct. Two models within 5% triggered urgency=0.3.
- **Exp 21**: A_hp (Optuna 15-trial) — **This is where things start deviating.** Optuna is a multi-variable search (depth, lr, mcw, n_estimators), not "ONE hyperparameter." The strategy document's ABES Step 3 for A_hp says "Change ONE hyperparameter."

**Grade: B+** (solid exploration, but Optuna introduced multi-variable HP search)

### Phase 3: Experiments 26-57 — THE GREAT PLATEAU (31 consecutive discards)

This is the most critical section. From experiment 26 (n_estimators=3000, keep at 0.842614) to experiment 57 (Optuna broad search, keep at 0.842890), the agent ran **31 straight experiments without improvement**.

Let me trace the ABES urgency scores through this period:

**At experiment 31** (after exp 25 keep):
- urgency(A_model) = families with <2 trials... XGBoost(~10), LGBM(2), CatBoost(2), RF(2), GBM(1-crashed), ET(2) = 1/6 ≈ 0.17
- urgency(A_hp) = 1/(1+count of A_hp in last 5) — exp 26-30 had 3 A_hp → 1/(1+3) = 0.25
- urgency(A_feature) = 1-(3/4) = 0.25 (3 of 4 groups ablated)

All urgencies are low, which is actually correct — the agent had reasonably explored the space. But the **ABES algorithm should have recognized the plateau as a signal to try radically different approaches** (Thompson Sampling's wide posteriors should inject randomness).

**Critical failures in this plateau**:
1. **Exp 30 (DART crash)**: Agent tried DART booster — reasonable exploration. But after the crash, no diagnostic was attempted.
2. **Exp 35-36 (HistGBM)**: Agent tried sklearn HistGradientBoosting at exp 35 (scored 0.71) and diagnosed at exp 36 (still 0.70). **This should have been flagged as anomalous** (0.71 < 0.5 × 0.843 = 0.42? No, 0.71 > 0.42). Actually the anomaly threshold is max(0.5×best, 0.68) = max(0.42, 0.68) = 0.68. Score 0.71 is above 0.68, so no anomaly flag — **but this reveals a weakness in the anomaly threshold**: 0.71 for a gradient boosting model IS anomalously bad and deserved more investigation. The threshold formula is too lenient.
3. **Exp 38-39 (imbalance)**: RandomUnderSampler scored 0.81 — a reasonable experiment but came too late.
4. **Exp 40-42**: Three consecutive A_hp experiments with diminishing marginal information (grow_policy, depth=5 again, max_bin). The agent had already confirmed depth=4 was optimal at exp 21.
5. **Exp 43-55**: **13 more A_hp experiments** in the same local basin. This is exactly what the ABES algorithm was designed to prevent. The urgency(A_hp) should have declined sharply: with 5+ consecutive A_hp experiments, urgency = 1/(1+5) = 0.17.

**Why did the agent keep choosing A_hp despite low urgency?** Because the agent wasn't computing urgency scores formally. The ABES algorithm was described in program.md but never implemented as actual numerical computations — the agent was *approximating* ABES through intuition, not executing it.

**Grade: D** — This phase directly replicated the mar30 failure mode of "greedy hill-climbing without restarts." The 31-experiment plateau is the single biggest waste in the budget.

### Phase 4: Experiment 57 — THE BREAKTHROUGH

**Exp 57 (Optuna broad 50-trial search)**: val_pr_auc = 0.842890

This is the most important experiment in the entire run. It discovered that depth=6 + lr=0.077 + mcw=7 is a fundamentally different and better basin than depth=4 + lr=0.02.

**ABES analysis**: This experiment is actually an A_hp action, but it's not a single-variable change — it searched over 5 parameters simultaneously. This **violates** ABES Step 3's single-variable rule. However, it was the *only way* to break out of the local optimum. The ABES framework didn't have a mechanism for "restart in a new basin" — it assumed single-variable perturbations could navigate the HP space.

**Key insight**: The strategy document's Section 4.4 (Successive Halving / Hyperband) and Section 4.1 (BO with low-fidelity proxies) described exactly this approach — use cheap proxy models (200 trees) to screen many configurations cheaply. The agent effectively implemented this, but as an ad-hoc response to the plateau, not because ABES prescribed it.

### Phase 5: Experiments 58-71 — EXCELLENT post-breakthrough HP refinement

After the basin shift, systematic single-variable refinement was appropriate:
- **Exp 58**: A_validate (reproduce Optuna result statically) — Correct.
- **Exp 59-63**: Binary search on n_estimators (1000→500→1500→2000→1250) — Well-structured.
- **Exp 64-66**: Confirm depth=5, lr=0.06, mcw=5 are worse — Correct ablation.
- **Exp 67**: A_feature (time_features with depth=6) — Good re-ablation given new config.
- **Exp 70-71**: reg_alpha=0.0, reg_lambda=0.5 — **Discovered +0.002 improvement.** Excellent.

**Grade: A** — Methodical, controlled, information-rich experiments.

### Phase 6: Experiments 72-100 — DIMINISHING RETURNS PLATEAU

After exp 71 (0.845984), **29 of the final 30 experiments were discards**. The agent continued burning budget on:
- 3 more reg_lambda values (0.0, 0.25, 0.75) — Reasonable, confirms 0.5 optimal.
- n_estimators=1200, 1800 — Reasonable, confirms 1500 optimal.
- depth=7 — Already tried and rejected earlier.
- Two more Optuna searches (exp 78, 84) confirming optimality — **Wasteful.** If two independent Optuna searches confirm the same optimum, a third won't help.
- DART booster (exp 82) — Already crashed in exp 30. **Known dead end retried.**
- colsample_bylevel (exp 83) — Already tried in exp 46. **Known dead end retried.**
- lossguide (exp 85) — Already tried in exp 39. **Known dead end retried.**
- V14_sq, V17_sq (exp 86) — Reasonable new experiment.
- IsolationForest score (exp 87) — Already tried in exp 49. **Known dead end retried.**
- Seed ensemble (exp 88) — Reasonable new approach.
- Feature removal experiments (exp 91-96) — Reasonable final ablation.
- Early stopping validation (exp 97) — Reasonable.
- subsample=1.0 (exp 99) — Reasonable.
- colsample_bynode=0.9 (exp 100) — Reasonable.

**At least 4 experiments (DART, colsample_bylevel, lossguide, IsolationForest) retried known dead ends.** This violates the warm-start principle and wastes 4% of the budget.

**Grade: C+** — Some useful ablation, but 29 consecutive discards signals the agent should have stopped much earlier or tried radically different approaches (neural nets, custom loss, etc.).

## 3. Algorithm Usage Assessment

### 3.1 Thompson Sampling (from MAB)
**Designed**: Sample from posterior of action-type rewards; stochastic selection ensures exploration.
**Actually used**: Never. The agent chose actions through qualitative reasoning, not sampling from posteriors. No posterior was ever computed or updated.

### 3.2 UCB1 (from MAB)
**Designed**: Score = μ̂ + c·√(ln(t)/nᵢ) — under-explored arms get exploration bonus.
**Actually used**: Never numerically. The agent did heuristically explore under-tried model families (exp 1-8), which is UCB1-like behavior, but the exploration bonus was never computed. After exp 18, the agent effectively abandoned model exploration despite UCB1 demanding it for GBM (1 crashed trial).

### 3.3 Bayesian Optimization / TPE (from Section 4.1)
**Designed**: Build surrogate model, use Expected Improvement to select next HP config.
**Actually used**: **YES, via Optuna.** Experiments 21, 31, 43, 51, 57, 68, 78, 84 used Optuna's TPE. This was the most faithfully implemented algorithm — Optuna internally uses TPE.
**But**: The multi-variable Optuna searches violated ABES's single-variable rule.

### 3.4 Successive Halving / Multi-Fidelity (from Section 4.4)
**Designed**: Screen many configs cheaply, eliminate bottom half, increase fidelity.
**Actually used**: **Partially.** The 200-tree proxy approach in experiment 57 is effectively a 1-bracket Successive Halving: 50 configs at ~13% fidelity (200/1500 trees), top-1 promoted to full fidelity. However, this was an ad-hoc invention, not a structured SH bracket schedule.

### 3.5 Anomaly Detection (from ABES Step 4)
**Designed**: Flag any score < max(0.5×best, 0.68), print predict_proba, diagnose.
**Actually used**: **YES, partially.** Experiment 2 (LGBM score 0.026) was correctly flagged and diagnosed. But experiment 35 (HistGBM score 0.71) was investigated but the threshold was too lenient to flag it automatically. The anomaly detection rule worked for extreme failures but missed moderate anomalies.

### 3.6 Urgency Scores (from ABES Step 1)
**Designed**: Numerical scores computed at every step, driving action selection.
**Actually used**: **Never computed numerically.** The agent approximated urgency through intuitive reasoning ("model families are all tried, so A_model urgency is low"). This approximation was adequate in phases 1-2 but failed catastrophically in the plateau (phase 3), where formally computed urgency would have flagged the overinvestment in A_hp.

### 3.7 λ_explore(t, T) Exploration Decay
**Designed**: Sigmoid-warped exploration rate; first 30% = high exploration, last 30% = exploitation.
**Actually used**: **Never.** The exploration rate was never computed. The agent's actual exploration rate was:
- Exp 1-12: ~50% exploration → Good (should be ~80%)
- Exp 13-30: ~20% exploration → Too exploitative (should be ~60%)
- Exp 31-60: ~10% exploration → Far too exploitative (should be ~40%)
- Exp 61-100: ~5% exploration → Acceptable for late-stage (should be ~10%)

### 3.8 Evolutionary Operators (from Section 4.3)
**Designed**: Crossover for recombining feature sets between configs.
**Actually used**: **Never.** No crossover or mutation operators were employed. The strategy document said EA crossover is viable at T≥100, but the agent didn't attempt it.

### 3.9 Multi-Objective / Pareto Front (from Section III)
**Designed**: Track Pareto front of (val_pr_auc, lift@10%, macro_f1); use hypervolume or scalarized objective.
**Actually used**: **Never.** The agent used val_pr_auc as the sole criterion, ignoring lift@10% and macro_F1 entirely. No Pareto dominance was ever checked. This was partially justified by the keep/discard rule in program.md which only uses val_pr_auc, but the strategy document explicitly called for multi-objective awareness.

### 3.10 Warm-Start / Meta-Learning (from Section IX)
**Designed**: Load known dead ends and valid priors from prior runs.
**Actually used**: **YES, effectively.** The agent loaded mar30 priors (dead ends, best config, feature groups) and incorporated them. Experiment 9 applied all 4 feature groups from mar30 at once. Known dead ends (SMOTE, BaggingClassifier, QuantileTransformer) were never retried. **This is one of the most successfully implemented components.**

**However**: Some dead ends from the apr01 run *within itself* were retried (DART, colsample_bylevel, lossguide, IsolationForest). Intra-run memory was imperfect.

## 4. What Improved vs. Mar30

| Dimension | Mar30 | Apr01 | Improvement |
|---|---|---|---|
| **val_pr_auc** | 0.8337 | 0.8460 | +0.012 (+1.5%) |
| **Model families tried** | 3 (XGB, LGBM-buggy, CatBoost) | 6 (all except SVM) | +3 families |
| **Anomaly detection** | 0 diagnosed | 2 diagnosed (LGBM, HistGBM) | New capability |
| **Warm-start** | None | Full prior loading | New capability |
| **Feature ablation** | 0 controlled | 4 groups ablated | New capability |
| **Single-variable rule** | 0/20 compliant | ~85/100 compliant | Major improvement |
| **Optuna usage** | 0 times | 8 times | New capability |
| **Action type logging** | Not tracked | All 100 logged | New capability |

## 5. What Did NOT Improve vs. Strategy Document Expectations

### 5.1 The Strategy Document Predicted val_pr_auc 0.865-0.880 at T=100
**Actual: 0.846.** The prediction was ~2-4% too optimistic. Why?

1. **The dataset ceiling is lower than estimated.** V1-V28 are PCA-compressed with information loss. The real ceiling for tree models on this feature set may be ~0.85.
2. **The prediction assumed ABES would be fully implemented.** Formal urgency scores, Thompson Sampling, and multi-fidelity were never implemented — the agent approximated them.
3. **The prediction assumed more model diversity.** Neural networks, SVMs, and custom loss functions were never tried.

### 5.2 Phased Exploration Never Emerged Naturally
ABES predicted that phases would "emerge" from the urgency dynamics. In reality, the agent locked into A_hp after the first 25 experiments and never meaningfully returned to model exploration. The mar30 failure mode (over-exploitation) was reduced but not eliminated.

### 5.3 No Multi-Objective Analysis Was Performed
Despite 100 experiments with lift@10% and macro_F1 logged, no Pareto analysis was done. The data shows interesting trade-offs:
- Best val_pr_auc (0.846) has macro_F1=0.923 and lift=9.19
- Some discarded experiments had higher macro_F1 (0.935 at exp 98) or higher lift (9.50 at exp 10)
- These trade-offs were never examined

### 5.4 Information Efficiency Was Low
- **17 keeps out of 100 experiments = 17% hit rate**
- **4 crashes = 4% wasted**
- **79 discards = 79% non-informative** (they confirmed something doesn't work, but at high cost)
- The strategy document estimated potential efficiency of 3-7 bits/experiment (controlled changes). Actual information rate was closer to 1 bit/experiment in the plateau.

## 6. Root Cause Analysis: Why the Algorithms Were Not Fully Used

### 6.1 The ABES Algorithm Was Specified Declaratively, Not Imperatively
The strategy document defined urgency formulas, posteriors, and attention mechanisms as Python code. But program.md translated these into **prose instructions** ("compute urgency for each action type"). The LLM agent interpreted the prose heuristically rather than computing the numbers.

**Fix**: Embed the urgency computations directly in `train.py` as a function that the agent must call before each experiment. Output numerical scores to stdout. Make the algorithm executable, not advisory.

### 6.2 No Feedback Loop Forced Re-Evaluation
The agent could run 31 consecutive A_hp experiments without any mechanism forcing it to stop and ask "is this working?" The 3-consecutive-discard plateau rule from CLAUDE.md was treated as a suggestion, not an enforcement.

**Fix**: Add a hard constraint: "If 5+ consecutive discards in the same action type, MUST switch to a different action type."

### 6.3 Optuna Was Used as a Crutch
When stuck, the agent defaulted to "run Optuna" — which is effectively outsourcing the decision to an inner optimizer. This is fine for HP tuning but it replaced ABES's role as the outer optimizer.

### 6.4 The Agent Lacked a "Restart" Mechanism
ABES has no explicit "abandon current basin and search a new one" action. The exp 57 breakthrough was ad-hoc. The strategy document's Section II identified "no random restarts" as a root cause of mar30's failure, but ABES didn't include a restart trigger.

**Fix**: Add action type `A_restart`: "When 10+ consecutive discards, run a broad multi-fidelity screening (50 configs, 200 trees) to search for new basins."

## 7. Summary Scorecard

| Algorithm/Strategy | Proposed In Document | Implemented? | How Faithfully? | Impact |
|---|---|---|---|---|
| ABES framework | Section VII | Partially | ~40% — qualitative approximation | Moderate |
| Thompson Sampling | Section VII | No | 0% — never sampled from posteriors | None |
| UCB1 model selection | Section 4.2 | Partially | ~50% — heuristic exploration | Moderate |
| Bayesian Optimization (TPE) | Section 4.1 | Yes | ~80% — via Optuna | **High** |
| Multi-Fidelity (low-fi proxy) | Section 4.4 | Partially | ~30% — ad-hoc, not structured | **High** (broke plateau) |
| Anomaly Detection | Section VII | Yes | ~70% — threshold too lenient | Moderate |
| Urgency Scores | Section VII | No | ~20% — never computed numerically | Low |
| λ_explore decay | Section VII | No | 0% — never computed | None |
| Pareto/Multi-Objective | Section III | No | 0% — single metric only | None |
| Warm-Start Priors | Section IX | Yes | ~90% — effective meta-learning | **High** |
| EA Crossover | Section 4.3 | No | 0% — never attempted | None |
| Single-Variable Rule | Section VII Step 3 | Mostly | ~85% — Optuna searches violated it | Moderate |
| Action Type Logging | Section VII | Yes | 100% — all 100 logged | High |

## 8. Bottom Line

**The agent achieved 0.846 vs. a theoretical prediction of 0.865-0.880.** The gap is attributable to:

1. **Only 3 of 10 proposed algorithms were meaningfully implemented** (TPE via Optuna, anomaly detection, warm-start priors). Thompson Sampling, UCB1, multi-fidelity, EA crossover, Pareto tracking, urgency computation, and exploration decay were all either skipped or approximated so loosely as to be non-functional.

2. **The 31-experiment plateau (exp 26-56) wasted 31% of the budget.** Had ABES urgency scores been computed numerically, A_hp urgency would have dropped to 0.17 by experiment 35, forcing the agent to try model-switching or feature engineering. Instead, the agent repeated the mar30 pattern of grinding on HP variations.

3. **The breakthrough at experiment 57 came from an algorithm (multi-fidelity proxy search) that was described in the strategy document but was invented ad-hoc by the agent**, not derived from the ABES protocol. The most impactful decision in the entire 100-experiment run was not prescribed by the framework.

4. **val_pr_auc improved from 0.834 → 0.846 (+1.5%)**. This is a genuine improvement, but ~60% of it came from a single experiment (exp 57, the broad Optuna search) and its aftermath (reg tuning). The other 70+ experiments that weren't part of that thread contributed almost nothing.

The strategy document was a good roadmap but its algorithms were treated as inspiration, not as executable protocols. The primary recommendation for the next run: **make the ABES decision engine a computable function, not a prose instruction.**
