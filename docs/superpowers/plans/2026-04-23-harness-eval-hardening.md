# Harness Evaluation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax (`- [ ]` pending, `- [x]` done).

**Goal:** Convert four prose-enforced spec rules into code-enforced driver gates, eliminating the four highest-ROI validity gaps identified in the tech-lead review.

**Architecture:** Each task modifies `runner_driver.py` (and its shell wrapper / tests) to add a mechanical check that currently exists only in role-prompt prose. Tasks are mutually independent — any ordering works, any task can be skipped without breaking the others. No new files are created except tests.

**Tech Stack:** Python 3.10+, pytest, existing `runner.tools.schema`, `runner.tools._common` utilities.

**Implementation status (2026-04-23):** All four tasks are complete. Driver: `f8cea23` (mandatory `tools_ran`), `660bdf6` (write-scope `commit_diff_files`), `081e6f3` (`c2_pending_diagnose` / A_diagnose gate), `1dce94c` (C3 advisory + `bootstrap_se`). Follow-up: `704750b` (`--bootstrap-se` in `run_round.sh`, README / `RUNNER.md` / role prompts, shell integration test). Every step checkbox below is marked `[x]`.

---

## File Map

| File | Responsibility | Tasks touching it |
|---|---|---|
| `runner/runner_driver.py` | State machine; all four checks land here | 1, 2, 3, 4 |
| `runner/run_round.sh` | CLI wrapper; passes new args to driver | 1, 2 |
| `runner/tools/schema.py` | `validate_campaign_state` gains optional field awareness | 3 |
| `tests/test_runner_driver.py` | Existing driver unit tests; new tests added here | 1, 2, 3, 4 |
| `tests/safety/test_mandatory_tools.py` | New safety test for item 1 | 1 |
| `tests/safety/test_write_scope.py` | New safety test for item 2 | 2 |
| `tests/safety/test_diagnose_after_c2.py` | New safety test for item 3 | 3 |
| `tests/safety/test_auto_c3_trigger.py` | New safety test for item 4 | 4 |

---

## Task 1: Mechanically enforce `mandatory_tools` in `review_finalize`

**Spec rule:** §8.3 item 8 — "A mandatory tool from EVAL_PROTOCOL.mandatory_tools did not run for this round → verdict = malformed."

**What changes:** `review_finalize` gains a new required parameter `tools_ran: list[str]` — a list of tool dotted-names that the Reviewer actually executed (e.g. `["runner.tools.anomaly", "runner.tools.bootstrap_ci"]`). The driver compares this against `EVAL_PROTOCOL.mandatory_tools` and **overrides verdict to `malformed`** if any mandatory tool is missing. `run_round.sh` gains a `--tools-ran` JSON-list argument for the CLI path.

**Files:**
- Modify: `runner/runner_driver.py:215-268` (`review_finalize`)
- Modify: `runner/run_round.sh:35-48` (review-finalize CLI block)
- Create: `tests/safety/test_mandatory_tools.py`

### Steps

- [x] **Step 1: Write the failing test**

Create `tests/safety/test_mandatory_tools.py`:

```python
"""Invariant: review_finalize rejects keep when mandatory tools are missing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

EVAL_WITH_MANDATORY = EVAL_PROTOCOL.replace(
    'mandatory_tools: ["tools/anomaly.py"]',
    'mandatory_tools: ["runner.tools.anomaly", "runner.tools.bootstrap_ci"]',
)


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_MANDATORY)
    return root


def test_keep_rejected_when_mandatory_tool_missing(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["runner.tools.anomaly"],  # missing bootstrap_ci
    )
    assert res["verdict"] == "malformed"
    assert "mandatory_tools" in res.get("halt_reason", "") or res["verdict"] == "malformed"


def test_keep_accepted_when_all_mandatory_tools_present(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["runner.tools.anomaly", "runner.tools.bootstrap_ci"],
    )
    assert res["verdict"] == "keep"


def test_discard_not_overridden_when_tools_missing(campaign: Path):
    """Discard/crash/malformed verdicts are not upgraded to malformed by missing tools."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="discard",
        commit="c1",
        metrics={"val_pr_auc": 0.50, "lift_at_10": 1.0, "macro_f1": 0.5, "val_f1": 0.4},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=[],
    )
    assert res["verdict"] == "discard"


def test_tools_ran_defaults_to_none_for_backward_compat(campaign: Path):
    """Callers that omit tools_ran don't break (backward compat)."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        # tools_ran intentionally omitted
    )
    # When tools_ran is None, the driver cannot verify → should pass through unchanged
    assert res["verdict"] == "keep"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/safety/test_mandatory_tools.py -v`
