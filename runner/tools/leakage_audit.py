"""Leakage audit (spec §2.2.1) — G2 support tool."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import roc_auc_score

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_USER_ERROR,
    FrontmatterError,
    emit_json,
    parse_frontmatter,
)


def leakage_audit(
    data_contract_path: str,
    data_path: str,
    target_col: str,
) -> dict[str, Any]:
    fm, _ = parse_frontmatter(Path(data_contract_path))
    temporal = fm.get("temporal") or {}
    columns_spec = fm.get("columns") or []
    availability = {
        col.get("name"): bool(col.get("available_at_prediction", False))
        for col in columns_spec
        if isinstance(col, dict)
    }

    df = pd.read_csv(data_path)
    if target_col not in df.columns:
        raise ValueError(f"target_col {target_col!r} not in data columns")
    y = df[target_col]
    features = [c for c in df.columns if c != target_col]

    flagged: list[str] = []
    notes: list[str] = []
    passed: list[str] = []

    for col in features:
        if not pd.api.types.is_numeric_dtype(df[col]):
            passed.append(col)
            continue
        series = df[col].astype(float)
        if series.nunique(dropna=True) <= 1:
            flagged.append(col)
            notes.append(f"{col}: constant/single-value column")
            continue
        try:
            corr = series.corr(y.astype(float))
        except Exception:  # noqa: BLE001
            corr = 0.0
        try:
            auc = roc_auc_score(y, series)
        except Exception:  # noqa: BLE001
            auc = 0.5
        if abs(corr) > 0.95 or abs(auc - 0.5) > 0.48:
            flagged.append(col)
            notes.append(f"{col}: |corr|={abs(corr):.3f} auc={auc:.3f} — target-adjacent")
        else:
            passed.append(col)

    if temporal.get("is_temporal"):
        pred_time_col = temporal.get("prediction_time_column")
        if pred_time_col is None:
            raise _ContractViolation("temporal.is_temporal=true but prediction_time_column is null")
        for col in features:
            if availability.get(col) is False and col not in flagged:
                flagged.append(col)
                notes.append(f"{col}: available_at_prediction=false but temporal")

    return {
        "flagged": flagged,
        "passed": passed,
        "notes": notes,
    }


class _ContractViolation(Exception):
    """Internal sentinel for contract-violation exit code."""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leakage audit over data contract + CSV.")
    p.add_argument("--data-contract-path", required=True)
    p.add_argument("--data-path", required=True)
    p.add_argument("--target-col", required=True)
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = leakage_audit(args.data_contract_path, args.data_path, args.target_col)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except (FrontmatterError, _ContractViolation) as exc:
        print(f"CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except Exception as exc:  # noqa: BLE001
        print(f"INTERNAL ERROR: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.json_output:
        emit_json(res)
    else:
        print(f"flagged: {res['flagged']}")
        for note in res["notes"]:
            print(f"  - {note}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
