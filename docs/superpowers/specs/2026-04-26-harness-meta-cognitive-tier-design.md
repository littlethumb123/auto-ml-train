# Harness Meta-Cognitive Tier — Design Spec

**Date:** 2026-04-26
**Status:** Approved by user (all sections reviewed in brainstorming session)
**Motivation:** Post-mortem of ip-commercial-new-te campaign (50 rounds). Root-cause analysis revealed five architectural absences — not symptom-level bugs — in the existing Planner/Executor/Reviewer harness. This spec addresses them as a unified architectural tier.

**Prior spec:** `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md`

---

## 0. Root Causes Being Addressed

Five architectural root causes were identified (not symptoms — patches to specific symptoms were explicitly rejected):

| ID | Root Cause | Manifested As |
|----|-----------|---------------|
| A | No reflective layer — harness is purely reactive, no role synthesizes across time | 23 rounds at a local weight optimum; C2 cycling 4× with same diagnostic result |
| B | Implicit assumptions — no mechanism to surface, register, or challenge beliefs accepted on keep | "NM found the global optimum" persisted unchallenged for 23 rounds |
| C | Memory is accumulation, not synthesis — DEAD_ENDS/NOTEBOOK grow but are never abstracted | Pattern "every change redistributes weight away from dominant model" never extracted |
| D | Role boundary misalignment — Reviewer anchored by reading plan before evidence; A_diagnose misuses Reviewer for trajectory work | Six informationally-redundant reproduction rounds |
| E | No operational dimension — harness has no model of its own cost or efficiency | r49 timeout was unpredictable; no cost/value ratio visible across rounds |

---

## 1. New State Artifacts (Data Model)

All new artifacts are **campaign-specific**, living in `campaigns/<id>/state/`. The `runner/state/` directory holds the generic template skeleton created at `init`.

### 1.1 ASSUMPTION_REGISTER.md

**Owner:** Reviewer writes entries on `keep`; Historian audits on periodic/C2 runs.
**Purpose:** Makes implicit beliefs explicit and challengeable. Every kept result accepts assumptions that, if false, would invalidate the campaign's current strategy.

```yaml
---
schema_version: 1
campaign_id: "<id>"
count: <int>
last_updated: "<date>"
---
```

Entry format:

```markdown
### A-<round>-<seq> — <short name>

- **Claim:** <specific falsifiable statement about result, optimizer, data, or eval>
- **Evidence for:** <what was observed that supports this>
- **Evidence against:** <what contradicts this — initially "none">
- **Confidence:** low | medium | high
- **Load-bearing:** yes | no
- **Verification status:** unverified | partially_verified | verified | falsified
- **Last audited:** round <N> by <Reviewer|Historian>
```

**Load-bearing** means: if this assumption is falsified, the current strategy collapses. Load-bearing + unverified is the critical risk state that both the Reviewer and Historian must flag.

Common assumption categories the Reviewer should consider on every `keep`:

| Category | Canonical example |
|---|---|
| Optimizer quality | "NM weight optimizer found the global (not local) optimum" |
| Result stability | "This result is robust to seed variation and feature perturbation" |
| Evaluation adequacy | "SE is small enough to detect remaining gains" |
| Complementarity source | "Ensemble gain comes from genuine inter-model complementarity, not val-set overfitting" |
| Feature dependence | "Result does not depend on exact feature count (N=794)" |

**Rules:**
- Reviewer MUST write ≥1 assumption entry on every `keep` verdict.
- Reviewer MAY update `verification_status` to `falsified` on `discard` rounds when the discard's evidence clearly falsifies an existing assumption.
- Historian reads and audits assumptions during every periodic/C2 run; updates `verification_status`, `evidence_against`, `last_audited`.
- Planner reads the full register before every plan. If proposing an experiment that interacts with a load-bearing, unverified assumption, the Planner must acknowledge it in NEXT_EXPERIMENT.md §2.

### 1.2 STRATEGY_MEMO.md

**Owner:** Historian. Overwritten on each Historian run (not append-only — always reflects current analysis).
**Purpose:** The Historian's synthesized view of the campaign's trajectory, patterns, assumption health, and current bottleneck.

