# RUNNER.md — Autonomous ML Runner entry point

You are running an autonomous ML experiment campaign. **Read this file first, then follow pointers.**

## 0. Orientation

- Problem + success criteria: `runner/contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `runner/contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `runner/contracts/EVAL_PROTOCOL.md` (G3) — names mandatory tools, budgets
- Current state: `runner/state/CAMPAIGN_STATE.json`
- History: `runner/state/results.tsv`, `runner/state/REVIEW.md`
- Memory: `runner/state/DEAD_ENDS.md`, `runner/state/NOTEBOOK.md`
- Retrospective: `runner/state/CAMPAIGN_JOURNAL.md` — planned reasoning vs actual outcome per round
- Priors (cross-campaign): `runner/contracts/PRIORS.md`

## 1. Your role for this turn

Pick the role that matches the current state:

- **Planner** — invoked when state expects a new `NEXT_EXPERIMENT.md`. Read `runner/roles/planner.md`.
- **Executor** — invoked after Planner and driver validated the plan. Read `runner/roles/executor.md`.
- **Reviewer** — invoked after Executor run. Read `runner/roles/reviewer.md`.

The driver (`runner/run_round.sh`) tells you which role to play.

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
