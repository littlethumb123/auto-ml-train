# Comprehensive Research: Why Auto-Train Plateaus and How to Break Through

**Date**: 2026-04-03
**Author**: Analysis of three experimental campaigns (mar30, apr01, apr03)
**Goal**: Identify the root causes of the 0.846 performance ceiling, explain why proposed algorithms failed to be fully implemented, and design a next-generation optimization harness that eliminates these bottlenecks

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Three-Run Forensic Analysis](#2-three-run-forensic-analysis)
3. [Root Cause Taxonomy: The Seven Bottlenecks](#3-root-cause-taxonomy)
4. [The Agent-Optimizer Separation Problem](#4-the-agent-optimizer-separation-problem)
5. [Why Each Proposed Algorithm Was Not Implemented](#5-algorithm-implementation-failures)
6. [The Dataset Ceiling Hypothesis](#6-the-dataset-ceiling-hypothesis)
7. [Optimization Algorithm Redesign](#7-optimization-algorithm-redesign)
8. [Long-Running Agent Harness Architecture](#8-long-running-agent-harness)
9. [Concrete Implementation Roadmap](#9-implementation-roadmap)
10. [Expected Impact Analysis](#10-expected-impact)

---

## 1. Executive Summary

Three campaigns attempted to optimize fraud detection val_pr_auc on the credit card dataset:

| Run | Branch | Budget | Best val_pr_auc | Key Achievement | Key Failure |
|-----|--------|--------|-----------------|-----------------|-------------|
| **Mar30** | autotrain/mar30 | 20 | 0.8337 (honest) | Established XGBoost baseline | Greedy hill-climbing, zero controlled experiments, LightGBM dismissed after 1 buggy trial |
| **Apr01** | autotrain/apr01 | 100 | 0.845984 | +0.012 gain, ABES designed, anomaly detection | ABES only 40% implemented, 31-experiment plateau, 55% A_hp over-allocation |
| **Apr03** | autotrain/apr03 | 20 | 0.845984 | Executable ABES engine, 0 crashes, fast recovery | No new SOTA, same basin rediscovered, 18/20 discards |

**The core finding**: All three runs converge to the same XGBoost basin (depth=6, lr~0.077, 1500 trees) at val_pr_auc ~0.846. The performance ceiling is not a search failure — it is a structural limitation arising from seven interlocking bottlenecks that compound to prevent the system from exploring fundamentally different solution architectures.

**The prediction gap**: The optimization strategy document predicted val_pr_auc 0.865-0.880 at T=100. Actual: 0.846. The ~2-4% gap is attributable to: (1) only 3 of 10 proposed algorithms being implemented, (2) the LLM agent replacing numerical computation with intuitive approximation, and (3) the search space remaining confined to tree ensembles on the existing feature substrate.

---

## 2. Three-Run Forensic Analysis

### 2.1 Run Trajectory Comparison

```
val_pr_auc over experiment count:

Mar30 (20 exp):     0.68 → 0.814 → 0.834 ──── ceiling
                    ↑↑↑↑   ↑                  (no movement after exp 5)
                   rapid   1 strong
                   gain    XGBoost

Apr01 (100 exp):   0.68 → 0.814 → 0.834 ─────────── 0.843 → 0.846 ── ceiling
                   ↑↑↑↑   ↑        ↑                  ↑       ↑
                   rapid   XGBoost  warm-start    exp 57    reg tuning
                   gain             gain          basin     exp 71
                                                  shift

Apr03 (20 exp):    0.839 ───────────────── 0.846 ──── ceiling
                   ↑                        ↑
                   warm-start               exp 12
                   baseline                 basin jump
                   (better start)           (same basin as apr01)
```

### 2.2 Information Yield Per Experiment

| Metric | Mar30 | Apr01 | Apr03 |
|--------|-------|-------|-------|
| Total experiments | 20 | 100 | 20 |
| Keeps (improvements) | ~5 | 17 | 2 |
| Discards | ~14 | 79 | 18 |
| Crashes | ~1 | 4 | 0 |
| Keep rate | ~25% | 17% | 10% |
| Experiments to find best | 14 | 71 | 12 |
| Net PR-AUC gain | +0.153 | +0.166 | +0.007 |
| PR-AUC gain per experiment | +0.0077 | +0.0017 | +0.00036 |
| Effective information bits/exp | ~2-3 | ~1 | ~0.3 |

**Key observation**: Information yield is declining across runs. Mar30 made large gains because the landscape was unexplored. Apr01 made moderate gains through the basin-shift breakthrough. Apr03 made almost no new gains because it rediscovered an already-known optimum. The marginal value of each additional experiment within the current paradigm is approaching zero.

### 2.3 Action Type Distribution Across Runs

| Action Type | Mar30 (inferred) | Apr01 | Apr03 |
|-------------|-------------------|-------|-------|
| A_model | ~35% | 12% | 35% |
| A_hp | ~45% | 55% | 10% |
| A_feature | ~10% | 18% | 15% |
| A_restart | 0% | 0% | 20% |
| A_diagnose | 0% | 3% | 10% |
| A_imbalance | ~5% | 3% | 10% |
| A_ensemble | ~5% | 5% | 0% |
| A_validate | 0% | 4% | 0% |

**Progression**: Mar30 was HP-dominated (45% A_hp). Apr01 was even more HP-dominated (55% A_hp). Apr03 corrected this — more balanced distribution thanks to the executable engine — but the improved distribution couldn't overcome the ceiling because the search space itself was exhausted.

### 2.4 The Convergence Pattern

All three runs converge to nearly identical configurations:

| Parameter | Mar30 Best | Apr01 Best | Apr03 Best |
|-----------|------------|------------|------------|
| Model | XGBoost | XGBoost | XGBoost |
| max_depth | 5 | 6 | 6 |
| learning_rate | 0.05 | 0.0777 | 0.0777 |
| n_estimators | 600 | 1500 | 1500 |
| Features | 39 (kitchen sink) | 33 (selective) | 33 (selective) |
| val_pr_auc | 0.8337 | 0.845984 | 0.845984 |

The difference between Mar30 and Apr01/03 is exactly one basin shift: from depth=5/lr=0.05 to depth=6/lr=0.077. Once this basin was discovered (apr01 exp 57), no further structural improvement was found in 49 more experiments (apr01 exp 72-100) or the entire apr03 campaign.

---

## 3. Root Cause Taxonomy: The Seven Bottlenecks

### Bottleneck 1: The Agent-Optimizer Conflation

**What it is**: The LLM agent serves as both the optimizer (deciding what to try) and the executor (implementing the experiment). These are fundamentally different cognitive tasks requiring different capabilities.

**Why it matters**: LLMs are poor numerical optimizers. They cannot:
- Sample from posterior distributions (Thompson Sampling requires actual random draws from Beta/Normal distributions)
- Compute acquisition functions (Expected Improvement requires integrating over a GP posterior)
- Maintain consistent internal state across 100 experiments (context limitations, recency bias)
- Resist the temptation to "tweak" rather than "transform" (exploitation bias inherent in language model pattern matching)

**Evidence across runs**:
- Mar30: Agent chose experiments by "what sounds good next" — pure intuition
- Apr01: ABES urgency scores were designed but never computed numerically by the agent — it approximated them qualitatively, leading to 55% A_hp over-allocation
- Apr03: Engine computed urgency numerically, but the agent still controlled the specific experiment within the recommended action type — and chose incremental variations

**Root cause**: The ABES engine (abes_engine.py) recommends an action *type* (e.g., "A_hp"), but the agent chooses the *specific experiment* (e.g., "try reg_lambda=0.5"). This means the outer optimization (action type selection) is formalized, but the inner optimization (specific parameter choice) remains intuitive. The most consequential decisions happen at the inner level.

### Bottleneck 2: The Search Space Confinement

**What it is**: All three runs searched exclusively within tree ensemble models on the same feature substrate (30 PCA features + 3-9 engineered features). No fundamentally different model architectures were attempted.

**Models never tried across all 140 experiments**:
- Neural networks (MLP, TabNet, NODE)
- Support Vector Machines (SVM with RBF kernel)
- k-Nearest Neighbors ensemble
- Linear models with nonlinear kernels
- Custom loss functions (focal loss, asymmetric loss)
- Calibrated probability models
- Deep embedding + gradient boosting hybrid

**Why it matters**: If the tree-ensemble ceiling on this feature set is ~0.846, then searching more tree-ensemble configurations has zero expected improvement. The search needs to cross model-class boundaries.

**Evidence**: Apr01 ran 8 separate Optuna searches within XGBoost (each 15-50 trials), confirming the same optimal basin every time. The 31-experiment plateau was not because the search was bad — it was because the XGBoost function landscape was fully mapped. No single-family optimization can improve beyond the family's capability ceiling.

### Bottleneck 3: The Feature Substrate Exhaustion

**What it is**: V1-V28 are PCA-transformed. The original feature identities are lost. Feature engineering on PCA components has limited semantic validity.

**Why it matters**:
- PCA components are already decorrelated — interaction terms (V1*V2) capture residual nonlinearity, but most signal is already in the principal components
- Tree models split on individual features — they can capture V1*V2 interactions implicitly through sequential splits. Explicit interaction features add marginal signal.
- The only features with real domain meaning are Amount and Time. Everything else is a statistical artifact of PCA.
- Features that helped: `log1p(Amount)` (nonlinear compression of a skewed feature) and `Amount*V1, Amount*V2` (cross-domain interactions). Features that hurt: `V1*V2, V1*V3` (PCA cross-terms with no interpretable meaning).

**The ceiling implication**: On this 30-feature PCA dataset, tree models can capture ~85% of the available classification signal. The remaining ~15% is either noise or requires:
1. Access to the original pre-PCA features (not available)
2. A model that can learn complex feature interactions beyond what trees capture (deep learning)
3. External data enrichment (not available)

### Bottleneck 4: The Single-Metric Tunnel Vision

**What it is**: The keep/discard rule uses only val_pr_auc. The Pareto front (pr_auc, lift@10, macro_f1) is tracked but never used for decision-making.

**Why it matters**: Experiments that improve lift@10 or macro_f1 while matching pr_auc (within noise) are discarded. This narrows the search to a single ridge in metric space, missing configurations that are Pareto-superior.

**Evidence from apr03 results.tsv**: Experiment `3af3f0a` (LightGBM) had macro_f1=0.927 vs. the keep's 0.914, and val_f1=0.854 vs. 0.828 — significantly better on secondary metrics — but was discarded because pr_auc was 0.830 vs. 0.839. In a Pareto-aware system, this LightGBM configuration would be retained as a Pareto front member, and its features/approach would inform future experiments.

### Bottleneck 5: The Exploration Rate Miscalibration

**What it is**: Even with the executable ABES engine, the exploration mechanism is too weak to escape the XGBoost attractor basin.

**Structural issue with λ_explore**:
```python
score(a) = urgency(a) × λ_explore + opportunity(a) × (1 - λ_explore/2)
```

This formula has two problems:
1. **It's deterministic** — argmax always picks the same action type given the same state. No stochastic exploration. Thompson Sampling was designed but never implemented in the engine.
2. **Opportunity defaults to prior** — for action types with <2 rewards, opportunity is a hardcoded constant (0.3 or 0.5). This means the engine cannot learn which action types are actually productive. After the first 10 experiments, opportunity is dominated by stdev of observed rewards, which is near-zero for consistently-failing action types.

**The A_restart threshold is too conservative**: Requiring 8 consecutive discards before triggering basin restart means the agent must fail 8 times in a row. In practice, an occasional near-miss keep (noise-level improvement) resets the counter, preventing restart from ever triggering until the plateau is severe.

### Bottleneck 6: The Temporal Coherence Problem (Long-Running Agent Harness)

**What it is**: The LLM agent loses context over long runs. In apr01 (100 experiments), the agent retried 4 known dead ends (DART, colsample_bylevel, lossguide, IsolationForest) because its working memory degraded.

**Why it matters**:
- At experiment 80+, the agent has processed ~80 experiment cycles, each involving reading recommendations, editing train.py, running the experiment, parsing results, and logging. This fills the context window.
- Context compaction (summarization) loses details about why specific approaches failed.
- The agent's "intuitive" memory of what has been tried is unreliable beyond ~20-30 experiments.

**Evidence**: Apr01 dead-end retries happened at experiments 82 (DART, already crashed at 30), 83 (colsample_bylevel, already failed at 46), 85 (lossguide, already failed at 39), 87 (IsolationForest, already failed at 49). All in the last 20% of the run — exactly when context degradation is worst.

### Bottleneck 7: The Reward Signal Sparsity Problem

**What it is**: The binary keep/discard reward signal is extremely sparse. Most experiments get reward=0 (discard) or reward=tiny_delta (marginal improvement). This makes posterior updating nearly useless.

**Why it matters**: Thompson Sampling requires meaningful variance in rewards to drive exploration. When 80-90% of experiments return reward=0, the posterior for every action type converges to "probably gives reward 0" — which makes Thompson Sampling degenerate into random uniform selection, providing no guidance.

**The improvement**: Use continuous information-theoretic rewards instead of binary keep/discard:
- **Information gain**: How much did this experiment reduce uncertainty about the optimum?
- **Gradient signal**: Did this experiment reveal the direction of improvement (even if it didn't improve)?
- **Diversity bonus**: Did this experiment cover an unexplored region of the configuration space?

---

## 4. The Agent-Optimizer Separation Problem

This is the single most impactful architectural change needed.

### Current Architecture (Flawed)

```
┌─────────────────────────────────────────────────┐
│               LLM AGENT                         │
│                                                 │
│  1. Read engine recommendation (action TYPE)    │
│  2. Decide specific experiment (INTUITION)      │ ← Inner optimization is uncontrolled
│  3. Edit train.py                               │
│  4. Run experiment                              │
│  5. Log results                                 │
│  6. Interpret outcomes                          │
└─────────────────────────────────────────────────┘
           ↕ reads/writes
┌─────────────────────────────────────────────────┐
│           abes_engine.py                        │
│                                                 │
│  Urgency scores → Action type recommendation    │ ← Outer optimization only
│  Pareto tracking, anomaly detection             │
└─────────────────────────────────────────────────┘
```

**Problem**: The engine controls the outer decision (action type), but the LLM controls the inner decision (specific config). The inner decision is where most value is created or destroyed. An agent that knows to "try A_hp" but intuitively picks reg_lambda=0.5 instead of the acquisition-function-optimal reg_lambda=0.73 is leaving performance on the table.

### Proposed Architecture (Two-Brain)

```
┌─────────────────────────────────────────────────┐
│            OPTIMIZATION BRAIN                   │
│            (Pure Python, numerical)             │
│                                                 │
│  1. Maintain surrogate model (TPE/RF)           │
│  2. Compute acquisition function (EI/UCB)       │
│  3. Generate EXACT next config:                 │
│     {"model": "xgboost",                        │
│      "depth": 6, "lr": 0.073, ...              │
│      "features": ["log_amount", "amt_v1"]}     │
│  4. Thompson Sampling for action type           │
│  5. Track Pareto front with hypervolume         │
│  6. Implement Hyperband multi-fidelity          │
│                                                 │
│  Output: Exact experiment configuration JSON     │
└──────────────────┬──────────────────────────────┘
                   │ config.json
                   ▼
┌─────────────────────────────────────────────────┐
│            EXECUTION BRAIN                      │
│            (LLM Agent)                          │
│                                                 │
│  1. Read config.json                            │
│  2. Translate to train.py code                  │
│  3. Commit and run                              │
│  4. Parse metrics from output                   │
│  5. Feed back to optimization brain             │
│  6. Handle crashes/errors                       │
│                                                 │
│  Does NOT decide what to try — only HOW to try  │
└─────────────────────────────────────────────────┘
```

**Why this works**:
- The optimization brain makes all numerical decisions using proper algorithms (BO, Thompson Sampling, Hyperband)
- The execution brain translates structured configs into runnable code
- The LLM's strengths (code generation, error handling, natural language understanding) are leveraged
- The LLM's weaknesses (numerical optimization, long-term consistency, exploration discipline) are eliminated
- The optimization brain persists state perfectly (JSON/pickle), with no context degradation over 1000 experiments

---

## 5. Why Each Proposed Algorithm Was Not Implemented

The optimization strategy research document (2026-03-31) proposed 10 algorithms. Here is why each was not faithfully implemented, and what would be needed:

### 5.1 Thompson Sampling (Not Implemented: 0%)

**Designed**: Sample θ(a) ~ Normal(μ_a, σ_a) for each action type, select argmax.

**Why it failed**: The ABES engine uses deterministic argmax of composite scores. No sampling from posteriors. This is because:
1. The engine runs as a CLI tool that produces deterministic output for reproducibility
2. Adding randomness to recommendations makes the agent's behavior harder to debug
3. The posterior parameters (μ, σ) require enough data to be meaningful — with 8 action types and 20 experiments, most posteriors have <3 observations

**What's needed**: 
- Add `--stochastic` flag to the engine that enables Thompson Sampling
- Track per-action-type Beta(α, β) distributions updated by keep/discard outcomes
- Sample from these posteriors before ranking
- The stochasticity is essential — deterministic selection cannot explore

### 5.2 UCB1 (Partially Implemented: ~30%)

**Designed**: score = μ̂ + c·√(ln(t)/nᵢ) where nᵢ is the number of times action i was tried.

**Why it failed**: The urgency formulas approximate UCB1 behavior (under-explored families get higher urgency) but don't use the actual UCB formula. The exploration bonus is not computed as √(ln(t)/nᵢ), so it doesn't decay correctly as t grows.

**Specific issue**: UCB1's exploration bonus for a 1-trial action at t=20 is √(ln(20)/1) = 1.73. At t=100, it's √(ln(100)/1) = 2.15. The logarithmic growth ensures exploration continues. The current urgency formula `under_explored/6` is static — it doesn't grow with t.

### 5.3 Bayesian Optimization / TPE (Implemented: ~60% via Optuna)

**Designed**: Build surrogate model, use Expected Improvement to select next config.

**What worked**: The agent used Optuna internally for HP search (8 times in apr01). Optuna's TPE surrogate model guided HP selection within XGBoost.

**What failed**: BO was only applied at Level 2 (HP optimization within a fixed model). It was never applied at Level 1 (selecting which model/feature/strategy combination to try). The agent chose Level 1 decisions intuitively.

**What's needed**: A unified BO framework that operates over the FULL config space (model family × features × HPs), not just HPs within one model. This requires conditional search spaces (XGBoost HPs only active when model_family="xgboost").

### 5.4 Multi-Fidelity / Successive Halving (Implemented: ~25%)

**Designed**: Screen many configs cheaply (200 trees), promote top-K to full fidelity (1500 trees).

**What worked**: `screen_configs()` in train.py does exactly this — tests 16 random configs at 200 trees on 25% data.

**What failed**: Screening only happens during A_restart (plateau recovery). It should be the DEFAULT mode for A_hp. Every HP experiment should screen 16 candidates cheaply before committing to full evaluation.

**The efficiency gain**: 16 low-fidelity evals × 3.5s = 56s total, yielding the top-3 configs. Then 1 full-fidelity eval × 45s for the winner. Total: ~100s for 16 candidates explored vs. 45s for 1 candidate in the current approach. This is a **16× increase in search breadth** for ~2× the wall time.

### 5.5 Evolutionary Crossover (Not Implemented: 0%)

**Designed**: Recombine feature sets and HP configurations from different high-performing parents.

**Why it failed**: The search space was never formalized as a chromosome structure. Without a structured representation, crossover is impossible. The agent can't "cross" two train.py files meaningfully.

**What's needed**: Define configurations as structured dictionaries:
```python
config_a = {"model": "xgboost", "depth": 6, "features": ["log_amount", "amt_v1"]}
config_b = {"model": "xgboost", "depth": 4, "features": ["log_amount", "magnitude"]}
child    = {"model": "xgboost", "depth": 6, "features": ["log_amount", "magnitude"]}  # crossover
```

### 5.6 Pareto / Multi-Objective (Tracked but unused: ~20%)

**Designed**: Track Pareto front, use hypervolume improvement to guide experiment selection.

**What worked**: The engine tracks the Pareto front in abes_state.json. The `check` command reports Pareto updates.

**What failed**: The Pareto front never influences the keep/discard decision or the next experiment selection. It's purely informational. Experiments that are Pareto-superior on secondary metrics but inferior on pr_auc are discarded and their train.py changes are lost via `git reset --hard`.

### 5.7 Urgency Scores (Implemented: ~50%)

**What worked**: Numerical urgency scores are computed correctly in abes_engine.py.

**What failed**: The composite score formula `urgency × λ + opportunity × (1 - λ/2)` is too simplistic:
- No interaction between urgency and opportunity
- No learning rate — urgency doesn't adapt based on observed rewards
- The opportunity score for under-explored actions uses hardcoded priors (0.3, 0.5, 0.7) that never update until the action has been tried twice

### 5.8 λ_explore Decay (Implemented: ~80%)

**What worked**: The sigmoid decay function is implemented correctly. It maps experiment progress to an exploration weight.

**What failed**: λ_explore is a function of (t, T) only — not of actual exploration outcomes. If exploration is highly productive (keeps coming from new action types), λ should stay high. If exploitation is productive, λ should drop faster. The current implementation ignores reward history.

### 5.9 Warm-Start / Meta-Learning (Implemented: ~70%)

**What worked**: Dead ends, known-good features, and optimal HP ranges are loaded from prior runs. The apr03 run started at 0.839 (vs. 0.68 for mar30) because of warm-start.

**What failed**: The surrogate model doesn't transfer. Optuna's TPE history from apr01 (8 searches × 15-50 trials each) is lost between runs. This is ~200 configurations worth of information that could warm-start the next TPE search.

### 5.10 Anomaly Detection (Implemented: ~75%)

**What worked**: The engine correctly flags scores below max(0.5 × best, 0.75). The 0.75 floor (raised from 0.68) catches moderate anomalies. Diagnosis is triggered as a first-class action type.

**What failed**: The anomaly threshold is still static. It should be model-family-adaptive: a score of 0.82 for XGBoost is normal, but 0.82 for a tuned CatBoost might indicate a configuration issue given CatBoost's typical performance on this dataset.

---

## 6. The Dataset Ceiling Hypothesis

### Is 0.846 the Theoretical Ceiling?

**Evidence for a ceiling near 0.85**:
1. Three independent optimization campaigns converge to 0.845-0.846
2. Eight independent Optuna searches within XGBoost all find the same basin
3. LightGBM, CatBoost, RF, and ET all achieve lower scores (0.82-0.83)
4. Feature additions consistently degrade or match current performance
5. The dataset is PCA-transformed, limiting feature engineering potential

**Evidence against a hard ceiling**:
1. Only tree ensembles have been tried (no neural nets, SVMs, custom losses)
2. No proper stacking with CV has been attempted (the one stacking attempt included a buggy LightGBM)
3. No instance-level analysis has been done to identify which fraud cases are being missed
4. No threshold optimization has been performed (val_pr_auc is threshold-agnostic, but specific threshold choices affect downstream metrics)
5. The best published result on this dataset (Kaggle) is significantly higher than 0.846 — models using neural networks, careful ensembling, and post-processing achieve 0.86-0.88+ PR-AUC

### What's Left to Try

| Approach | Expected PR-AUC Range | Rationale |
|----------|----------------------|-----------|
| Neural network (MLP, TabNet) | 0.84-0.87 | Can learn feature interactions trees miss; TabNet specifically designed for tabular data |
| Proper stacking (XGB + LGB + CatBoost → LR meta-learner) | 0.85-0.87 | Diverse base learners capture different aspects of the decision boundary |
| Custom loss (focal loss, asymmetric) | 0.84-0.86 | Better handling of hard-to-classify minority samples |
| Probability calibration + threshold optimization | 0.846-0.855 | May not improve PR-AUC but can improve operational metrics |
| Post-processing (score blending, rank averaging) | 0.847-0.855 | Ensemble of diverse scoring functions |
| Deep embedding + GBM | 0.85-0.87 | Autoencoder learns feature representations, GBM classifies on embeddings |

### Estimated True Ceiling

Based on published results and the PCA nature of the features:
- **Tree ensemble ceiling**: ~0.850 (achievable with perfect tuning of XGBoost + proper stacking)
- **Mixed-architecture ceiling**: ~0.870 (neural nets + tree ensembles + calibration)
- **Theoretical ceiling (Bayes-optimal)**: ~0.88-0.90 (limited by PCA information loss and class overlap)

The current best of 0.846 is ~96% of the tree ensemble ceiling and ~97% of the mixed-architecture ceiling. Breaking through requires model-class diversity, not more tree-ensemble hyperparameter search.

---

## 7. Optimization Algorithm Redesign

### 7.1 ABES v2: Full Computational Engine

The current abes_engine.py is a good foundation but needs three fundamental upgrades:

#### A. Thompson Sampling with Proper Posteriors

Replace the deterministic composite score with actual Thompson Sampling:

```python
class ActionTypeBandit:
    """Thompson Sampling bandit over action types."""

    def __init__(self, action_types):
        # Beta distribution for keep/discard outcomes
        self.alpha = {a: 1.0 for a in action_types}  # prior successes
        self.beta = {a: 1.0 for a in action_types}   # prior failures
        # Normal distribution for magnitude of improvement
        self.mu = {a: 0.0 for a in action_types}
        self.sigma = {a: 1.0 for a in action_types}
        self.n_obs = {a: 0 for a in action_types}

    def update(self, action, kept: bool, improvement: float):
        if kept:
            self.alpha[action] += 1
        else:
            self.beta[action] += 1

        # Bayesian update for improvement magnitude (conjugate normal)
        n = self.n_obs[action]
        old_mu = self.mu[action]
        old_sigma = self.sigma[action]
        self.n_obs[action] = n + 1
        # Weighted update
        self.mu[action] = (old_mu * n + improvement) / (n + 1)
        self.sigma[action] = max(0.01, old_sigma * 0.95)  # shrink uncertainty

    def sample(self):
        """Thompson Sampling: draw from posteriors, return action with highest draw."""
        draws = {}
        for a in self.alpha:
            p_keep = np.random.beta(self.alpha[a], self.beta[a])
            magnitude = np.random.normal(self.mu[a], self.sigma[a])
            draws[a] = p_keep * max(0, magnitude)
        return draws
```

Key: The `sample()` method returns different results each time it's called, providing natural exploration. Actions with few observations have wide posteriors, so they occasionally draw high values and get selected — this is exactly UCB-like exploration without requiring an explicit exploration bonus.

#### B. Surrogate-Guided Configuration Proposal

Instead of the agent choosing specific experiments, the engine proposes exact configurations:

```python
class ConfigurationProposer:
    """Surrogate-model-based configuration proposal."""

    def __init__(self):
        self.history = []  # List of (config_dict, pr_auc) tuples
        self.study = None  # Optuna study for TPE

    def propose_for_action(self, action_type, state):
        if action_type == "A_model":
            return self._propose_model(state)
        elif action_type == "A_hp":
            return self._propose_hp(state)
        elif action_type == "A_feature":
            return self._propose_features(state)
        elif action_type == "A_restart":
            return self._propose_restart(state)
        # ...

    def _propose_hp(self, state):
        """Use TPE to propose the next HP configuration."""
        if self.study is None:
            self.study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42)
            )
            # Warm-start with history
            for config, score in self.history:
                if config.get("model") == state["best_model_family"]:
                    trial = optuna.trial.create_trial(
                        params=config, values=[score],
                        distributions=self._get_distributions(config["model"])
                    )
                    self.study.add_trial(trial)

        # Ask TPE for the next config
        trial = self.study.ask(self._get_distributions(state["best_model_family"]))
        return trial.params

    def _propose_restart(self, state):
        """Multi-fidelity screening: Hyperband-style."""
        configs = []
        # Generate 27 random configs (Hyperband bracket 0)
        for i in range(27):
            configs.append(self._random_config(state))
        return {"mode": "hyperband", "configs": configs, "fidelity_schedule": [50, 150, 450, 1350]}
```

#### C. Continuous Information-Theoretic Rewards

Replace binary keep/discard rewards with information-rich continuous signals:

```python
def compute_reward(metrics, state, action_type):
    """Continuous reward based on multiple information signals."""
    pr_auc = metrics["val_pr_auc"]
    best = state["best_pr_auc"]

    # Component 1: Improvement (can be negative)
    improvement = pr_auc - best

    # Component 2: Information gain (always positive)
    # How much did this experiment reduce our uncertainty about the optimal config?
    nearest_prior = find_nearest_config(state["history"], metrics["config"])
    novelty = config_distance(metrics["config"], nearest_prior)
    info_gain = novelty * 0.1  # Scale factor

    # Component 3: Pareto improvement (always non-negative)
    pareto_improvement = compute_hypervolume_improvement(metrics, state["pareto_front"])

    # Component 4: Gradient signal (which direction to go?)
    if improvement > 0:
        gradient_signal = 1.0
    elif improvement > -0.005:
        gradient_signal = 0.3  # Close to best — useful calibration signal
    else:
        gradient_signal = 0.0  # Far from best — minimal information

    # Composite: weighted sum
    reward = (
        0.4 * max(0, improvement * 100) +  # Scale to ~[0, 1]
        0.2 * info_gain +
        0.2 * pareto_improvement +
        0.2 * gradient_signal
    )
    return reward
```

### 7.2 Hyperband Integration for Multi-Fidelity Search

The biggest untapped efficiency gain is multi-fidelity evaluation. Currently, every experiment uses full fidelity (1500 trees on 100% data, ~45s). With Hyperband:

```
Bracket s=3 (most aggressive):
  Rung 0: 27 configs × n_est=56   × 12.5% data → ~27 × 1s = 27s
  Rung 1:  9 configs × n_est=167  × 25% data   → ~9 × 3s  = 27s
  Rung 2:  3 configs × n_est=500  × 50% data   → ~3 × 12s = 36s
  Rung 3:  1 config  × n_est=1500 × 100% data  → ~1 × 45s = 45s
  Total: 135s for 27 configs explored (40 evaluations total)

Bracket s=2 (moderate):
  Rung 0:  9 configs × n_est=167  × 25% data   → ~9 × 3s  = 27s
  Rung 1:  3 configs × n_est=500  × 50% data   → ~3 × 12s = 36s
  Rung 2:  1 config  × n_est=1500 × 100% data  → ~1 × 45s = 45s
  Total: 108s for 9 configs explored (13 evaluations total)

Bracket s=1 (conservative):
  Rung 0:  3 configs × n_est=500  × 50% data   → ~3 × 12s = 36s
  Rung 1:  1 config  × n_est=1500 × 100% data  → ~1 × 45s = 45s
  Total: 81s for 3 configs explored (4 evaluations total)

Bracket s=0 (full fidelity):
  Rung 0:  1 config  × n_est=1500 × 100% data  → ~1 × 45s = 45s
```

**Efficiency comparison**:
- Current approach: 20 experiments × 45s = 900s → 20 configs explored
- Hyperband (20 "experiment slots"): Bracket cycle uses ~5 slots → 4 cycles → explores **~108 configs** in the same wall time

This is a **5.4× increase in search breadth**.

### 7.3 Genetic Algorithm for Feature-Model Co-Optimization

At budget T≥50, evolutionary feature construction becomes viable:

```python
class FeatureModelEvolution:
    """Co-evolve feature sets and model configurations."""

    def __init__(self, population_size=10):
        self.pop_size = population_size
        self.population = []  # List of (config, fitness) tuples

    def initialize(self, warm_start_configs):
        """Seed population with known-good configs plus random variants."""
        self.population = list(warm_start_configs)
        while len(self.population) < self.pop_size:
            parent = random.choice(warm_start_configs)
            child = self.mutate(parent[0])
            self.population.append((child, None))

    def evolve(self):
        """One generation: select parents → crossover → mutate → evaluate."""
        # Tournament selection
        parents = self.tournament_select(k=2)
        # Crossover: take features from parent1, HPs from parent2
        child = self.crossover(parents[0], parents[1])
        # Mutation: perturb one random gene
        child = self.mutate(child)
        return child

    def crossover(self, config_a, config_b):
        """Feature-level crossover between two configurations."""
        child = {}
        # Take model family from the fitter parent
        child["model"] = config_a["model"]
        # Take feature groups from config_b
        child["features"] = config_b["features"].copy()
        # Take HPs from config_a with 20% noise
        for hp, val in config_a["hps"].items():
            if isinstance(val, float):
                child.setdefault("hps", {})[hp] = val * np.random.lognormal(0, 0.1)
            else:
                child.setdefault("hps", {})[hp] = val
        return child

    def mutate(self, config, mutation_rate=0.2):
        """Randomly perturb one aspect of the configuration."""
        config = copy.deepcopy(config)
        if random.random() < mutation_rate:
            # Flip one feature group
            idx = random.randint(0, len(config["features"]) - 1)
            config["features"][idx] = 1 - config["features"][idx]
        if random.random() < mutation_rate:
            # Perturb one HP
            hp_key = random.choice(list(config["hps"].keys()))
            config["hps"][hp_key] *= np.random.lognormal(0, 0.2)
        return config
```

### 7.4 Dynamic Exploration Control

Replace the static sigmoid λ_explore with a reward-adaptive mechanism:

```python
class DynamicExplorationController:
    """Adjusts exploration rate based on observed reward patterns."""

    def __init__(self, budget):
        self.budget = budget
        self.explore_rewards = []  # Rewards from exploration experiments
        self.exploit_rewards = []  # Rewards from exploitation experiments
        self.base_lambda = None    # Initialized from sigmoid

    def get_lambda(self, t):
        # Base: sigmoid schedule
        self.base_lambda = sigmoid_lambda(t, self.budget)

        # Adjustment 1: If recent explorations are productive, boost exploration
        if len(self.explore_rewards) >= 3:
            recent_explore = np.mean(self.explore_rewards[-3:])
            recent_exploit = np.mean(self.exploit_rewards[-3:]) if self.exploit_rewards else 0
            if recent_explore > recent_exploit * 1.5:
                self.base_lambda = min(2.0, self.base_lambda * 1.3)  # Boost

        # Adjustment 2: If Pareto front hasn't grown in 10 experiments, force explore
        if self.pareto_stagnation_count > 10:
            self.base_lambda = max(self.base_lambda, 1.5)

        # Adjustment 3: If diversity metric is low, boost exploration
        if self.config_diversity() < 0.3:
            self.base_lambda = max(self.base_lambda, 1.0)

        return self.base_lambda
```

---

## 8. Long-Running Agent Harness Architecture

### 8.1 The Context Degradation Problem

The fundamental challenge of long-running LLM agents is context window management. Over 100 experiments:
- Each experiment cycle generates ~2000 tokens (recommendation, code edit, run output, logging)
- 100 experiments = ~200K tokens of conversation history
- Context windows are finite — compaction loses detail
- The agent's "memory" of experiments 1-30 is fuzzy by experiment 80

### 8.2 Three-Layer Memory Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: PERSISTENT STATE (never compacted)            │
│                                                         │
│  abes_state.json:                                       │
│    - All experiment results (structured)                │
│    - Per-action-type posterior parameters                │
│    - Pareto front                                       │
│    - Dead ends list                                     │
│    - Configuration history (full configs)               │
│    - Surrogate model parameters (serialized)            │
│                                                         │
│  results.tsv: Full experiment log                       │
│  config_history.json: Every config ever evaluated       │
│  surrogate_model.pkl: Pickled TPE/GP model              │
│                                                         │
│  → Survives any context compaction                      │
│  → Source of truth for all optimization decisions        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Layer 2: WORKING CONTEXT (recent experiments)          │
│                                                         │
│  Last 10 experiment summaries in agent context:         │
│    - Config tried, result, keep/discard                 │
│    - Key learnings from each                            │
│                                                         │
│  Current best config details                            │
│  Active hypotheses being tested                         │
│                                                         │
│  → Compacted periodically, oldest entries dropped       │
│  → Enough for the agent to maintain continuity          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Layer 3: RECOVERY PROTOCOL (compaction-safe)           │
│                                                         │
│  When context is compacted:                             │
│  1. python3 abes_engine.py status  → full state dump    │
│  2. Read results.tsv → all experiment history           │
│  3. Read train.py → current best approach               │
│  4. Engine recommend → next action with full context    │
│                                                         │
│  → Agent can fully recover from any compaction          │
│  → Engine state is the ground truth, not agent memory   │
└─────────────────────────────────────────────────────────┘
```

### 8.3 Checkpoint-Resumable Experiment Loop

```python
class ExperimentHarness:
    """Long-running harness that is resumable from any point."""

    def __init__(self, budget=100, checkpoint_interval=10):
        self.budget = budget
        self.checkpoint_interval = checkpoint_interval

    def run(self):
        """Main loop with checkpointing."""
        state = self.load_or_init_state()

        for t in range(state["experiment_count"], self.budget):
            # 1. Generate recommendation (deterministic from state)
            recommendation = self.engine.recommend(state)

            # 2. Generate exact configuration
            config = self.proposer.propose(recommendation, state)

            # 3. Write config to file for agent/automated execution
            self.write_config(config, f"experiment_{t}.json")

            # 4. Execute (either automated or via agent)
            result = self.execute(config)

            # 5. Update all state
            state = self.update_state(state, config, result)

            # 6. Checkpoint
            if t % self.checkpoint_interval == 0:
                self.save_checkpoint(state)
                self.print_progress_report(state, t)

            # 7. Early stopping checks
            if self.should_stop_early(state):
                break

        self.save_final_report(state)
```

### 8.4 Agent Instruction Protocol (Compaction-Safe)

```markdown
## Recovery Protocol (MUST RUN after any context compaction)

1. `python3 abes_engine.py status` — read the full state dump
2. `cat results.tsv | tail -5` — see the 5 most recent experiments
3. `cat train.py` — see the current best approach
4. `python3 abes_engine.py recommend` — get the next action
5. Resume the experiment loop from the recommendation

CRITICAL: The engine's state is always correct. If your memory of
what was tried conflicts with the engine's records, TRUST THE ENGINE.
```

### 8.5 Dead-End Memory System

```python
class DeadEndTracker:
    """Prevents retrying known failures across runs."""

    def __init__(self):
        self.dead_ends = []  # Semantic descriptions
        self.config_blacklist = []  # Structured configs that failed badly

    def check_proposed(self, config):
        """Returns True if this config is too similar to a known dead end."""
        for dead_config in self.config_blacklist:
            distance = self.config_distance(config, dead_config)
            if distance < 0.1:  # Within 10% of a dead end
                return True, dead_config
        return False, None

    def add_dead_end(self, config, reason):
        """Record a dead end with structured config AND semantic reason."""
        self.dead_ends.append(reason)
        self.config_blacklist.append(config)

    def config_distance(self, a, b):
        """Normalized distance between two configs (0=identical, 1=maximally different)."""
        if a.get("model") != b.get("model"):
            return 1.0  # Different models are maximally different
        # For same model: normalized HP distance
        distances = []
        for key in set(list(a.get("hps", {}).keys()) + list(b.get("hps", {}).keys())):
            va = a.get("hps", {}).get(key, 0)
            vb = b.get("hps", {}).get(key, 0)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                distances.append(abs(va - vb) / max(abs(va), abs(vb), 1e-8))
        return np.mean(distances) if distances else 1.0
```

---

## 9. Concrete Implementation Roadmap

### Phase 1: Upgrade ABES Engine (Immediate)

**Goal**: Make the optimization brain fully computational, eliminating agent intuition from numerical decisions.

| Task | Effort | Impact |
|------|--------|--------|
| Add Thompson Sampling to `recommend` | 2h | High — enables stochastic exploration |
| Add ConfigurationProposer that outputs exact configs | 4h | Critical — removes agent intuition from inner optimization |
| Add continuous reward signal (not just keep/discard) | 2h | Medium — improves posterior quality |
| Add dead-end proximity checking | 1h | Medium — prevents known-failure retries |
| Add multi-fidelity mode to engine recommend | 3h | High — enables Hyperband |

### Phase 2: Implement Hyperband Multi-Fidelity (Next)

**Goal**: 5× increase in search breadth per experiment slot.

| Task | Effort | Impact |
|------|--------|--------|
| Implement Hyperband bracket scheduler | 4h | Critical — core efficiency gain |
| Modify train.py to accept fidelity parameter | 2h | Required for Hyperband |
| Add n_estimators and data_fraction as fidelity axes | 1h | Required |
| Add rank correlation validation (low-fi vs full-fi) | 2h | Safety — ensures low-fi predicts full-fi |

### Phase 3: Expand Search Space (Break the Ceiling)

**Goal**: Cross model-class boundaries to find configurations above 0.85.

| Task | Effort | Impact |
|------|--------|--------|
| Add MLP/TabNet as model families | 3h | High — new model class |
| Add stacking meta-learner | 3h | High — ensemble diversity |
| Add focal loss / asymmetric loss | 2h | Medium — better minority handling |
| Add autoencoder feature extraction | 4h | Medium — new feature space |
| Formalize full search space as Optuna conditional config | 3h | Critical — enables unified BO |

### Phase 4: Evolutionary Co-Optimization (T≥100)

**Goal**: Evolve feature-model configurations using genetic operators.

| Task | Effort | Impact |
|------|--------|--------|
| Implement chromosome structure | 2h | Required |
| Implement crossover and mutation operators | 3h | Medium |
| Implement population management (μ+λ ES) | 2h | Medium |
| Integrate with ABES as a sub-strategy under A_restart | 2h | Medium |

### Phase 5: Full Pareto + Meta-Learning (T≥200)

**Goal**: Multi-objective optimization with cross-run knowledge transfer.

| Task | Effort | Impact |
|------|--------|--------|
| Implement hypervolume-based experiment selection | 3h | Medium |
| Serialize surrogate model between runs | 2h | Medium |
| Implement RGPE for cross-run transfer | 4h | Medium |
| Build configuration portfolio (top-10 diverse configs) | 2h | Medium |

---

## 10. Expected Impact Analysis

### Conservative Estimates

| Improvement | PR-AUC Delta | Mechanism |
|-------------|-------------|-----------|
| Thompson Sampling + proper exploration | +0.003-0.005 | Discovers basins that deterministic search misses |
| Hyperband multi-fidelity | +0.002-0.005 | 5× more configs explored, better basin coverage |
| Neural network model family | +0.005-0.015 | Crosses the tree-ensemble ceiling |
| Proper stacking | +0.003-0.008 | Ensemble diversity captures different aspects |
| Continuous rewards + better posteriors | +0.001-0.003 | More informative optimization signal |
| **Total estimated** | **+0.014-0.036** | |
| **Projected best** | **0.860-0.882** | Up from 0.846 |

### At Different Budget Scales

| Budget | Current System | Upgraded System | Gap |
|--------|---------------|-----------------|-----|
| T=20 | 0.846 (warm-start replay) | 0.850-0.855 | +0.004-0.009 |
| T=100 | 0.846 (same ceiling) | 0.860-0.870 | +0.014-0.024 |
| T=500 | Not tested | 0.870-0.880 | N/A |
| T=1000 | Not tested | 0.875-0.890 | N/A |

### Key Insight

The current system's ceiling is not an optimization failure — it's a **search space confinement**. The optimization engine (ABES) is reasonably good at finding the best XGBoost configuration. The problem is that the best XGBoost configuration is not the best possible model for this dataset.

The single most impactful change is **expanding the model family space** beyond tree ensembles. The second most impactful change is **multi-fidelity search** (Hyperband) to explore that expanded space efficiently. Everything else is incremental improvement on top of these two.

---

## Appendix A: Summary of All 140 Experiments Across Three Runs

### Mar30 (20 experiments)
- 5 experiments on XGBoost, found 0.834 basin
- 1 LightGBM (buggy, 0.037), 1 CatBoost (wrong config, 0.776)
- 0 controlled single-variable experiments
- Honest best: 0.8337

### Apr01 (100 experiments)
- Experiments 1-12: Model tournament (A-grade ABES compliance)
- Experiments 13-25: Good but starting to over-exploit (B+ grade)
- Experiments 26-56: **31-experiment plateau** (D grade, the critical failure)
- Experiment 57: **Breakthrough** via multi-fidelity proxy search (the most important experiment)
- Experiments 58-71: Excellent post-breakthrough refinement (A grade)
- Experiments 72-100: Diminishing returns, 4 dead-end retries (C+ grade)
- Best: 0.845984

### Apr03 (20 experiments, engine-driven)
- Experiment 1: Warm-start XGBoost baseline (0.839)
- Experiments 2-11: Model family tournament + feature/imbalance exploration
- Experiment 12: Basin jump to known optimal (0.846)
- Experiments 13-20: Verification and alternatives (all discards)
- Best: 0.845984

## Appendix B: Critical Configuration Comparison

The three best configs found across all runs are essentially identical:

```python
# Apr01/Apr03 best (0.845984)
XGBClassifier(
    n_estimators=1500, max_depth=6, learning_rate=0.0777,
    scale_pos_weight=ratio, subsample=0.806, colsample_bytree=0.943,
    reg_alpha=0.0, reg_lambda=0.5, min_child_weight=7,
)
# Features: Amount, V1-V28, log_amount, Amt_V1, Amt_V2 (33 total)

# Mar30 best (0.8337)
XGBClassifier(
    n_estimators=600, max_depth=5, learning_rate=0.05,
    scale_pos_weight=ratio, subsample=0.8, colsample_bytree=0.8,
    reg_alpha=1.0, reg_lambda=1.0, min_child_weight=5,
)
# Features: Amount, V1-V28 + 9 engineered (39 total, but many noisy)
```

The delta between these two configs accounts for the entire 0.012 improvement across 120 experiments. This is one basin shift, discovered by one lucky multi-fidelity search at apr01 experiment 57.

## Appendix C: Algorithm Implementation Status Matrix (Updated)

| Algorithm | Strategy Doc | abes_engine.py v1 | Proposed v2 |
|-----------|-------------|-------------------|-------------|
| Thompson Sampling | Designed (Section VII) | Not implemented | Full Beta/Normal posteriors |
| UCB1 | Designed (Section 4.2) | Approximated via urgency | Formal UCB bonus |
| TPE / Bayesian Optimization | Designed (Section 4.1) | Delegated to Optuna (ad-hoc) | Integrated ConfigurationProposer |
| Hyperband / Multi-Fidelity | Designed (Section 4.4) | screen_configs (A_restart only) | Full Hyperband with 4 brackets |
| Evolutionary Crossover | Designed (Section 4.3) | Not implemented | FeatureModelEvolution class |
| Pareto / Multi-Objective | Designed (Section III) | Tracked but unused for decisions | Hypervolume-based selection |
| Urgency Scores | Designed (Section VII) | Fully computed | Enhanced with reward adaptation |
| λ_explore Decay | Designed (Section VII) | Implemented (static sigmoid) | Dynamic, reward-adaptive |
| Warm-Start / Meta-Learning | Designed (Section IX) | Dead ends + feature priors | Surrogate model transfer (RGPE) |
| Anomaly Detection | Designed (Section VII) | Implemented (static threshold) | Model-family-adaptive threshold |
| **Implementation coverage** | **100%** | **~45%** | **~90% (target)** |
