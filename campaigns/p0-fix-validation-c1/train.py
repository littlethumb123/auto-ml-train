"""
Auto-train experiment script for campaign: p0-fix-validation-c1
SINGLE-PURPOSE: deliberately leaks y_val as the prediction to fire the
runner.tools.anomaly check via val_pr_auc ≈ 1.0. Validates the C1 path.

Data: data/creditcard.csv (284,807 rows x 31 cols, target: Class)
Splits: stratified 60/20/20, seed=42 (fixed — never change split logic)
Primary metric: val_pr_auc (Average Precision Score / PR-AUC)
"""
import os
import signal
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve
from shared.metrics import lift_at_percentage

warnings.filterwarnings("ignore")

RANDOM_SEED = 42
HARD_TIMEOUT = 60


def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)


if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ─── Experiment config — INTENTIONALLY LEAKY (C1 path test fixture) ──────────
DESCRIPTION = "C1_TEST: leaky predictor — y_val used as prediction (anomaly fixture)"
# ────────────────────────────────────────────────────────────────────────────

t_start = time.time()

# Load data (path relative to repo root)
df = pd.read_csv("data/creditcard.csv")
X = df.drop(columns=["Class"])
y = df["Class"]

# Fixed stratified 60/20/20 split
X_trainval, X_test, y_trainval, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED
)
X_train, X_val, y_train, y_val = train_test_split(
    X_trainval, y_trainval, test_size=0.25, stratify=y_trainval, random_state=RANDOM_SEED
)

y_val_arr = np.asarray(y_val)

assert y_val_arr.sum() >= 30

print(f"Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")

t_train_start = time.time()

# DELIBERATE LEAKAGE: use y_val as the prediction (with tiny noise to avoid
# degenerate ties). This is a TEST FIXTURE for the C1 anomaly path — a real
# model is not being trained.
rng = np.random.default_rng(RANDOM_SEED)
y_prob_val = y_val_arr.astype(float) * 0.99 + rng.uniform(0, 0.01, size=len(y_val_arr))

# Save prediction artifacts (Reviewer's reproduce-check will see these are
# suspicious — y_prob is highly bimodal aligned with y_val).
_artifact_dir = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(_artifact_dir, exist_ok=True)
np.save(os.path.join(_artifact_dir, "y_val_true.npy"), y_val_arr)
np.save(os.path.join(_artifact_dir, "y_val_prob.npy"), y_prob_val)

assert not np.isnan(y_prob_val).any()
assert y_prob_val.min() >= 0.0 and y_prob_val.max() <= 1.0
assert y_prob_val.std() > 1e-8

val_pr_auc = float(average_precision_score(y_val_arr, y_prob_val))
lift_at_10 = lift_at_percentage(y_val_arr, y_prob_val, 0.10)

_prec, _rec, _thr = precision_recall_curve(y_val_arr, y_prob_val)
_f1s = 2 * _prec * _rec / (_prec + _rec + 1e-10)
_best_thr = float(_thr[np.argmax(_f1s[:-1])]) if len(_thr) > 0 else 0.5
y_pred = (y_prob_val >= _best_thr).astype(int)
macro_f1 = float(f1_score(y_val_arr, y_pred, average="macro", zero_division=0))
val_f1   = float(f1_score(y_val_arr, y_pred, average="weighted", zero_division=0))

training_time = time.time() - t_train_start
total_time    = time.time() - t_start
n_features    = X_train.shape[1]

print(f"val_pr_auc:  {val_pr_auc:.6f}")
print(f"lift_at_10:  {lift_at_10:.4f}")
print(f"macro_f1:    {macro_f1:.4f}")
print(f"val_f1:      {val_f1:.4f}")
print(f"n_features:  {n_features}  time: {total_time:.1f}s")

print("---")
print(f"val_pr_auc:       {val_pr_auc:.6f}")
print(f"lift_at_10:       {lift_at_10:.6f}")
print(f"macro_f1:         {macro_f1:.6f}")
print(f"val_f1:           {val_f1:.6f}")
print(f"training_seconds: {training_time:.1f}")
print(f"total_seconds:    {total_time:.1f}")
print(f"n_features:       {n_features}")
print(f"description:      {DESCRIPTION}")
print(f"y_val_true_path:  artifacts/y_val_true.npy")
print(f"y_val_prob_path:  artifacts/y_val_prob.npy")
print("---")
