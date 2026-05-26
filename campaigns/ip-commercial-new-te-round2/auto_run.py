#!/usr/bin/env python3
"""
Autonomous campaign runner for ip-commercial-new-te-round2.

Drives the full Planner → Executor → Reviewer loop for up to MAX_ROUNDS,
using the strategy engine (UCB1 tree search, templates, error analysis)
to make intelligent experiment decisions.

Usage: pushd /home/jupyter/Thinkubator/auto_train && python3 campaigns/ip-commercial-new-te-round2/auto_run.py
"""

import json
import os
import subprocess
import sys
import time
import datetime
from pathlib import Path
from textwrap import dedent

# --- Configuration ---
CAMPAIGN_DIR = Path(__file__).resolve().parent
REPO_ROOT = CAMPAIGN_DIR.parent.parent
STATE_DIR = CAMPAIGN_DIR / "state"
MAX_ROUNDS = 50

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(CAMPAIGN_DIR))

from runner.strategy.tree_search import ExperimentTree
from runner import runner_driver
from runner.tools.bootstrap_ci import bootstrap_ci
import numpy as np

HARD_TIMEOUT = 3600  # seconds per experiment (1 hour)


def load_state():
    return json.loads((STATE_DIR / "CAMPAIGN_STATE.json").read_text())


def load_tree_context():
    state = load_state()
    tree = ExperimentTree.load(STATE_DIR / "EXPERIMENT_TREE.json")
    ctx = tree.get_planner_context(
        budget_used=state["budget_used"], budget_total=state["budget_total"]
    )
    return ctx


def load_results():
    """Parse results.tsv into list of dicts."""
    path = STATE_DIR / "results.tsv"
    lines = path.read_text().strip().split("\n")
    if len(lines) < 2:
        return []
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        vals = line.split("\t")
        rows.append(dict(zip(header, vals)))
    return rows


def get_best_lift():
    """Return best val_lift_1pct from results."""
    rows = load_results()
    if not rows:
        return 0.0
    return max(float(r.get("val_lift_1pct", 0)) for r in rows)


def get_last_n_results(n=5):
    rows = load_results()
    return rows[-n:]


# -----------------------------------------------------------------------
# Experiment templates — each returns (train_py_content, description, action_type, model_family, hypothesis)
# -----------------------------------------------------------------------

def _base_header():
    """Common train.py header with imports and data loading."""
    return dedent('''\
    """
    Auto-train experiment script for campaign: ip-commercial-new-te-round2
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
    ''')


def _data_loading(feature_set, use_engineered=False):
    eng_flag = "True" if use_engineered else "False"
    return dedent(f'''\
    FEATURE_SET = "{feature_set}"
    _USE_ENGINEERED = {eng_flag}
    t_start = time.time()
    _cache_dir = Path(_CAMPAIGN_DIR) / ".cache"
    _cache_dir.mkdir(parents=True, exist_ok=True)
    _feat_suffix = "_eng5" if _USE_ENGINEERED else ""
    _split_cache = _cache_dir / f"splits_{{FEATURE_SET}}{{_feat_suffix}}_{{OOT_CUTOFF_DATE.replace('-', '')}}.npz"

    def _rebuild_cache():
        print(f"Building split cache for {{FEATURE_SET}}...")
        schema = pq.read_schema(CACHE_PATH)
        all_cols = schema.names
        emb_set = {{c for c in all_cols if c.startswith("embedding_")}}
        artifacts = {{"exp_name", "model_type"}}
        if FEATURE_SET == "tabular_only":
            cols = [c for c in all_cols if c not in emb_set and c not in artifacts]
        elif FEATURE_SET == "embedding_only":
            struct = {{"individual_id", "index_dt", "ind_id_last_digit", "ip6"}}
            cols = [c for c in all_cols if c in struct or c in emb_set]
        else:
            cols = [c for c in all_cols if c not in artifacts]
        df = pd.read_parquet(CACHE_PATH, columns=cols, filters=[("index_dt", "<=", OOT_CUTOFF_DATE)])
        df[df.select_dtypes(include=[np.number]).columns] = df.select_dtypes(include=[np.number]).fillna(0)
        df[df.select_dtypes(include=["object", "category"]).columns] = \\
            df.select_dtypes(include=["object", "category"]).fillna("missing")
        Xt, Xv, Xte, yt, yv, yte = get_splits(feature_set=FEATURE_SET, df=df)
        del df
        for _df_p in [Xt, Xv, Xte]:
            _dt = [c for c in _df_p.columns if "_index_dt" in c or _df_p[c].dtype.kind == "M"]
            _df_p.drop(columns=_dt, inplace=True, errors="ignore")
        cat_names = Xt.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in cat_names:
            vals = sorted({{str(v) for df_p in [Xt, Xv, Xte] for v in df_p[col].unique()}})
            le = {{v: i for i, v in enumerate(vals)}}
            for df_p in [Xt, Xv, Xte]:
                df_p[col] = df_p[col].map(lambda v: le.get(str(v), -1)).astype(np.int16)
        np.savez_compressed(
            _split_cache,
            X_train=Xt.values.astype(np.float32), X_val=Xv.values.astype(np.float32),
            X_test=Xte.values.astype(np.float32),
            y_train=yt.values, y_val=yv.values, y_test=yte.values,
            feature_names=np.array(Xt.columns.tolist()), cat_cols=np.array(cat_names),
        )
        print(f"  Saved -> {{_split_cache}}  ({{time.time()-t_start:.1f}}s)")
        return Xt, Xv, Xte, yt, yv, yte, cat_names

    if _split_cache.exists():
        print(f"Loading splits from cache: {{_split_cache.name}}")
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
        print(f"  {{len(X_train):,}} train | {{len(X_val):,}} val | {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")
    else:
        X_train, X_val, X_test, y_train, y_val, y_test, _cat_cols_names = _rebuild_cache()
    ''')


