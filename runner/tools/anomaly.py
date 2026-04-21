"""Anomaly detector (spec §2.2.2).

Simplified port of abes_engine.cmd_check's anomaly branch — ~30 lines of
logic. Fires when the latest non-crash result is implausibly low relative
to an absolute floor and/or to the running best.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from runner.tools._common import EXIT_OK, EXIT_USER_ERROR, emit_json


def check_anomaly(
    latest_row: dict[str, Any],
    history: list[dict[str, Any]],
    floor: float = 0.75,
    primary_metric: str = "val_pr_auc",
    relative: float = 0.5,
) -> dict[str, Any]:
    """Return {'fired': bool, 'reason': str, 'proposed_diagnostic': str}.

    Fires if `status != 'crash'` AND 0 < latest[primary_metric] < max(floor, relative * best_prior).
    """
    status = latest_row.get("status", "")
    if status == "crash":
        return {
            "fired": False,
            "reason": "skipped (status=crash)",
            "proposed_diagnostic": "",
        }
    try:
        value = float(latest_row.get(primary_metric, 0.0))
    except (TypeError, ValueError):
        return {
            "fired": False,
            "reason": f"skipped (cannot parse {primary_metric})",
            "proposed_diagnostic": "",
        }
    best_prior = 0.0
    for row in history:
        if row.get("status") == "crash":
            continue
        try:
            best_prior = max(best_prior, float(row.get(primary_metric, 0.0)))
        except (TypeError, ValueError):
            continue
    threshold = max(floor, relative * best_prior) if best_prior > 0 else floor
    if 0 < value < threshold:
        family = latest_row.get("model_family", "unknown")
        return {
            "fired": True,
            "reason": f"{primary_metric}={value:.6f} below threshold={threshold:.6f} (floor={floor}, rel={relative}*best={best_prior:.6f})",
            "proposed_diagnostic": (
                f"Add `print(model.predict_proba(X_val[:5]))` to diagnose probability "
                f"inversion; do NOT dismiss {family} from one anomalous result."
            ),
        }
    return {
        "fired": False,
        "reason": f"{primary_metric}={value:.6f} within expected range (threshold={threshold:.6f})",
        "proposed_diagnostic": "",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Anomaly check for a single experiment result.")
    p.add_argument("--latest-json", required=True, help="JSON string or @path to file with the latest row dict.")
    p.add_argument("--history-json", default="[]", help="JSON string or @path with history list[dict].")
    p.add_argument("--floor", type=float, default=0.75)
    p.add_argument("--primary-metric", default="val_pr_auc")
    p.add_argument("--relative", type=float, default=0.5)
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)

    def _load(spec: str):
        if spec.startswith("@"):
            return json.loads(open(spec[1:]).read())
        return json.loads(spec)

    try:
        latest = _load(args.latest_json)
        history = _load(args.history_json)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    result = check_anomaly(
        latest_row=latest,
        history=history,
        floor=args.floor,
        primary_metric=args.primary_metric,
        relative=args.relative,
    )
    if args.json_output:
        emit_json(result)
    else:
        print(f"fired: {result['fired']}")
        print(f"reason: {result['reason']}")
        if result["proposed_diagnostic"]:
            print(f"proposed_diagnostic: {result['proposed_diagnostic']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