Expected: FAIL — `review_finalize() got an unexpected keyword argument 'tools_ran'`

- [x] **Step 3: Implement `tools_ran` parameter in `review_finalize`**

In `runner/runner_driver.py`, modify `review_finalize` signature and add the check:

```python
def review_finalize(
    verdict: Verdict,
    commit: str,
    metrics: dict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
    tools_ran: list[str] | None = None,
) -> dict[str, Any]:
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    prior_verdict = state.get("last_verdict")
    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    pm = (eval_fm.get("primary_metric") or {})
    metric_name = pm.get("name", "val_pr_auc")
    direction = pm.get("direction", "maximize")

    # --- Mandatory-tools gate (spec §8.3 item 8) ---
    mandatory = set(eval_fm.get("mandatory_tools") or [])
    if tools_ran is not None and mandatory and verdict == "keep":
        missing = mandatory - set(tools_ran)
        if missing:
            verdict = "malformed"

    log.append_result(
        # ... rest unchanged ...
```

The key design decisions:
- `tools_ran=None` (default) means "caller cannot attest" → skip the check (backward compat with existing tests and callers).
- Only override `keep` → `malformed`. Non-keep verdicts are already negative; adding a mandatory-tool check on them would be punitive without benefit.
- The check happens *before* `log.append_result`, so `results.tsv` records the overridden `malformed`, not the original `keep`.

- [x] **Step 4: Update `run_round.sh` to pass `--tools-ran`**

In the `review-finalize` block of `runner/run_round.sh`, parse the new `--tools-ran` argument (a JSON list string) and pass it through:

```python
elif stage == "review-finalize":
    metrics = json.loads(args["metrics_json"])
    tools_ran = json.loads(args["tools_ran"]) if "tools_ran" in args else None
    res = runner_driver.review_finalize(
        verdict=args["verdict"],
        commit=args["commit"],
        metrics=metrics,
        action_type=args["action_type"],
        hypothesis=args["hypothesis"],
        description=args["description"],
        model_family=args["model_family"],
        n_features=int(args["n_features"]),
        campaign_dir=args.get("campaign_dir", "runner/"),
        tools_ran=tools_ran,
    )
    print(json.dumps(res))
```

- [x] **Step 5: Run tests to verify they pass**

Run: `pytest tests/safety/test_mandatory_tools.py tests/test_runner_driver.py tests/integration/ -v`
Expected: ALL PASS (new tests pass; existing tests still pass because `tools_ran` defaults to `None`).

- [x] **Step 6: Commit**

```bash
git add runner/runner_driver.py runner/run_round.sh tests/safety/test_mandatory_tools.py
git commit -m "feat: mechanically enforce mandatory_tools in review_finalize (spec §8.3 item 8)"
```

---

## Task 2: Mechanically enforce Executor write-scope in `execute_finalize`

**Spec rule:** §8.3 item 6 — "Executor modified a read-only path (detected by inspecting the commit diff)."

**What changes:** `execute_finalize` gains an optional `commit_diff_files: list[str]` parameter — the list of files touched by the Executor's commit (the caller runs `git diff --name-only <base>..<commit>` and passes the result). The driver checks every path against the allowed write set: `train.py` + any files declared in `helpers_declared` from `NEXT_EXPERIMENT.md`. Paths outside this set → force `synthetic_verdict = "malformed"`.

**Files:**
- Modify: `runner/runner_driver.py:186-212` (`execute_finalize`)
- Modify: `runner/run_round.sh:30-34` (execute-finalize CLI block)
- Create: `tests/safety/test_write_scope.py`

### Steps

