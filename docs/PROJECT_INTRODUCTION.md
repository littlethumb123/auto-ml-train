# Autonomous ML Runner -- A Beginner's Guide

## Table of Contents

1. [What Business Problem Does This Solve?](#1-what-business-problem-does-this-solve)
2. [Results and Outcomes](#2-results-and-outcomes)
3. [System Design and Architecture](#3-system-design-and-architecture)
4. [The Core Mechanism: Contract-Governed Agent Loop](#4-the-core-mechanism-contract-governed-agent-loop)
5. [End-to-End Workflow and Pipeline](#5-end-to-end-workflow-and-pipeline)
6. [Memory Management: How the System Remembers](#6-memory-management-how-the-system-remembers)
7. [Strategy and Decision-Making: How the Next Experiment Is Chosen](#7-strategy-and-decision-making-how-the-next-experiment-is-chosen)
8. [Learning from History: The Historian and Pattern Evolution](#8-learning-from-history-the-historian-and-pattern-evolution)
9. [Future Enhancements](#9-future-enhancements)

---

## 1. What Business Problem Does This Solve?

Building high-performance machine learning models is an iterative, labor-intensive process. A data scientist typically runs dozens to hundreds of experiments -- trying different model families, tuning hyperparameters, engineering features, adjusting for class imbalance -- before converging on a champion model. Each experiment requires writing code, running it, evaluating results, deciding what to try next, and documenting what worked and what didn't. This cycle is slow, expensive, and error-prone when done manually.

**The Autonomous ML Runner automates this entire experimentation loop.** It replaces the manual scientist-in-the-loop with a system of four specialized LLM agents (Planner, Executor, Reviewer, Historian) that autonomously:

- Decide what experiment to run next, based on accumulated evidence
- Implement the code change in `train.py`
- Evaluate the result with statistical rigor (bootstrap confidence intervals, anomaly detection)
- Accept or reject the experiment based on transparent, auditable criteria
- Learn from accumulated history to avoid dead ends and exploit promising directions

The system has been deployed on two real business problems at CVS Health:

1. **IP-Commercial-New-TE (production campaign):** Predicting which commercial health insurance members will have 6+ inpatient hospital days in a 6-month window (the `ip6` target). This powers care management outreach -- identifying the highest-risk members so clinical teams can intervene before hospitalization. The primary metric is **lift@1%**: how much more likely are the top-1% scored members to be hospitalized compared to a random selection?

2. **Creditcard Fraud Detection (harness validation):** Binary fraud classification on the canonical Kaggle creditcard dataset (284,807 transactions, 0.17% fraud rate, PCA-transformed features). This campaign served as a smoke test to validate the harness itself.

---

## 2. Results and Outcomes

### IP-Commercial-New-TE Campaign (50 rounds, 50% of budget used)

| Metric | Target | Tabular-Only Baseline (r1) | Hybrid Baseline (r2) | Champion (r48) Val | Champion (r48) Test | Status |
|--------|--------|---------------------------|----------------------|-------------------|--------------------|----|
| lift@1% | >= 4.5 | 21.578 | 22.213 | **23.260** | **22.484** | Exceeds target by ~5x |
| AUC-ROC | >= 0.78 | 0.853 | 0.859 | **0.857** | **0.856** | Exceeds target |
| lift@5% | -- | 9.314 | 9.509 | 9.554 | 9.499 | Strong generalization |
| lift@10% | -- | 6.008 | 6.154 | 6.179 | 6.042 | Strong generalization |
| AUC-PR | -- | 0.103 | 0.109 | 0.111 | -- | -- |

- **Tabular-Only Baseline (r1):** CatBoost on 534 tabular features only (no embeddings)
- **Hybrid Baseline (r2):** CatBoost on 790 features (534 tabular + 256 new TE embeddings) -- embeddings add +0.635 lift@1% over tabular-only
- **Champion (r48):** 7-model DE-optimized ensemble after 50 rounds of autonomous experimentation -- +1.047 lift@1% over hybrid baseline

**Champion model:** A 7-model gradient boosting ensemble (3 LightGBM + 2 CatBoost + 2 XGBoost) with differential-evolution-optimized blending weights. Each base model is trained on a deliberately different feature subset (hybrid tabular+embeddings, tabular-only, or embedding-only) to maximize prediction diversity.

**Key outcome:** The top-1% of scored members are 22.5x more likely to be hospitalized than a randomly selected member. This enables clinical teams to focus outreach on the highest-risk individuals with high precision.

**Campaign statistics:**
- 12 keeps (improvements retained), 38 discards (experiments that didn't improve)
- 6 C2 plateau triggers (automated pause + Historian analysis)
- 16 dead ends formally catalogued
- 4 model families evaluated (CatBoost, LightGBM, XGBoost, ExtraTrees)
- 2 major breakthroughs discovered autonomously: AUC-ROC proxy for ensemble complementarity (round 25, +0.446 lift) and differential evolution global weight optimizer (round 48, +0.086 lift)

### Creditcard Fraud Smoke Test (10 rounds, budget exhausted)

| Metric | Target | Final |
|--------|--------|-------|
| val_pr_auc | >= 0.75 | **0.830** |

The smoke test validated the harness end-to-end: the Historian correctly diagnosed the bottleneck (undertrained model), recommended testing n_estimators convergence, and the Planner followed this guidance to produce 4 consecutive keeps.

---

## 3. System Design and Architecture

The system follows a **contract-first, role-separated, state-machine-driven** architecture. There are three distinct layers:

### Layer 1: Contracts (the "constitution")

Three signed contracts must be approved by a human before any experiment can run. The driver (`runner_driver.py`) enforces this via G1/G2/G3 gate validation at campaign initialization.

| Contract | What it governs | Example content |
|----------|----------------|-----------------|
| **PROBLEM_CONTRACT.md** | What problem to solve, success criteria, constraints | "ip6 binary classification; val_lift@1% >= 4.5; no third-party data" |
| **DATA_CONTRACT.md** | Data source, schema, split strategy, leakage audit | "new_te.parquet; digit-based splits; 40+ excluded columns" |
| **EVAL_PROTOCOL.md** | Primary metric, mandatory tools, budgets, action types | "val_lift_1pct maximize; 100 experiments; 60s timeout" |

Contracts are **sticky**: once signed, they cannot be changed except through the C3 escalation protocol (requires `tools/contract_diff` comparison + human approval).

### Layer 2: Roles (the "agents")

Four specialized agent roles, each defined by a role prompt in `runner/roles/`:

| Role | What it owns (can write) | What it reads | Purpose |
|------|-------------------------|---------------|---------|
| **Planner** | `NEXT_EXPERIMENT.md` | All contracts, all state files | Decides what experiment to run next |
| **Executor** | `train.py` only (+ declared helpers) | Contracts, NEXT_EXPERIMENT.md, train.py | Implements the code change and runs the experiment |
| **Reviewer** | `REVIEW.md`, `DEAD_ENDS.md`, `NOTEBOOK.md`, `CAMPAIGN_JOURNAL.md` | All contracts, all state, tool outputs, Executor stdout | Evaluates the result and issues a verdict |
| **Historian** | `STRATEGY_MEMO.md`, `PATTERN_BOOK.md`, `ASSUMPTION_REGISTER.md` (audit only) | All state files, results.tsv | Synthesizes lessons from accumulated history |

**Critical design principle: Producer != Verifier.** Each role is a fresh LLM invocation with only its declared input files. The Planner never sees its own code change. The Reviewer never sees the Planner's reasoning until Phase 2 of its evaluation (it first forms an independent judgment). No role can write to another role's state files. This separation prevents self-deception and creates genuine adversarial review.

### Layer 3: Driver (the "state machine")

`runner_driver.py` (695 lines) is a deterministic Python state machine that orchestrates the loop. It is not an LLM -- it is pure code that:

- Validates contracts at initialization
- Checks plan schema before execution
- Parses Executor output for structured channel lines (`RUN_COMPLETE`, `RUN_FAILED`, etc.)
- Enforces write-scope (only `train.py` may be modified)
- Enforces mandatory tools (anomaly detection + bootstrap CI must run before any "keep" verdict)
- Applies verdicts, updates `results.tsv` and `CAMPAIGN_STATE.json`
- Triggers the Historian automatically when plateau conditions or periodic intervals are met
- Issues C3 advisories when the target gap is within 2x the bootstrap standard error

The driver is the guardrail layer -- it ensures the agents cannot violate the contract invariants, regardless of what the LLM generates.

### Supporting Infrastructure

- **20 tools** in `runner/tools/` (anomaly detection, bootstrap CI, SHAP reports, Optuna HP search, feature selection, cross-validation, data profiling, etc.) -- these handle numerical computation that LLMs should not do
- **`log.py`**: Appends rows to `results.tsv` and updates `CAMPAIGN_STATE.json` after each experiment
- **`shared/metrics.py`**: Business-critical metric functions (lift@k%, precision@k%, AUC-PR, AUC-ROC)
- **`prepare.py`**: Frozen data infrastructure (load, split, evaluate) -- read-only, never modified during experiments

---

## 4. The Core Mechanism: Contract-Governed Agent Loop

The fundamental mechanism is a **Plan-Execute-Review loop with Historian synthesis**, governed by contracts and enforced by a deterministic driver.

```
                  ┌──────────────────────────────┐
                  │     CONTRACTS (G1/G2/G3)      │
                  │ PROBLEM · DATA · EVAL_PROTOCOL│
                  └──────────┬───────────────────┘
                             │ governs
                  ┌──────────▼───────────────────┐
        ┌────────►│        PLANNER               │
        │         │  reads: all state + contracts │
        │         │  writes: NEXT_EXPERIMENT.md   │
        │         └──────────┬───────────────────┘
        │                    │ plan
        │         ┌──────────▼───────────────────┐
        │         │        EXECUTOR               │
        │         │  reads: plan + train.py       │
        │         │  writes: train.py only        │
        │         │  runs: python train.py        │
        │         └──────────┬───────────────────┘
        │                    │ result
        │         ┌──────────▼───────────────────┐
        │         │        REVIEWER               │
        │         │  reads: result + all state    │
        │         │  writes: REVIEW, DEAD_ENDS,   │
        │         │  NOTEBOOK, JOURNAL            │
        │         │  emits: VERDICT keep|discard  │
        │         └──────────┬───────────────────┘
        │                    │
        │         ┌──────────▼───────────────────┐
        │         │     DRIVER (state machine)    │
        │         │  applies verdict              │
        │         │  updates results.tsv + state  │
        │         │  checks historian trigger     │
        │  next   └──────────┬───────────────────┘
        │  round             │
        │                    ▼
        │              ┌───────────┐
        │         no   │ Historian │  yes
        │◄─────────────┤ trigger?  ├──────────┐
        │              └───────────┘          │
        │                              ┌──────▼──────────┐
        │                              │    HISTORIAN     │
        │                              │  trajectory +   │
        │                              │  pattern + audit │
        │                              │  writes: MEMO,  │
        │                              │  PATTERN_BOOK,   │
        │                              │  ASSUMPTION_REG  │
        └──────────────────────────────┘                  │
                       ▲                                  │
                       └──────────────────────────────────┘
```

**On each round, the driver enforces these gates:**

1. **Plan-check gate**: Validates `NEXT_EXPERIMENT.md` YAML frontmatter schema and allowed action types before execution can begin
2. **Write-scope gate**: After execution, verifies only `train.py` (and declared helpers) were modified
3. **Mandatory-tools gate**: The Reviewer must run `anomaly.py` and `bootstrap_ci.py` before issuing a "keep" verdict. If these tools were not invoked, the driver rejects the verdict.
4. **C2 plateau gate**: After 3 consecutive discards, the driver automatically triggers the Historian (no agent decides this -- it is a deterministic rule)
5. **C3 advisory gate**: When the gap to the success target is within 2x the bootstrap standard error, the driver warns that measurement noise may be the bottleneck, not modeling

**Verdict outcomes:**
- **keep**: The experiment improved the primary metric. The commit is retained; `best_so_far` in `CAMPAIGN_STATE.json` is updated; `consecutive_discards` resets to 0.
- **discard**: The experiment did not improve. The commit is rolled back (`git reset --hard HEAD~1`); `consecutive_discards` increments.
- **anomaly**: Implausibly bad result (e.g., metric dropped below 50% of the champion). Triggers investigation.
- **crash/malformed**: The experiment failed to run or produced invalid output. The Executor gets up to 2 repair attempts.

---

## 5. End-to-End Workflow and Pipeline

### Campaign Lifecycle

A campaign is a complete experimentation run on a single problem. Here is the lifecycle:

#### Phase 0: Setup (human)
1. Human writes the three contracts: `PROBLEM_CONTRACT.md`, `DATA_CONTRACT.md`, `EVAL_PROTOCOL.md`
2. Human writes `prepare.py` (frozen data infrastructure) and an initial `train.py`
3. Human approves the contracts (adds `approved_at` and `approved_by` fields)
4. Human creates a campaign branch: `git checkout -b campaign/<id>`

#### Phase 1: Initialization (driver)
```bash
runner/run_round.sh init <campaign_dir>
```
The driver validates G1/G2/G3 gates, creates `CAMPAIGN_STATE.json`, initializes `results.tsv`, and creates skeleton state files (`ASSUMPTION_REGISTER.md`, `PATTERN_BOOK.md`, etc.).

#### Phase 2: Experiment Loop (automated)
Each round follows this sequence:

```bash
# 1. Planner agent invocation
#    Reads all state → writes NEXT_EXPERIMENT.md
runner/run_round.sh plan-check <campaign_dir>

# 2. Executor agent invocation
#    Reads plan → modifies train.py → runs experiment → commits
runner/run_round.sh execute-finalize <campaign_dir>

# 3. Reviewer agent invocation
#    Reads result → runs mandatory tools → issues verdict
runner/run_round.sh review-finalize <campaign_dir>

# 4. (Conditional) Historian agent invocation
#    Triggered every 10 rounds OR after 3 consecutive discards
runner/run_round.sh historian <campaign_dir>
runner/run_round.sh historian-finalize <campaign_dir>
```

#### Phase 3: Campaign Conclusion (human + agent)
When the budget is exhausted, the target is met, or the human decides to stop:
1. Final test-set evaluation run
2. `FINAL_REPORT.md` is generated (executive summary, timeline, what worked, dead ends, generalization analysis, recommendations)
3. Champion commit is merged to main

### Data Flow Through the Pipeline

```
data/creditcard.csv  ──►  prepare.py (frozen)  ──►  train.py (modified each round)
     or                     │                          │
.cache/new_te.parquet       │ load_data()              │ train models
                            │ get_splits()             │ compute metrics
                            │ evaluate()               │ print structured output
                            ▼                          ▼
                     stratified splits         metric block between --- markers
                     (train/val/test)                   │
                                                        ▼
                                              Reviewer reads stdout
                                              Reviewer runs anomaly.py
                                              Reviewer runs bootstrap_ci.py
                                                        │
                                                        ▼
                                              VERDICT → results.tsv
```

### What `train.py` Produces

The Executor modifies `train.py` to implement each experiment. When run, it prints a structured metric block between `---` delimiters:

```
---
val_lift_1pct: 23.260
val_auc_roc: 0.857
val_lift_5pct: 9.554
training_seconds: 245.3
---
```

The Reviewer and driver parse this output to evaluate the experiment.

---

## 6. Memory Management: How the System Remembers

The system uses a **file-based distributed memory** architecture. There is no database, no vector store, and no shared LLM context between rounds. Each agent is a fresh LLM invocation that reconstructs its understanding by reading a declared set of files.

### Memory Files and Their Purposes

| File | Who writes | Persistence | Purpose |
|------|-----------|-------------|---------|
| **results.tsv** | Driver (via `log.py`) | Permanent | Complete experiment history: round, commit, metrics, model family, action type, verdict, token counts |
| **CAMPAIGN_STATE.json** | Driver | Updated each round | Current round, budget, best_so_far, consecutive_discards, historian trigger state |
| **DEAD_ENDS.md** | Reviewer | Append-only | Techniques that have been tried and confirmed to not work, with evidence and reasoning |
| **NOTEBOOK.md** | Reviewer | Append-only | Surprising-but-not-dead-end observations worth remembering (e.g., "embedding-only baseline trains 6x faster than tabular") |
| **REVIEW.md** | Reviewer | Append-only | Detailed review of every experiment: bootstrap CI, anomaly check, verdict reasoning |
| **CAMPAIGN_JOURNAL.md** | Reviewer | Append-only | Short one-line summary per round for quick scanning |
| **NEXT_EXPERIMENT.md** | Planner | Overwritten each round | The current experiment plan: hypothesis, action type, expected delta, evidence from memory |
| **ASSUMPTION_REGISTER.md** | Reviewer (creates entries), Historian (audits) | Append + update | Explicit assumptions the system is operating under, with confidence levels and verification status |
| **PATTERN_BOOK.md** | Historian | Append + update | Structural patterns extracted from 3+ rounds of evidence (e.g., "feature additions destabilize Optuna") |
| **STRATEGY_MEMO.md** | Historian | Overwritten each run | Current strategic assessment: trajectory narrative, bottleneck diagnosis, highest-ROI next action |
| **UNEXPLORED_TECHNIQUES.md** | Historian | Append + update | Comprehensive catalog of techniques not yet tried, with expected deltas |
| **PRIORS.md** | Contract (cross-campaign) | Sticky | Known-good and known-bad patterns from prior campaigns |
| **STRATEGY_GUIDE.md** | Contract (advisory) | Sticky | Evidence-conditioned triggers and decision heuristics |

### How Memory Flows Between Roles

```
Planner reads ──► ALL state files (full context)
                  ├── results.tsv (what has been tried)
                  ├── DEAD_ENDS.md (what NOT to retry)
                  ├── NOTEBOOK.md (surprising observations)
                  ├── ASSUMPTION_REGISTER.md (what we believe and confidence)
                  ├── PATTERN_BOOK.md (structural regularities)
                  ├── STRATEGY_MEMO.md (Historian's strategic assessment)
                  ├── UNEXPLORED_TECHNIQUES.md (what to try)
                  ├── PRIORS.md (cross-campaign knowledge)
                  └── STRATEGY_GUIDE.md (decision heuristics)

Executor reads ──► NEXT_EXPERIMENT.md + train.py + contracts
                   (deliberately narrow -- Executor doesn't see history)

Reviewer reads ──► Executor stdout + all state + tool outputs
                   (forms independent judgment BEFORE reading the plan)

Historian reads ─► All state files
                   (synthesizes across multiple rounds)
```

### Key Design Choice: File-Based, Not Context-Based

Because each agent is a fresh LLM invocation, there is no accumulated conversational context. This is a deliberate design choice:

1. **Reproducibility**: Given the same state files, any agent invocation will produce deterministic-ish results
2. **Auditability**: Every piece of memory is a file in git -- human-readable, diffable, version-controlled
3. **No context window limits**: State files can grow without hitting token limits (the LLM reads only what it needs)
4. **Role separation**: Each role sees exactly its declared inputs -- no information leakage

---

## 7. Strategy and Decision-Making: How the Next Experiment Is Chosen

The Planner uses a multi-layered decision process defined in `runner/roles/planner.md` (11 steps):

### Step 1: Evidence Gathering
The Planner reads all state files and builds a summary of:
- What has been tried (from `results.tsv`)
- What worked and what didn't (from `REVIEW.md`, `CAMPAIGN_JOURNAL.md`)
- What is known to be a dead end (from `DEAD_ENDS.md`)
- What structural patterns exist (from `PATTERN_BOOK.md`)
- What the Historian recommends (from `STRATEGY_MEMO.md`)
- What assumptions the system is operating under (from `ASSUMPTION_REGISTER.md`)
- What hasn't been tried yet (from `UNEXPLORED_TECHNIQUES.md`)

### Step 2: Strategic Hierarchy
The `STRATEGY_GUIDE.md` contract provides a ROI-ordered hierarchy:

```
1. Data / feature representation   ← highest ROI when untapped
2. Model family capacity           ← second
3. HP search within best family    ← third
4. Ensemble / calibration          ← last; marginal gains only
```

The Planner determines where the campaign currently sits by checking evidence-conditioned triggers (a table of 14 conditions in `STRATEGY_GUIDE.md`). For example:
- "No baseline exists" → establish one
- "Fewer than 2 model families tried" → try an alternative
- "2+ A_hp rounds with diminishing delta" → move to features or ensemble
- "consecutive_discards >= 3" → read Historian's STRATEGY_MEMO before planning

### Step 3: Pre-Selection Reasoning (mandatory)
Before committing to an action, the Planner must:
1. Enumerate 2-3 candidate actions suggested by the evidence
2. Estimate expected delta for each using `PRIORS.md` ceilings and `results.tsv` history
3. Check each candidate against `DEAD_ENDS.md` and `PATTERN_BOOK.md`
4. Choose the candidate with the highest expected delta that is not ruled out
5. Record the alternatives and reasoning in `NEXT_EXPERIMENT.md`

### Step 4: Assumption-Aware Novelty Check
When `consecutive_discards >= 2`, the Planner must specifically check the `ASSUMPTION_REGISTER.md` for unverified assumptions that might be causing the plateau. If a critical assumption is flagged, the Planner should design an experiment that tests it.

### Step 5: Write the Plan
The output is `NEXT_EXPERIMENT.md` with YAML frontmatter (experiment_id, action_type, model_family, hypothesis, expected_delta) and markdown body (evidence from memory, implementation instructions, success criteria).

### Real-World Example of Strategic Learning

From the IP campaign NOTEBOOK.md:
- Round 25 discovered that AUC-ROC as an Optuna proxy for XGBoost produces ensemble-complementary predictions (+0.446 lift breakthrough)
- Rounds 26-34 explored variations: different seeds, different proxies, different model families -- all failed
- Round 33 discovered that adding features destabilizes the Optuna landscape
- The Historian synthesized these into Pattern Book entries
- The Planner in subsequent rounds avoided feature additions to XGB and focused on ensemble weight optimization instead
- Round 48: the Planner (informed by NOTEBOOK observations about scipy's multiple local optima) proposed differential evolution, breaking through the 23-round ceiling

---

## 8. Learning from History: The Historian and Pattern Evolution

The Historian is the system's **meta-cognitive layer**. It does not run experiments -- it analyzes the trajectory of experiments to extract transferable lessons.

### When the Historian Fires

The Historian is triggered automatically by the driver (not by any agent's decision):
- **Periodic**: Every 10 rounds (configurable in `EVAL_PROTOCOL.md`)
- **Plateau**: After 3 consecutive discards (the C2 plateau trigger)

### What the Historian Produces

The Historian's 10-step procedure (`runner/roles/historian.md`) produces three outputs:

#### 1. STRATEGY_MEMO.md (overwritten each run)
A strategic assessment of the campaign's current state:
- **Trajectory narrative**: Phase classification (exploration, exploitation, plateau), delta-per-round trend, improvement velocity
- **Bottleneck diagnosis**: Exactly one of `model_quality`, `optimizer_quality`, `data_quality`, `eval_quality`, `feature_representation`, or `near_optimum`
- **Highest-ROI next action**: A specific recommendation for the Planner

Example from the smoke-test campaign (round 4, C2 trigger):
> "Bottleneck: optimizer_quality. LightGBM with n_estimators=600 at lr=0.02 may be undertrained. Recommendation: test n_estimators=1000."

This recommendation led to 4 consecutive keeps (rounds 6-10).

#### 2. PATTERN_BOOK.md (append/update)
Structural regularities extracted from 3+ rounds of evidence. Each pattern includes:
- The pattern statement
- Supporting evidence (specific rounds)
- Confidence level (low/medium/high)
- Status (active, superseded, falsified)
- Implication for the Planner

Example pattern from the IP campaign:
> "P: Feature additions from raw data columns consistently hurt PR-AUC. Evidence: round 4 (log1p_Amount, delta=-0.035), round 9 (Time_mod_86400, delta=-0.044). Confidence: high. Implication: ALL feature addition experiments using Time/Amount columns are dead ends."

Patterns can evolve: P-1 in the smoke-test campaign was initially "simple perturbations consistently degrade" (low confidence), then partially falsified when n_estimators increases worked, then refined into the more precise P-3.

#### 3. ASSUMPTION_REGISTER.md (audit, not create)
The Historian audits existing assumptions (created by the Reviewer on each "keep" verdict):
- Checks whether new evidence supports or contradicts each assumption
- Flags assumptions as CRITICAL if they are load-bearing + unverified after 2+ audits
- Updates verification status and confidence levels

Example critical assumption flagged by the Historian:
> "CRITICAL: LightGBM champion HP (num_leaves=63, lr=0.02, n_est=600) is near-optimal for this dataset. This is implicit but NOT formally tested. n_estimators has not been varied."

### How Historical Knowledge Feeds Forward

The loop from history to strategy is:

```
Reviewer observes    ──► DEAD_ENDS.md (negative knowledge)
                     ──► NOTEBOOK.md (surprising observations)
                     ──► ASSUMPTION_REGISTER.md (beliefs + confidence)
                              │
                              ▼
Historian synthesizes ──► PATTERN_BOOK.md (structural regularities)
                      ──► STRATEGY_MEMO.md (what to do next)
                      ──► ASSUMPTION_REGISTER.md (audited beliefs)
                              │
                              ▼
Planner consumes      ──► Avoids dead ends
                      ──► Exploits patterns
                      ──► Tests critical assumptions
                      ──► Follows Historian strategy
                              │
                              ▼
                         NEXT_EXPERIMENT.md
```

This creates a **self-correcting learning loop**: the system accumulates knowledge, revises its beliefs, and adapts its strategy as evidence accumulates -- all through files, without persistent LLM context.

---

## 9. Future Enhancements

### 9.1 Global Expert Knowledge Base (proposed)

**The idea:** The current system's strategy is entirely derived from *local knowledge* -- what the system has learned during the current campaign through its own experimentation. It starts each campaign from near-zero domain understanding (only the `PRIORS.md` contract and `STRATEGY_GUIDE.md` advisory provide seed knowledge). The proposal is to embed a pre-built **global expert knowledge base** into the harness, containing:

- Domain expert knowledge (e.g., clinical risk modeling best practices for healthcare)
- Previous research findings (literature, academic papers)
- Kaggle competition insights and grandmaster playbooks
- Experience-based lessons learned from past projects

The agent would leverage this global knowledge from round 1, and as local experimentation progresses, both global and local knowledge would inform decision-making. Over time, the local knowledge (which is specific to this dataset and problem) would complement or override the global priors.

**Critical evaluation (evidence-based):**

**Where this is strongly supported by evidence:**

1. **Cold-start inefficiency is real and measurable.** In the IP campaign, rounds 1-8 were spent establishing baselines and discovering that LightGBM beats CatBoost defaults -- knowledge that an experienced Kaggle practitioner would bring from day one. The smoke-test campaign spent 3 rounds on failed perturbations before the Historian diagnosed the real issue (undertrained model). A pre-loaded knowledge base could have compressed these phases.

2. **The existing PRIORS.md mechanism already works this way -- just at minimal scale.** Cross-campaign priors (e.g., "SMOTE + scale_pos_weight double-counts imbalance") successfully prevented the IP campaign from repeating creditcard-campaign mistakes. The proposal extends this from a few bullet points to a structured knowledge base. Evidence: none of the 16 dead ends in the IP campaign overlap with PRIORS.md entries -- the system already avoids known bad paths when given prior knowledge.

3. **UNEXPLORED_TECHNIQUES.md demonstrates the value of structured technique catalogs.** The IP campaign's UNEXPLORED_TECHNIQUES.md contains 80+ techniques organized by category (feature engineering, imbalance handling, model families, ensemble methods, etc.) with expected deltas. This was manually populated. A global knowledge base could auto-populate similar catalogs for any problem domain.

4. **The STRATEGY_GUIDE.md evidence-conditioned triggers work well.** The 14-condition trigger table effectively guides Planner decisions. A global knowledge base could provide domain-specific trigger conditions (e.g., "for healthcare claims data with <1% positive rate, start with class-weighted gradient boosting before trying resampling").

**Where caution is warranted:**

1. **Global knowledge can be wrong for local contexts.** The IP campaign's biggest breakthrough (AUC-ROC proxy for ensemble complementarity, round 25) was counter-intuitive -- using a *worse* individual metric to get *better* ensemble performance. No Kaggle playbook would recommend this. A global knowledge base that says "optimize for the target metric" would have steered the system away from this discovery. The system needs a mechanism to weigh local evidence over global priors when they conflict.

2. **The current architecture already handles knowledge accumulation gracefully.** The Historian's PATTERN_BOOK and STRATEGY_MEMO are self-correcting: patterns are flagged with confidence levels, can be falsified, and evolve over time. Global knowledge imported without this calibration mechanism could become stale or misleading priors. The solution would need to treat global knowledge with the same assumption-audit rigor that the Historian applies to local assumptions.

3. **Domain specificity vs. generality is a real tension.** Kaggle knowledge about tabular classification may not transfer to healthcare claims modeling. The IP campaign discovered that "ensemble complementarity > individual accuracy" -- a pattern that is well-known in Kaggle but whose specific mechanisms (XGB_h weight dominance, scipy weight landscape multi-modality) are entirely local. Global knowledge can tell you *that* ensembles help, but not *how* to build one for your specific data.

4. **Knowledge maintenance and staleness.** ML best practices evolve rapidly (new model architectures, library updates, discovered failure modes). A static knowledge base would degrade over time. The system would need a mechanism to version, update, and deprecate global knowledge entries -- similar to how PATTERN_BOOK entries have status fields (active/superseded/falsified).

**Recommended implementation approach (if pursued):**

The most natural integration point is extending the existing contract layer with a new `KNOWLEDGE_BASE.md` or structured knowledge directory that:

- Is organized by domain (healthcare, fraud, tabular classification, etc.) and technique category (matching UNEXPLORED_TECHNIQUES structure)
- Each entry has provenance (source: Kaggle/paper/expert), confidence level, and applicability conditions
- The Planner treats global entries as lower-confidence priors that can be overridden by local PATTERN_BOOK entries
- The Historian explicitly compares local findings against global priors and flags contradictions
- Cross-campaign learning flows back into the global knowledge base (the IP campaign's "ensemble complementarity > individual accuracy" discovery becomes a future global prior with conditions)

This would create a **two-speed learning system**: fast local learning within a campaign (rounds), and slow global learning across campaigns (weeks/months).

### 9.2 Other Potential Enhancements (identified from codebase evidence)

**Phase 2 tools (deferred stubs in the codebase):** Four tools are currently stubs returning "deferred_to_phase_2": `calibration.py`, `dimred_eval.py`, `integrity_check.py`, and `multi_fidelity.py`. Implementing these would add:
- Model calibration assessment (important for healthcare: well-calibrated probabilities enable threshold-based outreach decisions)
- Dimensionality reduction evaluation (relevant for the 256-embedding-dimension feature space)
- Data integrity checks (automated data quality validation)
- Multi-fidelity evaluation (proxy metrics for faster iteration)

**Cross-validation upgrade (C3 advisory already issued):** The IP campaign's `FINAL_REPORT.md` explicitly recommends upgrading from single-holdout to k-fold CV. The current bootstrap SE=0.503 makes gains <0.5 undetectable. With 4-fold CV (using digit-groups 0-1, 2-3, 4-5, 6-7), SE would drop to ~0.25, enabling finer discrimination. Two C3 advisories (rounds 29 and 40) were issued for this but not acted upon.

**Re-evaluation of discarded experiments under global optimization:** The FINAL_REPORT documents that 22 experiments (rounds 25-47) were discarded under Nelder-Mead's suboptimal weights. Some might beat 23.260 under differential evolution. The campaign has 50 remaining rounds to test this hypothesis. This is a specific, actionable improvement for the IP campaign.

**Automated campaign resumption:** Currently, the human must manually invoke each round via `runner/run_round.sh`. The `.claude/hooks/force-continue.sh` hook and the `AGENTS-remote.md` file suggest work toward fully autonomous operation (possibly via Vertex AI remote execution), but this is not yet production-ready.

**Token budget optimization:** The harness tracks token usage per role per round (planner_tokens, executor_tokens, reviewer_tokens, historian_tokens) in `results.tsv`. This data could be used to identify cost optimization opportunities (e.g., shorter prompts for simple rounds, dynamic role-prompt compression, or early termination of unproductive exploration).
