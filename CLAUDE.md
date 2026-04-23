# CLAUDE.md — REDIRECT

See `AGENTS.md` (same content — both files mirror each other so any tool that reads either entry point finds the same invariants).

Entry point: `runner/RUNNER.md`. Role prompts: `runner/roles/`. Fossil record: `runner/AGENTS.md`.

## Hard invariants

1. Only `train.py` is modified by Executor during experiments.
2. `prepare.py`, `data/`, `runner/contracts/*` are read-only.
3. One git commit per experiment.
4. Primary metric + budgets live in `runner/contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky; change via C3 + `tools/contract_diff` + human approval.

Historical root `CLAUDE.md` content is preserved in git history (pre-2026-04-21).
