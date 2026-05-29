# Design Principles Reflection: From Over-Engineered Optimizer to Intelligent Agent

**Date**: 2026-04-21
**Context**: Critical review of three prior campaigns (mar30, apr01, apr03) and the comprehensive optimization research document, with independent analysis of what actually drove results vs. what was complexity theater.

---

## 1. The Central Finding

140 experiments across three campaigns converged to the same XGBoost basin at val_pr_auc ~0.846. The comprehensive research document attributed this to seven interlocking bottlenecks and proposed a 40+ hour, 5-phase engineering roadmap including Thompson Sampling, Hyperband, genetic algorithms, RGPE meta-learning, and hypervolume-based Pareto optimization.

**The independent assessment disagrees with this diagnosis.** The ceiling is not primarily a search failure. It is a combination of:

1. **Dataset/split ceiling**: ~97 fraud cases in the validation set means PR-AUC has a noise floor of approximately ±0.005-0.010. The 0.838→0.846 gains are near or within this noise band.
2. **Model class ceiling**: On PCA-decorrelated continuous features, XGBoost is already near-optimal. Neural networks don't have a structural advantage here.
3. **Evaluation reliability**: Single-split PR-AUC on small positive counts is an unreliable signal for small deltas.

The ABES engine (600 lines, urgency scores, composite formulas, lambda decay, Thompson Sampling design) produced zero measurable improvement over what a simple "try things, use Optuna for HPs" approach would have achieved. The two improvements in apr03 came from (1) a warm-started baseline and (2) an Optuna broad search — neither required ABES.

---

## 2. What Actually Drove Results (Evidence-Based)

