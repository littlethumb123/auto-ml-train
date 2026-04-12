# Optimization Strategy Research: Improving Auto-Train with Formal Algorithms

**Date**: 2026-03-31 (Rev 2: 2026-03-31)
**Context**: Post-mortem analysis of `autotrain/mar30` run (20/20 experiments, best honest val_pr_auc = 0.8337)
**Goal**: Design a principled, adaptive, budget-agnostic experiment selection strategy using optimization algorithms and exploration/exploitation tradeoffs

---

## Table of Contents

1. [Problem Formulation](#i-problem-formulation)
2. [Why the Current Strategy Fails](#ii-why-the-current-strategy-fails)
3. [Multi-Objective Optimization: Beyond PR-AUC](#iii-multi-objective)
4. [Optimization Algorithms for Experiment Selection](#iv-optimization-algorithms)
   - 4.1 Bayesian Optimization (BO)
   - 4.2 Multi-Armed Bandits (MAB)
   - 4.3 Genetic / Evolutionary Algorithms (EA)
   - 4.4 Successive Halving / Hyperband
   - 4.5 Population-Based Training (PBT)
5. [Exploration vs. Exploitation Frameworks](#v-exploration-vs-exploitation)
6. [The Two-Level Search Problem](#vi-two-level-search)
7. [REVISED: Adaptive Bayesian Experiment Selection (ABES)](#vii-abes)
8. [Budget-Adaptive Scaling: 20 → 100 → 1000](#viii-budget-scaling)
9. [Meta-Learning: Learning Across Runs](#ix-meta-learning)
10. [Comparison Matrix](#x-comparison-matrix)
11. [Recommendations](#xi-recommendations)

---

## I. Problem Formulation

### What Are We Actually Optimizing?

The auto-train agent faces a **multi-objective combinatorial optimization problem** with a variable evaluation budget:

```
maximize   F(config) = [val_pr_auc(config), lift@10%(config), macro_f1(config)]
subject to:
  - config ∈ C = C_model × C_features × C_hyperparams × C_preprocessing
  - |evaluations| ≤ T  (T ∈ {20, 100, 1000, ...} — variable budget)
  - time(evaluation) ≤ 60 seconds
  - search is sequential (no parallel evaluations)
```

The search space `C` is not a simple continuous hypercube. It has:

| Dimension | Type | Cardinality |
|-----------|------|-------------|
| Model family | Categorical (7 choices) | 7 |
| Class imbalance strategy | Categorical (6 choices) | 6 |
| Feature engineering | Subset selection (9+ features) | 2⁹ = 512 |
| Feature selection | Continuous threshold + method | ∞ |
| Hyperparameters per model | Mixed (continuous + discrete) | ~5-10 dims per model |
| Preprocessing | Categorical (5 choices) | 5 |

Rough estimate: **|C| ≈ 7 × 6 × 512 × 5 × 10⁵ ≈ 10⁹** candidate configurations.

Even at T=1000 experiments, the sampling ratio is 10⁻⁶. No brute-force or grid search is feasible at any realistic budget.

### Why This Is Harder Than Standard HPO

Standard hyperparameter optimization (HPO) assumes:
1. **Fixed model family** — you're tuning XGBoost, not choosing between XGBoost and LightGBM
2. **Fixed feature set** — features are given, not designed
3. **Smooth objective** — small HP changes → small metric changes
4. **Abundant budget** — Optuna typically runs 100-1000 trials

Our problem violates all four:
1. Model family is a first-class decision variable
2. Feature engineering is part of the search
3. The objective is **discontinuous** — switching model families causes large jumps; a LightGBM bug gives 0.036 vs. XGBoost's 0.814
4. Budget is **20 evaluations total**, not 20 per model

This is closer to **Algorithm Configuration** or **Combined Algorithm Selection and Hyperparameter optimization (CASH)** — the problem Auto-WEKA and Auto-sklearn were designed for.

---

## II. Why the Current Strategy Fails

The post-mortem identified the symptoms. Here's the root cause analysis through the lens of optimization theory:

### 1. Greedy Hill-Climbing Without Restarts

The mar30 run followed a **greedy best-first strategy**: always extend the current best config. After exp 5 established XGBoost + features as the incumbent, every subsequent experiment was a local perturbation.

**Optimization diagnosis**: Pure exploitation, zero exploration. In optimization terms, this is gradient descent with a step size of 1, no momentum, no random restarts. It will find the nearest local optimum and stay stuck.

### 2. No Surrogate Model of the Search Space

The agent made decisions based on **immediate previous results** without maintaining a model of how performance varies across the space. There was no mechanism to answer: "Given that XGBoost scores 0.83, what do we *expect* LightGBM to score?" or "Is it worth trying depth=7 given that depth=5 beats depth=4?"

**Optimization diagnosis**: Model-free optimization. Every evaluation is treated as independent, wasting information. Bayesian optimization would build a surrogate (Gaussian Process or Tree Parzen Estimator) that predicts performance in unexplored regions.

### 3. Catastrophic Failure Handling

When LightGBM scored 0.036, the agent treated it as a legitimate signal ("LightGBM is bad") rather than as an anomaly. There was no mechanism to distinguish between:
- **Signal**: The model genuinely performs poorly (like LogReg at 0.68 on this task)
- **Noise/Bug**: The implementation is broken and the score is meaningless

**Optimization diagnosis**: No outlier detection in the objective function. A robust optimizer would flag any score below the known floor (baseline = 0.68) as a suspected evaluation failure and request a retry with diagnostics.

### 4. Confounded Experiments Destroy Information

Changing 7 hyperparameters simultaneously (exp 4) yields 1 bit of information ("better/worse") when it could yield 7 bits ("which parameter helped"). The information rate per experiment was approximately:

```
Actual:     1 bit / experiment    (binary: improved or not)
Potential:  3-7 bits / experiment (if controlled: direction of each variable)
Efficiency: ~15-20% of theoretical maximum
```

**Optimization diagnosis**: This is equivalent to using a gradient-free optimizer when gradient information is available. Controlled experiments are the finite-difference analog of gradient computation in hyperparameter space.

---

## III. Multi-Objective Optimization: Beyond PR-AUC

### Why a Single Metric Is Insufficient

PR-AUC measures ranking quality across all thresholds, but fraud detection in production has specific operational requirements:

| Metric | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **val_pr_auc** | Area under Precision-Recall curve | Overall ranking quality; threshold-agnostic |
| **lift@10%** | Precision in top 10% of scored transactions ÷ base rate | Operational efficiency: "If I investigate the top 10% of flagged transactions, how many are actual fraud?" |
| **macro_f1** | Harmonic mean of per-class F1 scores | Balanced performance across majority and minority class |

These metrics can **conflict**:
- A model optimized purely for PR-AUC might sacrifice precision at high-confidence thresholds (hurting lift@10%)
- A model optimized for macro_F1 might set a conservative threshold, missing some fraud (lower recall part of PR-AUC)
- Lift@10% rewards extreme discrimination at the top of the score distribution, while PR-AUC and macro_F1 care about the full distribution

### Metric Definitions

```python
def lift_at_k(y_true, y_prob, k=0.10):
    """Lift at top k% of predictions."""
    n = len(y_true)
    top_k = int(n * k)
    # Sort by predicted probability descending
    sorted_indices = np.argsort(y_prob)[::-1][:top_k]
    precision_at_k = y_true.iloc[sorted_indices].mean()
    base_rate = y_true.mean()
    return precision_at_k / base_rate

def macro_f1(y_true, y_pred):
    """Macro-averaged F1 across both classes."""
    return f1_score(y_true, y_pred, average='macro')
```

### Multi-Objective Strategies

#### Strategy 1: Scalarization (Simple)

Combine metrics into a single scalar objective:

```python
# Weighted linear scalarization
objective = w1 * val_pr_auc + w2 * normalize(lift_at_10) + w3 * macro_f1

# Default weights (adjustable):
w1, w2, w3 = 0.50, 0.30, 0.20
```

**Pros**: Simple, compatible with all single-objective optimizers.
**Cons**: Weights are subjective; sensitive to normalization; can miss Pareto-optimal solutions that don't maximize the weighted sum.

**When to use**: Early experiments (budget < 50), when the metrics are positively correlated (common for fraud detection — a better model usually improves all three).

#### Strategy 2: Lexicographic Ordering (Prioritized)

```
1. Primary gate:  val_pr_auc ≥ threshold_1 (e.g., ≥ 0.80)
2. Secondary gate: lift@10% ≥ threshold_2 (e.g., ≥ 50)
3. Optimize:       macro_f1 among configs that pass both gates
```

**Pros**: Guarantees minimum performance on primary metrics. Clear priorities.
**Cons**: Rigid thresholds lose information; might reject configs that narrowly miss gate 1 but excel on gate 2.

**When to use**: When business requirements define hard constraints ("PR-AUC must exceed 0.80, then maximize lift").

#### Strategy 3: Pareto Front Tracking (Comprehensive)

Maintain the **Pareto front** — the set of configurations where no other config dominates on all metrics:

```
Config A dominates Config B iff:
  A.pr_auc ≥ B.pr_auc AND A.lift ≥ B.lift AND A.macro_f1 ≥ B.macro_f1
  with at least one strict inequality
```

At any point during the search, the Pareto front represents the **set of optimal trade-offs**. The agent should:
1. Track the full Pareto front, not just the single "best" config
2. When exploring, prefer configs in under-explored regions of the Pareto front
3. When exploiting, prefer configs near the current best on the primary metric

```python
# Example Pareto front after 50 experiments:
pareto = [
    {"config": "xgb_deep",   "pr_auc": 0.845, "lift": 120, "macro_f1": 0.72},  # Best PR-AUC
    {"config": "xgb_tuned",  "pr_auc": 0.835, "lift": 180, "macro_f1": 0.75},  # Best lift
    {"config": "lgbm_bal",   "pr_auc": 0.820, "lift": 150, "macro_f1": 0.82},  # Best macro_F1
    # All three are Pareto-optimal — none dominates any other on ALL metrics
]
```

**When to use**: Budget ≥ 100, when there's no clear hierarchy among metrics, or when the final choice of metric weights will be made post-search.

#### Strategy 4: Hypervolume-Based Selection (Formal Multi-Objective)

The **hypervolume indicator** measures the volume of objective space dominated by the Pareto front. A larger hypervolume means a better set of solutions.

```
For each candidate experiment x:
  HV_improvement(x) = E[ HV(Pareto_front ∪ {x}) - HV(Pareto_front) ]

Select x* = argmax HV_improvement(x)
```

This naturally balances:
- Improving the best on any single metric (pushes the front outward)
- Filling gaps in the Pareto front (increases hypervolume from below)

Compatible with multi-objective BO (e.g., **ParEGO**, **EHVI**, **NSGA-II** for generating Pareto sets).

### Recommended Multi-Objective Approach

| Budget | Approach | Rationale |
|--------|----------|-----------|
| T ≤ 50 | Scalarization (0.5/0.3/0.2 weights) | Too few points for Pareto analysis; keep it simple |
| 50 < T ≤ 200 | Lexicographic with Pareto tracking | Enough data to spot metric conflicts; track front but optimize scalarized |
| T > 200 | Full Pareto + Hypervolume | Sufficient budget to populate the Pareto front meaningfully |

### Impact on Results Logging

Expand `results.tsv` schema:

```
commit | val_pr_auc | lift_at_10 | macro_f1 | val_f1 | status | n_features | model_family | action_type | hypothesis | learning
```

The `status` column rule changes from "keep if pr_auc improved" to:
- **keep**: New point is on the Pareto front (or improves scalarized objective)
- **discard**: Dominated by an existing point on all metrics
- **archive**: Not Pareto-optimal but provides useful information (near misses)

---

## IV. Optimization Algorithms for Experiment Selection

### 4.1 Bayesian Optimization (BO)

**Core idea**: Build a probabilistic surrogate model of f(config) → val_pr_auc, then use an **acquisition function** to decide which config to evaluate next.

#### How It Works

```
for t = 1 to 20:
    1. Fit surrogate model M to {(config_i, score_i)} for i = 1..t-1
    2. For each candidate config c:
       - Predict μ(c), σ(c) using M        # mean and uncertainty
    3. Select c* = argmax acquisition(μ, σ)  # balance explore/exploit
    4. Evaluate score_t = f(c*)
    5. Add (c*, score_t) to history
```

#### Surrogate Models

| Surrogate | Strengths | Limitations | Fit for Our Problem |
|-----------|-----------|-------------|-------------------|
| **Gaussian Process (GP)** | Principled uncertainty, smooth interpolation | O(n³) per iteration, struggles with categorical vars | Poor — our space is mostly categorical |
| **Tree Parzen Estimator (TPE)** | Handles mixed types, fast, scales well | Independent marginals (ignores HP interactions) | Good — Optuna uses this |
| **Random Forest surrogate (SMAC)** | Handles categoricals, captures interactions, fast | Less principled uncertainty than GP | Excellent — designed for algorithm configuration |
| **Neural network (BOHB)** | Flexible, can model complex surfaces | Needs many points to train | Excellent at T≥200 — BOHB is state-of-the-art for large-budget AutoML |

**Recommendation**: At T=20-50, use TPE. At T=100+, use SMAC (RF surrogate). At T=500+, BOHB (BO + Hyperband).

#### Acquisition Functions

The acquisition function balances exploration (try uncertain regions) vs. exploitation (try regions predicted to be good):

| Function | Formula | Behavior |
|----------|---------|----------|
| **Expected Improvement (EI)** | E[max(f(x) - f*, 0)] | Conservative; good with limited budget |
| **Upper Confidence Bound (UCB)** | μ(x) + κ·σ(x) | κ controls explore/exploit; κ=2 is greedy, κ=5 is exploratory |
| **Probability of Improvement (PI)** | P(f(x) > f* + ξ) | Tends to exploit too much |
| **Knowledge Gradient (KG)** | Expected value of being able to observe x | Optimal per-step, expensive to compute |
| **Thompson Sampling** | Sample from posterior, optimize sample | Natural exploration; well-calibrated |

**For small budgets (T≤50), Expected Improvement (EI) is the best choice.** It naturally becomes more exploitative as the budget runs out. **For large budgets (T≥200), Knowledge Gradient (KG) or Thompson Sampling** provide better long-horizon planning and natural exploration respectively.

#### Applying BO to Our Problem

The critical insight: **BO should operate at the experiment-design level, not just the hyperparameter level.**

```python
# Search space definition for BO
space = {
    # Level 1: Structural choices (categorical)
    "model_family": Categorical(["xgboost", "lightgbm", "catboost", "rf", "gbm", "et"]),
    "imbalance_strategy": Categorical(["scale_pos_weight", "smote", "undersample", "none"]),
    "feature_set": Categorical(["raw", "raw+log_amount", "raw+time", "raw+interactions", "full_engineered"]),
    "preprocessing": Categorical(["none", "robust_scaler", "standard_scaler"]),

    # Level 2: Continuous HPs (conditional on model_family)
    "learning_rate": LogUniform(0.01, 0.3),
    "max_depth": Integer(3, 8),
    "n_estimators": Integer(100, 2000),
    "subsample": Uniform(0.6, 1.0),
    "reg_alpha": LogUniform(0.01, 10.0),
    "reg_lambda": LogUniform(0.01, 10.0),
}
```

**Limitation**: With T=20, the surrogate has few points to fit. BO becomes most effective after ~10 observations. At T=100+, the surrogate is well-calibrated and BO dominates random search. At T=1000+, BOHB with multi-fidelity is the clear winner.

**Mitigation**: Use **warm-starting** from the mar30 run (20 prior observations) and from domain knowledge (known priors about tree model hyperparameters).

---

### 4.2 Multi-Armed Bandits (MAB)

**Core idea**: Treat each model family (or strategy category) as an "arm." Pull the arm that's most likely to yield the best reward, while maintaining some exploration of under-sampled arms.

#### Mapping to Our Problem

```
Arms:
  - Arm 1: XGBoost family (tuning within XGBoost)
  - Arm 2: LightGBM family
  - Arm 3: CatBoost family
  - Arm 4: RandomForest family
  - Arm 5: Ensemble strategies
  - Arm 6: Feature engineering (model-agnostic)
  - Arm 7: Preprocessing variations

Reward: Improvement in val_pr_auc from current best
Budget: 20 pulls
```

#### Bandit Algorithms

| Algorithm | Approach | Exploration | Fit |
|-----------|---------|-------------|-----|
| **ε-greedy** | With prob ε, explore random arm; else best arm | Fixed exploration rate | Simple but wasteful |
| **UCB1** | Play arm with highest μ̂ + c·√(ln(t)/nᵢ) | Decreasing; favors under-sampled arms | Good — penalizes dismissing LightGBM after 1 try |
| **Thompson Sampling** | Sample from Beta(successes+1, failures+1), play highest sample | Naturally adaptive | Excellent — handles uncertainty |
| **EXP3** | For adversarial/non-stationary rewards | Strong exploration | Overkill — our rewards aren't adversarial |

#### UCB1 Analysis of Mar30

Let's retroactively apply UCB1 to the mar30 run. After 20 experiments:

```
Arm (Model)     | Pulls | Avg Score | UCB Score (c=√2)
XGBoost         |  12   | 0.806     | 0.806 + √2·√(ln(20)/12) = 0.806 + 0.72 = 1.53
LightGBM        |   1   | 0.037     | 0.037 + √2·√(ln(20)/1)  = 0.037 + 2.45 = 2.49  ← HIGHEST!
CatBoost        |   1   | 0.776     | 0.776 + √2·√(ln(20)/1)  = 0.776 + 2.45 = 3.22  ← HIGHEST!
RandomForest    |   0   | —         | ∞  ← MUST TRY
Ensemble        |   3   | 0.807     | 0.807 + √2·√(ln(20)/3)  = 0.807 + 1.41 = 2.22
Feature-only    |   3   | 0.794     | 0.794 + √2·√(ln(20)/3)  = 0.794 + 1.41 = 2.20
```

**UCB1 would have demanded more LightGBM, CatBoost, and RF pulls.** The exploration bonus for 1-pull arms is enormous. The confirmation bias toward XGBoost (12 pulls) directly violates UCB — the exploration bonus for XGBoost is negligible (c·√(ln(20)/12) = 0.72) while under-explored arms have bonuses of 2.45+.

#### Hierarchical Bandits

The search space has natural hierarchy: model family → hyperparameters → features. A **hierarchical bandit** can handle this:

```
Level 1: MAB over {model families}
  - UCB1 or Thompson Sampling to select model family
Level 2: Within selected family, MAB over {HP configurations}
  - Thompson Sampling with continuous prior
Level 3: Feature engineering applied across families
  - Separate MAB arm for "try feature X with current best"
```

This is closely related to **Monte Carlo Tree Search (MCTS)** — the algorithm behind AlphaGo. MCTS naturally handles hierarchical action spaces with UCB-based exploration.

**Limitation**: MAB treats arms as independent. But model families share information — if tree-based models do well, all tree-based families are likely good. This argues for **contextual bandits** or **Bayesian approaches** that share information.

---

### 4.3 Genetic / Evolutionary Algorithms (EA)

**Core idea**: Maintain a **population** of configurations. Evolve them through selection, crossover, and mutation.

#### Standard EA Framework

```
1. Initialize population P = {config_1, ..., config_k} randomly
2. Evaluate fitness f(config_i) for all i
3. Select parents: tournament or rank-based selection
4. Crossover: combine parts of two parent configs to create offspring
5. Mutation: randomly perturb offspring
6. Replace: survival of the fittest
7. Repeat from step 2 until budget exhausted
```

#### Applying EA to Our Problem

```python
# A "chromosome" encodes a full experiment configuration
chromosome = {
    "model": "xgboost",           # Gene 1: categorical
    "features": [1,0,1,0,1,0,1,0,0],  # Gene 2: binary mask (which features to add)
    "lr": 0.05,                   # Gene 3: continuous
    "depth": 5,                   # Gene 4: integer
    "n_estimators": 500,          # Gene 5: integer
    "subsample": 0.8,             # Gene 6: continuous
    "imbalance": "scale_pos_weight",  # Gene 7: categorical
}

# Crossover example: combine XGBoost HP config with LightGBM feature set
parent1 = {"model": "xgboost", "lr": 0.05, "features": [1,1,1,0,0,0,0,0,0]}
parent2 = {"model": "lightgbm", "lr": 0.1, "features": [0,0,0,1,1,1,1,1,1]}
child   = {"model": "xgboost", "lr": 0.05, "features": [0,0,0,1,1,1,1,1,1]}
# Took model+lr from parent1, features from parent2

# Mutation: randomly perturb one gene
child_mutated = {"model": "xgboost", "lr": 0.07, "features": [0,0,0,1,1,1,1,1,1]}
```

#### EA Variants Ranked for Our Use Case

| Variant | Population Size | Budget Required | Fit |
|---------|----------------|-----------------|-----|
| **(1+1) ES** | 1 incumbent + 1 offspring | 20 is ok | Reasonable — equivalent to hill-climbing with mutation |
| **(μ+λ) ES** | μ=3 parents, λ=3 offspring | ~30+ needed | Marginal — population too small for genetic diversity |
| **CMA-ES** | Adapts covariance matrix of mutations | 50+ needed | Poor — designed for continuous spaces, needs more budget |
| **NSGA-II** | Multi-objective Pareto front | 100+ needed | Excellent at T≥200 — designed for multi-objective optimization |
| **Differential Evolution** | Population-based with difference vectors | 40+ needed | Poor — too few evals |
| **Regularized EA (REA)** | Like (μ+λ) but old configs die | 30+ needed | Marginal |

**Key problem**: Evolutionary algorithms are **population-based** and need O(population_size × generations) evaluations. With budget=20 and minimum population=5, we get 4 generations. That's barely enough for evolution to start working.

#### When EAs Beat BO

EAs excel when:
- The search space is highly discrete/combinatorial (✓ our case has many categoricals)
- The objective is noisy (partially ✓ — PR-AUC has some variance across splits)
- We need diverse solutions, not just one optimum (✗ — we want the single best)
- Budget is large (✗ — budget is tiny)

**Verdict**: Pure EA is not ideal for T=20 budget. At T=100+, (μ+λ) ES with population 10-20 becomes competitive. At T=500+, full CMA-ES and differential evolution are strong choices. **EA-inspired operators** (crossover for recombining feature sets, mutation for HP perturbation) are useful as **proposal mechanisms** within ABES at any budget.

---

### 4.4 Successive Halving / Hyperband

**Core idea**: Start many configurations with a small evaluation budget (e.g., 100 trees instead of 2000), eliminate the bottom half, double the budget for survivors, repeat.

#### Successive Halving (SH)

```
Round 1: Evaluate 16 configs with 125 trees each     → keep top 8
Round 2: Evaluate 8 configs with 250 trees each       → keep top 4
Round 3: Evaluate 4 configs with 500 trees each       → keep top 2
Round 4: Evaluate 2 configs with 1000 trees each      → keep top 1 (WINNER)
Total evaluations: 16 + 8 + 4 + 2 = 30 (but each is cheaper in early rounds)
```

#### Applying to Our Problem

The "fidelity" knob can be:
- **n_estimators** (100 → 500 → 2000 trees)
- **training data fraction** (10% → 25% → 50% → 100%)
- **cross-validation folds** (1-fold → 2-fold → 5-fold)

```
Budget: 20 evaluations (but early rounds are cheap)
Round 1: 8 configs × n_estimators=100 × 25% data    → 8 evals (~3s each) → top 4
Round 2: 4 configs × n_estimators=300 × 50% data    → 4 evals (~10s each) → top 2
Round 3: 2 configs × n_estimators=1000 × 100% data  → 2 evals (~30s each) → top 1
Total: 14 evaluations, 6 remaining for refinement
```

This is **massively more efficient** than the mar30 approach. In 14 evaluations, we explored 8 different configurations and identified the best 2, versus the mar30 run which committed full 60-second evaluations to configs that scored 0.036.

#### Hyperband

Hyperband runs **multiple brackets** of SH with different aggressiveness:

```
Bracket 1 (aggressive): 16 configs, start at n_estimators=100
Bracket 2 (moderate):    8 configs, start at n_estimators=250
Bracket 3 (conservative): 4 configs, start at n_estimators=500
Bracket 4 (full budget):  2 configs, start at n_estimators=1000
```

This hedges against the risk that the cheapest fidelity level has poor rank correlation with full fidelity.

**Key insight**: If XGBoost with 100 trees scores 0.79 and LightGBM with 100 trees scores 0.01, we can be fairly confident the LightGBM result is a bug — real model quality differences shouldn't be that large at any fidelity level. This provides automatic anomaly detection.

#### BOHB (Bayesian Optimization + Hyperband)

BOHB combines BO's surrogate-guided search with Hyperband's multi-fidelity evaluation:
1. Use TPE to propose configurations (BO component)
2. Use Hyperband's bracket schedule to evaluate them cheaply first (SH component)
3. Feed results back to TPE to improve proposals

This is currently **state of the art** for AutoML with limited budgets.

**Applicability to our problem**: BOHB is designed for exactly the constraint structure we face (limited budget, mixed search space, multi-fidelity). However, it requires the fidelity dimension to be meaningful — early stopping at 100 trees must predict final performance at 2000 trees. For gradient boosting, this is generally true (rank correlation between 100-tree and 2000-tree performance ≈ 0.7-0.85).

---

### 4.5 Population-Based Training (PBT)

**Core idea**: Run a population of models in parallel, periodically **exploit** (copy weights from best performer) and **explore** (perturb hyperparameters).

```
Population: [config_1, config_2, ..., config_k]
Every T steps:
  - If my performance is in bottom 25%:
    - Copy weights from a top-25% performer (exploit)
    - Perturb their HPs by ±20% (explore)
  - Otherwise: keep training
```

**Relevance**: PBT is designed for neural network training where weights can be copied mid-training. For tree models (XGBoost, LightGBM), there's no meaningful "copy weights" operation — you can't transplant a half-trained XGBoost forest into a LightGBM model.

**Adaptation for tree models**: Instead of copying weights, PBT's schedule concept can be adapted:
- Run 4 configs for 250 trees each
- Bottom 2 are eliminated, top 2 continue
- Top 2 are cloned with perturbed HPs, continue training from their current checkpoint (XGBoost supports continued training via `xgb_model` parameter)

**Verdict**: Partially applicable. The "continue training" idea is relevant for XGBoost boost-from-checkpoint, but the core PBT mechanism doesn't transfer well to the sequential, 1-evaluation-at-a-time constraint of our problem.

---

## V. Exploration vs. Exploitation Frameworks

The mar30 run's central failure was excessive exploitation. Here we formalize the tradeoff and propose concrete strategies.

### The Fundamental Dilemma

At any point in the 20-experiment budget, the agent faces a choice:

| Strategy | Action | Risk |
|----------|--------|------|
| **Exploit** | Tune the best known config (XGBoost HP tweak) | Miss a better model family entirely |
| **Explore** | Try a completely new approach (SVM, stacking) | Waste budget on a dead end |

The optimal strategy depends on **how many experiments remain**:
- **Early** (exp 1-7): Explore heavily. We know nothing about the landscape.
- **Middle** (exp 8-14): Balance. We have a good incumbent; try promising alternatives.
- **Late** (exp 15-20): Exploit. Refine the best approach found.

### Formal Frameworks

#### 1. Epsilon-Schedule (Simple)

```python
def get_explore_probability(t, T):
    """Linearly decaying exploration rate. Budget-agnostic."""
    return max(0.1, 1.0 - (t / T))

# T=20:   t=1  → ε=0.95, t=10 → ε=0.50, t=18 → ε=0.10
# T=100:  t=5  → ε=0.95, t=50 → ε=0.50, t=90 → ε=0.10
# T=1000: t=50 → ε=0.95, t=500→ ε=0.50, t=900→ ε=0.10
```

Decision rule:
```python
if random() < epsilon:
    experiment = sample_unexplored_region()  # Explore: new model, new features
else:
    experiment = perturb_best_config()       # Exploit: tune current best
```

#### 2. UCB-Based Schedule (Principled)

```
Score each candidate experiment as:
  UCB(experiment) = predicted_performance(experiment) + κ · uncertainty(experiment)

κ = exploration_weight, typically √(2·ln(t))
```

This naturally explores under-sampled regions because `uncertainty(experiment)` is high when similar experiments haven't been tried.

#### 3. Knowledge Gradient (Optimal but Expensive)

```
For each candidate experiment x:
  KG(x) = E[ max_y μ_{t+1}(y | observe x) ] - max_y μ_t(y)

  "How much would observing x improve our ability to find the overall best?"
```

Knowledge Gradient is **myopically optimal** — it maximizes the expected improvement from one additional evaluation. It naturally becomes exploitative as the budget runs out because there's less value in learning about new regions when you can't act on the knowledge.

#### 4. Phased Strategy (Naive — Superseded by ABES)

> **Note**: This fixed-phase approach was the initial proposal but is too rigid. It's included here for reference — see Section VII for the adaptive ABES replacement that allows phases to emerge from the data rather than being prescribed.

Divide experiments into explicit phases with different exploration rates:

```
Phase 1: Discovery (exp 1-6)    → 100% exploration
  Purpose: Sample each major strategy region at least once
  - 1 baseline, 5 different model families with canonical configs

Phase 2: Comparison (exp 7-10)  → 70% explore, 30% exploit
  Purpose: Give promising models a fair second chance
  - Re-try top 2 non-XGBoost models with better configs
  - 1 feature engineering experiment on the best model
  - 1 controlled HP change on the best model

Phase 3: Optimization (exp 11-16) → 30% explore, 70% exploit
  Purpose: Intensify search around the best approach
  - Feature ablation on best model
  - One-variable-at-a-time HP tuning
  - 1 ensemble of top 2 models (properly tuned)

Phase 4: Refinement (exp 17-20)  → 100% exploitation
  Purpose: Squeeze the last bit of performance
  - Optuna fine-tuning with reduced search space
  - Early stopping with proper hold-out
  - Final ensemble if gain is clear
```

**This phased approach directly addresses the mar30 failure**. In the mar30 run, the agent was in Phase 3 from experiment 2 onward — it never completed Phase 1 (fair model tournament).

### Information-Theoretic View

Each experiment can be modeled as an information-gathering action. The **expected information gain (EIG)** of an experiment is:

```
EIG(experiment) = H(posterior_before) - E[H(posterior_after | observation)]
```

Where H is entropy over the space of "which config is best."

- **Exploring a new region**: High EIG because we have high uncertainty (large H) about that region.
- **Fine-tuning the incumbent**: Low EIG because we already have a good estimate of that region's performance.

The mar30 run collected most of its information in experiments 1-5, then spent experiments 6-20 collecting marginal information about a region (XGBoost HPs) that was already well-mapped.

**Optimal information gathering says**: Switch to a new region whenever the marginal EIG of exploring beats the marginal EIG of exploiting. With 7 model families and 12+ XGBoost experiments, the marginal EIG of another XGBoost experiment is near zero.

---

## VI. The Two-Level Search Problem

### Level 1: What to Try (Experiment Design)

This is the **meta-optimization** problem: selecting which experiment to run next. This is where BO, MAB, and EA concepts apply.

The search space at this level is:
```
{model_family} × {feature_set} × {imbalance_strategy} × {preprocessing}
```

This is a ~4-dimensional categorical space with ~7×5×6×5 = 1,050 combinations. With 20 experiments, we can sample ~2% of this space.

### Level 2: How to Configure It (Hyperparameter Optimization)

Given a fixed (model, features, imbalance, preprocessing) choice, optimize the continuous/integer hyperparameters.

For XGBoost: `{lr, depth, n_estimators, subsample, colsample_bytree, reg_alpha, reg_lambda, min_child_weight}` = 8 dimensions.

### Why Conflating the Levels Hurts

The mar30 run treated Levels 1 and 2 as a single flat search. Experiment 4 changed the model's regularization (Level 2) while experiment 6 changed the imbalance strategy (Level 1). The agent moved freely between levels without structure.

This is problematic because:

1. **Level 1 decisions have higher variance.** Switching from XGBoost to LightGBM can change PR-AUC by ±0.3. Changing lr from 0.05 to 0.03 changes it by ±0.01. Level 1 decisions dominate early.

2. **Level 2 decisions are only meaningful after Level 1 is settled.** Tuning XGBoost HPs is wasted effort if LightGBM would be better. The mars30 run spent 12 experiments tuning XGBoost while LightGBM got 1 buggy trial.

3. **Information doesn't transfer cleanly between levels.** Learning that `lr=0.05` is good for XGBoost tells us nothing about LightGBM's optimal learning rate. But learning that "engineered features help" likely transfers across all tree models.

### Correct Decomposition

```
Phase 1: Level 1 search — which (model, features, strategy) context is best?
  - Use MAB (UCB1 or Thompson Sampling) over model families
  - Feature engineering is model-agnostic → test once, apply to all

Phase 2: Level 2 search — optimize HPs within the winning context
  - Use BO (TPE or SMAC) within the winning model family
  - Controlled single-variable experiments for interpretability
```

This decomposition is not merely organizational — it's **mathematically optimal** under the assumption that Level 1 variance dominates Level 2 variance (which our data confirms: model family variance ≈ 0.3, HP variance within XGBoost ≈ 0.03).

---

## VII. REVISED: Adaptive Bayesian Experiment Selection (ABES)

> **Design revision**: The original HBES proposal used a rigid waterfall (Phase 1 → 2 → 3 → 4) with fixed budget allocations (35%/20%/25%/20%). This was rightly criticized as too rigid — the agent should **adaptively decide what to work on next** at every step, not be locked into a predetermined sequence.

### Core Philosophy: Every Step Is a Decision, Not a Phase Gate

Instead of "Phase 1 = models, Phase 2 = features, Phase 3 = HPs," the agent at every experiment t makes a **meta-decision** among action types:

```
Action types A = {
  A_model:      Try a new or re-try a model family
  A_feature:    Add/remove/modify engineered features
  A_hp:         Tune hyperparameters of current best model
  A_imbalance:  Change class imbalance strategy
  A_ensemble:   Combine multiple models
  A_diagnose:   Investigate an anomalous result
  A_validate:   Proper hold-out validation / early stopping
}
```

The meta-decision is governed by a **contextual bandit** that selects the action type with the highest expected marginal value, given the current state of knowledge.

### The ABES Algorithm

```
ABES(budget=T):  # T can be 20, 100, 1000, etc.

  Initialize:
    state = ExperimentState()  # Tracks all results, Pareto front, beliefs
    action_rewards = {a: GaussianPrior(μ=0, σ=1) for a in A}  # Prior on action-type value

  For t = 1 to T:

    # --- Step 1: Compute action-type scores ---
    For each action type a ∈ A:
      urgency(a)    = compute_urgency(a, state)      # How under-explored is this action type?
      opportunity(a)= compute_opportunity(a, state)   # How much improvement is possible here?
      recency(a)    = compute_recency(a, state)       # When was this action type last tried?

      # Thompson Sampling: sample from posterior of action-type reward
      θ(a) ~ Normal(μ_a, σ_a)

      # Composite score: combine sampled reward with urgency signal
      score(a) = θ(a) + λ_explore(t, T) * urgency(a) + λ_opportunity * opportunity(a)

    # --- Step 2: Select action type ---
    a* = argmax score(a)

    # --- Step 3: Within selected action type, choose specific experiment ---
    experiment = propose_experiment(a*, state)
    # Uses different sub-strategies per action type:
    #   A_model:    Thompson Sampling over model families
    #   A_feature:  Information-gain based feature selection
    #   A_hp:       BO with Expected Improvement (or GP-UCB)
    #   A_ensemble: Combine top-K from Pareto front
    #   A_diagnose: Re-run anomalous config with diagnostics

    # --- Step 4: Execute and observe ---
    result = run_experiment(experiment)
    metrics = {pr_auc, lift_at_10, macro_f1}

    # --- Step 5: Update beliefs ---
    state.add_result(experiment, metrics)
    reward = compute_reward(metrics, state)  # Improvement over previous Pareto front
    update_posterior(action_rewards[a*], reward)

    # --- Step 6: Anomaly check ---
    if is_anomalous(result, state):
      action_rewards[A_diagnose].boost()  # Increase urgency of diagnosis
      state.flag_anomaly(experiment)

  Return state.pareto_front, state.best_config
```

### Key Components Explained

#### 1. Adaptive Exploration Rate: λ_explore(t, T)

The exploration weight is **budget-proportional**, not hardcoded:

```python
def lambda_explore(t, T):
    """
    Exploration weight that adapts to remaining budget.
    High early, low late. Budget-agnostic.
    """
    fraction_remaining = (T - t) / T
    # Sigmoid-warped: fast decay early, slow decay late
    return 2.0 / (1.0 + np.exp(-5 * (fraction_remaining - 0.5)))

# For T=20:   t=1 → λ=1.92,  t=10 → λ=1.00,  t=18 → λ=0.08
# For T=100:  t=1 → λ=1.99,  t=50 → λ=1.00,  t=90 → λ=0.08
# For T=1000: t=1 → λ=2.00, t=500 → λ=1.00, t=900 → λ=0.08
```

This means at any budget:
- First ~30% of experiments: Strong exploration (λ > 1.5)
- Middle ~40%: Balanced (0.5 < λ < 1.5)
- Last ~30%: Strong exploitation (λ < 0.5)

But crucially, **the proportions shift based on actual results**. If exploration keeps finding improvements, λ stays high longer. If exploitation is yielding diminishing returns, the algorithm can switch back to exploration.

#### 2. Urgency Scores: When to Switch Action Types

```python
def compute_urgency(action_type, state):
    """
    Higher urgency = this action type has been under-explored
    relative to what the algorithm thinks is optimal.
    """
    if action_type == A_model:
        # Urgency = fraction of model families with < min_trials
        families = ["xgboost", "lightgbm", "catboost", "rf", "gbm", "et"]
        min_trials = max(2, state.total_experiments // (3 * len(families)))
        under_explored = sum(1 for f in families if state.family_count(f) < min_trials)
        return under_explored / len(families)

    elif action_type == A_feature:
        # Urgency = how many feature groups haven't been ablated
        tested = state.feature_groups_tested()
        total = state.feature_groups_available()
        return 1.0 - (tested / total) if total > 0 else 0.0

    elif action_type == A_hp:
        # Urgency inverse-proportional to recent HP experiments on best model
        recent_hp_count = state.recent_hp_experiments(window=5)
        return 1.0 / (1.0 + recent_hp_count)

    elif action_type == A_diagnose:
        # Urgency = number of anomalous results not yet investigated
        return min(1.0, state.undiagnosed_anomalies() * 0.5)

    elif action_type == A_ensemble:
        # Low urgency until ≥2 competitive models found
        competitive = state.models_within_pct(top_pct=0.05)  # Within 5% of best
        if competitive < 2: return 0.0
        return 0.3 if not state.ensemble_tried() else 0.0

    elif action_type == A_validate:
        # Only urgent near the end
        fraction_done = state.total_experiments / state.budget
        return max(0, fraction_done - 0.8) * 5.0  # Ramps up in last 20%
```

#### 3. Opportunity Scores: Where Is the Biggest Upside?

```python
def compute_opportunity(action_type, state):
    """
    Estimate expected improvement if we invest in this action type.
    Based on observed variance within each action type.
    """
    if action_type == A_model:
        # High if best model family has been tried < 3 times
        # (we might not have found its potential yet)
        best_family_trials = state.family_count(state.best_family())
        if best_family_trials < 3:
            return 0.8
        # Lower if family well-explored but untried families exist
        if state.untried_families() > 0:
            return 0.6
        return 0.2

    elif action_type == A_hp:
        # Estimate from historical variance of HP changes
        hp_deltas = state.get_metric_deltas(action_type=A_hp)
        if len(hp_deltas) < 2:
            return 0.5  # Prior: moderate opportunity
        # Expected improvement ≈ σ(deltas) * φ(0)/Φ(0) ≈ 0.8 * σ
        return 0.8 * np.std(hp_deltas)

    elif action_type == A_feature:
        feature_deltas = state.get_metric_deltas(action_type=A_feature)
        if len(feature_deltas) < 2:
            return 0.4
        return 0.8 * np.std(feature_deltas)

    # ... similar for other action types
```

#### 4. Reward Function: Multi-Metric with Pareto Awareness

```python
def compute_reward(metrics, state):
    """
    Reward = how much this experiment improved the Pareto front.
    Uses hypervolume improvement when Pareto front has ≥ 3 points,
    scalarized improvement otherwise.
    """
    if len(state.pareto_front) >= 3:
        # Hypervolume improvement (bounded [0, 1])
        hv_before = state.hypervolume()
        state.tentative_add(metrics)
        hv_after = state.hypervolume()
        state.tentative_remove()
        return (hv_after - hv_before) / hv_before  # Fractional improvement
    else:
        # Scalarized improvement
        scalarized = (0.5 * metrics['pr_auc'] +
                      0.3 * normalize(metrics['lift_at_10']) +
                      0.2 * metrics['macro_f1'])
        return max(0, scalarized - state.best_scalarized())
```

### Why ABES Is Not a Waterfall

Consider how ABES behaves in practice:

**Scenario 1: LightGBM bug discovered early (t=3)**
```
t=1: A_model (baseline LogReg)        → pr_auc=0.68
t=2: A_model (XGBoost canonical)      → pr_auc=0.81
t=3: A_model (LightGBM canonical)     → pr_auc=0.04 [ANOMALY FLAGGED]
t=4: A_diagnose (investigate LightGBM) → pr_auc=0.83 [BUG FIXED, reward=HIGH]
     → A_diagnose posterior updated: "diagnosis is very valuable"
t=5: A_model (CatBoost) selected by Thompson Sampling
     → NOT forced by a phase gate
```

The agent switches to diagnosis at t=4 because the anomaly boosted A_diagnose's urgency, not because a waterfall schedule told it to. After fixing the bug, it returns to model exploration because A_model's urgency is still high (untried families remain).

**Scenario 2: XGBoost clearly dominant after 10 experiments (T=100)**
```
t=1-8: Mixed A_model (6 families) + A_feature (2 ablations)
       → XGBoost + LightGBM competitive; CatBoost, RF lag
t=9-10: A_model (refine LightGBM config)
       → LightGBM settles at 0.82 vs. XGBoost 0.84

Now at t=11:
  urgency(A_model) = 0.1   (all families tried ≥ 2 times)
  urgency(A_hp)    = 0.9   (only 2 HP experiments so far)
  urgency(A_feature) = 0.6 (2 of 4 groups tested)
  opportunity(A_hp) = 0.5  (prior: moderate)

  → Agent naturally shifts to A_hp and A_feature
  → NOT because Phase 2 started, but because the data says model exploration is saturated
```

**Scenario 3: Late discovery of a new promising approach (t=80 out of T=100)**
```
t=75-79: A_hp (tuning XGBoost, diminishing returns)
t=80: A_model (RF with tuned features)  → pr_auc=0.85 [NEW BEST!]
     → A_model posterior spikes: "model exploration is still valuable!"
     → urgency(A_hp on RF) = HIGH (new best model, 0 HP tuning done)
t=81-85: A_hp (tuning RF)  → improves to 0.86

In a waterfall, this couldn't happen — Phase 1 (models) would have ended at t=30.
In ABES, the agent dynamically shifts attention wherever rewards are highest.
```

### ABES vs. Original HBES: Key Differences

| Aspect | HBES (Original) | ABES (Revised) |
|--------|-----------------|----------------|
| **Phase transitions** | Fixed: exp 1-7, 8-11, 12-17, 18-20 | Adaptive: driven by urgency/opportunity scores |
| **Budget allocation** | Fixed percentages (35%/20%/25%/20%) | Dynamic: proportional to observed reward rates |
| **Budget assumption** | Hardcoded for T=20 | Budget-agnostic via λ_explore(t, T) |
| **Action selection** | Deterministic: always follow phase | Stochastic: Thompson Sampling + urgency |
| **Can revisit earlier concerns** | No: Phase 1 is over after exp 7 | Yes: high reward on A_model at any t triggers re-exploration |
| **Metrics** | Single-objective (PR-AUC) | Multi-objective (PR-AUC + lift@10% + macro_F1) |
| **Learning across action types** | None | Posterior updated per action type → learns which is most productive |

---

## VIII. Budget-Adaptive Scaling: 20 → 100 → 1000

The algorithm's behavior should fundamentally change at different budget scales. Not just "do more of the same," but qualitatively different strategies become viable.

### Budget Regime Analysis

#### Regime 1: Tight Budget (T = 20-50)

**Constraints**: Every experiment counts. Can't afford to waste evaluations on dead ends. Population-based methods are infeasible.

**ABES behavior**:
- Thompson Sampling has very wide posteriors → high variance in action selection → natural exploration
- Surrogate model (for A_hp) has too few points → falls back to one-variable-at-a-time
- Typical trajectory: 8-10 model/feature explorations, 6-8 HP tuning, 2-4 validation
- EAs not viable (population too small for crossover to be meaningful)

**Recommended algorithm mix**:
| Component | Algorithm | Reason |
|-----------|-----------|--------|
| Action selection | Thompson Sampling | Most sample-efficient for tiny budgets |
| Model selection | UCB1 | Ensures every family gets min 1-2 trials |
| HP tuning | Random search + 1-at-a-time | BO needs ≥10 points to beat random |
| Features | Ablation (add/remove) | Controlled, interpretable |
| Metrics | Scalarization | Too few points for Pareto analysis |

#### Regime 2: Moderate Budget (T = 100-300)

**Constraints**: Enough to explore the structural space AND do meaningful HP optimization. BO becomes effective. Light evolutionary operators are viable.

**ABES behavior**:
- Posteriors tighten after ~30 experiments → action selection becomes more exploitative
- Surrogate model has enough points to guide HP search → BO outperforms random
- Can afford multi-fidelity: run 20% of experiments at reduced fidelity for screening
- EA crossover viable: recombine feature sets from top configs

**New capabilities unlocked at this budget**:
```
- Bayesian Optimization (TPE/SMAC) for HP tuning: ~30+ configs per model family
- Successive Halving: screen 30 configs at 25% data cost → 15 at 50% → 8 full
- Feature interaction search: test pairwise interactions systematically
- Cross-model knowledge transfer: features that help XGBoost → try on LightGBM
- Pareto front tracking: enough points to build meaningful multi-objective front
```

**Recommended algorithm mix**:
| Component | Algorithm | Reason |
|-----------|-----------|--------|
| Action selection | Thompson Sampling + decaying λ | Well-calibrated posteriors by t~50 |
| Model selection | Thompson Sampling | Sufficient pulls per arm for reliable estimates |
| HP tuning | SMAC (RF surrogate) or TPE | Enough data for surrogate to be useful |
| Features | Greedy forward selection + BO | Can systematically test interactions |
| Multi-fidelity | Successive Halving (1 bracket) | Screen 3× more configs for same compute |
| Metrics | Scalarized + Pareto tracking | Track front, optimize weighted sum |

#### Regime 3: Large Budget (T = 500-1000+)

**Constraints**: Compute time becomes the bottleneck, not information. Full evolutionary methods viable. Can run Optuna with proper cross-validation.

**ABES behavior**:
- Posteriors are tight → action selection is highly exploitative → most time on A_hp
- Surrogate model is well-calibrated → EI/KG give near-optimal HP proposals
- Can afford proper k-fold CV (5-fold on best configs) to get reliable estimates
- Full Pareto front exploration is viable

**New capabilities unlocked at this budget**:
```
- CMA-ES: Covariance Matrix Adaptation for continuous HP spaces
- NSGA-II/NSGA-III: Population-based multi-objective optimization
- Hyperband (full): Multiple brackets, automatic fidelity selection
- BOHB: Bayesian Optimization + Hyperband (state of the art)
- Optuna with 100+ trials per model family, 3-fold CV
- Proper model stacking with optimized weights (separate CV fold)
- Threshold optimization on dedicated hold-out set
- Confidence intervals on metrics via bootstrapping
```

**Recommended algorithm mix**:
| Component | Algorithm | Reason |
|-----------|-----------|--------|
| Action selection | ABES with short horizon | Update posteriors rapidly, tight convergence |
| Model selection | Full tournament + re-evaluation | Can afford 20+ configs per family |
| HP tuning | BOHB (BO + Hyperband) | State of the art for large-budget HPO |
| Features | Evolutionary feature construction | Population of feature sets evolved via crossover/mutation |
| Multi-fidelity | Hyperband (3 brackets) | Efficient resource allocation across fidelities |
| Ensemble | Stacking with Optuna-tuned weights | Enough compute for proper CV |
| Metrics | Full Pareto + Hypervolume | Build complete trade-off surface |

### Budget-Adaptive Configuration Table

```python
def get_abes_config(T):
    """Return ABES configuration adapted to total budget T."""
    config = {}

    # --- Minimum trials per model family ---
    # More budget → more trials before declaring a family "explored"
    config['min_family_trials'] = max(1, min(T // 20, 10))
    # T=20 → 1, T=100 → 5, T=1000 → 10

    # --- Anomaly re-try budget ---
    config['max_anomaly_retries'] = max(1, min(T // 50, 5))
    # T=20 → 1, T=100 → 2, T=1000 → 5

    # --- When to start BO (needs minimum observations) ---
    config['bo_warmup'] = max(10, T // 10)
    # T=20 → 10, T=100 → 10, T=1000 → 100

    # --- Cross-validation folds ---
    config['cv_folds'] = 1 if T < 100 else (3 if T < 500 else 5)

    # --- Multi-fidelity ---
    config['use_successive_halving'] = (T >= 50)
    config['sh_brackets'] = 1 if T < 200 else (2 if T < 500 else 3)

    # --- EA operators ---
    config['use_crossover'] = (T >= 100)
    config['population_size'] = max(5, T // 50) if T >= 100 else 0

    # --- Multi-objective ---
    config['pareto_tracking'] = (T >= 50)
    config['hypervolume_selection'] = (T >= 200)

    # --- Exploration decay schedule ---
    # At higher budgets, explore longer (proportionally)
    config['explore_midpoint'] = 0.4 if T < 100 else 0.3  # When λ=1.0
    # T=20: balanced at exp 8, T=1000: balanced at exp 300

    return config
```

### Iterative Refinement Cycles (Addressing the "Not Waterfall" Requirement)

Instead of phases, ABES operates in **continuous cycles**. Each cycle is a mini-loop of evaluate → learn → decide:

```
┌─────────────────────────────────────────────────┐
│                 ABES Main Loop                   │
│                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  SELECT   │───▶│ EXECUTE  │───▶│  UPDATE  │   │
│  │ action    │    │ experiment│    │ beliefs  │   │
│  │  type     │    │          │    │          │   │
│  └──────────┘    └──────────┘    └──────────┘   │
│       ▲                               │          │
│       │         ┌──────────┐          │          │
│       └─────────│ REWEIGHT │◀─────────┘          │
│                 │ action   │                     │
│                 │ priors   │                     │
│                 └──────────┘                     │
│                                                  │
│  At EVERY step, ALL action types compete.        │
│  No action type is ever "locked out."            │
│  Budget allocation is an EMERGENT property       │
│  of the reward history, not a preset schedule.   │
└─────────────────────────────────────────────────┘
```

The "phases" from the original HBES **emerge naturally** from the algorithm's dynamics:

- **Early**: A_model dominates because urgency(A_model) is high (untried families) and λ_explore is high
- **Middle**: A_feature and A_hp dominate because urgency(A_model) drops (families tried) and opportunity(A_hp) rises
- **Late**: A_hp and A_validate dominate because λ_explore is low and the algorithm focuses on refinement

But this is **emergent, not prescribed**. If A_model remains rewarding late in the run, the algorithm keeps exploring models. If A_hp hits a plateau early, the algorithm shifts to features or ensembles.

### Attention Mechanism Over Action Types

To formalize the "adaptive weights" concept:

```python
class ActionAttention:
    """
    Soft attention over action types.
    Weights are proportional to expected marginal value.
    Updated after every experiment.
    """
    def __init__(self, action_types, temperature=1.0):
        self.actions = action_types
        self.temperature = temperature
        # Initialize with uniform attention
        self.log_weights = {a: 0.0 for a in action_types}
        # Running statistics per action type
        self.reward_history = {a: [] for a in action_types}

    def get_attention(self):
        """Softmax over log-weights → attention distribution."""
        max_w = max(self.log_weights.values())
        exps = {a: np.exp((w - max_w) / self.temperature)
                for a, w in self.log_weights.items()}
        total = sum(exps.values())
        return {a: e / total for a, e in exps.items()}

    def update(self, action, reward, urgency):
        """Update attention based on observed reward and current urgency."""
        self.reward_history[action].append(reward)

        # Exponentially weighted moving average of rewards
        alpha = 0.3  # Learning rate
        if len(self.reward_history[action]) == 1:
            ewma = reward
        else:
            ewma = alpha * reward + (1 - alpha) * self.log_weights[action]

        self.log_weights[action] = ewma + 0.5 * urgency

    def select(self, urgencies, opportunities, lambda_explore):
        """
        Select action type using attention + Thompson Sampling.
        Returns selected action type.
        """
        attention = self.get_attention()

        # Sample from posterior for each action
        scores = {}
        for a in self.actions:
            # Thompson: sample from reward posterior
            if len(self.reward_history[a]) >= 2:
                mu = np.mean(self.reward_history[a])
                sigma = np.std(self.reward_history[a]) / np.sqrt(len(self.reward_history[a]))
            else:
                mu, sigma = 0.0, 1.0  # Wide prior

            thompson_sample = np.random.normal(mu, sigma)

            scores[a] = (
                attention[a] * thompson_sample +     # Historical value (attention-weighted)
                lambda_explore * urgencies[a] +       # Exploration bonus
                0.5 * opportunities[a]                # Opportunity bonus
            )

        return max(scores, key=scores.get)
```

This attention mechanism means:
- Action types that keep yielding rewards get increasing attention
- Action types that plateau get decreasing attention
- Urgency overrides attention when something critical needs investigation
- The temperature parameter controls how "focused" vs. "diffuse" the attention is

### Adaptive Budget Reallocation

Instead of fixed budget percentages, ABES uses **a rolling horizon**:

```python
def should_continue_action_type(action_type, state, horizon=5):
    """
    Look back at last `horizon` experiments of this action type.
    If improvement rate is declining, reduce future allocation.
    If improvement rate is accelerating, increase future allocation.
    """
    recent_rewards = state.get_recent_rewards(action_type, n=horizon)

    if len(recent_rewards) < 3:
        return True  # Not enough data, keep trying

    # Compute trend: are rewards increasing or decreasing?
    trend = np.polyfit(range(len(recent_rewards)), recent_rewards, 1)[0]

    if trend > 0:
        return True   # Still improving → continue investing
    elif trend < -0.01:
        return False  # Declining returns → shift to other action types
    else:
        # Flat → check absolute level
        mean_reward = np.mean(recent_rewards)
        return mean_reward > 0.001  # Still finding marginal improvements
```

This means the budget allocation is **a learned outcome**, not an input:

```
Run 1 (T=100, model-dominated dataset):
  → ABES spends 40% on A_model, 30% on A_hp, 20% on A_feature, 10% on A_validate
  → Because model selection kept yielding rewards

Run 2 (T=100, HP-sensitive dataset):
  → ABES spends 15% on A_model, 55% on A_hp, 20% on A_feature, 10% on A_validate
  → Because HP tuning was where the gains were

Run 3 (T=1000, complex dataset):
  → ABES spends 10% on A_model, 25% on A_hp, 30% on A_feature, 15% on A_ensemble, 20% on A_validate
  → Because feature engineering was the key differentiator at this budget
```

---

## IX. Meta-Learning: Learning Across Runs

### The Multi-Run Opportunity

Each auto-train run produces 20 experiments. Over K runs, we accumulate 20K observations. This enables **meta-learning**: using prior runs to warm-start future runs.

#### Transfer Learning for Algorithm Configuration

Techniques from the meta-learning literature:

| Technique | How It Works | Application |
|-----------|-------------|-------------|
| **Warm-starting BO** | Initialize surrogate with prior run's observations | Start with 20 "free" observations |
| **Meta-features** | Characterize dataset (n_rows, imbalance_ratio, n_features) → predict best config | Learn which models work for which datasets |
| **Portfolio methods** | Maintain a portfolio of K configs that collectively cover diverse datasets | Always have a strong starting point |
| **RGPE** | Rank-weighted GP ensemble over prior tasks | Sophisticated surrogate transfer |

#### Concrete Implementation: Run-Over-Run Memory

```markdown
# memory/experiment_priors.md

## Dataset: creditcard.csv
- Characteristics: 284K rows, 30 features, 0.17% positive, PCA-transformed
- Best known: XGBoost + feature eng, val_pr_auc = 0.8337

## Model Family Priors (updated after each run)
| Family | Best Score | Configs Tried | Status |
|--------|-----------|---------------|--------|
| XGBoost | 0.8337 | 15 | Well-explored |
| LightGBM | 0.0367 | 1 (BUGGY) | NEEDS FAIR TRIAL |
| CatBoost | 0.7755 | 1 (wrong config) | NEEDS FAIR TRIAL |
| RF | — | 0 (solo) | UNTRIED |
| GBM | — | 0 | UNTRIED |
| ET | — | 0 (solo) | UNTRIED |

## Known Dead Ends (don't repeat)
- SMOTE + scale_pos_weight = double-counting
- QuantileTransformer on tree models = no effect
- BaggingClassifier on XGBoost = redundant
- aucpr as early stopping metric = too noisy

## Known Good Components
- log1p(Amount) likely helps (part of +0.006 feature set)
- scale_pos_weight = n_neg/n_pos is reliable imbalance handling
- max_depth ∈ {5, 6}, lr ∈ {0.03, 0.1} seem competitive for XGBoost
```

This file would be consulted at the start of each new run, providing O(20K) worth of prior knowledge for free.

---

## X. Comparison Matrix

### Algorithm Suitability Scores (1-5) Across Budget Regimes

| Criterion | Bayesian Opt | Multi-Armed Bandit | Evolutionary | Hyperband | PBT | ABES (Proposed) |
|-----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Works with T=20 budget | 3 | 5 | 2 | 4 | 2 | 5 |
| Works with T=100 budget | 5 | 4 | 3 | 5 | 3 | 5 |
| Works with T=1000 budget | 5 | 3 | 5 | 5 | 4 | 5 |
| Handles categorical + continuous | 3 | 5 | 4 | 3 | 2 | 5 |
| Exploration/exploitation balance | 5 | 4 | 3 | 3 | 4 | 5 |
| Multi-objective support | 3 | 2 | 5 | 2 | 2 | 5 |
| Handles anomalous failures | 2 | 2 | 1 | 3 | 1 | 5 |
| Adaptive budget allocation | 2 | 3 | 2 | 4 | 4 | 5 |
| Uses prior run knowledge | 4 | 2 | 2 | 2 | 1 | 4 |
| Interpretable decisions | 2 | 4 | 2 | 3 | 2 | 5 |
| Implementable by LLM agent | 2 | 4 | 3 | 2 | 1 | 5 |
| Theoretical optimality | 5 | 4 | 3 | 4 | 4 | 4 |
| **Total** | **41** | **42** | **35** | **40** | **30** | **58** |

### Why Pure Algorithms Fall Short (And Why ABES Hybridizes)

No single algorithm perfectly fits across all budget regimes:

- **BO** needs warm-up observations; excellent at T=100+ but insufficient alone for model selection
- **MAB** doesn't model interactions between arms; loses advantage when arms are correlated (tree models)
- **EA** needs large populations; only viable at T≥100 for meaningful evolution
- **Hyperband** assumes a single fidelity dimension; excellent for HPO but doesn't handle model selection
- **PBT** needs parallel training and weight sharing; poorly suited to sequential evaluation

The proposed **ABES** is a hybrid that combines:
- **Thompson Sampling** from MAB (for meta-action selection at all budgets)
- **Expected Improvement** from BO (for HP tuning when surrogate is warm)
- **Attention mechanism** inspired by Transformer architectures (for adaptive action weighting)
- **Anomaly detection** (custom: prevents buggy evaluations from corrupting beliefs)
- **Multi-fidelity** from Hyperband (activated at T≥50)
- **Crossover operators** from EA (activated at T≥100 for feature set recombination)
- **Multi-objective** via Pareto/hypervolume (scales with budget)
- **Meta-learning** from portfolio methods (warm-starting from prior runs)

---

## XI. Recommendations

### Architecture-Level Changes

1. **Implement ABES as the core decision engine.** Replace the current "improvise each experiment" approach with the structured-but-adaptive algorithm. The key data structures:
   - `ExperimentState`: tracks all results, Pareto front, action-type posteriors
   - `ActionAttention`: soft attention over action types with Thompson Sampling
   - `AnomalyDetector`: flags scores below `max(0.5 × best, baseline)`

2. **Add multi-metric evaluation.** Extend `prepare.py` to compute lift@10% and macro_F1 alongside PR-AUC. All three metrics feed into the Pareto front. Use scalarized objective (0.5/0.3/0.2) for the "keep/discard" decision until enough experiments for real Pareto analysis.

3. **Make budget a first-class parameter.** `MAX_EXPERIMENTS` should configure not just the stopping condition but the algorithm's behavior: exploration rate, BO warm-up, multi-fidelity activation, EA population size. Use `get_abes_config(T)` from Section VIII.

### Immediate Changes (Next Run, Any Budget)

4. **Add anomaly detection rule**: Any score below `max(0.5 × current_best, baseline)` triggers a diagnostic check (print predict_proba, check for inversions) before the experiment is discarded.

5. **Enforce single-variable protocol**: Each experiment's commit message must state the one variable changed and the hypothesis. Log both in `results.tsv`.

6. **Track action types**: Add an `action_type` column to `results.tsv` so the agent can compute urgency/opportunity scores.

7. **Warm-start from mar30**: Load known dead ends and valid priors into the agent's context at the start of the next run.

### Medium-Term (Framework Improvements)

8. **Multi-fidelity evaluation**: Add a `fidelity` parameter to `prepare.py` (training data fraction). Enables Successive Halving — 8 experiments at 25% data in the time of 2 full experiments.

9. **Structured experiment representation**: Define a formal schema for experiment configs so the BO surrogate can learn from them:
   ```python
   ExperimentConfig = {
       "model_family": str,
       "feature_mask": List[bool],   # Which engineered features to include
       "imbalance_strategy": str,
       "hp_overrides": Dict[str, Any],  # Only HPs changed from defaults
   }
   ```

10. **Implement ActionAttention in `program.md`**: Translate the attention mechanism into explicit instructions the LLM agent can follow. Key: after each experiment, the agent must compute urgency scores for all action types and select the highest-scoring one.

### Long-Term Vision (Across Runs, Large Budget)

11. **Meta-learning database**: Accumulate experiment histories across runs. Warm-start the BO surrogate and action-type posteriors from prior runs.

12. **Automated BOHB at T=1000**: At large budgets, embedded Optuna handles level-2 HP search. The LLM agent focuses on level-1 structural decisions (model family, feature design, ensemble strategy).

13. **Evolutionary feature construction**: At T≥500, use genetic programming to evolve feature engineering functions. The "chromosome" is a feature-construction program; crossover recombines feature programs from high-performing configs.

14. **Properly validated Pareto front**: At T≥200, reserve 10% of budget for re-evaluating Pareto-front members with 5-fold CV to get confidence intervals on metric estimates.

### Summary of Expected Impact by Budget

| Change | T=20 Impact | T=100 Impact | T=1000 Impact |
|--------|------------|-------------|--------------|
| ABES adaptive action selection | +0.01-0.02 | +0.02-0.04 | +0.03-0.05 |
| Multi-metric (add lift, macro_F1) | Better decisions | Pareto front reveals tradeoffs | Full metric surface mapped |
| Anomaly detection | +0.01-0.02 (recover 1-2 bugged models) | +0.02 (recover all bugged configs) | +0.02 |
| Multi-fidelity | N/A | +0.01-0.02 (3× more screening) | +0.02-0.03 (Hyperband) |
| EA feature construction | N/A | +0.005-0.01 | +0.01-0.02 |
| Meta-learning (run-over-run) | +0.005 per run | +0.01 per run | +0.02 per run |

**Conservative aggregate estimate**:
- T=20:  val_pr_auc from 0.8337 → 0.850-0.860
- T=100: val_pr_auc from 0.8337 → 0.865-0.880
- T=1000: val_pr_auc from 0.8337 → 0.880-0.900+

---

*Rev 2 — Revised per feedback: (1) added multi-objective metrics (lift@10%, macro_F1), (2) budget-agnostic design (20→1000), (3) adaptive budget allocation replacing fixed phases, (4) ABES replaces HBES waterfall with continuous adaptive loop. Review alongside the [Mar30 Post-Mortem](2026-03-31-autotrain-mar30-postmortem.md).*
