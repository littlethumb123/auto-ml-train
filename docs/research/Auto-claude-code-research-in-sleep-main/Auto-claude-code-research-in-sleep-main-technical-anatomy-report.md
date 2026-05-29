# ARIS (Auto-claude-code-research-in-sleep) Technical Anatomy: A Comprehensive System Design Report

**Report Type:** Deep Technical Analysis & Engineering Assessment  
**Subject:** An autonomous ML research harness that orchestrates the complete research lifecycle — from idea discovery to peer-review rebuttal — using cross-model adversarial collaboration  
**Repository:** `/home/jupyter/Thinkubator/auto_train/references/Auto-claude-code-research-in-sleep-main`  
**Date:** April 20, 2026  
**Methodology:** Multi-Lens Repo Deep Dive (Structure, Logic, Agentic, Patterns, Systems)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [First Impressions](#2-first-impressions)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Technical Deep Dive](#4-technical-deep-dive)
5. [Extracted Patterns & Innovations](#5-extracted-patterns--innovations)
6. [Engineering Assessment](#6-engineering-assessment)
7. [Industry Alignment Analysis](#7-industry-alignment-analysis)
8. [Critical Findings & Recommendations](#8-critical-findings--recommendations)
9. [Transferable Insights](#9-transferable-insights)
10. [Self-Validation](#10-self-validation)

---

## 1. Executive Summary

ARIS is a **plugin-based skill orchestra** that decomposes the ML research lifecycle into ~65 composable Markdown-defined skills, chained through four major workflows: Idea Discovery (W1), Experiment Implementation (W1.5), Iterative Review (W2), and Paper Writing + Rebuttal (W3/W4). Its defining architectural innovation is **cross-model adversarial collaboration**: a fast executor agent (Claude Code) generates artifacts while a rigorous reviewer agent (GPT-5.4 via MCP) independently evaluates them, creating a 2-player game whose convergence criterion is a reviewer score ≥ 6/10.

The system is radically file-based — skills communicate via versioned Markdown artifacts (IDEA_REPORT.md, EXPERIMENT_PLAN.md, AUTO_REVIEW.md), not APIs or databases. This makes the system human-debuggable, platform-agnostic (runs on Claude Code, Cursor, Trae, Codex CLI, OpenClaw), and resilient to LLM context window compaction through a multi-layered state persistence strategy.

The top three transferable insights are: (1) **cross-model adversarial pairing** as a systematic alternative to self-review, with enforced reviewer independence protocols; (2) **file-based artifact contracts** as the coordination mechanism for multi-phase agent workflows; and (3) **hard invariants + soft knobs** as a constraint specification pattern where safety guarantees never flex while resource intensity scales from lite (0.4x) to beast (5-8x).

---

## 2. First Impressions

### 2.1 Scale & Maturity

- **306 total files**, 249 source/doc files (Markdown, Python, JSON, shell)
- **~64,800 lines** of content across all file types
- **65+ skills** covering the full research lifecycle plus patent writing, GPU orchestration, and meta-optimization
- **5 MCP server implementations** (codex-review, gemini-review, llm-chat, minimax-chat, feishu-bridge)
- **18 templates**, **16 shared reference policies**, **24 documentation guides**
- Evidence of significant iteration: community papers exist as worked examples, multiple platform adaptation guides (Cursor, Trae, Antigravity, OpenClaw), and a meta-optimization skill that improves the harness itself from usage logs

### 2.2 Feature Breadth

The feature inventory is remarkably dense for a "prompt-based" system:

| Category | Count | Examples |
|----------|-------|---------|
| Research skills | ~15 | literature search, idea discovery, novelty check, research review |
| Experiment skills | ~10 | experiment bridge, queue, monitor, audit, ablation planner |
| Writing skills | ~12 | paper plan, write, compile, figure, illustration, slides, poster |
| Review/audit skills | ~8 | auto-review-loop, paper-claim-audit, citation-audit, proof-checker |
| Infrastructure skills | ~8 | experiment-queue, serverless-modal, vast-gpu, overleaf-sync |
| Meta/knowledge skills | ~5 | research-wiki, meta-optimize, training-check, analyze-results |
| MCP servers | 5 | codex, gemini, llm-chat, minimax, feishu |
| Shared references | 16 | reviewer-independence, experiment-integrity, citation-discipline |

### 2.3 Code Quality Signals

- **Naming**: Consistent hyphenated skill names (`auto-review-loop`, `experiment-bridge`), UPPER_CASE artifact names (`IDEA_REPORT.md`, `EXPERIMENT_PLAN.md`)
- **Documentation density**: Every skill has a SKILL.md with YAML frontmatter (name, description, allowed-tools, argument-hint), workflow phases, constants, and output contracts
- **Type safety**: N/A — system is primarily Markdown-based; Python components (MCP servers, tools) are minimal
- **Testing**: Present but limited to infrastructure (MCP servers, fetchers); no end-to-end workflow tests (Testing Maturity: 2/4)
- **Shared protocols**: 16 cross-cutting policy documents enforce reviewer independence, experiment integrity, citation discipline, and output versioning across all skills

### 2.4 Questions Raised

1. How does the adversarial review loop actually converge — what prevents infinite oscillation between executor fixes and reviewer demands?
2. How resilient is the context recovery system when a session crashes mid-experiment on a remote GPU server?
3. What are the failure modes when executor and reviewer fundamentally disagree (score stalls at 4/10)?
4. How does the skill composition system handle error propagation across a 5-phase pipeline?
5. Can the meta-optimization skill actually improve the harness in practice, or is it aspirational?
6. How does the system handle the cold-start problem (new project, no prior data)?

---

## 3. System Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARIS: System Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐    │
│  │  DISCOVERY MESH   │     │  EXECUTION MESH   │     │  WRITING MESH    │    │
│  │  (W1)             │────▶│  (W1.5 + W2)      │────▶│  (W3 + W4)      │    │
│  │                   │     │                   │     │                   │    │
│  │  research-lit     │     │  experiment-bridge│     │  paper-plan      │    │
│  │  idea-creator     │     │  run-experiment   │     │  paper-write     │    │
│  │  novelty-check    │     │  experiment-queue │     │  paper-compile   │    │
│  │  research-review  │     │  auto-review-loop │     │  paper-claim-audit│   │
│  │  research-refine  │     │  experiment-audit │     │  citation-audit  │    │
│  └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘    │
│           │                         │                         │              │
│     IDEA_REPORT.md          EXPERIMENT_LOG.md           paper/main.tex      │
│     research_contract.md    AUTO_REVIEW.md              paper/main.pdf      │
│                             REVIEW_STATE.json            PASTE_READY.txt    │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    CROSS-CUTTING CONCERNS                            │   │
│  │  CLAUDE.md (Pipeline Status) │ shared-references/ (16 policies)     │   │
│  │  research-wiki/ (knowledge)  │ MANIFEST.md (output versioning)      │   │
│  │  meta-optimize (self-improve)│ watchdog.py (monitoring)             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    EXTERNAL MODEL BRIDGES (MCP)                      │   │
│  │  Codex MCP (GPT-5.4 xhigh) │ Oracle MCP (GPT-5.4 Pro)             │   │
│  │  Gemini MCP (image gen)     │ LLM-Chat MCP (generic OpenAI-compat) │   │
│  │  Feishu Bridge (notifications)                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent Runtime | Claude Code / Cursor / Trae / Codex CLI / OpenClaw | Executor agent (skill invocation, code generation, writing) |
| Review Bridge | Codex MCP (GPT-5.4 xhigh via npm) | External reviewer (adversarial scoring, weakness identification) |
| Alternative Reviewers | Oracle MCP, Gemini MCP, LLM-Chat MCP | Optional reviewer backends (GPT-5.4 Pro, Gemini, MiniMax, GLM, DeepSeek) |
| Image Generation | Gemini 2.0 Flash, DALL-E 3 | Paper illustrations and method diagrams |
| Paper Compilation | LaTeX (pdflatex/xelatex), natbib/cite | PDF generation with multi-pass reference resolution |
| Bibliography | DBLP API, CrossRef API | Anti-hallucination citation fetching |
| Literature Search | arXiv API, Semantic Scholar, Exa, DeepXiv | Multi-source paper discovery with deduplication |
| GPU Monitoring | watchdog.py (Python), nvidia-smi | Server-side task monitoring (OOM detection, idle detection) |
| Experiment Queue | SSH, tmux/screen, SLURM-compatible | Multi-job scheduling with wave transitions and OOM retry |
| Knowledge Base | SQLite (research_wiki.py) + Markdown | Persistent memory with typed relationships (extends, contradicts, tested_by) |
| Configuration | .env file, CLAUDE.md Pipeline Status | API keys + project state + constraints (zero-config mode available) |
| State Persistence | Markdown + JSON snapshots | Session recovery after context compaction (timestamped backups) |
| Skill Framework | Plain Markdown + YAML frontmatter | No framework dependency; readable by any LLM |

### 3.3 Module Dependency Map

```
Skills (65+)
  ├── read ──▶ shared-references/ (16 policy docs)
  ├── invoke ──▶ MCP servers (codex, gemini, llm-chat, minimax, feishu)
  ├── write ──▶ Artifact files (IDEA_REPORT, EXPERIMENT_LOG, AUTO_REVIEW, etc.)
  ├── read ──▶ Templates (18 input/output format templates)
  └── call ──▶ Tools (arxiv_fetch.py, deepxiv_fetch.py, figure_renderer.py, etc.)

Orchestrator skills (research-pipeline, experiment-bridge)
  └── chain ──▶ Sub-skills (idea-discovery → experiment-plan → run-experiment → ...)

MCP Servers
  └── bridge ──▶ External LLM APIs (OpenAI, Google Gemini, MiniMax, Feishu)

State Files (on disk)
  ├── CLAUDE.md ──▶ read by every session start (30-sec orientation)
  ├── REVIEW_STATE.json ──▶ read by auto-review-loop on recovery
  └── research-wiki/ ──▶ read by idea-creator, research-lit (persistent memory)
```

**Dependency direction**: Skills depend on shared-references (read-only). Skills write artifacts. Downstream skills read upstream artifacts. MCP servers are stateless adapters. No circular dependencies.

### 3.4 Entry Point Chain

```
User Invocation
    │
    ▼
/research-pipeline "topic" — effort: max, venue: NeurIPS
    │
    ├──▶ /idea-discovery (W1)
    │     ├── /research-lit → papers/
    │     ├── /idea-creator → IDEA_REPORT.md (12 ideas)
    │     ├── /novelty-check → novelty verdicts
    │     ├── /research-review (GPT-5.4) → scored ideas
    │     └── /research-refine-pipeline → EXPERIMENT_PLAN.md
    │
    │     🚦 GATE 1: AUTO_PROCEED or human picks idea
    │
    ├──▶ /experiment-bridge (W1.5)
    │     ├── Parse EXPERIMENT_PLAN.md
    │     ├── Implement code
    │     ├── GPT-5.4 code review
    │     └── Deploy via /run-experiment or /experiment-queue
    │
    ├──▶ /auto-review-loop (W2, ≤4 rounds)
    │     ├── Round N: GPT reviews → score + weaknesses
    │     ├── Claude fixes weaknesses
    │     ├── Re-deploy experiments if needed
    │     └── Loop until score ≥6/10 or max rounds
    │
    ├──▶ /paper-plan → /paper-write → /paper-compile (W3)
    │     ├── /auto-paper-improvement-loop (2 rounds)
    │     ├── /paper-claim-audit (zero-context number check)
    │     └── /citation-audit (DBLP/CrossRef verification)
    │
    └──▶ /rebuttal (W4, post-review)
          ├── Atomize reviewer concerns
          ├── Strategy → draft → stress-test
          └── PASTE_READY.txt (under char limit)
```

---

## 4. Technical Deep Dive

### 4.1 Skill System

**Location:** `skills/` (65+ directories, each containing a SKILL.md)

#### Architecture

Each skill is a standalone Markdown file with YAML frontmatter defining its contract:

```yaml
---
name: auto-review-loop
description: "Iterative review-fix-re-review loop with cross-model reviewer"
argument-hint: "research topic or paper description"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Agent, mcp__codex__codex
---
```

Skills are discovered by the host agent platform (Claude Code, Cursor, etc.) via filesystem scanning of `~/.claude/skills/` or `.agents/skills/`. No registry, no compilation, no runtime dependency.

#### Key Mechanisms

**Slash-command invocation**: Users invoke skills via `/skill-name "args" — param: value`. The agent platform loads the SKILL.md, interprets it as instructions, and executes the workflow.

**Parameter pass-through**: Orchestrator skills pass parameters to all sub-skills automatically:
```
/research-pipeline "topic" — effort: max, reviewer: oracle-pro
  → /idea-discovery receives effort=max
  → /auto-review-loop receives effort=max, reviewer=oracle-pro
  → /paper-write receives effort=max
```

**Effort-level knobs** (defined in `skills/shared-references/effort-contract.md`):
- `lite` (0.4x): 6-8 papers, 2 review rounds
- `balanced` (1x): 10-15 papers, 3-4 review rounds (default)
- `max` (2.5x): 18-25 papers, 6 review rounds
- `beast` (5-8x): 40-50 papers, 8+ review rounds

**Hard invariants** that never change regardless of effort:
- Codex reasoning = `xhigh` (reviewer quality non-negotiable)
- DBLP/CrossRef citations = always on (anti-hallucination)
- Reviewer independence = always enforced
- Experiment integrity audits = always run

#### Notable Decisions

The choice to encode skills as Markdown instructions rather than executable code is deliberate:
- **Platform-agnostic**: Any LLM that can read Markdown can execute skills
- **Human-auditable**: Non-engineers can read and understand what the system does
- **Fork-friendly**: Users customize by editing Markdown, not code
- **Trade-off**: No type checking, no compile-time guarantees, no unit testing of skill logic

### 4.2 Cross-Model Adversarial Review System

**Location:** `skills/auto-review-loop/SKILL.md`, `skills/shared-references/reviewer-independence.md`

#### Architecture

The review system implements a 2-player adversarial game:

```
┌────────────────────┐          ┌────────────────────┐
│  EXECUTOR (Claude)  │          │  REVIEWER (GPT-5.4) │
│  • Creates code     │          │  • Scores work       │
│  • Fixes issues     │  ◀────▶ │  • Finds weaknesses  │
│  • Writes narrative │          │  • Demands evidence   │
│  • Implements fixes │          │  • Judges if fixed    │
└────────────────────┘          └────────────────────┘
        │                                │
        ▼                                ▼
   ARTIFACT FILES                   MCP BRIDGE
   (code, results,                  (Codex MCP,
    paper draft)                    fresh threads)
```

#### Key Mechanisms

**Reviewer Independence Protocol** (`skills/shared-references/reviewer-independence.md`):

What the executor CAN send to the reviewer:
- File paths for direct reading
- Review objective
- Structural metadata ("paper has 8 sections")
- Venue constraints

What the executor CANNOT send:
- Summaries or interpretations of their own work
- Previous round scores (let reviewer judge fresh)
- Leading questions ("Is this publishable?")
- Executor's recommendations or fix descriptions

**Difficulty levels** modulate reviewer adversarial intensity:
- `medium`: Standard MCP review, fresh thread each round
- `hard`: + reviewer memory tracking + debate protocol (executor rebuts, reviewer rules)
- `nightmare`: + GPT reads the entire repo directly (no Claude filtering at all)

**Convergence mechanism**: The loop stops when:
- Score ≥ 6/10 AND verdict is "ready" or "almost" → STOP (success)
- Max rounds reached (default 4, configurable) → STOP (budget exhausted)
- 3+ consecutive rounds with no improvement → STOP (patience exhausted)

**State persistence for crash recovery** (`REVIEW_STATE.json`):
```json
{
  "round": 2,
  "threadId": "019cd392-...",
  "status": "in_progress",
  "last_score": 5.0,
  "pending_experiments": ["exp_001"],
  "timestamp": "2026-03-13T21:00:00Z"
}
```

If context is compacted or session crashes, the next session reads this JSON, recovers the round counter and thread ID, reads AUTO_REVIEW.md for full history, and resumes from the next round.

### 4.3 Integrity Audit Cascade

**Location:** `skills/experiment-audit/`, `skills/result-to-claim/`, `skills/paper-claim-audit/`, `skills/citation-audit/`, `skills/proof-checker/`

#### Architecture

A 6-layer validation stack where each layer uses a **fresh reviewer with no context from prior layers**:

```
Layer 1: CODE AUDIT ──────── GPT reads code, checks for fraud patterns
    ↓
Layer 2: EXPERIMENT AUDIT ── GPT checks: fake GT, score normalization, phantom results
    ↓
Layer 3: RESULT-TO-CLAIM ─── GPT maps claims to raw result files
    ↓
Layer 4: PAPER CLAIM AUDIT ─ Zero-context GPT reads .tex + result files directly
    ↓
Layer 5: CITATION AUDIT ──── GPT + web access verifies every \cite exists
    ↓
Layer 6: PROOF CHECKER ───── GPT checks theorem proofs (20-category taxonomy)
```

#### Key Mechanisms

**Zero-context audit** (Layer 4): The reviewer receives ONLY the .tex source files and raw result files. It is NOT given the executor's EXPERIMENT_LOG.md, AUTO_REVIEW.md, or any summaries. This prevents correlated blind spots — if the executor's framing is wrong, the reviewer catches it because it reads raw data independently.

**Proof checker two-axis severity** (Layer 6):
- Axis A (Proof Status): INVALID | UNJUSTIFIED | UNDERSTATED | OVERSTATED | UNCLEAR
- Axis B (Impact): GLOBAL | LOCAL | COSMETIC
- Derived severity: FATAL (INVALID+GLOBAL) through COSMETIC (UNCLEAR+COSMETIC)

**Fraud pattern detection** (Layer 2): The experiment audit specifically checks for:
- Fake ground truth (creating synthetic GT from model outputs)
- Score normalization fraud (dividing by model's own max value)
- Phantom results (claiming numbers from nonexistent files)
- Insufficient scope (labeling a pilot as "comprehensive evaluation")

### 4.4 MCP Server System

**Location:** `mcp-servers/` (5 server implementations)

#### Architecture

All MCP servers follow a common pattern: JSON-RPC over stdin/stdout, environment-based configuration, stateless operation, and retry-with-fallback error handling.

```
┌─────────────────────────────────────────┐
│            Claude Code Agent             │
└──────────────┬──────────────────────────┘
               │ tool calls
    ┌──────────┴──────────────────────┐
    │                                  │
┌───▼──────┐  ┌──────────┐  ┌────────▼───┐
│Codex MCP │  │Oracle MCP│  │Gemini/Local│
│GPT-5.4   │  │GPT-5.4Pro│  │Alternative │
│(DEFAULT)  │  │(optional)│  │Reviewers   │
└──────────┘  └──────────┘  └────────────┘
```

**Key implementation** (`mcp-servers/llm-chat/server.py`):
```python
API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
FALLBACK_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "gpt-4o")

# Retry strategy: original model → retry same → fallback model
for attempt in range(3):
    current_model = use_model if attempt < 2 else FALLBACK_MODEL
    response = post(...)
    if response.status_code == 504:
        continue  # retry or fallback
```

**Conversation threading**:
- `mcp__codex__codex`: New thread (fresh context, no prior conversation)
- `mcp__codex__codex-reply`: Reply in existing thread (maintains conversation context)
- Fresh threads are used for audit steps; reply threads for iterative review rounds

### 4.5 Context Management & Recovery

**Location:** `docs/SESSION_RECOVERY_GUIDE.md`, `docs/PROJECT_FILES_GUIDE.md`, `templates/CLAUDE_MD_TEMPLATE.md`

#### Architecture: Three-Layer Context System

```
Layer 1: CLAUDE.md Pipeline Status (30-second orientation)
  ├── stage: which workflow phase
  ├── idea: one-line current idea  
  ├── training_status: is anything running?
  ├── active_tasks: SSH commands to check status
  └── next: concrete next action

Layer 2: Active Artifact (loaded per-workflow)
  └── idea-stage/docs/research_contract.md
      (one-page focused context for chosen idea)

Layer 3: Stage-Specific State (loaded per-skill)
  ├── REVIEW_STATE.json (round, threadId, score, recovery)
  └── AUTO_REVIEW.md (full history of all rounds)

Layer 4: Discovery Log (append-only)
  └── findings.md (anomalies, root causes, decisions)
```

#### Key Mechanisms

**Compaction survival**: When Claude Code's context window fills up:
1. Pre-compact hook fires → agent saves current state to CLAUDE.md
2. Context is compacted (all prior messages discarded)
3. Session-restore hook fires → reads CLAUDE.md Pipeline Status → informs agent
4. Agent reads recovery files and resumes from where it left off

**Recovery time**: < 1 minute to fully re-orient (read 3-5 files, parse JSON, resume)

**Versioning protocol** (`skills/shared-references/output-versioning.md`):
```bash
# Write timestamped copy (immutable)
cp AUTO_REVIEW.md AUTO_REVIEW.2026-04-20T14-32-15Z.md
# Update fixed-name copy (latest)
ln -sf AUTO_REVIEW.2026-04-20T14-32-15Z.md AUTO_REVIEW.md
```

This ensures downstream skills always read the latest version via the fixed name, while audit trails and rollback are always available via timestamped versions.

### 4.6 Experiment Queue & GPU Orchestration

**Location:** `skills/experiment-queue/SKILL.md`, `skills/run-experiment/SKILL.md`, `skills/monitor-experiment/SKILL.md`, `tools/watchdog.py`

#### Architecture

```
Local Machine                        Remote GPU Server
┌────────────────────┐               ┌────────────────────┐
│ /experiment-queue  │──── SSH ──────▶│ tmux/screen sessions│
│ (skill orchestrator)│               │ (training jobs)     │
│                    │               │                     │
│ /monitor-experiment│──── SSH ──────▶│ watchdog.py         │
│ (status polling)   │               │ (continuous monitor) │
└────────────────────┘               └────────────────────┘
```

**Job scheduling with YAML manifest**:
```yaml
gpus: [0, 1, 2, 3]
max_parallel: 4
gpu_free_threshold_mib: 500
oom_retry:
  max_attempts: 3
```

**Wave transitions**: All jobs in phase N must complete before phase N+1 starts. Supports teacher→student dependency chains (e.g., pretrain teacher then distill student).

**Failure modes** handled by watchdog.py:
- DEAD: session gone (OOM kill, network timeout) → restart
- IDLE: session alive but GPU < 5% utilization → alert
- STALLED: download file not growing → check network/auth
- FAILED_OOM: explicit CUDA error → auto-retry with smaller batch

### 4.7 Research Wiki & Knowledge Persistence

**Location:** `skills/research-wiki/SKILL.md`, `tools/research_wiki.py`

#### Architecture

A SQLite-backed knowledge graph with typed relationships:

```
Entity Types: Paper, Idea, Experiment, Claim
Relationship Types: extends, contradicts, inspired_by, tested_by, supports, invalidates

Example:
  Paper("FactDiff2025") --extends--> Paper("DDPMs2020")
  Idea("factorized-attention") --inspired_by--> Paper("FactDiff2025")
  Experiment("exp_001") --tested_by--> Idea("factorized-attention")
  Claim("15% FID improvement") --supports--> Experiment("exp_001")
```

**Cross-skill integration**: `/research-lit` and `/idea-creator` are wiki-aware — they check existing entries before creating duplicates, and failed experiments become anti-repetition memory.

### 4.8 Meta-Optimization

**Location:** `skills/meta-optimize/SKILL.md`, `tools/meta_opt/`

#### Architecture

A self-improvement loop that analyzes harness usage logs and proposes SKILL.md patches:

```
┌─────────────────────────┐
│ Passive Event Logging   │
│ (.aris/meta/events.jsonl)│
│ via Claude Code hooks    │
└──────────┬──────────────┘
           ↓
┌──────────────────────────┐
│ /meta-optimize           │
│ Reads: event log         │
│ Analyzes: failure modes, │
│   parameter overrides,   │
│   timing patterns        │
│ Proposes: SKILL.md edits │
└──────────┬──────────────┘
           ↓
┌──────────────────────────┐
│ Human review + apply     │
│ (never auto-applied)     │
│ Backup always kept       │
└──────────────────────────┘
```

**Invariants**: Minimum 5 skill invocations before recommending changes. Proposed patches are cross-model reviewed. User must approve each patch. Backup of original SKILL.md always preserved.

---

## 5. Extracted Patterns & Innovations

### 5.1 Cross-Model Adversarial Collaboration

**Category:** Architectural / Agentic  
**Location:** `skills/auto-review-loop/SKILL.md`, `skills/shared-references/reviewer-independence.md`  
**The Pattern:** Pair a fast, creative executor (Claude) with a slow, rigorous reviewer (GPT-5.4) where the reviewer has no access to the executor's interpretations — only raw artifacts. The review loop converges via score thresholds with patience-based early stopping.  
**Why It's Notable:** Single-model self-review suffers from correlated failure modes (the model can't find its own blind spots). Cross-model pairing with enforced independence creates genuinely adversarial evaluation. Typical score progression: 3-4/10 → 7-8/10 over 3-4 rounds.  
**Transferability:** HIGH — applicable to any multi-model system. The key insight is that reviewer independence must be *enforced by protocol* (file paths only, no summaries), not just *suggested* (which models will silently violate).

### 5.2 File-Based Artifact Contracts

**Category:** Architectural  
**Location:** System-wide (all skills read/write Markdown artifacts)  
**The Pattern:** Skills communicate exclusively via versioned Markdown and JSON files on disk. Each artifact has a fixed name (read by downstream skills) and timestamped versions (for audit/rollback). No databases, no message queues, no RPC.  
**Why It's Notable:** This makes the system: (a) human-debuggable (read the files to understand state), (b) crash-resistant (files survive context compaction), (c) platform-agnostic (works on any filesystem), (d) version-controllable (git-trackable artifacts).  
**Transferability:** HIGH — any multi-phase agent system can adopt this pattern. The critical insight is that fixed-name + timestamped versions solves both the "latest reference" and "audit trail" problems simultaneously.

### 5.3 Hard Invariants + Soft Knobs

**Category:** Engineering Practice  
**Location:** `skills/shared-references/effort-contract.md`  
**The Pattern:** Separate constraints into two categories: hard invariants that NEVER change (reviewer quality, fraud prevention, citation verification) and soft knobs that scale linearly (papers searched, review rounds, iterations). Effort levels (lite/balanced/max/beast) only affect soft knobs.  
**Why It's Notable:** Prevents "budget mode" from silently degrading safety. Most systems make all parameters equally configurable, creating failure modes when users minimize for speed.  
**Transferability:** HIGH — applicable to any configurable system with safety-critical properties.

### 5.4 Zero-Context Reviewer Isolation

**Category:** Agentic  
**Location:** `skills/paper-claim-audit/SKILL.md`, `skills/shared-references/reviewer-independence.md`  
**The Pattern:** For critical audits, the reviewer is given ONLY raw file paths — no prior context, no executor summaries, no previous feedback. It reads source files directly and forms its own conclusions.  
**Why It's Notable:** Even with cross-model review, if the executor pre-digests content, it creates a framing bias. Zero-context isolation forces the reviewer to discover issues independently, catching problems the executor's framing might obscure.  
**Transferability:** MEDIUM — requires careful RPC/tool design to prevent accidental context leakage.

### 5.5 Deterministic Figure Generation (FigureSpec)

**Category:** Algorithmic  
**Location:** `tools/figure_renderer.py`  
**The Pattern:** JSON specification → deterministic SVG rendering. No API calls, no non-deterministic components. Figures are fully reproducible from their spec.  
**Why It's Notable:** Solves the problem that AI-generated illustrations (Gemini, DALL-E) are non-deterministic and not version-controllable. A JSON spec can be diffed, reviewed, and regenerated identically.  
**Transferability:** HIGH — applicable to any document generation pipeline requiring reproducible figures.

### 5.6 Research Wiki with Typed Relationships

**Category:** Algorithmic / Architectural  
**Location:** `skills/research-wiki/SKILL.md`, `tools/research_wiki.py`  
**The Pattern:** SQLite-backed knowledge graph where entities (papers, ideas, experiments, claims) are linked by typed relationships (extends, contradicts, inspired_by, tested_by). Wiki-aware skills check existing entries before creating duplicates; failed experiments become anti-repetition memory.  
**Why It's Notable:** Solves the "agent amnesia" problem where each session starts from scratch. Failed approaches are remembered, preventing wasteful repetition.  
**Transferability:** MEDIUM — the relationship types are domain-specific, but the pattern of persistent typed knowledge graphs is broadly applicable.

### 5.7 Rebuttal Atomization

**Category:** Algorithmic  
**Location:** `skills/rebuttal/SKILL.md`  
**The Pattern:** Parse reviewer comments into atomic tuples: `(reviewer_id, concern_type, severity, response_mode, status)`. Each concern is independently routed with safety gates (provenance, commitment, coverage) before final assembly.  
**Why It's Notable:** Most rebuttal systems treat reviewer feedback as unstructured text. Atomization enables systematic response that ensures no concern is missed (coverage gate) and no claim is unsupported (provenance gate).  
**Transferability:** MEDIUM — applicable to any system that must respond to structured criticism (code review, customer complaints, compliance responses).

---

## 6. Engineering Assessment

### 6.1 Strengths

- **Radical composability**: 65+ skills can be used standalone or chained into multi-phase pipelines. Adding a new skill requires only creating a SKILL.md file — no code changes, no registry updates.
- **Cross-model integrity**: The reviewer independence protocol and 6-layer audit cascade create genuine adversarial evaluation, not performative self-review.
- **Crash resilience**: Context compaction is handled gracefully via file-based state + session recovery hooks. Recovery time < 1 minute.
- **Platform agnosticism**: The same skills work on Claude Code, Cursor, Trae, Codex CLI, and OpenClaw with minimal adaptation (platform-specific docs provided).
- **Human-debuggability**: All state is in human-readable Markdown/JSON files. No opaque databases or binary state.
- **Safety-first configuration**: Hard invariants prevent quality degradation even at minimum effort levels.

### 6.2 Weaknesses / Gaps

- **No runtime type checking**: Skills are Markdown instructions interpreted by LLMs. A typo in a skill won't be caught until runtime (and the LLM might silently interpret it differently).
- **No end-to-end testing**: The test suite covers infrastructure (MCP servers, fetchers) but NOT skill orchestration, artifact passing, or state recovery. Regressions in skill logic are caught only by human observation or cross-model audit.
- **No centralized error logging**: Errors are logged per-skill in scattered files. No unified error dashboard or alerting beyond watchdog.py for experiment monitoring.
- **Security surface**: API keys in `.env` with no rotation policy. SSH keys assumed pre-configured. No audit logging of what data is sent to external LLM APIs (optional via review-tracing.md but not enforced).
- **Single-project scope**: ARIS runs one research project per invocation. No built-in support for managing multiple concurrent research threads.
- **MCP server documentation gap**: No guide for developing new MCP server backends, making it difficult for contributors to extend the reviewer ecosystem.

### 6.3 Testing Maturity

**Rating: 2/4 (Solid infrastructure tests, no workflow tests)**

| Component | Test Coverage | Notes |
|-----------|-------------|-------|
| Feishu bridge | ✅ Unit tests | Pure-Python logic testing |
| LLM chat server | ✅ Unit tests | API call logic, fallback strategy |
| MiniMax integration | ✅ Integration tests | Streaming response handling |
| DeepXiv fetch | ✅ Unit tests | Progressive retrieval mock |
| Exa search | ✅ Unit tests | API wrapper |
| Watchdog | ✅ Unit tests | File monitoring |
| Skill orchestration | ❌ None | No tests for W1→W2→W3 pipeline |
| State recovery | ❌ None | No tests for REVIEW_STATE.json recovery |
| Artifact contracts | ❌ None | No validation of artifact format compliance |

**Testing philosophy**: ARIS relies on cross-model audit and reviewer independence as the primary bug-catching mechanism, rather than traditional unit/integration tests for skill logic. This is a deliberate trade-off — testing Markdown-based skill instructions is fundamentally different from testing code.

### 6.4 Error Handling Assessment

**Strategy: Graduated retry with cross-model escalation**

- **Experiment layer**: Auto-debug 3x for OOM/import/CUDA errors. Graceful degradation (skip non-critical experiments). Rollback on failure (`git reset --hard HEAD~1`).
- **Review layer**: REVIEW_STATE.json persistence for crash recovery. Staleness detection (>24 hours = start fresh). Max rounds as budget cap.
- **Writing layer**: Multi-pass pdflatex (3 passes) for reference resolution. Auto-repair BibTeX on missing citations. Overfull box detection blocks submission.
- **Cross-model escalation**: If executor fails, reviewer can diagnose via `/codex:rescue` (GPT reads code and suggests fixes).
- **Gap**: No circuit breaker pattern. A failing MCP server will retry 3 times and then fail hard — no graceful fallback to local review.

### 6.5 Observability Assessment

- **State visibility**: Excellent — all state is human-readable Markdown/JSON on disk
- **Experiment monitoring**: Good — watchdog.py provides continuous GPU monitoring with IDLE/STALLED/DEAD alerts
- **Workflow progress**: Moderate — CLAUDE.md Pipeline Status tracks current phase but no timeline/gantt visualization
- **Audit trail**: Good — MANIFEST.md tracks all outputs; review-tracing.md enables full prompt/response archival
- **Metrics/dashboards**: Missing — no aggregated metrics, no latency tracking, no cost tracking per experiment
- **Alerting**: Partial — Feishu bridge enables mobile alerts but only for experiment events, not workflow failures

---

## 7. Industry Alignment Analysis

### Where ARIS Leads

1. **Cross-model adversarial review**: Most AI research systems use single-model self-review or human-in-the-loop review. ARIS's enforced reviewer independence protocol with zero-context auditing is ahead of industry practice.

2. **File-based orchestration**: While the industry moves toward complex orchestration frameworks (LangChain, CrewAI, AutoGen), ARIS demonstrates that file-based artifact contracts are simpler, more debuggable, and more resilient. This is a contrarian bet that may prove prescient.

3. **Integrity audit cascade**: The 6-layer audit stack (code → experiments → claims → citations → proofs) is more thorough than any published autonomous research system.

4. **Effort knobs with safety invariants**: Most configurable systems treat all parameters equally. ARIS's separation into hard invariants (never flex) and soft knobs (scale freely) is a mature engineering pattern rarely seen in AI agent systems.

### Where ARIS Follows

1. **MCP protocol**: Uses the standard Model Context Protocol for cross-model communication (industry standard).
2. **Skill/plugin architecture**: The skill-per-directory pattern is common across agent frameworks.
3. **Session recovery**: File-based state persistence is a known pattern, though ARIS's multi-layer implementation is thorough.

### Where ARIS Diverges

1. **No database**: Most comparable systems use SQLite/Postgres for state management. ARIS uses only flat files.
2. **No execution framework**: Unlike LangChain, CrewAI, or AutoGen, ARIS has no Python framework — skills are purely Markdown instructions.
3. **Markdown-only contracts**: No JSON Schema, no protobuf, no type-safe contracts. This trades type safety for simplicity and platform agnosticism.

---

## 8. Critical Findings & Recommendations

### For Users of This Codebase

1. **Start with single skills, not the full pipeline**: `/research-lit "topic"` or `/auto-review-loop "paper"` work standalone. Don't attempt the full W1→W4 pipeline until you understand each phase.
2. **Always set up CLAUDE.md Pipeline Status**: This is the single most important recovery mechanism. Keep it updated after every major step.
3. **Use `effort: balanced` for first runs**: Beast mode is expensive and slow. Balanced provides good quality at reasonable cost.
4. **Configure reviewer independence correctly**: The most common misconfiguration is accidentally passing executor summaries to the reviewer. Let the MCP bridge handle file access directly.
5. **Monitor experiments actively**: The watchdog.py daemon catches DEAD/STALLED experiments early. Set up Feishu notifications for overnight runs.

### For Builders of Similar Systems

1. **Enforce reviewer independence at the protocol level, not the prompt level**: Prompts can be ignored; tool restrictions cannot. If your reviewer bridge only accepts file paths (not content), independence is guaranteed.
2. **Separate hard invariants from soft knobs early**: Decide which properties are safety-critical before building the configuration system. Retrofitting invariants is much harder.
3. **Use file-based state for agent orchestration**: Databases add complexity without proportional benefit for agent coordination. Files are debuggable, git-trackable, and survive any failure mode.
4. **Build the audit cascade before building the pipeline**: It's tempting to build the "happy path" first and add auditing later. ARIS demonstrates that the audit layer IS the value — without it, autonomous research is dangerously unreliable.
5. **Design for context compaction from day one**: Every agent session will eventually exceed its context window. If your system can't recover from a fresh start by reading disk state in < 1 minute, it's fragile.

---

## 9. Transferable Insights

### Insight 1: Adversarial Collaboration Beats Self-Review

**Principle:** When an agent reviews its own work, it reproduces its own blind spots. Cross-model review with enforced independence creates genuine adversarial evaluation.  
**Evidence:** ARIS's auto-review-loop shows consistent score progression from 3-4/10 to 7-8/10 over 3-4 rounds, with the reviewer catching issues the executor systematically misses.  
**Application:** In any multi-step AI system, designate a separate model (or at minimum a separate prompt/context) as reviewer, and enforce that it reads raw outputs rather than executor summaries.

### Insight 2: Files Are the Best Inter-Agent Communication Protocol

**Principle:** For multi-phase agent workflows, versioned files on disk are simpler, more debuggable, and more resilient than databases, message queues, or RPC.  
**Evidence:** ARIS's entire 4-workflow pipeline coordinates via ~15 named Markdown/JSON files. Crash recovery reads 3-5 files and resumes in < 1 minute.  
**Application:** When building multi-agent systems, use fixed-name files (for latest state) + timestamped copies (for audit trail) as the primary coordination mechanism. Add databases only when query patterns demand it.

### Insight 3: Safety Invariants Must Be Architecture, Not Configuration

**Principle:** Safety-critical properties (reviewer independence, fraud prevention, citation verification) must be hardcoded into the system architecture, not exposed as configurable parameters.  
**Evidence:** ARIS's "hard invariants" (reviewer always xhigh, DBLP always on, integrity always checked) are constants in skill definitions. Effort knobs scale everything else but can never disable safety.  
**Application:** In any configurable AI system, identify the 5-10 properties that must ALWAYS hold, and make them non-configurable constants. All other parameters can be knobs.

### Insight 4: Decompose Complex Tasks into Gated Phases

**Principle:** Large autonomous tasks should be decomposed into phases with explicit input/output contracts and optional human checkpoints (gates) between them.  
**Evidence:** ARIS's W1→W1.5→W2→W3→W4 pipeline with GATE 1 (idea selection) and GATE 2 (venue selection) allows human steering at critical decision points while keeping execution autonomous within each phase.  
**Application:** When building autonomous AI workflows, identify the 2-3 decisions that most benefit from human judgment and insert gates there. Make gates optional (AUTO_PROCEED) for fully autonomous operation.

### Insight 5: Persistent Knowledge Prevents Repeated Mistakes

**Principle:** Agent systems that don't remember failed approaches will repeatedly attempt them. Persistent knowledge graphs with typed relationships prevent wasteful repetition.  
**Evidence:** ARIS's research-wiki tracks papers, ideas, experiments, and claims with relationships like `contradicts`, `invalidates`, and `tested_by`. Failed experiments are remembered, and `/idea-creator` is wiki-aware.  
**Application:** When building iterative AI systems, create a persistent store of attempts and outcomes. Use typed relationships to capture not just what was tried but how it related to other attempts.

### Insight 6: Meta-Optimization Creates Self-Improving Harnesses

**Principle:** Logging agent actions and analyzing patterns enables the harness itself to improve over time, rather than only improving the work product.  
**Evidence:** ARIS's `/meta-optimize` skill analyzes event logs from passive hooks, identifies failure patterns and parameter overrides, and proposes SKILL.md patches based on empirical usage data.  
**Application:** In any production AI agent system, add passive event logging (skill invocations, parameter overrides, failure modes) and periodically analyze these logs to identify harness improvement opportunities.

### Insight 7: Platform Agnosticism Through Simplicity

**Principle:** Agent systems built on the simplest possible substrate (plain text files, standard protocols) are naturally portable across platforms.  
**Evidence:** ARIS's Markdown-based skills work on Claude Code, Cursor, Trae, Codex CLI, and OpenClaw with only documentation changes (no code changes). MCP provides the standard inter-model protocol.  
**Application:** When building agent infrastructure, resist the urge to add framework-specific features. Every framework-specific feature is a portability tax.

---

## 10. Self-Validation

### Analysis Methodology

- **Files examined**: ~80 files across skills/, mcp-servers/, tools/, tests/, docs/, and templates/
- **Analysis lenses applied**: Structure & Architecture, Core Logic & Algorithms, Agentic & Harness Engineering, Design Patterns & Practices, System Design & Scalability
- **Three parallel exploration agents** dispatched, each returning 300+ lines of structured findings
- **Cross-cut synthesis** performed across all agent findings before writing

### Confidence Levels

| Section | Confidence | Notes |
|---------|-----------|-------|
| Architecture overview | HIGH | Directory structure, skill system, and MCP architecture are unambiguous |
| Cross-model review system | HIGH | Well-documented in multiple files with clear protocols |
| Integrity audit cascade | HIGH | Each layer has dedicated skill with full documentation |
| Context management | HIGH | SESSION_RECOVERY_GUIDE.md provides extensive detail |
| Meta-optimization | MEDIUM | Skill exists and is documented but limited evidence of real-world usage impact |
| Testing assessment | HIGH | Test directory is small and exhaustively readable |
| Performance characteristics | LOW | No benchmarks or timing data in the repo; claims about "3-4/10 → 7-8/10" progression are from documentation, not verified logs |
| Security assessment | MEDIUM | Based on .env.example and MCP server code; no explicit security documentation to confirm or deny |

### Known Gaps

- **Community papers not analyzed**: The `community_papers/` directory likely contains worked examples that would validate the system's practical effectiveness
- **Real experiment logs not available**: The repo doesn't include actual REVIEW_STATE.json or AUTO_REVIEW.md from real runs, so recovery patterns are validated via documentation only
- **Cost analysis not possible**: No pricing data or cost tracking in the repo to assess economic viability of the cross-model approach
- **Codex-specific skills not analyzed**: `skills/skills-codex/` contains a parallel skill set for Codex CLI that was not compared against the main skill set
