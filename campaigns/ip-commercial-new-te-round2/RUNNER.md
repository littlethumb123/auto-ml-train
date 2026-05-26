# RUNNER.md — IP Commercial New TE Round 2 Campaign

You are running an autonomous ML experiment campaign for commercial inpatient (IP6)
prediction using new TE embeddings. **Read this file first, then follow pointers.**

> **Path convention:** All `contracts/` and `state/` paths below are relative to this
> campaign directory (`campaigns/ip-commercial-new-te-round2/`). Harness paths
> (`runner/tools/`, `runner/roles/`, `runner/AGENTS.md`) are relative to repo root.

**Campaign dir flag:** `--campaign_dir campaigns/ip-commercial-new-te-round2`
(pass to all `run_round.sh` calls).

## 0. Orientation

- Problem + success criteria: `contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `contracts/EVAL_PROTOCOL.md` (G3) — names mandatory tools, budgets
- Strategy guide: `contracts/STRATEGY_GUIDE.md` — ML planning heuristics
- Priors (cross-campaign): `contracts/PRIORS.md`
- Current state: `state/CAMPAIGN_STATE.json`
- History: `state/results.tsv`, `state/REVIEW.md`
- Memory: `state/DEAD_ENDS.md`, `state/NOTEBOOK.md`
- Retrospective: `state/CAMPAIGN_JOURNAL.md` — planned reasoning vs actual outcome per round
- Exploration frontier: `state/UNEXPLORED_TECHNIQUES.md` — technique classes not yet tried (Planner reads every round; mandatory when consecutive_discards ≥ 2)
- Meta-cognitive: `state/ASSUMPTION_REGISTER.md`, `state/PATTERN_BOOK.md`
- Historian synthesis: `state/STRATEGY_MEMO.md` (exists after first Historian run)

**Primary metric:** `val_lift_1pct` (lift at top 1% of scored members — see EVAL_PROTOCOL.md).
**Feature sets:** `tabular_only` | `embedding_only` | `hybrid` — controlled by `FEATURE_SET` in `train.py`.

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

**Interactive:** "Read runner/roles/orchestrator.md and run the campaign at campaigns/ip-commercial-new-te-round2"

**Headless:** `claude -p "Read runner/roles/orchestrator.md and run campaigns/ip-commercial-new-te-round2" --dangerously-skip-permissions`

**Resume:** "Read runner/roles/orchestrator.md and resume campaigns/ip-commercial-new-te-round2 with --resume"

## 2. Hard invariants (never bypass)

1. G1–G3 signed before any experiment (driver refuses to init otherwise).
2. `runner/tools/anomaly.py` runs before any `keep` verdict.
3. Mandatory tools named in `EVAL_PROTOCOL.md §mandatory_tools` run before accepting small Δ; when `review-finalize` is called with `--tools-ran`, the driver mechanically rejects **`keep`** if any mandatory tool is missing from that list.
4. One git commit per experiment — driver enforces.
5. **Campaign branch:** `campaign/ip-commercial-new-te-round2`. All experiment commits on this branch.
6. Two repair attempts cap — Executor enforces.
7. Contracts are sticky — change only via C3 (approved diff).
8. **Executor write scope:** Only `train.py` and any declared `experiment_helpers/<exp_id>/` files. NOT `prepare.py`, `shared/`, `contracts/`, `runner/`.

## 3. Campaign-specific notes

- **Data:** `prepare.py` reads from a local parquet cache (`.cache/new_te.parquet`). First run auto-downloads from BigQuery (~20-30s). All subsequent runs read parquet (~3-5s).
- **Feature set:** Controlled by `FEATURE_SET = 'tabular_only'` in `train.py`. Executor changes this to `'hybrid'` or `'embedding_only'` per plan.
- **Metrics in run.log:** The Reviewer must parse `val_lift_1pct`, `val_auc_roc`, `val_lift_5pct`, `val_lift_10pct`, `val_auc_pr` from the `---` block in run.log.
- **bootstrap_ci metric:** Use `metric="lift_1pct"` (matches primary metric).

## 4. Fossil record

Read `runner/AGENTS.md` every role invocation for cross-campaign harness rules.
Campaign-specific lessons are in `state/NOTEBOOK.md` and `state/DEAD_ENDS.md`.
