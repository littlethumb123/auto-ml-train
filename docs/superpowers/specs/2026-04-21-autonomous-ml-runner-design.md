# Autonomous ML Runner — Design Spec

**Date:** 2026-04-21
**Status:** Approved Section 1 (Architecture) from handoff v2; Sections 2–5 drafted here; pending user review before `writing-plans`.
**Companion docs:**
- Locked architecture and decisions: `docs/brainstorming/2026-04-21-autonomous-ml-runner-design-handoff-v2.md`
- HITL gate research: `docs/research/2026-04-21-hitl-evaluation-gate-research.md`
- Post-mortem / design principles: `docs/reflections/2026-04-21-design-principles-reflection.md`
- Harness literature review: `docs/research/AGENTIC_ML_HARNESS_LITERATURE_REVIEW.md`, `docs/research/literature_review/harness-engineering-literature-review.md`

---

## 0. Intent in one page

Build a greenfield `runner/` that turns the `auto_train` codebase from a bandit-driven optimizer into an **autonomous ML research agent with mandatory human framing and acceptance gates**. The agent learns strategically (via memory artifacts), computes tactically (via callable tools), and is always auditable on disk.

**Design principles (non-negotiable, from handoff §Architecture and reflection §4):**

1. **Artifact-first.** Every decision lives on disk; chat is ephemeral.
2. **Producer ≠ verifier.** The Reviewer never shares chat context with the Executor; it reads files and tool outputs only.
3. **Reason strategically, compute tactically.** Planner reasons; `tools/` compute; `contracts/` bind.
4. **Contracts sticky.** `PROBLEM_CONTRACT`, `DATA_CONTRACT`, `EVAL_PROTOCOL` are immutable between gates unless gate **C3** fires.
5. **Progressive complexity.** Level-0 (LLM + memory) is the default; Level-1..5 tools activate only on trigger (reflection §5).

**Four human gates** G1–G4 (mandatory) + **three conditional** C1–C3 (silent unless triggered). Autonomous loop between G3 and G4.

**MVP scope (confirmed from handoff):**
- Single model, single process, three roles with **context isolation** (fresh invocation per role, only listed artifacts).
- No multi-process, no cross-model reviewer — both **deferred to Phase 2**.
- Target problem: any supervised or unsupervised learning problem; the credit-card dataset is campaign 0.

**Resolved from handoff "Open items":**
| # | Item | Decision |
|---|------|---------|
| 1 | Artifact format | YAML frontmatter (machine-readable metadata) + fixed markdown sections (human contract). See §2.3. |
| 2 | `train.py` path | Stays at repo root, unchanged. `runner/experiment_helpers/<exp_id>/` is added to `sys.path` from `train.py` when imported. |
| 3 | `experiment_helpers/<exp_id>/` import layout | `<exp_id>` is the first 12 chars of the git commit hash (post-commit); imports via `from runner.experiment_helpers.<exp_id> import ...`. Not importable until the commit exists (enforced by Reviewer). |
| 4 | CLI shape | Each `runner/tools/*.py` is both a callable Python function and a CLI entry point (`if __name__ == "__main__": …`). No `python -m runner`, no Makefile — matches legacy `python3 abes_engine.py …`. |
| 5 | `run_card.md` | On-demand only, emitted by `explain_run.py` when invoked (not always-on). |
| 6 | Cross-model reviewer | Phase 2 only; documented as an error-handling upgrade in §4.7. |

---

## 1. Architecture (SUMMARY — approved in handoff v2)

See `docs/brainstorming/2026-04-21-autonomous-ml-runner-design-handoff-v2.md` §1 for the full approved architecture. Summarized here for self-containment:

### Top-level layout

```
runner/
  RUNNER.md                   # Lean agent entry; progressive disclosure
  AGENTS.md                   # Harness fossil record (M4); human-curated
  contracts/                  # Per-problem artifacts (G1–G4)
    PROBLEM_CONTRACT.md       # G1
    DATA_CONTRACT.md          # G2
    EVAL_PROTOCOL.md          # G3
    PRIORS.md                 # M3 — cross-campaign priors
    FINAL_REPORT.md           # G4
  state/                      # Per-campaign recoverable state
    results.tsv               # M1 — schema preserved from abes_engine
    DEAD_ENDS.md              # M2 — "do not retry"
    NOTEBOOK.md               # M2 — surprising observations
    NEXT_EXPERIMENT.md        # Planner output; required sections
    REVIEW.md                 # Reviewer output per round (accumulates)
    run_card.md               # Optional, from explain_run
    CAMPAIGN_STATE.json       # Round, budget, last commit, verdict, exp_id counter
  tools/                      # Tactical compute — callable functions
    (MVP list in §2.2)
  roles/
    planner.md
    executor.md
    reviewer.md
  experiment_helpers/
    <exp_id>/                 # Rare Executor writes; rolled back with train.py

train.py                      # Repo root — primary experiment entry
log.py                        # ~30 lines; results.tsv append + budget status
prepare.py                    # Read-only; unchanged
data/                         # Read-only; unchanged
```

`abes_engine.py` is **fully removed** (no deprecation stub). Surviving logic is redistributed: anomaly → `tools/anomaly.py`; results/budget → `log.py`; dead-ends → `DEAD_ENDS.md`.

### Human gates

| ID | Kind | Artifact / action | Default-if-skipped |
|----|------|-------------------|--------------------|
| **G1** | Mandatory | Approve `PROBLEM_CONTRACT.md` | Halt |
| **G2** | Mandatory | Approve `DATA_CONTRACT.md` (leakage audit informed by tools) | Halt |
| **G3** | Mandatory | Approve `EVAL_PROTOCOL.md` | Halt |
| **G4** | Mandatory | Approve `FINAL_REPORT.md` + `PRIORS.md` diff | Defer |
| **C1** | Conditional | Anomaly / impossible metric — human decides | Discard; continue |
| **C2** | Conditional | Plateau + family switch request — human redirect | Let agent proceed |
| **C3** | Conditional | Agent requests contract change | Reject (sticky) |

### Hard invariants (never bypassed)

1. G1–G3 signed before the autonomous loop starts.
2. `tools/anomaly.py` runs before any keep verdict.
3. Mandatory tools named in `EVAL_PROTOCOL.md` run before accepting any small Δ.
4. One git commit per experiment; no squashing.
5. **Two repair attempts** per run; then the experiment is auto-discarded (Stripe pragmatic cap).
6. Contracts are not silently mutated; C3 is the only path.

---

## 2. Components

This section is the heart of the spec: role prompt skeletons, tool signatures, and artifact schemas. It is intentionally verbose because Section 1 is already locked — the remaining risk is ambiguity in the interfaces.

### 2.1 Role prompt skeletons

All three role prompts follow a **five-block template** so harness tooling can parse them uniformly. The blocks, in order:

1. **Identity & invariants** — role name, what the role owns, what it must never do.
2. **Inputs** — the exact list of files / tool outputs the role is allowed to read. No other context is provided.
3. **Required procedure** — ordered, enumerated; Reviewer's rejection list is defined here.
4. **Outputs** — the exact file(s) the role must produce and their required sections.
5. **Escalation protocol** — when to emit a conditional gate signal (C1/C2/C3) instead of finishing normally.

Each role is invoked with a **fresh context window**: only `runner/AGENTS.md`, `runner/roles/<role>.md`, and the files listed in the role's "Inputs" block. No other role's chat history is passed in (ARIS reviewer-independence protocol, see HITL research §2).

#### 2.1.1 `runner/roles/planner.md` — skeleton

