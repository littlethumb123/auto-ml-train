"""Memory query over results.tsv (spec §2.2.3).

Returns top rows filtered + ordered. Schema mismatch raises
SchemaMismatchError, mapped to exit code 3 in the CLI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_OK,
    EXIT_USER_ERROR,
    emit_json,
)

# Columns every campaign's results.tsv must contain (structural, not metric-specific).
# Campaigns may add any number of additional columns; the schema check only
# enforces the minimum required set so results_query works for any campaign.
_MINIMUM_COLUMNS = {
    "commit", "status", "n_features", "model_family",
    "action_type", "hypothesis", "description",
}

# Columns that should not be coerced to numeric (keep as strings).
_STRING_COLUMNS = {
    "commit", "status", "model_family", "action_type", "hypothesis", "description",
}


class SchemaMismatchError(Exception):
    """results.tsv is missing required structural columns."""


def results_query(
    filter_expr: str = "status != 'crash'",
    order_by: str = "val_pr_auc",
    limit: int = 10,
    campaign_dir: str = "runner/",
    ascending: bool = False,
) -> list[dict]:
    path = Path(campaign_dir) / "state" / "results.tsv"
    if not path.exists():
        return []
    df = pd.read_csv(path, sep="\t")
    missing = _MINIMUM_COLUMNS - set(df.columns)
    if missing:
        raise SchemaMismatchError(
            f"results.tsv is missing required columns: {sorted(missing)}. "
            f"Found: {list(df.columns)}"
        )
    for col in df.columns:
        if col not in _STRING_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if filter_expr:
        df = df.query(filter_expr)
    if order_by in df.columns:
        df = df.sort_values(by=order_by, ascending=ascending)
    if limit is not None and limit > 0:
        df = df.head(limit)
    return df.to_dict(orient="records")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Query runner/state/results.tsv.")
    p.add_argument("--filter", default="status != 'crash'", dest="filter_expr")
    p.add_argument("--order-by", default="val_pr_auc", help="Column to sort by (use primary metric name for the campaign)")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--ascending", action="store_true")
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    try:
        rows = results_query(
            filter_expr=args.filter_expr,
            order_by=args.order_by,
            limit=args.limit,
            campaign_dir=args.campaign_dir,
            ascending=args.ascending,
        )
    except SchemaMismatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    if args.json_output:
        emit_json(rows)
    else:
        if not rows:
            print("(no rows)")
        else:
            cols = ["commit", "val_pr_auc", "status", "model_family", "action_type"]
            for r in rows:
                print("  ".join(f"{r.get(c, ''):>12}" for c in cols))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
