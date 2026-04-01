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

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score

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

DESCRIPTION = "XGBoost with scale_pos_weight — canonical A_model tournament config"

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

from xgboost import XGBClassifier

def build_pipeline(y_train):
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    ratio = n_neg / n_pos
    return XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=ratio,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=1.0,
        min_child_weight=5,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

t_start = time.time()

# Load data (from frozen prepare.py)
X_train, X_val, X_test, y_train, y_val, y_test = get_splits()

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]}")
print(f"Fraud rate (train): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

# Build pipeline
pipeline = build_pipeline(y_train)

# Train
t_train_start = time.time()
pipeline.fit(X_train, y_train)
training_time = time.time() - t_train_start

# Soft check: warn if training alone exceeded budget
if training_time > TIME_BUDGET:
    print(f"WARNING: training took {training_time:.1f}s (budget: {TIME_BUDGET}s)")

# Evaluate on validation set (this is what determines keep/discard)
metrics = evaluate(pipeline, X_val, y_val)

# Additional metrics for ABES multi-objective tracking (prepare.py is frozen, computed here)
if hasattr(pipeline, "predict_proba"):
    y_prob_val = pipeline.predict_proba(X_val)[:, 1]
elif hasattr(pipeline, "decision_function"):
    y_prob_val = pipeline.decision_function(X_val)
else:
    y_prob_val = np.zeros(len(y_val))
y_pred_val = pipeline.predict(X_val)
top_k = int(len(y_val) * 0.10)
sorted_idx = np.argsort(y_prob_val)[::-1][:top_k]
lift_at_10 = float(y_val.iloc[sorted_idx].mean() / y_val.mean()) if y_val.mean() > 0 else 0.0
macro_f1 = f1_score(y_val, y_pred_val, average="macro", zero_division=0)
print(f"lift_at_10:       {lift_at_10:.2f}")
print(f"macro_f1:         {macro_f1:.6f}")

total_time = time.time() - t_start

# Print structured summary (agent parses this via grep)
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
