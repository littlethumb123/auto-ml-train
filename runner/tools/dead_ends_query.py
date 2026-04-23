"""Dead-ends query (spec §2.2.3)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from runner.tools._common import EXIT_OK, emit_json

_BULLET = re.compile(r"^\s*-\s+(.*\S)\s*$", re.MULTILINE)


def dead_ends_query(
    pattern: str | None = None,
    campaign_dir: str = "runner/",
) -> list[str]:
    path = Path(campaign_dir) / "state" / "DEAD_ENDS.md"
    if not path.exists():
        return []
    text = path.read_text()
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5 :]
    bullets = [m.group(1).strip() for m in _BULLET.finditer(text)]
    if pattern is None:
        return bullets
    regex = re.compile(pattern)
    return [b for b in bullets if regex.search(b)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Query runner/state/DEAD_ENDS.md.")
    p.add_argument("--pattern", default=None, help="Substring or regex.")
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    items = dead_ends_query(pattern=args.pattern, campaign_dir=args.campaign_dir)
    if args.json_output:
        emit_json(items)
    else:
        for item in items:
            print(f"- {item}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
