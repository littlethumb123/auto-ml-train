# Orchestrator v1 — Prompt-Level Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a prompt-level orchestrator that enables a single Claude Code agent session to autonomously run multi-round ML experiment campaigns (Plan → Execute → Review → Historian) with context-rot mitigation, using only Claude Code CLI — no Anthropic SDK required.

**Architecture:** The orchestrator is a prompt harness (`runner/roles/orchestrator.md`) that instructs a Claude Code agent to loop through experiment rounds. Each round, the agent executes one role at a time by reading that role's prompt, performing the role's work, calling `runner_driver` via bash for deterministic validation, then proceeding to the next role. Context rot is mitigated by (1) re-reading all state from disk each round (never relying on memory), (2) a mandatory context-reset protocol between roles, and (3) a round-summary checkpoint that replaces accumulated detail with a compact digest. The state machine enforcement stays in Python code (`runner_driver.py`); intelligence stays in role prompts.

**Tech Stack:** Python 3.10+, existing `runner_driver.py` (read-only), Claude Code CLI (interactive or `claude -p`), `pytest` for tests.

---

## Design Decisions

### Why prompt-level harness, not SDK

1. **Zero additional dependencies** — works with any Claude Code installation
2. **Adoption first** — any DS clones the repo, opens Claude Code, says "run the campaign"
3. **Post-hoc enforcement is sufficient** — `execute_finalize()` already checks write-scope violations and returns synthetic `malformed` verdict → rollback. Same safety guarantee as real-time blocking.
4. **Token estimation already built** — `_auto_estimate_round_tokens()` provides directional cost tracking without API `usage` objects.
5. **Upgrade path is clean** — v2 SDK orchestrator swaps WHO calls driver functions (Python import vs. agent bash call), not WHAT gets called. Role prompts, contracts, state artifacts all unchanged.

### Context-rot mitigation strategy

The #1 risk of a long-running agent session is context window saturation. Three mitigations:

1. **Disk-first, memory-never**: Every role re-reads state from disk at the start. The orchestrator prompt explicitly forbids relying on recalled content from previous rounds.
2. **Round checkpoint digest**: After each round completes, the agent writes a 3-line summary to a running digest and explicitly instructs itself to forget round details. This replaces unbounded conversation history with a fixed-size checkpoint.
3. **Driver as external brain**: All complex state logic (historian triggers, budget tracking, halt conditions) is computed by `runner_driver.py` via bash calls. The agent doesn't compute — it reads the driver's JSON output.

### Agent coordination strategy

Unlike Superpowers which dispatches separate sub-agents per task, this harness uses a **sequential role-switching pattern within a single session**:

- The orchestrator prompt defines a clear phase-transition protocol
- Between roles, the agent calls the driver for validation (deterministic gate)
- The agent explicitly discards role-specific context after each phase
- State handoff happens exclusively through disk artifacts, never through agent memory

This avoids the sub-agent dispatch complexity while preserving role separation through the prompt structure. The tradeoff vs. sub-agents is that context accumulates in one session, which the checkpoint digest mitigates.

### What the orchestrator does NOT do

- Does NOT replace role prompts — roles remain in `runner/roles/*.md`, read by the agent
- Does NOT implement decision logic — Planner decides what to try, Reviewer decides keep/discard
- Does NOT bypass `runner_driver.py` — all state transitions go through the driver
- Does NOT require API keys, SDK, or any infrastructure beyond Claude Code CLI

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `runner/roles/orchestrator.md` | The main orchestrator prompt — loop structure, phase transitions, context-rot mitigation, crash recovery |
| **Create:** `runner/orchestrator.py` | Lightweight Python helper for the orchestrator: stuck detection, metrics parsing, round digest formatting, resume-phase detection |
| **Modify:** `runner/runner_driver.py` | Add 2 small helpers: `get_campaign_status()` and `should_run_historian()` |
| **Create:** `tests/test_orchestrator_helpers.py` | Unit tests for the Python helper functions |
| **Create:** `tests/integration/test_orchestrator_prompt.py` | Integration test validating the prompt structure and driver integration |

---

## Task 1: Add Driver Helper Functions

**Files:**
- Modify: `runner/runner_driver.py`
- Test: `tests/test_runner_driver.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_runner_driver.py`:

```python
def test_get_campaign_status(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    status = runner_driver.get_campaign_status(campaign_dir=str(campaign))
    assert status["round"] == 0
    assert status["budget_used"] == 0
    assert status["budget_total"] == 3
    assert status["best_metric"] is None
    assert status["historian_trigger_pending"] is False
    assert status["consecutive_discards"] == 0
    assert "next_role" in status


def test_should_run_historian_false_initially(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    assert runner_driver.should_run_historian(campaign_dir=str(campaign)) is False


def test_should_run_historian_true_when_pending(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    import json
    state = json.loads(state_path.read_text())
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2))
    assert runner_driver.should_run_historian(campaign_dir=str(campaign)) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runner_driver.py::test_get_campaign_status tests/test_runner_driver.py::test_should_run_historian_false_initially tests/test_runner_driver.py::test_should_run_historian_true_when_pending -v`
Expected: FAIL — `AttributeError: module 'runner.runner_driver' has no attribute 'get_campaign_status'`

- [ ] **Step 3: Implement the helpers**

Add to the end of `runner/runner_driver.py` (before any `if __name__` block):

