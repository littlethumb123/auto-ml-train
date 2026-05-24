"""Validated ML code templates — copy-pasteable building blocks.

Each function is a self-contained, tested transformation that the Executor
can adapt into train.py.  Functions operate on numpy arrays and pandas
DataFrames; they never touch disk or global state.

Usage by Executor:
    from runner.strategy.templates import target_encode, group_agg_features
    # Then adapt the call into train.py's feature engineering section.

Usage by Planner:
    catalog = templates.get_catalog()
    # Returns list of {"name", "category", "description", "usage"} dicts.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Encoding templates
# ---------------------------------------------------------------------------

def target_encode(
    train: pd.DataFrame,
    val: pd.DataFrame,
    columns: list[str],
    target: str,
    min_samples: int = 10,
    smoothing: float = 5.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Smoothed target encoding fit on train, applied to train+val.

    Smoothing formula:
        weight = count / (count + smoothing)
        encoded = weight * category_mean + (1 - weight) * global_mean

    Unseen categories in val get the global mean.

    Args:
        train: Training DataFrame (must contain target column).
        val: Validation DataFrame (same columns minus target).
        columns: Categorical columns to encode.
        target: Name of the binary target column.
        min_samples: Minimum samples for a category to use its own mean.
        smoothing: Smoothing factor (higher = more regularization).

    Returns:
        (train_encoded, val_encoded) with new columns named '{col}_te'.
    """
    train_out = train.copy()
    val_out = val.copy()
    global_mean = train[target].mean()

    for col in columns:
        stats = train.groupby(col)[target].agg(["mean", "count"])
        weight = stats["count"] / (stats["count"] + smoothing)
        smoothed = weight * stats["mean"] + (1 - weight) * global_mean
        smoothed[stats["count"] < min_samples] = global_mean
        mapping = smoothed.to_dict()

        new_col = f"{col}_te"
        train_out[new_col] = train[col].map(mapping).fillna(global_mean)
        val_out[new_col] = val[col].map(mapping).fillna(global_mean)

    return train_out, val_out


