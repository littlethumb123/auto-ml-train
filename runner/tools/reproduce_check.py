"""Reproduce-check tool (GAP 10 — experiment reproducibility verification).

Recomputes metrics from saved prediction artifacts (y_val_true.npy,
y_val_prob.npy) and compares against self-reported values in run.log.
Catches silent metric corruption, log fabrication, and prediction artifacts
that don't match reported numbers.

Usage:
    python -m runner.tools.reproduce_check \
        --y-true artifacts/y_val_true.npy \
        --y-prob artifacts/y_val_prob.npy \
        --run-log run.log \
        --tolerance 0.001 \
        --json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

# import lazily to avoid circular deps
_METRIC_LINE_RE = re.compile(r"^([\w_]+):\s*([\d.eE+-]+)\s*$", re.MULTILINE)


def _parse_reported_metrics(run_log_text: str) -> dict[str, float]:
    """Extract key: value metric lines from run.log."""
    metrics: dict[str, float] = {}
    for m in _METRIC_LINE_RE.finditer(run_log_text):
        try:
            metrics[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    return metrics


def _recompute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    """Recompute standard metrics from prediction arrays."""
    from shared.metrics import lift_at_percentage

    result: dict[str, float] = {}
    result["val_auc_pr"] = float(average_precision_score(y_true, y_prob))
    result["val_pr_auc"] = result["val_auc_pr"]  # alias
    try:
        result["val_auc_roc"] = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        pass
    result["val_lift_1pct"] = float(lift_at_percentage(y_true, y_prob, 0.01))
    result["val_lift_5pct"] = float(lift_at_percentage(y_true, y_prob, 0.05))
    result["val_lift_10pct"] = float(lift_at_percentage(y_true, y_prob, 0.10))
    result["lift_at_10"] = float(lift_at_percentage(y_true, y_prob, 0.10))
    return result


def _validate_predictions(y_true: np.ndarray, y_prob: np.ndarray) -> list[str]:
    """Validate prediction arrays for well-formedness."""
    issues: list[str] = []
    if y_true.shape != y_prob.shape:
        issues.append(f"Shape mismatch: y_true={y_true.shape}, y_prob={y_prob.shape}")
    if np.isnan(y_prob).any():
        issues.append(f"y_prob contains {np.isnan(y_prob).sum()} NaN values")
    if y_prob.min() < 0.0 or y_prob.max() > 1.0:
        issues.append(f"y_prob out of [0,1]: min={y_prob.min():.6f}, max={y_prob.max():.6f}")
    if y_prob.std() < 1e-8:
        issues.append(f"y_prob near-constant: std={y_prob.std():.2e}")
    pos_count = int(y_true.sum())
    if pos_count == 0:
        issues.append("y_true has 0 positives — metrics are undefined")
    return issues


def reproduce_check(
    y_true_path: str | Path,
    y_prob_path: str | Path,
    run_log_path: str | Path | None = None,
    tolerance: float = 0.001,
) -> dict[str, Any]:
    """Run the reproduction check.

    Returns:
        {
            "artifacts_valid": bool,
            "validation_issues": [...],
            "recomputed": {metric: value, ...},
            "reported": {metric: value, ...},
            "mismatches": [{metric, reported, recomputed, delta}, ...],
            "passed": bool,
        }
    """
    y_true = np.load(y_true_path)
    y_prob = np.load(y_prob_path)

    validation_issues = _validate_predictions(y_true, y_prob)
    if validation_issues:
        return {
            "artifacts_valid": False,
            "validation_issues": validation_issues,
            "recomputed": {},
            "reported": {},
            "mismatches": [],
            "passed": False,
        }

    recomputed = _recompute_metrics(y_true, y_prob)

    reported: dict[str, float] = {}
    if run_log_path:
        log_path = Path(run_log_path)
        if log_path.exists():
            reported = _parse_reported_metrics(log_path.read_text())

    mismatches: list[dict[str, Any]] = []
    for metric_name, recomp_val in recomputed.items():
        if metric_name in reported:
            rep_val = reported[metric_name]
            delta = abs(recomp_val - rep_val)
            if delta > tolerance:
                mismatches.append({
                    "metric": metric_name,
                    "reported": round(rep_val, 6),
                    "recomputed": round(recomp_val, 6),
                    "delta": round(delta, 6),
                })

    return {
        "artifacts_valid": True,
        "validation_issues": [],
        "recomputed": {k: round(v, 6) for k, v in recomputed.items()},
        "reported": {k: round(v, 6) for k, v in reported.items()},
        "mismatches": mismatches,
        "passed": len(mismatches) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Recompute metrics from prediction artifacts.")
    p.add_argument("--y-true", required=True, help="Path to y_val_true.npy")
    p.add_argument("--y-prob", required=True, help="Path to y_val_prob.npy")
    p.add_argument("--run-log", default=None, help="Path to run.log for comparison")
    p.add_argument("--tolerance", type=float, default=0.001)
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    result = reproduce_check(args.y_true, args.y_prob, args.run_log, args.tolerance)

    if args.json_output:
        json.dump(result, sys.stdout, separators=(",", ":"), sort_keys=True)
        sys.stdout.write("\n")
    else:
        if not result["artifacts_valid"]:
            print("  ✗ Artifact validation failed:")
            for issue in result["validation_issues"]:
                print(f"    - {issue}")
        elif result["passed"]:
            print(f"  ✓ Metrics match (tolerance={args.tolerance})")
        else:
            print("  ✗ Metric mismatches:")
            for mm in result["mismatches"]:
                print(f"    {mm['metric']}: reported={mm['reported']}, recomputed={mm['recomputed']} (Δ={mm['delta']})")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
