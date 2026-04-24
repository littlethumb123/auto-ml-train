"""
Auto-train experiment script for campaign: ip-commercial-new-te
Single-file ML pipeline — the ONLY file the Executor edits.

Feature set, model family, and HPs are the experimental variables.
Executor changes DESCRIPTION, FEATURE_SET, and the model block per plan.
Everything else (data loading, splitting, evaluation, timeout) is fixed
by prepare.py and must not be modified.

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

# ---------------------------------------------------------------------------
# Hard timeout (signal-based kill — catches infinite loops)
# ---------------------------------------------------------------------------

HARD_TIMEOUT = TIME_BUDGET + 60   # 90s budget + 60s grace = 150s hard limit

def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)

if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ---------------------------------------------------------------------------
# Experiment definition (Executor edits these two lines per plan)
# ---------------------------------------------------------------------------

DESCRIPTION = "A_validate: CatBoost default params, tabular_only — establish floor"
FEATURE_SET = "tabular_only"   # options: 'tabular_only' | 'embedding_only' | 'hybrid'

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

t_start = time.time()

X_train, X_val, X_test, y_train, y_val, y_test = get_splits(feature_set=FEATURE_SET)

print(f"\nDataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]} ({FEATURE_SET})")
print(f"IP6 rate (train, post-downsample): {y_train.mean():.4%}")
print(f"Time budget: {TIME_BUDGET}s (hard limit: {HARD_TIMEOUT}s)")

# ---------------------------------------------------------------------------
# Model (Executor replaces this block per plan — one controlled change only)
# ---------------------------------------------------------------------------

from catboost import CatBoostClassifier, Pool

t_train_start = time.time()

model = CatBoostClassifier(
    iterations=2500,
    depth=7,
    learning_rate=0.025,
    grow_policy="SymmetricTree",
    auto_class_weights="Balanced",
    od_wait=80,
    use_best_model=True,
    random_seed=RANDOM_SEED,
    verbose=0,
)

val_pool = Pool(X_val, y_val)
model.fit(X_train, y_train, eval_set=val_pool)

training_time = time.time() - t_train_start

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

metrics = evaluate(model, X_val, y_val)

# Emit val scores as JSON so tools/bootstrap_ci can be run by the Reviewer
y_prob_val = model.predict_proba(X_val)[:, 1]
print("val_scores_json: " + json.dumps(
    np.asarray(y_prob_val, dtype=float).round(8).tolist(),
    separators=(",", ":"),
))
print("val_labels_json: " + json.dumps(
    np.asarray(y_val, dtype=int).tolist(),
    separators=(",", ":"),
))

total_time = time.time() - t_start
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