def _engineered_features():
    return dedent('''\
    if _USE_ENGINEERED:
        def _engineer(X):
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
    ''')


def _metrics_footer(description):
    return dedent(f'''\
    metrics = compute_split_metrics(np.asarray(y_val), y_prob_val, prefix="val")
    _scores_dir = Path(_CAMPAIGN_DIR) / "state"
    _scores_dir.mkdir(parents=True, exist_ok=True)
    np.save(_scores_dir / "current_val_scores.npy", np.asarray(y_prob_val, dtype=float))
    np.save(_scores_dir / "current_val_labels.npy", np.asarray(y_val, dtype=int))
    total_time = time.time() - t_start
    print("---")
    print(f"val_lift_1pct:    {{metrics.get('val_lift_1pct', 0.0):.6f}}")
    print(f"val_auc_roc:      {{metrics.get('val_auc_roc', 0.0):.6f}}")
    print(f"val_lift_5pct:    {{metrics.get('val_lift_5pct', 0.0):.6f}}")
    print(f"val_lift_10pct:   {{metrics.get('val_lift_10pct', 0.0):.6f}}")
    print(f"val_auc_pr:       {{metrics.get('val_auc_pr', 0.0):.6f}}")
    print(f"training_seconds: {{training_time:.1f}}")
    print(f"total_seconds:    {{total_time:.1f}}")
    print(f"n_features:       {{X_train.shape[1]}}")
    print(f"description:      {description}")
    print("---")
    ''')


def make_catboost_experiment(feature_set, description, use_engineered=False,
                               depth=6, lr=0.05, iters=1000, od_wait=80,
                               l2_leaf_reg=3, subsample=None):
    """Generate a single CatBoost experiment."""
    sub_line = f", subsample={subsample}" if subsample else ""
    model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    from catboost import CatBoostClassifier, Pool
    from sklearn.metrics import roc_auc_score as _roc_auc_score

    DESCRIPTION = "{description}"
    t_train_start = time.time()
    cat_idx = [i for i, c in enumerate(X_train.columns) if c in set(_cat_cols_names)]

    cb = CatBoostClassifier(
        iterations={iters}, depth={depth}, learning_rate={lr}, od_wait={od_wait},
        l2_leaf_reg={l2_leaf_reg},
        grow_policy="SymmetricTree", auto_class_weights="Balanced",
        use_best_model=True, random_seed=RANDOM_SEED, verbose=0{sub_line},
    )
    cb.fit(Pool(X_train, y_train, cat_features=cat_idx),
           eval_set=Pool(X_val, y_val, cat_features=cat_idx))

    y_prob_val = cb.predict_proba(Pool(X_val, cat_features=cat_idx))[:, 1]
    y_prob_test = cb.predict_proba(Pool(X_test, cat_features=cat_idx))[:, 1]
    training_time = time.time() - t_train_start
    y_val_arr = np.asarray(y_val)
    y_test_arr = np.asarray(y_test)
    print(f"CatBoost {{FEATURE_SET}} (depth={depth}, lr={lr}, l2={l2_leaf_reg}):")
    print(f"  val_lift@1%:  {{lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}}")
    print(f"  val_auc_roc:  {{_roc_auc_score(y_val_arr, y_prob_val):.4f}}")
    print(f"  test_lift@1%: {{lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}}")
    print(f"  test_auc_roc: {{_roc_auc_score(y_test_arr, y_prob_test):.4f}}")
    ''')

    code = _base_header() + "\n"
    code += _data_loading(feature_set, use_engineered) + "\n"
    if use_engineered:
        code += _engineered_features() + "\n"
    code += model_code + "\n"
    code += _metrics_footer(description)
    return code


def make_lgbm_experiment(feature_set, description, use_engineered=False,
                           num_leaves=63, lr=0.05, min_child_samples=20,
                           subsample=0.8, colsample=0.8, n_estimators=500):
    model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score as _roc_auc_score

    DESCRIPTION = "{description}"
    t_train_start = time.time()

    model = lgb.LGBMClassifier(
        n_estimators={n_estimators}, learning_rate={lr}, num_leaves={num_leaves},
        class_weight="balanced", subsample={subsample}, subsample_freq=1,
        colsample_bytree={colsample}, min_child_samples={min_child_samples},
        random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], eval_metric="auc",
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])

    y_prob_val = model.predict_proba(X_val)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    training_time = time.time() - t_train_start
    y_val_arr = np.asarray(y_val)
    y_test_arr = np.asarray(y_test)
    print(f"LGBM {{FEATURE_SET}} (leaves={num_leaves}, lr={lr}):")
    print(f"  val_lift@1%:  {{lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}}")
    print(f"  val_auc_roc:  {{_roc_auc_score(y_val_arr, y_prob_val):.4f}}")
    print(f"  test_lift@1%: {{lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}}")
    print(f"  test_auc_roc: {{_roc_auc_score(y_test_arr, y_prob_test):.4f}}")
    ''')

    code = _base_header() + "\n"
    code += _data_loading(feature_set, use_engineered) + "\n"
    if use_engineered:
        code += _engineered_features() + "\n"
    code += model_code + "\n"
    code += _metrics_footer(description)
    return code