```python
def get_campaign_status(campaign_dir: str = "runner/") -> dict[str, Any]:
    """Return a compact status dict for the orchestrator to display and act on."""
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        return {"status": "uninitialized", "next_role": "init"}

    state = json.loads(state_path.read_text())
    best = state.get("best_so_far") or {}

    # Determine next role from state
    next_role = "planner"
    if state.get("historian_trigger_pending", False):
        next_role = "historian"
    plan_path = camp / "state" / "NEXT_EXPERIMENT.md"
    run_log = camp / "run.log"
    if plan_path.exists() and not run_log.exists():
        next_role = "executor"
    elif run_log.exists():
        log_text = run_log.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^(RUN_COMPLETE|RUN_FAILED):", log_text, re.MULTILINE):
            next_role = "reviewer"

    return {
        "round": int(state.get("round", 0)),
        "budget_used": int(state.get("budget_used", 0)),
        "budget_total": int(state.get("budget_total", 0)),
        "best_metric": best.get("primary_metric"),
        "best_commit": best.get("commit"),
        "last_verdict": state.get("last_verdict"),
        "consecutive_discards": int(state.get("consecutive_discards", 0)),
        "historian_trigger_pending": bool(state.get("historian_trigger_pending", False)),
        "next_role": next_role,
    }


def should_run_historian(campaign_dir: str = "runner/") -> bool:
    """Check if the Historian should run before the next Planner turn."""
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        return False
    state = json.loads(state_path.read_text())
    return bool(state.get("historian_trigger_pending", False))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runner_driver.py::test_get_campaign_status tests/test_runner_driver.py::test_should_run_historian_false_initially tests/test_runner_driver.py::test_should_run_historian_true_when_pending -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add runner/runner_driver.py tests/test_runner_driver.py
git commit -m "feat(driver): add get_campaign_status and should_run_historian helpers"
```

---

## Task 2: Orchestrator Python Helpers

**Files:**
- Create: `runner/orchestrator.py`
- Create: `tests/test_orchestrator_helpers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_orchestrator_helpers.py`:

```python
"""Unit tests for runner/orchestrator.py helper functions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import orchestrator
from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "campaign"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    (root / "train.py").write_text("# placeholder\n")
    return root


# ── Stuck detection ───────────────────────────────────────────────────

class TestStuckDetection:
    def test_no_warnings_on_empty(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        assert orchestrator.detect_stuck(campaign) == []

    def test_warns_on_3_same_action_types(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        results_path = campaign / "state" / "results.tsv"
        header = results_path.read_text().splitlines()[0]
        col_names = header.split("\t")
        at_idx = col_names.index("action_type")
        n_cols = len(col_names)

        rows = []
        for i in range(3):
            row = [""] * n_cols
            row[0] = f"c{i}"
            row[at_idx] = "A_hp"
            rows.append("\t".join(row))
        results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

        warnings = orchestrator.detect_stuck(campaign)
        assert len(warnings) >= 1
        assert any("STUCK" in w for w in warnings)

    def test_warns_on_abab_alternation(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        results_path = campaign / "state" / "results.tsv"
        header = results_path.read_text().splitlines()[0]
        col_names = header.split("\t")
        at_idx = col_names.index("action_type")
        n_cols = len(col_names)

        rows = []
        for i, at in enumerate(["A_hp", "A_model", "A_hp", "A_model"]):
            row = [""] * n_cols
            row[0] = f"c{i}"
            row[at_idx] = at
            rows.append("\t".join(row))
        results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

        warnings = orchestrator.detect_stuck(campaign)
        assert any("alternation" in w.lower() or "A-B-A-B" in w for w in warnings)

    def test_no_warning_on_varied_types(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        results_path = campaign / "state" / "results.tsv"
        header = results_path.read_text().splitlines()[0]
        col_names = header.split("\t")
        at_idx = col_names.index("action_type")
        n_cols = len(col_names)

        rows = []
        for i, at in enumerate(["A_hp", "A_model", "A_feature"]):
            row = [""] * n_cols
            row[0] = f"c{i}"
            row[at_idx] = at
            rows.append("\t".join(row))
        results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

        assert orchestrator.detect_stuck(campaign) == []


# ── Metrics parsing ───────────────────────────────────────────────────

class TestMetricsParsing:
    def test_parses_val_lines(self, tmp_path: Path):
        log = tmp_path / "run.log"
        log.write_text("val_pr_auc: 0.875\nval_f1: 0.62\nother line\n")
        metrics = orchestrator.parse_metrics_from_log(log)
        assert metrics["val_pr_auc"] == pytest.approx(0.875)
        assert metrics["val_f1"] == pytest.approx(0.62)

    def test_parses_delimited_block(self, tmp_path: Path):
        log = tmp_path / "run.log"
        log.write_text("---\nval_pr_auc: 0.9\nlift_at_10: 4.2\n---\n")
        metrics = orchestrator.parse_metrics_from_log(log)
        assert metrics["val_pr_auc"] == pytest.approx(0.9)

    def test_empty_log(self, tmp_path: Path):
        log = tmp_path / "run.log"
        log.write_text("")
        assert orchestrator.parse_metrics_from_log(log) == {}

    def test_missing_log(self, tmp_path: Path):
        log = tmp_path / "nonexistent.log"
        assert orchestrator.parse_metrics_from_log(log) == {}


# ── Resume phase detection ────────────────────────────────────────────

class TestResumePhase:
    def test_planner_when_nothing_present(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        assert orchestrator.determine_resume_phase(campaign, state) == "planner"

    def test_executor_when_plan_exists(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        plan = "---\nround: 5\n---\n## 1. Context\ntest\n"
        (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(plan)
        assert orchestrator.determine_resume_phase(campaign, state) == "executor"

    def test_reviewer_when_run_log_exists(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        (campaign / "run.log").write_text("RUN_COMPLETE: abc123\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "reviewer"

    def test_historian_when_journal_complete_and_pending(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        state["historian_trigger_pending"] = True
        (campaign / "state" / "CAMPAIGN_JOURNAL.md").write_text("## Round 5\nDone.\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "historian"

    def test_next_round_when_journal_complete_no_trigger(self, campaign: Path):
        runner_driver.init_campaign(campaign_dir=str(campaign))
        state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
        state["round"] = 5
        state["historian_trigger_pending"] = False
        (campaign / "state" / "CAMPAIGN_JOURNAL.md").write_text("## Round 5\nDone.\n")
        assert orchestrator.determine_resume_phase(campaign, state) == "next_round"


# ── Round digest ──────────────────────────────────────────────────────

class TestRoundDigest:
    def test_format_round_digest(self):
        digest = orchestrator.format_round_digest(
            round_num=3,
            verdict="keep",
            action_type="A_feature",
            hypothesis="add county encoding",
            primary_metric_value=0.875,
            primary_metric_name="val_pr_auc",
        )
        assert "Round 3" in digest
        assert "keep" in digest
        assert "A_feature" in digest
        assert "0.875" in digest


# ── Tools-ran inference ───────────────────────────────────────────────

class TestToolsRanInference:
    def test_infers_from_text(self):
        text = "I ran anomaly detection and bootstrap_ci confidence intervals."
        tools = orchestrator.infer_tools_ran(text)
        assert "runner.tools.anomaly" in tools
        assert "runner.tools.bootstrap_ci" in tools

    def test_empty_text(self):
        assert orchestrator.infer_tools_ran("") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator_helpers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'runner.orchestrator'`

