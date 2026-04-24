# RUNNER.md — IP Commercial New TE Campaign entry point

You are running an autonomous ML experiment campaign for commercial inpatient (IP6) prediction using new TE embeddings. **Read this file first, then follow pointers.**

## 0. Orientation

- Problem + success criteria: `campaigns/ip-commercial-new-te/contracts/PROBLEM_CONTRACT.md` (G1)
- Data contract: `campaigns/ip-commercial-new-te/contracts/DATA_CONTRACT.md` (G2)
- Evaluation protocol: `campaigns/ip-commercial-new-te/contracts/EVAL_PROTOCOL.md` (G3)
- Current state: `campaigns/ip-commercial-new-te/state/CAMPAIGN_STATE.json`
- History: `campaigns/ip-commercial-new-te/state/results.tsv`, `campaigns/ip-commercial-new-te/state/REVIEW.md`
- Memory: `campaigns/ip-commercial-new-te/state/DEAD_ENDS.md`, `campaigns/ip-commercial-new-te/state/NOTEBOOK.md`
- Retrospective: `campaigns/ip-commercial-new-te/state/CAMPAIGN_JOURNAL.md` — planned reasoning vs actual outcome per round (Reviewer-owned, appended every round)
- Priors: `campaigns/ip-commercial-new-te/contracts/PRIORS.md`

**Primary metric:** `val_lift_1pct` (lift at top 1% of scored members — see EVAL_PROTOCOL.md).
**Feature sets:** `tabular_only` | `embedding_only` | `hybrid` — controlled by `FEATURE_SET` in `train.py`.
**Campaign dir flag:** `--campaign-dir campaigns/ip-commercial-new-te` (pass to all `run_round.sh` calls).

## 1. Your role for this turn

Pick the role that matches the current state:

- **Planner** — invoked when state expects a new `NEXT_EXPERIMENT.md`. Read `runner/roles/planner.md`.
- **Executor** — invoked after Planner and driver validated the plan. Read `runner/roles/executor.md`.
- **Reviewer** — invoked after Executor run. Read `runner/roles/reviewer.md`.

The driver tells you which role: `./runner/run_round.sh <stage> --campaign-dir campaigns/ip-commercial-new-te`

**Path substitution note:** Wherever `runner/roles/*.md` says `runner/contracts/` or `runner/state/`, substitute `campaigns/ip-commercial-new-te/contracts/` and `campaigns/ip-commercial-new-te/state/` respectively for this campaign.

## 2. Hard invariants (never bypass)

1. G1–G3 signed before any experiment (driver refuses to init otherwise).
2. `runner/tools/anomaly.py` runs before any `keep` verdict.
3. Both mandatory tools from EVAL_PROTOCOL.md (`runner.tools.anomaly`, `runner.tools.bootstrap_ci`) run before `keep`. Pass `--bootstrap-se <se>` from bootstrap_ci output to `review-finalize` so the driver can emit C3 advisories.
4. One git commit per experiment — driver enforces.
5. **Campaign branch:** `campaign/ip-commercial-new-te`. All experiment commits on this branch.
6. Two repair attempts cap — Executor enforces.
7. Contracts are sticky — change only via C3 (approved diff).
8. **Executor write scope:** Only `train.py` and any declared `experiment_helpers/<exp_id>/` files. NOT `prepare.py`, `shared/`, `campaigns/ip-commercial-new-te/contracts/`, `runner/`.

## 3. Key operational notes

- **Data:** `prepare.py` reads from a local parquet cache (`campaigns/ip-commercial-new-te/.cache/new_te.parquet`). First run auto-downloads from BigQuery (~20-30s). All subsequent runs read parquet (~3-5s).
- **Feature set:** Controlled by `FEATURE_SET = 'tabular_only'` in `train.py`. Executor changes this to `'hybrid'` or `'embedding_only'` per plan.
- **Metrics in run.log:** The Reviewer must parse `val_lift_1pct`, `val_auc_roc`, `val_lift_5pct`, `val_lift_10pct`, `val_auc_pr` from the `---` block in run.log.
- **bootstrap_ci metric:** Use `metric="lift_1pct"` (matches primary metric).

## 4. Fossil record

Read `runner/AGENTS.md` every role invocation for cross-campaign harness rules.
Campaign-specific lessons are in `campaigns/ip-commercial-new-te/state/NOTEBOOK.md` and `DEAD_ENDS.md`.
