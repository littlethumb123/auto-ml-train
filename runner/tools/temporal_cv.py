"""Temporal (time-based) cross-validation — production-standard validation for time-series.

Splits data chronologically with expanding training windows and optional gap periods
to prevent leakage from adjacent time periods.

Usage:
    python -m runner.tools.temporal_cv \\
        --dates-col time \\
        --n-splits 3 \\
        --train-ratio 0.6 \\
        --gap-days 30
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

import numpy as np
import pandas as pd


def temporal_cv_splits(
    dates: pd.DatetimeIndex | pd.Series,
    n_splits: int = 3,
    train_ratio: float = 0.6,
    gap_days: int = 0,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Generate temporal cross-validation split indices.

    Uses expanding window: each successive fold has more training data.
    Validation window slides forward in time.

    Args:
        dates: DatetimeIndex or Series of timestamps (one per row).
        n_splits: Number of CV folds.
        train_ratio: Minimum fraction of data for the first training fold.
        gap_days: Number of days gap between train end and val start (prevent leakage).

    Returns:
        List of (train_indices, val_indices) tuples.
    """
    if not isinstance(dates, pd.DatetimeIndex):
        dates = pd.DatetimeIndex(dates)

    sorted_idx = np.argsort(dates)
    sorted_dates = dates[sorted_idx]
    n = len(sorted_dates)

    # Calculate fold boundaries
    min_train = int(n * train_ratio)
    remaining = n - min_train
    val_size = remaining // (n_splits)

    if val_size < 1:
        val_size = 1

    splits = []
    for i in range(n_splits):
        # Expanding training window
        train_end_idx = min_train + i * val_size
        val_start_idx = train_end_idx
        val_end_idx = min(train_end_idx + val_size, n)

        if val_start_idx >= n or val_end_idx <= val_start_idx:
            break

        # Apply gap
        if gap_days > 0:
            train_end_date = sorted_dates[train_end_idx - 1]
            gap_cutoff = train_end_date + pd.Timedelta(days=gap_days)
            # Find first val index after gap
            gap_mask = sorted_dates[val_start_idx:val_end_idx] >= gap_cutoff
            if not gap_mask.any():
                continue  # Gap too large for this fold
            gap_offset = np.argmax(np.asarray(gap_mask))
            val_start_idx = val_start_idx + gap_offset

        if val_start_idx >= val_end_idx:
            continue

        train_indices = sorted_idx[:train_end_idx]
        val_indices = sorted_idx[val_start_idx:val_end_idx]

        splits.append((train_indices, val_indices))

    return splits


def temporal_cv_evaluate(
    X: pd.DataFrame,
    y: np.ndarray | pd.Series,
    dates: pd.DatetimeIndex | pd.Series,
    n_splits: int = 3,
    train_ratio: float = 0.6,
    gap_days: int = 0,
    metric_fn: Callable[[np.ndarray, np.ndarray], float] | None = None,
    model_factory: Callable | None = None,
) -> dict[str, Any]:
    """Run temporal CV and collect per-fold metrics.

    Args:
        X: Feature DataFrame.
        y: Target array/Series.
        dates: Timestamps for temporal ordering.
        n_splits: Number of folds.
        train_ratio: Minimum training fraction.
        gap_days: Gap between train/val.
        metric_fn: Function(y_true, y_prob) -> float. Defaults to average_precision_score.
        model_factory: Callable that returns a fresh sklearn-compatible model.

    Returns:
        {"fold_metrics": [...], "mean_metric": float, "std_metric": float}
    """
    if metric_fn is None:
        from sklearn.metrics import average_precision_score
        metric_fn = average_precision_score

    if model_factory is None:
        from sklearn.linear_model import LogisticRegression
        model_factory = lambda: LogisticRegression(max_iter=200)

    y_arr = np.asarray(y)
    splits = temporal_cv_splits(dates, n_splits, train_ratio, gap_days)

    fold_metrics = []
    for i, (train_idx, val_idx) in enumerate(splits):
        X_train = X.iloc[train_idx] if isinstance(X, pd.DataFrame) else X[train_idx]
        X_val = X.iloc[val_idx] if isinstance(X, pd.DataFrame) else X[val_idx]
        y_train = y_arr[train_idx]
        y_val = y_arr[val_idx]

        model = model_factory()
        model.fit(X_train, y_train)

        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_val)[:, 1]
        else:
            y_prob = model.predict(X_val)

        score = metric_fn(y_val, y_prob)
        fold_metrics.append(float(score))

    return {
        "fold_metrics": fold_metrics,
        "mean_metric": float(np.mean(fold_metrics)) if fold_metrics else 0.0,
        "std_metric": float(np.std(fold_metrics)) if fold_metrics else 0.0,
        "n_splits_used": len(fold_metrics),
    }


def main():
    parser = argparse.ArgumentParser(description="Temporal cross-validation splits")
    parser.add_argument("--n-splits", type=int, default=3)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--gap-days", type=int, default=0)
    parser.add_argument("--dates-col", default="time")
    args = parser.parse_args()

    config = {
        "n_splits": args.n_splits,
        "train_ratio": args.train_ratio,
        "gap_days": args.gap_days,
        "dates_col": args.dates_col,
    }
    json.dump(config, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
