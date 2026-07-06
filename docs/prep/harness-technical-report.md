# auto_train Harness — Technical Report for Agentic-Engineering QA

**Audience:** Senior agentic-engineering interviewer at a generic frontier or applied-ML/AutoML startup context.
**Purpose:** Ground the candidate's mental model of the `auto_train` harness — components, lineage, rationale, alternatives considered, tradeoffs — before a deep-dive Q&A.
**Companion doc:** `interview-question-bank.md` in this directory.

---

## 0. TL;DR

`auto_train` is a self-improving ML "campaign" harness. A **campaign** is a fixed problem (dataset + evaluation protocol + budget of ~20 experiments) that four LLM-driven **roles** — Planner, Executor, Reviewer, Historian — iterate on, one experiment per round, one git commit per round. The harness is built around three ideas:

1. **Disk-as-truth.** Every role is a fresh LLM invocation with zero chat memory of prior roles. All inter-role communication passes through versioned files on disk (`state/`). This eliminates a whole class of "context rot" and hallucinated-continuation failures common in agent frameworks that share a scratchpad.
2. **Structural gates over persuasion.** The driver (a Python state machine, `runner_driver.py`) enforces invariants mechanically — commit scope, tool-receipt verification, artifact-mtime freshness, noise-floor override — so the Reviewer cannot flip a `discard` to `keep` with prose. The gates are anti-sycophancy scaffolding.
3. **Contracts are sticky.** The problem definition (`PROBLEM_CONTRACT.md`), data schema (`DATA_CONTRACT.md`), and evaluation protocol (`EVAL_PROTOCOL.md`) live under `campaigns/<name>/contracts/`. They are read-only during experiments; changing them requires a `C3` escalation with a structured field diff and a human `approved_at` stamp.

Design lineage: influenced by AlphaEvolve / MLEvolve / RE-Bench framing, but explicitly rejects the "one long agent conversation" pattern in favor of a small, testable Python orchestrator that treats the LLM as a stateless function per role.

---

## 1. Hard Invariants (`CLAUDE.md`, `AGENTS.md`, `runner/RUNNER.md`)

1. Only `train.py` (inside the campaign dir) is modified during experiments.
2. `prepare.py`, `data/`, and `contracts/` are read-only during experiments.
3. One git commit per experiment (rollback = `git reset --hard HEAD~1` on the campaign branch).
4. Primary metric + budgets live in each campaign's `contracts/EVAL_PROTOCOL.md`.
5. Contracts are sticky; change via C3 process + `tools/contract_diff` + human approval.

These are not aspirational — items 1–3 are mechanically enforced by the driver's write-scope check and by the rollback branch discipline. Item 5 is enforced by the driver refusing `init_campaign()` on any contract missing `approved_at`.

---

