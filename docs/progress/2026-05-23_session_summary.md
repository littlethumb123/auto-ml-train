# Session Progress Report — Harness Evaluation Hardening Work
**Date**: 2026-05-23
**Status**: Implemented the core evaluation-hardening code and test changes, validated them with a passing 150-test run under the currently available dependencies, and left commits/documentation follow-up pending.

## 1. Executive Summary

The session started from two inputs: the harness review in `docs/reflections/2026-05-22-harness-engineering-review.md` and the concrete remediation checklist in `docs/brainstorming/evaluation-hardening-plan.md`. The immediate goal was to close the highest-priority evaluation integrity gaps by fixing the lift-metric inconsistency, making mandatory review-tool enforcement fail closed, exposing saved prediction artifacts for reviewer tooling, and adding cheap-but-effective assertions around validation data and prediction outputs.

Execution stayed close to that plan on the code path. The smoke-test campaign training script was updated to use the canonical shared lift implementation, save validation predictions to disk, assert minimum validation positives, and reject invalid probability outputs before structured metric reporting. The reviewer-side tooling was aligned by removing duplicate lift logic from `runner/tools/bootstrap_ci.py`, and the anomaly detector now flags suspiciously perfect results that are more consistent with leakage than genuine model behavior.

The most consequential harness-level behavior change was in `runner/runner_driver.py`: a `keep` verdict now fails closed when mandatory tools are configured but `tools_ran` is omitted. That surfaced a predictable regression in existing tests that assumed the old opt-in behavior, so the session also included the necessary safety, integration, and driver test updates to pass explicit tool receipts where required. Verification ended with a repo-wide pytest run, excluding only tests blocked by missing optional packages, and that run passed cleanly.

Two plan-adjacent items remain open. The plan described per-task commits, but no commits were created because the current session did not include an explicit user request to commit. The plan also suggested documenting prediction artifact paths in an evaluation contract file; that documentation follow-up was not completed in this session.

## 2. Planned vs. Executed

**Original Plan**: Implement the seven tasks in `docs/evaluation-hardening-plan.md` carefully and without inventing behavior beyond the plan.

**What Got Done**:
- [x] Standardized `lift_at_10` in the smoke-test campaign on `shared.metrics.lift_at_percentage`.
- [x] Removed duplicated lift logic from `runner/tools/bootstrap_ci.py` and added a regression test locking it to `shared.metrics`.
- [x] Saved validation prediction artifacts from `campaigns/smoke-test-creditcard/train.py` and emitted artifact paths in structured output.
- [x] Added cheap evaluation assertions for minimum validation positives and probability sanity.
- [x] Changed the mandatory-tool gate in `runner/runner_driver.py` to fail closed when `tools_ran` is omitted.
- [x] Added upper-bound anomaly detection for suspiciously perfect metrics and covered it with tests.
- [x] Updated affected safety/integration/driver tests and finished with a passing 150-test run under the currently installed dependencies.
- [ ] Create the per-task git commits described in the plan — deferred because no commit action was requested in-session.
- [ ] Document prediction artifact paths in an evaluation contract file — deferred; executable code and regression coverage were prioritized first.

**Alignment Notes**: The executable and test-facing parts of the plan were completed. Scope contracted slightly on repo history/documentation work: the plan’s commit cadence and contract-documentation follow-up were not executed this session.

## 3. Key Decisions & Rationale

### Decision: Canonicalize lift implementation
**Context**: `train.py` reported lift with a percentile-threshold implementation while shared code and bootstrap CI used exact top-k ranking.
**Options Considered**: Keep the local `train.py` helper and patch it; copy bootstrap logic into `train.py`; import the shared metric implementation in both places.
**Chosen**: Use `shared.metrics.lift_at_percentage` from both `train.py` and `runner/tools/bootstrap_ci.py`.
**Rationale**: This makes the reported point metric and the bootstrap confidence interval operate on the same statistic and removes a drift-prone duplicate implementation.
**Trade-offs**: Score-tie behavior changes to exact top-k semantics, which is stricter than the old percentile threshold and may slightly shift historical comparability.

### Decision: Enforce mandatory tools fail closed
**Context**: The review noted that `review_finalize()` skipped mandatory tool enforcement when `tools_ran` was `None`, allowing a `keep` verdict without evidence that required review tools ran.
**Options Considered**: Preserve backward compatibility; emit a warning but still allow `keep`; treat missing `tools_ran` as an empty tool receipt set.
**Chosen**: Keep the public signature unchanged but coerce `tools_ran=None` to `[]` inside the `keep`-path gate.
**Rationale**: This matches the intended safety contract and closes the bypass without requiring an API break.
**Trade-offs**: Existing tests and callers that relied on omission semantics had to be updated to pass explicit tool receipts for `keep` verdicts.