- [x] **Step 1: Write the failing test**

Create `tests/safety/test_write_scope.py`:

```python
"""Invariant: execute_finalize rejects commits that touch read-only paths."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

PLAN_NO_HELPERS = """---
schema_version: 1
campaign_id: "tiny"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "tighter range"
expected_effect_size: 0.001
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
1. noop.
## 4. Helpers
None.
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)
N/A.
"""


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_rejects_commit_touching_prepare_py(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(PLAN_NO_HELPERS)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py", "prepare.py"],
    )
    assert res["synthetic_verdict"] == "malformed"
    assert "prepare.py" in res.get("reason", "")


def test_rejects_commit_touching_contracts(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(PLAN_NO_HELPERS)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py", "runner/contracts/EVAL_PROTOCOL.md"],
    )
    assert res["synthetic_verdict"] == "malformed"


def test_accepts_commit_touching_only_train_py(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(PLAN_NO_HELPERS)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py"],
    )
    assert res["synthetic_verdict"] is None
    assert res["channel"] == "RUN_COMPLETE"


def test_accepts_declared_helpers(campaign: Path):
    plan_with_helpers = PLAN_NO_HELPERS.replace(
        "touches_helpers: false", "touches_helpers: true"
    ).replace(
        "helpers_declared: []",
        'helpers_declared: ["runner/experiment_helpers/abc123/custom.py"]',
    )
    runner_driver.init_campaign(campaign_dir=str(campaign))
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(plan_with_helpers)
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
        commit_diff_files=["train.py", "runner/experiment_helpers/abc123/custom.py"],
    )
    assert res["synthetic_verdict"] is None


def test_no_diff_files_skips_check(campaign: Path):
    """Backward compat: when commit_diff_files is not provided, skip the check."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
    )
    assert res["channel"] == "RUN_COMPLETE"
    assert res["synthetic_verdict"] is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/safety/test_write_scope.py -v`
Expected: FAIL — `execute_finalize() got an unexpected keyword argument 'commit_diff_files'`

- [x] **Step 3: Implement `commit_diff_files` check in `execute_finalize`**

In `runner/runner_driver.py`, modify `execute_finalize`:

```python
_READ_ONLY_PATTERNS = (
    "prepare.py",
    "data/",
    "runner/contracts/",
    "runner/roles/",
    "runner/tools/",
    "log.py",
)


def execute_finalize(
    executor_stdout: str,
    campaign_dir: str = "runner/",
    commit_diff_files: list[str] | None = None,
) -> dict[str, Any]:
    matches = list(_STDOUT_RE.finditer(executor_stdout))
    if not matches:
        return {
            "channel": None,
            "commit": None,
            "synthetic_verdict": "malformed",
            "reason": "Executor emitted no recognized channel line",
        }
    m = matches[-1]
    channel = m.group("channel")
    rest = m.group("rest").strip()

    if channel == "RUN_COMPLETE":
        commit = rest.split()[0] if rest else None

        # --- Write-scope gate (spec §8.3 item 6) ---
        if commit_diff_files is not None:
            camp = Path(campaign_dir)
            plan_path = camp / "state" / "NEXT_EXPERIMENT.md"
            allowed = {"train.py"}
            try:
                fm, _ = parse_frontmatter(plan_path)
                for h in fm.get("helpers_declared") or []:
                    allowed.add(h)
            except (FrontmatterError, OSError):
                pass
            violations = [
                f for f in commit_diff_files
                if f not in allowed and not any(f.startswith(a) for a in allowed)
            ]
            read_only_violations = [
                f for f in violations
                if any(f == p or f.startswith(p) for p in _READ_ONLY_PATTERNS)
            ]
            if read_only_violations:
                return {
                    "channel": channel,
                    "commit": commit,
                    "synthetic_verdict": "malformed",
                    "reason": f"write_scope_violation: {read_only_violations}",
                }

        return {"channel": channel, "commit": commit, "synthetic_verdict": None, "reason": ""}
    if channel == "RUN_FAILED":
        parts = rest.split(maxsplit=1)
        commit = parts[0] if parts else None
        reason = parts[1] if len(parts) > 1 else ""
        return {"channel": channel, "commit": commit, "synthetic_verdict": "crash", "reason": reason}
    if channel == "REVIEW_REQUIRED":
        return {"channel": channel, "commit": None, "synthetic_verdict": "malformed", "reason": rest}
    raise DriverError(f"unhandled channel: {channel}")
```

