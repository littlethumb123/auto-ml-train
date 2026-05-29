# ARIS (Auto-claude-code-research-in-sleep): From Code to Craft — A Learning Guide

**Guide Type:** Conceptualized Engineering Knowledge & Actionable Patterns  
**Source Repository:** `/home/jupyter/Thinkubator/auto_train/references/Auto-claude-code-research-in-sleep-main`  
**Date:** April 20, 2026  
**Companion:** [Technical Anatomy Report](Auto-claude-code-research-in-sleep-main-technical-anatomy-report.md)

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

This guide extracts the engineering knowledge embedded in ARIS — a system for autonomous ML research — and transforms it into reusable patterns, decision frameworks, and step-by-step playbooks for building AI agent harnesses. Whether you're building autonomous coding agents, research pipelines, or multi-model coordination systems, the patterns here apply.

### Prerequisites

- Familiarity with large language model APIs (OpenAI, Anthropic)
- Basic understanding of agent architectures (tool use, prompt chaining)
- Experience with at least one agent framework or custom agent implementation
- Understanding of the research paper lifecycle is helpful but not required

### Learning Outcomes

After reading this guide, you will be able to:

- Design **cross-model adversarial review systems** that catch blind spots single models miss
- Implement **file-based artifact contracts** for multi-phase agent pipelines
- Build **configurable agent systems** with safety invariants that never flex
- Architect **context recovery mechanisms** that survive session crashes and context compaction
- Structure **integrity audit cascades** for high-stakes autonomous workflows
- Create **composable skill systems** where new capabilities are added without code changes
- Apply the **hard invariants + soft knobs** pattern to any configurable system

---

## 2. Conceptual Foundation

### 2.1 Problem Domain

Systems that automate **complex, multi-phase, high-stakes workflows using LLM agents** face three fundamental challenges:

1. **Blind spot accumulation**: A single model reviewing its own work reproduces its own errors. Over multiple iterations, blind spots compound rather than diminish. This is the "single-player local minimum" problem.

2. **State fragility**: LLM sessions have finite context windows. When context is compacted or a session crashes, all in-progress work can be lost unless state is explicitly persisted to external storage.

3. **Quality-vs-speed tension**: Users want both fast execution and safe output. Making all parameters configurable creates the risk that "fast mode" silently disables safety checks.

These challenges are not specific to ML research — they appear in any autonomous agent system doing complex, multi-step work where errors have real consequences.

### 2.2 Solution Strategy

ARIS addresses these challenges through a five-pillar strategy that can be generalized to any domain:

**Pillar 1: Task Decomposition** — Break complex workflows into phases with clear input/output contracts. Each phase is a coherent task that one agent can handle within one context window.

**Pillar 2: Cross-Model Checks** — Pair a fast executor with a rigorous reviewer from a different model family. Enforce reviewer independence at the protocol level (not just the prompt level).

**Pillar 3: Constraint Specification** — Separate configuration into hard invariants (never change, safety-critical) and soft knobs (scale freely). Budget modes only affect throughput, never quality.

**Pillar 4: State Persistence** — Write all state to versioned files on disk. Every artifact has a timestamped immutable copy and a fixed-name latest pointer. Recovery from any failure reads 3-5 files and resumes in under a minute.

**Pillar 5: Skill Composition** — Encode capabilities as self-contained instruction files (not code libraries). New capabilities require only a new file — no compilation, no registry, no framework changes.

### 2.3 Key Abstractions

**Artifact Contract**: A named file (e.g., `IDEA_REPORT.md`) with a defined schema, written by one skill and read by downstream skills. The contract specifies what fields must be present and what invariants must hold. This is the fundamental unit of inter-skill communication.

**Skill**: A self-contained Markdown document that defines a workflow — inputs, outputs, phases, constants, and tool permissions. The execution environment (Claude Code, Cursor, etc.) reads the skill and follows its instructions. Skills compose by chaining artifact contracts.

**Gate**: A checkpoint between workflow phases where execution pauses for validation (human approval, automated score threshold, or precondition check). Gates can be set to auto-proceed for fully autonomous operation.

**Hard Invariant**: A system property that must hold regardless of configuration. Invariants are constants in the architecture, not parameters in the configuration.

**Reviewer Independence**: The principle that a reviewer agent receives only raw artifact paths — never executor summaries, interpretations, or previous scores. Independence must be enforced by the tool interface, not by the prompt.

---

## 3. Pattern Catalog

### Pattern 1: Cross-Model Adversarial Review Loop

**Problem:** When an AI agent reviews its own output, it systematically overlooks the same categories of errors it made while generating the output. Self-review converges to local minima.

**Solution:** Pair two different models in an executor-reviewer loop. The executor generates artifacts; the reviewer (from a different model family) evaluates them independently. Enforce that the reviewer reads raw artifacts, not executor summaries. Loop until convergence (score threshold) or budget exhaustion (max rounds).

**Structure:**
```
┌─────────────────┐     artifacts     ┌─────────────────┐
│    EXECUTOR      │ ──────────────▶  │    REVIEWER      │
│  (Model A)       │                  │  (Model B)       │
│  - Generate      │  ◀──────────── │  - Score (1-10)   │
│  - Fix issues    │   action items   │  - Find weakness  │
│  - Iterate       │                  │  - Judge progress │
└─────────────────┘                  └─────────────────┘
         │                                    │
    Loop until:                          Each round:
    - Score ≥ threshold                  - Fresh context
    - Max rounds reached                 - No prior scores
    - Patience exhausted                 - No executor summaries
```

