# Human-in-the-Loop and Evaluation Gates for Autonomous ML Runners

**Date:** 2026-04-21
**Purpose:** Exhaustive cross-industry research on *where* humans are inserted into autonomous agent systems — with particular attention to evaluation — then specialized to an autonomous ML experiment/research runner. Produces a cited findings section and a **recommended gate map** for our hybrid-autonomy design.
**Companion docs:** `docs/research/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md`, `docs/research/literature_review/harness-engineering-literature-review.md`, `docs/research/AutoKaggle-main/AutoKaggle-main-harness-engineering-comparative-analysis.md`, `docs/research/Auto-claude-code-research-in-sleep-main/Auto-claude-code-research-in-sleep-main-technical-anatomy-report.md`, `docs/reflections/2026-04-21-design-principles-reflection.md`, `docs/brainstorming/2026-04-21-autonomous-ml-runner-brainstorm-handoff.md`.

---

## TL;DR

1. Across the 2026 industry corpus, human-in-the-loop (HITL) is not a single pattern. It fractures into **six distinct roles**: *permission / safety*, *strategic steering*, *planning approval*, *evaluation & acceptance*, *escalation on repeated failure*, and *taste feedback into the harness itself*. Where each role is placed depends on **blast radius, harness maturity, and ambiguity of the decision**.
2. The single most important design finding: **evaluation is rarely delegated to the same agent that executed the work.** Every mature system — OpenAI, Anthropic long-running, ARIS, AutoKaggle, Stripe Minions, LangChain Terminal Bench — separates the verifier from the producer, either across models (ARIS cross-model adversarial review), across agent roles (Anthropic three-agent Plan-Generate-Evaluate), or via external oracles (tests, CI, browser automation, Kaggle leaderboard, GCC in Carlini's compiler).
3. For **autonomous ML specifically**, the literature converges on a narrow set of high-value human gates — problem framing, data contract and leakage, evaluation protocol commitment, final acceptance — and explicitly rejects human gating of routine tuning, seed-level variation, and within-family hyperparameter search. Agent Laboratory's empirical result is the strongest on this: **co-pilot mode (selective human feedback) outperforms both fully autonomous and fully manual modes** on MLE-bench-adjacent tasks ([Schmidgall et al., 2025](https://arxiv.org/abs/2501.04227)).
4. The recommended gate map for our hybrid runner places **four mandatory human gates** (problem framing, data contract, evaluation protocol, final acceptance) and **three conditional gates** triggered by agent-detected uncertainty (anomaly on first successful run, repeated plateau, family switch). Everything between gates runs fully autonomously, with agent-to-agent review as the primary quality mechanism.

---

## 1. The Six Roles of the Human in Agentic Systems

Across the corpus, human intervention serves different functions depending on *what decision is being made*. Conflating them produces either approval fatigue or unsafe autonomy. The six roles:

| Role | What the human supplies | Example systems |
|------|------------------------|-----------------|
| **R1. Permission / safety boundary** | Consent for irreversible or high-blast-radius actions | Claude Code `default` mode, Stripe Minion protected paths |
| **R2. Strategic steering** | Intent, priorities, acceptance criteria | OpenAI Codex ("humans prioritize work, translate user feedback into acceptance criteria"), Agent Laboratory co-pilot |
| **R3. Planning approval** | Go/no-go on a proposed plan before execution | Tane's four-phase (research → plan → annotate → implement), Claude Code `plan` mode, ARIS Gate 1 |
| **R4. Evaluation & acceptance** | Judgment on whether output is good enough to ship | Stripe PR review, Brockman's "say no to slop", AutoKaggle final report review |
| **R5. Escalation on repeated failure** | Diagnosis when automated loops exhaust | Stripe two-attempt pragmatic cap, OpenAI "what capability is missing?" |
| **R6. Taste feedback into the harness** | Review comments that become rules, docs, tests | OpenAI: "human taste fed back … encoded into documentation or tooling"; Hashimoto: "engineer a solution such that the agent never makes that mistake again" |

**Key observation (from `harness-engineering-literature-review.md` §7.6, §8.3):** every mature system preserves at least R2, R5, and R6 as mandatory. R1, R3, R4 vary by blast radius and harness maturity. R4 is the one most often *re-delegated to another agent or automated oracle*, not removed — see §2.

---

## 2. Evaluation: Who Actually Does It?

This is the deliverable the user emphasized. The headline pattern is consistent across every mature system:

> **The entity that produced the artifact is not the entity that accepts it.**

Concrete realizations:

| System | Producer | Verifier / evaluator | Source |
|--------|----------|---------------------|--------|
| **OpenAI Codex (million-line experiment)** | Codex agent | Other agents (local + cloud), CI, linters, structural tests; human only for "judgment required" escalation | [OpenAI, 2026 — Harness Engineering](https://openai.com/index/harness-engineering/) |
| **Anthropic long-running (Young)** | Coding agent | Browser automation (Playwright/Puppeteer) as test oracle; `feature_list.json` with strict "edit only status field" rule | [Anthropic, 2026 — Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) |
| **Anthropic Labs three-agent** | Generator | **Evaluator agent** with hard-threshold tools, independent of Generator | [Anthropic, 2026 — Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) |
| **ARIS (auto-claude-research-in-sleep)** | Claude Code executor | **GPT-5.4 reviewer via MCP** with "reviewer independence protocol" — fresh thread, zero summaries from executor, score ≥ 6/10 to converge, ≤4 rounds | `Auto-claude-code-research-in-sleep-main-technical-anatomy-report.md:258, :283, :307` |
| **ARIS integrity audit** | Claude | **6-layer cascade of fresh reviewers**, each with no context from prior layers (code → experiment → claim → citation → proof) | Same doc, §4.3 |
| **Stripe Minions** | Minion agent | (a) hardcoded deterministic gates interleaved in the blueprint (linters, security, tests); (b) **two-attempt pragmatic cap**; (c) mandatory human PR review before merge | [Stripe Dot Dev Blog, 2026](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents); [ByteByteGo, 2026](https://blog.bytebytego.com/p/how-stripes-minions-ship-1300-prs) |
| **LangChain Terminal Bench 2.0** | Codex agent | `PreCompletionChecklistMiddleware` (deterministic exit hook) + `LoopDetectionMiddleware` (per-file edit tracking). Score 52.8% → 66.5% from harness-only changes | `harness-engineering-literature-review.md:400-412` |
| **AutoKaggle** | Developer agent | Reviewer agent (gpt-4o-mini vs developer's gpt-4o) **but** reads executor-provided summaries — "not independent in the ARIS sense", same-stack critic | `AutoKaggle-main-harness-engineering-comparative-analysis.md:174-181, :252-258` |
| **Agent Laboratory** | Research agent | Automated paper reviewer + **researcher feedback at each stage**; co-pilot mode outperforms fully autonomous | [Schmidgall et al., 2025](https://arxiv.org/abs/2501.04227) |
| **MLE-bench** | Any agent | **External Kaggle leaderboard** — bronze-medal threshold as ground truth | Chan et al., 2024 (via `AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md` §3.1) |
| **Carlini compiler (Anthropic)** | 16 Claude agents | **GCC as oracle compiler** — randomly compile kernel files with GCC and a subset with Claude's compiler; delta-debug disagreements | `harness-engineering-literature-review.md:386-396` |

### Evaluation sub-patterns

1. **External oracle ≫ internal judgment.** When ground truth exists (CI green/red, leaderboard score, GCC output, browser shows the UI), use it. No LLM verdict required.
2. **Fresh-context reviewer** (ARIS, integrity audit cascade, OpenAI doc-gardening). Independence must be *engineered*, not assumed; specifically, the reviewer should not receive the producer's summaries, scores, or framing.
3. **Deterministic exit hooks** (LangChain PreCompletionChecklist, Stripe blueprint gates). Cheap, always-on, pre-commit — catches the most common failure mode: "premature completion" (`harness-engineering-literature-review.md:615`).
4. **Bounded repair loops** before escalation. ARIS: ≤4 review rounds. Stripe: 2 attempts to fix CI then flag human. This prevents *doom loops* (`:619`) while keeping humans out of routine fixes.
5. **Human only for the last mile.** Stripe engineers review PRs; OpenAI humans intervene when "judgment is required" or when a failure signals a missing capability. The human is the acceptance authority, not the bug-fixer.

---

## 3. Where Humans Are *Actually* Inserted (Cross-Industry Map)

Synthesis from all sources. "Mandatory" = every mature source agrees; "conditional" = triggered by agent uncertainty or failure signal; "agent-to-agent" = handled without humans by default.

### 3.1 Mandatory human gates (with role from §1)

| Phase | Role | Evidence |
|-------|------|----------|
| **Intent capture / initial prompt** | R2 steering | Universal — the human always states what to build. "Humans prioritize work, translate user feedback into acceptance criteria" ([OpenAI, 2026](https://openai.com/index/harness-engineering/)). |
| **Protected-path writes / destructive ops** | R1 permission | Claude Code never auto-approves `.git`, `.bashrc` even in `auto` mode ([Anthropic Code Docs](https://code.claude.com/docs/en/permission-modes)); Stripe devboxes isolated from production. |
| **Final merge / ship** | R4 acceptance | Stripe: *all* PRs reviewed pre-merge; Brockman: "ensure some human is accountable for any code that gets merged." Exceptions (Huntley, OpenAI internal) have extreme mechanical enforcement compensating. |
| **Taste / architectural direction drift** | R6 feedback | Every source: review comments, failure pattern documents, AGENTS.md updates. "Every failure should become a harness-design problem" (`harness-engineering-literature-review.md:702`). |

### 3.2 Conditional gates (triggered by signals)

| Trigger | Gate | Evidence |
|---------|------|----------|
| Agent has exhausted N auto-repair attempts | R5 escalation | Stripe pragmatic cap = 2; ARIS ≤4 review rounds; LangChain LoopDetection flags per-file repeat edits |
| Proposed action has high blast radius or irreversibility | R1 permission | Claude Code `auto` mode classifier blocks "hostile or exceeds user intent" actions and falls back to manual after 3 consecutive denials |
| Ambiguity in spec or input | R2 steering | HiL-Bench (arxiv 2604.09408) explicitly tests whether agents recognize when to ask; finding: frontier agents frequently fail to |
| Planning phase complete before execution | R3 planning approval | Tane: "I review and edit Claude's generated plans in a text editor before allowing code generation — an explicit human gate that catches architectural misalignments"; Claude Code `plan` mode enforces this by restricting to read-only until approved |

### 3.3 Explicitly agent-to-agent or automated (no human)

- **Code review at the line level** — OpenAI has "pushed almost all review effort towards being handled agent-to-agent" ([OpenAI, 2026](https://openai.com/index/harness-engineering/)); ARIS uses cross-model reviewer.
- **Build verification, tests, linters** — every system; part of "downstream backpressure" ([Huntley, 2026](https://ghuntley.com/)).
- **Routine progress tracking** — progress files, feature lists, git commits; `claude-progress.txt`, `REVIEW_STATE.json`, `EXPERIMENT_LOG.md`.
- **Within-bounds retries and repair loops** — fix-or-escalate logic; human only sees the escalation, not the retries.

### 3.4 Debate: required vs optional human review

Explicit disagreement in the literature:

- **Required** (Brockman, Guo, Tane, Stripe): "Say no to slop"; high blast radius or brownfield code; financial environment.
- **Optional** (OpenAI internal team, Huntley): direct-to-master with automated backpressure as the substitute.

The resolution (`harness-engineering-literature-review.md:515`): **the difference correlates with (a) harness maturity and (b) blast radius.** In our context (research-grade autonomous ML on our own infrastructure, greenfield), the OpenAI-style "heavy mechanical enforcement, light human review" position is reachable — but only once the harness is mature. Early on, a Stripe-like posture (human reviews final deliverable) is safer.

---

## 4. Specialization to Autonomous Machine Learning

General software HITL patterns transfer, but ML has *additional* decision surfaces where human judgment is demonstrably high-leverage. Synthesized from `AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md` §2, AutoKaggle paper, Agent Laboratory paper, `2026-04-21-design-principles-reflection.md`, and the web HITL research.

### 4.1 ML decision points ranked by human-judgment leverage

| # | Decision | Human-value signal | Why LLM/agent alone underperforms | Sources |
|---|----------|-------------------|-----------------------------------|---------|
| **1** | **Problem framing** — target, unit of observation, label definition, success criteria | Extremely high; wrong framing invalidates everything downstream | LLMs can reason but have no access to business context, regulatory constraints, deployment reality | Gudigantala 2025; AI Paradox 2026; AutoKaggle reports human intervention at EDA phase explicitly |
| **2** | **Data contract / leakage** — what columns are available at prediction time, temporal ordering, target-leaky features | Very high; single most common silent failure | Leakage often requires domain knowledge ("is this field populated before or after the label event?") | Leakage survey arxiv 2311.04179; eval-contamination primer (Apr 2026) |
| **3** | **Evaluation protocol** — metric, splitting strategy, CV scheme, CI/bootstrap, horizon | High; drives all keep/discard decisions | Our own reflection (`2026-04-21-design-principles-reflection.md` §7): "Many keep/discard decisions were based on noise. The agent may have been chasing random fluctuations for dozens of experiments." | Internal; Gudigantala 2025 |
| **4** | **Final acceptance** — ship, document, present, use | High; accountability + ethics | Human owns consequences; LLM can model probability but not own the ethical frame (AI Paradox 2026) | Stripe pattern; Brockman; turning-data-into-wisdom 2026 |
| **5** | **Fairness / subgroup analysis** (if applicable) | Domain-dependent, potentially very high | Requires choosing protected attributes and acceptable thresholds | Gudigantala 2025; public-sector AI 2024 |
| **6** | **Model family commitment** (when to stop exploring, when to switch) | Medium; recoverable | LLM reasoning + world knowledge are better than bandit algorithms here (our own ABES post-mortem), but agent self-judgment plus an escalation trigger is usually sufficient | `docs/reflections/2026-04-21-design-principles-reflection.md` §3, §8 |
| **7** | **Feature engineering strategy** | Medium | CAAFE shows LLMs add value from domain context; humans add more but agent-driven is often sufficient | Hollmann et al., CAAFE |
| **8** | **HP values within a fixed family** | Low; delegate to Optuna/TPE | "Picking learning_rate=0.05 because it sounds reasonable is next-token sampling cosplaying as optimization" (`2026-04-21-design-principles-reflection.md` §4) | Internal; BoTorch / TPE literature |
| **9** | **Seed selection, CV fold choice, model initialization** | None; delegate | Pure randomness / determinism; human gate would be pure friction | Universal |

### 4.2 Evidence for gates 1–4 being high-leverage

- **AutoKaggle** explicitly exposes intervention at every one of its six phases and markets "user-centric, highly customizable" as a feature — but the paper's case studies center human value at **EDA (data understanding), data cleaning (leakage/contract), and final model validation** ([Li et al., 2024 / ICLR 2025](https://arxiv.org/abs/2410.20424)).
- **Agent Laboratory** reports that **co-pilot mode outperforms fully autonomous** on research quality metrics, and human guidance is most impactful at **research ideation (≈ problem framing) and experiment design (≈ evaluation protocol)** ([Schmidgall et al., 2025](https://arxiv.org/abs/2501.04227)).
- Our own auto_train post-mortem (`2026-04-21-design-principles-reflection.md`) shows ~140 experiments converged to a ceiling that was not a search failure but a **split-size and evaluation-reliability ceiling** — i.e. the missing human-leverage gate in the current system is *evaluation protocol commitment*, not action-type selection.
- MLE-bench (Chan et al., 2024) treats the **external human-calibrated leaderboard** as the oracle; the agent never judges itself.

### 4.3 Evidence for gates 5–9 being low-leverage for humans

- The bandit / urgency-score / Thompson-sampling machinery in ABES produced zero measurable gains across three campaigns (`2026-04-21-design-principles-reflection.md` §2, §3). Structural decisions (#6) decompose poorly into independent arms; the agent plus a discard-and-rollback policy plus an escalation trigger is sufficient.
- Optuna/TPE beats any LLM or human at pure numerical HP search once the space is defined (#8).
- No paper or practitioner defends human gating of seed choice or fold choice (#9) as value-adding.

### 4.4 Implication

**Humans should gate the framing and acceptance of the experiment, not its inner mechanics.** The inner loop — code, run, evaluate, keep/discard, log — should run with zero human involvement and rely on:

- an **automated evaluation protocol** (CV, bootstrap CI) committed at gate 3 and frozen,
- an **external oracle** for correctness (train.py exit code, metric parse, anomaly detector from `abes_engine.py check`),
- an **agent-to-agent reviewer** for code/results where the harness has capacity,
- a **bounded retry policy** with explicit escalation.

---

## 5. Recommended Gate Map for the Hybrid Runner

Format: **Phase → Gate kind → Condition that opens it → Artifact reviewed → Allowed human actions → Default-if-skipped**. "Kind" maps to the role taxonomy in §1.

### 5.1 Mandatory phase gates

| # | Phase boundary | Kind | Opens when | Artifact | Allowed actions | Default-if-skipped |
|---|----------------|------|-----------|----------|-----------------|--------------------|
| **G1** | Problem framing ▸ data work | R2 + R3 | Always — once per problem | `PROBLEM_CONTRACT.md` (task type, target, unit of observation, success metric candidates, constraints, non-goals) | Approve / revise / reject | Halt (cannot proceed without a frame) |
| **G2** | Data contract + leakage check ▸ modeling | R3 + R4 | Always — once per dataset | `DATA_CONTRACT.md` (schema, prediction-time availability per column, temporal ordering, declared target-adjacent features, leakage self-audit results) | Approve / flag leaky feature / request additional audit | Halt |
| **G3** | Evaluation protocol ▸ experiment loop | R3 + R4 | Always — once per problem | `EVAL_PROTOCOL.md` (metric, CV scheme, bootstrap CI config, baseline targets, acceptance threshold, time budget per experiment) | Approve / revise metric or split | Halt |
| **G4** | End of experiment loop ▸ reporting | R4 | Always — once per campaign | `FINAL_REPORT.md` + best `train.py` + results.tsv summary + explainability artifacts | Accept / request further experiments / reject | Defer to next human review (do not auto-ship) |

### 5.2 Conditional gates (inside the experiment loop — usually silent, escalate only on trigger)

| # | Condition | Kind | Artifact surfaced | Allowed actions | Default-if-no-response |
|---|-----------|------|-------------------|-----------------|------------------------|
| **C1** | Anomaly detector fires (e.g. metric inversion, impossible score, crash loop) | R5 escalation | Run log + anomaly reason + proposed fix | Approve fix / override keep-discard / inspect | Discard experiment; continue |
| **C2** | N≥3 consecutive non-improvements *and* agent requests family switch or structural change | R5 escalation | Plateau summary + agent's proposed change + evidence it's structurally different | Approve / redirect / declare done | Let agent proceed with its proposal (log decision) |
| **C3** | Agent requests to modify an approved contract (PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL) | R1 + R3 | Diff of contract change + justification | Approve / reject | Reject (contracts are sticky) |

### 5.3 Never-gate (full autonomy)

- Within-family HP search, seed selection, CV fold execution, routine feature trials that stay within the approved data contract, train.py edits, commit and rollback of individual experiments, results.tsv logging, anomaly checks that *pass*, agent-to-agent review rounds ≤ bounded N.

### 5.4 Gate-map properties

1. **Four gates before the loop, one after, three silent-in-loop.** Total human interruptions per campaign: 4 mandatory + expected 0–3 conditional. Matches Agent Laboratory's co-pilot frequency envelope.
2. **Contracts are first-class and sticky.** Once approved, PROBLEM_CONTRACT / DATA_CONTRACT / EVAL_PROTOCOL cannot be silently mutated by the agent — only via gate C3. This is the mechanism that enforces the transparency-and-explainability requirement from the handoff: every decision in the loop is traceable to an approved contract.
3. **Mandatory gates operate on *artifacts*, not on chat.** Follows ARIS file-based artifact contract principle (`Auto-claude-code-research-in-sleep-main-technical-anatomy-report.md:546`) and AutoKaggle's phase reports (`AutoKaggle-main-harness-engineering-comparative-analysis.md` §4.4).
4. **Escalations carry full context** (AlignX 2026 principle) — when C1/C2/C3 fires, the agent surfaces the decision trail, not a bare alert.
5. **Bounded repair before escalation.** Inside the loop, the agent retries per Stripe's pragmatic cap pattern (recommended: max 2 repair attempts on a single experiment, then discard and continue).
6. **Agent-to-agent review is the default verifier** for within-loop artifacts; cross-model review (ARIS pattern) is the aspirational upgrade once we have >1 model available.

### 5.5 Gate-map ASCII

```
                    ┌────────────────────────────────┐
 Human intent  ───▶ │  G1 PROBLEM_CONTRACT (R2+R3)   │
                    └──────────────┬─────────────────┘
                                   ▼
                    ┌────────────────────────────────┐
 Data   ──────────▶ │  G2 DATA_CONTRACT  (R3+R4)     │
                    │    (leakage self-audit)        │
                    └──────────────┬─────────────────┘
                                   ▼
                    ┌────────────────────────────────┐
                    │  G3 EVAL_PROTOCOL  (R3+R4)     │
                    │    (CV + bootstrap CI frozen)  │
                    └──────────────┬─────────────────┘
                                   ▼
        ┌──────────────────────────▼──────────────────────────────┐
        │             AUTONOMOUS EXPERIMENT LOOP                  │
        │  plan → edit train.py → run → evaluate → keep/discard   │
        │  ─────────────────────────────────────────────────────  │
        │   C1 anomaly ──┐   C2 plateau/family switch ──┐         │
        │   C3 contract change request ──┐              │         │
        │                (silent unless triggered)      │         │
        └──────────────────────────┬──────────────────────────────┘
                                   ▼
                    ┌────────────────────────────────┐
                    │  G4 FINAL_REPORT    (R4)       │
                    │    (accept / extend / reject)  │
                    └────────────────────────────────┘
```

### 5.6 Why this gate map and not more/fewer gates

**Why not fewer (OpenAI-internal / Huntley posture)?** Those environments have either mature mechanical enforcement (five months of CI + doc-gardening + structural tests) or low blast radius (personal projects). Neither holds here: the runner is new, and a silent leakage or evaluation bug will waste substantial compute and invalidate reports.

**Why not more (e.g. per-experiment approval like early AutoKaggle UX)?** Empirical result from our own campaigns: 140 experiments at one-per-approval cadence would have been impossible; and the per-experiment decision is genuinely low-leverage for humans (agent + anomaly detector + Optuna covers it, §4.3). Agent Laboratory's finding that *selective* co-pilot beats both extremes directly supports this position.

**Why gate the evaluation protocol specifically (G3)?** Because that's where our own system's largest ceiling sat (`2026-04-21-design-principles-reflection.md` §7). Making the evaluation protocol a human-approved, frozen artifact closes the loop's largest hidden degree of freedom and restores the meaning of "improvement."

---

## 6. Concrete Cross-References for the Design Phase

Items the brainstorming / spec phase should pull from this research:

1. **Artifact names and shape** — PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL, FINAL_REPORT. Modeled on ARIS's UPPER_CASE artifact convention and AutoKaggle's per-phase report discipline.
2. **Cross-model reviewer (future)** — ARIS pattern is the target once a second model is configured; for now, same-model fresh-context review.
3. **Deterministic exit hook** — LangChain's PreCompletionChecklistMiddleware is the pattern; realize it as a pre-log check before writing to `results.tsv`.
4. **Feature-list-as-gate** — Anthropic's `feature_list.json` with strict "edit only status field" instruction is a cheap way to prevent one-shotting when we eventually add multi-feature campaigns.
5. **Pragmatic cap on repair** — Stripe's 2-attempt cap is the concrete number; combine with our existing rollback discipline.
6. **Hard invariants vs soft knobs** — ARIS pattern (`technical-anatomy-report.md:554`); candidate hard invariants for us: (a) contracts sticky, (b) eval protocol frozen, (c) anomaly-detector never bypassed, (d) commit-per-experiment never skipped.
7. **Escalation context package** — follows AlignX 2026 / SAP pattern — must include agent reasoning, decision trail, impact; not just an alert.

---

## 7. Citations (web + internal)

**Web sources (retrieved 2026-04-21):**

1. Anthropic. "Choose a permission mode." *Claude Code Documentation.* https://code.claude.com/docs/en/permission-modes
2. Anthropic. "Claude Code auto mode: a safer way to skip permissions." *Anthropic Engineering,* 2026. https://www.anthropic.com/engineering/claude-code-auto-mode
3. Anthropic. "Effective harnesses for long-running agents." *Anthropic Engineering,* 2026. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
4. Anthropic. "Harness design for long-running application development." *Anthropic Engineering,* 2026. https://www.anthropic.com/engineering/harness-design-long-running-apps
5. Anthropic. "Measuring AI agent autonomy in practice." *Anthropic News,* 2026. https://www.anthropic.com/news/measuring-agent-autonomy
6. OpenAI. "Harness engineering: leveraging Codex in an agent-first world." *OpenAI,* 2026. https://openai.com/index/harness-engineering/
7. Stripe. "Minions: Stripe's one-shot, end-to-end coding agents." *Stripe Dot Dev Blog,* 2026. https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents
8. ByteByteGo. "How Stripe's Minions Ship 1,300 PRs a Week." 2026. https://blog.bytebytego.com/p/how-stripes-minions-ship-1300-prs
9. InfoQ. "Stripe Engineers Deploy Minions, Autonomous Agents Producing Thousands of Pull Requests Weekly." 2026. https://www.infoq.com/news/2026/03/stripe-autonomous-coding-agents/
10. SAP Community. "Human-in-the-Loop SAP Agents: Approval, Escalation… Series 2 Part 5." 2026. https://community.sap.com/t5/artificial-intelligence-blogs-posts/human-in-the-loop-sap-agents-approval-escalation-and-audit-series-2-part-5/ba-p/14372994
11. AlignX AI. "Designing Human-in-the-Loop for Agentic Workflows." *Medium,* Mar 2026. https://medium.com/@AlignX_AI/designing-human-in-the-loop-for-agentic-workflows-079faec737ed
12. MachineLearningMastery. "Building a 'Human-in-the-Loop' Approval Gate for Autonomous Agents." 2026. https://machinelearningmastery.com/building-a-human-in-the-loop-approval-gate-for-autonomous-agents/
13. HumanLayer. "12 Factor Agents." 2026. https://www.humanlayer.dev/blog/12-factor-agents
14. Elementum AI. "Human-in-the-Loop Agentic AI: When You Need Both." 2026. https://www.elementum.ai/blog/human-in-the-loop-agentic-ai
15. Cursor. "Auto Run / YOLO mode." Forum and docs, 2026. https://forum.cursor.com/t/how-to-enable-actual-yolo-auto-run-mode/67491
16. HiL-Bench. "Do Agents Know When to Ask?" *arXiv:2604.09408,* 2026. https://arxiv.org/html/2604.09408v1
17. Schmidgall et al. "Agent Laboratory: Using LLM Agents as Research Assistants." *arXiv:2501.04227,* 2025. https://arxiv.org/abs/2501.04227
18. Li et al. "AutoKaggle: A Multi-Agent Framework for Autonomous Data Science Competitions." *arXiv:2410.20424,* ICLR 2025. https://arxiv.org/abs/2410.20424
19. "On Leakage in Machine Learning Pipelines." *arXiv:2311.04179,* 2024.
20. Gudigantala et al. "Improving Machine Learning Workflows Using the Normative-Descriptive-Prescriptive Decision Framework." *Applied AI Letters,* 2025. https://onlinelibrary.wiley.com/doi/10.1002/ail2.118
21. Turning Data Into Wisdom. "The AI Paradox: Why Automation Increases Human Value." 2026. https://www.turningdataintowisdom.com/the-ai-paradox-why-automation-increases-human-value/

**Internal sources:**

- `docs/research/literature_review/harness-engineering-literature-review.md`
- `docs/research/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md`
- `docs/research/AutoKaggle-main/AutoKaggle-main-harness-engineering-comparative-analysis.md`
- `docs/research/Auto-claude-code-research-in-sleep-main/Auto-claude-code-research-in-sleep-main-technical-anatomy-report.md`
- `docs/reflections/2026-04-21-design-principles-reflection.md`
- `docs/brainstorming/2026-04-21-autonomous-ml-runner-brainstorm-handoff.md`
- `docs/brainstorming/2026-04-20-ml-harness-engineering-brainstorm.md`

---

## 8. What this research does *not* settle (for the brainstorm)

Deliberately out of scope for this document; to be handled in the design / spec phase:

- Exact **phase graph** and whether to copy AutoKaggle's six phases or build a slimmer one.
- **Single vs multi-agent** decomposition (planner / executor / reviewer minimum set).
- Relationship to the **current repo** — evolution from `abes_engine.py` + `train.py` + `program.md` or a greenfield runner template.
- Storage format, CLI shape, and the agent prompt itself.
- Which specific **numerical tools** get first-class integration (Optuna, bootstrap, permutation importance).
- Any **UI** for the gates (CLI prompt, web form, Slack interrupt — HumanLayer-style).

These are where the approaches discussion (brainstorming step 4) should go next.
