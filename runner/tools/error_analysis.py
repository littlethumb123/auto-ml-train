"""Systematic error analysis — bucketize model failures into actionable patterns.

Given y_true, y_prob, and a feature DataFrame, identifies:
1. False positives: what do FP cases look like? (feature distributions)
2. False negatives: what do FN cases look like?
3. Probability calibration: are predicted probabilities well-calibrated?
4. Recommendations: specific feature engineering or model changes to address patterns.

Usage:
    python -m runner.tools.error_analysis \\
        --y-true artifacts/y_val_true.npy \\
        --y-prob artifacts/y_val_prob.npy \\
        --features artifacts/X_val.csv \\
        --threshold 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import numpy as np
import pandas as pd


def _describe_numeric(series: pd.Series) -> dict:
    """Compact numeric summary."""
    return {
        "mean": float(series.mean()),
        "median": float(series.median()),
        "std": float(series.std()) if len(series) > 1 else 0.0,
        "min": float(series.min()),
        "max": float(series.max()),
    }


def _describe_categorical(series: pd.Series, top_n: int = 5) -> dict:
    """Top-N value counts for categorical column."""
    vc = series.value_counts().head(top_n)
    return {
        "top_values": {str(k): int(v) for k, v in vc.items()},
        "n_unique": int(series.nunique()),
    }


def _feature_patterns(
    subset: pd.DataFrame,
    baseline: pd.DataFrame,
) -> list[dict]:
    """Compare feature distributions between an error subset and the full dataset."""
    patterns = []
    for col in subset.columns:
        entry: dict[str, Any] = {"feature": col}
        if pd.api.types.is_numeric_dtype(subset[col]):
            entry["type"] = "numeric"
            entry["error_subset"] = _describe_numeric(subset[col].dropna())
            entry["baseline"] = _describe_numeric(baseline[col].dropna())
            base_std = baseline[col].std()
            if base_std > 0:
                diff = abs(subset[col].mean() - baseline[col].mean()) / base_std
                entry["z_diff"] = round(float(diff), 3)
            else:
                entry["z_diff"] = 0.0
        else:
            entry["type"] = "categorical"
            entry["error_subset"] = _describe_categorical(subset[col])
            entry["baseline"] = _describe_categorical(baseline[col])
            entry["z_diff"] = 0.0
        patterns.append(entry)

    patterns.sort(key=lambda x: abs(x.get("z_diff", 0)), reverse=True)
    return patterns


def _calibration_buckets(y_true: np.ndarray, y_prob: np.ndarray, n_buckets: int = 10) -> list[dict]:
    """Bucketize predictions and compare predicted vs actual positive rate."""
    buckets = []
    edges = np.linspace(0, 1, n_buckets + 1)
    for i in range(n_buckets):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi) if i < n_buckets - 1 else (y_prob >= lo) & (y_prob <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        actual_rate = float(y_true[mask].mean())
        pred_mean = float(y_prob[mask].mean())
        buckets.append({
            "bucket": f"[{lo:.1f}, {hi:.1f})",
            "n_samples": n,
            "predicted_mean": round(pred_mean, 4),
            "actual_positive_rate": round(actual_rate, 4),
            "calibration_gap": round(abs(pred_mean - actual_rate), 4),
        })
    return buckets


def _generate_recommendations(
    fp_patterns: list[dict],
    fn_patterns: list[dict],
    fp_count: int,
    fn_count: int,
    calibration: list[dict],
) -> list[str]:
    """Generate actionable recommendations from error analysis."""
    recs = []

    fp_top = [p for p in fp_patterns if p.get("z_diff", 0) > 1.5 and p["type"] == "numeric"]
    fn_top = [p for p in fn_patterns if p.get("z_diff", 0) > 1.5 and p["type"] == "numeric"]

    if fp_top:
        names = [p["feature"] for p in fp_top[:3]]
        recs.append(
            f"FP concentration: features {names} differ significantly in FP subset. "
            f"Consider interaction features or binning to help model distinguish."
        )

    if fn_top:
        names = [p["feature"] for p in fn_top[:3]]
        recs.append(
            f"FN concentration: features {names} differ significantly in FN subset. "
            f"Consider adding derived features or group-by aggregations on these."
        )

    if fp_count > 0 and fn_count > 0:
        ratio = fp_count / max(fn_count, 1)
        if ratio > 3:
            recs.append(
                f"FP/FN ratio = {ratio:.1f}: model is over-predicting positives. "
                f"Consider raising threshold or adjusting class weights."
            )
        elif ratio < 0.33:
            recs.append(
                f"FP/FN ratio = {ratio:.1f}: model is missing positives. "
                f"Consider lowering threshold or adjusting class weights."
            )

    worst_cal = max(calibration, key=lambda x: x["calibration_gap"], default=None)
    if worst_cal and worst_cal["calibration_gap"] > 0.15:
        recs.append(
            f"Calibration gap of {worst_cal['calibration_gap']:.2f} in bucket {worst_cal['bucket']}. "
            f"Consider Platt scaling or isotonic regression."
        )

    if not recs:
        recs.append("No strong error patterns detected. Consider ensemble or HP tuning.")

    return recs


def analyze_errors(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    features: pd.DataFrame,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Run systematic error analysis on model predictions.

    Args:
        y_true: Ground truth labels (0/1).
        y_prob: Predicted probabilities.
        features: Feature DataFrame (same rows as y_true/y_prob).
        threshold: Classification threshold.

    Returns:
        Dict with 'fp_analysis', 'fn_analysis', 'summary' keys.
    """
    y_pred = (y_prob >= threshold).astype(int)

    fp_mask = (y_pred == 1) & (y_true == 0)
    fn_mask = (y_pred == 0) & (y_true == 1)
    tp_mask = (y_pred == 1) & (y_true == 1)
    tn_mask = (y_pred == 0) & (y_true == 0)

    fp_count = int(fp_mask.sum())
    fn_count = int(fn_mask.sum())

    fp_patterns = _feature_patterns(features[fp_mask], features) if fp_count > 0 else []
    fn_patterns = _feature_patterns(features[fn_mask], features) if fn_count > 0 else []

    calibration = _calibration_buckets(y_true, y_prob)
    recommendations = _generate_recommendations(
        fp_patterns, fn_patterns, fp_count, fn_count, calibration,
    )

    return {
        "fp_analysis": {
            "count": fp_count,
            "feature_patterns": fp_patterns[:10],
        },
        "fn_analysis": {
            "count": fn_count,
            "feature_patterns": fn_patterns[:10],
        },
        "summary": {
            "total_samples": len(y_true),
            "positives": int(y_true.sum()),
            "negatives": int((1 - y_true).sum()),
            "tp": int(tp_mask.sum()),
            "fp": fp_count,
            "fn": fn_count,
            "tn": int(tn_mask.sum()),
            "threshold": threshold,
            "prob_calibration_buckets": calibration,
            "recommendations": recommendations,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Systematic error analysis")
    parser.add_argument("--y-true", required=True, help="Path to y_true .npy file")
    parser.add_argument("--y-prob", required=True, help="Path to y_prob .npy file")
    parser.add_argument("--features", required=True, help="Path to features CSV")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    y_true = np.load(args.y_true)
    y_prob = np.load(args.y_prob)
    features = pd.read_csv(args.features)

    result = analyze_errors(y_true, y_prob, features, threshold=args.threshold)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
