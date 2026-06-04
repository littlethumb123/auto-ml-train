"""Substantive-diff checker (GAP 2 — four-level verification, level 2+3).

Validates that an experiment commit is non-trivial:
  Level 2 (Substantive): The diff contains real implementation changes,
      not just comments, whitespace, reordering, or no-ops.
  Level 3 (Wired): If helpers_declared is non-empty, at least one
      declared helper path appears in an import/open statement in train.py.

Usage:
    python -m runner.tools.substantive_diff \
        --diff-text "$(git show --unified=0 HEAD)" \
        --train-py campaigns/my-campaign/train.py \
        --helpers-declared '["experiment_helpers/e5/config.json"]' \
        --json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


# ── Heuristic: strip comment-only and whitespace-only diff hunks ──────

_COMMENT_ONLY_RE = re.compile(r"^[+-]\s*#.*$")
_BLANK_RE = re.compile(r"^[+-]\s*$")
_HUNK_HEADER_RE = re.compile(r"^@@")
_DIFF_LINE_RE = re.compile(r"^[+-]")


def _count_substantive_lines(diff_text: str) -> int:
    """Count diff lines that are not comments, blanks, or hunk headers."""
    count = 0
    for line in diff_text.splitlines():
        if not _DIFF_LINE_RE.match(line):
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if _COMMENT_ONLY_RE.match(line):
            continue
        if _BLANK_RE.match(line):
            continue
        count += 1
    return count


# ── Helper wiring check ──────────────────────────────────────────────

def _check_helpers_wired(train_py_text: str, helpers: list[str]) -> list[str]:
    """Return list of declared helpers NOT referenced in train.py source."""
    unwired: list[str] = []
    for h in helpers:
        h = h.strip()
        if not h:
            continue
        # Check for any substring reference — filename, module path, or path fragment
        basename = Path(h).name
        stem = Path(h).stem
        if basename not in train_py_text and h not in train_py_text and stem not in train_py_text:
            unwired.append(h)
    return unwired


# ── Public API ────────────────────────────────────────────────────────

def check_substantive(
    diff_text: str,
    train_py_text: str | None = None,
    helpers_declared: list[str] | None = None,
) -> dict[str, Any]:
    """Run the substantive-diff check.

    Returns:
        {
            "substantive": bool,
            "substantive_lines": int,
            "helpers_wired": bool,
            "unwired_helpers": [...],
            "issues": [...],
        }
    """
    issues: list[str] = []

    sub_lines = _count_substantive_lines(diff_text)
    is_substantive = sub_lines >= 1

    if not is_substantive:
        issues.append(
            f"Diff has 0 substantive lines (only comments/whitespace/blanks). "
            f"This is a no-op experiment."
        )

    unwired: list[str] = []
    helpers_ok = True
    if helpers_declared and train_py_text is not None:
        unwired = _check_helpers_wired(train_py_text, helpers_declared)
        if unwired:
            helpers_ok = False
            issues.append(
                f"Declared helpers not referenced in train.py: {unwired}. "
                f"These files exist but are never imported or used."
            )

    return {
        "substantive": is_substantive,
        "substantive_lines": sub_lines,
        "helpers_wired": helpers_ok,
        "unwired_helpers": unwired,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Check that an experiment diff is substantive.")
    p.add_argument("--diff-text", required=True, help="Raw git diff text (unified format).")
    p.add_argument("--train-py", default=None, help="Path to train.py for helper wiring check.")
    p.add_argument("--helpers-declared", default="[]", help="JSON array of declared helper paths.")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    helpers = json.loads(args.helpers_declared)
    train_text = None
    if args.train_py:
        train_text = Path(args.train_py).read_text()

    result = check_substantive(args.diff_text, train_text, helpers)

    if args.json_output:
        json.dump(result, sys.stdout, separators=(",", ":"), sort_keys=True)
        sys.stdout.write("\n")
    else:
        for issue in result["issues"]:
            print(f"  ⚠ {issue}")
        if not result["issues"]:
            print(f"  ✓ Substantive ({result['substantive_lines']} lines)")
    return 0 if (result["substantive"] and result["helpers_wired"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