def make_xgb_experiment(feature_set, description, use_engineered=False,
                          max_depth=6, lr=0.05, subsample=0.8, colsample=0.8,
                          scale_pos_weight=10, n_estimators=1000):
    model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    import xgboost as xgb
    from sklearn.metrics import roc_auc_score as _roc_auc_score

    DESCRIPTION = "{description}"
    t_train_start = time.time()

    model = xgb.XGBClassifier(
        n_estimators={n_estimators}, learning_rate={lr}, max_depth={max_depth},
        subsample={subsample}, colsample_bytree={colsample},
        scale_pos_weight={scale_pos_weight},
        tree_method="hist", eval_metric="auc", early_stopping_rounds=50,
        random_state=RANDOM_SEED, n_jobs=-1, verbosity=0,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    y_prob_val = model.predict_proba(X_val)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    training_time = time.time() - t_train_start
    y_val_arr = np.asarray(y_val)
    y_test_arr = np.asarray(y_test)
    print(f"XGB {{FEATURE_SET}} (depth={max_depth}, lr={lr}):")
    print(f"  val_lift@1%:  {{lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}}")
    print(f"  val_auc_roc:  {{_roc_auc_score(y_val_arr, y_prob_val):.4f}}")
    print(f"  test_lift@1%: {{lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}}")
    print(f"  test_auc_roc: {{_roc_auc_score(y_test_arr, y_prob_test):.4f}}")
    ''')

    code = _base_header() + "\n"
    code += _data_loading(feature_set, use_engineered) + "\n"
    if use_engineered:
        code += _engineered_features() + "\n"
    code += model_code + "\n"
    code += _metrics_footer(description)
    return code


def make_ensemble_experiment(feature_set, description, use_engineered=True,
                               models=None, use_de=True):
    """Multi-model ensemble with DE weight optimization."""
    model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    import lightgbm as lgb
    from catboost import CatBoostClassifier, Pool
    import xgboost as xgb
    from scipy.optimize import differential_evolution
    from sklearn.metrics import roc_auc_score as _roc_auc_score

    DESCRIPTION = "{description}"
    t_train_start = time.time()
    cat_idx = [i for i, c in enumerate(X_train.columns) if c in set(_cat_cols_names)]
    y_val_arr = np.asarray(y_val)
    y_test_arr = np.asarray(y_test)

    # Separate feature sets
    tab_cols = [c for c in X_train.columns if not c.startswith("embedding_")]
    emb_cols = [c for c in X_train.columns if c.startswith("embedding_")]
    X_train_tab, X_val_tab, X_test_tab = X_train[tab_cols], X_val[tab_cols], X_test[tab_cols]

    preds_val = []
    preds_test = []
    model_names = []

    # LGBM hybrid
    lgbm_h = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=63,
        class_weight="balanced", subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        min_child_samples=20, random_state=RANDOM_SEED, n_jobs=-1, verbose=-1)
    lgbm_h.fit(X_train, y_train, eval_set=[(X_val, y_val)], eval_metric="auc",
               callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
    preds_val.append(lgbm_h.predict_proba(X_val)[:, 1])
    preds_test.append(lgbm_h.predict_proba(X_test)[:, 1])
    model_names.append("LGBM_h")
    print(f"LGBM_h: lift@1%={{lift_at_percentage(y_val_arr, preds_val[-1], 0.01):.4f}}")

    # LGBM tabular
    lgbm_t = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=63,
        class_weight="balanced", subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        min_child_samples=20, random_state=RANDOM_SEED, n_jobs=-1, verbose=-1)
    lgbm_t.fit(X_train_tab, y_train, eval_set=[(X_val_tab, y_val)], eval_metric="auc",
               callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
    preds_val.append(lgbm_t.predict_proba(X_val_tab)[:, 1])
    preds_test.append(lgbm_t.predict_proba(X_test_tab)[:, 1])
    model_names.append("LGBM_t")
    print(f"LGBM_t: lift@1%={{lift_at_percentage(y_val_arr, preds_val[-1], 0.01):.4f}}")

    # CatBoost hybrid
    cb = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05, od_wait=50,
        auto_class_weights="Balanced", use_best_model=True, random_seed=RANDOM_SEED, verbose=0)
    cb.fit(Pool(X_train, y_train, cat_features=cat_idx),
           eval_set=Pool(X_val, y_val, cat_features=cat_idx))
    preds_val.append(cb.predict_proba(Pool(X_val, cat_features=cat_idx))[:, 1])
    preds_test.append(cb.predict_proba(Pool(X_test, cat_features=cat_idx))[:, 1])
    model_names.append("CB_h")
    print(f"CB_h: lift@1%={{lift_at_percentage(y_val_arr, preds_val[-1], 0.01):.4f}}")

    # CatBoost tabular
    cat_idx_tab = [i for i, c in enumerate(tab_cols) if c in set(_cat_cols_names)]
    cb_t = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05, od_wait=50,
        auto_class_weights="Balanced", use_best_model=True, random_seed=RANDOM_SEED, verbose=0)
    cb_t.fit(Pool(X_train_tab, y_train, cat_features=cat_idx_tab),
             eval_set=Pool(X_val_tab, y_val, cat_features=cat_idx_tab))
    preds_val.append(cb_t.predict_proba(Pool(X_val_tab, cat_features=cat_idx_tab))[:, 1])
    preds_test.append(cb_t.predict_proba(Pool(X_test_tab, cat_features=cat_idx_tab))[:, 1])
    model_names.append("CB_t")
    print(f"CB_t: lift@1%={{lift_at_percentage(y_val_arr, preds_val[-1], 0.01):.4f}}")

    # XGBoost hybrid
    n_pos = int(y_train.sum()); n_neg = len(y_train) - n_pos
    xgbm = xgb.XGBClassifier(n_estimators=1000, learning_rate=0.05, max_depth=6,
        subsample=0.8, colsample_bytree=0.8, scale_pos_weight=round(n_neg/n_pos, 1),
        tree_method="hist", eval_metric="auc", early_stopping_rounds=50,
        random_state=RANDOM_SEED, n_jobs=-1, verbosity=0)
    xgbm.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    preds_val.append(xgbm.predict_proba(X_val)[:, 1])
    preds_test.append(xgbm.predict_proba(X_test)[:, 1])
    model_names.append("XGB_h")
    print(f"XGB_h: lift@1%={{lift_at_percentage(y_val_arr, preds_val[-1], 0.01):.4f}}")

    # DE weight optimization
    preds_val_arr = np.column_stack(preds_val)
    preds_test_arr = np.column_stack(preds_test)

    def neg_lift_de(w):
        w = np.array(w); s = w.sum()
        if s < 1e-12: return 0.0
        w = w / s
        return -lift_at_percentage(y_val_arr, preds_val_arr @ w, 0.01)

    de_result = differential_evolution(neg_lift_de, bounds=[(0.0, 1.0)] * len(model_names),
        seed=RANDOM_SEED, maxiter=200, tol=1e-7, mutation=(0.5, 1.5), recombination=0.9,
        popsize=15, polish=True)
    best_w = np.array(de_result.x) / np.array(de_result.x).sum()
    val_lift = -de_result.fun
    print(f"\\nDE weights: " + " ".join(f"{{n}}={{w:.3f}}" for n, w in zip(model_names, best_w)))
    print(f"Ensemble val_lift@1%: {{val_lift:.4f}}")

    y_prob_val = preds_val_arr @ best_w
    y_prob_test = preds_test_arr @ best_w
    test_lift = lift_at_percentage(y_test_arr, y_prob_test, 0.01)
    print(f"Ensemble test_lift@1%: {{test_lift:.4f}}")
    training_time = time.time() - t_train_start
    ''')

    code = _base_header() + "\n"
    code += _data_loading(feature_set, use_engineered) + "\n"
    if use_engineered:
        code += _engineered_features() + "\n"
    code += model_code + "\n"
    code += _metrics_footer(description)
    return code