**How ARIS Implements It:**
- Executor: Claude Code (fast, creative, implements fixes)
- Reviewer: GPT-5.4 via Codex MCP (rigorous, critical, evaluates independently)
- Protocol: `mcp__codex__codex` for fresh threads, reviewer-independence.md enforces no summaries
- Convergence: Score ≥ 6/10 AND verdict "ready"/"almost", OR max 4 rounds, OR 3+ no-improvement rounds
- State persistence: REVIEW_STATE.json saves round/threadId/score for crash recovery

**When to Use:**
- Multi-step generation tasks where quality matters (research, documentation, code review)
- Any task where the generator has known blind spots
- Production systems where single-model quality is insufficient

**When NOT to Use:**
- Simple, single-step tasks (overhead doesn't justify the benefit)
- Latency-critical applications (cross-model calls add 30-60s per round)
- When both models share the same failure modes (e.g., both hallucinate the same facts)

**Variations:**
- **Same-model, different-context**: Use the same model but with completely isolated prompts/context
- **Multi-reviewer**: Use 3+ reviewers and take the consensus (more expensive, higher quality)
- **Human-in-the-loop**: Replace the automated reviewer with a human for the most critical rounds

---

### Pattern 2: File-Based Artifact Contracts

**Problem:** Multi-phase agent pipelines need a coordination mechanism. Databases add complexity; RPC adds coupling; in-memory state is fragile.

**Solution:** Skills communicate exclusively via named files on disk. Each artifact has a fixed name (for latest reference) and timestamped copies (for audit trail). Downstream skills read the fixed-name file. No central coordinator needed — the filesystem IS the coordination layer.

**Structure:**
```
Skill A writes:
  IDEA_REPORT_20260420_143022.md  ← timestamped (immutable)
  IDEA_REPORT.md                  ← fixed name (latest)

Skill B reads:
  IDEA_REPORT.md                  ← always gets latest
  (Can check timestamped versions for history)

File System = Message Bus + Database + Audit Log
```

**How ARIS Implements It:**
- ~15 named artifacts: IDEA_REPORT.md, EXPERIMENT_PLAN.md, AUTO_REVIEW.md, etc.
- Output versioning protocol (`skills/shared-references/output-versioning.md`): write timestamped, copy to fixed name
- MANIFEST.md: Append-only log of all artifact writes (timestamp, skill, file, description)
- Git-trackable: All artifacts are version-controlled alongside code

**When to Use:**
- Multi-phase workflows where phases run sequentially or with gaps between them
- Systems that need crash recovery (files survive process death)
- Human-debuggable systems (non-engineers need to inspect state)
- Multi-platform systems (files work everywhere, databases don't)

**When NOT to Use:**
- Real-time systems requiring sub-second coordination
- Systems with complex query patterns (graph traversals, aggregations)
- High-concurrency scenarios where file locking becomes a bottleneck

**Variations:**
- **JSON artifacts**: Use JSON instead of Markdown for machine-readable contracts
- **Git-based coordination**: Use git branches/tags as the coordination mechanism
- **Hybrid**: Files for primary state, SQLite for queryable indexes

---

### Pattern 3: Hard Invariants + Soft Knobs

**Problem:** Configurable systems need to support different usage modes (fast/cheap vs. thorough/expensive), but making everything configurable creates the risk that "budget mode" silently disables safety properties.

**Solution:** Classify all system parameters into two categories:
1. **Hard invariants**: Properties that must ALWAYS hold (safety, integrity, quality floors). These are constants in the architecture — not exposed as configuration.
2. **Soft knobs**: Properties that scale usage intensity (breadth, depth, iterations). These are freely configurable.

**Structure:**
```
┌─────────────────────────────────────────┐
│           HARD INVARIANTS               │
│  (NEVER change, regardless of mode)     │
│  • Reviewer quality = maximum           │
│  • Fraud detection = always on          │
│  • Citation verification = always on    │
│  • Independence protocol = enforced     │
└─────────────────────────────────────────┘
         ↑ Constants ↑

┌─────────────────────────────────────────┐
│           SOFT KNOBS                    │
│  (Scale freely per effort level)        │
│  lite(0.4x)  balanced(1x)  max(2.5x)   │
│  • Papers searched: 6-8 → 10-15 → 25   │
│  • Review rounds:   2   →  3-4  →  6   │
│  • Iterations:      1   →  3    →  5   │
└─────────────────────────────────────────┘
         ↑ Parameters ↑
```

**How ARIS Implements It:**
- Hard invariants defined in `skills/shared-references/effort-contract.md`
- Soft knobs controlled by `— effort: lite|balanced|max|beast` parameter
- Example hard invariant: "Codex reasoning_effort = xhigh" — never changes even at effort=lite
- Example soft knob: "Papers searched = 6-8 (lite) → 40-50 (beast)"

**When to Use:**
- Any system where some properties are safety-critical
- Configurable AI systems with budget-conscious users
- Systems where "fast mode" is common but quality must not degrade below a threshold

**When NOT to Use:**
- Systems where all parameters are equal in importance
- Prototypes where rapid iteration matters more than safety
- Single-use scripts where configuration doesn't apply

---

### Pattern 4: Layered Integrity Audit Cascade

**Problem:** Complex outputs (code, papers, experiments) can contain errors at multiple levels — code bugs, statistical errors, unsupported claims, fabricated citations. A single review pass catches some but not all.

**Solution:** Stack multiple audit layers, each with a fresh reviewer context and a specific focus. Each layer is independent — it doesn't see prior layers' findings. This prevents "satisficing" (accepting prior layers' judgment instead of auditing independently).

**Structure:**
```
Layer 1: CODE AUDIT ────── "Is the code correct?"
    ↓ (fresh reviewer)
Layer 2: RESULT AUDIT ──── "Are the results real?"
    ↓ (fresh reviewer)
Layer 3: CLAIM AUDIT ───── "Do results support claims?"
    ↓ (fresh reviewer)
Layer 4: CITATION AUDIT ── "Do cited papers exist?"
    ↓ (fresh reviewer)
Layer 5: PROOF AUDIT ───── "Are mathematical proofs valid?"
```

**How ARIS Implements It:**
- 6 distinct audit skills, each using a fresh MCP thread (no context carryover)
- Zero-context audit: Paper-claim-audit gives reviewer ONLY .tex files and raw result files — no summaries
- Specific fraud patterns checked at each layer (fake GT, score normalization, phantom results)

**When to Use:**
- High-stakes autonomous workflows (research, finance, legal, medical)
- Any system where errors compound across phases
- Systems where a single reviewer can't catch all error types

**When NOT to Use:**
- Low-stakes applications where approximate correctness is acceptable
- Cost-constrained scenarios (each layer = one reviewer API call)
- Real-time systems where multi-layer auditing adds too much latency

---

### Pattern 5: Context Recovery via State Files

**Problem:** LLM sessions have finite context windows. When context is compacted (old messages discarded) or a session crashes, the agent loses all progress unless state is externalized.

**Solution:** Persist all workflow state to disk using a layered file system. On session start (or recovery), read files in priority order to reconstruct full context in < 1 minute.

**Structure:**
```
Priority 1 (always read): Dashboard file
  └── 30-second orientation: stage, current task, next action

Priority 2 (read if applicable): Active artifact
  └── One-page focused context for current work

Priority 3 (read on recovery): State snapshots
  └── JSON with round counters, thread IDs, scores

Priority 4 (append-only): Discovery log
  └── Anomalies, decisions, root causes
```

**How ARIS Implements It:**
- CLAUDE.md Pipeline Status = Priority 1 (30-second orientation)
- research_contract.md = Priority 2 (active idea context)
- REVIEW_STATE.json = Priority 3 (auto-review-loop recovery)
- findings.md = Priority 4 (append-only discovery log)
- Claude Code hooks fire session-restore.sh on new session or compaction

**When to Use:**
- Any long-running agent workflow (>30 minutes)
- Systems running on platforms with context window limits
- Overnight autonomous operations

**When NOT to Use:**
- Short, single-turn interactions
- Systems where all state fits comfortably in one context window

---

### Pattern 6: Markdown-Based Skill System

**Problem:** Agent capability systems need to be extensible (new capabilities added easily), portable (work across platforms), and auditable (non-engineers can review them). Code-based plugin systems are extensible but not portable or auditable.

**Solution:** Encode each capability as a Markdown document with YAML frontmatter (metadata) and natural language instructions (workflow). The agent platform reads the document and follows the instructions. New capabilities = new Markdown files.

**Structure:**
```yaml
---
name: skill-name
description: "What this skill does; when to invoke."
argument-hint: [expected arguments]
allowed-tools: Bash(*), Read, Write, MCP
---

# Skill Title

## Constants
MAX_ROUNDS = 4

## Workflow

### Phase 1: [Name]
1. Read [input artifact]
2. Process with [specific instructions]
3. Write [output artifact]

### Phase 2: [Name]
...
```

**How ARIS Implements It:**
- 65+ SKILL.md files in `skills/` directory
- YAML frontmatter: name, description, allowed-tools, argument-hint
- Skills discovered by filesystem scan (no registry)
- Shared protocols in `skills/shared-references/` (read by all skills, modified by none)

**When to Use:**
- Multi-platform agent systems (the same skills need to work on different agent runtimes)
- Systems where non-engineers need to audit or customize agent behavior
- Rapidly evolving capability sets (adding a skill = adding a file)

**When NOT to Use:**
- Performance-critical systems (Markdown interpretation adds overhead)
- Systems requiring compile-time type checking of skill contracts
- Deeply nested skill composition (Markdown doesn't support type-safe composition)

---

## 4. Decision Frameworks

### Decision 1: Cross-Model Review vs. Self-Review

**When You Face:** Choosing whether to use the same model for both generation and review, or different models.

| Option | Pros | Cons | Best When |
|--------|------|------|-----------|
| Self-review (same model) | Simple, fast, cheap | Correlated blind spots, local minima | Low-stakes tasks, prototyping |
| Cross-model review | Genuine adversarial check, catches blind spots | 2x API cost, added latency, complexity | High-stakes output, production quality |
| Multi-reviewer (3+ models) | Highest quality, consensus-based | 3x+ cost, coordination complexity | Critical applications, research papers |

**What ARIS Chose:** Cross-model review (Claude executor + GPT-5.4 reviewer) as default, with optional multi-reviewer via alternative MCP backends.  
**Recommendation:** Start with cross-model review for any task where errors have real consequences. Self-review is acceptable only for drafts and prototypes.

### Decision 2: State Persistence Strategy

**When You Face:** Deciding how to persist agent workflow state for recovery.

| Option | Pros | Cons | Best When |
|--------|------|------|-----------|
| In-memory only | Simplest, fastest | Lost on crash/compaction | Short tasks (<10 min) |
| Database (SQLite/Postgres) | Queryable, ACID, scalable | Setup overhead, not human-readable | Complex queries, multi-user systems |
| Flat files (Markdown/JSON) | Human-readable, git-trackable, zero-setup | Not queryable, no ACID | Single-user agent workflows |
| Hybrid (files + index) | Best of both worlds | Complexity of maintaining both | Medium complexity systems |

**What ARIS Chose:** Flat files (Markdown + JSON), with SQLite only for the research-wiki knowledge graph.  
**Recommendation:** Start with flat files. Add a database index only when you need to query across artifacts (e.g., "show me all experiments that tested claim X").

### Decision 3: Skill Definition Format

**When You Face:** Choosing how to define agent capabilities/skills.

| Option | Pros | Cons | Best When |
|--------|------|------|-----------|
| Code (Python/TS functions) | Type-safe, testable, fast | Platform-specific, requires compilation | Single-platform systems |
| Markdown instructions | Portable, human-readable, fork-friendly | No type checking, no unit tests | Multi-platform, auditable systems |
| JSON/YAML configs | Machine-parseable, validated | Not flexible enough for complex workflows | Simple tool definitions |
| Hybrid (Markdown + code) | Best of both worlds | Complexity of two systems | Large-scale systems |

**What ARIS Chose:** Pure Markdown instructions with YAML frontmatter.  
**Recommendation:** Start with Markdown. When you find yourself writing the same complex logic in multiple skills, extract shared code into tool scripts that skills invoke via bash.

### Decision 4: Reviewer Independence Enforcement

**When You Face:** Deciding how to prevent the executor from biasing the reviewer.

| Option | Pros | Cons | Best When |
|--------|------|------|-----------|
| Prompt-level ("Don't pass summaries") | Simple to implement | Models can ignore prompts | Low-stakes scenarios |
| Tool-level (API only accepts file paths) | Enforced by interface | Requires custom tooling | High-stakes, production |
| Infrastructure-level (separate contexts) | Strongest isolation | Most complex | Critical applications |

**What ARIS Chose:** Tool-level enforcement via MCP — the reviewer tool only accepts file paths, not content. Plus protocol documentation (reviewer-independence.md) as a secondary layer.  
**Recommendation:** Always enforce at the tool level. Prompt-level enforcement is insufficient for production systems.

### Decision 5: Error Recovery Strategy

**When You Face:** Deciding how an agent system should handle failures.

| Option | Pros | Cons | Best When |
|--------|------|------|-----------|
| Fail-fast (crash, human fixes) | Simple, explicit | Requires human intervention | Development, debugging |
| Auto-retry (same approach, N times) | Handles transient failures | Can loop infinitely if bug is systematic | Network errors, API timeouts |
| Auto-diagnose + fix (parse error, adjust, retry) | Handles systematic failures | Complex, can make wrong fixes | OOM, import errors, config issues |
| Rollback + escalate (revert, report) | Safe, preserves good state | Loses progress on failed attempt | High-stakes production |

**What ARIS Chose:** Graduated strategy — auto-diagnose+fix (3 attempts), then rollback+escalate. Experiment-bridge tries to fix OOM/CUDA/import errors automatically, then marks FAILED and reports.  
**Recommendation:** Layer strategies: auto-retry for transient failures (network), auto-diagnose for systematic failures (OOM), rollback for persistent failures. Always cap retries to prevent infinite loops.

---

## 5. Implementation Playbooks

### Playbook 1: Building a Cross-Model Review System

**Goal:** Build a system where one model generates output and a different model reviews it, with enforced independence.

**Estimated Effort:** 2-4 hours for basic setup, 1-2 days for production quality  
**Prerequisites:** API access to two different LLM providers, basic agent framework

#### Step 1: Define the Review Protocol

Create a document specifying what the reviewer CAN and CANNOT receive:

```markdown
# Review Protocol

## Reviewer Input (ALLOWED)
- File paths to the generated artifacts
- Task description (what was the generator asked to do?)
- Structural hints (e.g., "output has 5 sections")
- Evaluation criteria (numbered, specific)

## Reviewer Input (FORBIDDEN)
- Generator's self-assessment or summary
- Previous review scores (each round is fresh)
- Generator's interpretation of results
- Leading questions ("Is this good?")
```

ARIS does this in `skills/shared-references/reviewer-independence.md`.

#### Step 2: Build the Reviewer Bridge

Create a tool interface that the executor calls to invoke the reviewer. The interface should only accept file paths, not content:

```python
def invoke_reviewer(file_paths: list[str], objective: str, criteria: list[str]) -> ReviewResult:
    """Invoke external reviewer. ONLY accepts file paths, never content summaries."""
    prompt = f"""Review the following files:
    {chr(10).join(file_paths)}
    
    Objective: {objective}
    
    Score 1-10 on each criterion:
    {chr(10).join(f'{i+1}. {c}' for i, c in enumerate(criteria))}
    
    For each weakness found, propose a specific fix."""
    
    return call_reviewer_api(prompt)
```

ARIS uses MCP servers (`mcp-servers/codex-review/`) as the bridge layer.

#### Step 3: Implement the Review Loop

```python
def review_loop(executor, reviewer, initial_artifact, max_rounds=4, score_threshold=6):
    artifact = initial_artifact
    state = {"round": 0, "scores": []}
    
    for round_num in range(1, max_rounds + 1):
        # Reviewer evaluates (fresh context each round)
        review = reviewer.invoke(
            file_paths=[artifact.path],
            objective="Evaluate quality and identify weaknesses"
        )
        
        state["round"] = round_num
        state["scores"].append(review.score)
        save_state(state)  # Crash recovery
        
        # Check stop conditions
        if review.score >= score_threshold:
            return artifact  # Success
        if len(state["scores"]) >= 3 and no_improvement(state["scores"][-3:]):
            return artifact  # Patience exhausted
        
        # Executor fixes weaknesses
        artifact = executor.fix(artifact, review.action_items)
    
    return artifact  # Budget exhausted
```

ARIS implements this in `skills/auto-review-loop/SKILL.md` with REVIEW_STATE.json for crash recovery.

#### Step 4: Add State Persistence

Save state after each round so the loop can resume after crashes:

```json
{
  "round": 2,
  "thread_id": "abc123",
  "last_score": 5.0,
  "last_verdict": "not ready",
  "timestamp": "2026-04-20T14:30:00Z"
}
```

On restart: read state file, check timestamp (<24h = resume, >24h = start fresh), continue from saved round.

#### Verification

Your review system is working correctly when:
- [ ] Reviewer never sees executor's self-assessment
- [ ] Each round uses a fresh context (no score history leakage)
- [ ] Scores show monotonic improvement (3→5→6→7) over rounds
- [ ] System survives a crash mid-review and resumes correctly
- [ ] System stops at budget limit (max rounds) even if score is low

---

### Playbook 2: Building a File-Based Coordination System

**Goal:** Build a multi-phase agent pipeline where phases communicate via versioned files.

**Estimated Effort:** 1-2 hours for basic setup  
**Prerequisites:** A multi-phase workflow to coordinate

#### Step 1: Define Artifact Contracts

For each phase transition, define what file is written and what schema it follows:

```
Phase 1 (Discovery) → Phase 2 (Implementation)
  Artifact: PLAN.md
  Required sections: ## Objective, ## Approach, ## Expected Outputs
  Written by: discovery skill
  Read by: implementation skill

Phase 2 (Implementation) → Phase 3 (Review)
  Artifact: RESULTS.json
  Required fields: {"metrics": {...}, "config": {...}, "timestamp": "..."}
  Written by: implementation skill
  Read by: review skill
```

#### Step 2: Implement Versioned Writing

```python
def write_artifact(name: str, content: str):
    """Write timestamped + fixed-name artifact."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_path = f"{name}_{timestamp}.md"
    fixed_path = f"{name}.md"
    
    # Write timestamped (immutable archive)
    with open(timestamped_path, 'w') as f:
        f.write(content)
    
    # Update fixed-name (latest pointer)
    shutil.copy(timestamped_path, fixed_path)
    
    # Log to manifest
    with open("MANIFEST.md", 'a') as f:
        f.write(f"| {timestamp} | {name} | {fixed_path} |\n")
```

#### Step 3: Implement Artifact Reading

```python
def read_artifact(name: str) -> str:
    """Read the latest version of a named artifact."""
    fixed_path = f"{name}.md"
    if not os.path.exists(fixed_path):
        raise FileNotFoundError(f"Artifact {name} not found. "
                                f"Was the upstream phase completed?")
    with open(fixed_path) as f:
        return f.read()
```

#### Verification

- [ ] Each phase writes both timestamped and fixed-name copies
- [ ] Downstream phases read the fixed-name copy
- [ ] MANIFEST.md contains a complete audit trail
- [ ] Deleting the fixed-name copy and re-copying a timestamped version recovers state
- [ ] Git history shows all artifact versions

---

### Playbook 3: Building a Configurable Agent with Safety Invariants

**Goal:** Create an agent configuration system where safety properties cannot be disabled.

**Estimated Effort:** 1-2 hours  
**Prerequisites:** An agent with configurable parameters

#### Step 1: Classify Parameters

```python
# HARD INVARIANTS — never change, never expose as config
INVARIANTS = {
    "reviewer_reasoning_effort": "maximum",  # Quality floor
    "citation_verification": True,           # Anti-hallucination
    "reviewer_independence": True,           # Bias prevention
    "audit_enabled": True,                   # Integrity check
}

# SOFT KNOBS — freely configurable
EFFORT_LEVELS = {
    "lite":     {"papers": 8,  "rounds": 2, "iterations": 1},
    "balanced": {"papers": 15, "rounds": 4, "iterations": 3},
    "max":      {"papers": 25, "rounds": 6, "iterations": 5},
    "beast":    {"papers": 50, "rounds": 8, "iterations": 10},
}
```

#### Step 2: Build the Configuration Resolver

```python
def resolve_config(user_params: dict) -> dict:
    """Merge user params with invariants. Invariants always win."""
    effort = user_params.get("effort", "balanced")
    config = {**EFFORT_LEVELS[effort]}
    
    # Apply user overrides to soft knobs
    for key in ["papers", "rounds", "iterations"]:
        if key in user_params:
            config[key] = user_params[key]
    
    # Apply invariants (CANNOT be overridden)
    config.update(INVARIANTS)
    
    return config
```

#### Verification

- [ ] Calling `resolve_config({"effort": "lite", "reviewer_independence": False})` still has `reviewer_independence: True`
- [ ] All effort levels produce different throughput but identical safety properties
- [ ] Adding a new invariant requires a code change (not a config change)

---

## 6. Architecture Templates

### Template 1: Multi-Phase Agent Pipeline with Review Gates

**Use Case:** Any autonomous workflow that proceeds through phases with quality checkpoints.

**Blueprint:**
```
┌──────────┐     artifact_1     ┌──────────┐     artifact_2     ┌──────────┐
│  Phase 1  │ ────────────────▶ │  Phase 2  │ ────────────────▶ │  Phase 3  │
│ (Generate)│                   │ (Execute) │                   │ (Polish)  │
└──────────┘                   └──────────┘                   └──────────┘
      │                              │                              │
      ▼                              ▼                              ▼
  🚦 Gate 1                     🚦 Gate 2                     🚦 Gate 3
  (Human or auto)               (Score threshold)             (Audit cascade)
```

**Components:**

| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| Phase skill | Execute one coherent task | Read input artifact, write output artifact |
| Gate | Validate phase output before proceeding | Check score/condition, pause if threshold not met |
| Artifact | Transfer state between phases | Named file with schema, timestamped versions |
| Recovery | Resume from any phase after crash | Read state files, reconstruct context |
| Orchestrator | Chain phases and gates | Invoke skills in sequence, pass parameters |

**Assembly Instructions:**
1. Define phases and their input/output artifacts
2. Define gates and their pass/fail criteria
3. Implement each phase as a standalone skill
4. Build the orchestrator that chains phases and gates
5. Add state persistence (state files + dashboard)
6. Add recovery logic (read state → resume from last completed phase)

**Customization Points:**
- Number and nature of phases (discovery, execution, review, delivery)
- Gate criteria (score threshold, human approval, automated checks)
- Whether gates can be bypassed (AUTO_PROCEED for fully autonomous)
- Recovery granularity (per-phase vs. per-step)

---

### Template 2: Cross-Model Adversarial System

**Use Case:** Systems requiring high-assurance output where single-model review is insufficient.

**Blueprint:**
```
                    ┌─────────────────────┐
                    │    ORCHESTRATOR      │
                    │  (manages rounds)    │
                    └─────┬───────┬───────┘
                          │       │
              ┌───────────▼─┐   ┌─▼───────────┐
              │   EXECUTOR   │   │   REVIEWER   │
              │  (Model A)   │   │  (Model B)   │
              │              │   │              │
              │ Tools:       │   │ Tools:       │
              │ - File R/W   │   │ - File Read  │
              │ - Bash       │   │ - Score      │
              │ - Edit       │   │ - Verdict    │
              └──────────────┘   └──────────────┘
                    │                   │
                    ▼                   ▼
              ┌─────────────────────────────┐
              │    SHARED ARTIFACTS (disk)   │
              │  - Generated output         │
              │  - Review scores            │
              │  - State snapshots          │
              └─────────────────────────────┘
```

**Components:**

| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| Orchestrator | Manage review rounds, check stop conditions | Invoke executor/reviewer, read scores, persist state |
| Executor | Generate and refine artifacts | Read reviews, implement fixes, write updated artifacts |
| Reviewer | Score and critique artifacts | Read raw files (never summaries), produce structured feedback |
| Shared Artifacts | Common ground between executor and reviewer | Files on disk, versioned, human-readable |
| Review Bridge | Isolate reviewer context from executor | Accept only file paths, enforce independence protocol |

**Assembly Instructions:**
1. Choose executor and reviewer models (different families recommended)
2. Build the review bridge (MCP server or API wrapper)
3. Define the review protocol (what reviewer can/cannot see)
4. Implement the review loop with stop conditions
5. Add state persistence for crash recovery
6. Define difficulty levels (standard, hard, adversarial)

---

## 7. Engineering Practice Guide

### 7.1 Code Organization

Principles derived from ARIS's approach:

1. **One capability = one directory**: Each skill/capability gets its own directory with a self-contained definition file. Don't put multiple capabilities in one file.
2. **Shared protocols in a dedicated directory**: Cross-cutting rules (reviewer independence, output versioning) go in a shared-references directory, read by all skills, modified by none.
3. **Templates separate from logic**: Input/output format templates go in a templates directory. Skills reference templates; they don't embed format definitions inline.
4. **Tools are utilities, not skills**: Executable scripts that skills invoke (fetchers, renderers, monitors) go in a tools directory, separate from the skills that use them.

### 7.2 Error Handling Strategy

Reusable framework based on ARIS's patterns:

```
Transient errors (network, API timeout):
  → Auto-retry 3x with exponential backoff
  → On exhaustion: switch to fallback provider
  → Log: "retried N times, switched to fallback"

Systematic errors (OOM, import error, configuration):
  → Parse error message
  → Apply diagnostic fix (reduce batch size, install package, fix config)
  → Retry with fix applied
  → On exhaustion (3 attempts): mark FAILED, log details, continue pipeline

Catastrophic errors (data corruption, infinite loop, security violation):
  → STOP immediately
  → Rollback to last known good state
  → Alert human
  → Never auto-retry

Scoring this:
  → Transient = recoverable automatically (minutes)
  → Systematic = recoverable with diagnosis (minutes to hours)
  → Catastrophic = requires human intervention (stop pipeline)
```

### 7.3 Testing Approach

Testing strategy for Markdown-based agent systems:

1. **Infrastructure tests** (traditional unit tests): Test API wrappers, file parsers, MCP servers with mocked dependencies
2. **Contract validation** (schema checks): Validate that artifact files conform to their expected schema after each phase
3. **Cross-model audit** (runtime quality): Use the adversarial review system itself as the primary quality gate (ARIS's approach)
4. **Regression detection** (score monitoring): Track review scores over time; flag if average score decreases after harness changes
5. **Recovery tests** (chaos engineering): Periodically kill sessions mid-workflow and verify recovery from state files

### 7.4 Configuration Management

Layered configuration with clear precedence:

```
Priority 1 (highest): Skill-level parameters (— effort: max)
Priority 2: Dashboard file (CLAUDE.md constraints)
Priority 3: Environment file (.env)
Priority 4 (lowest): Shell environment variables

Zero-config mode: If no .env exists, fall back to shell env vars.
If no shell vars, use defaults and disable optional features.
```

### 7.5 Performance Optimization

Techniques with generalized applicability:

1. **Skip redundant phases**: If artifact already exists and is fresh, skip the phase that produces it
2. **Parallel execution**: Run independent sub-tasks in parallel (e.g., multiple literature searches)
3. **Wave scheduling**: For dependent computations, batch independent jobs into waves; run each wave in parallel
4. **Early stopping**: In review loops, stop early when score plateaus (patience mechanism) rather than always running max rounds
5. **Effort scaling**: Use lite mode for exploration, balanced for development, max for production — don't run everything at maximum

---

## 8. Common Pitfalls & How This Repo Avoids Them

### Pitfall 1: Self-Review Blind Spots

**The Trap:** Using the same model to generate and review output feels efficient, but the model systematically overlooks the same categories of errors it introduced. Over multiple iterations, confidence increases but quality doesn't.

**The Repo's Solution:** Cross-model adversarial review with enforced independence. The reviewer (GPT-5.4) reads raw artifacts, not executor summaries (`skills/shared-references/reviewer-independence.md`). Each review round uses a fresh context thread.

**Your Takeaway:** Never use self-review for high-stakes output. If you can't afford a second model, at minimum use a separate prompt/context with no access to the generation history.

### Pitfall 2: Configuration-Induced Safety Degradation

**The Trap:** Making all parameters configurable means power users will minimize everything for speed, including safety-critical properties. "Just set everything to minimum and run overnight."

**The Repo's Solution:** Hard invariants + soft knobs (`skills/shared-references/effort-contract.md`). Reviewer quality, fraud detection, and citation verification are constants — not parameters. Setting `effort: lite` reduces breadth but never disables safety.

**Your Takeaway:** Before building your configuration system, identify 5-10 properties that must ALWAYS hold. Make these constants in your code, not entries in your config file.

### Pitfall 3: Context Window Amnesia

**The Trap:** Agent sessions that exceed their context window lose all prior state. The agent starts "fresh" but doesn't know what work has been done, leading to repeated effort or contradictory actions.

**The Repo's Solution:** Multi-layered state persistence with a 30-second orientation file (CLAUDE.md Pipeline Status). Session recovery hooks automatically inject state on new sessions. Recovery time: < 1 minute.

**Your Takeaway:** Design for context compaction from day one. Every agent workflow should write a dashboard file that answers: "What phase are we in? What was the last action? What should happen next?"

### Pitfall 4: Fragile Inter-Skill Communication

**The Trap:** Skills communicating via in-memory state, function returns, or ephemeral messages lose data when any component fails. The coordination layer becomes the single point of failure.

**The Repo's Solution:** File-based artifact contracts. Skills write versioned Markdown/JSON files to disk. Downstream skills read fixed-name files. The filesystem is the coordination layer — it survives process death, context compaction, and platform changes.

**Your Takeaway:** For multi-phase agent workflows, use files as the communication channel between phases. Files are the most reliable, debuggable, and portable coordination mechanism.

### Pitfall 5: Monolithic Agent Design

**The Trap:** Building one big agent prompt that handles the entire workflow. As complexity grows, the prompt becomes unmanageable, untestable, and impossible to extend.

**The Repo's Solution:** 65+ composable skills, each a standalone Markdown file. Adding a new capability = creating a new file. Orchestrator skills chain sub-skills via artifact contracts. No skill is more than a few hundred lines of Markdown.

**Your Takeaway:** Decompose agent capabilities into small, self-contained skills. Each skill should do one thing well and communicate via artifact contracts, not in-memory state.

### Pitfall 6: Trusting Citations

**The Trap:** LLMs hallucinate citations with realistic-looking authors, titles, and years. Papers that don't exist get cited; papers that exist get misattributed.

**The Repo's Solution:** Mandatory DBLP/CrossRef verification for every citation (`skills/shared-references/citation-discipline.md`). The citation audit skill verifies each `\cite{}` entry exists via web API call. This is a hard invariant — never bypassed even at minimum effort.

**Your Takeaway:** In any system that produces references or citations, always verify against an authoritative source. Never trust LLM-generated bibliographic data without confirmation.

---

## 9. Skill-Building Exercises

### Exercise 1: Build a Minimal Review Loop (Beginner)

**Objective:** Practice implementing the adversarial review pattern with two model calls.

**Task:** Build a Python script that:
1. Uses GPT-4o (or any model) to write a 200-word summary of a given topic
2. Uses Claude (or a different model) to score the summary 1-10 and list weaknesses
3. If score < 7, send weaknesses back to the writer for revision
4. Loop until score ≥ 7 or 3 rounds elapsed
5. Print the final summary and score progression

**Success Criteria:**
- Scores improve monotonically (most of the time)
- Reviewer never sees the writer's self-assessment
- System handles API errors gracefully (retry once, then fail)

### Exercise 2: File-Based Artifact Pipeline (Intermediate)

**Objective:** Practice building a multi-phase pipeline with artifact contracts.

**Task:** Build a 3-phase agent pipeline:
- Phase 1 (Research): Search for information on a topic, write RESEARCH.md
- Phase 2 (Analysis): Read RESEARCH.md, analyze patterns, write ANALYSIS.md
- Phase 3 (Summary): Read ANALYSIS.md, write SUMMARY.md

Requirements:
- Each phase reads only the artifact from the previous phase (no shared state)
- Add versioning (timestamped copies + fixed-name)
- Add a MANIFEST.md that tracks all artifact writes
- Add recovery: if the script crashes after Phase 2, rerunning skips Phase 1 and Phase 2

**Success Criteria:**
- Phases are independent (each can run standalone given its input artifact)
- Crash recovery works (kill mid-run, restart, resume from last completed phase)
- MANIFEST.md contains complete audit trail

### Exercise 3: Hard Invariants Configuration System (Advanced)

**Objective:** Practice separating invariants from knobs in a real system.

**Task:** Take an existing configurable system you've built and:
1. List all configurable parameters
2. Classify each as HARD INVARIANT or SOFT KNOB (justify each classification)
3. Refactor the configuration system so invariants are constants, not config entries
4. Build 3 effort levels (minimal, standard, thorough) that only affect soft knobs
5. Write a test that proves no effort level can disable any invariant

**Success Criteria:**
- Attempting to override an invariant via config silently preserves the invariant
- Each effort level produces measurably different throughput
- All effort levels produce identical safety behavior
- Test suite validates invariant immutability

---

## 10. Quick Reference

### Key Patterns Summary

| Pattern | Use When | Key Mechanism |
|---------|----------|--------------|
| Cross-Model Adversarial Review | Output quality matters, single model insufficient | Two models, enforced independence, score threshold |
| File-Based Artifact Contracts | Multi-phase pipeline, crash recovery needed | Timestamped + fixed-name files, MANIFEST logging |
| Hard Invariants + Soft Knobs | Configurable system with safety requirements | Constants for safety, parameters for throughput |
| Layered Audit Cascade | High-stakes output, errors compound across layers | Fresh reviewer per layer, zero context between layers |
| Context Recovery | Long-running workflows, context window limits | Dashboard file + state snapshots + recovery hooks |
| Markdown Skill System | Multi-platform, extensible, auditable agent capabilities | YAML frontmatter + natural language instructions |

### Decision Cheat Sheet

| Decision Point | Default Choice | Switch When |
|---------------|---------------|-------------|
| Review strategy | Cross-model | Budget-constrained → self-review; critical → multi-reviewer |
| State persistence | Flat files | Complex queries needed → add database index |
| Skill format | Markdown | Type safety critical → code-based plugins |
| Independence enforcement | Tool-level | Prototyping → prompt-level; critical → infrastructure-level |
| Error recovery | Auto-diagnose + retry | Low-stakes → fail-fast; high-stakes → rollback + escalate |

### Architecture Selection Guide

| Constraint | Recommended Architecture | Rationale |
|-----------|-------------------------|-----------|
| Multi-platform support needed | Markdown skills + file contracts | Platform-agnostic by design |
| High-assurance output required | Cross-model review + audit cascade | Catches errors single models miss |
| Overnight autonomous operation | File-based state + context recovery | Survives crashes and compaction |
| Rapid capability expansion | Skill-per-directory + shared protocols | New capability = new file |
| Budget-constrained operation | Self-review + effort knobs | Scales cost without disabling safety |
| Compliance/audit requirements | Versioned artifacts + MANIFEST + review tracing | Full audit trail on disk |
