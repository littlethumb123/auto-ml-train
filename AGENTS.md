# AGENTS.md — REDIRECT

This repository is now orchestrated by the runner at `runner/`. **Read `runner/RUNNER.md` first.** Role-specific prompts: `runner/roles/{planner,executor,reviewer,historian}.md`. Harness fossil record: `runner/AGENTS.md`.

## Hard invariants (preserved from pre-runner era)

1. **Only `train.py` may be modified by the Executor role** during an experiment. `prepare.py`, `data/`, and `contracts/*` inside each campaign are read-only.
2. **Primary metric is defined in each campaign's `contracts/EVAL_PROTOCOL.md`** — do not hand-pick one.
3. **Every experiment is one git commit.** Discards roll back with `git reset --hard HEAD~1`.
4. **Budgets** (per-experiment time and total experiment count) are defined in `EVAL_PROTOCOL.budgets`.
5. **Contracts are sticky** — change only via C3 (approved `tools/contract_diff` output).

## Project layout

- **Harness code**: `runner/` — driver, roles, tools, strategy (shared across all campaigns)
- **Campaign template**: `runner/campaign_template/` — copy to create a new campaign
- **Active campaigns**: `campaigns/<name>/` — each has own contracts/, state/, train.py
- **Shared utilities**: `shared/` — metrics, BQ loader
- **Tests**: `tests/`