```yaml
---
schema_version: 1
campaign_id: "<id>"
historian_round: <round at which produced>
trigger: "periodic" | "c2" | "periodic+c2"
rounds_covered: [<from>, <to>]
---
```

Four mandatory sections:

```markdown
## 1. Trajectory Narrative
What phase is the campaign in (exploration / exploitation / saturation)?
How has Δ-per-round changed across the covered window?
When did the last phase transition occur?

## 2. Pattern Extraction
Structural regularities across the covered rounds that no single round's
key finding captures. Each pattern: statement, supporting rounds, confidence.
Cross-reference against PATTERN_BOOK.md — confirm, strengthen, or note as new.

## 3. Assumption Audit
For each load-bearing, unverified assumption in ASSUMPTION_REGISTER.md:
state the assumption, assess whether covered-window evidence supports or
undermines it, recommend verification action. Flag critical assumptions
(load-bearing + unverified after ≥2 Historian audits).

## 4. Bottleneck Diagnosis
Current bottleneck category: model_quality | optimizer_quality | data_quality |
eval_quality | feature_representation.
One-paragraph justification citing trajectory evidence.
Highest-ROI technique class from UNEXPLORED_TECHNIQUES.md given this diagnosis.
```

**Not created at init.** Written by first Historian run. Planner checks for existence before reading.

### 1.3 PATTERN_BOOK.md

**Owner:** Historian. New entries are appended; existing entries can be updated in-place (confidence, status, supporting evidence). Superseded patterns are marked rather than deleted.
**Purpose:** Cross-round structural regularities extracted from CAMPAIGN_JOURNAL.md. Higher authority than NOTEBOOK.md because patterns have multi-round evidence vs. single observations.

```yaml
---
schema_version: 1
campaign_id: "<id>"
count: <int>
last_updated: "<date>"
---
```

Entry format:

```markdown
### P-<seq> — <pattern name>

- **Pattern:** <structural regularity as a generalizable rule>
- **Supporting evidence:** rounds <list> — <one-line summary per round>
- **Confidence:** low | medium | high
- **Status:** active | superseded_by P-<other>
- **Implication for Planner:** <what to do or avoid given this pattern>
```

Skeleton created at init (empty, header only). Historian appends entries during periodic/C2 runs.

---

## 2. Historian Role

**New file:** `runner/roles/historian.md`

### 2.1 Identity & Invariants

The Historian is the 4th role in the harness. It owns STRATEGY_MEMO.md, PATTERN_BOOK.md, and audit updates to ASSUMPTION_REGISTER.md. It NEVER writes NEXT_EXPERIMENT.md, train.py, REVIEW.md, or any contract. It is advisory — its outputs are required Planner inputs but the Planner may disagree with stated reasoning.

### 2.2 Inputs

```
runner/AGENTS.md
runner/contracts/EVAL_PROTOCOL.md
runner/contracts/STRATEGY_GUIDE.md
state/CAMPAIGN_STATE.json
state/CAMPAIGN_JOURNAL.md            # primary data source — full history
state/results.tsv                    # via tools/results_query
state/DEAD_ENDS.md                   # via tools/dead_ends_query
state/NOTEBOOK.md
state/ASSUMPTION_REGISTER.md
state/PATTERN_BOOK.md
state/UNEXPLORED_TECHNIQUES.md
```

The Historian reads MORE state than any other role by design. Trajectory synthesis requires the full picture. Other roles remain narrow-scoped.

### 2.3 Trigger Conditions

Managed by the driver, tracked in CAMPAIGN_STATE.json via `historian_trigger_pending`:

1. **Periodic:** Every K rounds (`historian_interval`, default 10). `rounds_since_last_historian` tracked in CAMPAIGN_STATE.json. For campaigns with `budget_total < 50`: K = max(5, budget_total × 0.10).
2. **C2-triggered:** When `consecutive_discards >= plateau_trigger`. This **replaces** the current `c2_pending_diagnose → A_diagnose` protocol. The Historian's STRATEGY_MEMO.md serves as the C2 diagnostic output.
3. **periodic+c2:** Both conditions true simultaneously — one combined run.

### 2.4 Required Procedure

