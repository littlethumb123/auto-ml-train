# CLAUDE.md — REDIRECT

See `AGENTS.md` for the same invariants. Entry point: `runner/RUNNER.md`.

## Hard invariants

1. Only `train.py` (inside the campaign dir) is modified by Executor during experiments.
2. `prepare.py`, `data/`, and `contracts/` inside each campaign are read-only.
3. One git commit per experiment.
4. Primary metric + budgets live in each campaign's `contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky; change via C3 + `tools/contract_diff` + human approval.

## Project layout

- **Harness code**: `runner/` — driver, roles, tools, strategy (shared across all campaigns)
- **Campaign template**: `runner/campaign_template/` — copy to create a new campaign
- **Active campaigns**: `campaigns/<name>/` — each has own contracts/, state/, train.py
- **Shared utilities**: `shared/` — metrics, BQ loader
- **Tests**: `tests/`
