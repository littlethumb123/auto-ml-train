"""
Frozen evaluation and data infrastructure for the ip-commercial-new-te campaign.

DO NOT MODIFY this file. It is the fixed evaluation contract for this campaign.
The Executor may only read from this module — never write to it.

Data source: BigQuery prejoined modeling table (new TE embeddings + tabular features + ip6 outcome).
             Cached locally to campaigns/ip-commercial-new-te/.cache/new_te.parquet on first run.

Provides:
    - Constants: TIME_BUDGET, RANDOM_SEED, TARGET_COL, OOT_CUTOFF_DATE
    - EXCLUDE_COLUMNS: frozen leakage exclusion list (matches notebook verbatim)
    - load_data()          — loads from parquet cache or BigQuery
    - get_splits(feature_set)  — digit-based train/val/test splits with downsampling
    - evaluate(model, X_val, y_val)  — computes val_lift_1pct + secondary metrics
    - print_summary(metrics, ...)    — structured stdout block for log parsing

Usage:
    from prepare import get_splits, evaluate, print_summary, TIME_BUDGET, RANDOM_SEED
"""

import os
import warnings
import gc
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants (frozen — do not modify)
# ---------------------------------------------------------------------------

TIME_BUDGET = 90            # seconds per experiment (model training only)
RANDOM_SEED = 42
TARGET_COL = "ip6"
OOT_CUTOFF_DATE = "2025-06-30"
NEGATIVE_DOWNSAMPLE_RATIO = 10   # 10 negatives per positive in train split

MODELING_TABLE = (
    "edp-prod-storage.edp_ent_sdoheir_cns"
    ".a834793_Commercial_formal_training_full_downstream_new_te_features_outcomes_exp_round10_exp2b"
)

_REPO_ROOT = Path(__file__).parent
CACHE_PATH = _REPO_ROOT / "campaigns" / "ip-commercial-new-te" / ".cache" / "new_te.parquet"

# ---------------------------------------------------------------------------
# Leakage exclusion list — frozen, matches notebook EXCLUDE_COLUMNS verbatim
# ---------------------------------------------------------------------------

EXCLUDE_COLUMNS = frozenset([
    # Keys and identifiers
    "individual_id", "member_id", "index_dt", "birth_dt", "feature_end_dt",
    # Outcome columns
    "ip6", "sum_ip6_admits", "sum_ip6_los", "sum_ip6_acu_days",
    # Eligibility / continuity flags
    "mon_3_include", "mon_6_include", "mon_12_include",
    "exclude_ip", "include_post_6_status",
    # Split key
    "ind_id_last_digit",
    # Join audit column (embedding timestamp, not a feature)
    "matched_embedding_index_dt",
    # Leakage — claim amounts overlap with the outcome window
    "clm_allowed_amt_1yr", "clm_allowed_amt_2yr", "clm_allowed_amt_3mo", "clm_allowed_amt_6mo",
    "clm_paid_amt_1yr", "clm_paid_amt_2yr", "clm_paid_amt_3mo", "clm_paid_amt_6mo",
    "clm_par_allowed_amt_1yr", "clm_par_allowed_amt_2yr",
    "clm_par_allowed_amt_3mo", "clm_par_allowed_amt_6mo",
    "clm_par_paid_amt_1yr", "clm_par_paid_amt_2yr",
    "clm_par_paid_amt_3mo", "clm_par_paid_amt_6mo",
    "clm_srv_copay_amt_1yr", "clm_srv_copay_amt_3mo", "clm_srv_copay_amt_6mo",
    # Leakage — post-index outcome or intervention flags
    "covid_19", "hpd_major_flag", "chronic",
    "txt_member", "txt_referral", "txt_1yr_outreach", "talked",
])

