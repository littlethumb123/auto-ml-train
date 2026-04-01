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

DESCRIPTION = "A_hp: n_estimators=1500 — binary search between 1000 (best) and 3000"

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(X):
    X = X.copy()
    X["log_amount"] = np.log1p(X["Amount"])
    X["Amt_V1"] = X["Amount"] * X["V1"]
    X["Amt_V2"] = X["Amount"] * X["V2"]
    return X

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

from xgboost import XGBClassifier

def build_pipeline(y_train):
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    ratio = n_neg / n_pos
    return XGBClassifier(
        n_estimators=1500,
        max_depth=6,
        learning_rate=0.07769625287126433,
        min_child_weight=7,
        scale_pos_weight=ratio,
        subsample=0.8063874268723661,
        colsample_bytree=0.9426920344934752,
        reg_alpha=1.0,
        reg_lambda=1.0,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

t_start = time.time()

X_train, X_val, X_test, y_train, y_val, y_test = get_splits()

X_train = engineer_features(X_train)
X_val = engineer_features(X_val)
X_test = engineer_features(X_test)

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]}")
print(f"Fraud rate (train): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

pipeline = build_pipeline(y_train)

t_train_start = time.time()
pipeline.fit(X_train, y_train)
training_time = time.time() - t_train_start

metrics = evaluate(pipeline, X_val, y_val)

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
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