## 2. System-Level Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  Outer wrapper: run_campaign.sh                                    │
│  - while budget_used < budget_total AND consecutive_discards < 6:  │
│    - launch `claude -p ...` (Claude Code CLI, --resume when able)  │
│    - reads CAMPAIGN_STATE.json between iterations                  │
└──────────────────────────────┬────────────────────────────────────┘
                               │ per-round, in-session
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  Orchestrator prompt (runner/roles/orchestrator.md)                │
│  Runs INSIDE the Claude Code session. State machine:               │
│                                                                    │
│    stuck-check → PLANNER → plan-check                              │
│      → EXECUTOR → execute-finalize                                 │
│      → REVIEWER → review-finalize                                  │
│      → [HISTORIAN if pending] → historian-finalize                 │
│      → repeat                                                      │
└──────────────────────────────┬────────────────────────────────────┘
                               │ every stage boundary
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  Driver: runner_driver.py (STATELESS Python)                       │
│  Invoked via: `bash runner/run_round.sh <stage> [--key value ...]` │
│  Reads / writes disk. Never holds in-memory state across calls.    │
│  Emits driver_events.jsonl. Enforces F1–F5 gates.                  │
└───────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  On disk: campaigns/<name>/{contracts/, state/, data/, train.py}   │
└───────────────────────────────────────────────────────────────────┘
```

Key structural point: the LLM is invoked at two levels — as the **orchestrator** (a long-running session that manages the state machine) and as **role sub-invocations** for Planner/Executor/Reviewer/Historian. The driver never invokes the LLM; it only reads what the LLM wrote, validates, and gates. The driver is a Python program you could unit test.

---

## 3. Roles

Role prompts live under `runner/roles/`. Each is a markdown file loaded verbatim into a fresh LLM context. Roles do not talk to each other — they read and write files.

### 3.1 Planner (`runner/roles/planner.md`)

- **Reads:** all three contracts, `STRATEGY_GUIDE.md`, `PRIORS.md`, `results.tsv`, `DEAD_ENDS.md`, `UNEXPLORED_TECHNIQUES.md`, `NOTEBOOK.md`, `REVIEW.md`, `CAMPAIGN_STATE.json`, `ASSUMPTION_REGISTER.md`, `PATTERN_BOOK.md`, `STRATEGY_MEMO.md`, `TOKEN_SUMMARY.txt`, `EXPERIMENT_TREE.json`.
- **Writes:** `state/NEXT_EXPERIMENT.md` only.
- **Selects action** from a whitelisted set (`A_model | A_feature | A_hp | A_imbalance | A_ensemble | A_validate | A_restart`) using UCB1 over `EXPERIMENT_TREE.json` plus explicit dead-end collision checks.
- **Mandatory output artifacts:** YAML frontmatter (schema-validated by `plan_check`), a rationalization table (candidate | action | UCB1 | expected Δ | dead-end? | assumption risk | rationale), a code block for `train.py`, and an escalation field (`null | C1 | C2 | C3`).

### 3.2 Executor (`runner/roles/executor.md`)

- **Reads:** `AGENTS.md`, contracts, `NEXT_EXPERIMENT.md`, current `train.py`, `CAMPAIGN_STATE.json`.
- **Writes:** modified `train.py`, optional helpers under `runner/experiment_helpers/<exp_id>/`, one git commit, `run.log`.
- **Sentinel:** must emit `RUN_COMPLETE: <sha>` or `RUN_FAILED: <sha> <reason>` to stdout.
- **Repair cap:** 2 attempts per experiment. After 2 failed attempts, the round is declared `crash` and the orchestrator moves on.
- **Scope discipline:** identity spec says "never touch prepare.py / contracts/ / roles/ / tools/"; mechanical enforcement is `_path_in_write_scope()` in `execute_finalize()`. Any violation forces `synthetic_verdict: "malformed"` regardless of what the Executor wrote.

### 3.3 Reviewer (`runner/roles/reviewer.md`)

Two-phase, ordering-mandated:

- **Phase 1 (blind):** reads only `AGENTS.md`, `EVAL_PROTOCOL.md`, `train.py`, `run.log`, mandatory tool outputs, `results.tsv`, `ASSUMPTION_REGISTER.md`. Writes an independent assessment and a **preliminary verdict**. Phase 1's verdict for `keep`/`discard` is binding — Phase 2 cannot flip it.
- **Phase 2:** reads `NEXT_EXPERIMENT.md` to compare to the plan and add mechanistic context.
- **Writes:** appended `## Round N` block in `REVIEW.md` and `CAMPAIGN_JOURNAL.md`; optional `DEAD_ENDS.md` / `NOTEBOOK.md` updates; mandatory `ASSUMPTION_REGISTER.md` append on `keep`.
- **Anti-sycophancy scaffolding:** rationalization table required; forbidden phrases listed explicitly ("shows promise", "encouraging direction", "marginal gain" followed by keep).

### 3.4 Historian (`runner/roles/historian.md`)

- **Trigger:** `historian_trigger_pending: true` set by `review_finalize` when either `rounds_since_last_historian >= historian_interval` (default 10) OR `consecutive_discards >= plateau_trigger` (default 3).
- **Reads:** everything the Planner reads, plus deeper aggregates.
- **Writes:** rewrites `STRATEGY_MEMO.md` (four required sections), appends to `PATTERN_BOOK.md`, audits `ASSUMPTION_REGISTER.md` (updates `last_audited`, never creates entries — that's the Reviewer's job), extends `UNEXPLORED_TECHNIQUES.md`.
- **Mandated bottleneck category:** must pick exactly one of `model_quality | optimizer_quality | data_quality | eval_quality | feature_representation`. Forces a hypothesis about *why* the campaign is stuck rather than diffuse observation.
- **Enforced by F1** (`_verify_strategy_memo`): all four required sections present, each ≥80 chars of non-placeholder content, `historian_round` matches `state.round`, mtime ≥ `round_started_at`.

**Why 4 roles, not 1 or 2 or 10?** The four correspond to distinct epistemic tasks that benefit from being blind to one another's output: hypothesis generation (Planner), controlled implementation (Executor), independent verification (Reviewer), and pattern-level synthesis (Historian). Fewer roles collapse verification into implementation and re-introduce sycophancy. More roles fragment context without adding independent perspectives; we tried a "Critic" role between Reviewer and Historian in an early draft and dropped it — the Reviewer's Phase-1 blind pass and the Historian's cross-round audit already covered its purpose.

