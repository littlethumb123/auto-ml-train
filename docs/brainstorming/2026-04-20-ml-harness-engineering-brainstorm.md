# Brainstorm: Strengthening the Agentic ML Harness

Date: 2026-04-20

## Purpose

Capture a repo-specific brainstorm on how to improve this project's automated ML harness by combining:

- ML-agent workflow lessons from `docs/literature_review/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md`
- General harness-engineering guidance from `docs/literature_review/harness-engineering-literature-review.md`
- The broader harness survey in `docs/literature_review/harness engineering survey 2026_xhs.pdf`
- The current ABES implementation in `abes_engine.py`, `results.tsv`, `abes_state.json`, `program.md`, and `train.py`

The goal is not just to understand existing harnesses, but to derive a stronger design direction for an automated machine learning harness that is scientifically disciplined, cost-aware, and robust over long experiment loops.

## Core Thesis

The next major improvement should not come from making the agent "more autonomous" in the abstract.

It should come from making the harness more rigorous.

More concretely: the current system is already a real first-generation ML harness, but the next-generation version should optimize evidence quality under budget, not just pick the next experiment category.

That means shifting emphasis:

- from action selection to evidence management
- from prose memory to structured experiment memory
- from score chasing to uncertainty-aware decision making
- from trial logging to traceable lifecycle governance
- from repeated local search to novelty-aware, information-gain-aware search

## Why This Thesis Is Supported by the Literature

Across the ML-specific and general harness literature, the strongest recurring findings are consistent.

### 1. The harness, not the model, becomes the binding constraint

The general harness literature repeatedly argues that after a model reaches a capability threshold, the operational environment determines practical performance. The harness survey sharpens this into a six-part governance model:

- Execution environment
- Tool integration
- Context management
- State store
- Lifecycle hooks
- Evaluation interface

This framing is directly useful for ML workflows because it forces us to treat experiment orchestration, memory, stopping rules, and metric interpretation as first-class engineering objects rather than secondary implementation details.

### 2. Good ML agents rely on artifact-centric memory

The ML workflow literature is especially clear that memory should not just be conversation history.

- DS-Agent uses case-based reasoning over prior successful solutions.
- AutoKaggle uses reusable toolkits and validated workflow components.
- Agent Laboratory and The AI Scientist externalize code, reports, and review artifacts.
- CAAFE shows that structured semantic prior can outperform generic long conversational context.

The implication for this repo is direct: `results.tsv` and `abes_state.json` are the right general direction, but they are still too weak and too text-heavy to support high-quality ML case reuse.

### 3. Strong agentic ML systems are stage-structured

The literature strongly favors staged workflows:

- research or framing
- plan selection
- execution
- verification
- report or artifact consolidation

The reason is not just organizational clarity. Stage separation is a form of context control. It narrows the active decision surface and reduces accidental drift.

### 4. The best systems are bound to external metrics

The ML review confirms that successful systems use external signals:

- leaderboard scores
- benchmark success rates
- held-out metrics
- reviewer scores

This repo already does this correctly by grounding decisions in `val_pr_auc` and related metrics. That is a major strength to preserve.

### 5. Long-running harnesses need explicit lifecycle governance

The general harness literature repeatedly emphasizes:

- hard constraints
- self-verification before exit
- recurring cleanup
- failure-driven harness updates
- progressive disclosure of context

This is highly relevant to automated ML because late-stage experiment loops tend to degrade into micro-variations, overfitting, or repeated dead ends unless the harness actively prevents it.

## Current Harness: What Is Already Strong

This repo already implements several important harness principles.

### Explicit external state

The system stores experiment history and control state in:

- `results.tsv`
- `abes_state.json`

This is already better than a pure prompt-driven loop because the memory survives context loss.

### Metric-bound execution loop

The workflow uses real evaluation outputs rather than a language-model judge. That is aligned with the strongest evidence in both reviews.

### Lifecycle hooks and constraint logic

`abes_engine.py` already implements:

- recommendation
- logging
- anomaly checks
- plateau detection
- Pareto tracking
- dead-end reminders

That makes the system meaningfully more structured than a naive edit-run-repeat loop.

### Domain priors and negative knowledge

The engine carries known dead ends and warm-start structural learnings. This is a real harness advantage and should be expanded, not removed.

## Current Harness: Main Gaps and Design Weaknesses

The main gaps are no longer basic orchestration gaps. They are scientific and systems-design gaps.

### 1. Source-of-truth drift

The repo currently has conflicting control signals.

- `AGENTS.md` says max experiments is 20.
- `CLAUDE.md` says max experiments is 100.
- `abes_engine.py` initializes with a default budget of 100.
- `abes_state.json` currently shows 23 experiments and 12 consecutive discards.
- `train.py` currently contains a LightGBM Optuna configuration that does not match the last row in `results.tsv`.

This is a harness reliability issue, not merely a documentation issue. A long-running agent cannot be trusted if policy, memory, and active code can silently diverge.

### 2. Experiment memory is too shallow

`results.tsv` stores a useful summary, but not enough structured evidence for high-quality reuse.

Missing or weakly represented information includes:

