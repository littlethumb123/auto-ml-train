"""Evaluation: AUC, lift, calibration, threshold metrics, SHAP."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)


def compute_auc(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute AUC-ROC and AUC-PR."""
    return {
        "auc_roc": roc_auc_score(y_true, y_pred),
        "auc_pr": average_precision_score(y_true, y_pred),
        "brier": brier_score_loss(y_true, y_pred),
    }


def compute_lift_at_k(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    k_pcts: list[float] | None = None,
) -> dict[str, float]:
    """Compute lift at given percentile cutoffs (e.g., top 1%, 5%, 10%)."""
    k_pcts = k_pcts or [0.01, 0.05, 0.10]
    base_rate = y_true.mean()
    order = np.argsort(-y_pred)

    lifts = {}
    for k in k_pcts:
        n = max(1, int(len(y_true) * k))
        top_idx = order[:n]
        top_rate = y_true.iloc[top_idx].mean() if hasattr(y_true, "iloc") else y_true[top_idx].mean()
        lifts[f"lift_top_{int(k*100)}pct"] = top_rate / base_rate if base_rate > 0 else 0.0
    return lifts


def compute_threshold_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    thresholds: np.ndarray | None = None,
) -> pd.DataFrame:
    """Compute sensitivity, specificity, PPV, NPV, accuracy, lift across thresholds."""
    if thresholds is None:
        thresholds = np.arange(0.0, 1.01, 0.01)

    rows = []
    for t in thresholds:
        pred_pos = y_pred >= t
        tp = ((pred_pos) & (y_true == 1)).sum()
        fp = ((pred_pos) & (y_true == 0)).sum()
        tn = ((~pred_pos) & (y_true == 0)).sum()
        fn = ((~pred_pos) & (y_true == 1)).sum()

        sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
        acc = (tp + tn) / len(y_true) if len(y_true) > 0 else 0.0
        base_rate = y_true.mean() if hasattr(y_true, "mean") else np.mean(y_true)
        lift = ppv / base_rate if base_rate > 0 else 0.0

        rows.append({
            "threshold": t, "sensitivity": sens, "specificity": spec,
            "ppv": ppv, "npv": npv, "accuracy": acc, "lift": lift,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        })
    return pd.DataFrame(rows)


def compute_calibration(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Compute calibration by decile: predicted risk vs observed rate."""
    df = pd.DataFrame({"y_true": y_true, "y_pred": y_pred})
    df["decile"] = pd.qcut(df["y_pred"], n_bins, labels=False, duplicates="drop")
    cal = df.groupby("decile").agg(
        predicted_risk=("y_pred", "mean"),
        observed_rate=("y_true", "mean"),
        count=("y_true", "count"),
    ).reset_index()
    return cal


def plot_roc_pr(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    save_path=None,
) -> None:
    """Plot ROC and PR curves side by side."""
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    fpr, tpr, _ = roc_curve(y_true, y_pred)
    auc_roc = roc_auc_score(y_true, y_pred)
    ax1.plot(fpr, tpr, label=f"AUC = {auc_roc:.3f}")
    ax1.plot([0, 1], [0, 1], "k--", alpha=0.3)
    ax1.set_xlabel("FPR")
    ax1.set_ylabel("TPR")
    ax1.set_title("ROC Curve")
    ax1.legend()

    prec, rec, _ = precision_recall_curve(y_true, y_pred)
    auc_pr = average_precision_score(y_true, y_pred)
    ax2.plot(rec, prec, label=f"AP = {auc_pr:.3f}")
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title("Precision-Recall Curve")
    ax2.legend()

    plt.tight_layout()
    if save_path:
        from pathlib import Path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Saved to {save_path}", flush=True)
    plt.close()


def run_shap_analysis(
    model,
    X: pd.DataFrame,
    top_n: int = 20,
    save_dir=None,
) -> None:
    """Run SHAP analysis on top features using XGBoost native pred_contribs."""
    from xgboost import DMatrix

    top_feature_idx = pd.Series(
        model.feature_importances_, index=X.columns
    ).nlargest(top_n).index

    # pred_contribs requires full feature matrix matching training columns
    contribs = model.get_booster().predict(DMatrix(X), pred_contribs=True)

    import matplotlib.pyplot as plt

    all_feature_names = list(X.columns)
    feature_importance = np.abs(contribs[:, :-1]).mean(axis=0)

    # Select top-N by mean |SHAP|
    top_shap_idx = np.argsort(feature_importance)[::-1][:top_n]
    top_names = [all_feature_names[i] for i in top_shap_idx]
    top_vals = feature_importance[top_shap_idx]
    sorted_order = np.argsort(top_vals)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(range(top_n), top_vals[sorted_order])
    ax.set_yticks(range(top_n))
    ax.set_yticklabels([top_names[i] for i in sorted_order])
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(f"Top {top_n} Feature Importance (SHAP)")
    plt.tight_layout()

    if save_dir:
        from pathlib import Path
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        plt.savefig(Path(save_dir) / "shap_importance.png", dpi=150, bbox_inches="tight")
        print(f"  SHAP plot saved to {save_dir}/shap_importance.png", flush=True)
    plt.close()


def print_summary(metrics: dict, lifts: dict, label: str = "") -> None:
    """Print a formatted summary of model metrics."""
    prefix = f"[{label}] " if label else ""
    print(f"\n{prefix}Model Performance:", flush=True)
    print(f"  AUC-ROC: {metrics['auc_roc']:.4f}", flush=True)
    print(f"  AUC-PR:  {metrics['auc_pr']:.4f}", flush=True)
    print(f"  Brier:   {metrics['brier']:.4f}", flush=True)
    for k, v in lifts.items():
        print(f"  {k}: {v:.2f}x", flush=True)
