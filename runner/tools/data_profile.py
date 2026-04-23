"""Data profiler (spec §2.2.1) — G2 support tool."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from runner.tools._common import EXIT_INTERNAL_ERROR, EXIT_OK, EXIT_USER_ERROR, emit_json


def data_profile(
    data_path: str,
    target_col: str,
    output_md: str = "runner/contracts/_data_profile.md",
) -> dict:
    p = Path(data_path)
    if not p.exists():
        raise FileNotFoundError(f"data file not found: {data_path}")
    df = pd.read_csv(p)
    if target_col not in df.columns:
        raise ValueError(f"target_col {target_col!r} not in columns: {list(df.columns)}")

    n_rows, n_cols = df.shape
    missingness = df.isna().sum().to_dict()
    target = df[target_col]
    target_dist = target.value_counts().to_dict()
    target_dist = {int(k) if isinstance(k, (int, float)) else str(k): int(v) for k, v in target_dist.items()}

    numeric_cols = [c for c in df.columns if c != target_col and pd.api.types.is_numeric_dtype(df[c])]
    numeric_stats = {}
    for c in numeric_cols:
        desc = df[c].describe()
        numeric_stats[c] = {
            "mean": float(desc["mean"]),
            "std": float(desc["std"]) if desc["count"] > 1 else 0.0,
            "min": float(desc["min"]),
            "q25": float(desc["25%"]),
            "q50": float(desc["50%"]),
            "q75": float(desc["75%"]),
            "max": float(desc["max"]),
        }

    result = {
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "missingness": {c: int(v) for c, v in missingness.items()},
        "target_col": target_col,
        "target_distribution": target_dist,
        "numeric_stats": numeric_stats,
    }

    out = Path(output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render_md(result))
    return result


def _render_md(res: dict) -> str:
    lines = [
        "# Data profile",
        "",
        f"- n_rows: {res['n_rows']}",
        f"- n_cols: {res['n_cols']}",
        f"- target_col: `{res['target_col']}`",
        f"- target_distribution: {res['target_distribution']}",
        "",
        "## Columns and dtypes",
        "",
    ]
    for c in res["columns"]:
        miss = res["missingness"][c]
        lines.append(f"- `{c}` — {res['dtypes'][c]} (missing: {miss})")
    lines.append("")
    lines.append("## Numeric statistics")
    lines.append("")
    for c, stats in res["numeric_stats"].items():
        lines.append(
            f"- `{c}` — mean={stats['mean']:.3f} std={stats['std']:.3f} "
            f"q[25/50/75]=({stats['q25']:.3f}/{stats['q50']:.3f}/{stats['q75']:.3f}) "
            f"range=[{stats['min']:.3f}, {stats['max']:.3f}]"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Data profile for a CSV.")
    p.add_argument("--data-path", required=True)
    p.add_argument("--target-col", required=True)
    p.add_argument("--output-md", default="runner/contracts/_data_profile.md")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = data_profile(args.data_path, args.target_col, args.output_md)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"INTERNAL ERROR: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.json_output:
        emit_json(res)
    else:
        print(f"Wrote profile to {args.output_md} (n_rows={res['n_rows']}, n_cols={res['n_cols']})")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
