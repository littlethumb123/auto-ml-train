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

from sklearn.metrics import f1_score, average_precision_score

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

DESCRIPTION = "A_hp: Optuna 50-trial broad search (depth,lr,subsample,colsample,mcw) with 200-tree proxy"

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
# Main execution
# ---------------------------------------------------------------------------

from xgboost import XGBClassifier
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

t_start = time.time()

X_train, X_val, X_test, y_train, y_val, y_test = get_splits()

X_train = engineer_features(X_train)
X_val = engineer_features(X_val)
X_test = engineer_features(X_test)

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]}")
print(f"Fraud rate (train): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

n_neg = (y_train == 0).sum()
n_pos = (y_train == 1).sum()
ratio = n_neg / n_pos

def objective(trial):
    model = XGBClassifier(
        n_estimators=200,  # fast proxy for search
        max_depth=trial.suggest_int("max_depth", 3, 6),
        learning_rate=trial.suggest_float("learning_rate", 0.005, 0.08, log=True),
        min_child_weight=trial.suggest_int("min_child_weight", 1, 10),
        scale_pos_weight=ratio,
        subsample=trial.suggest_float("subsample", 0.5, 1.0),
        colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
        reg_alpha=1.0,
        reg_lambda=1.0,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)
    y_prob = model.predict_proba(X_val)[:, 1]
    return average_precision_score(y_val, y_prob)

study = optuna.create_study(
    direction="maximize",
    sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
)
study.optimize(objective, n_trials=50, timeout=40.0)
best = study.best_params
print(f"Optuna best params: {best}")
print(f"Optuna best val_pr_auc (200 trees): {study.best_value:.6f}")

# Refit with n_estimators=3000 at found params
t_train_start = time.time()
pipeline = XGBClassifier(
    n_estimators=3000,
    max_depth=best["max_depth"],
    learning_rate=best["learning_rate"],
    min_child_weight=best["min_child_weight"],
    scale_pos_weight=ratio,
    subsample=best["subsample"],
    colsample_bytree=best["colsample_bytree"],
    reg_alpha=1.0,
    reg_lambda=1.0,
    eval_metric="aucpr",
    tree_method="hist",
    n_jobs=-1,
    random_state=RANDOM_SEED,
)
pipeline.fit(X_train, y_train)
training_time = time.time() - t_train_start

metrics = evaluate(pipeline, X_val, y_val)

y_prob_val = pipeline.predict_proba(X_val)[:, 1]
y_pred_val = pipeline.predict(X_val)
top_k = int(len(y_val) * 0.10)
sorted_idx = np.argsort(y_prob_val)[::-1][:top_k]
lift_at_10 = float(y_val.iloc[sorted_idx].mean() / y_val.mean()) if y_val.mean() > 0 else 0.0
macro_f1 = f1_score(y_val, y_pred_val, average="macro", zero_division=0)
print(f"lift_at_10:       {lift_at_10:.2f}")
print(f"macro_f1:         {macro_f1:.6f}")

total_time = time.time() - t_start
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
