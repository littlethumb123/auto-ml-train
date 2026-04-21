# Autonomous ML Runner — Design Session Handoff (v2)

**Date:** 2026-04-21  
**Purpose:** Resume design work in a **fresh agent session** with full context on locked decisions. **Next step:** Design **Section 2 (Components)** — role prompts, tool I/O contracts, artifact schemas — then Sections 3–5, spec file, self-review, user review.

---

## Why this handoff exists

Section 1 (architecture) and all Q&A through memory / learning loops are **approved**. A new session should **not** re-derive HITL research or re-read the full harness corpus; it should read this file + the cited deliverables below and continue from **Section 2**.

---

## Locked product direction (unchanged from v1 handoff)

| Dimension | Decision |
|-----------|----------|
| **Primary goal** | Better autonomous ML experiment / research runner (not harness papers as the main output). |
| **Problem scope** | Any supervised or unsupervised learning problem. |
| **Human model** | **Hybrid (Option B architecture):** four mandatory human gates (G1–G4) + three conditional gates (C1–C3); autonomous experiment loop between G3 and G4. |
| **Explainability** | Entire procedure transparent: artifact-first, disk-first, audit trail. |
| **Approach** | **Approach B** — greenfield `runner/` with artifact contracts + three **context-isolated** roles (Planner / Executor / Reviewer). **Not** full AutoKaggle six-phase clone (Approach C deferred). |

---

## Research deliverable (read-only for new session)

Full citations + recommended gate map:

- `docs/research/2026-04-21-hitl-evaluation-gate-research.md`

Prior evidence base (reference as needed, do not re-synthesize unless contradicting):

- `docs/research/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md`
- `docs/research/literature_review/harness-engineering-literature-review.md`
- `docs/reflections/2026-04-21-design-principles-reflection.md` (especially §4–§7: reason vs compute, progressive complexity, evaluation reliability, what to keep from ABES)

---

## Section 1 — Architecture (APPROVED)

### Top-level layout

```
runner/
  RUNNER.md                 # lean agent entry (progressive disclosure)
  AGENTS.md                 # harness fossil record (M4); human-curated, read every role start
  contracts/                # per problem — human-gated + optional priors
    PROBLEM_CONTRACT.md     # G1
    DATA_CONTRACT.md        # G2
    EVAL_PROTOCOL.md        # G3 — names mandatory tools, CV, CI rules, budgets
    PRIORS.md               # M3 — optional first campaign; filled/updated at G4
    FINAL_REPORT.md         # G4
  state/                    # per campaign — recoverable
    results.tsv             # M1 — schema preserved from legacy abes_engine logging
    DEAD_ENDS.md            # M2 — “do not retry” lines
    NOTEBOOK.md             # M2 — surprising observations, not clean dead-ends
    NEXT_EXPERIMENT.md      # Planner output; **required sections** (memory reads) — Reviewer enforces
    REVIEW.md               # Reviewer output per round
    run_card.md             # optional per experiment; from explain_run tool
    CAMPAIGN_STATE.json     # round, budget, last commit, last verdict, exp_id counter
  tools/                    # tactical compute — callable functions, not a framework
    (see MVP tool list below)
  train.py                  # primary experiment entry (kept; path may be repo root or runner — spec decides)
  log.py                    # ~30 lines: results.tsv append, budget status
  roles/
    planner.md
    executor.md
    reviewer.md
  experiment_helpers/
    <exp_id>/               # rare Executor writes; namespaced per experiment; same commit as train.py
```

### `abes_engine.py`

- **Full removal.** Surviving logic: anomaly (~10 lines) → `tools/anomaly.py`; results/budget → `log.py`; dead-ends concept → `DEAD_ENDS.md`. No deprecation stub.

### Roles: context isolation, single model, single process (MVP)

- **Not** multi-process or multi-model in MVP (defer ARIS-style cross-model reviewer).
- **Yes** context isolation: each role = **fresh invocation** with only listed artifacts + `roles/<role>.md`; **no** sharing other roles’ chat history.
- Producer ≠ verifier enforced at **artifact** boundary (Reviewer reads files, not Executor chat).

