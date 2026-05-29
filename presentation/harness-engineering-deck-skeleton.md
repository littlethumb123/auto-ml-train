# Harness Engineering Deck Skeleton

Status: content draft and source narrative for the visual HTML deck.

Audience: mixed business and technical.

Build target: visual-explainer HTML, not Marp/CVS theme.

## Narrative Shift From The Prior Outline

This revision changes the story order to match the business case first and the mechanism second:

1. Start with the problem statement and the proposed solution on slide 1.
2. Move the results to slide 2 as the prior IP commercial benchmark trajectory that the current autonomous rerun must match.
3. Use slide 3 to explain the design principles behind the harness.
4. Use slide 4 as the single overarching diagram for the harness mechanism, from dataset and target metric through approval, orchestration, role execution, and state updates.
5. Follow with verification and guardrails, memory reuse, and the exploration-exploitation algorithm.

---

## Slide 1 — Problem Statement And Proposed Solution

### Slide goal

Explain why autonomous experimentation is needed before talking about architecture.

### On-slide structure

Headline:

**Why an Auto-ML Harness Is Needed**

Subhead:

**The bottleneck is not only model quality. It is searching efficiently across a huge experiment space and turning each round into knowledge that can be audited and reused.**

Left column: Problems

Problem 1 — Manual experimentation over an unlimited problem space

- Feature sets, model families, preprocessing, encoding, imbalance handling, and hyperparameters interact combinatorially
- Search becomes slow, serial, and expensive to run rigorously by hand
- Teams can stop at locally good but sub-optimal solutions because the full space is too large to search informally

Problem 2 — Experiment knowledge is hard to audit, track, and reuse

- Results, rationale, and failures often end up scattered across notebooks, scripts, and chat
- It becomes hard to reconstruct why a decision was made or what actually changed
- Lessons do not reliably transfer to the next project or another data scientist

Right column: Harness response

- **Search efficiently:** bound the open-ended space into one governed experiment at a time
- **Separate responsibilities:** split proposal, execution, review, and synthesis across Planner, Executor, Reviewer, and Historian
- **Enforce the rules:** use a deterministic driver for approval gates, scope control, verification, rollback, and trigger handling
- **Preserve the knowledge:** store results, dead ends, assumptions, patterns, and strategy memos as reusable campaign memory

Bottom takeaway:

**The harness is the response to both problems: it makes the search more efficient and makes the knowledge auditable, trackable, and reusable.**

### Speaker transcript draft

The first problem is search inefficiency. In practice, experiment design is still manual, but the space being searched is combinatorial: feature subsets, model families, preprocessing choices, encoding strategies, imbalance treatments, and hyperparameters all interact. That makes the process slow and makes it easy to stop at a merely local improvement. The second problem is knowledge decay. Even when teams do learn something useful, the reasoning and evidence behind those results are often hard to audit, compare, and reuse. Another data scientist may inherit the code but not the logic of the trajectory. The harness is meant to solve both problems at once. It turns open-ended iteration into a governed experiment loop, separates responsibilities across roles, and stores the resulting knowledge as reusable state instead of disposable context.

---

## Slide 2 — Prior Campaign Benchmark

### Slide goal

Show the reference trajectory the current autonomous rerun has to match, using only the finished prior campaign record.

### On-slide structure

Headline:

**Prior IP Commercial Benchmark**

Subhead:

**This is the benchmark trajectory the current round 2 campaign must reproduce before we claim parity.**

Primary table:

