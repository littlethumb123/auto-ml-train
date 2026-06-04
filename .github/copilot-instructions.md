# Copilot Instructions for auto_train

This repository is an autonomous ML experiment system with a multi-campaign architecture.

## Entry points
- **Harness architecture:** `runner/RUNNER.md`
- **Development practices:** `runner/AGENTS.md` (§Development practices)
- **Role prompts:** `runner/roles/{planner,executor,reviewer,historian}.md`

## Two modes of work
1. **Harness development** — modifying `runner/`, `shared/`, `tests/`. Feature branches, full test suite.
2. **Campaign execution** — running experiments inside `campaigns/<name>/`. Only `train.py` changes.

## Hard invariants
1. Only `train.py` (inside campaign dir) is modified during experiments.
2. `prepare.py`, `data/`, and `contracts/` are read-only.
3. One git commit per experiment. Discards use `git reset --hard HEAD~1`.
4. Primary metric + budgets live in each campaign's `contracts/EVAL_PROTOCOL.md`.
5. New campaigns: copy from `runner/campaign_template/`.
7. When stopping: summarize results, report best val_pr_auc, list top 3 approaches.