### Executor write scope (APPROVED)

| Writable | Rule |
|----------|------|
| `train.py` | Every experiment. |
| `runner/experiment_helpers/<exp_id>/` | Rare; **must** be declared in `NEXT_EXPERIMENT.md` for that round; rolled back with same git commit as `train.py`. |
| **Read-only always** | `contracts/`, `roles/`, `tools/`, `log.py`, `prepare.py`, `data/`, other experiments’ `train.py` / other `experiment_helpers/`. |

### Core principles (non-negotiable)

1. **Artifact-first** — decisions live on disk, not chat.
2. **Producer ≠ verifier** — Reviewer gate on keep/discard + tool-backed stats.
3. **Reason strategically, compute tactically** — Planner reasons; `tools/` computes; `contracts/` bind (EVAL_PROTOCOL names mandatory tools).
4. **Contracts sticky** — G1–G3 immutable without conditional gate **C3** (human approves contract diff via `contract_diff` output).

### Human gates (summary)

| ID | When | Artifact / action |
|----|------|-------------------|
| **G1** | Start | Approve `PROBLEM_CONTRACT.md` |
| **G2** | After G1 | Approve `DATA_CONTRACT.md` (leakage audit informed by tools) |
| **G3** | After G2 | Approve `EVAL_PROTOCOL.md` |
| **G4** | End | Approve `FINAL_REPORT.md` + `PRIORS.md` diff |
| **C1** | Anomaly / impossible metric | Human decides override / inspect |
| **C2** | Plateau + family switch request (e.g. N≥3 non-improvements) | Human redirect / approve / stop |
| **C3** | Agent requests contract change | Human approves diff |

Autonomous loop: between G3 and G4 — Planner → Executor → Reviewer → git keep/reset → log.

### Hard invariants vs soft knobs

**Hard:** G1–G3 before loop; anomaly before keep; mandatory tools per EVAL_PROTOCOL before accepting small Δ; git commit per experiment; Stripe-style **2 repair attempts** then escalate; contracts not silently mutable.

**Soft:** metrics, CV folds, CI thresholds, time budget, plateau N, which v2 tools enabled.

---

## Memory & learning (APPROVED — answers “how does agent learn from failures?”)

### Four memory layers

| Layer | Artifact | Scope | Writer |
|-------|----------|-------|--------|
| **M1** | `results.tsv` | Campaign | `log.py` / Reviewer |
| **M2** | `DEAD_ENDS.md`, `NOTEBOOK.md` | Campaign | Reviewer / Planner |
| **M3** | `contracts/PRIORS.md` | Problem, cross-campaign | G4 human-approved promotion from M2 + aggregates |
| **M4** | `runner/AGENTS.md` | All problems | Human (or agent + human via C3) |

### Three feedback loops

1. **Intra-campaign:** after each experiment, Reviewer updates `DEAD_ENDS.md` / `NOTEBOOK.md` / `REVIEW.md`; next Planner **must** use `results_query`, `dead_ends_query`, cite last `REVIEW.md`; `NEXT_EXPERIMENT.md` has **required sections** — Reviewer rejects malformed plans.
2. **Inter-campaign (G4):** aggregate `results_query`, propose `PRIORS.md` update; human approves; next campaign on same problem reads `PRIORS.md` at G1.
3. **Harness:** repeated surprise → human edits `AGENTS.md` or tools — fossil record, read every session.

---

## MVP `tools/` list (APPROVED)

Gate support:

- `data_profile.py` — G2
- `leakage_audit.py` — G2
- `baseline_runner.py` — G3

Within-loop:

- `anomaly.py`
- `cv_runner.py`
- `bootstrap_ci.py`
- `paired_comparison.py`
- `optuna_search.py`

Memory / transparency / governance:

- `results_query.py`
- `dead_ends_query.py`
- `explain_run.py` → `run_card.md`
- `contract_diff.py` — C3

Unsupervised (when campaign type requires):

- `clustering_eval.py`

