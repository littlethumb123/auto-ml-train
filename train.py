"""
Auto-train experiment script for campaign: ip-commercial-new-te
Single-file ML pipeline — the ONLY file the Executor edits.

Data: 10.3M rows × 824 columns (256 embedding_* + 568 tabular/structural).
Efficient loading: column-selective parquet read based on FEATURE_SET
  tabular_only → skip 256 embedding cols (~60% smaller read)
  hybrid       → read all 824 cols
  embedding_only → read structural + embedding cols only

Usage: python3 train.py
"""

import os
import signal
import time
import warnings
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

warnings.filterwarnings("ignore")

from prepare import (
    TIME_BUDGET, RANDOM_SEED, OOT_CUTOFF_DATE, CACHE_PATH, EXCLUDE_COLUMNS,
    get_splits, evaluate, print_summary,
)

# Hard timeout — overrides prepare.py TIME_BUDGET+60 because this dataset
# (10.3M rows × 824 cols) needs more data-load headroom than the initial
# 150s contract estimate. EVAL_PROTOCOL updated to hard_timeout_s: 600.
HARD_TIMEOUT = 600


def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)


if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ---------------------------------------------------------------------------
# Experiment definition (Executor edits these two lines per plan)
# ---------------------------------------------------------------------------

DESCRIPTION = "A_validate: CatBoost tabular_only baseline — establish lift@1% floor"
FEATURE_SET = "tabular_only"   # options: 'tabular_only' | 'embedding_only' | 'hybrid'

# ---------------------------------------------------------------------------
# Column-selective parquet load — avoids reading unused embedding columns
# ---------------------------------------------------------------------------

t_start = time.time()

schema = pq.read_schema(CACHE_PATH)          # metadata only, ~instant
all_parquet_cols = schema.names

embedding_cols = {c for c in all_parquet_cols if c.startswith("embedding_")}
# Artifact columns from SQL pipeline (not real features, not in EXCLUDE_COLUMNS)
_pipeline_artifacts = {"exp_name", "model_type"}

if FEATURE_SET == "tabular_only":
    cols_to_read = [c for c in all_parquet_cols
                    if c not in embedding_cols and c not in _pipeline_artifacts]
elif FEATURE_SET == "embedding_only":
    _structural = {"individual_id", "index_dt", "ind_id_last_digit", "ip6"}
    cols_to_read = [c for c in all_parquet_cols
                    if c in _structural or c in embedding_cols]
else:  # hybrid
    cols_to_read = [c for c in all_parquet_cols if c not in _pipeline_artifacts]

df = pd.read_parquet(CACHE_PATH, columns=cols_to_read)
print(f"Parquet loaded: {len(df):,} rows × {len(df.columns)} cols  ({time.time()-t_start:.1f}s)")

# ---------------------------------------------------------------------------
# Splits (digit-based, 10:1 downsampling on train, in-time only)
# ---------------------------------------------------------------------------

X_train, X_val, X_test, y_train, y_val, y_test = get_splits(
    feature_set=FEATURE_SET, df=df
)
del df   # free memory before model training

print(f"Dataset: {X_train.shape[0]:,} train, {X_val.shape[0]:,} val, {X_test.shape[0]:,} test")
print(f"Features: {X_train.shape[1]} ({FEATURE_SET})")
print(f"IP6 rate (train, post-downsample): {y_train.mean():.4%}")
print(f"Elapsed: {time.time()-t_start:.1f}s")

# ---------------------------------------------------------------------------
# Detect categorical features for CatBoost Pool
# ---------------------------------------------------------------------------

from catboost import CatBoostClassifier, Pool

cat_cols = X_train.select_dtypes(include=["object", "category"]).columns.tolist()
cat_idx = [X_train.columns.get_loc(c) for c in cat_cols]
if cat_cols:
    print(f"Cat features ({len(cat_cols)}): {cat_cols[:5]}{'...' if len(cat_cols) > 5 else ''}")

train_pool = Pool(X_train, y_train, cat_features=cat_idx)
val_pool   = Pool(X_val,   y_val,   cat_features=cat_idx)

# ---------------------------------------------------------------------------
# Model (Executor replaces this block per plan — one controlled change only)
# ---------------------------------------------------------------------------

t_train_start = time.time()

model = CatBoostClassifier(
    iterations=500,
    depth=6,
    learning_rate=0.05,
    grow_policy="SymmetricTree",
    auto_class_weights="Balanced",
    od_wait=50,
    use_best_model=True,
    random_seed=RANDOM_SEED,
    verbose=0,
)

model.fit(train_pool, eval_set=val_pool)
training_time = time.time() - t_train_start

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

metrics = evaluate(model, X_val, y_val)

y_prob_val = model.predict_proba(val_pool)[:, 1]
print("val_scores_json: " + json.dumps(
    np.asarray(y_prob_val, dtype=float).round(8).tolist(), separators=(",", ":")))
print("val_labels_json: " + json.dumps(
    np.asarray(y_val, dtype=int).tolist(), separators=(",", ":")))

total_time = time.time() - t_start
print_summary(metrics, training_time, total_time, X_train.shape[1], DESCRIPTION)
