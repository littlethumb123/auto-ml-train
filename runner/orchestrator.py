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

    # Case C: NEXT_EXPERIMENT.md exists → executor
    next_exp = s / "NEXT_EXPERIMENT.md"
    if next_exp.exists():
        return "executor"

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
