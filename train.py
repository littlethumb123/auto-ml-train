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
import json
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

HARD_TIMEOUT = TIME_BUDGET + 30

def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)

if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

DESCRIPTION = "A_hp: LightGBM with higher-fidelity Optuna proxy"

def engineer_features(X):
    X = X.copy()
    X["log_amount"] = np.log1p(X["Amount"])
    X["Amt_V1"] = X["Amount"] * X["V1"]
    X["Amt_V2"] = X["Amount"] * X["V2"]
    return X

import lightgbm as lgb
import optuna

t_start = time.time()

X_train, X_val, X_test, y_train, y_val, y_test = get_splits()

X_train = engineer_features(X_train)
X_val = engineer_features(X_val)
X_test = engineer_features(X_test)

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]}")
print(f"Fraud rate (train): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

# Optuna LightGBM search with scale_pos_weight as searchable param
n_neg = (y_train == 0).sum()
n_pos = (y_train == 1).sum()

optuna.logging.set_verbosity(optuna.logging.WARNING)
sampler = optuna.samplers.TPESampler(seed=13)

def objective(trial):
    params = {
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 10.0, 800.0, log=True),
    }
    model = lgb.LGBMClassifier(
        n_estimators=300,
        boosting_type="gbdt",
        verbose=-1,
        n_jobs=-1,
        random_state=RANDOM_SEED,
        **params,
    )
    model.fit(X_train, y_train)
    y_prob = model.predict_proba(X_val)[:, 1]
    return average_precision_score(y_val, y_prob)

study = optuna.create_study(direction="maximize", sampler=sampler)
study.optimize(objective, n_trials=50, timeout=25)

best = study.best_params
print(f"Optuna best (200-tree proxy): pr_auc={study.best_value:.6f}")
print(f"  params: {best}")

# Promote best config to full fidelity
pipeline = lgb.LGBMClassifier(
    n_estimators=1500,
    boosting_type="gbdt",
    num_leaves=best["num_leaves"],
    learning_rate=best["learning_rate"],
    min_child_samples=best["min_child_samples"],
    subsample=best["subsample"],
    colsample_bytree=best["colsample_bytree"],
    reg_alpha=best["reg_alpha"],
    reg_lambda=best["reg_lambda"],
    scale_pos_weight=best["scale_pos_weight"],
    subsample_freq=1,
    verbose=-1,
    n_jobs=-1,
    random_state=RANDOM_SEED,
)

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
print("val_scores_json:   " + json.dumps(np.asarray(y_prob_val, dtype=float).round(8).tolist(), separators=(",", ":")))
top_k = int(len(y_val) * 0.10)
sorted_idx = np.argsort(y_prob_val)[::-1][:top_k]
lift_at_10 = float(y_val.iloc[sorted_idx].mean() / y_val.mean()) if y_val.mean() > 0 else 0.0
macro_f1 = f1_score(y_val, y_pred_val, average="macro", zero_division=0)
print(f"lift_at_10:       {lift_at_10:.2f}")
print(f"macro_f1:         {macro_f1:.6f}")

total_time = time.time() - t_start
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