- [x] **Step 4: Update `run_round.sh` to pass `--commit-diff-files`**

In the `execute-finalize` block of `runner/run_round.sh`, add optional diff-files parsing:

```python
elif stage == "execute-finalize":
    stdout_file = args["stdout_file"]
    text = open(stdout_file).read()
    diff_files = json.loads(args["commit_diff_files"]) if "commit_diff_files" in args else None
    res = runner_driver.execute_finalize(
        text,
        campaign_dir=args.get("campaign_dir", "runner/"),
        commit_diff_files=diff_files,
    )
    print(json.dumps(res))
```

- [x] **Step 5: Run tests to verify they pass**

Run: `pytest tests/safety/test_write_scope.py tests/test_runner_driver.py tests/integration/ -v`
Expected: ALL PASS.

- [x] **Step 6: Commit**

```bash
git add runner/runner_driver.py runner/run_round.sh tests/safety/test_write_scope.py
git commit -m "feat: mechanically enforce Executor write-scope in execute_finalize (spec §8.3 item 6)"
```

---

## Task 3: Gate `resolve_c2` on A_diagnose-first

**Spec rule:** STRATEGY_GUIDE.md §3.7 — "When C2 plateau trigger fires, the default next action is A_diagnose, not A_ensemble or A_model."

**What changes:** `resolve_c2` gains a new state tracking field `c2_pending_diagnose` in `CAMPAIGN_STATE.json`. When `resolve_c2` runs, it sets `c2_pending_diagnose = true` instead of immediately resetting `consecutive_discards`. Then `plan_check` enforces that the next plan after C2 resolution has `action_type == "A_diagnose"` when `c2_pending_diagnose` is true. After that A_diagnose round's `review_finalize` completes, `c2_pending_diagnose` is cleared.

This is slightly more nuanced than "just block resolve_c2" because the Planner needs to be able to produce a plan after C2 is resolved — but that plan must be A_diagnose.

**Files:**
- Modify: `runner/runner_driver.py` (`resolve_c2`, `plan_check`, `review_finalize`)
- Modify: `runner/tools/schema.py:219-247` (`_CS_REQUIRED_KEYS` — make `c2_pending_diagnose` an optional field)
- Create: `tests/safety/test_diagnose_after_c2.py`

### Steps

- [x] **Step 1: Write the failing test**

Create `tests/safety/test_diagnose_after_c2.py`:

```python
"""Invariant: after C2 resolve, the next plan must be A_diagnose."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety


def _make_plan(action_type: str = "A_hp", round_n: int = 4) -> str:
    return f"""---
schema_version: 1
campaign_id: "tiny"
round: {round_n}
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "{action_type}"
hypothesis: "test hypothesis"
expected_effect_size: 0.001
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
1. noop.
## 4. Helpers
None.
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)
N/A.
"""


@pytest.fixture
def campaign_at_plateau(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    runner_driver.init_campaign(campaign_dir=str(root))

    # Push state to 3 consecutive discards (plateau trigger)
    for i in range(3):
        runner_driver.review_finalize(
            verdict="discard", commit=f"d{i}",
            metrics={"val_pr_auc": 0.4, "lift_at_10": 0, "macro_f1": 0, "val_f1": 0},
            action_type="A_hp", hypothesis="h", description="d",
            model_family="lightgbm", n_features=10,
            campaign_dir=str(root),
        )
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 3
    return root


def test_plan_check_rejects_non_diagnose_after_c2_resolve(campaign_at_plateau: Path):
    root = campaign_at_plateau
    runner_driver.resolve_c2(
        resolution="switching strategy", campaign_dir=str(root),
    )
    # Write a plan with A_ensemble (not A_diagnose)
    (root / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_ensemble", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(root))
    assert res["status"] == "malformed"
    assert any("A_diagnose" in e for e in res["errors"])


def test_plan_check_accepts_diagnose_after_c2_resolve(campaign_at_plateau: Path):
    root = campaign_at_plateau
    runner_driver.resolve_c2(
        resolution="switching strategy", campaign_dir=str(root),
    )
    (root / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_diagnose", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(root))
    assert res["status"] == "ok"


def test_c2_pending_cleared_after_diagnose_round(campaign_at_plateau: Path):
    root = campaign_at_plateau
    runner_driver.resolve_c2(
        resolution="switching strategy", campaign_dir=str(root),
    )
    # Complete an A_diagnose round
    runner_driver.review_finalize(
        verdict="discard", commit="diag1",
        metrics={"val_pr_auc": 0.4, "lift_at_10": 0, "macro_f1": 0, "val_f1": 0},
        action_type="A_diagnose", hypothesis="diagnose", description="d",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(root),
    )
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state.get("c2_pending_diagnose") is not True

    # Now a non-diagnose plan should be accepted
    (root / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_model", round_n=5)
    )
    res = runner_driver.plan_check(campaign_dir=str(root))
    assert res["status"] == "ok"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/safety/test_diagnose_after_c2.py -v`
