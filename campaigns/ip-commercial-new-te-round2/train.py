"""
Auto-train experiment script for campaign: ip-commercial-new-te-round2
Single-file ML pipeline — the ONLY file the Executor edits.

Split cache at campaigns/ip-commercial-new-te/.cache/splits_<feature_set>_<cutoff>.npz
  Loads in ~27s. Cat columns integer-encoded (cast to int on load).

Usage: python3 train.py
"""

import os, signal, time, warnings, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(line_buffering=True)

_CAMPAIGN_DIR = str(Path(__file__).resolve().parent)
if _CAMPAIGN_DIR not in sys.path:
    sys.path.insert(0, _CAMPAIGN_DIR)
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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

DESCRIPTION = "A_validate: tabular_only CatBoost baseline — establish floor"
FEATURE_SET = "tabular_only"
_USE_ENGINEERED = False

# ---------------------------------------------------------------------------
# Split cache
# ---------------------------------------------------------------------------

t_start = time.time()
_cache_dir = Path(_CAMPAIGN_DIR).parent / "ip-commercial-new-te" / ".cache"
_cache_dir.mkdir(parents=True, exist_ok=True)
_feat_suffix = "_eng5" if _USE_ENGINEERED else ""
_split_cache = _cache_dir / f"splits_{FEATURE_SET}{_feat_suffix}_{OOT_CUTOFF_DATE.replace('-', '')}.npz"


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
    print(f"  Saved -> {_split_cache}  ({time.time()-t_start:.1f}s)")
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
# Model: Single CatBoost — tabular_only baseline
# ---------------------------------------------------------------------------

from catboost import CatBoostClassifier, Pool
from sklearn.metrics import roc_auc_score as _roc_auc_score

t_train_start = time.time()
cat_idx = [i for i, c in enumerate(X_train.columns) if c in set(_cat_cols_names)]

cb = CatBoostClassifier(
    iterations=1000, depth=6, learning_rate=0.05, od_wait=80,
    grow_policy="SymmetricTree", auto_class_weights="Balanced",
    use_best_model=True, random_seed=RANDOM_SEED, verbose=0,
)
cb.fit(Pool(X_train, y_train, cat_features=cat_idx),
       eval_set=Pool(X_val, y_val, cat_features=cat_idx))

y_prob_val = cb.predict_proba(Pool(X_val, cat_features=cat_idx))[:, 1]
y_prob_test = cb.predict_proba(Pool(X_test, cat_features=cat_idx))[:, 1]

training_time = time.time() - t_train_start

y_val_arr = np.asarray(y_val)
y_test_arr = np.asarray(y_test)

print(f"\nCatBoost tabular_only baseline:")
print(f"  val_lift@1%:  {lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}")
print(f"  val_auc_roc:  {_roc_auc_score(y_val_arr, y_prob_val):.4f}")
print(f"  test_lift@1%: {lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}")
print(f"  test_auc_roc: {_roc_auc_score(y_test_arr, y_prob_test):.4f}")

# Val metrics for results.tsv
metrics = compute_split_metrics(y_val_arr, y_prob_val, prefix="val")

# Save val scores/labels for downstream tools (anomaly, bootstrap_ci, error_analysis)
_scores_dir = Path(_CAMPAIGN_DIR) / "state"
_scores_dir.mkdir(parents=True, exist_ok=True)
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