```markdown
# Planner

## 1. Identity & invariants
You are the Planner for campaign <campaign_id>. You own `state/NEXT_EXPERIMENT.md`.
You NEVER write code, edit `train.py`, or run experiments. You write a plan; the Executor executes it.

## 2. Inputs (exactly these — nothing else)
- `runner/AGENTS.md`                    # harness fossil record
- `runner/contracts/PROBLEM_CONTRACT.md` # approved at G1
- `runner/contracts/DATA_CONTRACT.md`    # approved at G2
- `runner/contracts/EVAL_PROTOCOL.md`    # approved at G3 (names mandatory tools)
- `runner/contracts/PRIORS.md`           # if present
- `runner/state/results.tsv`             # read via `tools/results_query`
- `runner/state/DEAD_ENDS.md`            # read via `tools/dead_ends_query`
- `runner/state/NOTEBOOK.md`
- `runner/state/REVIEW.md`               # last round only (if present)
- `runner/state/CAMPAIGN_STATE.json`

## 3. Required procedure
1. Read all inputs. Summarize the current best, last review verdict, and active dead-ends in one paragraph.
2. Query `tools/results_query` for the top-5 by val_<primary_metric> and by last 5 runs.
3. Query `tools/dead_ends_query` for patterns the current idea might collide with.
4. Choose ONE hypothesis that (a) does not retry a dead-end, (b) is testable within the
   time budget in `EVAL_PROTOCOL.md`, (c) respects the `DATA_CONTRACT.md` column whitelist.
5. Decide the `action_type` (see `EVAL_PROTOCOL.md` for the allowed list).
6. If the plan needs `experiment_helpers/<exp_id>/` files, list them explicitly in §Plan.
7. Write `state/NEXT_EXPERIMENT.md` per the schema in §2.3.4.

## 4. Outputs
- `runner/state/NEXT_EXPERIMENT.md` — MUST contain every required section (see schema).

## 5. Escalation protocol
- If N≥3 consecutive discards AND your best structural idea requires a model family not
  yet in `MODEL_FAMILIES` in the eval protocol: emit a **C2 (plateau/family switch)**
  block in `NEXT_EXPERIMENT.md` under `## Escalation` instead of a normal plan, then stop.
- If you believe a contract must change: emit a **C3** block (proposed diff) instead of
  a plan, then stop. Do not mutate contracts yourself.
```

#### 2.1.2 `runner/roles/executor.md` — skeleton

```markdown
# Executor

## 1. Identity & invariants
You are the Executor for campaign <campaign_id>. You own `train.py` and — only if the
Planner declared it — `runner/experiment_helpers/<exp_id>/*`.
You NEVER modify `prepare.py`, `runner/contracts/`, `runner/roles/`, `runner/tools/`,
`log.py`, other experiments' `train.py`, or other `experiment_helpers/<other_exp_id>/`.
You do not decide keep/discard; the Reviewer does.

## 2. Inputs (exactly these)
- `runner/AGENTS.md`
- `runner/contracts/PROBLEM_CONTRACT.md`, `DATA_CONTRACT.md`, `EVAL_PROTOCOL.md`
- `runner/state/NEXT_EXPERIMENT.md`       # the only plan you execute
- `train.py`                              # current best
- `runner/state/CAMPAIGN_STATE.json`

## 3. Required procedure
1. Read `NEXT_EXPERIMENT.md`. If any required section is missing or malformed, STOP
   and emit `REVIEW_REQUIRED: malformed_plan` to stdout; do not edit anything.
2. Edit `train.py` to implement EXACTLY the plan. One controlled change. No side quests.
3. If the plan declares `experiment_helpers/<exp_id>/` files, create them in that
   directory (create the directory first). Do not touch any other helper directory.
4. `git add train.py` and any `experiment_helpers/<exp_id>/*`. Commit with
   `experiment: [<action_type>] - <hypothesis>` (≤72 chars in subject).
5. `python3 train.py > run.log 2>&1` — treat non-zero exit as crash.
6. If crash: retry up to ONE MORE TIME with a minimal fix (syntax/typo). If second
   attempt also fails: STOP. Do not continue editing.
7. Emit `RUN_COMPLETE: <commit>` or `RUN_FAILED: <commit> <reason>` to stdout.

## 4. Outputs
- Modified `train.py` (always).
- New files under `runner/experiment_helpers/<exp_id>/` (only if planned).
- New git commit.
- `run.log` (always, via shell redirection).
- Stdout terminal line: `RUN_COMPLETE: <commit>` or `RUN_FAILED: <commit> <reason>`.

## 5. Escalation protocol
- Hit the 2-attempt cap → STOP and emit `RUN_FAILED: <commit> repair_cap_exceeded`.
- Plan says you must edit a read-only path → STOP and emit
  `REVIEW_REQUIRED: write_scope_violation <path>`. Do NOT attempt the edit.
```

#### 2.1.3 `runner/roles/reviewer.md` — skeleton

```markdown
# Reviewer

## 1. Identity & invariants
You are the Reviewer for campaign <campaign_id>. You own `state/REVIEW.md`,
`state/DEAD_ENDS.md`, `state/NOTEBOOK.md`, and the keep/discard verdict.
You are NEVER the Executor: you do not read the Executor's chat, only artifacts.
You do not edit `train.py`, contracts, or helpers.

## 2. Inputs (exactly these — NO executor chat or planner chat)
- `runner/AGENTS.md`
- `runner/contracts/EVAL_PROTOCOL.md`   # names mandatory tools
- `runner/state/NEXT_EXPERIMENT.md`     # the plan you are reviewing against
- `train.py`                            # as it stands after Executor's commit
- `run.log`                             # stdout of the run
- `runner/state/results.tsv`            # via tools/results_query
- Outputs from: `tools/anomaly`, and every tool named as mandatory in EVAL_PROTOCOL.md

## 3. Required procedure
1. Check the full Reviewer rejection list (see spec §8.3 items 1–8). If ANY triggers,
   verdict = `malformed` and STOP here (skip steps 2–8; still do step 9).
2. Parse metrics from `run.log`. If parse fails: verdict = `crash`.
3. Run `tools/anomaly` on the latest result. If fires: verdict = `anomaly` → emit **C1**.
4. For each tool named mandatory in `EVAL_PROTOCOL.md §Mandatory tools`: run it against
   the current run and record the output in `REVIEW.md §Tool outputs`.
5. Compute Δ = val_<primary_metric> − best_prior. Decide:
   - `keep`   if Δ > 0 AND no mandatory tool flagged regression AND not anomaly
   - `discard` otherwise
6. If `discard`: append a one-liner to `state/DEAD_ENDS.md` (only if the pattern is
   structurally different from existing entries).
7. If the result contains a **surprising but not dead-end** observation: append a
   bullet to `state/NOTEBOOK.md`.
8. Append the current round block to `state/REVIEW.md` per schema §2.3.5.
9. Emit stdout: `VERDICT: <keep|discard|anomaly|crash|malformed> <commit>`.

## 4. Outputs
- Append block in `runner/state/REVIEW.md`.
- Optional append in `DEAD_ENDS.md` / `NOTEBOOK.md`.
- Stdout verdict line.
- If `keep`: git keeps the commit; otherwise the runner driver calls `git reset --hard HEAD~1`.

## 5. Escalation protocol
- `anomaly` → emit **C1** block in `REVIEW.md §Escalation` with the anomaly tool output,
  the suspected cause, and proposed next step. Do not discard silently.
- If `tools/results_query` reports ≥3 consecutive discards AND Planner had flagged C2
  in the last `NEXT_EXPERIMENT.md`: propagate the C2 block verbatim into `REVIEW.md §Escalation`.
```

### 2.2 Tool signatures (MVP list from handoff)

All tools live under `runner/tools/`. Each file exposes a Python function and a `__main__` CLI so it can be invoked either from role code or from the shell. Return / exit codes follow a common convention:

| Code | Meaning |
|-----|--------|
| `0` | Success; result on stdout (or written to `--output`). |
| `2` | User error (bad CLI args, missing required input). |
| `3` | Contract violation (e.g., a tool asked to analyze a column absent from DATA_CONTRACT). |
| `4` | Internal compute error (with traceback to stderr). |

Every tool accepts `--campaign-dir <path>` (default: `runner/`) and `--json` (switches stdout to JSON for machine consumption). Tools must be **idempotent on inputs** — calling twice with the same inputs produces the same output.

#### 2.2.1 Gate-support tools

```python
# runner/tools/data_profile.py — G2
def data_profile(
    data_path: str,                    # e.g. "data/creditcard.csv"
    target_col: str,                   # from PROBLEM_CONTRACT
    output_md: str = "runner/contracts/_data_profile.md",
) -> dict:
    """
    Emits a markdown profile (row count, column dtypes, missingness, target distribution,
    per-numeric quantiles, per-categorical top-k). Non-destructive, reads only.
    Used as input to DATA_CONTRACT.md authoring.
    Raises: FileNotFoundError, ValueError(target_col missing).
    Exit codes: 0 success; 2 missing args; 4 compute error.
    """