- exact model configuration as machine-readable data
- feature flags as structured fields rather than prose inference
- budget consumption and runtime profile per experiment
- calibration or threshold choices
- train or validation artifact summaries
- confidence or uncertainty around observed improvement
- local basin identity or experiment neighborhood

This means the harness cannot do true ML case-based reasoning yet.

### 3. The control policy is too low-resolution

The current engine recommends action types well enough, but its opportunity model is crude. Since most discard outcomes collapse to zero reward, many later decisions become under-informed. The result is visible in the long discard streaks and repeated restart behavior.

### 4. Diagnosis debt accumulates without a strong closure mechanism

Anomalies are recorded, but the system has no strong resolved or unresolved workflow. That means diagnosis becomes a queue rather than a control surface.

### 5. Evaluation is grounded but still too brittle

The system is optimized on one validation regime with no explicit uncertainty layer. In a long experiment loop, tiny differences in `val_pr_auc` can drive decisions that are not actually stable enough to justify keeping complexity.

### 6. Feature and strategy provenance depends too much on text descriptions

`A_feature` tracking currently depends on parsing free-text hypothesis and description fields. That is fragile. The harness should not need prose interpretation to know what was tested.

## The Design Shift I Would Make

I would shift the harness from experiment selection to evidence management.

The practical meaning is:

- choose experiments based on expected information gain, not just urgency class
- store enough structured evidence to make future reuse reliable
- block near-duplicate low-information runs
- treat uncertainty and complexity explicitly in keep or discard decisions
- unify recommendation, execution, anomaly detection, and reporting into one traceable record

## Proposed Framework for This Repo

The six-component survey model is a useful way to redesign this harness.

### E: Execution environment

Current state:

- Good: a defined loop exists
- Weakness: active code state and logged state can drift

Stronger version:

- one canonical harness config file for budget, stop rules, metrics, allowed files, action types, and hard constraints
- explicit run manifest produced before each experiment
- explicit run status transitions such as proposed, running, completed, anomalous, rejected, superseded

### T: Tool integration

Current state:

- Good: training and evaluation are script-based and deterministic enough for loop execution
- Weakness: tool outputs are not turned into strongly typed artifacts

Stronger version:

- structured experiment artifact bundle for each run
- machine-readable configuration and outcome files instead of relying on console text alone
- reusable proxy-screening tool built into the harness rather than recommended informally

### C: Context management

Current state:

- Good: the engine keeps negative priors and some structural learning
- Weakness: context is still partly duplicated across prose docs, state, and code

Stronger version:

- progressive disclosure of only the current best basin, unresolved anomalies, nearest failed neighbors, and currently available safe actions
- automatic suppression of stale or contradictory instructions
- explicit context tiers: constitutional rules, active run context, deep archive

### S: State store

Current state:

- Good: `results.tsv` and `abes_state.json` exist
- Weakness: the state schema is too shallow for case reuse

Stronger version:

- `ExperimentSpec` record
- `ExperimentResult` record
- `BasinCard` record
- `AnomalyCase` record
- `HarnessRunTrace` record

These should be machine-readable and versioned.

### L: Lifecycle hooks

Current state:

- Good: recommend, log, check, status
- Weakness: not enough pre-run gating and not enough post-run closure

Stronger version:

- novelty gate before execution
- uncertainty gate before keep
- contradiction gate when active code and logged state diverge
- explicit anomaly resolution workflow
- simplification gate that rewards equal performance with lower complexity

### V: Evaluation interface

Current state:

- Good: external metrics, Pareto logic, anomaly checks
- Weakness: no uncertainty-aware keep or discard logic

Stronger version:

- bootstrap confidence intervals on validation predictions
- practical-equivalence threshold for tiny score changes
- explicit complexity penalty
- cost-per-improvement tracking
- unified evaluation plus governance trace

## Concrete Improvements I Would Prioritize

### 1. Create a single harness contract

Move all control policy into one canonical machine-readable config artifact.

That contract should define:

- max experiments
- stop criteria
- primary and secondary metrics
- allowed edit scope
- dead ends
- action types
- restart conditions
- anomaly thresholds
- keep or discard policy

Then make `program.md`, `AGENTS.md`, `CLAUDE.md`, and `abes_engine.py` derive from it or at least point to it.

### 2. Replace free-text experiment memory with structured experiment objects

Suggested minimal schema set:

- `ExperimentSpec`: exact hyperparameters, feature switches, imbalance strategy, seed, expected cost, action type, hypothesis class
- `ExperimentResult`: metrics, runtime, artifacts, outcome class, diagnostics
- `BasinCard`: local optimum summary, stable ranges, nearby failed perturbations, simplification opportunities
- `AnomalyCase`: anomaly type, trigger condition, diagnosis steps, resolution status
- `HarnessRunTrace`: what the engine recommended, what was actually executed, what fired, and why the outcome was classified the way it was

This would move the harness much closer to DS-Agent-style reusable cases.

### 3. Add novelty and orthogonality gating

Before any run, score the proposed experiment against recent failures and recent keeps.

Block or downgrade runs that are too close to recent negative examples unless the agent can justify why the run is meaningfully different.