- [ ] **Step 3: Implement the orchestrator helpers**

Create `runner/orchestrator.py`:

```python
"""runner/orchestrator.py — Helper functions for the prompt-level orchestrator.

This module provides deterministic utility functions called by the orchestrator
agent (via bash) during campaign execution. The orchestrator prompt is in
runner/roles/orchestrator.md; this file provides the computational support.

Usage by the orchestrator agent:
    python -c "from runner.orchestrator import detect_stuck; ..."
    python -c "from runner.orchestrator import determine_resume_phase; ..."
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


# ── Stuck detection ───────────────────────────────────────────────────

def detect_stuck(campaign_dir: Path) -> list[str]:
    """Parse results.tsv for repetitive action_type patterns. Return warning strings."""
    results_path = campaign_dir / "state" / "results.tsv"
    if not results_path.exists():
        return []

    lines = results_path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 2:
        return []

    header = lines[0].split("\t")
    try:
        at_idx = header.index("action_type")
    except ValueError:
        return []

    action_types = []
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) > at_idx:
            action_types.append(cols[at_idx])

    warnings: list[str] = []

    # Same action_type for last 3 consecutive rows
    if len(action_types) >= 3 and len(set(action_types[-3:])) == 1:
        warnings.append(
            f"STUCK WARNING: Last 3 experiments all used action_type='{action_types[-1]}'. "
            f"You MUST try a different action_type."
        )

    # A-B-A-B alternation in last 4
    if len(action_types) >= 4:
        last4 = action_types[-4:]
        if last4[0] == last4[2] and last4[1] == last4[3] and last4[0] != last4[1]:
            warnings.append(
                f"STUCK WARNING: A-B-A-B alternation detected ({last4[0]}/{last4[1]}). "
                f"Break this pattern — try a completely different approach."
            )

    return warnings


# ── Metrics parsing ───────────────────────────────────────────────────

def parse_metrics_from_log(log_path: Path) -> dict[str, float]:
    """Parse val_<metric>: <float> lines and --- blocks from run.log."""
    if not log_path.exists():
        return {}

    text = log_path.read_text(encoding="utf-8", errors="replace")
    metrics: dict[str, float] = {}

    # Parse val_<metric>: <float> lines
    for m in re.finditer(r"^(val_\w+):\s*([\d.eE+-]+)\s*$", text, re.MULTILINE):
        try:
            metrics[m.group(1)] = float(m.group(2))
        except ValueError:
            pass

    # Parse --- delimited key-value blocks
    for block_match in re.finditer(
        r"^---\s*\n(.*?)\n---\s*$", text, re.MULTILINE | re.DOTALL
    ):
        block = block_match.group(1)
        for line in block.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                try:
                    metrics[key] = float(val)
                except ValueError:
                    pass

    return metrics


# ── Resume phase detection ────────────────────────────────────────────

_RUN_SENTINEL_RE = re.compile(r"^(RUN_COMPLETE|RUN_FAILED):", re.MULTILINE)


def determine_resume_phase(campaign_dir: Path, state: dict[str, Any]) -> str:
    """Determine which phase to resume from after a crash.

    Returns one of: "historian", "next_round", "reviewer", "executor", "planner"
    """
    current_round = int(state.get("round", 0))
    s = campaign_dir / "state"

    # Case A: Journal has entry for current round → reviewer done
    journal = s / "CAMPAIGN_JOURNAL.md"
    if journal.exists():
        journal_text = journal.read_text(encoding="utf-8")
        if f"## Round {current_round}" in journal_text:
            if state.get("historian_trigger_pending", False):
                return "historian"
            return "next_round"

    # Case B: run.log exists with sentinel but no journal entry → reviewer
    run_log = campaign_dir / "run.log"
    if run_log.exists():
        log_text = run_log.read_text(encoding="utf-8")
        if _RUN_SENTINEL_RE.search(log_text):
            return "reviewer"

    # Case C: NEXT_EXPERIMENT.md has round matching current → executor
    next_exp = s / "NEXT_EXPERIMENT.md"
    if next_exp.exists():
        try:
            from runner.tools._common import parse_frontmatter

            fm, _ = parse_frontmatter(next_exp)
            if int(fm.get("round", -1)) == current_round:
                return "executor"
        except Exception:
            pass

    # Case D: nothing present → planner
    return "planner"


# ── Round digest formatting ──────────────────────────────────────────

def format_round_digest(
    round_num: int,
    verdict: str,
    action_type: str,
    hypothesis: str,
    primary_metric_value: float | None,
    primary_metric_name: str = "val_pr_auc",
) -> str:
    """Format a compact 1-line digest for the orchestrator's running summary."""
    metric_str = f"{primary_metric_value:.4f}" if primary_metric_value is not None else "N/A"
    return (
        f"Round {round_num}: {verdict} | {action_type} | "
        f"{hypothesis[:60]} | {primary_metric_name}={metric_str}"
    )


# ── Tools-ran inference ──────────────────────────────────────────────

_TOOL_KEYWORDS: dict[str, str] = {
    "anomaly": "runner.tools.anomaly",
    "bootstrap_ci": "runner.tools.bootstrap_ci",
    "bootstrap": "runner.tools.bootstrap_ci",
    "confusion": "runner.tools.confusion_matrix",
    "calibration": "runner.tools.calibration",
    "feature_importance": "runner.tools.feature_importance",
    "lift": "runner.tools.lift_curve",
    "error_analysis": "runner.tools.error_analysis",
}


def infer_tools_ran(text: str) -> list[str]:
    """Infer which runner tools the Reviewer ran from its response text."""
    found: list[str] = []
    text_lower = text.lower()
    for keyword, tool_name in _TOOL_KEYWORDS.items():
        if keyword in text_lower and tool_name not in found:
            found.append(tool_name)
    return found


# ── Train.py duplicate detection ─────────────────────────────────────

def train_py_sha256(campaign_dir: Path) -> str:
    """Return SHA-256 of train.py for duplicate detection."""
    train_py = campaign_dir / "train.py"
    if not train_py.exists():
        return ""
    return hashlib.sha256(train_py.read_bytes()).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator_helpers.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All tests pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add runner/orchestrator.py tests/test_orchestrator_helpers.py
git commit -m "feat(orchestrator): helper functions — stuck detection, metrics parsing, resume phase"
```