| What produced gains | Mechanism | Complexity required |
|---|---|---|
| Trying XGBoost with reasonable defaults | Model selection | Zero |
| Optuna finding depth=6/lr=0.077 basin | Bayesian HP optimization (TPE) | One `optuna.create_study()` call |
| Warm-start priors (don't retry DART, keep log_amount) | A text list of learnings | A few lines in a markdown file |
| Feature engineering (log_amount, Amount*V1) | Domain-informed trial | LLM reasoning + one experiment each |

| What produced zero gains | Why it failed |
|---|---|
| Urgency scores and composite formulas | Not enough data (8 arms, sparse binary rewards) for meaningful posteriors |
| Action type taxonomy (8 categories) | Structural decisions don't decompose into independent bandit arms |
| Lambda explore sigmoid decay | Never computed in practice; when computed, didn't change agent behavior |
| Pareto front tracking | Metrics are highly correlated; tracking was informational but never influenced decisions |
| Thompson Sampling design | Never implemented; would have been data-starved even if implemented |

---

## 3. The Wrong Abstraction: Why ABES Over-Solved

The ABES framework formulated the problem as: *"Given 8 action types with unknown reward distributions, which arm should I pull next?"*

This is the wrong abstraction for four reasons:

1. **The arms are not independent.** The value of "try LightGBM" depends entirely on whether XGBoost has been tried and how well it did. Bandit algorithms assume independent reward distributions per arm.

2. **The rewards are non-stationary.** "Try a new model family" has high value at experiment 1 and zero value at experiment 50. UCB1 and Thompson Sampling assume stationarity.

3. **The rewards are too sparse.** With ~85% discard rate and 8 action types, most posteriors have <5 observations after 40 experiments. No bandit algorithm can learn meaningful structure from this.

4. **The categories are a straitjacket.** Real ML research involves novel ideas that don't fit into 8 predefined boxes. "Add focal loss" is not A_hp or A_model — it's a structural pipeline change. Forcing ideas into categories loses information.

The ABES engine was a sophisticated solution to a problem that didn't exist. The actual bottleneck was never "which action type to choose" — it was the quality and diversity of ideas within each experiment, and the reliability of the evaluation signal.

---

## 4. The Right Principle: Compute When Necessary, Reason When Appropriate

### The LLM should never guess when it can compute.

Picking `learning_rate=0.05` because it "sounds reasonable" is next-token sampling cosplaying as optimization. The LLM has no basis for choosing between 0.05 and 0.077 — that's a numerical decision that should be delegated to Optuna.

### But computation should not replace reasoning when reasoning is the right tool.

Deciding whether to try a neural network after exhausting tree models is a structural reasoning task. No optimization algorithm can make this decision well because:
- The search space of "all possible ML approaches" is not enumerable
- The value of trying something new depends on world knowledge (what works on tabular data, what papers say, what Kaggle winners used)
- The decision requires understanding why current approaches are failing, not just that they are

### Decision type → right tool:

| Decision | Right tool | Wrong tool |
|---|---|---|
| What model architecture to try next | LLM reasoning + research | Bandit algorithm |
| What hyperparameter values to use | Optuna / TPE / random search | LLM guessing |
| Whether a 0.003 gain is real | Bootstrap CI / cross-validation | LLM hope |
| Which features matter | Permutation importance / SHAP | LLM intuition |
| How to blend ensemble weights | LogisticRegressionCV on OOF predictions | LLM picking weights |
| What's structurally different to try | LLM reading results + reasoning | Any fixed algorithm |
| Why this model crashed | LLM reading stack trace | Nothing else can do this |

---

## 5. Progressive Complexity Architecture

Complexity should escalate only when triggered by evidence that the simpler approach is insufficient. The system has five levels, each activated by a specific trigger condition.

### Level 0: Baseline (always active)

```
Agent reads results history → reasons about what to try → writes train.py → runs
```

No optimization algorithms. Just an LLM with memory (results.tsv + dead_ends list). This handles: model selection, basic feature engineering, reasonable defaults, error diagnosis, structural changes.

**Escalation trigger:** Agent has chosen a model and needs to tune HPs within it.

### Level 1: Optuna for numerical decisions

The agent doesn't pick HP values — it defines a search space and delegates to Optuna inside train.py. The LLM decides **what** to search; Optuna decides **what values**.

**Escalation trigger:** Optuna keeps finding the same basin; agent suspects it's stuck.

### Level 2: Multi-fidelity screening

Screen 20 configs cheaply (200 trees, 25% data), promote top-3 to full fidelity. This is a callable function (~30 lines), not a framework. The agent invokes it when recognizing a plateau.

**Escalation trigger:** Multiple model families tried; agent wants to combine them.

### Level 3: Data-driven stacking

Use cross-validated meta-learner (LogisticRegressionCV) to find optimal ensemble weights from out-of-fold predictions. No hand-picking blend weights.

**Escalation trigger:** Gains are small (<0.005) and agent can't tell if they're real.

### Level 4: Statistical validation

Bootstrap CI on PR-AUC differences. Cross-validated evaluation. This prevents chasing noise — only activated when improvement deltas are small.

**Escalation trigger:** Feature space is large or agent suspects many features are useless.

### Level 5: Data-driven feature selection

Permutation importance, mutual information, SHAP values. Algorithmic feature selection instead of the LLM guessing which interactions might help.

### Key property: each level is a tool, not a framework

These are functions the agent calls when it recognizes the need — like a researcher reaching for a statistical test when eyeballing isn't enough. They are not a permanent control loop that runs every experiment.

---

## 6. What to Keep from ABES

Not everything in ABES was wasted. Two features proved their value:

### Keep: Dead-end memory

A simple text list of what not to retry. This was the most effective ABES feature across all three runs. It prevented re-exploring SMOTE+scale_pos_weight, DART booster, QuantileTransformer, and other known failures. Implementation: a list in a JSON or markdown file. No algorithm needed.

### Keep: Anomaly detection (simplified)

The threshold check (score < 0.75 or score < 0.5 × best) correctly caught the LightGBM probability inversion bug. Worth keeping as a simple post-experiment check. Implementation: 5 lines of code, not a subsystem.

### Keep: Results logging

The structured results.tsv with commit, metrics, status, model family, and description is essential for agent memory and human review. Keep the format.

### Remove: Everything else

Urgency scores, opportunity scores, composite ranking, lambda decay, action type enforcement, Pareto tracking for decision-making, Thompson Sampling stubs. None of these demonstrably improved outcomes.

---

## 7. Evaluation Reliability: The Biggest Gap

The most important missing piece across all three campaigns is **evaluation reliability**.

The validation set has ~56,000 samples with ~97 fraud cases. The variance of PR-AUC at this positive count is non-trivial. A back-of-envelope calculation:

- PR-AUC ≈ 0.846 with ~97 positives
- Bootstrap standard error ≈ 0.005-0.010
- 95% CI ≈ [0.826, 0.866]

This means:
- The difference between 0.838 and 0.846 (the entire apr01→apr03 "improvement") is **not statistically significant**
- Many keep/discard decisions were based on noise
- The agent may have been chasing random fluctuations for dozens of experiments

**Recommended fix:** 5-fold stratified cross-validation for PR-AUC. Costs 5× compute per experiment (~5 minutes instead of 1 minute), but gives a reliable estimate with standard error. The 60-second time budget in program.md should be reinterpreted as "60 seconds per fold" or the budget should be relaxed for evaluation quality.

Alternative: Bootstrap CI on the single validation split (cheaper, still informative).

---

## 8. What the System Should Become

### Vision

An autonomous ML research agent that:
- Explores solution spaces intelligently using its reasoning ability and world knowledge
- Delegates numerical/statistical decisions to appropriate algorithms (Optuna, bootstrap, permutation importance) when it recognizes the need
- Maintains memory of what worked and what failed across experiments
- Evaluates its own results with statistical rigor
- Starts simple and escalates complexity only when demonstrably necessary

### Not-vision

- Not a bandit algorithm that happens to use an LLM for code generation
- Not an AutoML framework (those already exist: AutoGluon, H2O, FLAML)
- Not a system that requires 600 lines of optimization engine to decide "try LightGBM next"

### Differentiator from AutoML

AutoML tools (AutoGluon, FLAML, Auto-sklearn) are excellent at the mechanical parts: searching model/HP spaces, running evaluations, tracking results. But they cannot:

- Read a research paper and apply a novel technique
- Reason about why an approach failed and what structurally different thing to try
- Adapt the evaluation methodology itself (e.g., recognizing that single-split PR-AUC is unreliable and switching to CV)
- Generate truly novel feature engineering ideas informed by domain knowledge
- Diagnose subtle bugs (probability inversions, data leakage, metric misuse)
- Decide when to stop optimizing and declare the problem solved

These are the agent's unique contributions. The optimization algorithms are its tools, not its identity.

---

## 9. Concrete Next Steps

1. **Simplify the control loop.** Replace ABES with: read results → reason about what's different to try → implement → evaluate → log. Keep dead-end memory and anomaly checks.

2. **Add cross-validated evaluation.** This is the single highest-value change. It answers "is this improvement real?" which is the question the system currently cannot answer.

3. **Build optimization tools as callable functions.** Optuna search, multi-fidelity screening, bootstrap CI, permutation importance — each as a standalone function the agent can invoke, not a framework it must obey.

4. **Test on a second dataset.** The system should generalize. Running on only the credit card dataset creates overfitting to one problem's quirks.

5. **Let the agent research.** Before starting experiments, the agent should look up what approaches work on similar problems (tabular classification with class imbalance). This leverages the LLM's unique strength: access to training knowledge about ML methodology.

---

## 10. Summary

The auto_train system's strength should be the LLM agent's ability to reason, research, diagnose, and adapt — not a complex optimization engine that the agent can't reliably execute anyway. Optimization algorithms are valuable tools that the agent invokes when the decision is numerical or statistical. They should not be the control loop.

**Complexity is earned, not assumed.** Every component must justify its existence through demonstrated impact on outcomes. The 140-experiment evidence shows that warm-start memory, Optuna for HP tuning, and anomaly detection earned their place. Urgency scores, Thompson Sampling, and action type bandits did not.

The principle: **reason at the strategic level, compute at the tactical level.** The agent decides what experiment to run. Algorithms decide the numerical details within that experiment. Each tool enters when the simpler approach demonstrably fails.