1. Read all inputs. Note trigger type and rounds covered.
2. **Trajectory analysis:** Compute Δ-per-round rate across covered window. Identify phase (exploration / exploitation / saturation). Note rounds since last `keep`.
3. **Pattern extraction:** Read CAMPAIGN_JOURNAL.md entries for covered window as a sequence. Identify structural regularities across ≥3 rounds. Cross-reference PATTERN_BOOK.md — confirm existing, strengthen confidence, or mark superseded. Append new patterns.
4. **Assumption audit:** For each ASSUMPTION_REGISTER.md entry with `verification_status != verified` and `load_bearing: yes`: assess whether covered-window evidence supports or undermines the claim. Update `verification_status`, `evidence_against`, `last_audited`. Flag critical assumptions in STRATEGY_MEMO.md §3.
5. **Bottleneck diagnosis:** Classify current bottleneck as one category. Cite trajectory evidence. Identify highest-ROI technique class from UNEXPLORED_TECHNIQUES.md.
6. **Frontier update:** If analysis reveals technique classes not in UNEXPLORED_TECHNIQUES.md, append them with `Status: Unexplored` and estimated Expected Δ.
7. Write STRATEGY_MEMO.md (overwrite).
8. Update PATTERN_BOOK.md (append new; update confidence on existing).
9. Update ASSUMPTION_REGISTER.md (audit updates only — no new entries; Reviewer creates new entries).
10. Emit stdout: `HISTORIAN_COMPLETE: round <N>, trigger <str>, patterns_added <int>, assumptions_flagged <int>, tokens_used <int>`

### 2.5 What the Historian Does NOT Do