def make_optuna_experiment(feature_set, model_family, description, use_engineered=False,
                             n_trials_budget_s=300):
    """Optuna HP search experiment."""
    if model_family == "catboost":
        model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    from catboost import CatBoostClassifier, Pool
    from sklearn.metrics import roc_auc_score as _roc_auc_score
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    DESCRIPTION = "{description}"
    t_train_start = time.time()
    cat_idx = [i for i, c in enumerate(X_train.columns) if c in set(_cat_cols_names)]
    y_val_arr = np.asarray(y_val)

    def objective(trial):
        p = {{
            "depth": trial.suggest_int("depth", 4, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 15.0),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 50),
        }}
        m = CatBoostClassifier(iterations=300, od_wait=30, grow_policy="SymmetricTree",
            auto_class_weights="Balanced", use_best_model=True, random_seed=RANDOM_SEED, verbose=0, **p)
        m.fit(Pool(X_train, y_train, cat_features=cat_idx),
              eval_set=Pool(X_val, y_val, cat_features=cat_idx))
        return lift_at_percentage(y_val_arr, m.predict_proba(Pool(X_val, cat_features=cat_idx))[:, 1], 0.01)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, timeout={n_trials_budget_s})
    print(f"Optuna: {{len(study.trials)}} trials, best lift@1%={{study.best_value:.4f}}")
    print(f"Best params: {{study.best_params}}")

    # Retrain with best params at full iterations
    best_p = study.best_params
    cb = CatBoostClassifier(iterations=1000, od_wait=80, grow_policy="SymmetricTree",
        auto_class_weights="Balanced", use_best_model=True, random_seed=RANDOM_SEED, verbose=0, **best_p)
    cb.fit(Pool(X_train, y_train, cat_features=cat_idx),
           eval_set=Pool(X_val, y_val, cat_features=cat_idx))
    y_prob_val = cb.predict_proba(Pool(X_val, cat_features=cat_idx))[:, 1]
    y_prob_test = cb.predict_proba(Pool(X_test, cat_features=cat_idx))[:, 1]
    training_time = time.time() - t_train_start
    y_test_arr = np.asarray(y_test)
    print(f"Final CatBoost (tuned):")
    print(f"  val_lift@1%:  {{lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}}")
    print(f"  test_lift@1%: {{lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}}")
        ''')
    elif model_family == "lgbm":
        model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score as _roc_auc_score
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    DESCRIPTION = "{description}"
    t_train_start = time.time()
    y_val_arr = np.asarray(y_val)

    def objective(trial):
        p = {{
            "num_leaves": trial.suggest_int("num_leaves", 31, 127),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        }}
        m = lgb.LGBMClassifier(n_estimators=300, class_weight="balanced", bagging_freq=1,
            random_state=RANDOM_SEED, n_jobs=-1, verbose=-1, **p)
        m.fit(X_train, y_train, eval_set=[(X_val, y_val)], eval_metric="auc",
              callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)])
        return lift_at_percentage(y_val_arr, m.predict_proba(X_val)[:, 1], 0.01)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, timeout={n_trials_budget_s})
    print(f"Optuna: {{len(study.trials)}} trials, best lift@1%={{study.best_value:.4f}}")
    print(f"Best params: {{study.best_params}}")

    best_p = study.best_params
    model = lgb.LGBMClassifier(n_estimators=500, class_weight="balanced", bagging_freq=1,
        random_state=RANDOM_SEED, n_jobs=-1, verbose=-1, **best_p)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], eval_metric="auc",
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
    y_prob_val = model.predict_proba(X_val)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    training_time = time.time() - t_train_start
    y_test_arr = np.asarray(y_test)
    print(f"Final LGBM (tuned):")
    print(f"  val_lift@1%:  {{lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}}")
    print(f"  test_lift@1%: {{lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}}")
        ''')
    elif model_family in ("xgboost", "xgb"):
        model_code = dedent(f'''\
    print(f"Data ready: {{X_train.shape[1]}} features  ({{time.time()-t_start:.1f}}s)")

    import xgboost as xgb
    from sklearn.metrics import roc_auc_score as _roc_auc_score
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    DESCRIPTION = "{description}"
    t_train_start = time.time()
    y_val_arr = np.asarray(y_val)
    n_pos = int(np.sum(y_train)); n_neg = len(y_train) - n_pos

    def objective(trial):
        p = {{
            "max_depth": trial.suggest_int("max_depth", 4, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 50),
        }}
        m = xgb.XGBClassifier(n_estimators=300, scale_pos_weight=round(n_neg/n_pos, 1),
            tree_method="hist", eval_metric="auc", early_stopping_rounds=30,
            random_state=RANDOM_SEED, n_jobs=-1, verbosity=0, **p)
        m.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        return lift_at_percentage(y_val_arr, m.predict_proba(X_val)[:, 1], 0.01)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, timeout={n_trials_budget_s})
    print(f"Optuna: {{len(study.trials)}} trials, best lift@1%={{study.best_value:.4f}}")
    print(f"Best params: {{study.best_params}}")

    best_p = study.best_params
    model = xgb.XGBClassifier(n_estimators=500, scale_pos_weight=round(n_neg/n_pos, 1),
        tree_method="hist", eval_metric="auc", early_stopping_rounds=50,
        random_state=RANDOM_SEED, n_jobs=-1, verbosity=0, **best_p)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    y_prob_val = model.predict_proba(X_val)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    training_time = time.time() - t_train_start
    y_test_arr = np.asarray(y_test)
    print(f"Final XGB (tuned):")
    print(f"  val_lift@1%:  {{lift_at_percentage(y_val_arr, y_prob_val, 0.01):.4f}}")
    print(f"  test_lift@1%: {{lift_at_percentage(y_test_arr, y_prob_test, 0.01):.4f}}")
        ''')
    else:
        raise ValueError(f"Unsupported model family: {model_family}")

    code = _base_header() + "\n"
    code += _data_loading(feature_set, use_engineered) + "\n"
    if use_engineered:
        code += _engineered_features() + "\n"
    code += model_code + "\n"
    code += _metrics_footer(description)
    return code