---

## 4. Driver (`runner_driver.py`) and Stages

The driver is invoked as a subprocess per stage via `bash runner/run_round.sh <stage>`. Every stage reads state from disk, validates, mutates, writes, and returns a JSON result. Stages:

| Stage | Function | Called by |
|---|---|---|
| `init` | `init_campaign()` | Bootstrap only |
| `stuck-check` | `detect_stuck()` in `orchestrator.py` | Before Planner |
| `plan-check` | `plan_check()` | After Planner |
| `execute-finalize` | `execute_finalize()` | After Executor |
| `review-finalize` | `review_finalize()` | After Reviewer |
| `historian` | `historian_run()` | Pre-Historian |
| `historian-finalize` | `historian_finalize()` | After Historian |
| `campaign-status` | `get_campaign_status()` | Every round start |
| `resume-phase` | `determine_resume_phase()` | Crash recovery |
| `substantive-check` | `check_substantive()` | Post-commit |
| `reproduce-check` | `reproduce_check()` | Optional post-run |
| `tool-run` | `execute()` in `tools/run.py` | Every mandatory tool call |
| `resolve-c2` | `resolve_c2()` | Human plateau override |

**Design rationale for stateless driver:** every stage can be re-run without side effects on in-memory state. Crash recovery is trivial: the wrapper relaunches Claude, the orchestrator re-reads `CAMPAIGN_STATE.json`, calls `resume-phase`, and continues. There's no scheduler state, no queue to reconcile.

### 4.1 Gates F1–F5

Named in the code and in `docs/reflections/2026-06-19-harness-self-audit.md`:

- **F1 (`_verify_strategy_memo`):** Historian output structure check. Failure → `historian_skipped`, keep `historian_trigger_pending: true` for retry.
- **F2 (`_verify_reviewer_artifacts`):** `CAMPAIGN_JOURNAL.md`, `REVIEW.md`, and (on keep) `ASSUMPTION_REGISTER.md` must have fresh `## Round N` entries with mtime ≥ `round_started_at`. Failure → verdict downgraded to `malformed`.
- **F3 (mandatory tool receipts):** the `tool-run` wrapper emits `event: "tool_run"` records to `driver_events.jsonl` with `exit_code`, `args_hash` (SHA-256[:16] of canonical JSON args), `start_ts`, `end_ts`. `review_finalize` cross-checks: every mandatory tool the Reviewer claims to have run must have a receipt with `exit_code == 0` and `start_ts >= round_started_at`. Failure → `tools_ran_unverified` event, verdict → `malformed`.
- **F4 (skeleton bootstrap):** `init_campaign()` seeds every state file with valid frontmatter and headings so downstream mtime checks never trip on missing files.
- **F5 (tree rebuild):** if `EXPERIMENT_TREE.json` is missing or empty at init, rebuild from `results.tsv`. Emits `tree_rebuilt` with `degraded: true` if the rebuild was defensive.

### 4.2 Verdict cascade in `review_finalize()`

Applied in order — each layer can override the previous:

1. Reviewer's own verdict (`keep | discard | anomaly | crash`).
2. **Mandatory tool gate (F3):** any missing receipt → `malformed`.
3. **Noise-floor gate (GAP 7):** if `keep` and `|Δ| < noise_floor` → `discard` (with `noise_floor_override` recorded).
4. **Reviewer-artifact gate (F2):** missing artifacts → `malformed`.
5. **Halt condition:** two consecutive `malformed` → `halt_loop: true`.
6. **Budget:** `round >= budget_total` → `halt_loop: true`.

The noise-floor gate is the load-bearing anti-sycophancy mechanism. It runs in the driver, in Python, with no LLM involvement — so a Reviewer that talks itself into calling a +0.001 improvement "marginal" cannot get past it.

---

## 5. Contracts

Three per campaign under `campaigns/<name>/contracts/`. All use YAML frontmatter + markdown body, parsed by `runner.tools._common.parse_frontmatter`.

- **`PROBLEM_CONTRACT.md`** — task type, unit of observation, target definition, success criteria, constraints, non-goals, `approved_at`, `approved_by`.
- **`DATA_CONTRACT.md`** — data sources, temporal window, full column schema with `dtype` and `available_at_prediction` per column, leakage audit (`performed_at` must be non-null before G2 sign-off), splits.
- **`EVAL_PROTOCOL.md`** — primary metric (`name`, `direction`, `noise_floor`), CV scheme, bootstrap_ci config, `mandatory_tools` list, `action_types` whitelist, `budgets.{time_budget_s, max_experiments, max_repair_attempts}` (schema validator hard-checks `max_repair_attempts == 2`), `plateau_trigger.consecutive_discards`, anomaly gate config, `historian_interval`.

