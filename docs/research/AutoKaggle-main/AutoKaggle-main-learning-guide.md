# AutoKaggle: From Code To Craft — A Learning Guide

**Guide Type:** Conceptualized Engineering Knowledge & Actionable Patterns  
**Source Repository:** `/home/jupyter/Thinkubator/auto_train/other_repos/AutoKaggle-main`  
**Date:** 2026-04-21  
**Companion:** [Technical Anatomy Report](./AutoKaggle-main-technical-anatomy-report.md)

---

## Table of Contents

1. [What This Guide Teaches](#1-what-this-guide-teaches)
2. [Conceptual Foundation](#2-conceptual-foundation)
3. [Pattern Catalog](#3-pattern-catalog)
4. [Decision Frameworks](#4-decision-frameworks)
5. [Implementation Playbooks](#5-implementation-playbooks)
6. [Architecture Templates](#6-architecture-templates)
7. [Engineering Practice Guide](#7-engineering-practice-guide)
8. [Common Pitfalls & How This Repo Avoids Them](#8-common-pitfalls--how-this-repo-avoids-them)
9. [Skill-Building Exercises](#9-skill-building-exercises)
10. [Quick Reference](#10-quick-reference)

---

## 1. What This Guide Teaches

This guide extracts the reusable engineering ideas behind AutoKaggle without assuming you want to build a Kaggle agent specifically. The underlying problem class is broader: any system that asks LLMs to perform multi-step analytical or coding work over real artifacts needs structure, validation, and memory. AutoKaggle is useful because it shows how to decompose that problem into a finite-state workflow, then enforce quality with contracts and critique.

### Prerequisites

- Working Python knowledge
- Comfort with LLM prompting and API-based inference
- Familiarity with tabular data workflows and pandas/sklearn-style tooling
- Basic understanding of process orchestration and test automation

### Learning Outcomes

- You will understand when to use a phase-based state machine instead of a free-form generalist agent.
- You will be able to design a code-generation loop that does not trust model output after execution alone.
- You will learn how semantic tool retrieval can shrink prompt surface area without giving up flexibility.
- You will know how to carry state and prior failures across retries without storing entire raw contexts forever.
- You will have templates for building your own orchestrator, validator, and artifact-reporting layers.

---

## 2. Conceptual Foundation

### 2.1 Problem Domain

The general problem is autonomous execution of open-ended expert workflows. These workflows share three characteristics:

- they span multiple stages where each stage changes what inputs are valid next
- they produce real artifacts, not only text
- they are easy for an LLM to describe and easy for it to get subtly wrong

Examples include data-science pipelines, ETL remediation, multi-step code migration, security triage, and report generation over generated evidence.

The challenge is that plain chat is a poor control structure for this class of work. It does not tell you what stage you are in, which artifacts must exist, what counts as acceptable completion, or how to learn from a failed attempt.

### 2.2 Solution Strategy

AutoKaggle’s core strategy is to replace “one smart agent” with “a workflow that happens to use agents.” In practice, that means:

1. model the task as explicit phases
2. assign a narrow role to each agent in that phase
3. define artifact contracts for phase success
4. persist the evidence trail
5. repeat a phase when contracts or review do not clear the threshold

That strategy generalizes far beyond Kaggle. If your task has natural intermediate artifacts and a meaningful quality threshold, you can often build a more reliable system by making the workflow first-class.

### 2.3 Key Abstractions

**Phase**  
The current stage of work, including its goals, constraints, inputs, and required outputs. In AutoKaggle this is driven by `multi_agents/config.json` and materialized through `multi_agents/state.py:13`.

**State**  
The mutable execution object that ties phase, memory, directories, rules, tests, and scores together. This is the minimal shared truth your agents need.

**Artifact Contract**  
The concrete definition of success for a phase: a file exists, rows are preserved, target columns remain intact, submission schema matches, and so on. AutoKaggle encodes this in `multi_agents/tools/unit_test.py:35` and `config.json`.

**Review Gate**  
A policy layer that decides whether to advance, repeat, or fail after examining the artifact and the execution context. AutoKaggle combines deterministic tests with `Reviewer` scoring.

**Tool Surface**  
The set of helper functions, documentation, or APIs the code-writing agent may rely on. AutoKaggle narrows this by phase and retrieves relevant docs semantically through `Agent._get_tools()`.

**Experience Memory**  
A compact record of prior attempts, their failures, and their reviewer feedback, reused during retries rather than reloading every raw interaction.

---

## 3. Pattern Catalog

### Pattern 1: Phase-Oriented Multi-Agent Loop

**Problem:** Free-form agents lose track of stage, success criteria, and handoff boundaries in long tasks.  
**Solution:** Encode the workflow as named phases, attach a fixed role sequence to each phase, and advance only when the phase is explicitly complete.

**Structure:**

```text
Phase -> [Agent A, Agent B, Agent C]
      -> artifacts
      -> review/tests
      -> repeat or next phase
```

**How AutoKaggle Implements It:**  
`multi_agents/config.json` maps each phase to its agents, tools, and tests; `multi_agents/sop.py:45` executes the sequence; `multi_agents/sop.py:69` advances or repeats.

**When To Use:**

- your task has natural intermediate outputs
- later stages depend on earlier artifacts
- you need auditability and bounded retries

**When NOT To Use:**

- the task is truly single-step
- there is no meaningful artifact between stages
- latency matters more than auditability

**Variations:**

- one agent per phase
- multiple reviewers instead of one reviewer
- human approval inserted before the transition gate

### Pattern 2: Critic-Gated Code Synthesis

**Problem:** LLM-generated code may run successfully while still violating the task’s real contract.  
**Solution:** Separate code authoring from judging, and add deterministic contract tests between the two.

**Structure:**

```text
Planner -> Developer -> Execute -> Contract Tests -> Reviewer
                                       |
                                       +--> failure context -> retry/debug
```

**How AutoKaggle Implements It:**  
`Developer._run_code()` executes the generated script, `Developer._conduct_unit_test()` runs phase checks, and `Reviewer._execute()` turns results into scores and suggestions (`developer.py:142`, `:249`, `reviewer.py:81`).

**When To Use:**

- the output can be tested cheaply
- failure modes split into runtime errors and semantic/data-quality errors
- you want bounded autonomous retries

**When NOT To Use:**

- no reliable postconditions can be checked
- the cost of repeated execution is prohibitive

**Variations:**

- replace the reviewer with a rules engine
- keep the reviewer but make transition decisions fully deterministic
- use a static analyzer before runtime execution

### Pattern 3: Semantic Tool Surface Reduction

**Problem:** A large helper library overwhelms prompts if presented wholesale.  
**Solution:** Filter tools by phase, then retrieve only relevant tool documentation for the current task.

**Structure:**

```text
phase config -> candidate tools -> semantic retrieval -> injected docs -> generated code
```

**How AutoKaggle Implements It:**  
`config.json` limits tool names by phase, `Agent._get_tools()` chooses the active subset, and `RetrieveTool` queries a ChromaDB collection built from markdown docs (`agent_base.py:189`, `retrieve_doc.py:68`, `:87`).

**When To Use:**

- you have dozens of helper functions
- the code-writing agent needs flexibility more than strict tool execution
- your internal API is still evolving

**When NOT To Use:**

- your tool set is tiny
- reliability and permission control matter more than authoring flexibility

**Variations:**

- pure semantic retrieval
- semantic retrieval followed by structured function calling
- hand-curated tool bundles per task type

### Pattern 4: Cumulative Artifact Inheritance

**Problem:** Multi-stage workflows waste effort when every phase starts from scratch.  
**Solution:** Carry forward prior code or artifacts, but strip obsolete output side effects before reuse.

**Structure:**

```text
previous artifact -> sanitize side effects -> append new stage logic -> new artifact
```

**How AutoKaggle Implements It:**  
`Developer._is_previous_code()`, `_delete_output_in_code()`, and `_generate_code_file()` reuse earlier phase code while removing plotting and print behavior that should not be replayed (`developer.py:30`, `:39`, `:92`).

**When To Use:**

- stages truly refine the same underlying program
- earlier preprocessing must remain consistent later

**When NOT To Use:**

- each stage uses a completely different representation
- inherited side effects are hard to isolate safely

**Variations:**

- code inheritance
- artifact inheritance through structured data objects
- notebook cell inheritance with explicit pruning

### Pattern 5: Artifact-Based Summarization

**Problem:** End-of-run narratives drift if they summarize model memory rather than actual outputs.  
**Solution:** Build the summary from generated artifacts, review files, and selected visual evidence.

**Structure:**

```text
plan + code + output + review + plots -> questions -> answers -> report
```

**How AutoKaggle Implements It:**  
`Summarizer._execute()` builds questions, answers them from artifacts, and augments the report with plot interpretations from `ImageToTextTool` (`summarizer.py:40`, `:84`, `:101`).

**When To Use:**

- humans will read the result
- you need postmortems or reproducibility
- visual outputs matter

**When NOT To Use:**

- no one consumes the report
- artifact persistence cost outweighs the debugging value

**Variations:**

- text-only summarization
- summary over structured event logs
- summary generated by a separate offline analytics process

---

## 4. Decision Frameworks

### Decision 1: Specialized Role Agents Or A Generalist Agent?

**When You Face:** A complex workflow with clearly different cognitive tasks.

| Option | Pros | Cons | Best When |
|---|---|---|---|
| Generalist agent | Simple architecture, fewer handoffs | Harder to debug, weaker accountability | Task is short and homogeneous |
| Specialized roles | Clear responsibilities, better prompts, easier diagnosis | More orchestration overhead | Task spans planning, coding, reviewing, summarizing |

**What AutoKaggle Chose:** Specialized roles via `Reader`, `Planner`, `Developer`, `Reviewer`, and `Summarizer`.  
**Recommendation:** Default to specialized roles when the task includes authoring plus evaluation. Collapse roles only when you can prove the orchestration overhead is not paying off.

### Decision 2: Prompt-Injected Tools Or Executable Tool Calling?

**When You Face:** An agent needs access to a library of internal capabilities.

| Option | Pros | Cons | Best When |
|---|---|---|---|
| Prompt-injected tool docs | Flexible, easy to evolve | Less reliable, weaker control | Tool library changes often |
| Structured tool calling | Strong control, easier auditing | More engineering, less flexible composition | Safety and precision are critical |
| Hybrid | Balance of both | Highest complexity | Mature systems with mixed needs |

**What AutoKaggle Chose:** Prompt-injected retrieved docs with code generation, despite shipping a schema registry.  
**Recommendation:** Use prompt retrieval as a fast path to usefulness, then migrate the highest-risk actions to structured tool execution.

### Decision 3: File Artifacts Or In-Memory State?

**When You Face:** A multi-step workflow that needs auditability and restart clues.

| Option | Pros | Cons | Best When |
|---|---|---|---|
| File artifacts | Easy to inspect, human-readable | Messy trees, weak transactions | Research harnesses and debugging-heavy systems |
| In-memory state only | Fast, simple runtime | Poor audit trail | Short-lived workflows |
| DB-backed run state | Durable, queryable | More infrastructure | Multi-user or long-running systems |

**What AutoKaggle Chose:** Heavy filesystem persistence of plans, histories, reports, errors, and outputs.  
**Recommendation:** Start with files if your main bottleneck is debugging. Move to DB-backed state when coordination, concurrency, or lifecycle management becomes the bigger problem.

### Decision 4: Fixed Sequential Progress Or Repeat-Until-Threshold?

**When You Face:** An autonomous workflow where some artifacts are “good enough” and others need repair.

| Option | Pros | Cons | Best When |
|---|---|---|---|
| Always advance | Simple, predictable | Accumulates bad outputs | Failure costs are low |
| Fixed retry count without scoring | Easy to implement | Blind to quality level | You only care about execution success |
| Threshold-gated repeat | Quality-aware, bounded | Needs scoring policy | You can define meaningful contracts and scores |

**What AutoKaggle Chose:** Repeat when average score is below 3 and iteration cap is not reached.  
**Recommendation:** Use threshold-gated repeats when downstream quality matters more than raw throughput.

---

## 5. Implementation Playbooks

### Playbook 1: Building A Phase State Machine For Open-Ended Work

**Goal:** Build a small orchestrator that turns an ambiguous task into explicit stages.  
**Estimated Effort:** 1-2 days for a first usable version  
**Prerequisites:** You know the stages, expected outputs, and basic failure conditions.

#### Step 1: Define The Phases And Their Contracts

Create a declarative map that names each phase, assigns the responsible roles, and lists required outputs and tests. AutoKaggle does this in `multi_agents/config.json`.

#### Step 2: Design A Minimal State Object

Your state object should answer: where are we, what artifacts do we already have, what tools/tests are valid here, and what evidence should survive a retry? AutoKaggle’s `State` object in `multi_agents/state.py:13` is a good reference.

#### Step 3: Implement A Small Orchestrator

The orchestrator should do only three things well: create the right actor, run the actor, and decide whether to repeat or advance. Avoid hiding the policy. `SOP.step()` and `SOP.update_state()` illustrate the right level of explicitness.

#### Step 4: Persist Enough Evidence

Write plans, reports, outputs, and errors to disk or durable storage. Do not keep everything only in RAM if you expect to debug the system later.

#### Verification

You know this playbook worked when you can inspect a failed run and answer: which phase failed, why it failed, what artifacts were present, and what would happen on a retry.

### Playbook 2: Building A Code Generation, Execution, And Repair Loop

**Goal:** Safely iterate on LLM-generated code without trusting the first successful execution.  
**Estimated Effort:** 2-4 days depending on the richness of the contract tests  
**Prerequisites:** Ability to execute generated code in a controlled environment.

#### Step 1: Separate Planning From Coding

Have one role or step define the intended work before the coding role starts. This narrows the space of likely implementations and gives you a stable artifact to critique.

#### Step 2: Wrap Generated Code In A Predictable Shell

AutoKaggle encloses generated code in a standard function wrapper and writes explicit script files (`developer.py:92`). This makes execution and inheritance easier.

#### Step 3: Capture Execution Artifacts

Always persist stdout, stderr, and the generated source. You need those artifacts for debugging and reviewer context.

#### Step 4: Add Contract Tests

Write tests that reflect domain correctness, not only Python correctness. AutoKaggle’s output file, missing-value, and schema checks in `multi_agents/tools/unit_test.py` are the right pattern.

#### Step 5: Split Runtime Errors From Contract Failures

Use different repair prompts for code that crashes and code that runs but violates a contract. AutoKaggle does this through two different debug paths.

#### Step 6: Cap Retries And Preserve Failure Memory

Bound the loop. Persist error history and reviewer suggestions so retries improve rather than simply repeat.

#### Verification

The loop is ready when the system can distinguish “program crashed,” “program ran but output is invalid,” and “program passed.”

### Playbook 3: Building Semantic Tool Retrieval For A Prompt-Based Agent

**Goal:** Expose a broad internal tool library without flooding every prompt.  
**Estimated Effort:** 1-2 days for a doc-based version  
**Prerequisites:** A tool library with stable names and some documentation.

#### Step 1: Write Concise Per-Tool Documentation

AutoKaggle stores tool docs as markdown chunks under `multi_agents/tools/ml_tools_doc`. Keep each tool description short, structured, and example-rich.

#### Step 2: Add A Phase Filter Before Retrieval

Do not search a single global pool if the workflow already tells you which tools are valid. Use config to narrow first, then embed and retrieve.

#### Step 3: Build A Small Vector Index

`Memory` plus ChromaDB in AutoKaggle is enough for this. You do not need a large retrieval stack to get the value.

#### Step 4: Inject Retrieved Docs Into The Prompt

Keep the retrieval output close to the relevant plan or task so the model can map intention to tools.

#### Step 5: Track Which Tools Were Exposed

Persist the subset of tools actually shown to the agent. This helps debugging and later migration to structured tool execution.

#### Verification

This playbook worked when prompt sizes shrink while generated code still uses appropriate helpers.

---

## 6. Architecture Templates

### Template 1: Single-Orchestrator Multi-Agent Workflow Harness

**Use Case:** You need one process to run a staged autonomous workflow over local artifacts.

**Blueprint:**

```text
CLI/API trigger
    |
    v
Orchestrator
    |
    +--> State store
    +--> Phase policy
    +--> Agent factory
            |
            +--> Planner
            +--> Worker/Developer
            +--> Reviewer
            +--> Summarizer
    |
    +--> Artifact storage
    +--> Contract tests
```

**Components:**

| Component | Responsibility | Interface |
|---|---|---|
| Orchestrator | Run phase loop and transition policy | `step(state) -> next_state` |
| State store | Hold current phase and memory | object or durable record |
| Agent factory | Instantiate specialized roles | `create_agent(name)` |
| Worker agent | Produce the main artifact | `action(state)` |
| Reviewer | Score and suggest | `review(artifact, context)` |
| Validator | Run contracts | `execute_tests(state)` |
| Artifact store | Persist outputs and logs | filesystem or object store |

**Assembly Instructions:**

1. Define phases and contracts.
2. Build the state object.
3. Implement the orchestrator.
4. Add one worker and one reviewer.
5. Only then add more specialized roles.

**Customization Points:**

- number of roles
- scoring policy
- retry cap
- state persistence method

### Template 2: Retrieval-Augmented Tool Catalog

**Use Case:** Your agent needs many internal utilities, but direct structured tool calling is not yet worth the engineering cost.

**Blueprint:**

```text
tool docs -> embeddings -> vector index
                         |
task + phase ----------> retrieval
                         |
                         v
                 selected tool docs
                         |
                         v
                   prompt context
                         |
                         v
                   generated program
```

**Components:**

| Component | Responsibility | Interface |
|---|---|---|
| Tool docs | Describe internal helpers | markdown/json |
| Embedder | Convert docs/query to vectors | `encode(text)` |
| Index | Store and search vectors | `query(vector)` |
| Policy filter | Narrow candidate tools by phase/task | config map |
| Prompt builder | Insert docs into task context | `build_prompt()` |

**Assembly Instructions:**

1. Standardize doc format per tool.
2. Create a phase/task-to-tool filter.
3. Build the vector index lazily.
4. Retrieve top matches at runtime.
5. Log the tools returned.

**Customization Points:**

- semantic-only vs hybrid symbolic/semantic retrieval
- doc chunk size
- top-k retrieval count
- path from retrieved docs to direct tool execution later

---

## 7. Engineering Practice Guide

### 7.1 Code Organization

Separate concerns by *workflow responsibility*, not only by technical layer. AutoKaggle’s split between `sop.py`, `state.py`, `agents/`, `tools/`, and `prompts/` works because each directory answers a different operational question.

### 7.2 Error Handling Strategy

Use a three-layer strategy:

1. edge retries for upstream API failures
2. execution capture for generated program failures
3. contract tests for semantic correctness

Then persist each failure mode separately so repair prompts can target the right problem.

### 7.3 Testing Approach

Do not choose between unit tests and workflow tests; use both. AutoKaggle’s helper-library pytest coverage and its phase-level output-contract tests are complementary. Copy that split.

### 7.4 Configuration Management

Workflow policy belongs in config when it is meant to change. Agent class implementations belong in code. Secret values do not belong in repository files. If you reuse this pattern, move credentials to environment variables or a secret manager from day one.

### 7.5 Performance Optimization

The useful optimization techniques in this repo are mostly context and search optimizations:

- preview data instead of loading all rows into prompts
- narrow tools by phase before retrieval
- use lighter models for reading/review roles and heavier models only where necessary
- enforce phase-specific timeouts
- truncate long outputs before summary prompts

---

## 8. Common Pitfalls & How This Repo Avoids Them

### Pitfall 1: Letting The Agent See Too Much Raw Data

**The Trap:** Dumping entire CSVs or whole libraries into prompts burns context and often worsens decisions.  
**The Repo's Solution:** `Agent._read_data()` and `_data_preview()` limit prompt-time data exposure to small samples and summarized previews.  
**Your Takeaway:** Build compact context intentionally. More raw input is not automatically better.

### Pitfall 2: Treating “Program Ran” As The Finish Line

**The Trap:** An artifact can be executable and still violate the real business or dataset contract.  
**The Repo's Solution:** `TestTool.execute_tests()` checks file creation, schema alignment, missingness, and submission validity before phase success.  
**Your Takeaway:** Put cheap, domain-aware postconditions after execution.

### Pitfall 3: Repeating Failures Without Learning

**The Trap:** Retry loops become expensive randomness when each attempt forgets why the last one failed.  
**The Repo's Solution:** `_gather_experience_with_suggestion()` injects prior results and reviewer feedback into retries.  
**Your Takeaway:** Preserve compact structured failure memory, not only raw chat history.

### Pitfall 4: Restarting Every Phase From Scratch

**The Trap:** Later stages redo earlier work, drift from established preprocessing, and waste tokens.  
**The Repo's Solution:** `Developer` inherits prior code and strips side effects before adding the next phase.  
**Your Takeaway:** Reuse earlier artifacts when the workflow is cumulative.

### Pitfall 5: Overloading The Agent With Every Possible Tool

**The Trap:** Too many tool choices make planning noisy and brittle.  
**The Repo's Solution:** Phase-level filtering plus semantic retrieval narrows the prompt to likely-relevant helpers.  
**Your Takeaway:** Shrink the action space before you ask the model to choose.

---

## 9. Skill-Building Exercises

### Exercise 1: Build A Two-Phase Cleaner (Beginner)

**Objective:** Practice state machines and artifact contracts.  
**Task:** Create a mini workflow with two phases: inspect a CSV, then produce a cleaned CSV. Add one reviewer step and at least three output checks.  
**Success Criteria:** The system can repeat the cleaning phase when the cleaned file still has missing values or duplicate columns.

### Exercise 2: Add A Critic-Gated Code Loop (Intermediate)

**Objective:** Practice separating authoring from judging.  
**Task:** Extend Exercise 1 so a coding agent writes the cleaner script, a validator runs it, and a reviewer decides whether to retry.  
**Success Criteria:** Execution errors and validation errors take different retry paths.

### Exercise 3: Replace Retrieved Tool Docs With Direct Tool Calling (Advanced)

**Objective:** Understand the trade-off between prompt flexibility and runtime control.  
**Task:** Keep AutoKaggle’s phase policy, but swap the prompt-injected tool docs for direct structured function calls on a subset of safe helpers.  
**Success Criteria:** You can compare failure modes, prompt size, and implementation complexity between the two approaches.

---

## 10. Quick Reference

### Key Patterns Summary

| Pattern | Use When | Key Mechanism |
|---|---|---|
| Phase-oriented workflow | Task has natural intermediate artifacts | explicit phases + transition policy |
| Critic-gated synthesis | Execution alone is not enough | runtime + contract tests + review |
| Semantic tool reduction | Tool library is large | phase filter + vector retrieval |
| Cumulative inheritance | Later stages refine earlier work | sanitize and reuse prior artifacts |
| Artifact-based summarization | Humans need traceability | summarize from outputs, not memory alone |

### Decision Cheat Sheet

| Decision Point | Default Choice | Switch When |
|---|---|---|
| Generalist vs specialized roles | Specialized roles | Task is short and homogeneous |
| Prompt docs vs tool calling | Prompt docs first | Safety/control needs dominate |
| Files vs in-memory state | Files first | Concurrency or lifecycle management grows |
| Fixed flow vs threshold-gated repeat | Threshold-gated repeat | Failure cost is negligible |

### Architecture Selection Guide

| Constraint | Recommended Architecture | Rationale |
|---|---|---|
| Research workflow, single operator | Single-process orchestrator | Fastest path to useful iteration |
| Many internal helpers, evolving API | Retrieval-augmented tool catalog | Keeps prompts focused without over-engineering |
| High-risk actions or strict compliance | Structured tool execution | Better control and auditability |
| Need for postmortems and explainability | Artifact-heavy workflow | Easier to inspect failures and decisions |

---

Read the companion report for the code-level evidence behind these patterns: `AutoKaggle-main-technical-anatomy-report.md`.