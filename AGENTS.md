# AGENTS.md — REDIRECT

This repository is now orchestrated by the runner at `runner/`. **Read `runner/RUNNER.md` first.** Role-specific prompts: `runner/roles/{planner,executor,reviewer}.md`. Harness fossil record: `runner/AGENTS.md`.

## Hard invariants (preserved from pre-runner era)

1. **Only `train.py` may be modified by the Executor role** during an experiment. `prepare.py`, `data/`, and `runner/contracts/*` are read-only.
2. **Primary metric is defined in `runner/contracts/EVAL_PROTOCOL.md`** — do not hand-pick one.
3. **Every experiment is one git commit.** Discards roll back with `git reset --hard HEAD~1`.
4. **Budgets** (per-experiment time and total experiment count) are defined in `EVAL_PROTOCOL.budgets`.
5. **Contracts are sticky** — change only via C3 (approved `tools/contract_diff` output).

Historical root `AGENTS.md` content is preserved in git history (pre-2026-04-21).