This directly addresses local looping and low-information retries.

### 4. Make keep or discard uncertainty-aware

Current issue:

- tiny score changes can drive decisions as if they are equally meaningful

Stronger approach:

- add confidence intervals or bootstrap-based uncertainty estimates
- use a practical-equivalence band for tiny deltas
- include a complexity cost

This aligns the harness with the repo's stated simplicity criterion.

### 5. Turn multi-fidelity search into a first-class harness subsystem

Do not leave restart strategy as a mostly advisory pattern.

Instead, define:

- proxy evaluation budget
- promotion criteria
- number of candidates to screen
- number of candidates to promote
- acceptable proxy-to-full-fidelity mismatch tolerance

This would operationalize the budget-aware discipline emphasized by FLAML-style AutoML work and missing in many agentic systems.

### 6. Build an ML-specific anomaly taxonomy

Suggested anomaly classes:

- probability inversion
- class-collapse predictions
- calibration collapse
- split-overfit suspicion
- feature leakage suspicion
- timeout-risk configuration
- low-signal overparameterization
- proxy or full-fidelity disagreement

Each anomaly class should map to a distinct diagnostic playbook and a resolved status.

### 7. Use light specialization instead of many-agent overhead

The literature supports specialization, but also warns that multi-agent overhead is only justified when the agents are genuinely heterogeneous.

For this repo, a reasonable structure would be:

- Planner: proposes the next experiment under policy constraints
- Executor: edits `train.py` and runs the experiment
- Reviewer: audits the result, anomaly class, and keep or discard reasoning

This is likely enough. A large multi-agent swarm is not yet justified.

### 8. Benchmark the harness itself, not just the fraud model

If the aim is to invent a better automated ML harness, then this repo should become one benchmark target in a larger harness-evaluation stack.

Suggested layers:

- this fraud dataset for fast imbalanced tabular iteration
- a small set of additional tabular datasets with different failure modes
- a competition-style held-out score task
- at least one broader agent benchmark for long-horizon workflow comparison

Metrics should include:

- best score
- score after fixed budget
- cost per meaningful improvement
- crash rate
- anomaly rate
- reproducibility
- rate of near-duplicate wasted runs

### 9. Unify evaluation and governance traces

Every run should answer, in one artifact:

- what the engine recommended
- what actually changed
- what artifacts were produced
- what lifecycle hooks fired
- what anomalies were detected
- why the result was kept, discarded, or marked inconclusive

This is one of the highest-leverage harness upgrades because it improves both debugging and research value.

### 10. Introduce an ML-HARNESSCARD

For the system overall and eventually for major harness variants, record a compact disclosure artifact organized by:

- Execution
- Tools
- Context
- State
- Lifecycle
- Evaluation

This makes harness behavior explicit and auditable.

## Suggested Development Roadmap

### Phase 1: Hardening the current harness

Target: eliminate drift and make state trustworthy.

- create one canonical harness policy file
- reconcile budget and stop-rule conflicts
- ensure `train.py`, state, and logged result cannot silently diverge
- replace prose-derived feature tracking with explicit structured flags
- add resolved status for anomalies

### Phase 2: Smarter experiment control

Target: improve search efficiency under the same budget.

- novelty gate
- uncertainty-aware keep or discard logic
- first-class multi-fidelity screening
- cost-per-improvement tracking
- simplification-aware reward model

### Phase 3: Stronger ML memory and reuse

Target: enable true case-based experiment reuse.

- structured experiment objects
- BasinCard generation
- retrieval of nearest successful and failed neighbors
- template-based hypothesis generation from prior basin structure

### Phase 4: Harness research mode

Target: make the harness itself the object of evaluation.

- compare harness variants across multiple datasets
- record harness configurations explicitly
- measure not only best score but also search efficiency and reliability

## Research Questions Worth Pursuing

These seem especially promising if the broader goal is to invent better ML harness engineering rather than only optimize this single dataset.

### 1. What is the right unit of memory for automated ML?

Is the best reusable artifact an experiment row, a basin summary, a feature-family lesson, or a failure pattern?

### 2. What search policy best balances score improvement against information gain?

Many ML harnesses still optimize only expected score. A stronger harness may optimize expected learning under budget.

### 3. How should a harness decide that a result is real enough to keep?

This is an uncertainty and evaluation-design question, not just a model question.

### 4. What is the smallest amount of specialization that meaningfully improves ML workflow quality?

The answer is likely less than a full multi-agent society and more than a single unrestricted executor.

### 5. Which harness choices transfer across datasets and which are dataset-specific?

This is the core question if the goal is to invent reusable harness engineering rather than just improve this one experiment loop.

## Short Conclusion

This repo already has the skeleton of a real ML harness.

The next step is not more prompt cleverness and not necessarily more agent count.

The next step is to make the harness more scientific:

- one source of truth
- structured artifact memory
- novelty-aware search
- uncertainty-aware evaluation
- explicit lifecycle governance
- benchmarked harness variants rather than only benchmarked models

If that shift is made, this project can evolve from an autonomous experiment loop into a genuine harness-engineering research asset for automated machine learning.