---

## Task 3: Add `run_round.sh` Stages for Orchestrator Helpers

**Files:**
- Modify: `runner/run_round.sh`

- [ ] **Step 1: Add `campaign-status`, `stuck-check`, and `resume-phase` stages**

Add the following cases inside the Python block in `runner/run_round.sh`, before the final `else` clause:

```python
elif stage == "campaign-status":
    res = runner_driver.get_campaign_status(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res, indent=2))
elif stage == "stuck-check":
    from runner.orchestrator import detect_stuck
    from pathlib import Path
    warnings = detect_stuck(Path(args.get("campaign_dir", "runner/")))
    print(json.dumps({"warnings": warnings}))
elif stage == "resume-phase":
    from runner.orchestrator import determine_resume_phase
    from pathlib import Path
    camp = Path(args.get("campaign_dir", "runner/"))
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(open(state_path).read()) if state_path.exists() else {"round": 0}
    phase = determine_resume_phase(camp, state)
    print(json.dumps({"phase": phase}))
```

- [ ] **Step 2: Verify stages work**

Run: `bash runner/run_round.sh campaign-status --campaign_dir campaigns/smoke-test-creditcard 2>/dev/null || echo "Expected: JSON output or error if not initialized"`

- [ ] **Step 3: Commit**

```bash
git add runner/run_round.sh
git commit -m "feat(run_round): add campaign-status, stuck-check, resume-phase CLI stages"
```

---

## Task 4: The Orchestrator Prompt — Core Loop Structure

This is the central deliverable. The orchestrator prompt instructs a Claude Code agent to autonomously run multi-round experiment campaigns.

**Files:**
- Create: `runner/roles/orchestrator.md`

- [ ] **Step 1: Create the orchestrator prompt**

Create `runner/roles/orchestrator.md`:

