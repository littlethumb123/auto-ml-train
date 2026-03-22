"""
Frozen evaluation and data infrastructure for auto_train experiments.

DO NOT MODIFY this file. It contains the fixed evaluation contract.
The agent may only read from this module — never write to it.

Provides:
    - Constants (TIME_BUDGET, RANDOM_SEED, splits, etc.)
    - load_data() — loads and cleans the credit card dataset
    - get_splits() — returns stratified train/val/test splits (fixed seed)
    - get_feature_names() — returns feature column names
    - evaluate(model, X_val, y_val) — computes PR-AUC + secondary metrics
    - print_summary(metrics, training_time, total_time, n_features, description)

Usage:
    from prepare import get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    f1_score,
    precision_score,
    recall_score,
)

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants (fixed, do not modify)
# ---------------------------------------------------------------------------

TIME_BUDGET = 60            # seconds per experiment
RANDOM_SEED = 42            # reproducibility seed for all splits
TEST_SIZE = 0.20            # fraction held out for final test
VAL_SIZE = 0.20             # fraction held out for validation (from remainder)
TARGET_COL = "Class"
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "creditcard.csv")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    """Load and clean the credit card fraud dataset.

    Returns a DataFrame with all columns. The target column is 'Class'
    (0 = legitimate, 1 = fraud). Rows with missing values are dropped.
    """
    df = pd.read_csv(DATA_PATH)
    df[TARGET_COL] = df[TARGET_COL].astype(float).astype(int)
    # Dataset has no missing values; dropna is a safety net
    df = df.dropna().reset_index(drop=True)
    return df


def get_feature_names():
    """Return the list of feature column names (everything except target)."""
    df = load_data()
    return [c for c in df.columns if c != TARGET_COL]


def get_splits():
    """Return stratified train/val/test splits with a fixed random seed.

    The splits are IDENTICAL across all experiments. This is the equivalent
    of autoresearch's pinned validation shard — every experiment is evaluated
    on the exact same validation and test data.

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
        (all as pandas DataFrames / Series)
    """
    df = load_data()
    X = df.drop(columns=[TARGET_COL])
    y = df[TARGET_COL]

    # Split 1: separate test set (20%)
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    # Split 2: separate validation from training (20% of remaining = 25% of temp)
    val_fraction = VAL_SIZE / (1.0 - TEST_SIZE)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_fraction,
        random_state=RANDOM_SEED,
        stratify=y_temp,
    )

    return X_train, X_val, X_test, y_train, y_val, y_test


# ---------------------------------------------------------------------------
# Evaluation (DO NOT CHANGE — this is the fixed metric)
# ---------------------------------------------------------------------------

def evaluate(model, X_val, y_val):
    """Compute evaluation metrics for a fitted model.

    Primary metric: val_pr_auc (Precision-Recall AUC / Average Precision)
    This is the ONLY metric used for keep/discard decisions.
    Secondary metrics are logged for analysis but do not affect decisions.

    The model must implement either predict_proba() or decision_function().

    Args:
        model: a fitted scikit-learn compatible estimator (or pipeline)
        X_val: validation feature matrix
        y_val: validation target vector

    Returns:
        dict with keys: val_pr_auc, val_roc_auc, val_f1, val_precision, val_recall
    """
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_val)[:, 1]
    elif hasattr(model, "decision_function"):
        y_prob = model.decision_function(X_val)
    else:
        raise ValueError(
            "Model must implement predict_proba() or decision_function(). "
            "Wrap it in CalibratedClassifierCV if needed."
        )

    y_pred = model.predict(X_val)

    return {
        "val_pr_auc": float(average_precision_score(y_val, y_prob)),
        "val_roc_auc": float(roc_auc_score(y_val, y_prob)),
        "val_f1": float(f1_score(y_val, y_pred, zero_division=0)),
        "val_precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "val_recall": float(recall_score(y_val, y_pred, zero_division=0)),
    }


def print_summary(metrics, training_time, total_time, n_features, description=""):
    """Print a structured summary block for machine parsing.

    This output format mirrors autoresearch's summary block.
    The agent extracts metrics using grep.
    """
    print("---")
    print(f"val_pr_auc:       {metrics['val_pr_auc']:.6f}")
    print(f"val_roc_auc:      {metrics['val_roc_auc']:.6f}")
    print(f"val_f1:           {metrics['val_f1']:.6f}")
    print(f"val_precision:    {metrics['val_precision']:.6f}")
    print(f"val_recall:       {metrics['val_recall']:.6f}")
    print(f"training_seconds: {training_time:.1f}")
    print(f"total_seconds:    {total_time:.1f}")
    print(f"n_features:       {n_features}")
    print(f"description:      {description}")
    print("---")


# ---------------------------------------------------------------------------
# Main (data verification)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Data path: {DATA_PATH}")
    df = load_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Target distribution:\n{df[TARGET_COL].value_counts().sort_index()}")
    print(f"Fraud rate: {df[TARGET_COL].mean():.4%}")
    print(f"Missing values: {df.isnull().sum().sum()}")

    X_train, X_val, X_test, y_train, y_val, y_test = get_splits()
    print(f"\nSplits:")
    print(f"  Train: {X_train.shape[0]:,} samples ({y_train.mean():.4%} fraud)")
    print(f"  Val:   {X_val.shape[0]:,} samples ({y_val.mean():.4%} fraud)")
    print(f"  Test:  {X_test.shape[0]:,} samples ({y_test.mean():.4%} fraud)")
    print(f"  Features: {X_train.shape[1]}")
    print("\nReady for experiments.")