- Does NOT write NEXT_EXPERIMENT.md (Planner's job)
- Does NOT issue keep/discard (Reviewer's job)
- Does NOT modify train.py or run experiments (Executor's job)
- Does NOT create new assumption entries (Reviewer's job on keep)
- Does NOT override the Planner — STRATEGY_MEMO.md is advisory input

---

## 3. Revised Reviewer Role

Changes to `runner/roles/reviewer.md`: two structural modifications.

### 3.1 Evidence-First, Plan-Last

**Phase 1 — Independent Assessment (before reading the plan):**
1. Read `runner/AGENTS.md`, `runner/contracts/EVAL_PROTOCOL.md`
2. Read `train.py` (as committed by Executor)
3. Read `run.log`
4. Run `tools/anomaly` and every mandatory tool from EVAL_PROTOCOL.md
5. Parse metrics. Compute Δ = val_primary_metric − best_prior.
6. Write `REVIEW.md §Independent Assessment` — what does the evidence show? What is surprising? Form a preliminary verdict based purely on numbers and tool outputs.

**Phase 2 — Plan Comparison (now reads the plan):**
7. Read `state/NEXT_EXPERIMENT.md`
8. Compare actual vs. expected. Did the experiment confirm or falsify the Planner's hypothesis? What does the discrepancy reveal?
9. Write `REVIEW.md §Plan Comparison` — expected Δ vs. actual Δ. Hypothesis confirmed or falsified.

**Phase 3 — Verdict and State Updates:**
10. Final verdict: `keep` if Δ > 0 AND no mandatory tool flagged regression AND not anomaly.
11. If `keep`: Write ≥1 assumption entry to ASSUMPTION_REGISTER.md (mandatory).
12. If `discard`: Check ASSUMPTION_REGISTER.md for assumptions this discard falsifies. Update `verification_status: falsified` with evidence.
13. Append to DEAD_ENDS.md, NOTEBOOK.md, CAMPAIGN_JOURNAL.md as per existing protocol.
14. Call `run_round.sh review-finalize` as before.

CAMPAIGN_JOURNAL.md entry gains one field:
```markdown
**Independent assessment:** <1-2 sentences written in Phase 1, before reading the plan>
```

### 3.2 Mandatory Assumption Registration on Keep

At least one assumption entry per `keep` verdict. The Reviewer asks: "What must remain true for this kept result to remain the champion? What have we not verified?"

The Reviewer is not required to verify assumptions — only to surface them as explicit, challengeable objects.

### 3.3 Discard → Assumption Falsification Check

On `discard`, the Reviewer scans ASSUMPTION_REGISTER.md for assumptions the current evidence clearly falsifies. If found: update `verification_status`, append to `evidence_against`. Lightweight — only obviously-relevant assumptions need checking. Historian does the deeper cross-round audit.

---

## 4. Revised Planner Role

Changes to `runner/roles/planner.md`: new inputs and procedure steps.

### 4.1 New Required Inputs

Added to the Planner's input list (read after existing inputs, before pre-selection reasoning):

```
state/STRATEGY_MEMO.md          # Historian trajectory analysis (read if exists)
state/ASSUMPTION_REGISTER.md    # Load-bearing assumptions to respect
state/PATTERN_BOOK.md           # Cross-round structural regularities
state/TOKEN_SUMMARY.txt         # Operational cost digest (informational)
```

### 4.2 Revised Procedure

Steps 1-3 unchanged (read inputs, query results, query dead ends).

**Step 4 — Assumption-Aware Novelty Check (revised):**
In addition to UNEXPLORED_TECHNIQUES.md check, the Planner must:
1. Identify all ASSUMPTION_REGISTER.md entries with `load_bearing: yes` AND `verification_status: unverified`.
2. Read STRATEGY_MEMO.md §3 (if exists) for Historian-flagged critical assumptions.
3. If critical unverified assumptions exist AND `consecutive_discards >= 2`: SHOULD prioritize an experiment that tests the most critical assumption over selecting from UNEXPLORED_TECHNIQUES.md.

**Step 5 — Pattern-Informed Strategy (new):**
1. Read PATTERN_BOOK.md. For each `active` pattern with `confidence: high`: check whether the candidate experiment collides with it.
2. Read STRATEGY_MEMO.md §4 (Bottleneck Diagnosis) if exists. Candidate selection should address the diagnosed bottleneck category.

**Step 6 — Pre-selection Reasoning (expanded):**
For each candidate, justification now includes:
- Expected Δ (unchanged)
- **Assumption interaction:** Does this experiment interact with a load-bearing unverified assumption? Does it test or depend on it?
- **Pattern consistency:** Does this experiment collide with an active Pattern Book pattern? If so, why try it anyway?
- **Historian alignment:** Is this consistent with the Historian's bottleneck diagnosis? If not, why disagree?

Record in NEXT_EXPERIMENT.md §2 (Evidence from memory).

### 4.3 NEXT_EXPERIMENT.md Schema Addition

Frontmatter gains one optional field:
```yaml
assumptions_tested:
  - "A-25-1"   # ASSUMPTION_REGISTER entry IDs this experiment is designed to test
```

§2 (Evidence from memory) gains a required subsection when STRATEGY_MEMO.md exists:
```markdown
### Historian context
- **Bottleneck diagnosis:** <category from STRATEGY_MEMO §4>
- **Critical assumptions:** <list from STRATEGY_MEMO §3, if any>
- **Alignment:** <how this experiment addresses the bottleneck, or why it diverges>
```

### 4.4 A_diagnose Removed

`A_diagnose` removed from `action_types` in EVAL_PROTOCOL.md. Diagnostic synthesis is now the Historian's responsibility, triggered by the driver. Planner can still propose reproduction runs framed as `A_validate` with explicit assumption ID in `assumptions_tested` — more targeted than the generic A_diagnose.

---

## 5. Driver Changes

### 5.1 CAMPAIGN_STATE.json — New Fields (schema_version: 2)

```json
{
  "$schema_version": 2,
  "rounds_since_last_historian": 0,
  "historian_interval": 10,
  "last_historian_round": null,
  "historian_trigger_pending": false,
  "total_tokens": {
    "planner": 0,
    "executor": 0,
    "reviewer": 0,
    "historian": 0
  }
}
```

`historian_interval` is set from EVAL_PROTOCOL.md at `init`. For `budget_total < 50`: `max(5, int(budget_total * 0.10))`.

`historian_trigger_pending` is set to `true` by `review_finalize` when:
- `rounds_since_last_historian >= historian_interval` (periodic), OR
- `consecutive_discards >= plateau_trigger` (C2)

### 5.2 New Driver Stage: `historian`

New functions in `runner_driver.py`:

```python
def historian_run(campaign_dir: str = "runner/") -> dict[str, Any]:
    """Return metadata for the outer loop to pass to the Historian agent."""
    # Determine trigger type from state
    # Return: status, trigger, rounds_covered, campaign_dir

def historian_finalize(
    campaign_dir: str = "runner/",
    trigger: str = "periodic",       # "periodic" | "c2" | "periodic+c2"
    patterns_added: int = 0,
    assumptions_flagged: int = 0,
    tokens_used: int = 0,
) -> dict[str, Any]:
    """Update state after Historian completes."""
    # Reset rounds_since_last_historian = 0
    # Set last_historian_round = current round
    # Set historian_trigger_pending = False
    # If "c2" in trigger: reset consecutive_discards = 0
    # Add tokens_used to total_tokens["historian"]
```

New shell stage:
```bash
run_round.sh historian [--campaign-dir <path>]
run_round.sh historian-finalize --trigger <str> --patterns-added <int> --assumptions-flagged <int> --tokens-used <int> [--campaign-dir <path>]
```

### 5.3 Revised C2 Protocol

**Old flow:**
```
consecutive_discards >= 3
→ Planner emits escalation: C2
→ plan_check returns pause_c2
→ Human runs resolve_c2
→ c2_pending_diagnose = true
→ Planner must select A_diagnose next round
```

**New flow:**
```
consecutive_discards >= 3
→ review_finalize sets historian_trigger_pending = true
→ Outer loop runs historian stage before next Planner turn
→ Historian produces STRATEGY_MEMO.md, updates PATTERN_BOOK.md, audits assumptions
→ historian_finalize resets consecutive_discards = 0
→ Planner reads STRATEGY_MEMO.md as required input
```

`resolve_c2` retained as a manual override (human can still invoke it) but is no longer the default C2 path. `c2_pending_diagnose` field removed from state. `plan_check` no longer enforces C2 escalation.

### 5.4 Revised Loop Sequence

```
[If historian_trigger_pending]
  → run_round.sh historian
  → Historian agent reads state, writes STRATEGY_MEMO.md, PATTERN_BOOK.md, ASSUMPTION_REGISTER.md
  → run_round.sh historian-finalize --trigger <periodic|c2|periodic+c2> --patterns-added N --assumptions-flagged M --tokens-used T

→ Planner reads all inputs (now includes STRATEGY_MEMO.md, ASSUMPTION_REGISTER.md, PATTERN_BOOK.md)
→ Planner writes NEXT_EXPERIMENT.md

→ run_round.sh plan-check

→ Executor implements, runs
→ run_round.sh execute-finalize

→ Reviewer runs (evidence-first):
    Phase 1: reads run.log + tools → writes §Independent Assessment
    Phase 2: reads NEXT_EXPERIMENT.md → writes §Plan Comparison
    Phase 3: verdict + assumption registration + CAMPAIGN_JOURNAL.md
→ run_round.sh review-finalize
  (may set historian_trigger_pending for next iteration)
```

### 5.5 init_campaign Changes

Creates skeleton files at campaign init:
```python
(state_dir / "ASSUMPTION_REGISTER.md").write_text(assumption_register_skeleton(campaign_id))
(state_dir / "PATTERN_BOOK.md").write_text(pattern_book_skeleton(campaign_id))
# STRATEGY_MEMO.md is NOT created at init — only after first Historian run
```

EVAL_PROTOCOL.md gains new optional field:
```yaml
historian_interval: 10
```

If absent, driver defaults to 10.

---

## 6. Token Tracking

### 6.1 results.tsv New Columns

`log.py` appends to results.tsv per round:

```
planner_tokens   executor_tokens   reviewer_tokens   historian_tokens   round_total_tokens
```

Historian tokens written to the row of the round that triggered the Historian. Zero if unavailable.

### 6.2 Capture Mechanism

Primary: API-level token metadata captured by the outer loop and passed to finalize functions as optional integer parameters.

Fallback: Each role prompt includes a final instruction:
```
As the last line of your response, emit:
TOKENS_USED: <integer>
```
Driver parses from stdout when API metadata unavailable.

New parameters added:
```python
review_finalize(..., planner_tokens: int = 0, executor_tokens: int = 0, reviewer_tokens: int = 0)
historian_finalize(..., historian_tokens: int = 0)
```

### 6.3 TOKEN_SUMMARY.txt

New tool: `runner/tools/token_summary.py`. Reads results.tsv token columns. Writes `state/TOKEN_SUMMARY.txt` after each `review_finalize`. One-line digest:

```
Campaign tokens — total: 2.4M | avg/round: 48K | historian avg: 142K |
top cost: r48 (DE optimizer, 187K) | trend: stable (last 10 rounds avg=51K)
```

Planner reads as informational signal — not a budget constraint. Value: if recent rounds are high-cost AND low-ROI (many discards), the Planner can prefer cheaper experiments. Not mechanically enforced.

---

## 7. Complete Change Surface

### New Files
```
runner/roles/historian.md
runner/state/ASSUMPTION_REGISTER.md      (skeleton created at init)
runner/state/PATTERN_BOOK.md             (skeleton created at init)
runner/state/STRATEGY_MEMO.md            (written by first Historian run)
runner/state/TOKEN_SUMMARY.txt           (generated by tools/token_summary.py)
runner/tools/token_summary.py
```

### Modified Files
```
runner/roles/reviewer.md                 Evidence-first order; assumption registration; discard falsification check
runner/roles/planner.md                  New inputs; assumption-aware novelty check; pattern-informed strategy; Historian context section
runner/runner_driver.py                  historian_run(); historian_finalize(); revised review_finalize(); C2 change; token columns
runner/run_round.sh                      New 'historian' and 'historian-finalize' stages
runner/RUNNER.md                         New state files in Planner input list; Historian added to role list
runner/AGENTS.md                         Historian role recorded as harness fossil record update
runner/contracts/EVAL_PROTOCOL.md        historian_interval field; A_diagnose removed from action_types
runner/tools/schema.py                   Validate new EVAL_PROTOCOL fields; ASSUMPTION_REGISTER schema validation
log.py                                   New token columns in results.tsv header and append
```

### Removed / Retired
```
A_diagnose action type          Removed from EVAL_PROTOCOL.action_types
c2_pending_diagnose state flag  Replaced by historian_trigger_pending
plan_check C2 escalation gate   Removed (Planner no longer emits escalation: C2)
resolve_c2 as default C2 path   Retained for manual override; no longer default
```

### Schema Version
CAMPAIGN_STATE.json bumped to `$schema_version: 2`. Existing version-1 campaigns migrated by `historian_run` on first invocation (detects missing fields, adds defaults).

---

## 8. Validation: What This Design Would Have Changed

Applied retrospectively to ip-commercial-new-te:

| Round | Old behavior | New behavior |
|-------|-------------|--------------|
| r25 keep | No assumption registered | Reviewer writes A-25-1 ("NM is global", load-bearing, unverified) and A-25-2 ("stable to feature count", load-bearing, unverified) |
| r30 Historian | Does not exist | Historian runs (periodic K=10). Flags A-25-1 as critical. Adds "global weight optimization" to UNEXPLORED_TECHNIQUES.md. Diagnoses bottleneck as optimizer_quality. |
| r31 Planner | Selects CCI clinical features | Reads STRATEGY_MEMO.md. Sees optimizer_quality bottleneck + critical unverified A-25-1. Selects DE optimizer test instead. |
| r31 result | DE not tried until r48 | DE runs at r31. Finds 23.260. 17 rounds saved. |
| r32-r47 | 16 wasted rounds | Freed for re-evaluating discarded experiments under DE, or new technique classes |

---

## 9. Design Principles Upheld

All five original harness design principles are preserved:

1. **Artifact-first** — All new state is on disk (ASSUMPTION_REGISTER.md, STRATEGY_MEMO.md, PATTERN_BOOK.md). No new in-memory state.
2. **Producer ≠ verifier** — Historian is a new distinct role. It does not evaluate experiments (Reviewer's job) or plan experiments (Planner's job). It synthesizes. The Planner remains free to disagree with the Historian's advisory output.
3. **Reason strategically, compute tactically** — Historian reasons across time (LLM); token_summary.py computes costs (tool). Pattern extraction is LLM reasoning; results_query is tactical compute.
4. **Contracts sticky** — EVAL_PROTOCOL.md gains `historian_interval` but this is a configuration field, not a contract change. The C3 process is unchanged.
5. **Progressive complexity** — The Historian activates only on trigger (periodic or C2). It does not run every round. The base Planner/Executor/Reviewer loop is unchanged when the Historian is not triggered.