```

```python
# runner/tools/leakage_audit.py — G2
def leakage_audit(
    data_contract_path: str,           # runner/contracts/DATA_CONTRACT.md
    data_path: str,
    target_col: str,
) -> dict:
    """
    Runs three checks:
      1. Target-adjacent column detection: any feature with
         |Pearson(col, target)| > 0.95 or AUC(col→target) > 0.98 gets flagged.
      2. Temporal leakage: if DATA_CONTRACT declares a temporal ordering, any
         feature computed *after* the prediction time (per the contract's per-column
         availability table) is flagged.
      3. Constant / single-value column check.
    Returns: {"flagged": [...], "passed": [...], "notes": [...]}.
    Exit codes: 0 success (even with flags); 3 contract violation (missing availability
    table when declared temporal); 4 compute.
    """
```

```python
# runner/tools/baseline_runner.py — G3
def baseline_runner(
    family: str,                       # "logreg" | "xgboost" | "rf" | "kmeans" etc.
    eval_protocol_path: str,
    output_path: str = "runner/state/_baseline.json",
) -> dict:
    """
    Runs a *minimal* baseline for the declared task type (classification /
    regression / clustering) using the metric and CV scheme from EVAL_PROTOCOL.md.
    Writes {family, metric_name, metric_value, metric_ci, fold_scores, runtime_s} to JSON.
    Supports multiple families; caller runs once per family. Used as the numeric
    target under which the autonomous loop is a failure (agent must beat baseline).
    Exit codes: 0; 2; 3 (eval protocol not readable / invalid); 4.
    """
```

#### 2.2.2 Within-loop tools

```python
# runner/tools/anomaly.py
def check_anomaly(
    latest_row: dict,                  # parsed row from results.tsv (or run.log)
    history: list[dict],               # prior rows (status != crash)
    floor: float = 0.75,               # from EVAL_PROTOCOL; default preserved from legacy ABES
) -> dict:
    """
    Returns {"fired": bool, "reason": str, "proposed_diagnostic": str}.
    Fires if:
      - status != "crash" AND 0 < latest.primary_metric < max(floor, 0.5*best_prior)
      - metric inversion suspected (predict_proba[:,1] mean < 0.5 * class prior; advisory)
    Simplified port of abes_engine.cmd_check anomaly branch — ~30 lines.
    Exit codes: 0 (always); 2 missing args.
    """
```

```python
# runner/tools/cv_runner.py
def cv_runner(
    estimator_factory,                 # callable returning a fresh estimator
    X, y,                              # already engineered per train.py
    scheme: str,                       # "stratified_kfold" | "kfold" | "group_kfold"
    n_splits: int,
    primary_metric: str,               # "pr_auc" | "roc_auc" | "rmse" | "silhouette" etc.
    random_state: int,
) -> dict:
    """
    Runs the CV scheme declared in EVAL_PROTOCOL.md. Returns
    {"fold_scores": [...], "mean": float, "std": float, "ci95": [lo, hi]}.
    CI via t-interval on fold scores (matches reflection §7 recommendation).
    Exit codes: 0; 2; 4. CLI version accepts a JSON config file path only (not callables).
    """
```

```python
# runner/tools/bootstrap_ci.py
def bootstrap_ci(
    y_true, y_prob_or_pred,
    metric: str,                       # "pr_auc" | "roc_auc" | "f1" | ...
    n_boot: int = 1000,
    random_state: int = 42,
    alpha: float = 0.05,
) -> dict:
    """
    Returns {"metric": float, "ci_lo": float, "ci_hi": float, "se": float, "n_boot": int}.
    Default configured for the reflection's "is a 0.003 gain real?" question.
    Exit codes: 0; 2; 4.
    """
```

```python
# runner/tools/paired_comparison.py
def paired_comparison(
    a_scores: list[float],             # e.g. fold PR-AUCs for candidate
    b_scores: list[float],             # same folds for baseline/prior-best
    test: str = "wilcoxon",            # or "t" for paired t-test
) -> dict:
    """
    Fold-paired test (non-parametric by default). Returns
    {"p_value": float, "effect_size": float, "direction": "a>b"|"b>a"|"tie"}.
    Used by Reviewer when Δ is small (< 0.005) to decide if the improvement is real.
    Exit codes: 0; 2.
    """
```

```python
# runner/tools/optuna_search.py
def optuna_search(
    objective_py_path: str,            # path to a .py exposing `objective(trial) -> float`
    n_trials: int,
    timeout_s: int,
    direction: str = "maximize",
    study_name: str | None = None,
    seed: int = 13,
) -> dict:
    """
    Thin wrapper. Runs Optuna TPE, returns {"best_params": {...}, "best_value": float,
    "n_completed": int, "pruned": int}. Used when the Planner decides the current
    experiment is "tune within a fixed family" (reflection Level-1 escalation).
    Exit codes: 0; 2 (bad objective file); 4.
    """
```

#### 2.2.3 Memory / transparency tools

```python
# runner/tools/results_query.py
def results_query(
    filter_expr: str = "status != 'crash'",   # pandas .query() expression
    order_by: str = "val_pr_auc",             # the primary metric column
    limit: int = 10,
    campaign_dir: str = "runner/",
) -> list[dict]:
    """
    Reads `runner/state/results.tsv`, filters + orders, returns top rows as list of dicts.
    CLI: `python3 runner/tools/results_query.py --filter "model_family == 'xgboost'" --limit 5`.
    Exit codes: 0; 2; 3 (results.tsv schema mismatch).
    """
```

```python
# runner/tools/dead_ends_query.py
def dead_ends_query(
    pattern: str | None = None,               # substring/regex match on DEAD_ENDS.md lines
    campaign_dir: str = "runner/",
) -> list[str]:
    """
    Returns the list of active dead-end one-liners (optionally filtered).
    Used by Planner in its required procedure step 3.
    Exit codes: 0; 2.
    """
```

```python
# runner/tools/explain_run.py
def explain_run(
    commit: str,                               # short SHA of the run
    output_path: str = "runner/state/run_card.md",
    campaign_dir: str = "runner/",
) -> str:
    """
    Builds a human-readable run card for ONE experiment:
      - commit, hypothesis, action_type (from NEXT_EXPERIMENT for that round)
      - metrics parsed from run.log
      - diff summary of train.py (and experiment_helpers if any)
      - which mandatory tools ran and what they said
    Writes markdown to output_path, returns the path. On-demand only.
    Exit codes: 0; 2; 3 (commit not found).
    """
```

#### 2.2.4 Governance tool (C3)

```python
# runner/tools/contract_diff.py
def contract_diff(
    contract_name: str,                        # "PROBLEM" | "DATA" | "EVAL"
    proposed_path: str,                        # path to the proposed new contract
    campaign_dir: str = "runner/",
) -> dict:
    """
    Produces a structured diff (added / removed / modified fields keyed by the
    contract's YAML frontmatter and H2 sections). Returns
    {"contract": str, "changes": [{"field": ..., "before": ..., "after": ...}],
     "risk_level": "low"|"medium"|"high"}.
    Used by the Planner/Reviewer when emitting a C3 escalation. Does NOT apply
    the diff — the human does, after approval.
    Exit codes: 0; 2; 3 (missing current contract).
    """