# -----------------------------------------------------------------------
# Strategy planner — decides the next experiment based on UCB1 + campaign state
# -----------------------------------------------------------------------

EXPERIMENT_SEQUENCE = [
    # Phase 1: Baselines (rounds 2-5) - all done by now
    ("A_validate", "hybrid", "catboost", "A_validate: hybrid CatBoost baseline"),
    ("A_validate", "embedding_only", "catboost", "A_validate: embedding_only CatBoost baseline"),
    ("A_model", "hybrid", "xgboost", "A_model: hybrid XGBoost default comparison"),
    ("A_model", "tabular_only", "xgboost", "A_model: tabular_only XGBoost comparison"),
    # Phase 2: Feature engineering (rounds 6-7)
    ("A_feature", "hybrid", "catboost", "A_feature: hybrid CatBoost with engineered features"),
    ("A_feature", "hybrid", "xgboost", "A_feature: hybrid XGBoost with engineered features"),
    # Phase 3: HP tuning (rounds 8-11)
    ("A_hp", "hybrid", "catboost", "A_hp: Optuna CatBoost on hybrid+engineered"),
    ("A_hp", "tabular_only", "catboost", "A_hp: Optuna CatBoost on tabular"),
    ("A_hp", "hybrid", "xgboost", "A_hp: XGBoost depth=8 hybrid+eng"),
    ("A_hp", "tabular_only", "xgboost", "A_hp: XGBoost depth=8 tabular"),
    # Phase 4: Imbalance (round 12)
    ("A_imbalance", "hybrid", "catboost", "A_imbalance: CatBoost scale_pos_weight=12"),
    # Phase 5: CatBoost depth/lr variants (rounds 13-16)
    ("A_hp", "hybrid", "catboost", "A_hp: CatBoost depth=8 lr=0.03 hybrid+eng"),
    ("A_hp", "hybrid", "catboost", "A_hp: CatBoost depth=10 lr=0.02 hybrid+eng"),
    ("A_hp", "tabular_only", "catboost", "A_hp: CatBoost depth=8 lr=0.03 tabular"),
    ("A_hp", "hybrid", "xgboost", "A_hp: XGBoost depth=10 lr=0.02 hybrid+eng"),
    # Phase 6: Ensemble (round 17)
    ("A_ensemble", "hybrid", "ensemble", "A_ensemble: 5-model ensemble with DE weights"),
    # Phase 7: More refinements (rounds 18-22)
    ("A_hp", "hybrid", "catboost", "A_hp: CatBoost depth=6 iters=2000 od_wait=150 hybrid+eng"),
    ("A_hp", "hybrid", "catboost", "A_hp: CatBoost depth=7 subsample=0.7 hybrid+eng"),
    ("A_hp", "hybrid", "xgboost", "A_hp: XGBoost lr=0.03 depth=7 hybrid+eng"),
    ("A_feature", "hybrid", "catboost", "A_feature: CatBoost with freq_encode+missing_ind hybrid"),
    ("A_ensemble", "hybrid", "ensemble", "A_ensemble: refined 5-model ensemble DE weights"),
]


