"""runner/tools/token_summary.py — token cost digest for Planner consumption.

Reads results.tsv token columns and writes state/TOKEN_SUMMARY.txt.
Called after each review_finalize. Non-critical: caller should catch all exceptions.
"""
from __future__ import annotations

import csv
from pathlib import Path


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def write_token_summary(campaign_dir: str = "runner/") -> str:
    """Read results.tsv token columns and write TOKEN_SUMMARY.txt.

    Returns the summary line written (also written to file).
    """
    camp = Path(campaign_dir)
    results_path = camp / "state" / "results.tsv"
    summary_path = camp / "state" / "TOKEN_SUMMARY.txt"

    if not results_path.exists():
        summary = "Campaign tokens — no results yet"
        summary_path.write_text(summary + "\n")
        return summary

    rows: list[dict] = []
    fieldnames: list[str] = []
    with results_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append(row)

    if "round_total_tokens" not in fieldnames:
        summary = "Campaign tokens — token tracking not enabled (no token columns in results.tsv)"
        summary_path.write_text(summary + "\n")
        return summary

    def _int(row: dict, col: str) -> int:
        try:
            return int(row.get(col, 0) or 0)
        except (TypeError, ValueError):
            return 0

    totals = [_int(r, "round_total_tokens") for r in rows]
    historian_cols = [_int(r, "historian_tokens") for r in rows]

    grand_total = sum(totals)
    n_rounds = len(totals)
    avg_per_round = grand_total // n_rounds if n_rounds else 0

    historian_runs = [t for t in historian_cols if t > 0]
    historian_avg = sum(historian_runs) // len(historian_runs) if historian_runs else 0

    max_idx = totals.index(max(totals)) if totals else 0
    top_round = max_idx + 1
    top_cost = totals[max_idx] if totals else 0
    top_action = rows[max_idx].get("action_type", "unknown") if rows else "unknown"

    recent = totals[-10:]
    recent_avg = sum(recent) // len(recent) if recent else 0
    if avg_per_round == 0:
        trend = "stable"
    elif abs(recent_avg - avg_per_round) < avg_per_round * 0.20:
        trend = "stable"
    elif recent_avg > avg_per_round:
        trend = "rising"
    else:
        trend = "falling"

    summary = (
        f"Campaign tokens — total: {_fmt(grand_total)} | avg/round: {_fmt(avg_per_round)} | "
        f"historian avg: {_fmt(historian_avg)} | "
        f"top cost: r{top_round} ({top_action}, {_fmt(top_cost)}) | "
        f"trend: {trend} (last {len(recent)} rounds avg={_fmt(recent_avg)})"
    )
    summary_path.write_text(summary + "\n")
    return summary