```

#### 2.2.5 Unsupervised support

```python
# runner/tools/clustering_eval.py
def clustering_eval(
    X, labels,                                 # predicted cluster labels
    metrics: list[str] = ("silhouette", "davies_bouldin", "calinski_harabasz"),
    random_state: int = 42,
) -> dict:
    """
    Returns {metric_name: value} for unsupervised runs. Used only when
    PROBLEM_CONTRACT.task_type == "clustering" (see §2.3.1 allowed values).
    Exit codes: 0; 2; 4.
    """
```

#### 2.2.6 Deferred to Phase 2 (named so Planner can reference them as unavailable)

`multi_fidelity.py`, `stacking.py`, `feature_selection.py`, `calibration.py`, `shap_report.py`, `dimred_eval.py`, `integrity_check.py`. If invoked in MVP, exit code `2` with message `"deferred_to_phase_2"`.

### 2.3 Artifact schemas

**Convention (all artifacts):** YAML frontmatter at the top between `---` delimiters, then fixed markdown sections (H2 headers, prefixed by a number, e.g. `## 1. Task`). Human-authored prose inside each section; machine-readable fields in frontmatter. Every schema lists REQUIRED vs OPTIONAL fields and sections; a Reviewer rejection happens when a required field/section is missing.

All numeric fields use YAML native types (float / int / list). Dates are ISO-8601 `YYYY-MM-DD`.

#### 2.3.1 `contracts/PROBLEM_CONTRACT.md` (G1)

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"          # kebab-case; REQUIRED
problem_title: "Credit-card fraud detection"   # REQUIRED
task_type: "binary_classification"             # enum: binary_classification |
                                               #       multiclass_classification |
                                               #       regression | clustering |
                                               #       anomaly_detection; REQUIRED
unit_of_observation: "transaction"             # REQUIRED (e.g. "customer-day")
target:                                        # REQUIRED
  name: "Class"
  positive_class: 1
  definition: "1 if labeled fraud by issuer within 30 days of transaction."
success_criteria:                              # REQUIRED (ordered: primary first)
  - "val_pr_auc >= 0.85 on held-out validation"
  - "lift_at_10 >= 8.0"
constraints:                                   # REQUIRED (may be empty list)
  - "No third-party data integration."
  - "Total campaign compute <= 60s/experiment, 100 experiments."
non_goals:                                     # REQUIRED (may be empty list)
  - "No deployment / inference service."
  - "No fairness / subgroup analysis in this campaign (future)."
approved_at: null                              # ISO date, filled at G1 signoff
approved_by: null                              # human name/handle
---

## 1. Task

<Free-form description of what the agent is solving. 1–3 paragraphs.>

## 2. Why the task matters

<Business / research framing. Used by Planner for tie-breaking.>

## 3. Success criteria (detail)

<Expansion of the frontmatter success_criteria with rationale.>

## 4. Constraints (detail)

<Expansion of the frontmatter constraints.>

## 5. Non-goals (detail)

<Expansion of the frontmatter non_goals.>
```

**Reviewer must reject** if any REQUIRED frontmatter field is null/missing or any `## N.` section is missing.

#### 2.3.2 `contracts/DATA_CONTRACT.md` (G2)

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"          # must match PROBLEM_CONTRACT
data_sources:                                  # REQUIRED, list of dicts
  - path: "data/creditcard.csv"
    n_rows: 284807
    n_cols: 31
    primary_key: "implicit row index"
temporal:                                      # REQUIRED
  is_temporal: false                           # bool
  order_column: null                           # column if is_temporal else null
  prediction_time_column: null                 # when the label becomes known
columns:                                       # REQUIRED, one entry per feature + target
  - name: "Time"
    dtype: "float64"
    role: "feature"                            # enum: feature | target | id | drop
    available_at_prediction: true              # bool
    notes: "Seconds since first observation."
  - name: "Amount"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  # ... V1..V28 elided ...
  - name: "Class"
    dtype: "int64"
    role: "target"
    available_at_prediction: false
leakage_audit:                                 # REQUIRED, from tools/leakage_audit
  performed_at: "2026-04-21"
  flagged_columns: []
  notes: "Audit clean."
splits:                                        # REQUIRED — mirrors prepare.py for MVP
  train: "stratified 60% of data"
  val:   "stratified 20% of data"
  test:  "stratified 20% of data"
  random_seed: 42
approved_at: null
approved_by: null
---

## 1. Schema summary

<Narrative description of the data: n rows, target prevalence, any special dtypes.>

## 2. Availability table (narrative)

<Plain-English expansion of the per-column `available_at_prediction` — especially any
column whose availability is not obvious from the name.>

## 3. Leakage audit summary

<Human-readable expansion of the frontmatter `leakage_audit` — what was checked,
what was flagged, what was dismissed as non-leaky and why.>

## 4. Transformations applied pre-agent (if any)

<E.g., "V1..V28 were produced by PCA at data generation time; original columns are
not accessible.">

## 5. Known data quality issues

<E.g., "None", or "Amount has a long right tail; consider log1p at feature-engineering time.">
```

**Reviewer must reject** if `leakage_audit.performed_at` is null.

#### 2.3.3 `contracts/EVAL_PROTOCOL.md` (G3)

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
primary_metric:                                # REQUIRED
  name: "pr_auc"                               # arbitrary string; tools must recognize
  direction: "maximize"                        # enum: maximize | minimize
  noise_floor: 0.005                           # from reflection §7 — treat Δ < this as noise
acceptance_threshold:                          # REQUIRED
  baseline_family: "logreg"                    # which baseline to beat (from tools/baseline_runner)
  min_improvement: 0.01                        # agent's final best must beat baseline by this
cv_scheme:                                     # REQUIRED
  type: "single_holdout"                       # enum: single_holdout | stratified_kfold | kfold | group_kfold
  n_splits: 1
  random_state: 42
  notes: "Preserving prepare.py splits for MVP; upgrade to stratified_kfold in Phase 2."
bootstrap_ci:                                  # REQUIRED
  enabled: true
  n_boot: 1000
  alpha: 0.05
paired_test:                                   # REQUIRED
  enabled: true
  test: "wilcoxon"                             # only applies when cv_scheme.n_splits >= 5
mandatory_tools:                               # REQUIRED — Reviewer runs all before keep
  - "tools/anomaly.py"
  - "tools/bootstrap_ci.py"
action_types:                                  # REQUIRED — allowed Planner labels
  - "A_model"
  - "A_feature"
  - "A_hp"
  - "A_imbalance"
  - "A_ensemble"
  - "A_diagnose"
  - "A_validate"
  - "A_restart"
budgets:                                       # REQUIRED
  time_budget_s: 60
  hard_timeout_s: 90
  max_experiments: 100
  max_repair_attempts: 2                       # Stripe cap; invariant (not a soft knob)
plateau_trigger:                               # REQUIRED
  consecutive_discards: 3                      # Planner must emit C2 on N≥3
anomaly:                                       # REQUIRED
  floor: 0.75
  relative: 0.5                                # <0.5 * best_prior also anomalous
approved_at: null
approved_by: null
---

## 1. Rationale

<Why these choices? Concretely reference reflection §7 and PROBLEM_CONTRACT.>

## 2. How keep/discard is decided

<Plain English: Δ vs best_prior, anomaly must not fire, mandatory tools must all pass.>

## 3. How plateau is handled

<Plain English: after N=3 consecutive discards, Planner must emit C2 instead of a plan.>

## 4. Contract change policy

<Reference to C3 gate: contracts are sticky; use tools/contract_diff + human approval.>
```

**Reviewer must reject** a keep verdict if `mandatory_tools` is non-empty and any named tool was not run in the round.

#### 2.3.4 `state/NEXT_EXPERIMENT.md` (per round, Planner output)

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
round: 7                                       # monotonic integer
planner_invocation_at: "2026-04-21T18:30:00Z"
action_type: "A_hp"                            # must be in EVAL_PROTOCOL.action_types
hypothesis: "Narrowing LightGBM num_leaves to [15,63] will escape the current plateau."
expected_effect_size: 0.003                    # float; may be 0
base_commit: "83acdb8"                         # commit the Executor starts from
touches_helpers: false                         # bool
helpers_declared: []                           # list of relative paths; may be empty
escalation: null                               # null | "C2" | "C3"
---