**C3 (Contract Change Protocol):**
1. Planner sets `escalation: C3` in `NEXT_EXPERIMENT.md` frontmatter, includes proposed diff in §6.
2. `plan_check` returns `pause_c3`; orchestrator halts the loop.
3. Human (or Planner) runs `python -m runner.tools.contract_diff --contract-name EVAL --proposed-path <new>`; the tool classifies risk (`high` if any `_HIGH_RISK_FIELDS` changed, `medium` if >5 fields, else `low`).
4. Human reviews, sets `approved_at`, replaces file.
5. Campaign resumes.

---

## 6. Tools (`runner/tools/`)

All invoked through `tools/run.execute()` (the receipt-emitting wrapper). Direct invocation of `python -m runner.tools.<X>` also works but does not emit a receipt, so `review_finalize` will fail F3.

| Tool | Purpose | Output shape |
|---|---|---|
| `runner.tools.anomaly` | Two-condition anomaly: primary >0.99 (leakage suspicion) OR primary < max(floor, relative × best_prior) (degradation) | `{fired, reason, proposed_diagnostic}` |
| `runner.tools.bootstrap_ci` | Bootstrap 1000× on `y_true`/`y_prob` for a chosen metric; point + 95% CI + SE, RNG=42 | `{metric, ci_lo, ci_hi, se, n_boot}` |
| `runner.tools.reproduce_check` | Recompute metrics from `y_val_true.npy` / `y_val_prob.npy`; cross-check against `run.log`; catches log fabrication and silent metric drift | `{artifacts_valid, recomputed, reported, mismatches, passed}` |
| `runner.tools.contract_diff` | Field-level structured diff on YAML frontmatter of a contract; risk-classifies | `{contract, changes, risk_level}` |
| `orchestrator.detect_stuck` | Detects action-type repetition, A-B-A-B alternation, hypothesis repetition, metric stagnation | `{warnings: [...]}` |
| `tools.substantive_diff.check_substantive` | Rejects no-op commits (whitespace-only, comment-only) | verdict shim |

**Why a receipt system rather than trusting the Reviewer's "I ran the tool"?** Closes P0-3 from the June 2026 self-audit: Reviewers were claiming they ran mandatory tools without doing so. The receipt is a system-of-record cross-check that the Reviewer cannot fake without also forging a subprocess exit-code trace and matching `args_hash`.

---

## 7. State Artifacts (`campaigns/<name>/state/`)

| File | Writer(s) | Reader(s) | Notes |
|---|---|---|---|
| `CAMPAIGN_STATE.json` | driver | every role & stage | central counter store, `schema_version: 2` |
| `NEXT_EXPERIMENT.md` | Planner | Executor, Reviewer (Phase 2) | overwritten each round |
| `REVIEW.md` | Reviewer (append), driver (frontmatter patch) | Planner | `last_verdict` regex-patched by driver |
| `CAMPAIGN_JOURNAL.md` | Reviewer (append) | Historian, resume | F2 checks `## Round N` heading |
| `ASSUMPTION_REGISTER.md` | Reviewer (new entries on keep), Historian (audit only) | all | `### A-N-<seq>` format |
| `DEAD_ENDS.md` | Reviewer | Planner, `plan_check` | `count` frontmatter must match bullet count |
| `PATTERN_BOOK.md` | Historian | Planner | `### P-<seq>` format |
| `NOTEBOOK.md` | Reviewer | Planner | free-form surprising observations |
| `STRATEGY_MEMO.md` | Historian (overwrite) | Planner | 4 required sections; F1-enforced |
| `UNEXPLORED_TECHNIQUES.md` | Historian | Planner | mandatory read when `consecutive_discards >= 2` |
| `results.tsv` | `log.append_result()` | Planner, Historian, `detect_stuck`, `ExperimentTree` | one row per experiment |
| `driver_events.jsonl` | driver, `tools/run.execute` | `review_finalize` (F3), post-mortem | append-only, non-critical |
| `EXPERIMENT_TREE.json` | init + `review_finalize` | Planner (UCB1) | rebuildable from `results.tsv` (F5) |
| `TOKEN_SUMMARY.txt` | `review_finalize` | Planner | informational only |

**Drift prevention:** F2 mtime check + explicit schema validators (`tools/schema.py`) + `_verify_reviewer_artifacts` regex checks on `## Round N` headings. The system is designed so that a role skipping an artifact write is caught within one round.

---

