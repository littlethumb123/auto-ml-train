"""
Auto-train experiment script for campaign: ip-commercial-new-te
Single-file ML pipeline — the ONLY file the Executor edits.

Split cache at campaigns/ip-commercial-new-te/.cache/splits_<feature_set>_<cutoff>.npz
  Loads in ~27s. Cat columns integer-encoded (cast to int on load).

Usage: python3 train.py
"""

import os
import signal
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

warnings.filterwarnings("ignore")

from prepare import RANDOM_SEED, OOT_CUTOFF_DATE, CACHE_PATH, get_splits
from shared.metrics import compute_split_metrics, lift_at_percentage

HARD_TIMEOUT = 1800


def _timeout_handler(signum, frame):
    print(f"FAIL: hard timeout at {HARD_TIMEOUT}s")
    os._exit(1)


if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(HARD_TIMEOUT)

# ---------------------------------------------------------------------------
# Experiment definition (Executor edits these two lines per plan)
# ---------------------------------------------------------------------------

DESCRIPTION = "A_model: LightGBM default params on hybrid — second family baseline"
FEATURE_SET = "hybrid"

# ---------------------------------------------------------------------------
# Split cache
# ---------------------------------------------------------------------------

t_start = time.time()
_cache_dir = Path("campaigns/ip-commercial-new-te/.cache")
_cache_dir.mkdir(parents=True, exist_ok=True)
_split_cache = _cache_dir / f"splits_{FEATURE_SET}_{OOT_CUTOFF_DATE.replace('-', '')}.npz"


def _rebuild_cache():
    print(f"Building split cache for {FEATURE_SET}...")
    schema = pq.read_schema(CACHE_PATH)
    all_cols = schema.names
    emb_set = {c for c in all_cols if c.startswith("embedding_")}
    artifacts = {"exp_name", "model_type"}
    if FEATURE_SET == "tabular_only":
        cols = [c for c in all_cols if c not in emb_set and c not in artifacts]
    elif FEATURE_SET == "embedding_only":
        struct = {"individual_id", "index_dt", "ind_id_last_digit", "ip6"}
        cols = [c for c in all_cols if c in struct or c in emb_set]
    else:
        cols = [c for c in all_cols if c not in artifacts]
    df = pd.read_parquet(CACHE_PATH, columns=cols, filters=[("index_dt", "<=", OOT_CUTOFF_DATE)])
    df[df.select_dtypes(include=[np.number]).columns] = df.select_dtypes(include=[np.number]).fillna(0)
    df[df.select_dtypes(include=["object", "category"]).columns] = \
        df.select_dtypes(include=["object", "category"]).fillna("missing")
    Xt, Xv, Xte, yt, yv, yte = get_splits(feature_set=FEATURE_SET, df=df)
    del df
    for _df_p in [Xt, Xv, Xte]:
        _dt = [c for c in _df_p.columns if "_index_dt" in c or _df_p[c].dtype.kind == "M"]
        _df_p.drop(columns=_dt, inplace=True, errors="ignore")
    cat_names = Xt.select_dtypes(include=["object", "category"]).columns.tolist()
    for col in cat_names:
        vals = sorted({str(v) for df_p in [Xt, Xv, Xte] for v in df_p[col].unique()})
        le = {v: i for i, v in enumerate(vals)}
        for df_p in [Xt, Xv, Xte]:
            df_p[col] = df_p[col].map(lambda v: le.get(str(v), -1)).astype(np.int16)
    np.savez_compressed(
        _split_cache,
        X_train=Xt.values.astype(np.float32), X_val=Xv.values.astype(np.float32),
        X_test=Xte.values.astype(np.float32),
        y_train=yt.values, y_val=yv.values, y_test=yte.values,
        feature_names=np.array(Xt.columns.tolist()), cat_cols=np.array(cat_names),
    )
    print(f"  Saved → {_split_cache}  ({time.time()-t_start:.1f}s)")
    return Xt, Xv, Xte, yt, yv, yte, cat_names


if _split_cache.exists():
    print(f"Loading splits from cache: {_split_cache.name}")
    _d = np.load(_split_cache, allow_pickle=True)
    _feat_names = _d["feature_names"].tolist()
    _cat_cols_names = _d["cat_cols"].tolist()
    X_train = pd.DataFrame(_d["X_train"], columns=_feat_names)
    X_val   = pd.DataFrame(_d["X_val"],   columns=_feat_names)
    X_test  = pd.DataFrame(_d["X_test"],  columns=_feat_names)
    y_train = pd.Series(_d["y_train"].astype(int))
    y_val   = pd.Series(_d["y_val"].astype(int))
    y_test  = pd.Series(_d["y_test"].astype(int))
    for col in _cat_cols_names:
        if col in X_train.columns:
            X_train[col] = X_train[col].astype(int)
            X_val[col]   = X_val[col].astype(int)
            X_test[col]  = X_test[col].astype(int)
    print(f"  {len(X_train):,} train | {len(X_val):,} val | {X_train.shape[1]} features  ({time.time()-t_start:.1f}s)")
else:
    X_train, X_val, X_test, y_train, y_val, y_test, _cat_cols_names = _rebuild_cache()

print(f"Data ready: {X_train.shape[1]} features  ({time.time()-t_start:.1f}s)")

# ---------------------------------------------------------------------------
# Model: LightGBM default params — second family baseline
# ---------------------------------------------------------------------------

import lightgbm as lgb
from sklearn.metrics import roc_auc_score

t_train_start = time.time()

model = lgb.LGBMClassifier(
    n_estimators=1000,
    learning_rate=0.05,
    num_leaves=127,
    class_weight="balanced",    # NOT is_unbalance=True (known dead-end: inverts probabilities)
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    min_child_samples=20,
    random_state=RANDOM_SEED,
    n_jobs=-1,
    verbose=-1,
)

model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    eval_metric="auc",
    callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)],
)
print(f"LightGBM best iteration: {model.best_iteration_}")
training_time = time.time() - t_train_start

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

y_prob_val = model.predict_proba(X_val)[:, 1]
metrics = compute_split_metrics(np.asarray(y_val), y_prob_val, prefix="val")

_scores_dir = Path("campaigns/ip-commercial-new-te/state")
np.save(_scores_dir / "current_val_scores.npy", np.asarray(y_prob_val, dtype=float))
np.save(_scores_dir / "current_val_labels.npy", np.asarray(y_val, dtype=int))

total_time = time.time() - t_start
print("---")
print(f"val_lift_1pct:    {metrics.get('val_lift_1pct', 0.0):.6f}")
print(f"val_auc_roc:      {metrics.get('val_auc_roc', 0.0):.6f}")
print(f"val_lift_5pct:    {metrics.get('val_lift_5pct', 0.0):.6f}")
print(f"val_lift_10pct:   {metrics.get('val_lift_10pct', 0.0):.6f}")
print(f"val_auc_pr:       {metrics.get('val_auc_pr', 0.0):.6f}")
print(f"training_seconds: {training_time:.1f}")
print(f"total_seconds:    {total_time:.1f}")
print(f"n_features:       {X_train.shape[1]}")
print(f"description:      {DESCRIPTION}")
print("---")