## 1. Context summary

<1 paragraph, cites last REVIEW.md verdict, current best, active dead-ends referenced.>

## 2. Evidence from memory

- results_query output (top-5 relevant rows) — raw JSON or tabular
- dead_ends_query output — matched patterns (or "none")
- NOTEBOOK observations drawn on (cite lines)

## 3. Plan

<Enumerated, unambiguous. Executor follows EXACTLY. Example:>
1. In `train.py`, replace the Optuna search space for `num_leaves` from (15, 127) to (15, 63).
2. Keep all other hyperparameter bounds unchanged.
3. Keep n_trials=50, timeout=25.

## 4. Helpers

<If `touches_helpers: true`, list the exact files to create under
`runner/experiment_helpers/<base_commit_short>/*` and a one-line purpose per file.
If `touches_helpers: false`, this section reads: "None.">

## 5. How this differs from prior experiments

<1 paragraph. Explicitly distinguishes from each row in results_query hit.>

## 6. Escalation (only if `escalation` frontmatter is non-null)

### For C2 (plateau / family switch):
- Rationale: why current family is exhausted.
- Proposed alternative family and why it is structurally different.
- What signal would confirm the switch was right.

### For C3 (contract change request):
- Which contract (PROBLEM | DATA | EVAL).
- Diff summary (field-level).
- Why the existing contract blocks progress.
```

**Reviewer must reject** if action_type is not in the approved list, if `touches_helpers: true` but `helpers_declared` is empty, or if `escalation` is non-null but §6 is missing.

#### 2.3.5 `state/REVIEW.md` (per-round, Reviewer output; appended)

The file accumulates across the campaign — each round adds one block delimited by `<!-- round:N -->` HTML comments so tools can parse by round without overwriting. Frontmatter applies to the file as a whole and is updated on every write.

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
last_round: 7                                  # frontmatter updated each append
last_verdict: "discard"                        # the latest block's verdict
---

<!-- round:7 -->
## Round 7

### Verdict
`discard` at commit `83acdb8` (Δ val_pr_auc = -0.002 vs best 0.846).

### Plan adherence
train.py diff matches §3 of NEXT_EXPERIMENT.md round 7. OK.

### Metrics parsed
- val_pr_auc: 0.844
- lift_at_10: 9.60
- macro_f1: 0.902
- val_f1:    0.802
- n_features: 33

### Tool outputs
- anomaly: `fired=false reason=within_expected_range`
- bootstrap_ci: `metric=0.844 ci=[0.828, 0.861] se=0.008`
- paired_comparison (if applicable): `N/A (cv_scheme n_splits=1)`

### Dead-end update
- Appended to DEAD_ENDS.md: "Narrowing num_leaves to [15,63] on LGBM does not escape plateau."

### Notebook update
- None this round.

### Escalation
- None. (If anomaly fired, a `C1` block appears here with tool output and proposed next step.)
<!-- /round:7 -->
```

#### 2.3.6 `state/DEAD_ENDS.md`

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
count: 9
last_updated: "2026-04-21"
---

# Dead ends — do NOT retry

<!-- Each line is a one-sentence dead-end; the Reviewer appends here during
`discard` verdicts if the pattern is structurally new. Planner reads these
via tools/dead_ends_query before proposing. -->

- SMOTE + scale_pos_weight — double-counts imbalance (mar30)
- QuantileTransformer on tree models — monotonic transform can't change splits (mar30)
- DART booster — exceeds 90s timeout at 500 trees (apr01)
- LightGBM is_unbalance=True — inverts probabilities (mar30+apr01)
- Narrowing num_leaves to [15,63] on LGBM — does not escape plateau (apr21 r7)
```

#### 2.3.7 `state/NOTEBOOK.md`

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
count: 3
last_updated: "2026-04-21"
---

# Observations worth remembering (non-dead-end)

<!-- Surprising results, partial wins, or "we should come back to this" items. Each
bullet prefixed by the round it came from. Planner reads these when choosing the
next hypothesis. -->

- r3: XGBoost depth=4 and depth=6 both found independent optima — basin not a single point.
- r5: Removing time_features improved by ~0.003 AND simplified the pipeline.
- r6: lift_at_10 is ~3x more stable across seeds than val_pr_auc on this split.
```

#### 2.3.8 `state/results.tsv`

**Preserved exactly** from legacy `abes_engine.py` (handoff: "schema preserved"). Columns:

```
commit  val_pr_auc  lift_at_10  macro_f1  val_f1  status  n_features  model_family  action_type  hypothesis  description
```

`log.py` owns appends — no direct writes from roles. `results_query` reads this file.

#### 2.3.9 `state/CAMPAIGN_STATE.json`

```jsonc
{
  "$schema_version": 1,
  "campaign_id": "apr21-creditcard-fraud",
  "round": 7,                          // monotonic; incremented by Reviewer
  "exp_id_counter": 7,                 // equals round in MVP; separated for Phase 2
  "last_commit": "83acdb8",            // short SHA of the most recent run
  "last_verdict": "discard",           // mirrors REVIEW.md frontmatter
  "best_so_far": {                     // running best, primary metric only
    "commit": "37f4048",
    "primary_metric": 0.846
  },
  "consecutive_discards": 3,
  "budget_used": 7,
  "budget_total": 100,
  "created_at": "2026-04-21T12:00:00Z",
  "updated_at": "2026-04-21T18:45:00Z"
}
```

Owner: `log.py` writes it (after Reviewer emits a verdict). No role writes it directly. This is the single read-only source of truth for budget and "where are we" recovery.

#### 2.3.10 `contracts/PRIORS.md` (M3)

```markdown
---
schema_version: 1
problem_id: "creditcard-fraud"                 # reused across campaigns
last_campaign: "apr21-creditcard-fraud"
updated_at: "2026-04-21"
---

## Known good

- log1p(Amount) adds signal (confirmed mar30, apr01, apr21).
- Amount*V1 and Amount*V2 interactions add signal.
- XGBoost depth in [4,6] is the canonical range for single-model runs.

## Known bad

- v_interactions (V1*V2, V1*V3, V3*V4) are noise.
- time_features are noise.
- SMOTE + scale_pos_weight double-counts imbalance.

## Known ceilings

- Single-holdout PR-AUC at ~0.846 on this split; above this, need CV-with-CI to trust Δ.

## Open questions (for next campaign)

- Does 5-fold CV raise the observed ceiling or confirm the cap is structural?
- Does LightGBM match XGBoost after fixing the is_unbalance inversion?
```

Only updated at G4 via human-approved promotion of M2 items. No role writes this directly; the G4 human edits it.

#### 2.3.11 `contracts/FINAL_REPORT.md` (G4)

```markdown
---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
final_commit: "<sha>"
final_primary_metric: 0.852
final_ci: [0.834, 0.869]
baseline_primary_metric: 0.810
n_experiments: 42
n_keeps: 7
n_discards: 35
reviewed_at: null
reviewed_by: null
---

## 1. Headline

<1 paragraph: what was the best approach, by how much it beat baseline, CI overlap.>

## 2. What worked

<Enumerated list of keep commits with short rationale.>

## 3. What did not work (and why)

<Reference to DEAD_ENDS.md — no need to repeat; cite.>

## 4. Statistical caveats

<CI overlap with baseline? paired test significance? any anomalies? reflection §7.>

## 5. Recommended priors update

<Diff for PRIORS.md — what to add/remove/modify.>

## 6. Open questions

<What should a follow-up campaign try?>
```

### 2.4 `log.py` — 30-line utility

Not a role; not in `tools/`. Owns two operations: append a row to `results.tsv` AND update `CAMPAIGN_STATE.json`. Single entry point:

```python
# log.py
def append_result(
    commit: str,
    metrics: dict,         # parsed from run.log by caller
    status: str,           # "keep" | "discard" | "anomaly" | "crash" | "malformed"
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
) -> None: ...
```

Invoked by the runner driver (see §3) after the Reviewer emits a verdict.

---

## 3. Data flow

