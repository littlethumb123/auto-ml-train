# RUNNER.md — Autonomous ML Runner entry point

You are running an autonomous ML experiment campaign. **Read this file first, then follow pointers.**

> **Path convention:** All `contracts/` and `state/` paths below are relative to the campaign directory (e.g., `campaigns/<name>/contracts/`). Harness paths (`runner/tools/`, `runner/roles/`, `runner/AGENTS.md`) are relative to repo root.

## 0. Orientation

- Problem + success criteria: `contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `contracts/EVAL_PROTOCOL.md` (G3) — names mandatory tools, budgets
- Current state: `state/CAMPAIGN_STATE.json`
- History: `state/results.tsv`, `state/REVIEW.md`
- Memory: `state/DEAD_ENDS.md`, `state/NOTEBOOK.md`
- Retrospective: `state/CAMPAIGN_JOURNAL.md` — planned reasoning vs actual outcome per round
- Exploration frontier: `state/UNEXPLORED_TECHNIQUES.md` — technique classes not yet tried (Planner reads every round; mandatory when consecutive_discards ≥ 2)
- Priors (cross-campaign): `contracts/PRIORS.md`
- Meta-cognitive: `state/ASSUMPTION_REGISTER.md`, `state/PATTERN_BOOK.md`
- Historian synthesis: `state/STRATEGY_MEMO.md` (exists after first Historian run)
- Token digest: `state/TOKEN_SUMMARY.txt` (informational)

## 1. Your role for this turn

Pick the role that matches the current state:

- **Planner** — invoked when state expects a new `NEXT_EXPERIMENT.md`. Read `runner/roles/planner.md`.
- **Executor** — invoked after Planner and driver validated the plan. Read `runner/roles/executor.md`.
- **Reviewer** — invoked after Executor run. Read `runner/roles/reviewer.md`.
- **Historian** — invoked by the outer loop when `historian_trigger_pending` is true in `CAMPAIGN_STATE.json`. Runs before the next Planner turn. Read `runner/roles/historian.md`.

The driver (`runner/run_round.sh`) tells you which role to play.

## 1b. Autonomous operation (orchestrator loop)

For fully autonomous multi-round operation, read `runner/roles/orchestrator.md` instead
of picking a single role. The orchestrator drives the full Plan → Execute → Review →
Historian cycle, calling the driver between phases for validation.

**Interactive:** "Read runner/roles/orchestrator.md and run the campaign at campaigns/\<name\>"

**Headless:** `claude -p "Read runner/roles/orchestrator.md and run campaigns/<name>" --dangerously-skip-permissions`

**Resume:** "Read runner/roles/orchestrator.md and resume campaigns/\<name\> with --resume"

## 2. Hard invariants (never bypass)

1. G1–G3 signed before any experiment (driver refuses to init otherwise).
2. `runner/tools/anomaly.py` runs before any `keep` verdict.
3. Mandatory tools named in `EVAL_PROTOCOL.md §mandatory_tools` run before accepting small Δ; when `review-finalize` is called with `--tools-ran`, the driver mechanically rejects **`keep`** if any mandatory tool is missing from that list.
4. One git commit per experiment — driver enforces.
5. **Campaign branch:** Create a dedicated branch (e.g., `campaign/<campaign_id>`)
   before running `init`. All experiment commits happen on this branch. On **discard**,
   `git reset --hard HEAD~1` rolls back cleanly without affecting `main`. Merge the
   final best commit to `main` only after the campaign concludes.
5. Two repair attempts cap — Executor enforces.
6. Contracts are sticky — change only via C3 (approved diff).

## 3. Fossil record

Harness rules, lessons, and rules that apply across campaigns live in `runner/AGENTS.md`. Read it every role invocation.

## Token tracking

The driver auto-estimates token costs from round artifacts when exact counts are unavailable:

- **Planner tokens** — estimated from `NEXT_EXPERIMENT.md` size (3× input overhead)
- **Executor tokens** — estimated from the experiment commit diff (`git show`)
- **Reviewer tokens** — estimated from the latest `CAMPAIGN_JOURNAL.md` entry
- **Historian tokens** — estimated from `STRATEGY_MEMO.md` size

Estimates are directionally correct (±50%) and sufficient for relative cost comparisons in TOKEN_SUMMARY.txt. The Planner reads TOKEN_SUMMARY.txt each round and can see which action types cost more.

**To supply exact counts** (e.g. from Anthropic API `usage.input_tokens + usage.output_tokens`), pass them explicitly — they take precedence over estimates:

```bash
python runner/run_round.sh review-finalize \
  ...existing args... \
  --planner-tokens <int> \
  --executor-tokens <int> \
  --reviewer-tokens <int>
```

```bash
python runner/run_round.sh historian-finalize \
  ...existing args... \
  --tokens-used <int>
```

TOKEN_SUMMARY.txt is written after every `review-finalize` regardless.
