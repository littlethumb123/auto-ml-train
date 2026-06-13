"""XGBoost training: feature selection, model training, and artifact saving."""

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


def split_data(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple:
    """Stratified train/test split. Returns (X_train, X_test, y_train, y_test)."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state,
    )
    print(f"  Train: {len(X_train):,} ({y_train.mean():.4f} pos rate)", flush=True)
    print(f"  Test:  {len(X_test):,} ({y_test.mean():.4f} pos rate)", flush=True)
    return X_train, X_test, y_train, y_test


def split_data_three_way(
    X: pd.DataFrame,
    y: pd.Series,
    val_size: float = 0.2,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple:
    """Stratified 60/20/20 train/val/test split.

    val_size and test_size are both fractions of the full dataset.
    Returns (X_train, X_val, X_test, y_train, y_val, y_test).
    Test set is carved off first; val is then split from the remaining trainval pool.
    """
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state,
    )
    val_frac = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=val_frac, stratify=y_trainval,
        random_state=random_state,
    )
    pct_tr = len(X_train) / len(X)
    pct_va = len(X_val) / len(X)
    pct_te = len(X_test) / len(X)
    print(f"  Split: {pct_tr:.0%}/{pct_va:.0%}/{pct_te:.0%} (train/val/test)", flush=True)
    print(f"  Train: {len(X_train):,} ({y_train.mean():.4f} pos rate)", flush=True)
    print(f"  Val:   {len(X_val):,} ({y_val.mean():.4f} pos rate)", flush=True)
    print(f"  Test:  {len(X_test):,} ({y_test.mean():.4f} pos rate)", flush=True)
    return X_train, X_val, X_test, y_train, y_val, y_test


def save_split_ids(
    df: pd.DataFrame,
    id_col: str,
    train_idx,
    val_idx,
    test_idx,
    path: Path,
) -> None:
    """Save member IDs per split so all downstream steps use the exact same split."""
    split = {
        "train": df.loc[train_idx, id_col].tolist(),
        "val": df.loc[val_idx, id_col].tolist(),
        "test": df.loc[test_idx, id_col].tolist(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(split, fh)
    print(
        f"  Split IDs → {path.name}: "
        f"train={len(split['train']):,}  val={len(split['val']):,}  test={len(split['test']):,}",
        flush=True,
    )


def load_split_ids(path: Path) -> dict[str, list]:
    """Load member IDs per split. Returns {'train': [...], 'val': [...], 'test': [...]}."""
    with open(path) as fh:
        return json.load(fh)


def smoke_test(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    xgb_params: dict,
    n_samples: int = 2000,
) -> None:
    """Quick sanity check on a small subset."""
    idx = np.random.RandomState(42).choice(len(X_train), min(n_samples, len(X_train)), replace=False)
    X_sub = X_train.iloc[idx]
    y_sub = y_train.iloc[idx]

    model = XGBClassifier(**{**xgb_params, "n_estimators": 50})
    neg = (y_sub == 0).sum()
    pos = (y_sub == 1).sum()
    model.set_params(scale_pos_weight=neg / pos if pos > 0 else 1.0)

    t0 = time.time()
    model.fit(X_sub, y_sub)
    print(f"  Smoke test ({n_samples} samples, 50 trees): {time.time() - t0:.1f}s", flush=True)


def train_full_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    xgb_params: dict,
    sample_weight: np.ndarray | None = None,
) -> XGBClassifier:
    """Train XGBoost on all features. Returns fitted model."""
    model = XGBClassifier(**xgb_params)
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    model.set_params(scale_pos_weight=neg / pos if pos > 0 else 1.0)

    print(f"  Training on {X_train.shape[1]:,} features...", flush=True)
    t0 = time.time()
    model.fit(X_train, y_train, sample_weight=sample_weight)
    print(f"    Done in {time.time() - t0:.0f}s", flush=True)
    return model


def select_top_features(
    model: XGBClassifier,
    feature_names: list[str],
    top_n: int = 500,
) -> tuple[list[str], pd.DataFrame]:
    """Select top-N features by gain importance.

    Returns (selected_feature_names, importance_df).
    """
    importance = pd.DataFrame({
        "feature": feature_names,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    selected = importance.head(top_n)["feature"].tolist()
    print(f"  Selected top {len(selected)} features (max importance: {importance['importance'].iloc[0]:.4f})", flush=True)
    return selected, importance


def retrain_on_selected(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    selected_features: list[str],
    xgb_params: dict,
    sample_weight: np.ndarray | None = None,
) -> tuple[XGBClassifier, np.ndarray]:
    """Retrain on selected features and return predictions.

    Returns (model, test_predictions).
    """
    X_tr = X_train[selected_features]
    X_te = X_test[selected_features]

    model = XGBClassifier(**xgb_params)
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    model.set_params(scale_pos_weight=neg / pos if pos > 0 else 1.0)

    print(f"  Retraining on {len(selected_features)} features...", flush=True)
    t0 = time.time()
    model.fit(X_tr, y_train, sample_weight=sample_weight)
    preds = model.predict_proba(X_te)[:, 1]
    print(f"    Done in {time.time() - t0:.0f}s", flush=True)
    return model, preds


def train_on_selected(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    selected_features: list[str],
    xgb_params: dict,
    sample_weight: np.ndarray | None = None,
) -> "XGBClassifier":
    """Train on selected features only. Returns fitted model (no test eval)."""
    cols = [f for f in selected_features if f in X_train.columns]
    X_tr = X_train[cols]
    model = XGBClassifier(**xgb_params)
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    model.set_params(scale_pos_weight=neg / pos if pos > 0 else 1.0)
    print(f"  Training on {len(cols):,} features ({X_tr.shape[0]:,} rows)...", flush=True)
    t0 = time.time()
    model.fit(X_tr, y_train, sample_weight=sample_weight)
    print(f"    Done in {time.time() - t0:.0f}s", flush=True)
    return model


def save_model(model: XGBClassifier, path: Path) -> None:
    """Save XGBoost model as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))
    print(f"  Model saved to {path}", flush=True)


def save_feature_list(features: list[str], path: Path) -> None:
    """Save selected feature names to text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Strip sanitization prefix for clean names
    clean = [re.sub(r"^col_(?=\d)", "", f) for f in features]
    with open(path, "w") as f:
        f.write("\n".join(clean))
    print(f"  Feature list saved to {path} ({len(clean)} features)", flush=True)


def save_importance(importance_df: pd.DataFrame, path: Path) -> None:
    """Save feature importance ranking as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    importance_df.to_csv(path, index=False)
    print(f"  Importance ranking saved to {path}", flush=True)
