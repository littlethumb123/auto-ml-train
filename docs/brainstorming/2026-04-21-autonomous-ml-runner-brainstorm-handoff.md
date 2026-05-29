# Autonomous ML Experiment Runner — Brainstorm Session Handoff

**Date:** 2026-04-21  
**Status:** Paused before design approval; next session focuses on human-in-the-loop research  
**Companion docs:** `2026-04-20-ml-harness-engineering-brainstorm.md`, reflections under `docs/reflections/`, research under `docs/research/`

---

## Purpose of this document

Capture agreed goals, open questions, and a concrete agenda for the **next committed session** so work can resume without re-reading the full evidence base.

---

## Agreed product direction

| Dimension | Decision |
|-----------|----------|
| **Primary goal** | A **better autonomous ML experiment and research runner** — not a meta-project whose main output is harness research papers. |
| **Problem scope** | **Any supervised or unsupervised** learning problem (not limited to credit card fraud). |
| **Role of harness engineering** | Use **robust, systematic, industry-aligned harness design** as infrastructure (how we build), informed by general harness literature + agentic ML literature + prior auto_train campaigns. |
| **Workflow depth** | **Between** single-script iteration and full AutoKaggle breadth: **closer to end-to-end ML workflow** — data understanding through modeling/evaluation, with boundaries still TBD in detail. |
| **Human involvement** | **Hybrid (Option C):** autonomous phases **plus strategic gates** at key inflection points. Exact gate list **deferred** — needs dedicated research. |
| **Explainability** | The **entire modeling and decision-making procedure** must be **transparent and explainable** to users (first-class audit trail, not an afterthought). |
| **Reference systems** | **AutoKaggle-style** phase discipline and artifacts; **modern harness** patterns (progressive disclosure, mechanical enforcement, disk-first state, recovery); **ARIS-style** ideas where appropriate (e.g. cross-model review, file contracts) — adapted to ML workflow scale, not copying full research OS scope. |

---

## Evidence already synthesized (no need to re-derive)

- **Internal campaigns:** mar30 / apr01 / apr03 — ~140 experiments, XGBoost basin ~0.846 PR-AUC; ABES bandit framing questioned in `docs/reflections/2026-04-21-design-principles-reflection.md`.
- **Optimization forensics:** Seven bottlenecks, Two-Brain proposal, implementation gaps — `docs/reflections/2026-04-03-comprehensive-optimization-research.md`.
- **Agentic ML literature:** MLAgentBench, MLE-bench, MLGym, DS-Agent, CAAFE, AutoKaggle, AI Scientist, Agent Laboratory — `docs/research/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md`.
- **Harness engineering (2026):** Four Pillars, failure modes, guidelines — `docs/research/literature_review/harness-engineering-literature-review.md`.
- **Repo examinations:** AutoKaggle + ARIS technical anatomy and comparative analysis — `docs/research/AutoKaggle-main/`, `docs/research/Auto-claude-code-research-in-sleep-main/`.
- **Prior harness brainstorm:** Evidence management, six-component model, concrete priorities — `docs/brainstorming/2026-04-20-ml-harness-engineering-brainstorm.md`.

---

## Resolved vs open (for next session)

### Resolved in this brainstorm

- Mission is **runner first**, harness literature as **discipline**, not primary research output.
- Workflow is **near end-to-end** with **hybrid human gates**.
- **Visual companion** accepted for future architecture / diagram steps.

### Explicitly open — next session #1 topic

**Human-in-the-loop at ML-specific decision points**

Research and decide:

1. How **Claude Code**, **Cursor**, **Anthropic engineering**, **OpenAI / Codex**, **Stripe Minions**, **Agent Laboratory**, **AutoKaggle**, and similar systems place humans in the loop — especially for **evaluation** and **high-stakes decisions**.
2. **Which gates** belong in an autonomous ML workflow (problem framing, data contract, leakage checks, feature strategy, model family commitment, deployment vs research mode, final acceptance, anomaly triage, etc.).
3. Tradeoffs: **gate frequency** vs **throughput**; **when human input improves outcomes** vs **adds friction** (cite practitioner + paper evidence where possible).
4. Output: a **recommended gate map** (phase → condition → artifact reviewed → allowed actions) aligned with transparency requirements.

### Still open after gates (later design sections)

- Exact **phase graph** and artifact schema (build on AutoKaggle phases vs slim custom graph).
- **Single vs multi-agent** roles (planner / executor / reviewer minimum viable set from prior brainstorm).
- **Numerical tools** (Optuna, CV, bootstrap) vs **LLM reasoning** — follow `2026-04-21-design-principles-reflection.md` progressive complexity.
- **Evaluation contract** per problem type (supervised vs unsupervised metrics, leakage, uncertainty).
- Relationship to **current repo** (`program.md`, `abes_engine.py`, `train.py`) — evolution vs greenfield template.

---

## Brainstorming workflow status (per attached skill)

| Step | Status |
|------|--------|
| Explore project context | Done |
| Visual companion offer | Accepted |
| Clarifying questions | Partially done (mission, scope, human model); **gate specifics deferred** |
| Propose 2–3 approaches | **Not started** — blocked on gate research |
| Present design + per-section approval | **Not started** |
| Write `docs/superpowers/specs/YYYY-MM-DD-*-design.md` + commit | **Not started** |
| Spec self-review | N/A |
| User review of spec | N/A |
| Invoke `writing-plans` skill | **After** design doc approved |

---

## Suggested next session prompt (copy-paste)

> Continue the autonomous ML experiment runner design from `docs/brainstorming/2026-04-21-autonomous-ml-runner-brainstorm-handoff.md`.  
> Do **exhaustive research** on how industry (Claude Code, Cursor, Anthropic long-running agents, OpenAI harness engineering, Stripe Minions, etc.) handles **evaluation** and **human-in-the-loop** — especially **where** humans are inserted.  
> Then specialize to **machine learning**: which decision points should use strategic human gates vs full autonomy?  
> Deliver: cited findings + a **recommended gate map** for our hybrid model.  
> After that, return to brainstorming: approaches, design sections, then spec in `docs/superpowers/specs/`.

---

## File locations quick reference

| Path | Contents |
|------|----------|
| `docs/brainstorming/2026-04-21-autonomous-ml-runner-brainstorm-handoff.md` | This handoff (session summary) |
| `docs/brainstorming/2026-04-20-ml-harness-engineering-brainstorm.md` | Prior harness priorities |
| `docs/reflections/2026-04-21-design-principles-reflection.md` | ABES critique, progressive complexity |
| `docs/reflections/2026-04-03-comprehensive-optimization-research.md` | Bottlenecks, Two-Brain |
| `docs/research/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md` | ML agent papers + patterns |
| `docs/research/literature_review/harness-engineering-literature-review.md` | General harness engineering |
| `docs/research/literature_review/harness engineering survey 2026_xhs.pdf` | General harness engineering survey |
| `docs/research/AutoKaggle-main/` | AutoKaggle anatomy + comparative analysis |
| `docs/research/Auto-claude-code-research-in-sleep-main/` | ARIS anatomy |
| `docs/superpowers/specs/README.md` | Where the approved design doc will land |

---

## Contact note

When the formal design is written and self-reviewed, it should live at:

`docs/superpowers/specs/YYYY-MM-DD-autonomous-ml-runner-design.md`

(per brainstorming skill convention).
