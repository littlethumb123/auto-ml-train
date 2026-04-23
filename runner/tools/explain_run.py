"""Run card builder (spec §2.2.3) — on-demand."""
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


def explain_run(
    commit: str,
    output_path: str = "runner/state/run_card.md",
    campaign_dir: str = "runner/",
) -> str:
    camp = Path(campaign_dir)
    results = camp / "state" / "results.tsv"
    if not results.exists():
        raise FileNotFoundError(f"results.tsv not found at {results}")
    df = pd.read_csv(results, sep="\t")
    rows = df[df["commit"].astype(str) == commit]
    if rows.empty:
        raise LookupError(f"commit {commit!r} not found in results.tsv")
    row = rows.iloc[-1].to_dict()

    next_exp = camp / "state" / "NEXT_EXPERIMENT.md"
    next_exp_excerpt = ""
    if next_exp.exists():
        next_exp_excerpt = next_exp.read_text()[:2000]

    lines = [
        f"# Run card — {commit}",
        "",
        f"- action_type: `{row.get('action_type', '?')}`",
        f"- model_family: `{row.get('model_family', '?')}`",
        f"- status: `{row.get('status', '?')}`",
        f"- hypothesis: {row.get('hypothesis', '')}",
        f"- description: {row.get('description', '')}",
        "",
        "## Metrics",
        "",
        f"- val_pr_auc: {row.get('val_pr_auc', '?')}",
        f"- lift_at_10: {row.get('lift_at_10', '?')}",
        f"- macro_f1: {row.get('macro_f1', '?')}",
        f"- val_f1: {row.get('val_f1', '?')}",
        f"- n_features: {row.get('n_features', '?')}",
        "",
    ]
    if next_exp_excerpt:
        lines += ["## NEXT_EXPERIMENT.md (at time of run)", "", "```", next_exp_excerpt, "```", ""]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    return str(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate a run card for a commit.")
    p.add_argument("--commit", required=True)
    p.add_argument("--output-path", default="runner/state/run_card.md")
    p.add_argument("--campaign-dir", default="runner/")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        path = explain_run(args.commit, args.output_path, args.campaign_dir)
    except LookupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    if args.json_output:
        emit_json({"path": path})
    else:
        print(path)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