| Stage | Rounds | Key finding | Informed by prior trajectory | val lift@1% |
| --- | --- | --- | --- | --- |
| **Baselines** | 1-3 | Hybrid beats tabular; embeddings alone are weak, so both signal sources matter. | No prior trajectory yet. Rounds 1-3 established the reference deltas for tabular-only, hybrid, and embedding-only runs so later gains were interpretable. | 22.21 |
| **Model families** | 4-10 | Three gradient boosting families widened the frontier; comparing families beat staying inside CatBoost tuning. | Rounds 1-3 and the SHAP / diagnose passes showed the hybrid feature space was worth keeping, while CatBoost-only proxy tuning was too slow and noisy, so the search shifted to LGBM, XGB, and honest family-level comparisons. | 22.33 |
| **Ensemble expansion** | 10-22 | Structural diversity beat more local hyperparameter work; the best gains came from combining models trained on different feature views. | Round 14's leakage-free three-family mean ensemble beat any single family, and rounds 16-18 showed weaker but different models could still add signal, so the next moves emphasized diverse base-model predictions instead of more single-model tuning. | 22.73 |
| **Breakthrough** | 25 | Tuning XGBoost for AUC-ROC, not lift@1%, made it far more complementary in the ensemble tail: **+0.446 in one round**. | Rounds 11-13 showed short lift@1% proxy tuning was unreliable, while rounds 16 and 22 showed XGBoost carried disproportionate ensemble weight. That combination motivated AUC-ROC Optuna on XGB specifically. | **23.17** |
| **Plateau** | 26-47 | Twenty-two follow-up rounds kept returning to 23.174; by the end of this stage the evidence pointed to a stable local weight optimum. | The round-25 jump became the new anchor. Repeated exact reproductions plus rounds 44-47 showed that even tiny structural changes moved the weight solution away from the 23.174 saddle point. | 23.17 |
| **Escape** | 48 | Global weight search found a better blend than 23 rounds of local search. | Round 47 showed the scipy / Nelder-Mead weight landscape had multiple local optima, so the next discriminating test was a global optimizer rather than another base-model change. | **23.26** |
| **Final test** | 50 | Ranking quality generalizes near-perfectly; the gap concentrates in the extreme top-1% tail. | Once differential evolution broke the plateau at round 48 and reproduced at round 49, the next evidence need was held-out confirmation, not more tuning. | test: **22.48** |

Production Baseline vs. Campaign Champion:

|  | Baseline (default CatBoost, hybrid features) | Champion (DE-optimized 7-model ensemble) | Gain |
| --- | --- | --- | --- |
| **val lift@1%** | 22.21 | **23.26** | **+1.05 (+4.7%)** |
| **val AUC-ROC** | 0.859 | 0.857 | -0.002 |

### Speaker transcript draft

This slide is the benchmark, not the claim. It summarizes the finished prior IP commercial campaign in the same stage-by-stage format we used before, but now with one more column: what each stage learned from the trajectory immediately before it. That matters because this campaign did not improve through random search. It improved by repeatedly turning observations into the next experiment. The baselines established that hybrid features mattered. The family comparison showed it was time to widen the model set. The ensemble rounds showed structural diversity mattered more than more local tuning. That directly set up the XGBoost AUC-ROC breakthrough at round 25. Then the long plateau showed something different: the models were not obviously getting worse, but the weight optimizer kept collapsing to the same local solution. That is why round 48 switched from local search to differential evolution and found the final 23.26 validation result, which then held up with a 22.48 test lift at round 50. This is the trajectory the current autonomous rerun has to match.

---

## Slide 3 — Harness Design Principles

### Slide goal

Show the principles and recurring design patterns reflected in this project, and why they were chosen.

### On-slide structure

Headline:

**Harness Design Patterns Reflected In This Project**

Recommended visual treatment:

Use a pattern-and-rationale grid with two columns: principle on the left, reason on the right.

Patterns to show:

1. **Contract-first governance**
  - Fix the problem, data, and evaluation rules before the campaign starts
  - Why: the system should not redefine success mid-search

2. **Producer is not verifier**
  - Separate Planner, Executor, Reviewer, and Historian
  - Why: proposal, implementation, judgment, and synthesis should not collapse into one opinion

3. **Bounded autonomy**
  - Limit writable scope, repair attempts, and allowed actions
  - Why: experimentation should be high-velocity but still reversible and safe

4. **State on disk, not in chat**
  - Keep campaign memory in files, not only in conversational context
  - Why: the next round should reconstruct the truth from persistent artifacts

5. **Deterministic orchestration around probabilistic agents**
  - Put the driver between roles for validation, rollback, and state transitions
  - Why: policy and control should not depend on an agent remembering to behave

6. **Escalate instead of improvise**
  - Plateau, anomaly, and contract conflicts have explicit paths
  - Why: when evidence is weak or the system is stuck, the harness should change mode rather than guess

7. **Reason strategically, compute tactically**
  - Let the agent choose directions; let tools handle metrics, anomaly checks, and statistical verification
  - Why: language models are good at framing and diagnosis, not at being the final numerical authority

Bottom takeaway:

**The harness is not one trick. It is a set of design choices that deliberately shape how the agent is allowed to think, act, verify, and learn.**

### Speaker transcript draft

The design of the harness follows a small number of principles that show up repeatedly in the implementation. The first is contract-first governance: define the problem, the data boundaries, and the evaluation rule before any search begins. The second is role separation: the agent that proposes a move should not be the same one that judges it. The third is bounded autonomy: limit what can be edited, how many repair attempts are allowed, and how a round can succeed or fail. The fourth is durable state: write memory to disk so each role can rebuild context from evidence rather than from an unreliable running conversation. The fifth is deterministic control around probabilistic agents: the driver validates and enforces policy instead of trusting the model to do so perfectly. And finally, the system escalates instead of improvising when it hits ambiguity, anomaly, or plateau. Those are the principles that make the harness repeatable rather than merely clever.