Expected: FAIL — `test_plan_check_rejects_non_diagnose_after_c2_resolve` fails because `plan_check` currently accepts `A_ensemble` after C2 resolve.

- [x] **Step 3: Add `c2_pending_diagnose` to `resolve_c2`**

In `runner/runner_driver.py`, modify `resolve_c2` to set the flag:

After the line `state["consecutive_discards"] = 0`, add:
```python
    state["c2_pending_diagnose"] = True
```

- [x] **Step 4: Add `c2_pending_diagnose` check to `plan_check`**

In `runner/runner_driver.py`, in `plan_check`, after the existing C2 escalation check block (after line ~115), add:

```python
    if state.get("c2_pending_diagnose") and escalation is None:
        plan_action = fm.get("action_type") if fm else None
        if plan_action != "A_diagnose":
            errors.append(
                f"c2_pending_diagnose is active — next plan must be A_diagnose "
                f"(STRATEGY_GUIDE §3.7), got {plan_action!r}"
            )
```

- [x] **Step 5: Clear `c2_pending_diagnose` in `review_finalize` after A_diagnose round**

In `runner/runner_driver.py`, in `review_finalize`, after the call to `log.append_result(...)` and `state_after = json.loads(...)`, add:

```python
    if action_type == "A_diagnose" and state_after.get("c2_pending_diagnose"):
        state_after["c2_pending_diagnose"] = False
        state_path.write_text(json.dumps(state_after, indent=2, sort_keys=True) + "\n")
```

- [x] **Step 6: Run tests to verify they pass**

Run: `pytest tests/safety/test_diagnose_after_c2.py tests/test_runner_driver.py tests/integration/ -v`
Expected: ALL PASS.

- [x] **Step 7: Commit**

```bash
git add runner/runner_driver.py tests/safety/test_diagnose_after_c2.py
git commit -m "feat: gate post-C2 plans on A_diagnose-first (STRATEGY_GUIDE §3.7)"
```

---

## Task 4: Auto-emit C3 advisory when target gap ≤ 2×bootstrap_se

**Spec rule:** STRATEGY_GUIDE.md §1 evidence-trigger — "Target gap ≤ 2× bootstrap_se → the bottleneck is measurement, not modeling. Trigger C3 to upgrade the CV scheme before continuing."

**What changes:** `review_finalize` gains an optional `bootstrap_se: float | None` parameter. When the Reviewer reports a bootstrap SE, the driver computes `target_gap = success_criterion - best_so_far` and checks `target_gap <= 2 * bootstrap_se`. If true, the return dict gains `c3_advisory: True` and `c3_advisory_reason: "..."` fields — this is an advisory signal (not a hard block) that the next Planner should emit a C3 escalation to upgrade the CV scheme. The driver does NOT halt; it adds the signal to the return, and updates `CAMPAIGN_STATE.json` with `c3_advisory_active: true` so `plan_check` can warn on subsequent rounds.