```markdown
# Orchestrator — Autonomous Campaign Loop

> You are the Orchestrator for an autonomous ML experiment campaign.
> You drive the Plan → Execute → Review → (Historian) loop by switching
> between roles each phase, calling the driver for validation, and
> managing the campaign lifecycle.

## 0. Critical Rules — Read Before Anything Else

1. **NEVER rely on your memory of previous rounds.** Always re-read state from disk.
   Every round starts fresh: read `state/CAMPAIGN_STATE.json`, `state/results.tsv`,
   and the relevant state files. Your memory WILL degrade over rounds — the disk is truth.

2. **You are a dispatcher, not a decision-maker.** The Planner decides what to try.
   The Executor writes code. The Reviewer decides keep/discard. The Historian synthesizes.
   You coordinate and validate.

3. **The driver is your external brain.** Call `runner/run_round.sh` for all state
   transitions. Read its JSON output. Do not compute budget, round numbers, or
   historian triggers yourself — the driver does that.

4. **One role at a time.** Complete each role's full procedure before moving to the next.
   Do not interleave roles.

5. **Context hygiene after every role:** After completing a role's work, write one
   sentence summarizing what happened, then move on. Do NOT carry detailed analysis
   or experiment content between roles — it is on disk for the next role to read.

## 1. Startup Protocol

When you begin, determine the campaign directory. Look for one of:
- An explicit instruction like "run campaign at campaigns/<name>"
- The current working directory if it contains `contracts/` and `state/`
- Ask the user if ambiguous

Then:

```bash
# Step 1: Check if campaign is initialized
python runner/run_round.sh campaign-status --campaign_dir <CAMPAIGN_DIR>
```

Read the JSON output. If `status == "uninitialized"`:
```bash
python runner/run_round.sh init --campaign_dir <CAMPAIGN_DIR>
```

If `--resume` was requested:
```bash
python runner/run_round.sh resume-phase --campaign_dir <CAMPAIGN_DIR>
```
Read `phase` from the JSON output and skip to that phase.

Otherwise, proceed to the **Round Loop** starting with the Historian check.

## 2. Round Loop

Repeat this loop until a stop condition is met:

### 2.0 — Read Campaign Status (EVERY round — mandatory)

```bash
python runner/run_round.sh campaign-status --campaign_dir <CAMPAIGN_DIR>
```

Read and display: round number, budget used/total, best metric, last verdict.
If `budget_used >= budget_total`: STOP — budget exhausted.

### 2.1 — Historian Check

```bash
python runner/run_round.sh campaign-status --campaign_dir <CAMPAIGN_DIR>
```

If `historian_trigger_pending` is `true`:

1. Read `runner/roles/historian.md` — follow its FULL procedure (§1–§10)
2. Read all Historian §2 Inputs from disk
3. Perform the Historian's work: trajectory analysis, pattern extraction,
   assumption audit, bottleneck diagnosis
4. Write `state/STRATEGY_MEMO.md` and update `state/PATTERN_BOOK.md`
   and `state/ASSUMPTION_REGISTER.md` per the Historian's procedure
5. Emit `HISTORIAN_COMPLETE: round <N>, trigger <T>, patterns_added <P>, assumptions_flagged <A>, tokens_used 0`
6. Call the driver to finalize:
```bash
python runner/run_round.sh historian-finalize \
    --campaign_dir <CAMPAIGN_DIR> \
    --trigger <trigger> \
    --patterns_added <P> \
    --assumptions_flagged <A> \
    --tokens_used 0
```
7. **Context hygiene:** Write one sentence: "Historian done: wrote STRATEGY_MEMO.md,
   added P patterns, flagged A assumptions." Then continue to Planner.

### 2.2 — Planner Phase

1. Check for stuck patterns:
```bash
python runner/run_round.sh stuck-check --campaign_dir <CAMPAIGN_DIR>
```
If warnings are returned, note them — you MUST include them when planning.

2. Read `runner/roles/planner.md` — follow its FULL procedure (§1–§12)
3. Read all Planner §2 Inputs from disk (ALL of them — contracts, state, patterns)
4. If stuck warnings exist, prepend them to your planning context:
   "⚠ STUCK: <warning text>. You MUST address this in your plan."
5. Perform the Planner's work: summarize, query history, dead-ends check,
   assumption-aware novelty, pattern-informed strategy, UCB1 selection,
   write `state/NEXT_EXPERIMENT.md`
6. Call the driver to validate:
```bash
python runner/run_round.sh plan-check --campaign_dir <CAMPAIGN_DIR>
```
7. Read the JSON output:
   - `status == "ok"` → proceed to Executor
   - `status == "malformed"` → re-read errors, fix NEXT_EXPERIMENT.md, re-check (max 2 retries)
   - `status == "pause_c2"` → print "C2 plateau — Historian will run next round" and loop back to §2.0
   - `status == "pause_c3"` → print "C3 contract change requested — human review required" and STOP

8. Record train.py SHA before Executor runs:
```bash
python -c "from runner.orchestrator import train_py_sha256; from pathlib import Path; print(train_py_sha256(Path('<CAMPAIGN_DIR>')))"
```

9. **Context hygiene:** Write one sentence: "Plan written: <action_type> — <hypothesis>."

### 2.3 — Executor Phase

1. Read `runner/roles/executor.md` — follow its FULL procedure (§1–§5)
2. Read all Executor §2 Inputs from disk
3. Perform the Executor's work: implement the plan in `train.py`, git commit,
   run `python3 <CAMPAIGN_DIR>/train.py > <CAMPAIGN_DIR>/run.log 2>&1`
4. If crash: retry ONCE with minimal fix. If second crash: emit `RUN_FAILED`.
5. Emit `RUN_COMPLETE: <commit_sha>` or `RUN_FAILED: <commit_sha> <reason>`

6. Save executor output to a temp file and call the driver:
```bash
# Write your sentinel line to a file
echo "RUN_COMPLETE: <sha>" > /tmp/executor_stdout.txt
# Get diff files
DIFF_FILES=$(git diff --name-only <sha>^ <sha> 2>/dev/null | python -c "import sys,json; print(json.dumps(sys.stdin.read().strip().split('\n')))")
python runner/run_round.sh execute-finalize \
    --campaign_dir <CAMPAIGN_DIR> \
    --stdout_file /tmp/executor_stdout.txt \
    --commit_diff_files "$DIFF_FILES"