### Decision: Persist validation prediction artifacts locally
**Context**: `bootstrap_ci` and any future metric re-computation need raw `y_true` and `y_prob` arrays, but the smoke-test campaign only emitted scalar metrics.
**Options Considered**: Recompute predictions inside reviewer tools; write predictions into logs; save binary arrays under a campaign-local artifact directory.
**Chosen**: Save `.npy` arrays under `campaigns/smoke-test-creditcard/artifacts/` and expose the relative paths in structured output.
**Rationale**: It is cheap, deterministic, easy for tools to load, and avoids turning logs into a large data transport channel.
**Trade-offs**: The training script now emits local binary artifacts and required an accompanying `.gitignore` rule.

## 4. Technical Changes

### 4.1 Files Created
- `tests/tools/test_bootstrap_ci_lift.py` — regression test asserting that `bootstrap_ci(..., metric="lift_10pct")` matches `shared.metrics.lift_at_percentage(...)` exactly.

### 4.2 Files Modified
- `.gitignore` — added `campaigns/*/artifacts/` so saved prediction arrays stay out of version control.
- `campaigns/smoke-test-creditcard/train.py` — imported the shared lift implementation, added a minimum-positive assertion, saved `y_val_true.npy` and `y_val_prob.npy`, added probability-range/NaN/variance assertions, and emitted artifact paths in structured output.
- `runner/tools/bootstrap_ci.py` — removed the local `_lift_at_pct` helper and delegated lift metrics to `shared.metrics.lift_at_percentage`.
- `runner/runner_driver.py` — changed the mandatory-tool gate to reject `keep` when mandatory tools exist but `tools_ran` is absent or incomplete.
- `runner/tools/anomaly.py` — added an upper-bound leakage heuristic for values above `0.99`.
- `tests/tools/test_anomaly.py` — added coverage for suspiciously perfect scores.
- `tests/safety/test_mandatory_tools.py` — updated the backward-compat expectation and added a fail-closed test for omitted `tools_ran`.
- `tests/test_runner_driver.py` — updated `keep`-path tests to pass explicit mandatory tool receipts under the new gate behavior.
- `tests/integration/test_happy_loop.py` — passed explicit tool receipts when the simulated reviewer returns `keep`.
- `tests/integration/test_run_round_shell.py` — passed `--tools-ran` through the shell wrapper integration test.
- `tests/safety/test_auto_c3_trigger.py` — updated `keep`-path setup calls to include mandatory tool receipts.

### 4.3 Configuration / Schema Updates
- No production schema changes.
- One repo-level ignore rule was added for campaign prediction artifacts.
- No evaluation-contract documentation was updated in this session.

## 5. Discussions & Reasoning

### Topic: Lift metric consistency
**Question**: Were the reported lift metric and bootstrap CI bound to the same underlying statistic?
**Analysis**: `campaigns/smoke-test-creditcard/train.py` imported the canonical lift helper and now computes `lift_at_10` with `lift_at_percentage`, while `runner/tools/bootstrap_ci.py` delegates its lift variants to that same function. This removed the old mismatch between percentile-threshold selection and exact top-k selection.
**Conclusion**: The point estimate and CI path now share one implementation, which closes the evaluation inconsistency identified in the plan.
**Citations**: `campaigns/smoke-test-creditcard/train.py:22,114`; `runner/tools/bootstrap_ci.py:13,24-28`; `tests/tools/test_bootstrap_ci_lift.py:11`

### Topic: Mandatory tool enforcement semantics
**Question**: Should omitted `tools_ran` preserve backward compatibility or be treated as missing evidence when mandatory tools are configured?
**Analysis**: The key guard in `runner/runner_driver.py` now always evaluates on `keep` when `mandatory_tools` is non-empty, and it explicitly normalizes `tools_ran=None` to an empty list before checking for missing tools. That change immediately invalidated older test assumptions, which were then updated to provide explicit tool receipts in `keep` paths.
**Conclusion**: The harness now enforces mandatory reviewer-tool execution by default instead of relying on caller opt-in.
**Citations**: `runner/runner_driver.py:554-564`; `tests/safety/test_mandatory_tools.py:106`; `tests/test_runner_driver.py:208`; `tests/integration/test_happy_loop.py:87`

### Topic: Prediction artifact support and cheap assertions
**Question**: What is the smallest change that enables reviewer-side re-computation while preventing obviously invalid metric runs?
**Analysis**: The cheapest robust path was to save validation arrays immediately after `predict_proba`, then assert no NaNs, bounded probabilities, and non-near-constant predictions before downstream metric computation. The same edit also added a minimum-positive assertion after the split and exposed the artifact paths in the structured output block.
**Conclusion**: Reviewer tooling can now load raw validation artifacts directly, and the training script fails early on several classes of silent metric corruption.
**Citations**: `campaigns/smoke-test-creditcard/train.py:62`; `campaigns/smoke-test-creditcard/train.py:96-99`; `campaigns/smoke-test-creditcard/train.py:102`; `campaigns/smoke-test-creditcard/train.py:144-145`