---

## Slide 4 — Overarching Harness Mechanism Diagram

### Slide goal

Show the full mechanism in one diagram: from dataset and target metric, through contract approval, into role execution, review, synthesis, and the next round.

### On-slide structure

Headline:

**From Dataset And Metric To Autonomous Experiment Loop**

Recommended visual treatment:

Use a four-lane workflow diagram or swimlane:

- Lane 1: Human / business owner
- Lane 2: Claude Code playing role prompts
- Lane 3: Harness driver and guardrail layer
- Lane 4: Persistent state and artifacts

Proposed flow to visualize:

1. **Inputs arrive**
  - Dataset
  - Target definition
  - Business metric or target metric

2. **Contract drafting and approval gate**
  - Problem contract
  - Data contract
  - Evaluation protocol
  - Claude Code can prepare or refine these artifacts
  - Human approval is required before initialization proceeds

3. **Driver initializes campaign state**
  - `CAMPAIGN_STATE.json`
  - `results.tsv`
  - skeleton state files

4. **Planner role starts**
  - Reads contracts and campaign memory
  - Writes `NEXT_EXPERIMENT.md`
  - Driver runs `plan-check`

5. **Executor role starts**
  - Reads plan and allowed code surface
  - Edits only allowed files
  - Runs training and produces `run.log`
  - Driver runs `execute-finalize`

6. **Reviewer role starts**
  - Reads code, outputs, and required tools
  - Forms independent judgment
  - Emits verdict
  - Driver runs `review-finalize`

7. **Historian conditional path**
  - Triggered periodically or on plateau
  - Reads accumulated evidence across rounds
  - Writes pattern, assumption, and strategy artifacts
  - Driver runs `historian-finalize`

8. **Loop returns to Planner**
  - Next round begins from updated state, not from scratch

Artifacts to place in the state lane:

- `NEXT_EXPERIMENT.md`
- `run.log`
- `REVIEW.md`
- `results.tsv`
- `DEAD_ENDS.md`
- `NOTEBOOK.md`
- `ASSUMPTION_REGISTER.md`
- `PATTERN_BOOK.md`
- `STRATEGY_MEMO.md`
- `EXPERIMENT_TREE.json`

Bottom takeaway:

**Claude Code is the acting agent, but the harness decides what role it is playing, what it can touch, what it must read, and how its output becomes state.**

### Speaker transcript draft

This diagram is the main mechanism of the harness. It starts with the user giving the system a dataset, a target, and a business metric. From there, Claude Code can help prepare the campaign artifacts, but the harness requires explicit approval of the problem, data, and evaluation contracts before the campaign can even initialize. Once approved, the driver creates campaign state and controls the loop. The Planner reads the approved contracts and current memory, writes the next experiment, and passes through plan validation. The Executor applies one bounded change and runs training. The Reviewer independently judges the result and updates the campaign record. When the campaign hits either a periodic checkpoint or a plateau, the Historian is inserted to synthesize what the campaign has learned so far. Then the next round begins. The important point is that the agent is not wandering through a repo. It is stepping through a governed workflow where every role, artifact, and transition is explicit.

---

## Slide 5 — Verification And Guardrails

### Slide goal

Explain how the harness verifies that both the code path and the ML decision path are credible enough to accept.

### On-slide structure

Headline:

**How The Harness Verifies Code, Strategy, And Results**

Recommended visual treatment:

Use a staged verification ladder with four checkpoints: before execution, during execution, after execution, across rounds.

Verification checkpoints:

1. **Before execution**
  - Contracts approved
  - Plan schema validated
  - Allowed action type checked
  - Budget and time constraints enforced

2. **During execution**
  - Write scope restricted to approved surfaces
  - Bounded repair attempts
  - Commit and diff can be checked for substantive change

3. **After execution**
  - Metrics parsed from run artifacts
  - Mandatory tools run
  - Anomaly checks and bootstrap confidence checks applied
  - Reviewer decides independently before aligning with the plan
  - Noise-floor logic prevents calling trivial movement progress

4. **Across rounds**
  - Discards roll back
  - Anomalies pause the loop
  - Plateaus trigger historical diagnosis
  - Contract conflicts escalate instead of being silently worked around

Bottom line to show:

