# Harness Engineering: A Comprehensive Literature Review

## Mechanisms, Principles, Practices, and Future Directions for Agentic Software Development

---

**Date:** March 12, 2026
**Scope:** Synthesis of 7 primary sources and 20+ supplementary expert perspectives
**Purpose:** Inform the design of guidelines and instructions for agentic systems practicing harness engineering

---

## Table of Contents

1. [Introduction and Terminology](#1-introduction-and-terminology)
2. [Origins and Evolution of the Concept](#2-origins-and-evolution-of-the-concept)
3. [Primary Source Analysis](#3-primary-source-analysis)
4. [Converging Principles and Mechanisms](#4-converging-principles-and-mechanisms)
5. [The Four Pillars of Harness Engineering](#5-the-four-pillars-of-harness-engineering)
6. [Experimentation Details and Empirical Evidence](#6-experimentation-details-and-empirical-evidence)
7. [Areas of Agreement](#7-areas-of-agreement)
8. [Points of Debate and Divergence](#8-points-of-debate-and-divergence)
9. [Relationship to Adjacent Disciplines](#9-relationship-to-adjacent-disciplines)
10. [Expert and Practitioner Perspectives](#10-expert-and-practitioner-perspectives)
11. [Failure Modes and Mitigations](#11-failure-modes-and-mitigations)
12. [Practical Guidelines for Agentic Systems](#12-practical-guidelines-for-agentic-systems)
13. [Open Problems and Future Directions](#13-open-problems-and-future-directions)
14. [Conclusion](#14-conclusion)
15. [References](#15-references)

---

## 1. Introduction and Terminology

### 1.1 Definition

**Harness engineering** is the discipline of designing the infrastructure, constraints, feedback loops, and environmental scaffolding that surrounds AI coding agents to make them reliable, productive, and maintainable at scale. The term distinguishes itself from prompt engineering (crafting individual instructions) and context engineering (curating what the model sees) by encompassing the *entire operational environment* in which agents execute — including deterministic enforcement mechanisms, testing pipelines, documentation systems, architectural constraints, and agent lifecycle management.

Vivek Trivedy (LangChain) provides the foundational definition: an agent equals a model plus a harness, where the harness is "every piece of code, configuration, and execution logic that isn't the model itself" (Trivedy, 2026). Mitchell Hashimoto frames it as a practice: "anytime you find an agent makes a mistake, you take the time to engineer a solution such that the agent never makes that mistake again" (Hashimoto, 2026).

### 1.2 The Central Thesis

Across all primary and supplementary sources reviewed, a single thesis emerges with remarkable consistency: **the bottleneck to reliable agentic software development is infrastructure, not model intelligence**. Past a capability threshold, improving the harness yields better returns than improving the model.

This thesis is supported by converging evidence from OpenAI (Lopopolo, 2026), Anthropic (Young, 2025; Carlini, 2026), LangChain (2026), Vercel (2025), Martin Fowler's Thoughtworks series (Böckeler, 2026), and multiple independent practitioners.

### 1.3 Scope and Method

This review synthesizes seven primary sources:

1. **OpenAI** — "Harness engineering: leveraging Codex in an agent-first world" (Lopopolo, Feb 2026)
2. **Anthropic** — "Effective harnesses for long-running agents" (Young, Nov 2025)
3. **Anthropic** — "Building a C compiler with a team of parallel Claudes" (Carlini, Feb 2026)
4. **Martin Fowler / Thoughtworks** — "Harness Engineering" (Böckeler, Feb 2026)
5. **Artificial Ignorance** — "The Emerging Harness Engineering Playbook" (Guo, Feb 2026)
6. **Alex Lavaee** — "How to Harness Coding Agents with the Right Infrastructure" (Lavaee, 2026)
7. **LangChain** — "Improving Deep Agents with harness engineering" (LangChain Engineering, Feb 2026)

These are supplemented by 20+ additional sources from practitioners including Mitchell Hashimoto, Geoffrey Huntley, Dex Horthy, Boris Tane, Greg Brockman, Peter Steinberger, Addy Osmani, Chad Fowler, Evangelos Pappas, Vitthal Mirji, Pawel Jozefiak, and academic work by Vasilopoulos (2026).

---

## 2. Origins and Evolution of the Concept

### 2.1 Terminological Lineage

The term "harness engineering" crystallized rapidly in early 2026, though its constituent practices predate the label:

- **Mitchell Hashimoto** (creator of Terraform and Ghostty) described the practice in his AI adoption journey series, articulating the principle of systematically preventing agent mistakes through environmental fixes rather than prompt tweaks (Hashimoto, 2026). His six-step adoption ladder culminates in "Engineer the Harness" as step five.

- **Vivek Trivedy** (LangChain) formalized the concept structurally in "The Anatomy of an Agent Harness," defining harness components: hooks/middleware, orchestration logic, bundled infrastructure, tools, and system prompts (Trivedy, 2026). (Lavaee (2026) credits Trivedy with coining the term; Guo (2026) attributes it to Hashimoto's usage. The precise origin is ambiguous, but the term gained currency through multiple independent contributors in early 2026.)

- **OpenAI** adopted the term for their February 2026 engineering blog post, giving it institutional weight when Ryan Lopopolo described their five-month experiment building a million-line product with zero manually-written code (Lopopolo, 2026).

- **Böckeler** (Thoughtworks/Martin Fowler) noted the term may have been "an afterthought inspired by Mitchell Hashimoto's recent blog post" in OpenAI's case, but endorsed it: "I like 'harness' as a word to describe the tooling and practices we can use to keep AI agents in check" (Böckeler, 2026).

### 2.2 Precursor Concepts

Several precursor practices informed harness engineering:

- **Geoffrey Huntley's Ralph Wiggum Loop** (2025): A bash-based autonomous agent loop (`while :; do cat PROMPT.md | claude-code; done`) that introduced the concepts of fresh context per iteration and backpressure — bidirectional constraints (upstream steering via patterns, downstream gates via tests and linters) that keep agents on track (Huntley, 2025–2026).

- **Anthropic's initializer/coding agent pattern** (Young, Nov 2025): The first documented two-phase harness for long-running agents, establishing the pattern of separate setup and execution prompts with structured progress artifacts.

- **AGENTS.md convention**: An open standard (stewarded by the Agentic AI Foundation under the Linux Foundation) adopted by 60,000+ GitHub repositories, providing a standardized format for agent-readable project instructions (agents.md, 2025–2026).

### 2.3 Timeline of Convergence

| Date | Event | Contributor |
|------|-------|-------------|
| 2025 | Ralph Wiggum Loop introduced | Geoffrey Huntley |
| Nov 2025 | "Effective harnesses for long-running agents" published | Anthropic (Young) |
| Late 2025 | AGENTS.md reaches 60,000+ repos | Community / Linux Foundation |
| Jan 2026 | Hashimoto publishes AI adoption journey with "engineer the harness" | Mitchell Hashimoto |
| Feb 2026 | OpenAI publishes "Harness engineering" | OpenAI (Lopopolo) |
| Feb 2026 | Carlini publishes parallel Claude compiler experiment | Anthropic (Carlini) |
| Feb 2026 | Böckeler publishes Thoughtworks analysis | Thoughtworks (Böckeler) |
| Feb 2026 | Guo publishes "Emerging Harness Engineering Playbook" | Charlie Guo |
| Feb 2026 | LangChain publishes Terminal Bench results | LangChain |
| Feb 2026 | Vasilopoulos publishes "Codified Context" paper | Vasilopoulos (arXiv) |
| Feb 2026 | Lavaee publishes infrastructure synthesis | Alex Lavaee |
| Feb 2026 | Trivedy publishes "Anatomy of an Agent Harness" | LangChain (Trivedy) |

---

## 3. Primary Source Analysis

### 3.1 OpenAI: "Harness Engineering" (Lopopolo, Feb 2026)

**Context:** A team of three engineers (later seven) built and shipped an internal beta product with zero manually-written code over five months, producing approximately one million lines of code across ~1,500 merged pull requests.

**Key contributions:**

1. **Repository knowledge as system of record.** OpenAI discovered that a monolithic AGENTS.md fails at scale: "It rots instantly. A monolithic manual turns into a graveyard of stale rules" (Lopopolo, 2026). Their solution: treat AGENTS.md (~100 lines) as a table of contents pointing to a structured `docs/` directory containing design docs, execution plans, product specs, and reference materials.

2. **Progressive disclosure.** Agents start with a small, stable entry point and are taught where to look next, rather than being overwhelmed upfront. This prevents context window pollution while maintaining access to deep knowledge.

3. **Mechanical enforcement of architecture.** Each business domain follows a fixed layered structure (Types → Config → Repo → Service → Runtime → UI) with dependency directions enforced by custom linters and structural tests. Cross-cutting concerns enter through a single explicit interface (Providers).

4. **Custom linter error messages as remediation instructions.** When an agent violates a constraint, the error message tells the agent how to fix it — "the tooling teaches the agent while it works" (Guo, 2026, summarizing OpenAI).

5. **Entropy and garbage collection.** The team initially spent 20% of their time ("every Friday") cleaning up "AI slop." They replaced this with recurring background agents that scan for deviations, update quality grades, and open refactoring pull requests — most reviewable in under a minute and auto-mergeable.

6. **Agent-legible environments.** The application was made bootable per git worktree so Codex could launch and drive instances per change. Chrome DevTools Protocol was wired into the agent runtime. Observability tooling (logs, metrics, traces) was exposed via local stacks ephemeral to each worktree.

**Throughput data:** 3.5 PRs per engineer per day, with throughput *increasing* as the team grew from three to seven engineers.

### 3.2 Anthropic: "Effective Harnesses for Long-Running Agents" (Young, Nov 2025)

**Context:** Anthropic's engineering team addressed the challenge of agents working across multiple context windows, where each new session begins with no memory of prior work.

**Key contributions:**

1. **Two-phase agent architecture.** An *initializer agent* sets up the environment on first run (writing `init.sh`, `claude-progress.txt`, creating initial git commits), and a *coding agent* makes incremental progress in each subsequent session while leaving structured artifacts for the next.

2. **Failure mode taxonomy.** Four documented failure modes with corresponding solutions:
   - Agent attempts to one-shot the entire project → Feature list file with granular feature descriptions
   - Agent leaves environment in buggy/undocumented state → Git commits with descriptive messages + progress file updates
   - Agent marks features as complete prematurely → Self-verification with browser automation before marking "passing"
   - Agent spends time figuring out how to run the app → `init.sh` script for reproducible environment setup

3. **JSON over Markdown for structured state.** The team found that "the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files" (Young, 2025) when tracking feature completion status.

4. **Browser automation for end-to-end verification.** Providing Claude with Puppeteer MCP "dramatically improved performance, as the agent was able to identify and fix bugs that weren't obvious from the code alone" (Young, 2025).

5. **Session bootstrapping protocol.** Every coding agent starts by: (1) running `pwd` to orient itself, (2) reading git logs and progress files to understand recent work, (3) reading the feature list and choosing the highest-priority incomplete feature. The agent then starts the dev server and runs a basic end-to-end test before implementing anything new. (The exact ordering of these initial steps varied in Anthropic's experiments, but the principle of orientation before action was consistent.)

### 3.3 Anthropic: "Building a C Compiler" (Carlini, Feb 2026)

**Context:** Nicholas Carlini tasked 16 parallel Claude Opus 4.6 agents with building a Rust-based C compiler from scratch, producing 100,000 lines of code across ~2,000 Claude Code sessions at a cost of ~$20,000.

**Key contributions:**

1. **Bare-bones parallel agent coordination.** Agents coordinate through a shared git repository with file-based task locks (`current_tasks/`). No orchestrator agent. No message-passing. Git's synchronization forces the second agent to pick a different task when two claim the same one.

2. **Harness designed for LLM constraints:**
   - *Context window pollution:* Test output minimized; errors logged with `ERROR: [reason]` on single lines for grep-ability; aggregate statistics pre-computed.
   - *Time blindness:* Agents "can't tell time and, left alone, will happily spend hours running tests" (Carlini, 2026). The harness prints progress infrequently and includes a `--fast` flag for deterministic per-agent random test subsampling (1–10%), ensuring collective coverage without per-agent exhaustion.

3. **Oracle-based parallelization.** When all 16 agents converged on the same bug (compiling the Linux kernel), Carlini used GCC as an oracle — randomly compiling most files with GCC, leaving only a subset for Claude's compiler. This allowed each agent to work on different files in parallel, then further refined via delta debugging.

4. **Agent specialization.** Beyond core compiler work, dedicated agents handled: code deduplication (since "LLM-written code frequently re-implements existing functionality"), performance optimization, Rust code quality critique, and documentation.

5. **CI as harness evolution.** Late in the project, Claude started frequently breaking existing functionality when implementing new features. The fix was a CI pipeline with stricter enforcement — a harness-level solution to a model-level problem.

**Results:** The compiler builds a bootable Linux 6.9 on x86, ARM, and RISC-V. It compiles PostgreSQL, Redis, FFmpeg, SQLite, CPython, and 150+ other projects. It achieves 99% pass rate on GCC torture tests. It can compile and run Doom.

### 3.4 Thoughtworks: "Harness Engineering" (Böckeler, Feb 2026)

**Context:** Birgitta Böckeler, Distinguished Engineer at Thoughtworks, analyzed OpenAI's harness engineering post through the lens of software architecture and maintainability.

**Key contributions:**

1. **Taxonomy of harness components.** Böckeler categorizes OpenAI's harness into three groups:
   - *Context engineering:* Continuously enhanced knowledge base in the codebase plus dynamic context (observability data, browser navigation)
   - *Architectural constraints:* Monitored by both LLM-based agents and deterministic custom linters/structural tests
   - *Garbage collection:* Periodic agents that find inconsistencies and violations, fighting entropy

2. **Harnesses as future service templates.** Böckeler hypothesizes that harnesses — with custom linters, structural tests, context documentation, and context providers — could become the new service templates, similar to how organizations currently use golden-path templates for new services.

3. **Constrained runtimes for AI autonomy.** "Increasing trust and reliability required constraining the solution space: specific architectural patterns, enforced boundaries, standardized structures. That means giving up some 'generate anything' flexibility" (Böckeler, 2026).

4. **The retrofit problem.** Böckeler raises a critical unresolved question: "Which techniques could we apply to existing applications, and which would only work for applications built from scratch with a harness in mind?" She compares retrofitting to running a static analysis tool on a codebase that's never had one — "drowning in alerts."

5. **Missing verification of functionality.** Böckeler notes that OpenAI's write-up lacks discussion of how functionality and behavior are verified — a significant gap in an otherwise thorough treatment.

### 3.5 Artificial Ignorance: "The Emerging Harness Engineering Playbook" (Guo, Feb 2026)

**Context:** Charlie Guo synthesizes practices from OpenAI, Anthropic, Stripe, and solo practitioners (Steinberger) into an emerging playbook.

**Key contributions:**

1. **The engineer's job is splitting in two:** Building the environment (harness engineering) and managing the work (directing agent execution). These are concurrent, not sequential — agent failures inform harness design, and better harnesses reduce management friction.

2. **Evidence triangulation.** Guo assembles convergent evidence from three very different scales:
   - Solo: Peter Steinberger, 6,600+ commits in one month, running 5–10 agents simultaneously
   - Small team: OpenAI, 3 engineers, ~1M lines, 3.5 PRs/engineer/day
   - Enterprise: Stripe Minions, 1,000+ merged PRs per week

3. **Attended vs. unattended parallelization.** Guo distinguishes two modes: attended (actively managing several agent sessions, checking in, redirecting) and unattended (posting a task and walking away, re-entering only at review). The balance depends on harness maturity and trust.

4. **"Say no to slop" as a principle.** Citing Greg Brockman: "Ensure that some human is accountable for any code that gets merged. As a code reviewer, maintain at least the same bar as you would for human-written code." Higher agent throughput makes lowering the bar tempting but counterproductive.

5. **The cultural adoption challenge.** "None of this happens by accident. Someone has to build this stuff" — the investment compounds (every AGENTS.md update prevents future failures, every custom linter teaches every future session) but requires deliberate organizational commitment.

### 3.6 Alex Lavaee: "How to Harness Coding Agents with the Right Infrastructure" (2026)

**Context:** Lavaee provides a technical deep-dive synthesizing five independent teams' findings into a four-pillar framework, and describes Atomic, an open-source CLI operationalizing these patterns.

**Key contributions:**

1. **The Four Pillars framework:** Context Architecture, Agent Specialization, Persistent Memory, and Structured Execution (detailed in Section 5 below).

2. **Context utilization sweet spot.** Citing Horthy's empirical observation: performance degrades beyond ~40% context utilization. The "Smart Zone" (first ~40%) yields focused, accurate reasoning; the "Dumb Zone" (beyond ~40%) produces hallucinations, looping, and malformed tool calls.

3. **Progressive context tiers:** Tier 1 (hot memory — always loaded, ~100 lines), Tier 2 (specialist context — loaded when specific agents are invoked), Tier 3 (cold memory — persistent knowledge base, loaded on demand). This directly addresses the smart zone principle.

4. **Graph-based autonomous execution.** Lavaee describes a compiled DAG execution engine (Ralph) that decomposes specs into structured tasks, dispatches concurrent worker sub-agents for independent tasks, and includes review/fix gates.

5. **Academic validation.** Lavaee integrates Vasilopoulos's (2026) arXiv paper, which validated three-tier context infrastructure across 283 development sessions on a 108,000-line C# codebase with 19 specialized agents and 34 on-demand specification documents.

### 3.7 LangChain: "Improving Deep Agents with Harness Engineering" (Feb 2026)

**Context:** LangChain improved their coding agent (deepagents-cli) from 52.8% to 66.5% on Terminal Bench 2.0 — a 13.7-point improvement — by only modifying the harness while keeping the model fixed (GPT-5.2-Codex).

**Key contributions:**

1. **Self-verification as the highest-leverage intervention.** The most common failure pattern: agents wrote solutions, re-read their own code, confirmed it looked correct, and stopped — without running tests. Adding structured build-verify loops (plan → build → verify → fix) was the single most impactful change.

2. **PreCompletionChecklistMiddleware.** A deterministic hook that intercepts the agent before it exits and reminds it to run verification against the task specification. Similar to Huntley's Ralph loop, but targeted at the exit condition.

3. **Loop detection middleware.** Tracks per-file edit counts; after N edits to the same file, injects context like "consider reconsidering your approach." This is explicitly framed as a workaround for current model limitations that will "almost surely dissolve over time."

4. **Reasoning budget optimization.** LangChain found that an `xhigh-high-xhigh` "reasoning sandwich" (high reasoning for planning, lower for implementation, high again for verification) performed best. Running only at `xhigh` scored poorly (53.9%) due to timeouts, while `high` alone scored 63.6%.

5. **Trace-based improvement loop.** An automated "Trace Analyzer" skill fetches experiment traces from LangSmith, spawns parallel error analysis agents, and aggregates feedback into targeted harness changes. This works "similarly to boosting which focuses on mistakes from previous runs."

6. **Environment onboarding.** A `LocalContextMiddleware` runs on agent start to map the working directory, identify available tools (Python installations, etc.), and inject this context — reducing error surface from poor search and avoidable planning mistakes.

---

## 4. Converging Principles and Mechanisms

Across all seven primary sources and supplementary expert perspectives, the following principles emerge with broad agreement:

### 4.1 The Infrastructure Principle

**"The bottleneck is infrastructure, not intelligence."**

Every primary source arrives at this conclusion independently:

- OpenAI: "Progress was slower than we expected, not because Codex was incapable, but because the environment was underspecified" (Lopopolo, 2026).
- Carlini: "Most of my effort went into designing the environment around Claude — the tests, the environment, the feedback — so that it could orient itself without me" (Carlini, 2026).
- LangChain: 13.7-point improvement on Terminal Bench 2.0 with zero model changes.
- Vercel: Tool reduction (removing ~80% of tools, from ~17 down to a single bash tool) improved accuracy from 80% to 100% on a text-to-SQL agent benchmark.

### 4.2 The Incrementality Principle

**Agents must make incremental, verifiable progress rather than attempting to one-shot complex tasks.**

- Anthropic's coding agent works on "only one feature at a time" (Young, 2025).
- OpenAI's engineers break goals into "smaller building blocks" and prompt the agent to construct those blocks (Lopopolo, 2026).
- Boris Tane enforces strict separation of research, planning, and implementation phases (Tane, 2026).
- Carlini's agents each pick one failing test or one source file to work on (Carlini, 2026).

### 4.3 The Clean State Principle

**Each agent session must leave the environment in a state that another agent (or human) can immediately continue from.**

- Anthropic: "By 'clean state' we mean the kind of code that would be appropriate for merging to a main branch: there are no major bugs, the code is orderly and well-documented" (Young, 2025).
- OpenAI: Pull requests are short-lived, agents commit with descriptive messages, progress is tracked in versioned artifacts.
- Carlini: Agents push changes, remove task locks, and update progress documentation before spawning new sessions.

### 4.4 The Self-Verification Principle

**Agents must verify their own work through automated feedback before declaring completion.**

- LangChain: Self-verification was the single highest-leverage intervention.
- Anthropic: Browser automation for end-to-end testing "dramatically improved performance."
- OpenAI: Agents use Chrome DevTools Protocol, LogQL, and PromQL to verify their own changes.
- Carlini: Test suites with strict CI enforcement prevent regressions.

### 4.5 The Mechanical Enforcement Principle

**Constraints must be enforced deterministically (through linters, structural tests, CI), not just communicated through prompts.**

- OpenAI: Custom linters enforce layered architecture, naming conventions, and file size limits. Error messages double as remediation instructions.
- Carlini: CI pipeline prevents commits that break existing functionality.
- Huntley: Downstream backpressure (tests, linting, type-checking, builds) rejects invalid work before it can be committed.

### 4.6 The Feedback Loop Principle

**When an agent fails, the failure should be treated as a harness design problem, not a model problem.**

- OpenAI: "When something failed, the fix was almost never 'try harder.' ... human engineers always stepped into the task and asked: 'what capability is missing?'" (Lopopolo, 2026).
- Hashimoto: "Anytime you find an agent makes a mistake, you take the time to engineer a solution such that the agent never makes that mistake again" (Hashimoto, 2026).
- LangChain: Automated trace analysis turns failures into targeted harness improvements.

---

## 5. The Four Pillars of Harness Engineering

Lavaee (2026) synthesized the converging practices into four pillars. This framework is validated across all primary sources.

### Pillar 1: Context Architecture

**Principle:** An agent should receive exactly the context it needs for its current task — no more, no less.

| Source | Implementation |
|--------|---------------|
| OpenAI | ~100-line AGENTS.md as table of contents → structured `docs/` directory with design docs, exec plans, product specs, references |
| Anthropic (Young) | READMEs, progress files, feature lists updated per session |
| Anthropic (Carlini) | Extensive READMEs maintained by agents; minimal console output; grep-friendly log formats; pre-computed aggregate statistics |
| Horthy | Frequent Intentional Compaction — actively reducing context to stay in the "Smart Zone" (<40% utilization) |
| Vasilopoulos | Three-tier architecture: Hot Memory (constitution), Specialized Agents, Cold Memory (knowledge base) |
| Jozefiak | Lean CLAUDE.md (~61 lines after reducing from 471) + reference pattern pointing to external docs |

**Critical finding:** Research by Gloaguen, Mündler, Müller, Raychev, and Vechev at SRI Lab, ETH Zurich (arXiv:2602.11988, 2026) found that unnecessary instructions increase reasoning tokens by 14–22%. LLM-generated AGENTS.md files actually *reduce* task success rates by ~3% while increasing inference costs by over 20%. Human-written context files provide only a marginal ~4% improvement on average while also increasing costs. Less is demonstrably more.

**Anti-pattern:** The "one big AGENTS.md" approach. OpenAI explicitly abandoned this: "Too much guidance becomes non-guidance. When everything is 'important,' nothing is" (Lopopolo, 2026).

### Pillar 2: Agent Specialization

**Principle:** A focused agent with restricted tools outperforms a general-purpose agent with full access.

| Source | Implementation |
|--------|---------------|
| Carlini | Dedicated agents for: core compiler, code deduplication, performance optimization, Rust quality, documentation |
| Vasilopoulos | 19 domain-specific agents (code reviewer, network protocol expert, debugger, UI designer, etc.) with targeted prompts |
| Lavaee/Atomic | 10 specialized agents split into research agents (read-only) and workflow agents (plan, execute, review, debug) |
| OpenAI | Background "doc-gardening" agent, quality-grading agents, refactoring agents, review agents |
| Vercel | Removed ~80% of tools (from ~17 to a single bash tool), improving accuracy from 80% to 100% on a text-to-SQL benchmark |

**Mechanism:** Specialization is fundamentally a context management strategy. Each specialist carries less irrelevant information, keeping it in the "Smart Zone" (Horthy's framework). Fewer tools also reduce decision fatigue — Pappas (2026) documents that vague tool descriptions force models to guess behavior and retry incorrectly.

### Pillar 3: Persistent Memory

**Principle:** Progress persists on disk, not in the context window. Each new session reconstructs context from filesystem artifacts.

| Source | Implementation |
|--------|---------------|
| Anthropic (Young) | `claude-progress.txt` + git history; JSON feature list with `passes` field |
| Anthropic (Carlini) | Git-tracked task lock files (`current_tasks/`); running docs of failed approaches |
| OpenAI | Versioned execution plans, completed plans, tech debt tracker — all in the repository |
| Huntley | `IMPLEMENTATION_PLAN.md` and `progress.txt` updated each iteration |
| Horthy | Structured markdown artifacts from compaction |
| Vasilopoulos | 34 on-demand specification documents accessed via MCP retrieval |

**Key design choice:** Anthropic found that JSON is more resistant to inappropriate agent modification than Markdown for structured state tracking (Young, 2025).

### Pillar 4: Structured Execution

**Principle:** Separate thinking from typing. Research and planning happen in controlled phases; execution happens against a verified plan; verification happens through automated feedback.

| Source | Workflow |
|--------|----------|
| Tane | Research → Plan → Annotate → Implement (strict human gates between phases) |
| Horthy | Research → Plan → Implement (RPI) with Frequent Intentional Compaction |
| Anthropic (Young) | Initialize environment → Bootstrap session → Choose feature → Implement → Verify → Commit → Update progress |
| LangChain | Plan & Discover → Build → Verify → Fix (with middleware hooks at transitions) |
| Lavaee/Atomic | Research → Spec → Implement → Review (human checkpoints at each transition) |
| Huntley | Requirements → Planning → Building (three-phase Ralph workflow) |

**Consensus:** Every source enforces a planning phase before implementation. Boris Tane states the principle most directly: "This separation of planning and execution is the single most important thing I do. It prevents wasted effort, keeps me in control of architecture decisions, and produces significantly better results" (Tane, 2026).

---

## 6. Experimentation Details and Empirical Evidence

### 6.1 Quantitative Results Summary

| Experiment | Team | Duration | Output | Cost | Key Metric |
|-----------|------|----------|--------|------|------------|
| Million-line product | OpenAI (3→7 engineers) | 5 months | ~1M LOC, ~1,500 PRs | Not disclosed | 3.5 PRs/engineer/day; ~1/10th time vs. manual |
| C compiler | Anthropic (1 researcher + 16 agents) | ~2 weeks | 100K LOC (Rust) | ~$20,000 | 99% GCC torture test pass rate; compiles Linux 6.9 |
| Terminal Bench 2.0 | LangChain | Not specified | N/A | Not disclosed | 52.8% → 66.5% (+13.7 pts), harness-only change |
| OpenClaw | Steinberger (solo) | ~2 months | 6,600+ commits/month | Not disclosed | 180K+ GitHub stars |
| Codified Context study | Vasilopoulos | 70 days (part-time) | 108K LOC (C#) | Not disclosed | 283 sessions tracked; 19 agents; 34 spec docs |
| Vercel tool reduction (text-to-SQL agent) | Vercel | Dec 2025 | N/A | Not disclosed | 80% → 100% accuracy on 5 representative queries; -37% tokens; 3.5x speed |
| Stripe Minions | Stripe | Ongoing | 1,000+ merged PRs/week | Not disclosed | End-to-end agent-to-merge pipeline |

### 6.2 Carlini's Compiler: Detailed Experimental Design

This experiment provides the most detailed public account of multi-agent harness design:

**Infrastructure:**
- 16 Docker containers, each with a local git clone mounted from a bare upstream repo
- Simple bash loop: `while true; do claude --dangerously-skip-permissions -p "$(cat AGENT_PROMPT.md)" --model claude-opus-X-Y; done`
- Task synchronization via git-tracked text files in `current_tasks/`
- No orchestrator agent; each agent self-selects work

**Cost breakdown:** 2 billion input tokens + 140 million output tokens = ~$20,000 total.

**Parallelization challenge and solution:** When agents hit the Linux kernel compilation task, all 16 converged on the same bug. Carlini introduced GCC as an oracle compiler — randomly compiling most kernel files with GCC and only a subset with Claude's compiler. If the kernel worked, the problem was not in Claude's subset. If it broke, delta debugging further refined which files contained bugs. This re-enabled effective parallel work.

**Emergent agent behavior:** In one instance, an agent accidentally executed `pkill -9 bash`, killing itself and ending its loop — an unintended consequence of unrestricted shell access. In another, agents maintained running documents of failed approaches, enabling future agents to avoid repeating dead ends.

### 6.3 LangChain's Terminal Bench: Controlled Experiment

LangChain's experiment is the cleanest controlled study in the corpus, because the model was held constant (GPT-5.2-Codex) while only the harness was modified.

**Baseline:** Default prompt + standard tools + standard middleware → 52.8% on Terminal Bench 2.0.

**Interventions (cumulative):**
1. Build & Self-Verify guidance in system prompt
2. PreCompletionChecklistMiddleware (deterministic exit hook)
3. LocalContextMiddleware (environment onboarding)
4. LoopDetectionMiddleware (per-file edit tracking)
5. Reasoning budget optimization (xhigh-high-xhigh sandwich)
6. Time budget warnings

**Final score:** 66.5% — a 13.7-point improvement, moving from Top 30 to Top 5 on the leaderboard.

**Reasoning budget finding:** Running at only `xhigh` reasoning scored 53.9% (worse than baseline) due to agent timeouts. Running at `high` scored 63.6%. The "reasoning sandwich" (high reasoning for planning/verification, lower for implementation) achieved 66.5%.

### 6.4 Vasilopoulos: Academic Validation

The only peer-reviewed academic contribution in the corpus (arXiv preprint, February 2026).

**Methodology:** 283 development sessions on a 108,000-line C# distributed system, tracked over 70 days of part-time development. Four observational case studies documented how codified context prevented failures and maintained consistency.

**Three-tier architecture:**
- Tier 1 (Hot Memory): Always-loaded manifest with conventions, orchestration protocols, and an agent trigger table routing tasks to specialists
- Tier 2 (Specialists): 19 focused agents invoked automatically based on Tier 1 triggers
- Tier 3 (Cold Memory): 34 specification documents loaded on demand via MCP retrieval

**Finding:** "Systematic, multi-layered context management significantly improves agent reliability. Single-file instruction sets break down at scale because they can't encode domain specialization, progressive disclosure, or session-persistent knowledge" (Vasilopoulos, 2026).

**Methodology caveat:** This was a single-developer, single-project study with observational case studies rather than controlled experiments. The author explicitly notes that no causal relationships are claimed. The results are suggestive rather than definitive, but they independently converge on the same patterns observed by larger teams at OpenAI and Anthropic.

---

## 7. Areas of Agreement

The following points enjoy near-universal agreement across all sources:

### 7.1 The Model Is Necessary but Not Sufficient

Every source acknowledges that model capability is a prerequisite. Pappas (2026) explicitly states a "capability floor" below which no harness compensates. But above that floor, harness investment yields superior returns.

### 7.2 Testing Is Non-Negotiable

Every source emphasizes automated testing as the backbone of agent reliability:
- Anthropic: Browser automation for end-to-end testing
- OpenAI: Agent-driven test suites, observability-based verification
- LangChain: Build-verify loop as highest-leverage intervention
- Carlini: "Write extremely high-quality tests" — first lesson in his post
- Huntley: Downstream backpressure (tests, linting, type-checking)
- Tane: "If the research is wrong, the plan will be wrong, and the implementation will be wrong"

### 7.3 Documentation Must Be Living, Not Static

Every source rejects static documentation in favor of continuously updated, mechanically enforced knowledge bases:
- OpenAI: Doc-gardening agents scan for stale documentation
- Hashimoto: Update AGENTS.md every time the agent does something wrong
- Anthropic: Progress files updated every session
- Vasilopoulos: Tier 1 (hot) and Tier 3 (cold) documents maintained alongside code

### 7.4 Git as the Universal Coordination Primitive

Git serves as the shared state, rollback mechanism, and coordination layer across all experiments:
- Carlini: 16 agents coordinate through git push/pull with file-based locks
- Anthropic: Git history enables agents to understand project evolution
- OpenAI: Pull requests as the unit of agent work
- Huntley: Direct push to master with automated rollback

### 7.5 Architecture Constrains Enable Speed

A counterintuitive finding with broad agreement: rigid architectural constraints *accelerate* agent productivity rather than slowing it.

- OpenAI: "This is the kind of architecture you usually postpone until you have hundreds of engineers. With coding agents, it's an early prerequisite" (Lopopolo, 2026).
- Böckeler: "Increasing trust and reliability required constraining the solution space" (Böckeler, 2026).
- Stripe: Agents run in isolated devboxes with access to 400+ internal tools via MCP — constrained but capable.

### 7.6 Humans Must Remain Accountable

Despite varying levels of autonomy, every source maintains human accountability:
- OpenAI: "Humans always remain in the loop, but work at a different layer of abstraction"
- Brockman: "Ensure that some human is accountable for any code that gets merged"
- Guo: "Say no to slop" as a core principle
- Steinberger: Acts as "architectural gatekeeper" despite shipping code he hasn't read line by line

---

## 8. Points of Debate and Divergence

### 8.1 Specialized vs. Generic Scaffolds

**The debate:** Do elaborate, specialized harnesses justify their engineering cost?

**For specialization:**
- OpenAI, Anthropic, LangChain, and Stripe all report significant gains from purpose-built harnesses
- Vasilopoulos validated 19 specialized agents with measurable improvements over 283 sessions

**Against specialization:**
- METR research (2026) found that Claude Code (with Opus 4.5) beat ReAct in only 50.7% of bootstrap samples (statistically indistinguishable from chance), while Codex (with GPT-5) beat METR's generic Triframe scaffold in only 14.5% of bootstrap samples — meaning the generic scaffold outperformed the specialized one in most comparisons. This suggests "the underlying model matters more than the scaffold for autonomous task endurance" on time-horizon benchmarks (METR, 2026). Critically, METR measures autonomous endurance on bounded tasks, not production code quality, elegance, or maintainability over sustained development.
- Vercel demonstrated that *removing* tools improved accuracy — fewer, clearer constraints outperformed more complex tooling.

**Resolution:** These findings are not necessarily contradictory. METR measures *time horizon* (autonomous endurance on short-lived tasks), while OpenAI/Anthropic measure *production quality across sustained development*. Specialized harnesses may not help with individual task completion but may be essential for maintaining quality, consistency, and architectural coherence over thousands of commits. As Adam Baitch (2026) notes, the distinction matters: "time horizon measures only autonomous endurance, not code quality, elegance, or real-world utility."

### 8.2 Tool Maximalism vs. Tool Minimalism

**Maximalist position (Stripe, OpenAI):** Give agents access to as many tools as possible. Stripe's agents connect to 400+ internal tools via MCP's Toolshed. OpenAI provides Chrome DevTools Protocol, LogQL, PromQL, and full filesystem access.

**Minimalist position (Vercel, Horthy):** Fewer tools yield better results. Vercel removed 80% of tools and accuracy jumped from 80% to 100%. Horthy advocates keeping context below 40% utilization.

**Synthesis:** The resolution lies in *progressive disclosure* (OpenAI's term) or *tiered context* (Vasilopoulos's term). The number of available tools matters less than how many are loaded into context simultaneously. Stripe's 400+ tools are not all loaded at once — they are accessible on demand through MCP routing. The principle is: make many tools available, but load few into any single context window.

### 8.3 Human Review: Required or Optional?

**Required (Brockman, Guo, Tane):** Human code review must maintain at least the same bar as for human-written code. "Say no to slop."

**Optional (OpenAI engineering team, Huntley):** OpenAI notes that "humans may review pull requests, but aren't required to. Over time, we've pushed almost all review effort towards being handled agent-to-agent." Huntley pushes directly to master with no human review, relying on automated backpressure.

**Nuance:** The difference correlates with harness maturity and blast radius. OpenAI's team has spent five months building mechanical enforcement (linters, structural tests, CI, doc-gardening agents) that functions as an automated reviewer. Huntley operates on personal projects where the blast radius is low. Stripe, operating in a high-stakes financial environment, requires human review for every merged PR.

### 8.4 Greenfield vs. Brownfield Applicability

**Greenfield optimists:** All primary source experiments are greenfield projects (or internal tools). The harness is designed alongside the code from day one.

**Brownfield skeptics (Böckeler):** "Applying these techniques to a ten-year-old codebase with no architectural constraints, inconsistent testing, and patchy documentation is a much more complex problem" (Böckeler, 2026). Retrofitting may not be cost-effective.

**Emerging brownfield practices:** Practitioners working with legacy codebases recommend (engineering.harness.io, 2026): tests as system boundaries (especially E2E tests), agent-focused documentation of architectural decisions and data flow assumptions, incremental structure building with gradually increasing agent autonomy, and phased technical debt resolution (15–25% sprint capacity allocation).

### 8.5 Single Agent vs. Multi-Agent Architectures

**Single-agent advocates:** Anthropic's long-running agent post explicitly avoids multi-agent coordination: "It's still unclear whether a single, general-purpose coding agent performs best across contexts, or if better performance can be achieved through a multi-agent architecture" (Young, 2025).

**Multi-agent advocates:** Carlini demonstrates clear benefits of parallelization (16 agents, ~2,000 sessions). OpenAI uses multiple agent roles (coding, reviewing, doc-gardening, refactoring). Stripe runs multiple Minions in parallel.

**Emerging consensus:** Guo (2026) offers the most nuanced position — the choice depends on harness maturity. Attended parallelization (active management of several sessions) requires less harness investment; unattended parallelization (agent works independently through to PR) requires much more. Most teams are "somewhere in the middle — attended for complex tasks, unattended for well-scoped ones."

---

## 9. Relationship to Adjacent Disciplines

### 9.1 Prompt Engineering → Context Engineering → Harness Engineering

These three disciplines form nested layers of increasing scope:

| Discipline | Scope | Question | Focus |
|-----------|-------|----------|-------|
| Prompt Engineering | Single instruction | "What should I ask?" | Crafting effective text prompts |
| Context Engineering | Model's full input | "What should the model see?" | System prompts, RAG, tool descriptions, conversation history |
| Harness Engineering | Entire environment | "How should the whole system work?" | Constraints, feedback loops, CI/CD, linters, documentation, agent lifecycle |

M. Trajan (2026) articulates the key distinction: "Context engineering alone cannot solve production stability problems — while it ensures the agent knows the right information, harness engineering ensures the agent can reliably *do* the right thing without supervision."

### 9.2 Relationship to DevOps and Platform Engineering

Harness engineering shares substantial DNA with platform engineering and DevOps:

- **CI/CD as backpressure** — Agent output passes through the same pipelines as human code
- **Infrastructure-as-Code** — Harness configuration (AGENTS.md, linter rules, structural tests) is version-controlled
- **Observability** — Agents consume the same logs, metrics, and traces as human engineers
- **Service templates → Harness templates** — Böckeler's hypothesis that harnesses become the new golden-path templates

### 9.3 Relationship to Software Architecture

Chad Fowler's "Relocating Rigor" concept (2026) provides the deepest connection: each major shift in software (XP, dynamic languages, CI/CD) *appears* to remove constraints but actually relocates rigor "closer to where truth lives." With AI-generated code, rigor relocates from implementation to specification, verification, and environmental design.

Addy Osmani (2026) echoes this: "The rise of AI coding doesn't replace the craft of software engineering — it raises the bar for it." The 80% problem (AI generates most of the code but the remaining 20% is as hard as ever) means that architectural judgment, verification design, and constraint specification become the primary engineering skills.

---

## 10. Expert and Practitioner Perspectives

### 10.1 Mitchell Hashimoto — The Pragmatic Adoptionist

Hashimoto's six-step adoption ladder provides the most grounded on-ramp to harness engineering. His key insight: adoption is a progression through inefficiency, adequacy, and workflow-altering discovery. Engineers must deliberately experiment through all three phases. His AGENTS.md for Ghostty contains lines that each correspond to a specific past agent failure that is now prevented — the file is a fossil record of harness evolution.

### 10.2 Greg Brockman — The Organizational Perspective

Brockman's recommendation to appoint an "agents captain" per team acknowledges that harness engineering is an organizational challenge, not just a technical one. His six recommendations:
1. Start with AI agents as the default, not the fallback
2. Maintain a list of team tools and make them agent-accessible (via CLI or MCP)
3. Create and maintain AGENTS.md; update it when agents struggle
4. Write fast-running tests with high-quality component interfaces
5. "Say no to slop" — maintain the same code review bar as human code
6. Designate an agents captain

### 10.3 Peter Steinberger — The Solo Architect

Steinberger demonstrates harness engineering at the individual scale: 6,600+ commits in one month, 5–10 simultaneous agents, shipping code he hasn't read line-by-line. His approach centers on maintaining architectural control ("the benevolent dictator") while delegating all implementation. He distinguishes his practice from "vibe coding" — treating AI coding as a craft requiring skill and architectural judgment. His observation that "engineers who love solving algorithmic puzzles struggle to go agent-native, while those who love shipping products adapt quickly" captures a fundamental orientation shift.

### 10.4 Boris Tane — The Planning Disciplinarian

Tane's strict four-phase workflow (research → plan → annotate → implement) is the most rigorous planning-first approach in the literature. His core principle: "if the research is wrong, the plan will be wrong, and the implementation will be wrong. Garbage in, garbage out." He reviews and edits Claude's generated plans in a text editor before allowing code generation — an explicit human gate that catches architectural misalignments before they propagate.

### 10.5 Dex Horthy — The Context Scientist

Horthy's "Smart Zone" / "Dumb Zone" framework, derived from empirical observation on a 300,000-line Rust codebase (BAML), provides the most actionable context management guidance. His RPI (Research, Plan, Implement) methodology with Frequent Intentional Compaction is designed explicitly to keep context utilization below the ~40% degradation threshold. Results include shipping a week's worth of work in a day with code quality passing expert review.

### 10.6 Pawel Jozefiak — The Iterative Practitioner

After 1,000+ Claude Code sessions, Jozefiak's CLAUDE.md evolved from 3 lines to 471 lines and back to 61 lines. This trajectory encapsulates a key lesson: more instructions are not better. The optimal pattern is a lean primary file with reference pointers to deeper documentation loaded on demand — independently converging on the same progressive disclosure pattern as OpenAI, Vasilopoulos, and Horthy.

### 10.7 Vitthal Mirji — The Staff Engineer's Perspective

Mirji's guide frames harness engineering through the lens of staff/principal engineering, proposing an 11-step autonomy ladder from bug reproduction to autonomous PR merge. His distinction between harness engineering and context engineering is precise: harness engineering focuses on what the system *prevents, measures, and corrects*, not just what information the agent receives.

### 10.8 Addy Osmani — The Pragmatic Skeptic

Osmani brings a measured perspective, documenting "the 80% problem": AI generates most code but the final 20% (edge cases, security, production integration, debugging) remains as time-consuming as ever. He emphasizes that trust remains low — only 33% of developers trust AI output. His evolution model (coder → conductor → orchestrator) maps the trajectory of the engineering role transformation.

---

## 11. Failure Modes and Mitigations

The primary sources document a comprehensive taxonomy of agent failure modes with corresponding harness mitigations:

### 11.1 Agent Failure Mode Taxonomy

| Failure Mode | Description | Source | Mitigation |
|-------------|-------------|--------|-----------|
| **One-shotting** | Agent attempts entire project in one pass | Anthropic (Young) | Feature list with granular items; one feature per session |
| **Premature completion** | Agent declares done without verification | Anthropic (Young), LangChain | Self-verification loops; browser automation; PreCompletionChecklistMiddleware |
| **Context rot** | Accumulated context degrades reasoning | Horthy, Huntley | Frequent Intentional Compaction; fresh context per iteration (Ralph loop) |
| **Doom loops** | Agent makes small variations to the same broken approach 10+ times | LangChain | LoopDetectionMiddleware; per-file edit tracking; reconsideration prompts |
| **Regression** | New features break existing functionality | Carlini | CI pipeline with strict enforcement; comprehensive test suites |
| **Duplication** | Agent re-implements existing functionality | Carlini | Dedicated deduplication agents; architectural constraint enforcement |
| **Documentation rot** | AGENTS.md/docs drift from actual code | OpenAI | Doc-gardening agents; mechanical freshness validation in CI |
| **Entropy/slop accumulation** | Gradual quality degradation over many commits | OpenAI | Recurring cleanup agents; golden principles; quality grading |
| **Context window pollution** | Excessive output drowns useful information | Carlini | Minimal console output; file-based logging; grep-friendly error formats |
| **Time blindness** | Agent spends hours on low-value activities (e.g., running all tests) | Carlini | Deterministic test subsampling; time budget warnings |
| **Convergent parallelism** | All parallel agents fix the same bug | Carlini | Oracle-based problem decomposition; random work assignment |
| **Tool confusion** | Too many tools cause decision fatigue | Vercel, Pappas | Tool reduction; progressive disclosure; clear tool descriptions |

### 11.2 The Backpressure Framework

Huntley's backpressure framework (2025–2026) provides the most systematic model for preventing failures:

**Upstream backpressure** (steering input):
- Deterministic setup and consistent context
- Existing code patterns guide preferred implementations
- AGENTS.md and architectural documentation

**Downstream backpressure** (validating output):
- Tests, type checks, linting, builds
- Security scanners and custom validators
- LLM-as-judge for subjective criteria
- CI pipeline enforcement

The principle: "The more you capture the backpressure, the more autonomy you can grant. That's the game for the new unit economics" (Huntley, 2026).

---

## 12. Practical Guidelines for Agentic Systems

Synthesizing all sources, the following guidelines emerge for systems practicing harness engineering:

### 12.1 Context Architecture Guidelines

1. **Keep primary instruction files lean.** AGENTS.md/CLAUDE.md should be ~60–150 lines, functioning as a table of contents rather than an encyclopedia. Reference deeper documentation on demand.

2. **Implement progressive disclosure.** Structure context in tiers: always-loaded core conventions (Tier 1), specialist context loaded per-task (Tier 2), and on-demand knowledge base (Tier 3).

3. **Monitor context utilization.** Performance degrades beyond ~40% context window utilization. Design all context loading to keep the agent in the "Smart Zone."

4. **Use structured formats for state.** JSON is more resistant to inappropriate agent modification than Markdown for tracking completion status, feature lists, and progress.

5. **Pre-compute summaries.** Agents should not have to recompute aggregate statistics from raw data. Provide summary files that are maintained by the harness.

### 12.2 Agent Specialization Guidelines

6. **Assign distinct roles.** Separate research/analysis agents (read-only) from implementation agents (write access). Consider dedicated agents for: planning, implementation, code review, documentation, deduplication, performance, and cleanup.

7. **Restrict tool access per role.** Each specialist should carry only the tools and permissions it needs. A code analyzer should not have write access; a reviewer should flag but not fix.

8. **Use progressive tool loading.** Make many tools available via MCP, but load few into any single context window. Route tools through semantic or rule-based dispatch.

### 12.3 Persistent Memory Guidelines

9. **Persist progress on disk, not in conversation.** Use git-tracked progress files, feature lists, implementation plans, and task lock files. Each new session reconstructs context from filesystem artifacts.

10. **Maintain a running log of failed approaches.** Prevent agents from repeating dead ends across sessions.

11. **Version all artifacts.** Execution plans, completed plans, research documents, and known technical debt should be versioned in the repository alongside code.

### 12.4 Structured Execution Guidelines

12. **Enforce research → plan → implement → verify phases.** Never allow implementation without a reviewed plan. Planning is cheaper than rework.

13. **Require self-verification before completion.** Agents must run tests, check linter output, and verify end-to-end behavior (preferably through browser automation for web apps) before marking work complete.

14. **Use deterministic exit hooks.** A PreCompletionChecklist or similar mechanism should intercept the agent before it declares completion and force a verification pass.

15. **Implement session bootstrapping.** Every new session should: read progress files, check git history, run basic health checks, then choose the next task.

### 12.5 Mechanical Enforcement Guidelines

16. **Enforce architecture with linters and structural tests.** Dependency directions, naming conventions, file size limits, and module boundaries should be checked mechanically, not just documented.

17. **Write error messages as remediation instructions.** When a constraint is violated, the error message should tell the agent how to fix it.

18. **Use CI as a harness gate.** No commit should break existing tests. CI enforcement prevents the regression failure mode.

19. **Deploy garbage collection agents.** Recurring background agents should scan for stale documentation, architectural violations, duplicated code, and quality regressions, opening cleanup PRs automatically.

### 12.6 Feedback Loop Guidelines

20. **Treat every failure as a harness design problem.** When an agent makes a mistake, update the harness (documentation, linters, tests, constraints) so it never happens again.

21. **Use trace-based analysis for systematic improvement.** Collect traces from agent sessions; use automated analysis to identify patterns of failure; translate findings into harness improvements.

22. **Maintain a failure fossil record.** The AGENTS.md file should evolve to reflect specific past failures that have been mitigated — each line corresponding to a lesson learned.

### 12.7 Parallelization Guidelines

23. **Use git as the coordination primitive.** File-based task locks, descriptive commit messages, and push/pull synchronization are sufficient for most multi-agent scenarios.

24. **Prevent convergent parallelism.** When multiple agents work on related problems, use oracle-based decomposition or random assignment to ensure each agent works on a distinct sub-problem.

25. **Start with attended parallelization.** Actively manage multiple sessions before graduating to unattended workflows. The harness must be mature enough to support unattended execution.

---

## 13. Open Problems and Future Directions

### 13.1 Long-Term Architectural Coherence

OpenAI acknowledges: "What we don't yet know is how architectural coherence evolves over years in a fully agent-generated system" (Lopopolo, 2026). Current evidence covers at most five months of sustained agent development. Whether harness engineering techniques maintain coherence over multi-year timescales remains untested.

### 13.2 The Brownfield Retrofit Problem

No primary source demonstrates successful retrofit of harness engineering to a large legacy codebase. Böckeler's analogy — "running a static analysis tool on a codebase that's never had one, and then drowning in alerts" — captures the challenge. Emerging practices (incremental structure building, tests as boundaries, phased technical debt resolution) are promising but unvalidated at scale.

### 13.3 Verification at Scale

Böckeler's critique that OpenAI's write-up lacks "verification of functionality and behavior" applies broadly. Browser automation helps but has known limitations (Anthropic found agents couldn't see browser-native alert modals through Puppeteer). Comprehensive end-to-end verification of agent-generated code remains an open problem, especially for non-web domains.

### 13.4 Multi-Agent Coordination Beyond Git

Current multi-agent coordination is primitive — git-based locks and push/pull. There is no established pattern for agents to communicate plans, share intermediate findings, negotiate work allocation, or resolve conflicting architectural decisions. Anthropic explicitly flags this: "I haven't yet implemented any other method for communication between agents, nor do I enforce any process for managing high-level goals" (Carlini, 2026).

### 13.5 Harness Portability and Standardization

Harnesses remain highly custom and project-specific. Böckeler's hypothesis — that harnesses could become standardized templates for common application topologies — is intriguing but unimplemented. The AGENTS.md convention is a first step toward standardization but covers only the instruction layer, not the full harness (linters, structural tests, CI configuration, garbage collection agents).

### 13.6 Adaptive Reasoning Budgets

LangChain's "reasoning sandwich" (xhigh-high-xhigh) is a static heuristic. Optimal reasoning allocation likely varies by task complexity, phase, and agent state. Adaptive reasoning — where the agent or harness dynamically adjusts compute allocation — is identified as a natural evolution. Claude and Gemini already implement this at the model level; harness-level orchestration of reasoning budgets across multi-agent workflows is unexplored.

### 13.7 Domain Generalization

All primary sources focus on software engineering (mostly full-stack web and compiler development). Anthropic notes: "A future direction is to generalize these findings to other fields. It's likely that some or all of these lessons can be applied to... scientific research or financial modeling" (Young, 2025). Systematic validation in non-software domains is absent.

### 13.8 The Governance Gap

Industry data suggests 73% of enterprise AI agents remain unmonitored and ungoverned (htek.dev, 2026). As agents operate with increasing autonomy — including auto-merging PRs, deploying code, and managing infrastructure — governance frameworks (audit trails, access controls, rollback policies, compliance verification) become critical but are largely unaddressed in the harness engineering literature.

### 13.9 The Diminishing Returns Question

As models improve, some harness components will become unnecessary. LangChain explicitly acknowledges that LoopDetectionMiddleware is "a design heuristic that engineers around today's perceived model issues. As models improve, these guardrails will likely be unnecessary" (LangChain, 2026). Understanding which harness components are permanent (architectural enforcement, testing) versus temporary (loop detection, time budget warnings) is important for long-term investment decisions.

---

## 14. Conclusion

Harness engineering has emerged in early 2026 as a coherent discipline with broad practitioner convergence, supported by empirical evidence from OpenAI, Anthropic, LangChain, Stripe, and multiple independent practitioners. The central finding is robust: past a model capability threshold, the primary determinant of agentic software development success is the quality of the infrastructure surrounding the agent, not the intelligence of the model itself.

The Four Pillars — Context Architecture, Agent Specialization, Persistent Memory, and Structured Execution — provide an actionable framework validated across scales ranging from solo developers to enterprise engineering organizations. Mechanical enforcement (linters, structural tests, CI) and systematic feedback loops (trace analysis, failure-driven harness updates, garbage collection agents) distinguish harness engineering from its predecessors (prompt engineering, context engineering) by addressing the *operational environment* rather than just the *informational input*.

Critical open problems remain: long-term architectural coherence, brownfield applicability, verification at scale, multi-agent coordination, and governance. The discipline is still forming — as Böckeler notes, "the practices built for human-only development are breaking in predictable ways under AI assistance, and replacements are still forming but not yet mature."

For practitioners building agentic systems, the evidence points to a clear investment priority: **build the harness before writing the prompts.** Design the constraints, testing infrastructure, documentation systems, and feedback loops first. The agent will be only as reliable as the environment it operates within.

---

## 15. References

### Primary Sources

1. **Lopopolo, R.** (2026). "Harness engineering: leveraging Codex in an agent-first world." *OpenAI Engineering Blog*, February 11, 2026. https://openai.com/index/harness-engineering/

2. **Young, J.** (2025). "Effective harnesses for long-running agents." *Anthropic Engineering*, November 26, 2025. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

3. **Carlini, N.** (2026). "Building a C compiler with a team of parallel Claudes." *Anthropic Engineering*, February 5, 2026. https://www.anthropic.com/engineering/building-c-compiler

4. **Böckeler, B.** (2026). "Harness Engineering." *Martin Fowler / Thoughtworks — Exploring Gen AI*, February 17, 2026. https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html

5. **Guo, C.** (2026). "The Emerging 'Harness Engineering' Playbook." *Artificial Ignorance (Substack)*, February 22, 2026. https://www.ignorance.ai/p/the-emerging-harness-engineering

6. **Lavaee, A.** (2026). "How to Harness Coding Agents with the Right Infrastructure." *Alex Lavaee Blog*, 2026. https://alexlavaee.me/blog/harness-engineering-why-coding-agents-need-infrastructure/

7. **LangChain Engineering.** (2026). "Improving Deep Agents with harness engineering." *LangChain Blog*, February 17, 2026. https://blog.langchain.com/improving-deep-agents-with-harness-engineering/

### Supplementary Sources

8. **Hashimoto, M.** (2026). "My AI Adoption Journey." https://mitchellh.com/writing/my-ai-adoption-journey

9. **Huntley, G.** (2025–2026). "Ralph Wiggum Loop / How to Ralph Wiggum." https://ghuntley.com/ralph/ ; https://github.com/ghuntley/how-to-ralph-wiggum

10. **Horthy, D.** (2026). "Advanced Context Engineering for Coding Agents." *HumanLayer Blog*. https://www.hlyr.dev/blog/advanced-context-engineering

11. **Tane, B.** (2026). "How I Use Claude Code." *Boris Tane Blog*. https://boristane.com/tags/agents

12. **Brockman, G.** (2026). Agent-first engineering recommendations thread, cited in Guo (2026) and MoneyControl (2026).

13. **Steinberger, P.** (2026). OpenClaw development practices, documented in *The Pragmatic Engineer* and *TeamDay.ai*. https://petersteinberger.com/

14. **Vasilopoulos, A.** (2026). "Codified Context: Infrastructure for AI Agents in a Complex Codebase." *arXiv:2602.20478*. https://arxiv.org/abs/2602.20478

15. **Osmani, A.** (2026). "The 80% Problem in Agentic Coding." *Addy Osmani Substack*. https://addyo.substack.com/p/the-80-problem-in-agentic-coding

16. **Fowler, C.** (2026). "Relocating Rigor." Referenced in Böckeler (2026) and Martin Fowler Fragments.

17. **Trivedy, V.** (2026). "The Anatomy of an Agent Harness." *LangChain Blog*. https://blog.langchain.com/the-anatomy-of-an-agent-harness/

18. **Pappas, E.** (2026). "The Agent Harness Is the Architecture (and Your Model Is Not the Bottleneck)." *Medium*. https://medium.com/@epappas/the-agent-harness-is-the-architecture-and-your-model-is-not-the-bottleneck-5ae5fd067bb2

19. **Mirji, V.** (2026). "Build the harness, not the code: a staff/principal engineer's guide to AI-agent systems." https://vitthalmirji.com/2026/02/build-the-harness-not-the-code-a-staff/principal-engineers-guide-to-ai-agent-systems/

20. **Jozefiak, P.** (2026). "How I Structure CLAUDE.md After 1000+ Sessions." *Substack*. https://substack.com/home/post/p-189453314

21. **Vercel Engineering.** (2025). "We removed 80% of our agent's tools." *Vercel Blog*, December 22, 2025. https://vercel.com/blog/we-removed-80-percent-of-our-agents-tools

22. **Stripe Engineering.** (2026). "Minions: Stripe's one-shot, end-to-end coding agents." Documented at https://www.engineering.fyi/article/minions-stripe-s-one-shot-end-to-end-coding-agents

23. **METR.** (2026). "Measuring Time Horizon using Claude Code and Codex." https://metr.org/notes/2026-02-13-measuring-time-horizon-using-claude-code-and-codex/

24. **Fowler, M. / Böckeler, B.** (2026). "Humans and Agents in Software Engineering Loops." *Martin Fowler — Exploring Gen AI*. https://martinfowler.com/articles/exploring-gen-ai/humans-and-agents.html

25. **Fowler, M. / Böckeler, B.** (2026). "Context Engineering for Coding Agents." *Martin Fowler — Exploring Gen AI*. https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html

26. **Trajan, M.** (2026). "Harness Engineering Is Not Context Engineering." *Substack*. https://mtrajan.substack.com/p/harness-engineering-is-not-context

27. **AGENTS.md.** (2025–2026). Open convention for AI coding agent instructions. https://agents.md/

28. **Gupta, A.** (2026). "2025 was the year of agents. 2026 is the year of agent harnesses." *Substack note*. https://substack.com/@aakashgupta/note/c-196151948

29. **Gloaguen, T., Mündler, N., Müller, M., Raychev, V., & Vechev, M.** (2026). "Understanding the Effect of AGENTS.md-Style Instruction Files on Coding Agents." *SRI Lab, ETH Zurich. arXiv:2602.11988*. https://arxiv.org/abs/2602.11988
