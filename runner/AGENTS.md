# AGENTS.md — Harness fossil record (M4)

**Scope:** All campaigns, all problems. Human-curated (or agent+human via C3). Read every role invocation.

## Lessons that became rules

### Evaluation reliability (from mar30–apr03 campaigns, reflection §7)

- Single-split PR-AUC on ~100 positives has CI ≈ ±0.005–0.010. Treat any Δ below `EVAL_PROTOCOL.primary_metric.noise_floor` as noise.
- Prefer `tools/bootstrap_ci` or `tools/cv_runner` when `EVAL_PROTOCOL.cv_scheme.n_splits >= 5`.

### Reason strategically, compute tactically (reflection §4)

- Model-family choice, problem framing, diagnosis → LLM reasoning.
- HP numerical search, CI computation, permutation importance → `runner/tools/*`.
- Do not hand-pick HP values. Use `tools/optuna_search` or declare a space inside `train.py`.

### Artifact-first discipline

- Every decision lives on disk. Chat is ephemeral.
- Reviewer never reads Executor chat; it reads `train.py`, `run.log`, `NEXT_EXPERIMENT.md`, and tool outputs.

### Producer ≠ verifier

- Each role is a fresh invocation with ONLY its §2 Inputs files.

### Bounded repair

- Executor has 2 attempts (Stripe cap). Structural failures escalate immediately.

## Known dead-ends that generalize across problems

(None yet promoted. Planner reads `runner/state/DEAD_ENDS.md` for campaign-specific lines; only structurally reusable ones are promoted here by human.)

## Harness changes (when to update this file)

Update when:

- A repeated surprise reveals a missing guardrail.
- Post-G4 review identifies a rule that applies to future campaigns.
- A contract mutation (C3) establishes a new invariant.