def frequency_encode(
    train: pd.DataFrame,
    val: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Frequency encoding: replace category with its proportion in training data.

    Unseen categories in val get 0.

    Args:
        train: Training DataFrame.
        val: Validation DataFrame.
        columns: Columns to encode.

    Returns:
        (train_encoded, val_encoded) with new columns named '{col}_freq'.
    """
    train_out = train.copy()
    val_out = val.copy()

    for col in columns:
        freq = train[col].value_counts(normalize=True)
        mapping = freq.to_dict()
        new_col = f"{col}_freq"
        train_out[new_col] = train[col].map(mapping).fillna(0.0)
        val_out[new_col] = val[col].map(mapping).fillna(0.0)

    return train_out, val_out


# ---------------------------------------------------------------------------
# Group aggregation templates
# ---------------------------------------------------------------------------

def group_agg_features(
    df: pd.DataFrame,
    group_col: str,
    agg_cols: list[str],
    agg_funcs: list[str] | None = None,
) -> pd.DataFrame:
    """Add group-level aggregation features (in-place, single DataFrame).

    For train/val split scenarios, use fit_group_agg + transform_group_agg instead.

    Args:
        df: Input DataFrame.
        group_col: Column to group by.
        agg_cols: Numeric columns to aggregate.
        agg_funcs: Aggregation functions (default: ["mean", "std"]).

    Returns:
        DataFrame with new columns named '{agg_col}_by_{group_col}_{func}'.
    """
    if agg_funcs is None:
        agg_funcs = ["mean", "std"]

    result = df.copy()
    for col in agg_cols:
        for func in agg_funcs:
            new_col = f"{col}_by_{group_col}_{func}"
            result[new_col] = result.groupby(group_col)[col].transform(func)
    return result


def fit_group_agg(
    train: pd.DataFrame,
    group_col: str,
    agg_cols: list[str],
    agg_funcs: list[str] | None = None,
) -> dict:
    """Fit group aggregation statistics on training data only.

    Returns a mapping dict to apply with transform_group_agg.
    """
    if agg_funcs is None:
        agg_funcs = ["mean", "std"]

    agg_map: dict = {"group_col": group_col, "mappings": {}}
    for col in agg_cols:
        for func in agg_funcs:
            key = f"{col}_by_{group_col}_{func}"
            stats = train.groupby(group_col)[col].agg(func)
            agg_map["mappings"][key] = {"col": col, "func": func, "values": stats.to_dict()}
    return agg_map


def transform_group_agg(
    df: pd.DataFrame,
    agg_map: dict,
    group_col: str,
) -> pd.DataFrame:
    """Apply pre-fit group aggregation to a new DataFrame.

    Unseen groups get NaN.
    """
    result = df.copy()
    for key, info in agg_map["mappings"].items():
        result[key] = df[group_col].map(info["values"])
    return result


# ---------------------------------------------------------------------------
# Outlier handling
# ---------------------------------------------------------------------------

def clip_outliers(
    arr: np.ndarray,
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> np.ndarray:
    """Clip values to percentile bounds (winsorize).

    Args:
        arr: 1-D numeric array.
        lower_pct: Lower percentile (0-1).
        upper_pct: Upper percentile (0-1).

    Returns:
        Clipped array.
    """
    lo = np.percentile(arr, lower_pct * 100)
    hi = np.percentile(arr, upper_pct * 100)
    return np.clip(arr, lo, hi)


# ---------------------------------------------------------------------------
# Missing value indicators
# ---------------------------------------------------------------------------

def add_missing_indicators(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Add binary indicator columns for missingness.

    Args:
        df: Input DataFrame.
        columns: Columns to create indicators for.

    Returns:
        DataFrame with new '{col}_missing' columns (1=missing, 0=present).
    """
    result = df.copy()
    for col in columns:
        result[f"{col}_missing"] = df[col].isna().astype(int)
    return result


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def temporal_split(
    df: pd.DataFrame,
    time_col: str,
    train_end: str,
    val_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split DataFrame by time column into train and validation.

    Args:
        df: Input DataFrame with a datetime-like column.
        time_col: Name of the time column.
        train_end: Cutoff date string for training (exclusive).
        val_end: End date for validation (inclusive).

    Returns:
        (train, val) DataFrames.
    """
    ts = pd.to_datetime(df[time_col])
    train_mask = ts < pd.Timestamp(train_end)
    val_mask = (ts >= pd.Timestamp(train_end)) & (ts <= pd.Timestamp(val_end))
    return df[train_mask].copy(), df[val_mask].copy()


# ---------------------------------------------------------------------------
# Seed averaging
# ---------------------------------------------------------------------------

def seed_average(predictions: list[np.ndarray]) -> np.ndarray:
    """Average predictions from multiple random seeds.

    Args:
        predictions: List of prediction arrays (same shape).

    Returns:
        Element-wise mean of all prediction arrays.
    """
    return np.mean(np.stack(predictions), axis=0)


# ---------------------------------------------------------------------------
# Catalog — machine-readable index of available templates
# ---------------------------------------------------------------------------

def get_catalog() -> list[dict]:
    """Return a list of all available templates with metadata.

    Each entry: {"name", "category", "description", "usage"}.
    The Planner reads this to know what templates the Executor can use.
    """
    return [
        {
            "name": "target_encode",
            "category": "encoding",
            "description": "Smoothed target encoding with regularization. Prevents leakage via train-only fitting.",
            "usage": "train_enc, val_enc = templates.target_encode(train, val, columns=['cat_col'], target='y')",
        },
        {
            "name": "frequency_encode",
            "category": "encoding",
            "description": "Replace categories with their frequency proportion in training data.",
            "usage": "train_enc, val_enc = templates.frequency_encode(train, val, columns=['cat_col'])",
        },
        {
            "name": "group_agg_features",
            "category": "aggregation",
            "description": "Group-by aggregation features (mean, std, etc.). Core Kaggle winner pattern.",
            "usage": "df = templates.group_agg_features(df, group_col='entity', agg_cols=['amount'], agg_funcs=['mean','std'])",
        },
        {
            "name": "fit_group_agg / transform_group_agg",
            "category": "aggregation",
            "description": "Train/val safe group aggregation: fit on train, transform val (unseen groups get NaN).",
            "usage": "agg_map = templates.fit_group_agg(train, ...); val = templates.transform_group_agg(val, agg_map, ...)",
        },
        {
            "name": "clip_outliers",
            "category": "preprocessing",
            "description": "Winsorize outliers to percentile bounds.",
            "usage": "arr = templates.clip_outliers(arr, lower_pct=0.01, upper_pct=0.99)",
        },
        {
            "name": "add_missing_indicators",
            "category": "preprocessing",
            "description": "Binary indicator columns for missing values. Often adds signal for tree models.",
            "usage": "df = templates.add_missing_indicators(df, columns=['col_a', 'col_b'])",
        },
        {
            "name": "temporal_split",
            "category": "validation",
            "description": "Time-based train/val split. Production standard for temporal data.",
            "usage": "train, val = templates.temporal_split(df, time_col='date', train_end='2024-01-01', val_end='2024-06-01')",
        },
        {
            "name": "seed_average",
            "category": "ensemble",
            "description": "Average predictions from N random seeds. Reduces variance with zero complexity.",
            "usage": "avg_preds = templates.seed_average([preds_seed1, preds_seed2, preds_seed3])",
        },
    ]
