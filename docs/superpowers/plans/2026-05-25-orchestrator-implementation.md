# Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `runner/orchestrator.py` — the outer ReAct while-loop that dispatches LLM agents (via Anthropic SDK) per role per experiment round, plus integration tests.

**Architecture:** Classical tool-use loop using `anthropic.Anthropic().messages.create()` with `read_file`, `write_file`, `run_bash` tools. Each role gets its `.md` prompt as system message and §2 inputs injected as user message. The orchestrator is a thin dispatcher — zero decision logic; intelligence stays in role prompts. State flows through `CAMPAIGN_STATE.json` and disk artifacts managed by `runner_driver.py`.

**Tech Stack:** Python 3.10+, `anthropic` SDK (already installed), `runner_driver.py` state machine (read-only), `pytest` with mock.

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `runner/orchestrator.py` | Main CLI entry point + ReAct loop: context assembly, LLM dispatch, sentinel parsing, driver integration, stuck detection, crash recovery |
| **Create:** `tests/integration/test_orchestrator.py` | 5 integration tests with mocked Anthropic client: planner, historian, stuck detection, crash recovery, tools_ran inference |

Both files are self-contained. `orchestrator.py` depends on `runner_driver` and `anthropic`; the test file depends on both plus test fixtures from `tests/test_runner_driver.py`.

---

## Task 1: Orchestrator — Constants, Tool Definitions, Sentinel Regexes

**Files:**
- Create: `runner/orchestrator.py`

- [ ] **Step 1: Create `runner/orchestrator.py` with imports, constants, tool definitions, and sentinel regexes**

```python
"""runner/orchestrator.py — Outer ReAct loop dispatching LLM agents per role.

Usage:
    python runner/orchestrator.py --campaign-dir campaigns/<name>
    python runner/orchestrator.py --campaign-dir campaigns/<name> --resume
    python runner/orchestrator.py --campaign-dir campaigns/<name> --max-rounds 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import anthropic

from runner import runner_driver

# ── Repo root (parent of runner/) ──────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Model tiering ──────────────────────────────────────────────────────
MODEL_PLANNER = "claude-opus-4-6"
MODEL_EXECUTOR = "claude-sonnet-4-6"
MODEL_REVIEWER = "claude-opus-4-6"
MODEL_HISTORIAN = "claude-opus-4-6"

# ── Safety caps ────────────────────────────────────────────────────────
MAX_TOOL_CALLS_PER_ROLE = 60
BASH_TIMEOUT_S = 600

# ── Tool definitions ──────────────────────────────────────────────────
READ_FILE_TOOL = {
    "name": "read_file",
    "description": "Read a file. Path relative to repo root or absolute.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer"},
        },
        "required": ["path"],
    },
}

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write content to a file. Creates parent dirs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
}

RUN_BASH_TOOL = {
    "name": "run_bash",
    "description": "Run a bash command from repo root. Returns stdout+stderr. Timeout: 600s.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
        },
        "required": ["command"],
    },
}

TOOLS = [READ_FILE_TOOL, WRITE_FILE_TOOL, RUN_BASH_TOOL]

# ── Sentinel regexes ──────────────────────────────────────────────────
RUN_COMPLETE_RE = re.compile(r"RUN_COMPLETE:\s*(\S+)")
RUN_FAILED_RE = re.compile(r"RUN_FAILED:\s*(\S+)(?:\s+(.+))?")
REVIEW_REQUIRED_RE = re.compile(r"REVIEW_REQUIRED:\s*(.+)")
VERDICT_RE = re.compile(
    r"VERDICT:\s*(keep|discard|anomaly|crash|malformed)\s+(\S+)", re.I
)
HISTORIAN_RE = re.compile(
    r"HISTORIAN_COMPLETE:\s*round\s+(\d+),\s*trigger\s+(\S+),\s*"
    r"patterns_added\s+(\d+),\s*assumptions_flagged\s+(\d+),\s*tokens_used\s+(\d+)",
    re.I,
)
```

- [ ] **Step 2: Verify file parses**

Run: `python -c "import runner.orchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): scaffold with constants, tools, sentinel regexes"
```

---

## Task 2: Tool Execution Handlers with Write-Scope Enforcement

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add tool execution helpers**

Append to `runner/orchestrator.py`:

```python
# ── Write-scope enforcement ───────────────────────────────────────────

def _resolve_path(path_str: str) -> Path:
    """Resolve a path relative to REPO_ROOT, or use as absolute."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return REPO_ROOT / p


def _check_write_scope(path_str: str, role: str, campaign_dir: Path) -> str | None:
    """Return an error string if the write is blocked, else None."""
    resolved = _resolve_path(path_str)
    try:
        rel = resolved.relative_to(REPO_ROOT)
    except ValueError:
        return f"[BLOCKED] write_scope_violation: {path_str} (outside repo)"
    rel_str = str(rel)
    camp_rel = str(campaign_dir.relative_to(REPO_ROOT))

    if role == "executor":
        # Executor may only write train.py (in campaign dir) and experiment_helpers
        allowed_prefixes = [
            f"{camp_rel}/train.py",
            "runner/experiment_helpers/",
        ]
        if any(rel_str == p or rel_str.startswith(p) for p in allowed_prefixes):
            return None
        # Also allow exact match on just "train.py" resolved to campaign dir
        if rel_str == "train.py" or resolved == campaign_dir / "train.py":
            return None
        return f"[BLOCKED] write_scope_violation: {rel_str}"
    else:
        # All other roles: allow writes under <campaign_dir>/state/ and run.log
        allowed_prefixes = [
            f"{camp_rel}/state/",
            f"{camp_rel}/run.log",
        ]
        blocked_prefixes = [
            f"{camp_rel}/contracts/",
            "runner/roles/",
            "runner/tools/",
            f"{camp_rel}/prepare.py",
            "log.py",
        ]
        if any(rel_str == p or rel_str.startswith(p) for p in blocked_prefixes):
            return f"[BLOCKED] write_scope_violation: {rel_str}"
        if any(rel_str == p or rel_str.startswith(p) for p in allowed_prefixes):
            return None
        return f"[BLOCKED] write_scope_violation: {rel_str}"


def _handle_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    role: str,
    campaign_dir: Path,
) -> str:
    """Execute a tool call and return its text result."""
    if tool_name == "read_file":
        path = _resolve_path(tool_input["path"])
        max_chars = tool_input.get("max_chars")
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if max_chars and len(content) > max_chars:
                content = content[:max_chars] + f"\n... [truncated at {max_chars} chars]"
            return content
        except FileNotFoundError:
            return f"[ERROR] File not found: {tool_input['path']}"
        except Exception as e:
            return f"[ERROR] reading {tool_input['path']}: {e}"

    elif tool_name == "write_file":
        path_str = tool_input["path"]
        block_msg = _check_write_scope(path_str, role, campaign_dir)
        if block_msg:
            return block_msg
        path = _resolve_path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tool_input["content"], encoding="utf-8")
        return f"OK: wrote {len(tool_input['content'])} chars to {path_str}"

    elif tool_name == "run_bash":
        command = tool_input["command"]
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=BASH_TIMEOUT_S,
            )
            output = result.stdout + result.stderr
            if len(output) > 50_000:
                output = output[:50_000] + "\n... [truncated at 50000 chars]"
            return output if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            return f"[ERROR] Command timed out after {BASH_TIMEOUT_S}s"
        except Exception as e:
            return f"[ERROR] running command: {e}"

    return f"[ERROR] Unknown tool: {tool_name}"
```

