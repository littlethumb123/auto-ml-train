"""Baseline runner (spec §2.2.1) — G3 support tool.

Runs a minimal baseline with the metric + CV scheme from EVAL_PROTOCOL.md.
Supported families for MVP: logreg, xgboost, rf, kmeans (clustering). This
is NOT a search — just a sanity baseline.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold

from runner.tools._common import (
    EXIT_CONTRACT_VIOLATION,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_USER_ERROR,
    FrontmatterError,
    emit_json,
    parse_frontmatter,
)

_METRIC_FNS = {
    "pr_auc": lambda y_true, y_score: float(average_precision_score(y_true, y_score)),
    "roc_auc": lambda y_true, y_score: float(roc_auc_score(y_true, y_score)),
    "val_pr_auc": lambda y_true, y_score: float(average_precision_score(y_true, y_score)),
}


def _build_model(family: str):
    if family == "logreg":
        return LogisticRegression(max_iter=500, class_weight="balanced", solver="liblinear")
    if family == "rf":
        return RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, class_weight="balanced")
    if family == "xgboost":
        import xgboost as xgb

        return xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", random_state=42, n_jobs=-1,
        )
    raise ValueError(f"unsupported family: {family!r}")


def baseline_runner(
    family: str,
    eval_protocol_path: str,
    data_path: str,
    target_col: str,
    output_path: str = "runner/state/_baseline.json",
) -> dict[str, Any]:
    fm, _ = parse_frontmatter(Path(eval_protocol_path))
    metric_name = (fm.get("primary_metric") or {}).get("name", "pr_auc")
    if metric_name not in _METRIC_FNS:
        raise _ProtocolError(f"metric {metric_name!r} not supported by baseline_runner MVP")
    metric_fn = _METRIC_FNS[metric_name]
    cv = fm.get("cv_scheme") or {}
    scheme = cv.get("type", "single_holdout")
    n_splits = int(cv.get("n_splits", 1))
    random_state = int(cv.get("random_state", 42))

    df = pd.read_csv(data_path)
    if target_col not in df.columns:
        raise ValueError(f"target_col {target_col!r} not in data")
    X = df.drop(columns=[target_col])
    y = df[target_col].astype(int)

    fold_scores: list[float] = []
    t0 = time.time()
    if scheme == "single_holdout":
        from sklearn.model_selection import train_test_split

        X_tr, X_va, y_tr, y_va = train_test_split(X, y, test_size=0.2, stratify=y, random_state=random_state)
        model = _build_model(family)
        model.fit(X_tr, y_tr)
        y_score = model.predict_proba(X_va)[:, 1]
        fold_scores.append(metric_fn(y_va, y_score))
    else:
        if scheme == "stratified_kfold":
            splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        elif scheme == "kfold":
            splitter = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        else:
            raise _ProtocolError(f"unsupported cv_scheme.type: {scheme!r}")
        for tr_idx, va_idx in splitter.split(X, y):
            model = _build_model(family)
            model.fit(X.iloc[tr_idx], y.iloc[tr_idx])
            y_score = model.predict_proba(X.iloc[va_idx])[:, 1]
            fold_scores.append(metric_fn(y.iloc[va_idx], y_score))
    runtime_s = time.time() - t0
    mean = float(np.mean(fold_scores))
    std = float(np.std(fold_scores, ddof=1)) if len(fold_scores) > 1 else 0.0
    result = {
        "family": family,
        "metric_name": metric_name,
        "metric_value": mean,
        "metric_ci": [mean - 1.96 * std / max(1, len(fold_scores)) ** 0.5,
                      mean + 1.96 * std / max(1, len(fold_scores)) ** 0.5],
        "fold_scores": fold_scores,
        "runtime_s": runtime_s,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    return result


class _ProtocolError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Baseline family runner (G3 support).")
    p.add_argument("--family", required=True, choices=["logreg", "rf", "xgboost"])
    p.add_argument("--eval-protocol-path", required=True)
    p.add_argument("--data-path", required=True)
    p.add_argument("--target-col", required=True)
    p.add_argument("--output-path", default="runner/state/_baseline.json")
    p.add_argument("--json", action="store_true", dest="json_output")
    args = p.parse_args(argv)
    try:
        res = baseline_runner(
            family=args.family,
            eval_protocol_path=args.eval_protocol_path,
            data_path=args.data_path,
            target_col=args.target_col,
            output_path=args.output_path,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except (FrontmatterError, _ProtocolError) as exc:
        print(f"CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return EXIT_CONTRACT_VIOLATION
    except Exception as exc:  # noqa: BLE001
        print(f"INTERNAL ERROR: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.json_output:
        emit_json(res)
    else:
        print(f"{res['family']} {res['metric_name']}={res['metric_value']:.4f} ({res['runtime_s']:.1f}s)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