```

7. Read the JSON output:
   - If `synthetic_verdict` is `"malformed"` (write scope violation): note it, proceed to Reviewer
     phase which will handle the rollback
   - If `synthetic_verdict` is `"crash"`: proceed to Reviewer phase

8. Check for duplicate train.py:
```bash
python -c "from runner.orchestrator import train_py_sha256; from pathlib import Path; print(train_py_sha256(Path('<CAMPAIGN_DIR>')))"
```
If SHA matches the pre-executor SHA: this is a no-op. The verdict will be treated as `crash`.

9. **Context hygiene:** Write one sentence: "Executor done: <RUN_COMPLETE|RUN_FAILED> <sha>."

### 2.4 — Reviewer Phase

1. Read `runner/roles/reviewer.md` — follow its FULL procedure (§1–§18)
2. Read all Reviewer §2 Inputs from disk — Phase 1 inputs FIRST, then Phase 2
3. Perform the Reviewer's work: independent assessment, plan comparison,
   verdict, state updates (REVIEW.md, CAMPAIGN_JOURNAL.md, DEAD_ENDS.md,
   ASSUMPTION_REGISTER.md, NOTEBOOK.md)
4. Emit `VERDICT: <keep|discard|anomaly|crash|malformed> <commit>`

5. Parse metrics from run.log:
```bash
python -c "
from runner.orchestrator import parse_metrics_from_log, infer_tools_ran
from pathlib import Path
import json
metrics = parse_metrics_from_log(Path('<CAMPAIGN_DIR>/run.log'))
print('METRICS:', json.dumps(metrics))
"
```

6. Call the driver to finalize:
```bash
python runner/run_round.sh review-finalize \
    --campaign_dir <CAMPAIGN_DIR> \
    --verdict <verdict> \
    --commit <commit> \
    --metrics_json '<json>' \
    --action_type <action_type> \
    --hypothesis "<hypothesis>" \
    --description "<description>" \
    --model_family "<model_family>" \
    --n_features <n> \
    --tools_ran '<json array>'
```

7. Read the JSON output:
   - `should_rollback == true`: run `git reset --hard HEAD~1` from the repo root
   - `halt_loop == true`: print halt reason and STOP
   - `pause_loop == true`: print "Anomaly (C1) — human review required at state/REVIEW.md" and STOP

8. **Context hygiene:** Write one sentence: "Review done: <verdict>. Best so far: <metric>."

### 2.5 — Round Checkpoint (mandatory — context rot mitigation)

After completing all phases for a round:

1. Re-read `state/CAMPAIGN_STATE.json` for the updated round number and best metric.

2. Print a checkpoint summary:
```
═══ ROUND <N> COMPLETE ═══
Verdict: <keep|discard|...>
Action: <action_type> — <hypothesis>
Primary metric: <value>
Best so far: <best_metric> (commit <best_commit>)
Budget: <used>/<total>
Historian pending: <yes|no>
══════════════════════════
```

3. Continue to §2.0 for the next round.

## 3. Stop Conditions

Stop the loop when ANY of these is true:
- `budget_used >= budget_total` (from campaign-status)
- `halt_loop == true` (from review-finalize)
- `pause_loop == true` (anomaly — C1)
- `pause_c2` or `pause_c3` (from plan-check)
- Two consecutive `malformed` verdicts (driver sets `halt_loop`)

When stopping:

1. Print final status:
```
═══ CAMPAIGN COMPLETE ═══
Rounds completed: <N>
Best metric: <value> (commit <sha>)
Last verdict: <verdict>
Reason: <budget_exhausted|halt|anomaly|...>
═════════════════════════
```

2. Read and display a summary of `state/results.tsv` (top 3 by primary metric).

## 4. Error Recovery

If any bash command fails unexpectedly:
1. Print the error
2. Read `state/CAMPAIGN_STATE.json` to determine current state
3. Run `python runner/run_round.sh resume-phase --campaign_dir <CAMPAIGN_DIR>`
4. Resume from the indicated phase

If the agent session itself is interrupted (context limit, crash):
- The human restarts with: "Resume the campaign at <CAMPAIGN_DIR> with --resume"
- The orchestrator runs the resume-phase detection and picks up where it left off

## 5. How to Invoke This Orchestrator

### Interactive (recommended for first use):
Open Claude Code in the repo root. Say:
```
Read runner/roles/orchestrator.md and run the campaign at campaigns/<name>
```

### Headless (for autonomous operation):
```bash
claude -p "Read runner/roles/orchestrator.md and run the campaign at campaigns/<name>. \
Do not ask for confirmation — run autonomously until a stop condition." \
--dangerously-skip-permissions
```

### Resume after interruption:
```
Read runner/roles/orchestrator.md and resume the campaign at campaigns/<name> with --resume
```
```

- [ ] **Step 2: Verify the prompt file is well-formed**

Run: `wc -l runner/roles/orchestrator.md`
Expected: ~200 lines (non-trivial prompt)

Run: `head -5 runner/roles/orchestrator.md`
Expected: Shows the title and opening blockquote

- [ ] **Step 3: Commit**

```bash
git add runner/roles/orchestrator.md
git commit -m "feat(orchestrator): prompt-level harness for autonomous campaign loop"
```

---

## Task 5: Update RUNNER.md to Reference the Orchestrator

**Files:**
- Modify: `runner/RUNNER.md`

- [ ] **Step 1: Add orchestrator section to RUNNER.md**

Add the following after the "## 1. Your role for this turn" section (before "## 2. Hard invariants"):