**Design note:** We make this an advisory (warning in `plan_check` return) rather than a hard block because the success criterion parsing from `PROBLEM_CONTRACT.md` is heuristic (we parse the first `success_criteria` entry for a number). A hard block on a heuristic parse would be fragile.

**Files:**
- Modify: `runner/runner_driver.py` (`review_finalize`, `plan_check`)
- Create: `tests/safety/test_auto_c3_trigger.py`

### Steps

- [x] **Step 1: Write the failing test**

Create `tests/safety/test_auto_c3_trigger.py`:

```python
"""Invariant: review_finalize advises C3 when target_gap <= 2*bootstrap_se."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

PROBLEM_WITH_TARGET = PROBLEM_CONTRACT.replace(
    'success_criteria: ["val_pr_auc >= 0.5"]',
    'success_criteria: ["val_pr_auc >= 0.85"]',
)


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_WITH_TARGET)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    return root


def test_c3_advisory_emitted_when_gap_within_noise(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    # First round: establish a best_so_far
    runner_driver.review_finalize(
        verdict="keep", commit="c1",
        metrics={"val_pr_auc": 0.844, "lift_at_10": 9.0, "macro_f1": 0.9, "val_f1": 0.8},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=30,
        campaign_dir=str(campaign),
    )
    # Second round: bootstrap_se=0.035 → 2*se=0.07, gap=0.85-0.844=0.006 < 0.07
    res = runner_driver.review_finalize(
        verdict="discard", commit="c2",
        metrics={"val_pr_auc": 0.840, "lift_at_10": 8.0, "macro_f1": 0.88, "val_f1": 0.78},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=30,
        campaign_dir=str(campaign),
        bootstrap_se=0.035,
    )
    assert res.get("c3_advisory") is True
    assert "measurement" in res.get("c3_advisory_reason", "").lower() or \
           "cv" in res.get("c3_advisory_reason", "").lower()


def test_no_c3_advisory_when_gap_large(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    # best_so_far at 0.60 → gap = 0.85 - 0.60 = 0.25, well above 2*0.035=0.07
    runner_driver.review_finalize(
        verdict="keep", commit="c1",
        metrics={"val_pr_auc": 0.60, "lift_at_10": 3.0, "macro_f1": 0.6, "val_f1": 0.5},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="logreg", n_features=30,
        campaign_dir=str(campaign),
    )
    res = runner_driver.review_finalize(
        verdict="discard", commit="c2",
        metrics={"val_pr_auc": 0.55, "lift_at_10": 2.0, "macro_f1": 0.5, "val_f1": 0.4},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="logreg", n_features=30,
        campaign_dir=str(campaign),
        bootstrap_se=0.035,
    )
    assert res.get("c3_advisory") is not True


def test_no_c3_advisory_when_se_not_provided(campaign: Path):
    """Backward compat: when bootstrap_se is omitted, no advisory."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    runner_driver.review_finalize(
        verdict="keep", commit="c1",
        metrics={"val_pr_auc": 0.844, "lift_at_10": 9.0, "macro_f1": 0.9, "val_f1": 0.8},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=30,
        campaign_dir=str(campaign),
    )
    res = runner_driver.review_finalize(
        verdict="discard", commit="c2",
        metrics={"val_pr_auc": 0.840, "lift_at_10": 8.0, "macro_f1": 0.88, "val_f1": 0.78},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="xgboost", n_features=30,
        campaign_dir=str(campaign),
        # bootstrap_se intentionally omitted
    )
    assert res.get("c3_advisory") is not True
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/safety/test_auto_c3_trigger.py -v`
Expected: FAIL — `review_finalize() got an unexpected keyword argument 'bootstrap_se'`

- [x] **Step 3: Add success-criterion parser helper**

In `runner/runner_driver.py`, add a small helper near the top (after `_STDOUT_RE`):