# ---------------------------------------------------------------------------
# Data loading (parquet cache → BigQuery fallback)
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Load the prejoined modeling table.

    Reads from local parquet cache if it exists (fast, ~3-5s).
    Downloads from BigQuery and writes the cache on first call (~20-30s).
    """
    if CACHE_PATH.exists():
        df = pd.read_parquet(CACHE_PATH)
        print(f"Loaded {len(df):,} rows from parquet cache ({CACHE_PATH.name})")
        return df

    print(f"Cache not found at {CACHE_PATH} — downloading from BigQuery...")
    from shared.bq_loader import load_bigquery_table_storage_api
    df = load_bigquery_table_storage_api(MODELING_TABLE, max_stream_count=10, verbose=True)

    # Normalize: parse dates, dedup on (individual_id, index_dt)
    df["index_dt"] = pd.to_datetime(df["index_dt"]).dt.strftime("%Y-%m-%d")
    df["individual_id"] = df["individual_id"].astype(str)
    if "matched_embedding_index_dt" in df.columns:
        df["matched_embedding_index_dt"] = (
            pd.to_datetime(df["matched_embedding_index_dt"]).dt.strftime("%Y-%m-%d")
        )
    df = df.drop_duplicates(subset=["individual_id", "index_dt"], keep="last")

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_PATH, index=False)
    print(f"Cached {len(df):,} rows to {CACHE_PATH}")
    return df


def _identify_feature_columns(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Return (embedding_features, tabular_features).

    embedding_features: columns starting with 'embedding_'
    tabular_features:   all other columns minus EXCLUDE_COLUMNS and target
    """
    all_cols = set(df.columns)
    embedding_features = sorted(c for c in all_cols if c.startswith("embedding_"))
    excluded = EXCLUDE_COLUMNS | set(embedding_features)
    tabular_features = sorted(
        c for c in all_cols if c not in excluded and c != TARGET_COL
    )
    return embedding_features, tabular_features


