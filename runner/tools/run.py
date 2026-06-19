"""Tool-execution wrapper that emits structured receipts (F3).

Every mandatory tool invocation must go through ``execute()``. The wrapper
brackets the subprocess with a ``tool_run`` event in ``state/driver_events.jsonl``
that ``review_finalize()`` cross-checks against the caller's ``tools_ran``
claim. This closes the structural mandatory-gate bypass documented in
``docs/reflections/2026-06-19-harness-self-audit.md`` (P0-3).

Receipt schema::

    {
      "ts": "<ISO Z>",
      "event": "tool_run",
      "name": "runner.tools.anomaly",
      "start_ts": "<ISO Z>",
      "end_ts": "<ISO Z>",
      "exit_code": 0,
      "args_hash": "<sha256[:16] of canonical args>",
      "round": 5,
      "campaign_dir": "<path>"
    }
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from runner.runner_driver import (
    _emit_event,
    _normalize_mandatory_tool_name,
)


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_args(args: list[str]) -> str:
    canonical = json.dumps(list(args), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _current_round(campaign_dir: str) -> int:
    state_path = Path(campaign_dir) / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        return 0
    try:
        return int(json.loads(state_path.read_text()).get("round", 0))
    except (json.JSONDecodeError, OSError, ValueError):
        return 0


def execute(
    name: str,
    args: list[str],
    campaign_dir: str,
    cwd: str | None = None,
) -> int:
    """Run ``python -m <name> <args>`` and emit a tool_run receipt.

    Args:
        name: Tool module path (e.g. ``runner.tools.anomaly``). Accepts both
            dotted and slashed forms; normalized via
            :func:`_normalize_mandatory_tool_name`.
        args: List of CLI arguments forwarded to the subprocess.
        campaign_dir: Campaign directory (used for the receipt path and round
            lookup).
        cwd: Optional working directory for the subprocess. Defaults to the
            current working directory.

    Returns:
        The subprocess exit code. The receipt is written even on non-zero exit
        so consumers can distinguish "claimed but failed" from "claimed but
        never invoked".
    """
    normalized = _normalize_mandatory_tool_name(name)
    start = _utcnow()
    proc = subprocess.run(
        [sys.executable, "-m", normalized, *args],
        cwd=cwd if cwd is not None else os.getcwd(),
    )
    end = _utcnow()
    _emit_event(campaign_dir, "tool_run", {
        "name": normalized,
        "start_ts": start,
        "end_ts": end,
        "exit_code": int(proc.returncode),
        "args_hash": _hash_args(args),
        "round": _current_round(campaign_dir),
        "campaign_dir": campaign_dir,
    })
    return int(proc.returncode)