**The harness does not prove that a strategy is globally optimal. It proves that each accepted step is scoped, verified, and justified.**

### Speaker transcript draft

This slide is about trust. The harness verifies different things at different stages. Before execution, it verifies that the campaign is operating under approved contracts and that the planned experiment is structurally valid. During execution, it verifies bounded behavior by limiting what can be edited and how many repairs are allowed. After execution, it verifies the result numerically through required tools, anomaly detection, confidence checks, and independent review. Across rounds, it verifies the integrity of the search itself by rolling back failed steps, pausing on anomalies, and triggering the Historian when the loop appears stuck. So the claim is not that the harness can certify the one true best model. The claim is that it can make each accepted step much more reliable than an unconstrained autonomous coding loop.

---

## Slide 6 — How Experiment History Becomes The Next Experiment

### Slide goal

Explain how raw logs and experiment outcomes are converted into reusable memory that directly influences the next round.

### On-slide structure

Headline:

**How The Harness Reuses History And Logs**

Recommended visual treatment:

Use a left-to-right evidence transformation pipeline:

**Raw execution output**

- `train.py`
- `run.log`
- tool outputs

becomes

**Normalized round memory**

- `results.tsv`
- `REVIEW.md`
- `CAMPAIGN_JOURNAL.md`
- `DEAD_ENDS.md`
- `NOTEBOOK.md`
- `ASSUMPTION_REGISTER.md`

then becomes

**Cross-round synthesis**

- `PATTERN_BOOK.md`
- `STRATEGY_MEMO.md`
- `UNEXPLORED_TECHNIQUES.md`
- `EXPERIMENT_TREE.json`

then feeds into

**The next planning decision**

- What to avoid
- What to test
- What bottleneck to address
- What branch to deepen
- What assumption to validate

Key message box:

**The system does not just log the past. It operationalizes the past.**

### Speaker transcript draft

This is how the harness learns. A run produces raw outputs, but raw outputs alone are not enough to guide the next decision. The Reviewer converts those outputs into structured round memory: results, verdicts, dead ends, notebook observations, and explicit assumptions. Then the Historian reads across many rounds and turns that memory into higher-order artifacts: pattern extraction, bottleneck diagnosis, and the frontier of what remains worth trying. The Planner then consumes both the round-level memory and the synthesized memory to choose the next experiment. So the system does not reuse history as a passive archive. It reuses history as an active decision input.

---

## Slide 7 — Exploration–Exploitation Balance And Algorithm

### Slide goal

Deep dive into how the harness allocates experiment budget between trying new directions and refining known good ones.

### On-slide structure

Headline:

**How The Harness Balances Exploration And Exploitation**

Recommended visual treatment:

Use three stacked sections: representation, scoring, and phase policy.

Section 1: representation

- Experiments are tracked in an experiment tree
- Each node stores commit, parent commit, strategy class, metric, and verdict
- Strategy classes include model, feature, hyperparameter, imbalance, ensemble, validation, and error analysis

Section 2: scoring

- Use UCB1 by strategy class
- Formula:
  - mean delta + exploration bonus
  - UCB1_i = mean_delta_i + c * sqrt(ln(N) / n_i)
- Untried strategy classes get infinite priority until sampled
- Diminishing-return classes are penalized when recent deltas stay below the noise floor

Section 3: phase policy

- **Diversify**: 0% to 30% of budget
  - sample untried strategy classes first
- **Deepen**: 30% to 70% of budget
  - follow the highest UCB1 branches
- **Exploit**: 70% to 100% of budget
  - refine, ensemble, or final-tune the champion while preserving a small moonshot budget

Supporting details to show in callouts:

- Best branch point is the strongest kept commit to branch from
- Noise floor is used to detect when a direction is no longer producing meaningful gains
- Historian output can override a naive search preference when the bottleneck diagnosis says the campaign is stuck for a structural reason

Bottom takeaway:

**The harness does not search exhaustively. It allocates scarce experiment budget adaptively using evidence from prior rounds.**

### Speaker transcript draft

The harness uses an explicit exploration-exploitation policy rather than leaving search behavior implicit. Under the hood, experiments are organized as an experiment tree, with each node tagged by strategy class, verdict, and metric. The planner then receives a UCB1-style score by strategy class. That score combines observed average improvement with an exploration bonus, so untried directions are favored early and proven directions are deepened later. The harness also detects diminishing returns and downweights branches that have recently produced only noise-level movement. On top of that, the campaign follows a phase schedule: diversify early, deepen in the middle, exploit late. This lets the system spend experiment budget intentionally rather than drifting between random novelty and endless local tuning.