def _downsample_negatives(
    X: pd.DataFrame,
    y: pd.Series,
    ratio: int = NEGATIVE_DOWNSAMPLE_RATIO,
    random_state: int = RANDOM_SEED,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Downsample negatives to `ratio` per positive in the training set."""
    rng = np.random.default_rng(random_state)
    pos_idx = X.index[y == 1].tolist()
    neg_idx = X.index[y == 0].tolist()
    n_pos = len(pos_idx)
    target_neg = int(n_pos * ratio)

    if len(neg_idx) <= target_neg:
        return X, y

    sampled_neg = rng.choice(neg_idx, size=target_neg, replace=False).tolist()
    keep = pos_idx + sampled_neg
    shuffle = rng.permutation(len(keep))
    X_res = X.loc[keep].iloc[shuffle].reset_index(drop=True)
    y_res = y.loc[keep].iloc[shuffle].reset_index(drop=True)
    print(
        f"  Downsampled train: {len(neg_idx)}:{n_pos} → {target_neg}:{n_pos} "
        f"({ratio}:1 neg:pos)"
    )
    return X_res, y_res


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------

def get_splits(
    feature_set: str = "tabular_only",
    df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Return digit-based train/val/test splits with training set downsampled 10:1.

    Args:
        feature_set: 'tabular_only' | 'embedding_only' | 'hybrid'
        df: optional pre-loaded DataFrame (skips load_data if provided)

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
    """
    valid = {"tabular_only", "embedding_only", "hybrid"}
    if feature_set not in valid:
        raise ValueError(f"feature_set must be one of {valid}, got {feature_set!r}")

    if df is None:
        df = load_data()

    oot_cutoff = pd.to_datetime(OOT_CUTOFF_DATE)
    df = df.copy()
    df["_index_dt_parsed"] = pd.to_datetime(df["index_dt"])

    # In-time only (OOT excluded from train/val/test)
    in_time = df[df["_index_dt_parsed"] <= oot_cutoff].copy()

    train_df = in_time[in_time["ind_id_last_digit"].isin([0, 1, 2, 3, 4, 5, 6, 7])]
    val_df   = in_time[in_time["ind_id_last_digit"] == 8]
    test_df  = in_time[in_time["ind_id_last_digit"] == 9]

    # Print split summary
    for name, split in [("train", train_df), ("val", val_df), ("test", test_df)]:
        prev = split[TARGET_COL].mean() * 100
        print(f"  {name}: {len(split):,} rows, {int(split[TARGET_COL].sum())} positives ({prev:.2f}%)")

    embedding_features, tabular_features = _identify_feature_columns(in_time)
    if feature_set == "embedding_only":
        feature_cols = embedding_features
    elif feature_set == "tabular_only":
        feature_cols = tabular_features
    else:  # hybrid
        feature_cols = tabular_features + embedding_features

    print(f"  Feature set: {feature_set} — {len(feature_cols)} features "
          f"({len(embedding_features)} embedding, {len(tabular_features)} tabular)")

    def _xy(split_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        X = split_df[feature_cols].copy()
        y = split_df[TARGET_COL].astype(int)
        # Fill missing
        num_cols = X.select_dtypes(include=[np.number]).columns
        X[num_cols] = X[num_cols].fillna(0)
        cat_cols = X.select_dtypes(include=["object", "category"]).columns
        X[cat_cols] = X[cat_cols].fillna("missing")
        return X.reset_index(drop=True), y.reset_index(drop=True)

    X_train, y_train = _xy(train_df)
    X_val,   y_val   = _xy(val_df)
    X_test,  y_test  = _xy(test_df)

    X_train, y_train = _downsample_negatives(X_train, y_train)

    del df, in_time, train_df, val_df, test_df
    gc.collect()

    return X_train, X_val, X_test, y_train, y_val, y_test


# ---------------------------------------------------------------------------
# Evaluation (DO NOT CHANGE — this is the fixed metric)
# ---------------------------------------------------------------------------

def evaluate(model, X_val: pd.DataFrame, y_val: pd.Series) -> Dict[str, float]:
    """Compute evaluation metrics for a fitted model on the validation split.

    Primary metric: val_lift_1pct
    Secondary:      val_auc_roc, val_lift_5pct, val_lift_10pct, val_auc_pr

    The model must implement predict_proba().
    """
    from shared.metrics import compute_split_metrics

    if not hasattr(model, "predict_proba"):
        raise ValueError("Model must implement predict_proba().")

    y_prob = model.predict_proba(X_val)[:, 1]
    return compute_split_metrics(np.asarray(y_val), y_prob, prefix="val")


def print_summary(
    metrics: Dict[str, float],
    training_time: float,
    total_time: float,
    n_features: int,
    description: str = "",
) -> None:
    """Print a structured summary block for machine parsing.

    The Reviewer parses this block from run.log using grep.
    Key format: '<key>: <value>' with fixed keys matching results_columns.
    """
    print("---")
    print(f"val_lift_1pct:    {metrics.get('val_lift_1pct', 0.0):.6f}")
    print(f"val_auc_roc:      {metrics.get('val_auc_roc', 0.0):.6f}")
    print(f"val_lift_5pct:    {metrics.get('val_lift_5pct', 0.0):.6f}")
    print(f"val_lift_10pct:   {metrics.get('val_lift_10pct', 0.0):.6f}")
    print(f"val_auc_pr:       {metrics.get('val_auc_pr', 0.0):.6f}")
    print(f"training_seconds: {training_time:.1f}")
    print(f"total_seconds:    {total_time:.1f}")
    print(f"n_features:       {n_features}")
    print(f"description:      {description}")
    print("---")


# ---------------------------------------------------------------------------
# Main (data verification — run to prime the parquet cache)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Modeling table: {MODELING_TABLE}")
    print(f"Cache path: {CACHE_PATH}")
    df = load_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Target distribution:\n{df[TARGET_COL].value_counts().sort_index()}")
    print(f"IP6 rate: {df[TARGET_COL].mean():.4%}")

    emb_cols, tab_cols = _identify_feature_columns(df)
    print(f"\nEmbedding features: {len(emb_cols)}")
    print(f"Tabular features:   {len(tab_cols)}")

    X_train, X_val, X_test, y_train, y_val, y_test = get_splits("hybrid", df=df)
    print(f"\nSplits (hybrid):")
    print(f"  Train: {X_train.shape[0]:,} samples ({y_train.mean():.4%} IP6) — after downsampling")
    print(f"  Val:   {X_val.shape[0]:,} samples ({y_val.mean():.4%} IP6)")
    print(f"  Test:  {X_test.shape[0]:,} samples ({y_test.mean():.4%} IP6)")
    print(f"  Features: {X_train.shape[1]}")
    print("\nReady for experiments.")
