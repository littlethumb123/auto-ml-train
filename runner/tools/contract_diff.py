"""Contract diff (spec §2.2.4) — C3 governance."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_OK,
    EXIT_USER_ERROR,
    FrontmatterError,
    emit_json,
    parse_frontmatter,
)

_CONTRACT_FILES = {
    "PROBLEM": "PROBLEM_CONTRACT.md",
    "DATA": "DATA_CONTRACT.md",
    "EVAL": "EVAL_PROTOCOL.md",
}

_HIGH_RISK_FIELDS = {
    "budgets.max_repair_attempts",
    "primary_metric.name",
    "primary_metric.direction",
    "cv_scheme.type",
}


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten(v, key))
    else:
        out[prefix] = d
    return out


def contract_diff(
    contract_name: str,
    proposed_path: str,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    if contract_name not in _CONTRACT_FILES:
        raise ValueError(f"contract_name must be one of {list(_CONTRACT_FILES)}")
    current_path = Path(campaign_dir) / "contracts" / _CONTRACT_FILES[contract_name]
    if not current_path.exists():
        raise FileNotFoundError(f"current contract not found: {current_path}")
    cur_fm, _ = parse_frontmatter(current_path)
    new_fm, _ = parse_frontmatter(Path(proposed_path))

    cur_flat = _flatten(cur_fm)
    new_flat = _flatten(new_fm)
    all_keys = sorted(set(cur_flat) | set(new_flat))

    changes = []
    for k in all_keys:
        before = cur_flat.get(k)
        after = new_flat.get(k)
        if before != after:
            changes.append({"field": k, "before": before, "after": after})

    risk = "low"
    if any(c["field"] in _HIGH_RISK_FIELDS for c in changes):
        risk = "high"
    elif len(changes) > 5:
        risk = "medium"

    return {
        "contract": contract_name,
        "changes": changes,
        "risk_level": risk,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Structured contract diff (C3).")
    p.add_argument("--contract-name", required=True, choices=list(_CONTRACT_FILES))
    p.add_argument("--proposed-path", required=True)
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = contract_diff(args.contract_name, args.proposed_path, args.campaign_dir)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except FrontmatterError as exc:
        print(f"CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    if args.json_output:
        emit_json(res)
    else:
        print(f"contract={res['contract']} risk={res['risk_level']} changes={len(res['changes'])}")
        for c in res["changes"]:
            print(f"  {c['field']}: {c['before']!r} -> {c['after']!r}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