- [ ] **Step 2: Verify file parses**

Run: `python -c "import runner.orchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): tool execution handlers with write-scope enforcement"
```

---

## Task 3: LLM Invocation Loop (ReAct)

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add the core LLM invocation function**

Append to `runner/orchestrator.py`:

```python
# ── LLM invocation ────────────────────────────────────────────────────

def _invoke_role(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    user_message: str,
    role: str,
    campaign_dir: Path,
) -> tuple[str, int]:
    """Run a tool-use ReAct loop for one role. Returns (accumulated_text, tokens_used)."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    accumulated_text = ""
    total_input_tokens = 0
    total_output_tokens = 0

    for _ in range(MAX_TOOL_CALLS_PER_ROLE):
        response = client.messages.create(
            model=model,
            max_tokens=16384,
            system=system_prompt,
            messages=messages,
            tools=TOOLS,
        )

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Collect text blocks from this response
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_parts:
            accumulated_text += "\n".join(text_parts) + "\n"

        if response.stop_reason == "end_turn":
            break

        if not tool_uses:
            break

        # Build assistant message with all content blocks
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and build tool_result messages
        tool_results = []
        for tool_use in tool_uses:
            result_text = _handle_tool(
                tool_use.name,
                tool_use.input,
                role=role,
                campaign_dir=campaign_dir,
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})

    tokens_used = total_input_tokens + total_output_tokens
    return accumulated_text, tokens_used
```

- [ ] **Step 2: Verify file parses**

Run: `python -c "import runner.orchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): core LLM invocation ReAct loop"
```

---

## Task 4: Context Assembly Functions (Per-Role)

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add helper to read a file safely**

Append to `runner/orchestrator.py`:

```python
# ── Context assembly helpers ──────────────────────────────────────────

def _safe_read(path: Path, label: str | None = None, tail_lines: int | None = None) -> str:
    """Read a file, returning empty string if missing. Optionally tail."""
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if tail_lines is not None:
            lines = content.splitlines()
            # Always keep header + last N data lines for TSV
            if len(lines) > tail_lines + 1:
                content = "\n".join([lines[0]] + lines[-(tail_lines):])
        if label:
            return f"\n### {label}\n```\n{content}\n```\n"
        return content
    except Exception:
        return ""
```

- [ ] **Step 2: Add per-role context builders**

Append to `runner/orchestrator.py`:

```python
def _build_planner_context(campaign_dir: Path, stuck_warnings: list[str]) -> str:
    """Assemble the user message for the Planner role."""
    s = campaign_dir / "state"
    c = campaign_dir / "contracts"

    parts = [
        "# Planner Context\n",
        _safe_read(REPO_ROOT / "runner" / "AGENTS.md", "runner/AGENTS.md"),
        _safe_read(c / "PROBLEM_CONTRACT.md", "contracts/PROBLEM_CONTRACT.md"),
        _safe_read(c / "DATA_CONTRACT.md", "contracts/DATA_CONTRACT.md"),
        _safe_read(c / "EVAL_PROTOCOL.md", "contracts/EVAL_PROTOCOL.md"),
        _safe_read(c / "STRATEGY_GUIDE.md", "contracts/STRATEGY_GUIDE.md"),
        _safe_read(c / "PRIORS.md", "contracts/PRIORS.md"),
        _safe_read(s / "CAMPAIGN_STATE.json", "state/CAMPAIGN_STATE.json"),
        _safe_read(s / "results.tsv", "state/results.tsv (last 10 rows)", tail_lines=10),
        _safe_read(s / "DEAD_ENDS.md", "state/DEAD_ENDS.md"),
        _safe_read(s / "UNEXPLORED_TECHNIQUES.md", "state/UNEXPLORED_TECHNIQUES.md"),
        _safe_read(s / "NOTEBOOK.md", "state/NOTEBOOK.md"),
        _safe_read(s / "REVIEW.md", "state/REVIEW.md"),
        _safe_read(s / "ASSUMPTION_REGISTER.md", "state/ASSUMPTION_REGISTER.md"),
        _safe_read(s / "PATTERN_BOOK.md", "state/PATTERN_BOOK.md"),
        _safe_read(s / "STRATEGY_MEMO.md", "state/STRATEGY_MEMO.md"),
        _safe_read(s / "EXPERIMENT_TREE.json", "state/EXPERIMENT_TREE.json"),
        _safe_read(s / "TOKEN_SUMMARY.txt", "state/TOKEN_SUMMARY.txt"),
    ]

    if stuck_warnings:
        parts.append("\n## ⚠ STUCK WARNINGS\n")
        for w in stuck_warnings:
            parts.append(f"- {w}\n")

    full_path = str(campaign_dir / "state" / "NEXT_EXPERIMENT.md")
    parts.append(
        f"\n## YOUR TASK\n"
        f"Write state/NEXT_EXPERIMENT.md using the write_file tool at the full path: "
        f"`{full_path}`\n"
    )

    return "\n".join(parts)


def _build_executor_context(campaign_dir: Path) -> str:
    """Assemble the user message for the Executor role."""
    s = campaign_dir / "state"
    c = campaign_dir / "contracts"
    train_py = campaign_dir / "train.py"

    parts = [
        "# Executor Context\n",
        _safe_read(REPO_ROOT / "runner" / "AGENTS.md", "runner/AGENTS.md"),
        _safe_read(c / "PROBLEM_CONTRACT.md", "contracts/PROBLEM_CONTRACT.md"),
        _safe_read(c / "DATA_CONTRACT.md", "contracts/DATA_CONTRACT.md"),
        _safe_read(c / "EVAL_PROTOCOL.md", "contracts/EVAL_PROTOCOL.md"),
        _safe_read(s / "NEXT_EXPERIMENT.md", "state/NEXT_EXPERIMENT.md"),
        _safe_read(s / "CAMPAIGN_STATE.json", "state/CAMPAIGN_STATE.json"),
        _safe_read(train_py, "train.py (current)"),
    ]

    full_train_path = str(train_py)
    parts.append(
        f"\n## YOUR TASK\n"
        f"1. Edit train.py at full path: `{full_train_path}`\n"
        f"2. Git commit your changes\n"
        f"3. Run: `python3 {campaign_dir}/train.py > {campaign_dir}/run.log 2>&1`\n"
        f"4. Emit `RUN_COMPLETE: <commit_sha>` as your final line\n"
        f"   If the run fails, emit `RUN_FAILED: <commit_sha> <reason>`\n"
    )

    return "\n".join(parts)


def _build_reviewer_context(campaign_dir: Path) -> str:
    """Assemble the user message for the Reviewer role."""
    s = campaign_dir / "state"
    c = campaign_dir / "contracts"

    parts = [
        "# Reviewer Context\n",
        _safe_read(REPO_ROOT / "runner" / "AGENTS.md", "runner/AGENTS.md"),
        _safe_read(c / "EVAL_PROTOCOL.md", "contracts/EVAL_PROTOCOL.md"),
        _safe_read(s / "CAMPAIGN_STATE.json", "state/CAMPAIGN_STATE.json"),
        _safe_read(campaign_dir / "run.log", "run.log"),
        _safe_read(s / "results.tsv", "state/results.tsv (last 5 rows)", tail_lines=5),
        _safe_read(s / "ASSUMPTION_REGISTER.md", "state/ASSUMPTION_REGISTER.md"),
        _safe_read(s / "DEAD_ENDS.md", "state/DEAD_ENDS.md"),
        _safe_read(s / "NEXT_EXPERIMENT.md", "state/NEXT_EXPERIMENT.md"),
    ]

    parts.append(
        f"\n## YOUR TASK\n"
        f"1. Run mandatory evaluation tools via run_bash\n"
        f"2. Write state files at full paths under: `{s}/`\n"
        f"3. Emit `VERDICT: <keep|discard|anomaly|crash|malformed> <commit>` as your final line\n"
    )

    return "\n".join(parts)


def _build_historian_context(campaign_dir: Path, trigger_meta: dict[str, Any]) -> str:
    """Assemble the user message for the Historian role."""
    s = campaign_dir / "state"
    c = campaign_dir / "contracts"

    parts = [
        "# Historian Context\n",
        _safe_read(REPO_ROOT / "runner" / "AGENTS.md", "runner/AGENTS.md"),
        _safe_read(c / "EVAL_PROTOCOL.md", "contracts/EVAL_PROTOCOL.md"),
        _safe_read(c / "STRATEGY_GUIDE.md", "contracts/STRATEGY_GUIDE.md"),
        _safe_read(s / "CAMPAIGN_STATE.json", "state/CAMPAIGN_STATE.json"),
        _safe_read(s / "CAMPAIGN_JOURNAL.md", "state/CAMPAIGN_JOURNAL.md"),
        _safe_read(s / "results.tsv", "state/results.tsv (all rows)"),
        _safe_read(s / "DEAD_ENDS.md", "state/DEAD_ENDS.md"),
        _safe_read(s / "NOTEBOOK.md", "state/NOTEBOOK.md"),
        _safe_read(s / "ASSUMPTION_REGISTER.md", "state/ASSUMPTION_REGISTER.md"),
        _safe_read(s / "PATTERN_BOOK.md", "state/PATTERN_BOOK.md"),
        _safe_read(s / "UNEXPLORED_TECHNIQUES.md", "state/UNEXPLORED_TECHNIQUES.md"),
    ]

    parts.append(
        f"\n## Trigger Metadata\n```json\n{json.dumps(trigger_meta, indent=2)}\n```\n"
    )

    memo_path = str(s / "STRATEGY_MEMO.md")
    pb_path = str(s / "PATTERN_BOOK.md")
    parts.append(
        f"\n## YOUR TASK\n"
        f"1. Write STRATEGY_MEMO.md at full path: `{memo_path}`\n"
        f"2. Write/update PATTERN_BOOK.md at full path: `{pb_path}`\n"
        f"3. Emit `HISTORIAN_COMPLETE: round N, trigger T, patterns_added P, "
        f"assumptions_flagged A, tokens_used T` as your final line\n"
    )

    return "\n".join(parts)