Two flows: the **gated setup flow** (G1→G2→G3) and the **autonomous loop** (between G3 and G4). A third flow describes **recovery** (interrupted campaign resume).

### 3.1 Setup flow (human-involved)

```
human intent ──▶ [G1] ──▶ [G2] ──▶ [G3] ──▶ ready to loop

[G1] Human + Planner author PROBLEM_CONTRACT.md.
     Planner may only propose; human fills/approves. `approved_by` + `approved_at`
     are set by human. No autonomous transition to G2 without both fields set.
[G2] tools/data_profile → tools/leakage_audit → Planner drafts DATA_CONTRACT →
     human reviews + signs. `leakage_audit.performed_at` is a required frontmatter
     field; Reviewer rejects if null.
[G3] tools/baseline_runner (once per candidate baseline family) → Planner drafts
     EVAL_PROTOCOL.md → human signs. Once signed, `mandatory_tools` and
     `acceptance_threshold.min_improvement` are immutable without a C3 diff.
```

`CAMPAIGN_STATE.json` is initialized (round=0, budget_total from EVAL_PROTOCOL, best_so_far.primary_metric = null) only after G3 is signed. Until then, no loop.

### 3.2 Autonomous loop (between G3 and G4)

Driven by a thin orchestration shell script `runner/run_round.sh` (or the equivalent hand-invocation) — the driver is linear, stateless between rounds, and reads `CAMPAIGN_STATE.json` to know what round it is.

```
Round N:
  1. DRIVER  : read CAMPAIGN_STATE.json
               if round >= budget_total:
                   write final status "budget_exhausted"; stop.
               (plateau / family-switch is NOT a halt condition here — it is surfaced
                by the Planner as escalation=C2; see step 2.)

  2. PLANNER : fresh invocation
               inputs: per §2.1.1
               output: state/NEXT_EXPERIMENT.md
               DRIVER reads the NEXT_EXPERIMENT frontmatter:
                 if escalation == "C2":
                     pause loop; surface C2 block to human (see §4.4);
                     on human resume, re-invoke PLANNER for the same round N.
                 if escalation == "C3":
                     pause loop; run tools/contract_diff; surface to human (§4.5);
                     on approval + manual apply, re-invoke PLANNER for round N.
                 if escalation is null:
                     continue to step 3.

  3. EXECUTOR: fresh invocation
               inputs: per §2.1.2
               output: train.py edit + git commit + run.log
               stdout contracts recognized by driver:
                 REVIEW_REQUIRED:<reason>       → treat as `malformed`; do NOT invoke
                                                  Reviewer; skip to step 5 with
                                                  synthetic verdict=malformed
                                                  (no commit exists to roll back).
                 RUN_COMPLETE:<commit>          → continue to step 4.
                 RUN_FAILED:<commit> <reason>   → treat as `crash`; skip to step 5
                                                  with synthetic verdict=crash.

  4. REVIEWER: fresh invocation (only reached on RUN_COMPLETE)
               inputs: per §2.1.3 (artifacts only; NO Executor chat)
               runs tools/anomaly + every mandatory tool
               output: state/REVIEW.md append + DEAD_ENDS/NOTEBOOK if applicable
               stdout contract: VERDICT:<keep|discard|anomaly|crash|malformed> <commit>

  5. DRIVER  : on verdict (real or synthetic from step 3):
                 keep      → leave commit; log.py appends row (status=keep);
                             consecutive_discards := 0; increment round
                 discard   → `git reset --hard HEAD~1`; log.py appends row
                             (status=discard); consecutive_discards += 1; increment round
                 anomaly   → leave commit in place (for inspection); log.py appends
                             row (status=anomaly); consecutive_discards unchanged;
                             surface C1 to human (§4.3); pause loop; on human resume,
                             round advances to N+1.
                 crash     → if a commit exists: `git reset --hard HEAD~1`; else skip.
                             log.py appends row (status=crash); consecutive_discards += 1;
                             increment round.
                 malformed → if a commit exists: `git reset --hard HEAD~1`; else skip.
                             log.py appends row (status=malformed); consecutive_discards
                             += 1; increment round. If the last 2 verdicts are both
                             `malformed`: halt loop with BUG status (§4.6).
  6. go to 1.
```

**Key invariants enforced by the driver (not the roles):**

- Git commit happens inside the Executor run; the driver rolls back ONLY on discard / crash / malformed AND only if a commit exists.
- `log.py` appends one row per round regardless of verdict, so `results.tsv` is the complete audit trail (including anomaly / crash / malformed rows).
- Round increments on every terminal verdict (keep, discard, crash, malformed, anomaly-after-resume). Budget is about work attempted, not kept.
- `consecutive_discards` in `CAMPAIGN_STATE.json` increments on `discard`, `crash`, `malformed`; resets to 0 on `keep`; is **unchanged** on `anomaly` (anomaly is not a failed experiment, it is a suspicious result requiring inspection).
- The plateau trigger (`consecutive_discards >= EVAL_PROTOCOL.plateau_trigger.consecutive_discards`) is **not** a driver halt. It is a signal the **next Planner** is required to convert into an `escalation: "C2"` plan. The driver only halts the loop when it sees C2 in the NEXT_EXPERIMENT.md (step 2).

### 3.3 Recovery flow

Any fresh agent session can resume by:

1. Read `runner/state/CAMPAIGN_STATE.json` — know current round, budget, last verdict, best.
2. Read `runner/state/REVIEW.md` last block — know what the last Reviewer said.
3. Read `runner/state/NEXT_EXPERIMENT.md` — if round matches CAMPAIGN_STATE and no REVIEW for it, we're mid-Executor; run Reviewer. Otherwise loop is clean to invoke Planner for round+1.
4. `git log --oneline -n 10` — sanity check commit line matches `last_commit`.

No special recovery commands; the artifacts are the state.

### 3.4 Data flow diagram

```
┌──────────────┐
│ human intent │──────┐
└──────────────┘      │
                      ▼
                 ┌────────┐       ┌────────┐       ┌────────┐
                 │  G1    │──────▶│  G2    │──────▶│  G3    │
                 │ PROBL. │       │ DATA   │       │ EVAL   │
                 │ CONTR. │       │ CONTR. │       │ PROTO  │
                 └────────┘       └────────┘       └───┬────┘
                                                      │
                                                      ▼
         ┌──────────────────── AUTONOMOUS LOOP ────────┴──────────────────┐
         │                                                               │
         │   CAMPAIGN_STATE.json                                         │
         │        │                                                      │
         │        ▼                                                      │
         │   ┌─────────┐   NEXT_EXPERIMENT.md    ┌─────────┐             │
         │   │ PLANNER │ ────────────────────────▶│ EXECUTOR│             │
         │   │ (fresh) │                         │ (fresh) │             │
         │   └─────────┘                         └────┬────┘             │
         │        ▲                                   │ train.py commit │
         │        │                                   │ run.log         │
         │        │                                   ▼                  │
         │        │                              ┌─────────┐             │
         │        │    REVIEW.md (append)        │ REVIEWER│             │
         │        └──────────────────────────────│ (fresh) │             │
         │                                       └────┬────┘             │
         │                                            │ verdict          │
         │                                            ▼                  │
         │                                       ┌─────────┐             │
         │                                       │ DRIVER  │             │
         │                                       │ keep /  │             │
         │                                       │ reset / │             │
         │                                       │ log.py  │             │
         │                                       └────┬────┘             │
         │                                            │                  │
         │                                            │ (C1/C2 pause)    │
         │                                            ▼                  │
         │                              ┌── human escalation ──┐         │
         │                              └──────────┬───────────┘         │
         │                                         │                      │
         └─────────────────────────────────────────┼──────────────────────┘
                                                   ▼
                                               ┌────────┐
                                               │  G4    │
                                               │ FINAL_ │
                                               │ REPORT │
                                               └────────┘
```

---

## 4. Error handling

Errors are categorized by **who** can recover them: the role itself, the driver, or the human. For each, we specify the **detection point**, the **action**, and the **artifact trail**.