## 8. Event Bus (`driver_events.jsonl`)

Append-only NDJSON, one record per event. Minimum keys: `ts` (ISO-Z UTC), `event`. Emitted by `_emit_event()` (driver) and `tools/run.execute()`. Non-critical writes never raise — silent skip on I/O errors, because the harness must not crash the campaign because of a logging issue.

Events used by control logic (not just observability):
- `tool_run` — the F3 receipt.
- `plan_check`, `review_finalize`, `historian_finalize` — stage completion.
- `tools_ran_unverified`, `reviewer_artifacts_missing`, `reviewer_artifacts_all_missing` — gate violations.
- `historian_skipped`, `tree_rebuilt` — degraded-mode signals.

We deliberately did not put this in a message bus (Kafka, Redis Streams). File-appended JSONL is diffable, greppable, git-friendly for post-mortems, and needs zero infrastructure. The tradeoff is no live subscription — but nothing in the harness needs live subscription; the driver reads the file synchronously when it needs to.

---

## 9. Round Lifecycle (Full Trace)

Round N of a campaign:

1. **Wrapper** (`run_campaign.sh`) launches Claude Code CLI with `--resume <session_id>` (if available).
2. **Orchestrator prompt** (loaded via `runner/roles/orchestrator.md`) instructs the LLM to: check `CAMPAIGN_STATE.json`, call `stuck-check`.
3. **Stuck-check** (`orchestrator.detect_stuck`) reads `results.tsv`, emits warnings if applicable.
4. **Planner** subrole invoked. Reads all its inputs (§3.1). Writes `NEXT_EXPERIMENT.md`.
5. **`plan-check`** validates YAML schema, action_type against whitelist, dead-end collision. Stamps `round_started_at` on `CAMPAIGN_STATE.json`. Returns `ok | pause_c2 | pause_c3 | malformed`.
6. **Executor** subrole invoked. Edits `train.py`, stages + commits, runs `python3 train.py > run.log 2>&1`, emits sentinel.
7. **`execute-finalize`** checks commit-diff files against write-scope, checks sentinel, returns `keep | crash | malformed`.
8. **Mandatory tools** invoked via `tool-run` wrapper — each emits a `tool_run` event with `exit_code`, `args_hash`, timestamps.
9. **Reviewer** subrole invoked. Phase 1 blind, Phase 2 with plan. Appends to `REVIEW.md`, `CAMPAIGN_JOURNAL.md`, `ASSUMPTION_REGISTER.md` / `DEAD_ENDS.md` / `NOTEBOOK.md` as applicable.
10. **`review-finalize`** applies the verdict cascade (§4.2). Emits `review_finalize` event. If `should_rollback: true`, orchestrator runs `git reset --hard HEAD~1`. Increments counters. Sets `historian_trigger_pending` if applicable.
11. **Historian** (conditional). Rewrites `STRATEGY_MEMO.md`, appends to `PATTERN_BOOK.md`, extends `UNEXPLORED_TECHNIQUES.md`, audits `ASSUMPTION_REGISTER.md`.
12. **`historian-finalize`** F1-verifies, resets counters.
13. Loop or exit (budget / double-plateau).

The critical invariant: **every stage boundary is a disk-persisted commit point.** If Claude crashes between any two stages, the next relaunch calls `resume-phase`, which walks four disk-artifact heuristics to determine which stage to resume from, and continues.

---

## 10. Campaign Lineage — otto-r1 → otto-r2 as a Case Study

### 10.1 Seeding

Not a live API call. Otto-r1 concluded with a `FINAL_REPORT.md` (commit `24a0fdb`) whose §5 "Recommended priors update" prescribes exact `PRIORS.md` text for any future Otto campaign. A human (or the orchestrator during setup) creates otto-r2 via commit `5e12430` — `setup(otto-r2): clone otto-r1 contracts + data, reset state and train.py`. What propagates:

- **Contracts:** copied verbatim (problem, data schema, eval protocol unchanged).
- **`PRIORS.md`:** populated from r1 FINAL_REPORT §5 — known-good baselines, known dead-ends, known ceilings.
- **`UNEXPLORED_TECHNIQUES.md`:** seeded from a prior internal `ip-commercial-new-te` campaign's frontier, then enriched with r1 FINAL_REPORT §6 open questions (KNN-distance, t-SNE, target encoding, pairwise interactions, stacking, RF, MLP).
- **State artifacts** (`PATTERN_BOOK`, `ASSUMPTION_REGISTER`, `DEAD_ENDS`, `results.tsv`): reset to empty skeletons.

