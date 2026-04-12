"""Model training and evaluation for the XGBoost training pipeline.

Uses the low-level xgboost.train() API (DMatrix) to match the notebook
approach and provide full control over hyperparameters.

Note: DMatrix objects are always built from numpy arrays (not DataFrames)
so the saved model contains NO feature names.  This is required for
Vertex AI Batch Prediction, which sends plain numeric arrays without
column-name metadata.
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score, confusion_matrix


# ---------------------------------------------------------------------------
# Default model parameters (mirror of the notebook)
# ---------------------------------------------------------------------------

DEFAULT_XGB_PARAMS = {
    'objective': 'binary:logistic',
    'base_score': 0.5,
    'booster': 'gbtree',
    'colsample_bylevel': 1,
    'colsample_bynode': 1,
    'colsample_bytree': 0.551691605418298,
    'device': 'cpu',           # override with 'cuda' if GPU available
    'eval_metric': 'logloss',
    'gamma': 0,
    'grow_policy': 'lossguide',
    'learning_rate': 0.008410840153403855,
    'max_bin': 256,
    'max_delta_step': 0,
    'max_depth': 4,
    'max_leaves': 0,
    'min_child_weight': 1,
    'multi_strategy': 'one_output_per_tree',
    'n_jobs': -1,
    'num_parallel_tree': 1,
    'random_state': 53,
    'reg_alpha': 0,
    'reg_lambda': 1,
    'sampling_method': 'uniform',
    'scale_pos_weight': 1,
    'subsample': 0.5826667789672917,
    'tree_method': 'hist',
    'verbosity': 1,
}

DEFAULT_NUM_BOOST_ROUND = 3101


# ---------------------------------------------------------------------------
# DMatrix helpers
# ---------------------------------------------------------------------------

def make_dmatrix(X: pd.DataFrame, y: pd.Series = None) -> xgb.DMatrix:
    """Create an xgb.DMatrix from a pandas DataFrame and optional Series.

    The DataFrame is converted to a **float32 numpy array** before being
    passed to DMatrix so that the resulting booster stores **no feature
    names**.  This is mandatory for Vertex AI Batch Prediction, which
    sends plain numeric arrays without column-name metadata.

    Args:
        X: Feature DataFrame (column order must be consistent across
           train / test / val / holdout sets)
        y: Label Series (optional; omit for inference)

    Returns:
        xgb.DMatrix with no feature names
    """
    X_np = X.to_numpy(dtype=np.float32, copy=False)
    if y is not None:
        return xgb.DMatrix(X_np, label=y.to_numpy(copy=False).astype(int))
    return xgb.DMatrix(X_np)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_xgb_model(
    dtrain: xgb.DMatrix,
    dval: xgb.DMatrix,
    params: dict,
    num_boost_round: int = DEFAULT_NUM_BOOST_ROUND,
    verbose_eval: int = 100,
) -> xgb.Booster:
    """Train an XGBoost booster using the low-level xgb.train() API.

    Args:
        dtrain: Training DMatrix
        dval: Validation DMatrix (used for eval only, no early stopping by default)
        params: XGBoost parameter dict
        num_boost_round: Total number of boosting rounds
        verbose_eval: Print eval every N rounds (0 = silent)

    Returns:
        Trained xgb.Booster
    """
    evals = [(dval, 'eval')]
    model = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=num_boost_round,
        evals=evals,
        verbose_eval=verbose_eval if verbose_eval > 0 else False,
    )
    print(f"  ✅ Training complete ({num_boost_round} rounds)")

    # Verify model has NO feature names (required for Vertex AI Batch Prediction)
    if model.feature_names:
        print(f"  ⚠  WARNING: Model has feature names – batch prediction may fail!")
    else:
        print(f"  ✓  Model has no feature names – compatible with Vertex AI Batch Prediction")

    return model


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _percentile_metrics(y_true: pd.Series, y_pred: np.ndarray, percentile: float) -> dict:
    """Calculate lift, PPV and sensitivity at a given top-N percentile.

    Args:
        y_true: True binary labels (reset index)
        y_pred: Predicted probabilities
        percentile: Fraction of population to consider (e.g. 0.01 = top 1 %)

    Returns:
        dict with keys: lift, ppv, sensitivity
    """
    idx = np.argsort(y_pred)[::-1]
    cutoff = max(1, int(percentile * len(y_true)))
    top_idx = idx[:cutoff]

    preds_binary = np.zeros(len(y_true), dtype=int)
    preds_binary[top_idx] = 1

    tn, fp, fn, tp = confusion_matrix(y_true, preds_binary, labels=[0, 1]).ravel()
    ppv         = 100.0 * tp / (tp + fp) if (tp + fp) > 0 else 0.0
    sensitivity = 100.0 * tp / (tp + fn) if (tp + fn) > 0 else 0.0

    pos_rate_top  = y_true.iloc[top_idx].mean()
    pos_rate_all  = y_true.mean()
    lift = pos_rate_top / pos_rate_all if pos_rate_all > 0 else 0.0

    return {'lift': lift, 'ppv': ppv, 'sensitivity': sensitivity}


def calculate_metrics(
    model: xgb.Booster,
    dtest: xgb.DMatrix,
    y_test: pd.Series,
    percentiles: list = None,
) -> tuple:
    """Compute ROC-AUC and percentile-based lift / PPV / sensitivity.

    Args:
        model: Trained xgb.Booster
        dtest: Test DMatrix (features only)
        y_test: True labels for the test set
        percentiles: List of percentile fractions (default: [0.01, 0.10])

    Returns:
        tuple: (roc_auc, metrics_dict)
            metrics_dict keys: lift_1_perc, ppv_1_perc, sensitivity_1_perc,
                               lift_10_perc, ppv_10_perc, sensitivity_10_perc, …
    """
    if percentiles is None:
        percentiles = [0.01, 0.10]

    y_pred = model.predict(dtest)
    y_true = y_test.reset_index(drop=True)

    roc_auc = roc_auc_score(y_true, y_pred)
    print(f"  ROC-AUC: {roc_auc:.4f}")

    metrics = {}
    for p in percentiles:
        pct_label = f"{int(round(p * 100))}_perc"
        result = _percentile_metrics(y_true, y_pred, p)
        metrics[f'lift_{pct_label}']        = result['lift']
        metrics[f'ppv_{pct_label}']         = result['ppv']
        metrics[f'sensitivity_{pct_label}'] = result['sensitivity']
        print(
            f"  Top {int(p*100)}%  →  Lift: {result['lift']:.2f} | "
            f"PPV: {result['ppv']:.1f}% | Sensitivity: {result['sensitivity']:.1f}%"
        )

    return roc_auc, metrics


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def predict_holdout(model: xgb.Booster, dholdout: xgb.DMatrix) -> np.ndarray:
    """Generate probability predictions for the holdout set.

    Args:
        model: Trained xgb.Booster
        dholdout: Holdout DMatrix (features only)

    Returns:
        numpy array of predicted probabilities (positive class)
    """
    preds = model.predict(dholdout)
    print(f"  Holdout predictions generated: {len(preds):,} rows")
    return preds