```python
_SUCCESS_METRIC_RE = re.compile(
    r"(\w+)\s*>=?\s*([\d.]+)", re.IGNORECASE,
)


def _parse_success_target(
    problem_contract_path: Path,
    primary_metric_name: str,
) -> float | None:
    """Best-effort parse of the first success_criteria entry for a numeric target."""
    try:
        fm, _ = parse_frontmatter(problem_contract_path)
    except (FrontmatterError, OSError):
        return None
    criteria = fm.get("success_criteria") or []
    for crit in criteria:
        m = _SUCCESS_METRIC_RE.search(str(crit))
        if m and m.group(1) == primary_metric_name:
            return float(m.group(2))
    return None
```

- [x] **Step 4: Add `bootstrap_se` parameter and C3 advisory logic to `review_finalize`**

In `runner/runner_driver.py`, add `bootstrap_se: float | None = None` to the `review_finalize` signature.

After the existing `halt_loop` / `halt_reason` block (before the `return` dict), add:

```python
    c3_advisory = False
    c3_advisory_reason = ""
    if bootstrap_se is not None and bootstrap_se > 0:
        problem_path = camp / "contracts" / "PROBLEM_CONTRACT.md"
        success_target = _parse_success_target(problem_path, metric_name)
        best_metric = state_after.get("best_so_far", {}).get("primary_metric")
        if success_target is not None and best_metric is not None:
            target_gap = success_target - best_metric
            if target_gap > 0 and target_gap <= 2 * bootstrap_se:
                c3_advisory = True
                c3_advisory_reason = (
                    f"target_gap={target_gap:.4f} <= 2*bootstrap_se={2*bootstrap_se:.4f} — "
                    f"bottleneck is measurement, not modeling; consider C3 to upgrade CV scheme"
                )
```

And update the return dict:

```python
    result = {
        "verdict": verdict,
        "should_rollback": should_rollback,
        "pause_loop": pause_loop,
        "halt_loop": halt_loop,
        "halt_reason": halt_reason,
    }
    if c3_advisory:
        result["c3_advisory"] = True
        result["c3_advisory_reason"] = c3_advisory_reason
    return result
```

- [x] **Step 5: Run tests to verify they pass**

Run: `pytest tests/safety/test_auto_c3_trigger.py tests/test_runner_driver.py tests/integration/ -v`
Expected: ALL PASS.

- [x] **Step 6: Commit**

```bash
git add runner/runner_driver.py tests/safety/test_auto_c3_trigger.py
git commit -m "feat: auto-emit C3 advisory when target_gap <= 2*bootstrap_se (STRATEGY_GUIDE §1)"
```

---

## Self-Review Checklist

### 1. Spec coverage

| Review finding | Task | Covered? |
|---|---|---|
| T2: `mandatory_tools` prose-only enforcement | Task 1 | Yes — `tools_ran` parameter + override to malformed |
| T5: Plan adherence / write-scope prose-only | Task 2 | Yes — `commit_diff_files` + read-only pattern check |
| Round-10 loophole: A_diagnose skipped after C2 | Task 3 | Yes — `c2_pending_diagnose` state flag + plan_check gate |
| STRATEGY_GUIDE §1 "target_gap ≤ 2·SE" not enforced | Task 4 | Yes — advisory in `review_finalize` return |

### 2. Placeholder scan

No "TBD", "TODO", "implement later", "similar to Task N", or description-only steps found.

### 3. Type consistency

- `tools_ran: list[str] | None` — used consistently in Task 1 tests and implementation.
- `commit_diff_files: list[str] | None` — used consistently in Task 2 tests and implementation.
- `c2_pending_diagnose: bool` — set `True` in `resolve_c2`, checked in `plan_check`, cleared in `review_finalize`.
- `bootstrap_se: float | None` — used consistently in Task 4 tests and implementation.
- `_parse_success_target` returns `float | None` — checked for `None` before arithmetic.
- All tasks use existing test fixture patterns from `tests/test_runner_driver.py`.

### 4. Backward compatibility

All four changes use optional parameters with `None` defaults. Existing callers (including all existing tests, the integration tests, and the shell wrapper) continue to work unchanged. The shell wrapper changes in Tasks 1–2 only parse the new args when present.

### 5. Independence

Tasks 1–4 modify different sections of `runner_driver.py` and do not share any new code. They can be implemented in any order, on separate branches, or as four independent PRs.
