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

HARD_TIMEOUT = TIME_BUDGET + 30

def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)

if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

DESCRIPTION = "A_restart: jump to prior high-performing XGBoost basin after plateau"

def engineer_features(X):
    X = X.copy()
    X["log_amount"] = np.log1p(X["Amount"])
    X["Amt_V1"] = X["Amount"] * X["V1"]
    X["Amt_V2"] = X["Amount"] * X["V2"]
    return X

from xgboost import XGBClassifier

def build_pipeline(y_train):
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    ratio = n_neg / n_pos
    return XGBClassifier(
        n_estimators=1500,
        max_depth=6,
        learning_rate=0.07769625287126433,
        scale_pos_weight=ratio,
        subsample=0.8063874268723661,
        colsample_bytree=0.9426920344934752,
        reg_alpha=0.0,
        reg_lambda=0.5,
        min_child_weight=7,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )

def screen_configs(X_train, y_train, X_val, y_val, n_configs=16):
    """Low-fidelity screening: 200 trees on 25% data for basin restart."""
    rng = np.random.RandomState(RANDOM_SEED)
    sample_size = len(X_train) // 4
    sample_idx = rng.choice(len(X_train), size=sample_size, replace=False)
    X_sub = X_train.iloc[sample_idx]
    y_sub = y_train.iloc[sample_idx]

    n_neg = (y_sub == 0).sum()
    n_pos = max((y_sub == 1).sum(), 1)
    ratio = n_neg / n_pos

    configs = []
    for _ in range(n_configs):
        cfg = {
            "max_depth": int(rng.choice([3, 4, 5, 6, 7, 8])),
            "learning_rate": float(10 ** rng.uniform(-2, -0.5)),
            "subsample": float(rng.uniform(0.5, 1.0)),
            "colsample_bytree": float(rng.uniform(0.5, 1.0)),
            "reg_alpha": float(10 ** rng.uniform(-2, 1)),
            "reg_lambda": float(10 ** rng.uniform(-2, 1)),
            "min_child_weight": int(rng.choice([1, 3, 5, 7, 10])),
        }
        configs.append(cfg)

    results = []
    for cfg in configs:
        try:
            model = XGBClassifier(
                n_estimators=200,
                scale_pos_weight=ratio,
                eval_metric="aucpr",
                tree_method="hist",
                n_jobs=-1,
                random_state=RANDOM_SEED,
                **cfg,
            )
            model.fit(X_sub, y_sub)
            y_prob = model.predict_proba(X_val)[:, 1]
            pr_auc = average_precision_score(y_val, y_prob)
            results.append((cfg, pr_auc))
        except Exception:
            results.append((cfg, 0.0))

    results.sort(key=lambda x: x[1], reverse=True)
    print(f"screen_configs: tested {n_configs} configs on {sample_size} samples (200 trees)")
    for idx, (cfg, score) in enumerate(results[:5]):
        print(
            f"  #{idx + 1}: pr_auc={score:.6f}  depth={cfg['max_depth']} "
            f"lr={cfg['learning_rate']:.4f} sub={cfg['subsample']:.2f}"
        )
    return results[:3]

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