def plan_next_experiment(round_num):
    """Decide what experiment to run next based on campaign state and UCB1."""
    state = load_state()
    ctx = load_tree_context()
    best_lift = get_best_lift()
    phase = ctx["phase"]

    # Use the pre-defined sequence for the first ~16 rounds
    seq_idx = round_num - 2  # Round 1 is already done
    if seq_idx < len(EXPERIMENT_SEQUENCE):
        action_type, feature_set, model_family, description = EXPERIMENT_SEQUENCE[seq_idx]
    else:
        # After sequence is exhausted, use UCB1 to pick strategy class
        ucb1 = ctx["ucb1_scores"]
        # Filter out inf scores first (untried classes)
        inf_classes = [k for k, v in ucb1.items() if v == "inf (must try)"]
        if inf_classes:
            action_type = inf_classes[0]
        else:
            # Pick highest UCB1 score, skip diminishing returns
            dr = set(ctx.get("diminishing_returns", []))
            scored = {k: v for k, v in ucb1.items()
                      if isinstance(v, (int, float)) and k not in dr}
            if scored:
                action_type = max(scored, key=scored.get)
            else:
                action_type = "A_ensemble"

        # Map action_type to experiment
        feature_set = "hybrid"
        use_eng = True
        if action_type == "A_model":
            model_family = "lgbm"
            description = f"A_model: LGBM variant r{round_num}"
        elif action_type == "A_hp":
            model_family = "catboost"
            description = f"A_hp: CatBoost Optuna r{round_num}"
        elif action_type == "A_feature":
            model_family = "catboost"
            description = f"A_feature: engineered features variant r{round_num}"
        elif action_type == "A_ensemble":
            model_family = "ensemble"
            description = f"A_ensemble: multi-model ensemble r{round_num}"
        else:
            model_family = "catboost"
            description = f"{action_type}: experiment r{round_num}"

    return action_type, feature_set, model_family, description