This is deliberate. The r2 campaign treats itself as authoritative for its own results (it observed a different LightGBM version giving 0.507 vs r1's 0.474 — the Reviewer flagged this in R1 review) but inherits r1's *conclusions about what not to try* and *what's worth trying*.

### 10.2 Failure Taxonomy Across otto-r2 Rounds 2–14

Eight distinct mechanistic categories, each mapped to which layer of the harness caught it:

| Round | Category | Mechanism | Who caught | Artifact |
|---|---|---|---|---|
| R2 | Calibration-noise | KNN dist features degraded log_loss but roc_auc unchanged → redundant proximity signal | Reviewer diagnosed dissociation | `DEAD_ENDS #1` |
| R6 | Model-internal redundancy | Pairwise products vs CatBoost depth=10 (nested splits already capture) | Reviewer | `DEAD_ENDS #2`, `P-1` |
| R7 | Model-internal redundancy #2 | Target encoding vs CatBoost ordered boosting (which does implicit target stats) | Reviewer | `DEAD_ENDS #3` (scoped to CatBoost — critical for R14) |
| R8 | Plan-spec bug | Plan listed `bootstrap_type="Bayesian"` in champion HPs; actual champion used default MVS | Reviewer, via manual code audit of `CHAMPION_HP` dict vs commit `1335f4e` | `P-3`, `A-4-1` updated |
| R9 | Environmental + proxy-quality | LightGBM proxy=30 trees at load 95/32 → high-lr HPs "win" proxy but underfit final by 0.10 | Reviewer + Historian pattern | `P-4` seeded |
| R11 | Search-space failure | Log-uniform reg_lambda∈(0.0001, 10) allows near-zero L2 → catastrophic overfit at 1000 trees | Reviewer | `DEAD_ENDS #4`, `P-5` |
| R12 | Silent API break | `early_stopping_rounds` silently ignored by XGBoost 3.x constructor kwargs | Reviewer, via manual code + smoke test | `DEAD_ENDS #5` |
| R13 | Environmental only | Correct code (`callbacks=[EarlyStopping]`), 95/32 CPU load → per-trial 900s → timeout | Reviewer post-mortem | `P-4` updated |
| R14 | Partial-signal / HP-mismatch | XGBoost target encoding, top-10 (reduced from top-20 under load), 3/5 folds worse | Reviewer (Δ < noise_floor) | `P-6`, `DEAD_ENDS` note (scoped) |

Notable properties:
- **The harness caught every failure programmatically.** No human made a keep/discard decision. Humans intervened only to complete partial Reviewer artifact writes after `malformed` events.
- **`DEAD_ENDS` entries are scoped, not blanket.** DEAD_ENDS #3 says "target encoding is dead for CatBoost, potentially productive for XGBoost/LightGBM" — this scoping directly enabled R14 as a legitimate distinct experiment, not a dead-end repeat.
- **Rollback is git-only for `train.py`.** State artifacts (REVIEW.md, DEAD_ENDS.md, PATTERN_BOOK.md, counters) survive rollback by design, so the learning from a discard persists even though the code reverts.
- **Two consecutive `malformed` verdicts trip `halt_loop: true`.** In otto-r2 driver_events.jsonl this fired twice — around R10/R11 and again around R14/R15 — indicating structural role failures that required human unblock.

### 10.3 Pattern Register (Otto-r2, at R14)

The Historian codified six patterns:

- **P-1 (high):** CatBoost depth≥10 blocks FE augmentations that duplicate its internal mechanisms. Scope-updated to CatBoost-only after R10 XGBoost success.
- **P-2 (high):** 5-fold OOF fold_std is 0.007–0.012 across 10 rounds. The nominal `noise_floor=0.005` understates the real detection threshold (≈ 2× fold_std). Directly informs Planner conservatism.
- **P-3 (medium):** CatBoost `bootstrap_type="Bayesian"` costs ~0.015 vs default MVS at depth=10.
- **P-4 (medium):** Machine load >8/32 cores blocks multi-trial Optuna within 1800s. Prescribes `uptime` check before HPO experiments.
- **P-5 (medium):** XGBoost Optuna with unconstrained log-uniform reg_lambda near zero selects overfit HPs at proxy → constrain `reg_lambda >= 0.5`.
- **P-6 (low):** XGBoost target encoding increases fold-to-fold variance; likely needs HP co-optimization.

Pattern format is prescriptive not merely descriptive: every entry has an `Implication for Planner` field.

---

## 11. Alternatives Considered and Rejected

This is a summary of decisions the codebase and reflections in `docs/reflections/` document; expect interview probing on any of these.

| Design decision | Chosen | Alternative(s) considered | Why we picked it |
|---|---|---|---|
| Inter-role comms | Files on disk | Shared scratchpad / single-context agent | Disk-as-truth prevents context rot; enables blind Reviewer Phase 1; allows crash recovery via file inspection |
| Driver | Stateless Python invoked per stage | Long-running orchestrator with in-memory state | Every stage is unit-testable; crash recovery trivial; no scheduler state to reconcile |
| Role count | 4 (Planner/Executor/Reviewer/Historian) | 1 mega-agent; 2 (Actor/Critic); 5 (add Critic between R/H) | Fewer collapses verification into implementation → sycophancy. More fragments context without independent perspective. Critic was tried and dropped |
| LLM framework | Direct Claude Code CLI + prompts | LangGraph, DSPy, CrewAI, AutoGen | Framework overhead was net negative for our use case: prompts are markdown files, tools are Python modules, the driver is Python. LangGraph would have added a compilation step for a state machine we can express in a shell dispatch. DSPy's optimizer conflicts with our human-approved contract model. CrewAI's "crew" abstraction adds indirection without benefit at 4 roles |
| State schema | Markdown + YAML frontmatter | JSON, TOML, SQLite, Postgres | Diffable in git; human-readable; renders in every tool. Schema validators in `tools/schema.py` give us the safety of typed storage without giving up readability. SQLite considered for `results.tsv` — rejected because grepping and `sort` work fine at n=20 rows |
| Event bus | Append-only JSONL | Kafka / Redis Streams / SQLite events table | Zero infra; git-friendly; sync-readable. No live subscriber needs anyway |
| Tool receipt system | SHA-256 args_hash + subprocess exit_code in JSONL | Trust the Reviewer's "I ran it" claim; sign receipts cryptographically | JSONL receipt closes documented P0-3 sycophancy bypass; crypto signing would be theatre — the driver is trusted |
| Metric verification | Recompute from `y_val_*.npy` artifacts, cross-check `run.log` | Trust stdout; require a database write | Catches silent metric fabrication or drift with zero infra |
| Contract change | C3 escalation + structured diff + human `approved_at` | Auto-approve if risk=low; version contracts and let Planner branch | AutoML systems that let the agent redefine success collapse; the contract IS the ground truth, mutating it invalidates all prior results |
| Rollback semantics | `git reset --hard HEAD~1` on campaign branch, state artifacts NOT rolled back | Full state rollback; branch-per-experiment | Learning from a discard round must persist (DEAD_ENDS, patterns). Branch-per-experiment considered — rejected because the linear branch preserves a legible experiment history matching `results.tsv` row order |
| Repair cap | 2 attempts hardcoded in EVAL_PROTOCOL schema | Configurable per action_type; unlimited retries | Empirically observed: attempts 3+ are almost always thrashing. Schema validator hard-checks `max_repair_attempts == 2` to prevent per-campaign creep |
| Stuck-check | Deterministic 4-pattern check on `results.tsv` action_type / hypothesis / metric | LLM-based "am I stuck?" self-reflection | Deterministic rules are auditable and can't be talked out of. LLM self-reflection reliably underreports stuck-ness (motivated reasoning) |
| UCB1 over strategy classes | Multi-armed bandit on `action_type` | Full-blown BayesOpt over HPs; hand-tuned exploration schedule | Right level of abstraction — the strategy class (A_model / A_feature / A_hp) has semantically distinct exploration value. HP-level BayesOpt was tried at otto-r1 and lost to a UCB1-driven action-type rotation |
| Wrapper resume | `claude --resume <session_id>` between iterations | Fresh session every iteration; no wrapper | Resume preserves cache warmth and mid-round context; fresh sessions per round would burn 500k+ tokens per campaign in cold-context re-reads |
| Machine-load handling | Post-hoc: encode learning as P-4 pattern, Planner consults `uptime` | Pre-flight resource scheduler, cgroups, quota system | We share a machine with other campaigns; the harness cannot control load. Pattern-based learning lets the Planner adapt without infrastructure changes. Eventually a pre-flight `uptime` gate in the driver would be a natural extension |
| Anomaly gate | Fixed thresholds in EVAL_PROTOCOL | Bayesian anomaly detector; LLM-based sanity check | Fixed threshold catches the obvious cases (>0.99 = leakage; < floor = probability inversion). LLM sanity check tried in early draft — reliably rationalized bad results as "novel signal" |

---

## 12. Positioning vs Industry Frameworks

**LangGraph / LangChain agents:** LangGraph would model our stages as graph nodes with typed edges. Comparable at surface level, but LangGraph's checkpointing is designed for a single long-running agent state, not for four blind roles that share nothing but files. Our disk-as-truth model would degenerate into a wrapper around LangGraph state and lose the property that each stage is a standalone `python -m runner_driver <stage>` call.

**DSPy:** DSPy optimizes prompts against a metric using an LLM-as-optimizer approach. Directly conflicts with our contract model — DSPy would want to adjust `EVAL_PROTOCOL.md` to make the metric easier to hit, which is precisely what our sticky-contract invariant forbids. DSPy's `Module` / `Signature` abstractions could layer in for the Reviewer's structured output, but so could a JSON schema + validator, and we don't need DSPy's compilation pipeline.

**CrewAI / AutoGen:** These frameworks emphasize conversational multi-agent coordination. Our four roles do not converse — they write to disk and never see each other's chat. CrewAI's "delegation" primitive is close to what our orchestrator does, but adds a message-passing indirection that would obscure the F1–F5 gate structure.

**AlphaEvolve / MLEvolve:** Closest philosophical relatives — evolve code via LLM-in-the-loop. We diverge in three key ways: (1) our Planner is not just a mutation operator, it is a first-class strategist with UCB1 and dead-end memory; (2) our Reviewer is structurally blind to the plan in Phase 1, giving independent verification that pure evolutionary approaches lack; (3) our contract system pins down the fitness function against tampering, preventing the "spec gaming" failure mode observed in some evolve-your-own-metric research.

**RE-Bench / METR agent evals:** Our four-role structure is designed for real ML campaigns (finite budget, real datasets, real cost), not for benchmark performance. RE-Bench-style evals could readily use `p0-fix-smoke` as a template — a fixed dataset, tight timeout, deliberately-inflated noise-floor to force at least one discard, verifying that F1–F5 all fire.

**AutoML frameworks (AutoGluon, TPOT, H2O, Auto-sklearn):** These are one-shot pipeline searchers with no agent in the loop. Comparable to a single Planner+Executor pass, but no Reviewer, no Historian, no learning across campaigns. Their fixed search spaces are what our Planner learns to prune via `DEAD_ENDS.md` and `PATTERN_BOOK.md`.

---

## 13. Known Limitations and Directions

Documented in `docs/reflections/` and referenced by `PATTERN_BOOK.md` P-4 among others:

- **No pre-flight resource gate in the driver.** Machine load is checked only post-hoc via P-4 pattern learning. A pre-flight `uptime` check in `plan_check` would surface infeasible plans before they burn 1800s.
- **`runner.tools.anomaly` is not direction-aware.** It assumes `direction: maximize`. Otto-r2 (minimize) has to disable both gates and rely on train.py-internal assertions. Documented in EVAL_PROTOCOL.md comment; fix is a two-line change.
- **`reproduce_check` is hardcoded to binary classification shape** (`y_prob: (N,)`). Multiclass otto campaigns get `artifacts_valid: false` on every round — a known false negative. Manual verification is done inline in REVIEW.md.
- **Cross-campaign learning is human-curated.** The r1→r2 seeding via FINAL_REPORT §5 is manual. A `runner/tools/seed_campaign.py` that reads FINAL_REPORT and populates the new campaign's PRIORS.md is a natural extension.
- **Historian trigger criteria are conservative.** Fires every 10 rounds or on plateau. A more sophisticated criterion could trigger on distributional shifts in per-fold variance, or on Assumption Register saturation.
- **No adversarial verification stage.** The Reviewer is one LLM. A second-opinion adversarial Reviewer (echoing the "N judges" pattern) would catch cases where a single Reviewer misses a subtle bug. Considered; not implemented because it doubles per-round LLM cost.
- **Contracts have no versioning.** A C3 change replaces the contract file; there's no history of prior contract versions on disk (only via git blame). A `contracts/history/` mirror would improve auditability.

---

## 14. Reading Guide for Deep Dive

If the interviewer asks "walk me through the code", start here in this order:
1. `runner/RUNNER.md` — high-level protocol.
2. `runner/roles/orchestrator.md` — the state machine narrative.
3. `runner/runner_driver.py` — the actual state machine, especially `review_finalize()`.
4. `runner/roles/reviewer.md` — the blind-phase-one, rationalization-table design.
5. `runner/tools/run.py` — the receipt-emitting wrapper (§F3 detail).
6. `campaigns/otto-r2/state/REVIEW.md` — real Reviewer outputs across 14 rounds.
7. `campaigns/otto-r2/state/PATTERN_BOOK.md` — real Historian pattern extraction.
8. `campaigns/p0-fix-smoke/` — the harness's own integration test.

Companion: `interview-question-bank.md`.
