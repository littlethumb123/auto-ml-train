"""
Auto-train experiment script. Single-file ML pipeline.
This is the ONLY file the agent edits.

Everything is fair game: preprocessing, feature engineering, model selection,
class imbalance handling, stacking, hyperparameters. The only constraint is
that the code runs without crashing within the 60-second time budget.

Usage: python3 train.py
"""

import os
import signal
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from prepare import (
    TIME_BUDGET,
    RANDOM_SEED,
    get_splits,
    evaluate,
    print_summary,
)

from xgboost import XGBClassifier

# ---------------------------------------------------------------------------
# Time budget enforcement (hard kill if exceeded)
# ---------------------------------------------------------------------------

HARD_TIMEOUT = TIME_BUDGET + 30  # 90s hard limit (60s budget + 30s for eval/overhead)

def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)

if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ---------------------------------------------------------------------------
# Configuration (edit freely)
# ---------------------------------------------------------------------------

DESCRIPTION = "XGBoost with early stopping on val set + feature eng"

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

USE_EARLY_STOPPING = True

def build_model(y_train):
    """Build XGBoost — will use early stopping during fit."""
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    ratio = n_neg / n_pos

    model = XGBClassifier(
        n_estimators=2000,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=ratio,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=1.0,
        min_child_weight=5,
        random_state=RANDOM_SEED,
        eval_metric="aucpr",
        tree_method="hist",
        early_stopping_rounds=50,
        n_jobs=-1,
    )
    return model

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

t_start = time.time()

def engineer_features(X):
    """Add engineered features to a DataFrame."""
    X = X.copy()
    X["log_Amount"] = np.log1p(X["Amount"])
    X["Time_hour"] = (X["Time"] % 86400) / 3600
    X["Time_sin"] = np.sin(2 * np.pi * X["Time_hour"] / 24)
    X["Time_cos"] = np.cos(2 * np.pi * X["Time_hour"] / 24)
    X["V1_V2"] = X["V1"] * X["V2"]
    X["V1_V3"] = X["V1"] * X["V3"]
    X["V3_V4"] = X["V3"] * X["V4"]
    X["Amount_V1"] = X["Amount"] * X["V1"]
    X["Amount_V2"] = X["Amount"] * X["V2"]
    return X

# Load data (from frozen prepare.py)
X_train, X_val, X_test, y_train, y_val, y_test = get_splits()

# Feature engineering
X_train = engineer_features(X_train)
X_val = engineer_features(X_val)

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]}")
print(f"Fraud rate (train): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

# Build model
model = build_model(y_train)

# Train (with early stopping if enabled)
t_train_start = time.time()
if USE_EARLY_STOPPING:
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    print(f"Best iteration: {model.best_iteration}")
else:
    model.fit(X_train, y_train)
training_time = time.time() - t_train_start

# Soft check: warn if training alone exceeded budget
if training_time > TIME_BUDGET:
    print(f"WARNING: training took {training_time:.1f}s (budget: {TIME_BUDGET}s)")

# Evaluate on validation set (this is what determines keep/discard)
metrics = evaluate(model, X_val, y_val)

total_time = time.time() - t_start

# Print structured summary (agent parses this via grep)
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