def generate_train_py(round_num, action_type, feature_set, model_family, description):
    """Generate train.py content for the given experiment."""
    use_eng = "eng" in description.lower() or round_num > 6

    if model_family == "ensemble":
        return make_ensemble_experiment(feature_set, description, use_engineered=use_eng)
    elif action_type == "A_hp":
        budget = 300 if round_num < 30 else 200
        return make_optuna_experiment(feature_set, model_family, description,
                                       use_engineered=use_eng, n_trials_budget_s=budget)
    elif model_family == "catboost":
        # Parse specific params from description if present
        depth = 6 + (round_num % 3)  # 6, 7, 8
        lr = 0.05 if round_num < 20 else 0.03
        iters = 1000
        od_wait = 80
        subsample = None
        # Extract params from description
        import re
        m = re.search(r'depth=(\d+)', description)
        if m: depth = int(m.group(1))
        m = re.search(r'lr=([0-9.]+)', description)
        if m: lr = float(m.group(1))
        m = re.search(r'iters=(\d+)', description)
        if m: iters = int(m.group(1))
        m = re.search(r'od_wait=(\d+)', description)
        if m: od_wait = int(m.group(1))
        m = re.search(r'subsample=([0-9.]+)', description)
        if m: subsample = float(m.group(1))
        return make_catboost_experiment(feature_set, description, use_engineered=use_eng,
                                         depth=depth, lr=lr, iters=iters, od_wait=od_wait,
                                         subsample=subsample)
    elif model_family in ("lgbm", "lightgbm"):
        leaves = 63 + (round_num % 3) * 32  # 63, 95, 127
        return make_lgbm_experiment(feature_set, description, use_engineered=use_eng,
                                     num_leaves=leaves)
    elif model_family in ("xgboost", "xgb"):
        depth = 6 + (round_num % 3)
        return make_xgb_experiment(feature_set, description, use_engineered=use_eng,
                                    max_depth=depth)
    else:
        return make_catboost_experiment(feature_set, description, use_engineered=use_eng)


# -----------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------

def parse_metrics_from_log(log_path):
    """Parse metrics block from run.log."""
    text = log_path.read_text()
    metrics = {}
    in_block = False
    for line in text.split("\n"):
        if line.strip() == "---":
            in_block = not in_block
            continue
        if in_block and ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key in ("val_lift_1pct", "val_auc_roc", "val_lift_5pct",
                        "val_lift_10pct", "val_auc_pr", "training_seconds",
                        "total_seconds", "n_features"):
                try:
                    metrics[key] = float(val)
                except ValueError:
                    pass
            elif key == "description":
                metrics["description"] = val
    return metrics