```markdown
## 1b. Autonomous operation (orchestrator loop)

For fully autonomous multi-round operation, read `runner/roles/orchestrator.md` instead
of picking a single role. The orchestrator drives the full Plan → Execute → Review →
Historian cycle, calling the driver between phases for validation.

**Interactive:** "Read runner/roles/orchestrator.md and run the campaign at campaigns/<name>"

**Headless:** `claude -p "Read runner/roles/orchestrator.md and run campaigns/<name>" --dangerously-skip-permissions`

**Resume:** "Read runner/roles/orchestrator.md and resume campaigns/<name> with --resume"
```

- [ ] **Step 2: Commit**

```bash
git add runner/RUNNER.md
git commit -m "docs(RUNNER): add orchestrator reference for autonomous operation"
```

---

## Task 6: Update Campaign Template README

**Files:**
- Modify: `runner/campaign_template/README.md`

- [ ] **Step 1: Add autonomous operation instructions to the template**

Add after the existing "## Running" section:

```markdown
## Autonomous Operation

Once contracts are signed (G1/G2/G3 — `approved_at` is non-null in each):

```bash
# Interactive — observe and intervene
# Open Claude Code in repo root, then say:
# "Read runner/roles/orchestrator.md and run the campaign at campaigns/<your-name>"

# Headless — fully autonomous
claude -p "Read runner/roles/orchestrator.md and run the campaign at campaigns/<your-name>. Run autonomously until a stop condition." --dangerously-skip-permissions

# Resume after interruption
# "Read runner/roles/orchestrator.md and resume campaigns/<your-name> with --resume"
```

The orchestrator reads all role prompts, executes each phase, calls the driver for
validation between phases, and manages halt/pause/budget conditions automatically.
```

- [ ] **Step 2: Commit**

```bash
git add runner/campaign_template/README.md
git commit -m "docs(template): add autonomous operation instructions"
```

---

## Task 7: Integration Test — Driver Stages Chain Correctly via CLI

**Files:**
- Create: `tests/integration/test_orchestrator_prompt.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_orchestrator_prompt.py`:

```python
"""Integration tests validating that the orchestrator's CLI stage calls
chain correctly with runner_driver. These test the bash-invocable pipeline
the orchestrator prompt uses — no LLM calls."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from runner import runner_driver
from runner.orchestrator import (
    detect_stuck,
    determine_resume_phase,
    format_round_digest,
    infer_tools_ran,
    parse_metrics_from_log,
)
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "campaign"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    (root / "train.py").write_text("# placeholder\n")
    return root


VALID_NEXT_EXPERIMENT = """---
schema_version: 1
campaign_id: "tiny"
round: 1
planner_invocation_at: "2026-05-25T00:00:00Z"
action_type: "A_hp"
hypothesis: "tune learning rate"
expected_effect_size: 0.01
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary
First round.
## 2. Evidence from memory
None yet.
## 3. Plan
1. Set lr=0.01.
## 4. Helpers
None.
## 5. How this differs from prior experiments
First experiment.
## 6. Escalation (only if `escalation` frontmatter is non-null)
N/A.
"""


def test_full_round_driver_chain(campaign: Path):
    """Simulate what the orchestrator does in one round:
    init → plan_check → execute_finalize → review_finalize.
    No LLM calls — just verify the driver chain works."""
    # Init
    state = runner_driver.init_campaign(campaign_dir=str(campaign))
    assert state["round"] == 0

    # Status check
    status = runner_driver.get_campaign_status(campaign_dir=str(campaign))
    assert status["next_role"] == "planner"
    assert status["budget_total"] == 3

    # Historian check
    assert runner_driver.should_run_historian(campaign_dir=str(campaign)) is False

    # Stuck check
    assert detect_stuck(campaign) == []

    # Planner writes plan
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(VALID_NEXT_EXPERIMENT)
    check = runner_driver.plan_check(campaign_dir=str(campaign))
    assert check["status"] == "ok"

    # Executor runs
    exec_result = runner_driver.execute_finalize(
        executor_stdout="RUN_COMPLETE: abc123\n",
        campaign_dir=str(campaign),
    )
    assert exec_result["channel"] == "RUN_COMPLETE"

    # Reviewer finalizes
    metrics = {"val_pr_auc": 0.75, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.6}
    review_result = runner_driver.review_finalize(
        verdict="keep",
        commit="abc123",
        metrics=metrics,
        action_type="A_hp",
        hypothesis="tune learning rate",
        description="round 1",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        tools_ran=["tools/anomaly.py"],
    )
    assert review_result["halt_loop"] is False
    assert review_result["should_rollback"] is False

    # Verify state advanced
    final_status = runner_driver.get_campaign_status(campaign_dir=str(campaign))
    assert final_status["round"] == 1
    assert final_status["best_metric"] == pytest.approx(0.75)

    # Round digest
    digest = format_round_digest(
        round_num=1,
        verdict="keep",
        action_type="A_hp",
        hypothesis="tune learning rate",
        primary_metric_value=0.75,
    )
    assert "Round 1" in digest
    assert "keep" in digest


def test_stuck_detection_feeds_into_planning(campaign: Path):
    """Verify stuck detection works on realistic results.tsv data."""
    runner_driver.init_campaign(campaign_dir=str(campaign))

    results_path = campaign / "state" / "results.tsv"
    header = results_path.read_text().splitlines()[0]
    col_names = header.split("\t")
    at_idx = col_names.index("action_type")
    n_cols = len(col_names)

    rows = []
    for i in range(4):
        row = [""] * n_cols
        row[0] = f"c{i}"
        row[at_idx] = "A_hp"
        rows.append("\t".join(row))
    results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

    warnings = detect_stuck(campaign)
    assert len(warnings) >= 1
    assert any("A_hp" in w for w in warnings)


def test_resume_phase_detection(campaign: Path):
    """Verify crash recovery works for all 4 phases."""
    runner_driver.init_campaign(campaign_dir=str(campaign))

    state = json.loads(
        (campaign / "state" / "CAMPAIGN_STATE.json").read_text()
    )
    state["round"] = 3

    # No artifacts → planner
    assert determine_resume_phase(campaign, state) == "planner"

    # Plan exists → executor
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(
        VALID_NEXT_EXPERIMENT.replace("round: 1", "round: 3")
    )
    assert determine_resume_phase(campaign, state) == "executor"

    # run.log with sentinel → reviewer
    (campaign / "run.log").write_text("RUN_COMPLETE: abc\n")
    assert determine_resume_phase(campaign, state) == "reviewer"

    # Journal entry → next_round or historian
    (campaign / "state" / "CAMPAIGN_JOURNAL.md").write_text("## Round 3\nDone.\n")
    state["historian_trigger_pending"] = False
    assert determine_resume_phase(campaign, state) == "next_round"

    state["historian_trigger_pending"] = True
    assert determine_resume_phase(campaign, state) == "historian"


def test_metrics_parsing_and_tools_inference():
    """Verify the helpers the orchestrator calls via python -c."""
    tools = infer_tools_ran("Ran anomaly check and bootstrap_ci. Both passed.")
    assert "runner.tools.anomaly" in tools
    assert "runner.tools.bootstrap_ci" in tools
```