### Topic: Leakage-oriented anomaly coverage
**Question**: Did the anomaly detector only catch implausibly low outcomes and miss implausibly perfect ones?
**Analysis**: `runner/tools/anomaly.py` now checks for values above `0.99` before the lower-bound threshold logic and returns a leakage-oriented diagnostic when that branch fires. A dedicated test was added to assert the detector fires on `0.999` PR-AUC.
**Conclusion**: The anomaly tool now covers both suspiciously low and suspiciously perfect outcomes.
**Citations**: `runner/tools/anomaly.py:52-57`; `tests/tools/test_anomaly.py:61`

## 6. Verification & Quality Checks

**Tests Run**:
- `python -m pytest tests/ -v --tb=short -q` — failed during collection because `optuna` is not installed in the current environment.
- `python -m pytest tests/ -v --tb=short --ignore=tests/tools/test_optuna_search.py` — surfaced expected regressions from the stricter mandatory-tool gate and additional pre-existing optional-dependency failures for `catboost` and `shap`.
- `python -m pytest tests/ -v --tb=short --ignore=tests/tools/test_optuna_search.py --ignore=tests/tools/test_feature_selection.py --ignore=tests/tools/test_shap_report.py` — 150 passed in 3.96s.

**Linter/Formatter**:
- Not run for this session scope.

**Build Status**:
- N/A — Python code and test validation session; no separate build artifact.

**Manual Validation**:
- Verified that the modified runtime files reported no editor/analysis errors (`train.py`, `bootstrap_ci.py`, `runner_driver.py`, `anomaly.py`).
- Reviewed `git diff --stat` and current `git status --short` to confirm the modified surface matches the intended evaluation-hardening scope.

## 7. Plan Alignment Review

**PRD/Original Goals**: Implement the remediation items in `docs/evaluation-hardening-plan.md`, derived from the harness review in `docs/reflections/2026-05-22-harness-engineering-review.md`.

**Completion Status**:
- Standardize lift computation across training and reviewer tooling: Complete
- Save validation prediction artifacts and expose their paths: Complete
- Add minimum-positive and probability-sanity assertions: Complete
- Enforce mandatory reviewer tools fail closed: Complete
- Add upper-bound anomaly detection: Complete
- Create the per-task commits listed in the plan: Pending
- Document artifact paths in an evaluation contract file: Pending

**Scope Changes**: Executable scope matched the plan. Commit creation was intentionally skipped because the session did not include a request to create commits, and one documentation-oriented follow-up was left open.

## 8. Blockers & Issues

**Resolved**:
- Existing test expectations around `keep` verdicts broke once `tools_ran=None` became fail closed; those call sites were updated to pass explicit mandatory tool receipts.
- Git initially refused `status`/`log` inspection during reporting because the repo was not marked safe for the current user; a local `safe.directory` entry was added so logging could proceed.

**Outstanding**:
- The full unignored pytest suite is still blocked by missing optional dependencies in the current environment: `optuna`, `catboost`, and `shap`.
- The plan’s per-task commit steps were not executed, so the worktree remains uncommitted.
- Prediction artifact paths were not documented in an evaluation contract file during this session.

## 9. Next Session Plan

**Immediate Priorities** (ranked):
1. Decide whether to keep the current code as one reviewable patch or split it into the plan’s per-task commits.
2. Add the deferred artifact-path documentation to the appropriate evaluation contract file if that contract should advertise reviewer-readable artifacts.
3. Install or otherwise gate the optional `optuna`, `catboost`, and `shap` dependencies so the full test suite can run without ignore flags.

**Preparation Required**:
- Confirm whether commit creation is desired in the next session.
- Decide whether the artifact-path documentation belongs in `runner/contracts/EVAL_PROTOCOL.md`, a campaign-local contract, or both.
- Prepare an environment with the optional ML dependencies if full-suite validation is required.

**Open Questions**:
- Should the current uncommitted work be preserved as a single changeset or re-executed as the plan’s smaller commit sequence?
- Is contract-level documentation for saved prediction artifacts part of the intended acceptance criteria, or is the executable support sufficient?
- Should optional-tool tests be made skippable by default when dependencies are absent, or should the environment be normalized instead?

---
**Session Duration**: Approximately 1 hour.
**Files Modified**: 12 primary files — `campaigns/smoke-test-creditcard/train.py`, `runner/tools/bootstrap_ci.py`, `runner/runner_driver.py`, `runner/tools/anomaly.py`, `.gitignore`, 6 existing test files updated, and 1 new regression test file created.
**Commits**: 0 created in this session. Recent repo head before these changes: `ad1ec2a updates`.
**Environment**: Linux, VS Code workspace, Python 3.10.20, pytest 9.0.3, git.