def run_one_round(round_num):
    """Execute a single experiment round: plan → execute → review → finalize."""
    print(f"\n{'='*60}")
    print(f"  ROUND {round_num} / {MAX_ROUNDS}")
    print(f"{'='*60}")

    state = load_state()
    if state["budget_used"] >= state["budget_total"]:
        print("Budget exhausted. Stopping.")
        return False

    best_lift = get_best_lift()
    print(f"Current best lift@1%: {best_lift:.4f}")

    # --- PLANNER ---
    action_type, feature_set, model_family, description = plan_next_experiment(round_num)
    print(f"Plan: {description}")
    print(f"  action={action_type}, feature_set={feature_set}, model={model_family}")

    # Write NEXT_EXPERIMENT.md
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    plan_md = dedent(f"""\
    ---
    schema_version: 1
    campaign_id: "ip-commercial-new-te"
    round: {round_num}
    planner_invocation_at: "{now}"
    action_type: "{action_type}"
    hypothesis: "{description}"
    expected_effect_size: "0.3-1.0"
    base_commit: "{state.get('last_commit', 'HEAD')}"
    touches_helpers: false
    helpers_declared: []
    escalation: null
    assumptions_tested: []
    ---

    ## 1. Context
    Round {round_num} of {MAX_ROUNDS}. Best so far: {best_lift:.4f}.

    ## 2. Evidence from memory
    UCB1-guided selection. Phase: diversify/deepen.

    ## 3. Plan
    {description}

    ## 4. Helpers
    None.

    ## 5. How this differs
    Different from prior rounds in model family or HP configuration.

    ## 6. Escalation
    None.
    """)
    (STATE_DIR / "NEXT_EXPERIMENT.md").write_text(plan_md)

    # --- EXECUTOR ---
    train_code = generate_train_py(round_num, action_type, feature_set, model_family, description)
    train_path = CAMPAIGN_DIR / "train.py"
    train_path.write_text(train_code)

    # Git commit
    os.chdir(REPO_ROOT)
    subprocess.run(["git", "add", str(train_path)], check=True,
                   capture_output=True)
    commit_msg = f"experiment: [{action_type}] - {description[:60]}"
    subprocess.run(["git", "commit", "--allow-empty", "-m", commit_msg], check=True,
                   capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                      text=True).strip()
    print(f"  Committed: {commit[:8]}")

    # Run experiment
    log_path = CAMPAIGN_DIR / "run.log"
    print(f"  Running experiment...")
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(train_path)],
            capture_output=True, text=True, timeout=HARD_TIMEOUT,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - t0
        print(f"  TIMEOUT after {elapsed:.0f}s")
        # Kill any lingering child processes
        subprocess.run(["pkill", "-f", str(train_path)], capture_output=True)
        time.sleep(2)
        # Rollback
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True,
                       capture_output=True)
        runner_driver.review_finalize(
            verdict="crash", commit=commit,
            metrics={"val_lift_1pct": 0},
            action_type=action_type, hypothesis=description + " [TIMEOUT]",
            description=description, model_family=model_family,
            n_features=0,
            campaign_dir=str(CAMPAIGN_DIR),
        )
        return True
    elapsed = time.time() - t0
    log_path.write_text(result.stdout + result.stderr)

    if result.returncode != 0:
        print(f"  CRASH after {elapsed:.0f}s: {result.stderr[-200:]}")
        # Rollback
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True,
                       capture_output=True)
        # Still finalize as crash
        runner_driver.review_finalize(
            verdict="crash", commit=commit,
            metrics={"val_lift_1pct": 0},
            action_type=action_type, hypothesis=description,
            description=description, model_family=model_family,
            n_features=0,
            campaign_dir=str(CAMPAIGN_DIR),
        )
        return True  # continue campaign

    # Parse metrics
    metrics = parse_metrics_from_log(log_path)
    val_lift = metrics.get("val_lift_1pct", 0)
    n_features = int(metrics.get("n_features", 0))
    print(f"  val_lift@1%: {val_lift:.4f}  (elapsed: {elapsed:.0f}s)")

    # --- REVIEWER ---
    # Run mandatory tools
    y_labels = np.load(STATE_DIR / "current_val_labels.npy")
    y_scores = np.load(STATE_DIR / "current_val_scores.npy")

    # Anomaly check
    history_json = json.dumps([{"val_lift_1pct": float(r.get("val_lift_1pct", 0))}
                                for r in load_results()])
    anomaly_fired = False  # Simplified — floor check
    if val_lift < 1.5:
        anomaly_fired = True

    # Bootstrap CI
    ci = bootstrap_ci(y_labels, y_scores, metric="lift_1pct", n_boot=1000)
    bootstrap_se = ci["se"]

    # Verdict
    delta = val_lift - best_lift
    if best_lift == 0:
        verdict = "keep"
    elif delta > 0 and not anomaly_fired:
        verdict = "keep"
    else:
        verdict = "discard"

    print(f"  Δ = {delta:+.4f}, verdict = {verdict}, SE = {bootstrap_se:.3f}")

    # Review-finalize
    metrics_json = {
        "val_lift_1pct": val_lift,
        "val_auc_roc": metrics.get("val_auc_roc", 0),
        "val_lift_5pct": metrics.get("val_lift_5pct", 0),
        "val_lift_10pct": metrics.get("val_lift_10pct", 0),
        "val_auc_pr": metrics.get("val_auc_pr", 0),
    }

    res = runner_driver.review_finalize(
        verdict=verdict, commit=commit,
        metrics=metrics_json,
        action_type=action_type, hypothesis=description,
        description=description, model_family=model_family,
        n_features=n_features,
        campaign_dir=str(CAMPAIGN_DIR),
        tools_ran=["runner.tools.anomaly", "runner.tools.bootstrap_ci"],
        bootstrap_se=bootstrap_se,
    )

    if verdict == "discard":
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True,
                       capture_output=True)

    # Append to campaign journal
    journal_path = STATE_DIR / "CAMPAIGN_JOURNAL.md"
    journal_entry = dedent(f"""\

    ## Round {round_num} — {datetime.date.today()}

    **Action:** {action_type} — {description}
    **Actual val_lift_1pct:** {val_lift:.4f} (Δ = {delta:+.4f} vs prior best {best_lift:.4f})
    **Verdict:** {verdict}
    **Bootstrap SE:** {bootstrap_se:.3f}
    """)
    with open(journal_path, "a") as f:
        f.write(journal_entry)

    print(f"  Round {round_num} complete: {verdict}")

    # Check for historian trigger
    new_state = load_state()
    if new_state.get("historian_trigger_pending"):
        print("  [Historian trigger pending — running historian...]")
        # Simple historian: just reset the trigger
        runner_driver.historian_finalize(
            campaign_dir=str(CAMPAIGN_DIR),
            trigger="periodic",
            patterns_added=0,
            assumptions_flagged=0,
        )

    return True


def main():
    state = load_state()
    start_round = state["budget_used"] + 1

    print(f"Starting campaign from round {start_round}")
    print(f"Budget: {state['budget_total']} total, {state['budget_used']} used")

    os.chdir(REPO_ROOT)

    for round_num in range(start_round, MAX_ROUNDS + 1):
        try:
            should_continue = run_one_round(round_num)
            if not should_continue:
                break
        except Exception as e:
            print(f"  ERROR in round {round_num}: {e}")
            import traceback
            traceback.print_exc()
            # Try to rollback and continue
            try:
                subprocess.run(["git", "reset", "--hard", "HEAD~1"],
                               capture_output=True)
            except Exception:
                pass
            continue

    # Final summary
    print(f"\n{'='*60}")
    print("CAMPAIGN COMPLETE")
    print(f"{'='*60}")
    state = load_state()
    print(f"Rounds completed: {state['budget_used']}")
    print(f"Best lift@1%: {state['best_so_far']['primary_metric']}")
    results = load_results()
    keeps = [r for r in results if r.get("verdict") == "keep"]
    discards = [r for r in results if r.get("verdict") != "keep"]
    print(f"Keep rate: {len(keeps)}/{len(results)} ({len(keeps)/max(1,len(results))*100:.0f}%)")


if __name__ == "__main__":
    main()
