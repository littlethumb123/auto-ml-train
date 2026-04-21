"""Shared utilities for runner.tools modules.

Contents:
  - Exit-code constants (spec §2.2).
  - YAML frontmatter parser used by schema validators and contract-diff tool.
  - JSON emitter for `--json` CLI switch.
  - argparse helpers (campaign_dir and json flags).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

EXIT_OK = 0
EXIT_USER_ERROR = 2
EXIT_CONTRACT_VIOLATION = 3
EXIT_INTERNAL_ERROR = 4


class FrontmatterError(Exception):
    """Raised when YAML frontmatter cannot be located or parsed."""


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Parse `---\n<yaml>\n---` from the top of a markdown file.

    Returns (frontmatter_dict, body_after_frontmatter).
    Raises FrontmatterError if delimiters are missing or YAML is invalid.
    """
    text = Path(path).read_text()
    if not text.startswith("---\n"):
        raise FrontmatterError(f"{path}: file does not begin with '---' delimiter")
    rest = text[4:]
    end = rest.find("\n---\n")
    if end < 0:
        end_alt = rest.find("\n---")
        if end_alt < 0:
            raise FrontmatterError(f"{path}: no closing '---' delimiter found")
        fm_text = rest[:end_alt]
        body = rest[end_alt + 4 :]
    else:
        fm_text = rest[:end]
        body = rest[end + 5 :]
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"{path}: invalid YAML — {exc}") from exc
    if not isinstance(data, dict):
        raise FrontmatterError(f"{path}: frontmatter must be a YAML mapping, got {type(data).__name__}")
    return data, body


def emit_json(payload: Any) -> None:
    """Write payload as a single compact JSON line to stdout and flush."""
    json.dump(payload, sys.stdout, separators=(",", ":"), sort_keys=True)
    sys.stdout.write("\n")
    sys.stdout.flush()


def add_standard_args(parser: argparse.ArgumentParser) -> None:
    """Add --campaign-dir and --json to a tool's argparse parser."""
    parser.add_argument(
        "--campaign-dir",
        default="runner/",
        help="Path to the runner campaign directory (default: runner/).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit result as a single JSON line on stdout.",
    )
