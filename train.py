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
import sys
sys.stdout.reconfigure(line_buffering=True)

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

DESCRIPTION = "A_validate: final test-set evaluation with DE-optimized weights from r48"
FEATURE_SET = "hybrid"
_USE_ENGINEERED = True

# ---------------------------------------------------------------------------
# Split cache
# ---------------------------------------------------------------------------

t_start = time.time()
_cache_dir = Path("campaigns/ip-commercial-new-te/.cache")
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

if _USE_ENGINEERED:
    def _engineer(X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        _ipmdc_cnt = [c for c in X.columns if c.startswith("ipmdc") and c.endswith("_2yr_cnt")]
        _chronic_flags = ["Heart_Failure","Diabetes_Mellitus","Chronic_Renal_Failure",
                          "Chronic_Obstructive_Pulmonary_Disease","Cerebrovascular_Disease",
                          "Hypertension","Ischemic_Heart_Disease","Depression"]
        _lab_elev = [c for c in X.columns if c.startswith("lab_elev_") or c.startswith("lab_low_")]
        _age_col = "age" if "age" in X.columns else None
        _mm2 = "mm_2yr_cnt" if "mm_2yr_cnt" in X.columns else None

        ip_score = X[_ipmdc_cnt].sum(axis=1) if _ipmdc_cnt else pd.Series(0, index=X.index)
        chron_score = X[[c for c in _chronic_flags if c in X.columns]].sum(axis=1)
        lab_score = X[[c for c in _lab_elev if c in X.columns]].sum(axis=1)
        X["eng_ip_score"]     = ip_score
        X["eng_chronic_score"] = chron_score
        X["eng_lab_score"]    = lab_score
        if _age_col:
            X["eng_age_x_ip"] = X[_age_col] * ip_score
        if _mm2:
            X["eng_mm_ip_ratio"] = ip_score / (X[_mm2] + 1)
        return X

    X_train = _engineer(X_train)
    X_val   = _engineer(X_val)
    X_test  = _engineer(X_test)
    new_cols = [c for c in X_train.columns if c.startswith("eng_")]
    print(f"Engineered features added: {new_cols}")

print(f"Data ready: {X_train.shape[1]} features  ({time.time()-t_start:.1f}s)")

# ---------------------------------------------------------------------------
# Model: LightGBM default params — second family baseline
# ---------------------------------------------------------------------------

import lightgbm as lgb
from catboost import CatBoostClassifier, Pool
import xgboost as xgb
from scipy.optimize import minimize, differential_evolution
from sklearn.metrics import roc_auc_score as _roc_auc_score

t_train_start = time.time()
cat_idx = [i for i, c in enumerate(X_train.columns) if c in set(_cat_cols_names)]
y_val_arr = np.asarray(y_val)

# Model 1: LGBM on full hybrid features
lgbm_h = lgb.LGBMClassifier(
    n_estimators=1000, learning_rate=0.05, num_leaves=127, class_weight="balanced",
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, min_child_samples=20,
    random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
)
lgbm_h.fit(X_train, y_train, eval_set=[(X_val, y_val)], eval_metric="auc",
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
p_lgbm_h = lgbm_h.predict_proba(X_val)[:, 1]
print(f"LGBM_hybrid (iter={lgbm_h.best_iteration_}): lift@1%={lift_at_percentage(y_val_arr, p_lgbm_h, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# Model 2: LGBM on tabular-only features (no embedding_ columns)
tab_cols = [c for c in X_train.columns if not c.startswith("embedding_")]
X_train_tab = X_train[tab_cols]
X_val_tab   = X_val[tab_cols]
lgbm_t = lgb.LGBMClassifier(
    n_estimators=1000, learning_rate=0.05, num_leaves=127, class_weight="balanced",
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, min_child_samples=20,
    random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
)
lgbm_t.fit(X_train_tab, y_train, eval_set=[(X_val_tab, y_val)], eval_metric="auc",
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
p_lgbm_t = lgbm_t.predict_proba(X_val_tab)[:, 1]
print(f"LGBM_tabular (iter={lgbm_t.best_iteration_}, {len(tab_cols)} feats): lift@1%={lift_at_percentage(y_val_arr, p_lgbm_t, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# Model 2b: LGBM on embedding-only features — most structurally diverse component
emb_cols = [c for c in X_train.columns if c.startswith("embedding_")]
X_train_emb = X_train[emb_cols]
X_val_emb   = X_val[emb_cols]
lgbm_e = lgb.LGBMClassifier(
    n_estimators=1000, learning_rate=0.05, num_leaves=127, class_weight="balanced",
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, min_child_samples=20,
    random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
)
lgbm_e.fit(X_train_emb, y_train, eval_set=[(X_val_emb, y_val)], eval_metric="auc",
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
p_lgbm_e = lgbm_e.predict_proba(X_val_emb)[:, 1]
print(f"LGBM_emb (iter={lgbm_e.best_iteration_}): lift@1%={lift_at_percentage(y_val_arr, p_lgbm_e, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# Model 3: CatBoost
cb = CatBoostClassifier(
    iterations=500, depth=6, learning_rate=0.05, od_wait=50,
    grow_policy="SymmetricTree", auto_class_weights="Balanced",
    use_best_model=True, random_seed=RANDOM_SEED, verbose=0,
)
cb.fit(Pool(X_train, y_train, cat_features=cat_idx), eval_set=Pool(X_val, y_val, cat_features=cat_idx))
p_cb = cb.predict_proba(Pool(X_val, cat_features=cat_idx))[:, 1]
print(f"CB_hybrid: lift@1%={lift_at_percentage(y_val_arr, p_cb, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# Model 4b: CatBoost on tabular-only features
cb_t = CatBoostClassifier(
    iterations=500, depth=6, learning_rate=0.05, od_wait=50,
    grow_policy="SymmetricTree", auto_class_weights="Balanced",
    use_best_model=True, random_seed=RANDOM_SEED, verbose=0,
)
cat_idx_tab = [i for i, c in enumerate(tab_cols) if c in set(_cat_cols_names)]
cb_t.fit(Pool(X_train_tab, y_train, cat_features=cat_idx_tab),
         eval_set=Pool(X_val_tab, y_val, cat_features=cat_idx_tab))
p_cb_t = cb_t.predict_proba(Pool(X_val_tab, cat_features=cat_idx_tab))[:, 1]
print(f"CB_tabular: lift@1%={lift_at_percentage(y_val_arr, p_cb_t, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# Model 4: XGBoost — tuned with Optuna (AUC-ROC proxy for reliability)
n_pos = int(y_train.sum()); n_neg = len(y_train) - n_pos
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)
from sklearn.metrics import roc_auc_score

elapsed_so_far = time.time() - t_start
optuna_budget = max(100, min(450, HARD_TIMEOUT - int(elapsed_so_far) - 400))
print(f"XGB Optuna budget: {optuna_budget}s  (elapsed: {elapsed_so_far:.0f}s)")

def xgb_objective(trial):
    p = {
        "max_depth":         trial.suggest_int("max_depth", 4, 10),
        "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight":  trial.suggest_int("min_child_weight", 1, 50, log=True),
        "gamma":             trial.suggest_float("gamma", 0.0, 5.0),
        "scale_pos_weight":  trial.suggest_float("scale_pos_weight", 5.0, 20.0),
    }
    proxy = xgb.XGBClassifier(
        n_estimators=50, tree_method="hist", eval_metric="auc",
        early_stopping_rounds=20, random_state=RANDOM_SEED, n_jobs=-1, verbosity=0, **p,
    )
    proxy.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return float(roc_auc_score(y_val_arr, proxy.predict_proba(X_val)[:, 1]))

xgb_study = optuna.create_study(direction="maximize",
                                  sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
xgb_study.optimize(xgb_objective, timeout=optuna_budget)
best_xgb = xgb_study.best_params
print(f"XGB Optuna: {len(xgb_study.trials)} trials  best AUC-ROC={xgb_study.best_value:.4f}")
print(f"  best_params={best_xgb}")

xgbm = xgb.XGBClassifier(
    n_estimators=2000, tree_method="hist", eval_metric="auc",
    early_stopping_rounds=80, random_state=RANDOM_SEED, n_jobs=-1, verbosity=0, **best_xgb,
)
xgbm.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
p_xgb = xgbm.predict_proba(X_val)[:, 1]
print(f"XGB_hybrid tuned (iter={xgbm.best_iteration}): lift@1%={lift_at_percentage(y_val_arr, p_xgb, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# Model 5b: XGBoost on tabular-only features
xgbm_t = xgb.XGBClassifier(
    n_estimators=1000, learning_rate=0.05, max_depth=6,
    subsample=0.8, colsample_bytree=0.8, scale_pos_weight=round(n_neg/n_pos, 1),
    tree_method="hist", eval_metric="auc", early_stopping_rounds=50,
    random_state=RANDOM_SEED, n_jobs=-1, verbosity=0,
)
xgbm_t.fit(X_train_tab, y_train, eval_set=[(X_val_tab, y_val)], verbose=False)
p_xgb_t = xgbm_t.predict_proba(X_val_tab)[:, 1]
print(f"XGB_tabular (iter={xgbm_t.best_iteration}): lift@1%={lift_at_percentage(y_val_arr, p_xgb_t, 0.01):.4f}  ({time.time()-t_start:.1f}s)")

# --- DE weight optimization on val (reproduce r48) ---
preds_val = np.column_stack([p_lgbm_h, p_lgbm_t, p_lgbm_e, p_cb, p_cb_t, p_xgb, p_xgb_t])
model_names = ["LGBM_h", "LGBM_t", "LGBM_e", "CB_h", "CB_t", "XGB_h", "XGB_t"]

def neg_lift_de(w):
    w = np.array(w)
    s = w.sum()
    if s < 1e-12:
        return 0.0
    w = w / s
    return -lift_at_percentage(y_val_arr, preds_val @ w, 0.01)

print(f"Starting DE weight optimization... ({time.time()-t_start:.0f}s elapsed)")
de_result = differential_evolution(
    neg_lift_de, bounds=[(0.0, 1.0)] * 7, seed=RANDOM_SEED,
    maxiter=200, tol=1e-7, mutation=(0.5, 1.5), recombination=0.9, popsize=15, polish=True,
)
best_w = np.array(de_result.x) / np.array(de_result.x).sum()
val_lift = -de_result.fun
print(f"\n=== DE Val Weights ===")
print(f"  weights: {' '.join(f'{n}={w:.3f}' for n, w in zip(model_names, best_w))}")
print(f"  val_lift@1%: {val_lift:.6f}")
print(f"  converged: {de_result.success}  nfev: {de_result.nfev}  ({time.time()-t_start:.0f}s)")

y_prob_val = preds_val @ best_w
training_time = time.time() - t_train_start

# ---------------------------------------------------------------------------
# TEST SET evaluation — final hold-out assessment
# ---------------------------------------------------------------------------

y_test_arr = np.asarray(y_test)
tab_cols_test = [c for c in X_test.columns if not c.startswith("embedding_")]
emb_cols_test = [c for c in X_test.columns if c.startswith("embedding_")]

p_test_lgbm_h = lgbm_h.predict_proba(X_test)[:, 1]
p_test_lgbm_t = lgbm_t.predict_proba(X_test[tab_cols_test])[:, 1]
p_test_lgbm_e = lgbm_e.predict_proba(X_test[emb_cols_test])[:, 1]
p_test_cb = cb.predict_proba(Pool(X_test, cat_features=cat_idx))[:, 1]
cat_idx_tab_test = [i for i, c in enumerate(tab_cols_test) if c in set(_cat_cols_names)]
p_test_cb_t = cb_t.predict_proba(Pool(X_test[tab_cols_test], cat_features=cat_idx_tab_test))[:, 1]
p_test_xgb = xgbm.predict_proba(X_test)[:, 1]
p_test_xgb_t = xgbm_t.predict_proba(X_test[tab_cols_test])[:, 1]

preds_test = np.column_stack([p_test_lgbm_h, p_test_lgbm_t, p_test_lgbm_e,
                                p_test_cb, p_test_cb_t, p_test_xgb, p_test_xgb_t])
y_prob_test = preds_test @ best_w

test_lift_1 = lift_at_percentage(y_test_arr, y_prob_test, 0.01)
test_lift_5 = lift_at_percentage(y_test_arr, y_prob_test, 0.05)
test_lift_10 = lift_at_percentage(y_test_arr, y_prob_test, 0.10)
test_auc_roc = float(_roc_auc_score(y_test_arr, y_prob_test))

print(f"\n{'='*60}")
print(f"  FINAL TEST SET EVALUATION")
print(f"{'='*60}")
print(f"  test_lift_1pct:   {test_lift_1:.6f}")
print(f"  test_lift_5pct:   {test_lift_5:.6f}")
print(f"  test_lift_10pct:  {test_lift_10:.6f}")
print(f"  test_auc_roc:     {test_auc_roc:.6f}")
print(f"  test_n:           {len(y_test_arr)}")
print(f"  test_prevalence:  {y_test_arr.mean():.4f}")
print(f"{'='*60}")

for i, name in enumerate(model_names):
    ind_lift = lift_at_percentage(y_test_arr, preds_test[:, i], 0.01)
    print(f"  {name} individual test_lift@1%: {ind_lift:.4f}")

print(f"\n  val_lift@1% (for comparison):  {val_lift:.6f}")
print(f"  val-test gap:                  {val_lift - test_lift_1:+.6f}")

# Val metrics for results.tsv
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