```

- [ ] **Step 3: Verify file parses**

Run: `python -c "import runner.orchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): per-role context assembly functions"
```

---

## Task 5: Stuck Detection

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add stuck detection function**

Append to `runner/orchestrator.py`:

```python
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

    warnings = []

    # Check: same action_type for last 3 consecutive rows
    if len(action_types) >= 3 and len(set(action_types[-3:])) == 1:
        warnings.append(
            f"STUCK WARNING: Last 3 experiments all used action_type='{action_types[-1]}'. "
            f"You MUST try a different action_type."
        )

    # Check: A-B-A-B alternation in last 4
    if len(action_types) >= 4:
        last4 = action_types[-4:]
        if last4[0] == last4[2] and last4[1] == last4[3] and last4[0] != last4[1]:
            warnings.append(
                f"STUCK WARNING: A-B-A-B alternation detected ({last4[0]}/{last4[1]}). "
                f"Break this pattern — try a completely different approach."
            )

    return warnings


def _train_py_sha256(campaign_dir: Path) -> str:
    """Return SHA-256 of train.py for duplicate detection."""
    train_py = campaign_dir / "train.py"
    if not train_py.exists():
        return ""
    return hashlib.sha256(train_py.read_bytes()).hexdigest()
```

- [ ] **Step 2: Verify**

Run: `python -c "from runner.orchestrator import detect_stuck; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): stuck detection and duplicate train.py check"
```

---

## Task 6: Crash Recovery (Resume Phase Detection)

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add resume phase determination**

Append to `runner/orchestrator.py`:

```python
# ── Crash recovery ────────────────────────────────────────────────────

def _determine_resume_phase(campaign_dir: Path, state: dict[str, Any]) -> str:
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

    # Case B: run.log exists with sentinel but no journal entry → go to reviewer
    run_log = campaign_dir / "run.log"
    if run_log.exists():
        log_text = run_log.read_text(encoding="utf-8")
        if RUN_COMPLETE_RE.search(log_text) or RUN_FAILED_RE.search(log_text):
            return "reviewer"

    # Case C: NEXT_EXPERIMENT.md has round: current_round but no run.log → executor
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
```

- [ ] **Step 2: Verify**

Run: `python -c "from runner.orchestrator import _determine_resume_phase; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): crash recovery resume phase detection"
```

---

## Task 7: Per-Role Phase Runners

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add metrics parsing helper**

Append to `runner/orchestrator.py`:

```python
# ── Metrics parsing ───────────────────────────────────────────────────

def _parse_metrics_from_log(campaign_dir: Path) -> dict[str, float]:
    """Parse val_<metric>: <float> lines and --- key-value blocks from run.log."""
    run_log = campaign_dir / "run.log"
    if not run_log.exists():
        return {}

    text = run_log.read_text(encoding="utf-8", errors="replace")
    metrics: dict[str, float] = {}

    # Parse val_<metric>: <float> lines
    for m in re.finditer(r"^(val_\w+):\s*([\d.eE+-]+)\s*$", text, re.MULTILINE):
        try:
            metrics[m.group(1)] = float(m.group(2))
        except ValueError:
            pass

    # Parse --- delimited key-value blocks
    for block_match in re.finditer(r"^---\s*\n(.*?)\n---\s*$", text, re.MULTILINE | re.DOTALL):
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
```

- [ ] **Step 2: Add tools_ran inference helper**

Append to `runner/orchestrator.py`:

```python
def _infer_tools_ran(accumulated_text: str) -> list[str]:
    """Infer which runner tools the Reviewer ran from its response text."""
    tool_keywords = {
        "anomaly": "runner.tools.anomaly",
        "bootstrap_ci": "runner.tools.bootstrap_ci",
        "bootstrap": "runner.tools.bootstrap_ci",
        "confusion": "runner.tools.confusion_matrix",
        "calibration": "runner.tools.calibration",
        "feature_importance": "runner.tools.feature_importance",
        "lift": "runner.tools.lift_curve",
    }
    found = []
    text_lower = accumulated_text.lower()
    for keyword, tool_name in tool_keywords.items():
        if keyword in text_lower and tool_name not in found:
            found.append(tool_name)
    return found
```

- [ ] **Step 3: Add phase runner functions**

Append to `runner/orchestrator.py`:

```python
# ── Phase runners ─────────────────────────────────────────────────────

def run_historian_phase(
    client: anthropic.Anthropic,
    campaign_dir: Path,
) -> dict[str, Any]:
    """Run the Historian role and finalize state."""
    print(f"[orchestrator] Running Historian phase...")
    trigger_meta = runner_driver.historian_run(campaign_dir=str(campaign_dir))

    system_prompt = (REPO_ROOT / "runner" / "roles" / "historian.md").read_text(encoding="utf-8")
    user_message = _build_historian_context(campaign_dir, trigger_meta)

    accumulated_text, tokens_used = _invoke_role(
        client=client,
        model=MODEL_HISTORIAN,
        system_prompt=system_prompt,
        user_message=user_message,
        role="historian",
        campaign_dir=campaign_dir,
    )

    # Parse sentinel
    hm = HISTORIAN_RE.search(accumulated_text)
    if hm:
        trigger = hm.group(2)
        patterns_added = int(hm.group(3))
        assumptions_flagged = int(hm.group(4))
        sentinel_tokens = int(hm.group(5))
    else:
        print("[orchestrator] WARNING: Historian did not emit HISTORIAN_COMPLETE sentinel")
        trigger = trigger_meta.get("trigger", "periodic")
        patterns_added = 0
        assumptions_flagged = 0
        sentinel_tokens = tokens_used

    result = runner_driver.historian_finalize(
        campaign_dir=str(campaign_dir),
        trigger=trigger,
        patterns_added=patterns_added,
        assumptions_flagged=assumptions_flagged,
        tokens_used=sentinel_tokens,
    )
    print(f"[orchestrator] Historian done: {result}")
    return result