- [ ] **Step 2: Run the integration tests**

Run: `python -m pytest tests/integration/test_orchestrator_prompt.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_orchestrator_prompt.py
git commit -m "test(orchestrator): integration tests for driver chain and helpers"
```

---

## Task 8: Final Validation and Documentation Commit

**Files:**
- None modified — validation only

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All existing tests + new tests pass (no regressions)

- [ ] **Step 2: Verify orchestrator prompt is readable**

Run: `cat runner/roles/orchestrator.md | head -20`
Expected: Shows title and critical rules

- [ ] **Step 3: Verify helper module imports cleanly**

Run: `python -c "from runner.orchestrator import detect_stuck, determine_resume_phase, parse_metrics_from_log, format_round_digest, infer_tools_ran, train_py_sha256; print('All helpers OK')"`
Expected: `All helpers OK`

- [ ] **Step 4: Verify driver helpers work**

Run: `python -c "from runner.runner_driver import get_campaign_status, should_run_historian; print('Driver helpers OK')"`
Expected: `Driver helpers OK`

- [ ] **Step 5: Verify CLI stages**

Run: `python runner/run_round.sh campaign-status --campaign_dir campaigns/smoke-test-creditcard 2>&1 | head -5`
Expected: JSON output (either status dict or error about missing state)

- [ ] **Step 6: Final commit**

```bash
git add -A
git status
git commit -m "feat(orchestrator): v1 prompt-level harness for autonomous ML campaigns

Implements the missing external loop as a prompt-level harness:

runner/roles/orchestrator.md:
  - Autonomous campaign loop (Plan → Execute → Review → Historian)
  - Context-rot mitigation via disk-first reads + round checkpoints
  - Crash recovery with resume-phase detection
  - Stuck detection warnings injected into Planner context
  - Stop conditions: budget, halt, anomaly, C2/C3 pauses

runner/orchestrator.py:
  - detect_stuck(): repetitive action_type detection
  - parse_metrics_from_log(): val_* line and --- block parsing
  - determine_resume_phase(): crash recovery phase detection
  - format_round_digest(): compact round summary
  - infer_tools_ran(): keyword-based tool inference
  - train_py_sha256(): duplicate experiment detection

runner/runner_driver.py (additive):
  - get_campaign_status(): compact status dict for orchestrator
  - should_run_historian(): trigger check

Tests: 14 unit + 4 integration tests, all passing"
```

---

## Implementation Notes

### What this plan builds (v1):
- A prompt (`orchestrator.md`) that a Claude Code agent follows to autonomously run experiment campaigns
- Python helpers (`orchestrator.py`) called by the agent via bash for deterministic computations
- Driver helpers (`get_campaign_status`, `should_run_historian`) for the agent to query state
- CLI stages in `run_round.sh` for bash-accessible helper invocation
- Full test coverage for all Python code

### What this plan does NOT build (deferred to v2):
- Anthropic SDK-based orchestrator with programmatic tool-use loop
- Real-time write-scope interception (relies on post-hoc `execute_finalize` check)
- Exact token tracking (relies on existing `_auto_estimate_round_tokens`)
- Per-role model tiering (all roles use session's model)
- Knowledge extraction pipeline (Layer 3)

### Context rot mitigation summary:
| Mitigation | Where | Mechanism |
|---|---|---|
| Disk-first reads | `orchestrator.md` §0 Rule 1 | Every role re-reads all inputs from disk |
| Context hygiene | `orchestrator.md` §2.x Step 7/9 | 1-sentence summary between roles |
| Round checkpoints | `orchestrator.md` §2.5 | Structured checkpoint replaces detail |
| Driver as external brain | `orchestrator.md` §0 Rule 3 | Complex state logic computed by Python, not agent |
| No memory reliance | `orchestrator.md` §0 Rule 1 | Explicit prohibition on recalled content |