**Deferred to v2:** `multi_fidelity.py`, `stacking.py`, `feature_selection.py`, `calibration.py`, `shap_report.py`, `dimred_eval.py`, `integrity_check.py` (FINAL_REPORT vs results.tsv audit).

---

## Relationship to current `auto_train` repo

- **Remove:** `abes_engine.py` (bandit / urgency / recommend machinery).
- **Preserve concepts:** `results.tsv` schema, anomaly thresholds, dead-ends list, git-per-experiment discipline.
- **Read-only:** `prepare.py`, `data/` (per workspace rules unless policy changes).
- **Evolve:** `program.md` → `RUNNER.md` (or equivalent lean entry); harness rules → `AGENTS.md`.

Exact migration path (symlinks, backward-compatible CLI) is **TBD in spec** — not locked in v2 handoff.

---

## Brainstorming workflow status

| Step | Status |
|------|--------|
| Explore context | Done |
| HITL research + gate map | Done (`docs/research/2026-04-21-hitl-evaluation-gate-research.md`) |
| Approaches (A/B/C) | Done — **B chosen** |
| Design Section 1 (Architecture) | **Done / approved** |
| Design Section 2 (Components) | **Done** (role skeletons, tool signatures, artifact schemas) |
| Design Section 3 (Data flow) | **Done** (setup flow, autonomous loop pseudocode, recovery, diagram) |
| Design Section 4 (Error handling) | **Done** (parse/schema, Executor repair cap, C1/C2/C3 escalation, driver errors, Phase 2 upgrade) |
| Design Section 5 (Testing) | **Done** (unit/schema/integration/safety test layers + MVP-out-of-scope list) |
| Write `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md` + commit | **Done** (pending commit) |
| Spec self-review | **Done** (fixes in §3.2 driver stdout routing, plateau semantics, cross-reference repairs, §4.1 tightening; zero placeholders remaining) |
| User review spec | **Next** |
| `writing-plans` skill → implementation plan | After spec approved |

---

## Copy-paste prompt for the NEW session

```
Continue the autonomous ML experiment runner design from:
  docs/brainstorming/2026-04-21-autonomous-ml-runner-design-handoff-v2.md

Architecture (Section 1) and all decisions in that file are APPROVED — do not re-open unless you find an internal contradiction.

Your tasks:
1. Write Design Section 2 (Components): role prompt skeletons (planner/executor/reviewer), each MVP tool’s CLI or Python function signature (inputs/outputs/errors), and each artifact’s schema (YAML frontmatter or fixed markdown sections — pick one and be consistent).
2. Then Sections 3–5 (data flow, error handling, testing).
3. Write the full spec to: docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md
4. Run spec self-review (placeholders, contradictions, scope).
5. Git commit the spec and handoff updates.

Follow the brainstorming skill: after the spec is written, ask me to review the spec file before invoking writing-plans.

Do NOT re-run exhaustive web research unless a claim needs a new primary source.
```

---

## File quick reference

| Path | Role |
|------|------|
| `docs/brainstorming/2026-04-21-autonomous-ml-runner-design-handoff-v2.md` | **This file** — session bridge |
| `docs/brainstorming/2026-04-21-autonomous-ml-runner-brainstorm-handoff.md` | Original brainstorm handoff (HITL agenda) |
| `docs/research/2026-04-21-hitl-evaluation-gate-research.md` | HITL + gate map + citations |
| `docs/superpowers/specs/README.md` | Spec folder convention |
| `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md` | **Target spec path** (to be created) |

---

## Open items intentionally left for Section 2+

- Exact path for `train.py` (repo root vs `runner/`) and import layout for `experiment_helpers/<exp_id>/`.
- JSON schemas for `CAMPAIGN_STATE.json`, `NEXT_EXPERIMENT.md` / `REVIEW.md` section templates.
- Whether `run_card.md` is always-on or only when `explain_run` is invoked.
- CLI shape (`python -m runner ...`) vs Makefile vs thin shell scripts.
- Cross-model reviewer hook (deferred) — mention as Phase 2 in spec only.

---

*End of handoff v2.*