### 4.1 Parse & schema errors

| Error | Detected by | Action |
|-------|-------------|--------|
| `NEXT_EXPERIMENT.md` missing required frontmatter field or section | Executor step 1 (§2.1.2) | Executor emits `REVIEW_REQUIRED: malformed_plan`. No commit exists. Driver treats as synthetic `malformed` verdict (§3.2 step 3); increments round; re-invokes Planner for round N+1. |
| `NEXT_EXPERIMENT.md` shows `escalation: null` but `results.tsv` has N≥`plateau_trigger.consecutive_discards` consecutive non-keep rows | Reviewer (§2.1.3 step 1 + §8.3 item 5) | Verdict `malformed` (Planner failed to emit C2). Round increments; if next Planner also fails to convert, 2 consecutive malformed halts the loop (§4.6). |
| `REVIEW.md` append malformed (driver can't parse the last block to advance state) | Driver parsing | Halt loop; write driver error log; requires human fix. Rare; protects against silent corruption. |
| Contract missing required frontmatter field at G1/G2/G3 sign-off | Human gate pre-check (driver won't start the loop) | Human re-authors; no loop until fixed. |

### 4.2 Executor runtime errors (bounded repair)

Executor handles crashes per its own procedure: up to **2 attempts total** (initial + 1 repair). Repair is limited to **syntax / import / typo / undefined-name** classes — anything that looks structural goes straight to `RUN_FAILED`. The cap is a hard invariant from EVAL_PROTOCOL.

If both attempts fail:
1. Executor emits `RUN_FAILED: <commit> repair_cap_exceeded`.
2. Driver logs the row with `status=crash`, `description="repair_cap_exceeded: <last stderr one-liner>"`.
3. Driver calls `git reset --hard HEAD~1` (if a commit happened) or discards the working tree (if not).
4. Consecutive-discard counter increments → may trigger plateau check.

### 4.3 Anomaly detection (C1 escalation)

- `tools/anomaly.py` runs inside the Reviewer; if it fires, the Reviewer writes its block with `verdict: anomaly` AND a `## Escalation` subsection that includes the tool's `reason` and `proposed_diagnostic`.
- Driver sees `VERDICT: anomaly` and **pauses the loop** (does not roll back the commit — it's preserved for inspection).
- `log.py` appends a row with `status=anomaly`.
- Human decides next action via C1: approve fix / override-keep / inspect-and-instruct. Resume is manual.

This preserves the reflection §6 property: "Do NOT dismiss this model family from one anomalous result."

### 4.4 Plateau / family-switch (C2 escalation)

- When `consecutive_discards >= EVAL_PROTOCOL.plateau_trigger.consecutive_discards` (default 3), the **next Planner** MUST emit a plan with `escalation: "C2"` and fill §6.
- The driver, upon seeing `escalation: "C2"` in `NEXT_EXPERIMENT.md` (step 2 of §3.2), does NOT invoke the Executor. It surfaces the C2 block to the human and pauses.
- Human response options: approve the proposed family switch → loop resumes with that plan (escalation cleared); redirect → human writes a new plan to `NEXT_EXPERIMENT.md`; declare done → proceed to G4.

**Guardrail against Planner mis-compliance:** If the Planner fails to emit `escalation: "C2"` despite the trigger being active, the Reviewer catches it via its rejection rule §8.3 item 5 and issues verdict `malformed`. The driver then gives the Planner one more chance (round N+1). If that Planner also fails, two consecutive `malformed` verdicts halt the loop with a BUG status (§4.6) — this is the backstop.

### 4.5 Contract change (C3 escalation)

- Planner may emit `escalation: "C3"` in NEXT_EXPERIMENT.md with §6 filled in.
- Driver does NOT invoke Executor. Runs `tools/contract_diff` to produce a structured diff block and surfaces it to the human.
- Human response: approve diff → human applies diff manually, bumps contract `approved_at`, resumes loop; reject → Planner is re-invoked with the C3 rejection noted in REVIEW.md.

Contracts are **sticky**: there is no path for a role to mutate a contract file directly.

### 4.6 Driver-level errors

| Error | Action |
|-------|--------|
| `CAMPAIGN_STATE.json` missing or unparseable | Halt; require human fix. (The state is the campaign — no silent re-init.) |
| `git reset --hard HEAD~1` fails (dirty tree, missing HEAD) | Halt; surface to human. |
| 2 consecutive `malformed` verdicts | Halt with `BUG: role producing malformed artifacts — see REVIEW.md round N-1, N`. |
| `results.tsv` schema drift (header mismatch) | `results_query` returns exit 3; driver halts. Preserves M1 integrity. |
| Tool exit code 4 (internal compute error) from a mandatory tool | Reviewer records in REVIEW.md; verdict = `malformed` (not keep/discard). Driver rolls back. |

### 4.7 Known Phase 2 upgrade (cross-model reviewer)

The ARIS pattern (HITL research §2) calls for a **different model** as Reviewer. In MVP we rely on context isolation + fresh invocation for independence. Phase 2 upgrade path:

- Add `roles/reviewer.md §1.A Required model` field naming a different model; driver invokes that specific model. No change to artifact schemas.
- Optionally enable a cascade (code → experiment → claim review) analogous to ARIS's 6-layer audit. Deferred until a 2nd model is configured.

No MVP code dependency on this; but by structuring prompts with `§1 Identity` and `§2 Inputs`, the swap is a one-field change.

---

## 5. Testing

Three layers of tests, each with a specific failure mode they catch. **No role-level LLM unit tests in MVP** — roles are exercised via integration tests that use small deterministic inputs.

### 5.1 Unit tests — `tests/tools/` (pytest)

Each tool in `runner/tools/` gets **three** unit tests:

1. **Happy path** with a fixture input; assert output shape, keys, and a known expected value.
2. **Bad input** (missing file, wrong dtype); assert the documented exit code + clear error message.
3. **Determinism** — call twice with the same inputs; outputs are byte-identical (use `random_state` in the fixture).

Specific high-value tests:

| Tool | High-value test case |
|------|----------------------|
| `leakage_audit` | A fixture with a column perfectly correlated with target — must flag. |
| `anomaly` | `best=0.85, latest=0.40` → fires. `best=0.85, latest=0.86` → does not. |
| `bootstrap_ci` | CI is strictly contained in [0, 1] for PR-AUC on stratified fixture. |
| `cv_runner` | On an obviously-imbalanced fixture, `stratified_kfold` folds all have ≥1 positive. |
| `paired_comparison` | Fixture where a > b in all folds → p < 0.05 and direction="a>b". |
| `results_query` | `filter_expr="status == 'keep'"` on a fixture tsv returns only keep rows. |
| `contract_diff` | A real PROBLEM_CONTRACT edit produces a diff with the changed fields only. |

### 5.2 Schema validation tests — `tests/schemas/`

Every artifact schema (PROBLEM / DATA / EVAL / NEXT_EXPERIMENT / REVIEW / DEAD_ENDS / NOTEBOOK / CAMPAIGN_STATE / PRIORS / FINAL_REPORT) has a validator implemented as a **pure function** in `runner/tools/schema.py` (small, local; not on the MVP tool list because it's internal infra).

Tests:
- Golden good fixtures for each artifact pass.
- Fixtures with each required field missing fail with a clear message naming that field.
- YAML that is valid but has wrong types (e.g. `round: "seven"` instead of int) fails.

This is the mechanism that makes "Reviewer must reject" enforceable without human-written prose checking.

### 5.3 Integration tests — `tests/integration/` (slow, gated)

Two end-to-end tests, both using a **tiny fixture dataset** (500 rows of a toy binary classification) so they run in <30 s. Both test the *driver*, not the LLM — the role agents are replaced with **deterministic stub scripts** that write fixed artifacts.

1. **Happy path loop** (`test_happy_loop.py`):
   - G3 is pre-signed in fixtures.
   - Stub Planner writes a fixed NEXT_EXPERIMENT.md per round (3 rounds).
   - Stub Executor edits a pre-scripted train.py and commits.
   - Real Reviewer stub runs real anomaly + bootstrap_ci tools.
   - Expected: 3 rows in results.tsv, `CAMPAIGN_STATE.json` at round=3, no crashes.

2. **Escalation path** (`test_c1_anomaly.py`):
   - Stub Executor produces a metric that trips `tools/anomaly`.
   - Expected: Reviewer verdict=anomaly, driver pauses loop, `results.tsv` has status=anomaly row, commit NOT rolled back.

No MVP coverage for C2/C3 end-to-end (they exercise the same driver halt path as C1); covered by unit tests on `contract_diff` and by integration-by-inspection during the first campaign.

### 5.4 Safety tests — `tests/safety/`

Cheap assertions that encode the hard invariants:

1. `test_no_role_writes_contract.py` — run each role's stub against a fixture workspace; assert `contracts/*.md` unchanged.
2. `test_executor_scope.py` — Executor stub with a plan that says "modify prepare.py" → stub must emit `REVIEW_REQUIRED: write_scope_violation`; no file mutation occurs.
3. `test_repair_cap.py` — Executor stub simulating repeated syntax errors → after 2 attempts, emits `RUN_FAILED: repair_cap_exceeded`.
4. `test_commit_per_experiment.py` — happy-path integration: count `git log --oneline` commits; must equal successful + crashed experiments (no silent squash).

### 5.5 What is NOT tested in MVP (and why)

- **LLM role outputs semantically.** The harness tests whether the *scaffolding* works (parsing, driver transitions, invariants). Whether the Planner actually produces good plans is what the campaign itself tests — and the human gates are the external oracle.
- **Cross-model reviewer agreement.** Single-model MVP; covered by the Phase 2 upgrade path in §4.7.
- **Long-running stability (100 rounds).** The happy-path 3-round test + the invariants covers the per-round correctness; the first real campaign is the stability test.

---

## 6. Migration from current `auto_train`

This is the concrete path from today's codebase to the MVP. Full removal; no compatibility stub (handoff §`abes_engine.py`).

### 6.1 Deletions

| Path | Reason |
|------|--------|
| `abes_engine.py` | Replaced; §`Relationship to current auto_train` in handoff. |
| `abes_state.json` | Replaced by `runner/state/CAMPAIGN_STATE.json` + `runner/state/results.tsv` + `runner/state/DEAD_ENDS.md` (the three fields that mattered). |
| `program.md` (contents) | Replaced by `runner/RUNNER.md`. File stub kept temporarily (redirect line) during the first campaign; removed at end. |
| `CLAUDE.md`, `AGENTS.md` (repo root) | Replaced by `runner/AGENTS.md` + `runner/RUNNER.md`. Root files become short stubs pointing at the runner. |

### 6.2 Additions

| Path | Source |
|------|--------|
| `runner/…` | New tree per §1. |
| `log.py` | Repo root; ~30 LOC; owns `results.tsv` append + `CAMPAIGN_STATE.json` update. |
| `tests/` | New; per §5. |

### 6.3 Preserved (unchanged)

| Path | Reason |
|------|--------|
| `prepare.py` | Fixed evaluation contract — read-only. |
| `data/creditcard.csv` | Read-only dataset. |
| `train.py` | Lives at repo root; Executor continues to own. |
| `requirements.txt` | Unchanged library set (reflection §Available libraries). |

### 6.4 Preserved (concept, new location)

| Concept | Old | New |
|---------|-----|-----|
| Anomaly floor 0.75 | `ANOMALY_FLOOR` in `abes_engine.py` | `EVAL_PROTOCOL.anomaly.floor` |
| Dead-ends list | `DEAD_ENDS_DEFAULT` | Seeded into `runner/state/DEAD_ENDS.md` at campaign init |
| Dead-ends seed rows (from apr01) | `state.warm_start.known_bad_features` etc. | `runner/contracts/PRIORS.md` §Known bad |
| Budget tracking | `state.budget`, `state.experiment_count` | `CAMPAIGN_STATE.budget_total`, `budget_used` |
| Per-experiment commit discipline | `program.md` §Experiment loop step 4 | Executor §3 step 4 (hard invariant 4) |

### 6.5 Migration order (implementation sequence — for the plan, not the spec)

Deliberately omitted here. `writing-plans` will sequence migration safely: scaffold runner/ alongside, implement tools, implement driver, migrate state, then delete abes_engine. The spec only specifies the end state.

---

## 7. Scope and what this spec is NOT

**In scope:**
- Full design of the MVP runner per handoff v2.
- Interface contracts for roles, tools, artifacts.
- Data flow, error handling, test strategy.

**Out of scope (intentional, for future specs):**
- Phase 2 cross-model reviewer (noted in §4.7).
- UI for gates (CLI-only MVP; HITL research §8 out-of-scope list).
- Multi-process or distributed execution.
- Additional problem types' first campaigns (spec is dataset-agnostic; credit-card is campaign 0).
- Specific schedule / ordering of the `writing-plans` steps (the plan owns that).
- Any change to `prepare.py` or evaluation function (remains per reflection §1 workspace rule).

---

## 8. Appendices

### 8.1 Summary of decisions made in this spec (not in handoff v2)

These resolve open items from handoff v2 §"Open items intentionally left for Section 2+":

1. Artifact format = YAML frontmatter + fixed numbered H2 markdown sections. (§2.3)
2. `train.py` path = repo root, unchanged. (§0 decision 2)
3. `experiment_helpers/<exp_id>/` = first 12 chars of commit hash, importable post-commit. (§0 decision 3)
4. CLI shape = each tool is its own `python3 runner/tools/<name>.py` with both function + __main__. (§0 decision 4)
5. `run_card.md` = on-demand via `tools/explain_run.py`. (§0 decision 5)
6. Driver = thin shell script `runner/run_round.sh` that orchestrates the linear round; stateless between rounds. (§3.2)
7. Schema-validator tool `runner/tools/schema.py` is internal infra (not on the MVP public tool list) but tested. (§5.2)
8. Test strategy = unit tests on tools, schema tests on artifacts, 2 integration tests with stub roles, safety tests on invariants. (§5)

### 8.2 Allowed `action_type` values (current default)

`A_model, A_feature, A_hp, A_imbalance, A_ensemble, A_diagnose, A_validate, A_restart`.
Authoritative list is `EVAL_PROTOCOL.action_types` for each campaign — the above is the default seed the Planner may propose during G3. (Preserved from legacy abes_engine; reflection §3 criticizes their use as bandit arms, not as human-readable labels.)

### 8.3 Reviewer rejection list (consolidated)

The Reviewer rejects with verdict `malformed` when ANY of these hold:

1. NEXT_EXPERIMENT.md missing a required frontmatter field or numbered section (§2.3.4).
2. `action_type` not in `EVAL_PROTOCOL.action_types`.
3. `touches_helpers: true` but `helpers_declared` is empty.
4. `escalation != null` but §6 is missing the corresponding C1/C2/C3 subsection.
5. ≥3 consecutive discards in `results.tsv` and `escalation != "C2"`.
6. Executor modified a read-only path (detected by inspecting the commit diff).
7. `train.py` diff does not implement §3 "Plan" of the corresponding NEXT_EXPERIMENT.md.
8. A mandatory tool from `EVAL_PROTOCOL.mandatory_tools` did not run for this round.

### 8.4 Glossary

| Term | Definition |
|------|-----------|
| **Campaign** | One problem, one approved contract set, one `runner/state/` directory, G1→G4. |
| **Round** | One plan/execute/review cycle inside a campaign; monotonic; increments every Reviewer verdict. |
| **Experiment** | Synonym for round in MVP (1:1). Phase 2 may decouple if multi-plan rounds are added. |
| **Verdict** | Reviewer's decision: `keep | discard | anomaly | crash | malformed`. |
| **Context isolation** | Fresh LLM invocation with ONLY the role's `§2 Inputs` files; no prior role's chat. |
| **Sticky contract** | A contract whose only mutation path is a C3-approved human edit. |

---

*End of Autonomous ML Runner Design Spec.*