def run_planner_phase(
    client: anthropic.Anthropic,
    campaign_dir: Path,
    stuck_warnings: list[str],
) -> dict[str, Any]:
    """Run the Planner role and validate output via plan_check."""
    print(f"[orchestrator] Running Planner phase...")
    system_prompt = (REPO_ROOT / "runner" / "roles" / "planner.md").read_text(encoding="utf-8")
    user_message = _build_planner_context(campaign_dir, stuck_warnings)

    accumulated_text, tokens_used = _invoke_role(
        client=client,
        model=MODEL_PLANNER,
        system_prompt=system_prompt,
        user_message=user_message,
        role="planner",
        campaign_dir=campaign_dir,
    )

    check = runner_driver.plan_check(campaign_dir=str(campaign_dir))
    print(f"[orchestrator] plan_check: {check}")
    return {**check, "tokens_used": tokens_used}


def run_executor_phase(
    client: anthropic.Anthropic,
    campaign_dir: Path,
) -> dict[str, Any]:
    """Run the Executor role and finalize via execute_finalize."""
    print(f"[orchestrator] Running Executor phase...")
    system_prompt = (REPO_ROOT / "runner" / "roles" / "executor.md").read_text(encoding="utf-8")
    user_message = _build_executor_context(campaign_dir)

    accumulated_text, tokens_used = _invoke_role(
        client=client,
        model=MODEL_EXECUTOR,
        system_prompt=system_prompt,
        user_message=user_message,
        role="executor",
        campaign_dir=campaign_dir,
    )

    # Parse sentinel from accumulated text
    executor_stdout = ""
    rc = RUN_COMPLETE_RE.search(accumulated_text)
    rf = RUN_FAILED_RE.search(accumulated_text)
    rr = REVIEW_REQUIRED_RE.search(accumulated_text)

    if rc:
        commit = rc.group(1)
        executor_stdout = f"RUN_COMPLETE: {commit}\n"
    elif rf:
        commit = rf.group(1)
        reason = rf.group(2) or ""
        executor_stdout = f"RUN_FAILED: {commit} {reason}\n"
    elif rr:
        executor_stdout = f"REVIEW_REQUIRED: {rr.group(1)}\n"
    else:
        executor_stdout = "RUN_FAILED: unknown no_sentinel_emitted\n"
        print("[orchestrator] WARNING: Executor did not emit any sentinel")

    # Get commit diff files if RUN_COMPLETE
    commit_diff_files = None
    if rc:
        commit = rc.group(1)
        try:
            diff_out = subprocess.run(
                ["git", "diff", "--name-only", f"{commit}^", commit],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if diff_out.returncode == 0:
                commit_diff_files = [f for f in diff_out.stdout.strip().splitlines() if f]
        except Exception:
            pass

    exec_result = runner_driver.execute_finalize(
        executor_stdout=executor_stdout,
        campaign_dir=str(campaign_dir),
        commit_diff_files=commit_diff_files,
    )
    print(f"[orchestrator] execute_finalize: {exec_result}")
    return {**exec_result, "tokens_used": tokens_used}


def run_reviewer_phase(
    client: anthropic.Anthropic,
    campaign_dir: Path,
    executor_result: dict[str, Any],
    planner_tokens: int,
    executor_tokens: int,
) -> dict[str, Any]:
    """Run the Reviewer role and finalize via review_finalize."""
    print(f"[orchestrator] Running Reviewer phase...")
    system_prompt = (REPO_ROOT / "runner" / "roles" / "reviewer.md").read_text(encoding="utf-8")
    user_message = _build_reviewer_context(campaign_dir)

    # If executor produced a synthetic verdict, skip LLM call
    if executor_result.get("synthetic_verdict"):
        verdict = executor_result["synthetic_verdict"]
        commit = executor_result.get("commit", "unknown")
        tools_ran: list[str] = []
        reviewer_tokens = 0
        print(f"[orchestrator] Skipping Reviewer LLM: synthetic verdict={verdict}")
    else:
        accumulated_text, reviewer_tokens = _invoke_role(
            client=client,
            model=MODEL_REVIEWER,
            system_prompt=system_prompt,
            user_message=user_message,
            role="reviewer",
            campaign_dir=campaign_dir,
        )

        # Parse verdict sentinel
        vm = VERDICT_RE.search(accumulated_text)
        if vm:
            verdict = vm.group(1).lower()
            commit = vm.group(2)
        else:
            print("[orchestrator] WARNING: Reviewer did not emit VERDICT sentinel")
            verdict = "malformed"
            commit = executor_result.get("commit", "unknown")

        tools_ran = _infer_tools_ran(accumulated_text)

    # Parse metrics from run.log
    metrics = _parse_metrics_from_log(campaign_dir)

    # Read NEXT_EXPERIMENT.md for action_type, hypothesis, description
    action_type = "unknown"
    hypothesis = ""
    description = ""
    model_family = "unknown"
    n_features = 0
    try:
        from runner.tools._common import parse_frontmatter
        fm, body = parse_frontmatter(campaign_dir / "state" / "NEXT_EXPERIMENT.md")
        action_type = fm.get("action_type", "unknown")
        hypothesis = fm.get("hypothesis", "")
        description = body.strip()[:200] if body else ""
    except Exception:
        pass

    review_result = runner_driver.review_finalize(
        verdict=verdict,
        commit=commit,
        metrics=metrics,
        action_type=action_type,
        hypothesis=hypothesis,
        description=description,
        model_family=model_family,
        n_features=n_features,
        campaign_dir=str(campaign_dir),
        tools_ran=tools_ran,
        planner_tokens=planner_tokens,
        executor_tokens=executor_tokens,
        reviewer_tokens=reviewer_tokens,
    )
    print(f"[orchestrator] review_finalize: {review_result}")
    return review_result
```

- [ ] **Step 4: Verify**

Run: `python -c "from runner.orchestrator import run_planner_phase, run_executor_phase, run_reviewer_phase, run_historian_phase; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): per-role phase runners with sentinel parsing"
```

---

## Task 8: Main Loop and CLI

**Files:**
- Modify: `runner/orchestrator.py`

- [ ] **Step 1: Add the main orchestration loop**

Append to `runner/orchestrator.py`:

```python
# ── Main loop ─────────────────────────────────────────────────────────

def run_campaign(
    campaign_dir: str,
    resume: bool = False,
    max_rounds: int | None = None,
    client: anthropic.Anthropic | None = None,
) -> None:
    """Run the full outer loop for a campaign."""
    camp = Path(campaign_dir).resolve()
    if client is None:
        client = anthropic.Anthropic()

    state_path = camp / "state" / "CAMPAIGN_STATE.json"

    # Initialize if needed
    if not state_path.exists():
        print(f"[orchestrator] Initializing campaign at {camp}")
        runner_driver.init_campaign(campaign_dir=str(camp))

    state = json.loads(state_path.read_text())
    budget_total = int(state.get("budget_total", 100))
    if max_rounds is not None:
        budget_total = min(budget_total, int(state.get("budget_used", 0)) + max_rounds)

    # Determine start phase for --resume
    start_phase = "planner"
    if resume:
        start_phase = _determine_resume_phase(camp, state)
        print(f"[orchestrator] Resuming from phase: {start_phase}")

    phase = start_phase

    while int(state.get("budget_used", 0)) < budget_total:
        current_round = int(state.get("round", 0))
        print(f"\n{'='*60}")
        print(f"[orchestrator] Round {current_round + 1} | budget {state.get('budget_used', 0)}/{budget_total}")
        print(f"{'='*60}")

        # ── Historian (if pending) ──
        if phase == "historian" or (
            phase == "planner" and state.get("historian_trigger_pending", False)
        ):
            run_historian_phase(client, camp)
            state = json.loads(state_path.read_text())
            phase = "planner"

        if phase == "next_round":
            phase = "planner"
            continue

        # ── Planner ──
        if phase == "planner":
            stuck_warnings = detect_stuck(camp)
            train_sha_before = _train_py_sha256(camp)

            plan_result = run_planner_phase(client, camp, stuck_warnings)
            planner_tokens = plan_result.get("tokens_used", 0)

            if plan_result["status"] in ("pause_c2", "pause_c3"):
                print(f"[orchestrator] {plan_result['status']} — human review required")
                break
            if plan_result["status"] != "ok":
                print(f"[orchestrator] plan_check failed: {plan_result}")
                break

            phase = "executor"

        # ── Executor ──
        if phase == "executor":
            exec_result = run_executor_phase(client, camp)
            executor_tokens = exec_result.get("tokens_used", 0)

            # Duplicate train.py check
            train_sha_after = _train_py_sha256(camp)
            if (
                "train_sha_before" in dir()
                and train_sha_before
                and train_sha_before == train_sha_after
                and exec_result.get("channel") == "RUN_COMPLETE"
            ):
                print("[orchestrator] WARNING: train.py unchanged — treating as crash")
                exec_result["synthetic_verdict"] = "crash"
                exec_result["reason"] = "train.py SHA-256 identical before/after executor"

            phase = "reviewer"

        # ── Reviewer ──
        if phase == "reviewer":
            # planner_tokens / executor_tokens may not be set during --resume
            pt = planner_tokens if "planner_tokens" in dir() else 0
            et = executor_tokens if "executor_tokens" in dir() else 0

            review_result = run_reviewer_phase(client, camp, exec_result, pt, et)

            # Rollback if needed
            if review_result.get("should_rollback", False):
                print("[orchestrator] Rolling back: git reset --hard HEAD~1")
                subprocess.run(
                    ["git", "reset", "--hard", "HEAD~1"],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                )

            # Halt/pause checks
            if review_result.get("halt_loop", False):
                print(f"[orchestrator] HALT: {review_result.get('halt_reason', 'unknown')}")
                break
            if review_result.get("pause_loop", False):
                print("[orchestrator] Anomaly (C1) — human review required at state/REVIEW.md")
                break

        # Reload state for next iteration
        state = json.loads(state_path.read_text())
        phase = "planner"  # Reset for next round

    print(f"\n[orchestrator] Campaign loop finished. Rounds completed: {state.get('round', 0)}")
```

- [ ] **Step 2: Add CLI entry point**

Append to `runner/orchestrator.py`:

```python
# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestrator: outer ReAct loop for the auto-train harness"
    )
    parser.add_argument(
        "--campaign-dir",
        required=True,
        help="Path to campaign directory (e.g. campaigns/smoke-test-creditcard)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from crash — detect last completed phase",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Maximum additional rounds to run (overrides budget if smaller)",
    )
    args = parser.parse_args()

    run_campaign(
        campaign_dir=args.campaign_dir,
        resume=args.resume,
        max_rounds=args.max_rounds,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify full module**

Run: `python -c "import runner.orchestrator; print('OK')"`
Expected: `OK`

Run: `python runner/orchestrator.py --help`
Expected: Shows usage help with `--campaign-dir`, `--resume`, `--max-rounds` options.

- [ ] **Step 4: Commit**

```bash
git add runner/orchestrator.py
git commit -m "feat(orchestrator): main loop with CLI entry point"
```

---

## Task 9: Test 1 — Planner Writes NEXT_EXPERIMENT.md

**Files:**
- Create: `tests/integration/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_orchestrator.py`:

```python
"""Integration tests for runner/orchestrator.py with mocked Anthropic client."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest

from runner import runner_driver, orchestrator
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.integration


# ── Helpers ───────────────────────────────────────────────────────────

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


def _make_campaign(tmp_path: Path) -> Path:
    """Create a minimal campaign directory with signed contracts."""
    root = tmp_path / "campaign"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_PROTOCOL)
    (root / "train.py").write_text("# placeholder\n")
    return root


def _mock_response(text: str = "", tool_calls: list | None = None, stop_reason: str = "end_turn"):
    """Build a mock Anthropic response."""
    content = []
    if tool_calls:
        for tc in tool_calls:
            content.append(SimpleNamespace(
                type="tool_use",
                id=f"tool_{tc['name']}",
                name=tc["name"],
                input=tc["input"],
            ))
    if text:
        content.append(SimpleNamespace(type="text", text=text))
    if not content:
        content.append(SimpleNamespace(type="text", text=""))

    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


# ── Test 1: Planner writes NEXT_EXPERIMENT.md ─────────────────────────

def test_planner_writes_next_experiment(tmp_path: Path):
    campaign = _make_campaign(tmp_path)
    runner_driver.init_campaign(campaign_dir=str(campaign))

    # Mock: first response writes file via tool, second response is end_turn
    write_call = _mock_response(
        tool_calls=[{
            "name": "write_file",
            "input": {
                "path": str(campaign / "state" / "NEXT_EXPERIMENT.md"),
                "content": VALID_NEXT_EXPERIMENT,
            },
        }],
        stop_reason="tool_use",
    )
    end_turn = _mock_response(text="Plan written successfully.")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [write_call, end_turn]

    result = orchestrator.run_planner_phase(
        client=mock_client,
        campaign_dir=campaign,
        stuck_warnings=[],
    )

    assert result["status"] == "ok"
    assert (campaign / "state" / "NEXT_EXPERIMENT.md").exists()

    check = runner_driver.plan_check(campaign_dir=str(campaign))
    assert check["status"] == "ok"
    assert check["errors"] == []
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/integration/test_orchestrator.py::test_planner_writes_next_experiment -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_orchestrator.py
git commit -m "test(orchestrator): planner writes NEXT_EXPERIMENT.md"
```

---

## Task 10: Test 2 — Historian Runs When Trigger Pending

**Files:**
- Modify: `tests/integration/test_orchestrator.py`

- [ ] **Step 1: Write the test**

Append to `tests/integration/test_orchestrator.py`:

```python
# ── Test 2: Historian runs when trigger pending ───────────────────────

def test_historian_runs_when_trigger_pending(tmp_path: Path):
    campaign = _make_campaign(tmp_path)
    runner_driver.init_campaign(campaign_dir=str(campaign))

    # Manually set historian_trigger_pending and advance state
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["historian_trigger_pending"] = True
    state["round"] = 5
    state["rounds_since_last_historian"] = 10
    state_path.write_text(json.dumps(state, indent=2))

    memo_path = str(campaign / "state" / "STRATEGY_MEMO.md")
    pb_path = str(campaign / "state" / "PATTERN_BOOK.md")

    # Mock: write STRATEGY_MEMO.md, write PATTERN_BOOK.md, then end_turn with sentinel
    write_memo = _mock_response(
        tool_calls=[{
            "name": "write_file",
            "input": {
                "path": memo_path,
                "content": "# Strategy Memo\nFocus on ensemble methods.\n",
            },
        }],
        stop_reason="tool_use",
    )
    write_pb = _mock_response(
        tool_calls=[{
            "name": "write_file",
            "input": {
                "path": pb_path,
                "content": "# Pattern Book\n### P-1 — LR sensitivity\nLR < 0.01 works best.\n",
            },
        }],
        stop_reason="tool_use",
    )
    end_turn = _mock_response(
        text="HISTORIAN_COMPLETE: round 5, trigger periodic, patterns_added 1, assumptions_flagged 0, tokens_used 500",
    )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [write_memo, write_pb, end_turn]

    result = orchestrator.run_historian_phase(client=mock_client, campaign_dir=campaign)

    assert result["status"] == "ok"
    assert (campaign / "state" / "STRATEGY_MEMO.md").exists()

    state_after = json.loads(state_path.read_text())
    assert state_after["historian_trigger_pending"] is False
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/integration/test_orchestrator.py::test_historian_runs_when_trigger_pending -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_orchestrator.py
git commit -m "test(orchestrator): historian runs when trigger pending"
```

---

## Task 11: Test 3 — Stuck Detection

**Files:**
- Modify: `tests/integration/test_orchestrator.py`

- [ ] **Step 1: Write the test**

Append to `tests/integration/test_orchestrator.py`:

```python
# ── Test 3: Stuck detection fires after 3 same action_types ───────────

def test_stuck_detection_fires(tmp_path: Path):
    campaign = _make_campaign(tmp_path)
    runner_driver.init_campaign(campaign_dir=str(campaign))

    # Write results.tsv with header + 4 rows all having action_type=A_hp
    results_path = campaign / "state" / "results.tsv"
    header = results_path.read_text().splitlines()[0]

    # Count columns in header to build matching data rows
    n_cols = len(header.split("\t"))
    col_names = header.split("\t")
    at_idx = col_names.index("action_type")

    rows = []
    for i in range(4):
        row = [""] * n_cols
        row[0] = f"commit{i}"  # commit
        row[at_idx] = "A_hp"
        rows.append("\t".join(row))

    results_path.write_text(header + "\n" + "\n".join(rows) + "\n")

    warnings = orchestrator.detect_stuck(campaign)
    assert len(warnings) > 0
    assert any("STUCK WARNING" in w for w in warnings)
    assert any("A_hp" in w for w in warnings)
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/integration/test_orchestrator.py::test_stuck_detection_fires -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_orchestrator.py
git commit -m "test(orchestrator): stuck detection fires for 3 same action_types"
```

---

## Task 12: Test 4 — Crash Recovery Resume Phase

**Files:**
- Modify: `tests/integration/test_orchestrator.py`

- [ ] **Step 1: Write the test**

Append to `tests/integration/test_orchestrator.py`:

```python
# ── Test 4: Crash recovery determines correct resume phase ────────────

def test_crash_recovery_determines_resume_phase(tmp_path: Path):
    """Four sub-cases for _determine_resume_phase."""
    campaign = _make_campaign(tmp_path)
    runner_driver.init_campaign(campaign_dir=str(campaign))

    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["round"] = 5

    s = campaign / "state"

    # Case A: Journal has "## Round 5" → next_round
    (s / "CAMPAIGN_JOURNAL.md").write_text("# Journal\n\n## Round 5\nDone.\n")
    state["historian_trigger_pending"] = False
    assert orchestrator._determine_resume_phase(campaign, state) == "next_round"

    # Case A variant: historian pending → historian
    state["historian_trigger_pending"] = True
    assert orchestrator._determine_resume_phase(campaign, state) == "historian"

    # Clean up for Case B
    (s / "CAMPAIGN_JOURNAL.md").unlink()
    state["historian_trigger_pending"] = False

    # Case B: run.log has RUN_COMPLETE but no journal → reviewer
    (campaign / "run.log").write_text("Training done.\nRUN_COMPLETE: abc123\n")
    assert orchestrator._determine_resume_phase(campaign, state) == "reviewer"

    # Clean up for Case C
    (campaign / "run.log").unlink()

    # Case C: NEXT_EXPERIMENT.md has round: 5, no run.log → executor
    next_exp_text = VALID_NEXT_EXPERIMENT.replace("round: 1", "round: 5")
    (s / "NEXT_EXPERIMENT.md").write_text(next_exp_text)
    assert orchestrator._determine_resume_phase(campaign, state) == "executor"

    # Clean up for Case D
    (s / "NEXT_EXPERIMENT.md").unlink()

    # Case D: Nothing present → planner
    assert orchestrator._determine_resume_phase(campaign, state) == "planner"
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/integration/test_orchestrator.py::test_crash_recovery_determines_resume_phase -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_orchestrator.py
git commit -m "test(orchestrator): crash recovery resume phase detection"
```

---

## Task 13: Test 5 — tools_ran Inferred from Reviewer Text

**Files:**
- Modify: `tests/integration/test_orchestrator.py`

- [ ] **Step 1: Write the test**

Append to `tests/integration/test_orchestrator.py`:

```python
# ── Test 5: tools_ran inferred from Reviewer text ─────────────────────

def test_tools_ran_inferred_from_reviewer_text(tmp_path: Path):
    campaign = _make_campaign(tmp_path)
    runner_driver.init_campaign(campaign_dir=str(campaign))

    # Set up state for a round that needs review
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["round"] = 1
    state_path.write_text(json.dumps(state, indent=2))

    # Write NEXT_EXPERIMENT.md
    (campaign / "state" / "NEXT_EXPERIMENT.md").write_text(VALID_NEXT_EXPERIMENT)

    # Write run.log with metrics
    (campaign / "run.log").write_text("val_pr_auc: 0.75\nval_f1: 0.60\n")

    # Mock Reviewer response with tool names mentioned and VERDICT sentinel
    reviewer_text = (
        "I ran the anomaly detection check and the bootstrap_ci confidence intervals. "
        "Both passed. The model shows significant improvement.\n"
        "VERDICT: keep abc123def"
    )
    end_turn = _mock_response(text=reviewer_text)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [end_turn]

    # Mock the executor result as if RUN_COMPLETE
    executor_result = {
        "channel": "RUN_COMPLETE",
        "commit": "abc123def",
        "synthetic_verdict": None,
        "reason": "",
    }

    with patch.object(runner_driver, "review_finalize") as mock_rf:
        mock_rf.return_value = {
            "verdict": "keep",
            "should_rollback": False,
            "pause_loop": False,
            "halt_loop": False,
            "halt_reason": "",
        }

        orchestrator.run_reviewer_phase(
            client=mock_client,
            campaign_dir=campaign,
            executor_result=executor_result,
            planner_tokens=100,
            executor_tokens=200,
        )

        # Assert review_finalize was called with tools_ran containing both tools
        call_kwargs = mock_rf.call_args
        tools_ran_arg = call_kwargs.kwargs.get("tools_ran") or call_kwargs[1].get("tools_ran", [])
        assert "runner.tools.anomaly" in tools_ran_arg
        assert "runner.tools.bootstrap_ci" in tools_ran_arg
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/integration/test_orchestrator.py::test_tools_ran_inferred_from_reviewer_text -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_orchestrator.py
git commit -m "test(orchestrator): tools_ran inferred from reviewer response text"
```

---

## Task 14: Full Test Suite Validation

**Files:**
- None modified

- [ ] **Step 1: Run the new integration tests**

Run: `python -m pytest tests/integration/test_orchestrator.py -v`
Expected: All 5 tests PASS

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: All existing tests still pass; no regressions

- [ ] **Step 3: Verify CLI help**

Run: `python runner/orchestrator.py --help`
Expected: Shows usage with `--campaign-dir`, `--resume`, `--max-rounds` options

- [ ] **Step 4: Final commit (squash or tag)**

```bash
git add -A
git commit -m "feat(orchestrator): complete outer loop + 5 integration tests

Implements runner/orchestrator.py with:
- Tool-use ReAct loop via Anthropic SDK
- Per-role context assembly (Planner/Executor/Reviewer/Historian)
- Write-scope enforcement per role
- Sentinel parsing for all 4 roles
- Stuck detection (3-same, A-B-A-B patterns)
- Crash recovery (--resume flag)
- Duplicate train.py SHA-256 detection
- CLI: --campaign-dir, --resume, --max-rounds

Tests: 5 integration tests with mocked Anthropic client"
```

---

## Implementation Notes

**What this plan does NOT build (per spec):**
- No template-based experiment generation
- No hardcoded experiment sequences
- No Python code that decides what experiment to run
- No stub historian
- No inlined role prompt content — all `.md` files are read at runtime

**Key design decisions:**
1. **Single file** — `orchestrator.py` is ~500 lines; splitting would add complexity without benefit at this size
2. **`run_campaign()` accepts a `client` parameter** — enables test injection of mocked client
3. **Phase runners are public functions** — enables per-phase testing without running the full loop
4. **`_determine_resume_phase` uses file presence heuristics** — no extra state tracking needed
5. **`_infer_tools_ran` is keyword-based** — simple, extensible, matches how tool names appear in Reviewer prose
6. **Duplicate detection uses SHA-256 of `train.py`** — catches executor no-ops without git inspection
