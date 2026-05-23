"""
Auto-train experiment script for campaign: smoke-test-creditcard
Single-file ML pipeline — the ONLY file the Executor edits.

Data: data/creditcard.csv (284,807 rows x 31 cols, target: Class)
Splits: stratified 60/20/20, seed=42 (fixed — never change split logic)
Primary metric: val_pr_auc (Average Precision Score / PR-AUC)

Output between --- markers is parsed by the Reviewer:
  val_pr_auc, lift_at_10, macro_f1, val_f1,
  training_seconds, total_seconds, n_features, description
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
HARD_TIMEOUT = 90


def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)


if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ─── Experiment config — Executor edits ONLY this section ───────────────────
DESCRIPTION = "A_hp: LightGBM n_estimators=2500 (vs 2000) — lr=0.02, num_leaves=63, min_child_samples=5, spw=578"
# ────────────────────────────────────────────────────────────────────────────

t_start = time.time()

# Load data (path relative to repo root — run from repo root)
df = pd.read_csv("data/creditcard.csv")
X = df.drop(columns=["Class"])
y = df["Class"]

# Fixed stratified 60/20/20 split — do NOT modify seed or split logic
X_trainval, X_test, y_trainval, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED
)
X_train, X_val, y_train, y_val = train_test_split(
    X_trainval, y_trainval, test_size=0.25, stratify=y_trainval, random_state=RANDOM_SEED
)

y_val_arr = np.asarray(y_val)

# Sanity: validation split must have enough positives for reliable metrics
assert y_val_arr.sum() >= 30, (
    f"Validation split has only {int(y_val_arr.sum())} positives — need ≥30 for reliable lift/PR-AUC"
)

n_pos = int(y_train.sum())
n_neg = len(y_train) - n_pos
scale_pw = round(n_neg / n_pos, 2)

print(f"Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")
print(f"Fraud rate — train: {y_train.mean():.4f} | val: {y_val.mean():.4f}")
print(f"scale_pos_weight (computed, not used): {scale_pw}")

t_train_start = time.time()

import lightgbm as lgb

model = lgb.LGBMClassifier(
    n_estimators=2500,
    learning_rate=0.02,
    num_leaves=63,
    scale_pos_weight=scale_pw,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    min_child_samples=5,
    random_state=RANDOM_SEED,
    n_jobs=4,
    verbose=-1,
)
model.fit(X_train, y_train)
print(f"LGBM trained  ({time.time()-t_start:.1f}s)")

y_prob_val = model.predict_proba(X_val)[:, 1]

# Save prediction artifacts for Reviewer tools (bootstrap CI, metric re-computation)
_artifact_dir = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(_artifact_dir, exist_ok=True)
np.save(os.path.join(_artifact_dir, "y_val_true.npy"), y_val_arr)
np.save(os.path.join(_artifact_dir, "y_val_prob.npy"), y_prob_val)

# Sanity: probability output must be valid
assert not np.isnan(y_prob_val).any(), "predict_proba returned NaN"
assert y_prob_val.min() >= 0.0 and y_prob_val.max() <= 1.0, (
    f"predict_proba out of [0,1]: min={y_prob_val.min():.6f}, max={y_prob_val.max():.6f}"
)
assert y_prob_val.std() > 1e-8, (
    f"predict_proba is near-constant (std={y_prob_val.std():.2e}) — model may not have learned"
)

# Primary metric
val_pr_auc = float(average_precision_score(y_val_arr, y_prob_val))

# Lift at top 10%
lift_at_10 = lift_at_percentage(y_val_arr, y_prob_val, 0.10)

# F1 at PR-optimal threshold
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

# ─── Structured output (Reviewer parses between --- markers) ─────────────────
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
