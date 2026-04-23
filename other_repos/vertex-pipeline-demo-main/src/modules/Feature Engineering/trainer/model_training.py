"""Model training, undersampling experiments, and RFECV for the Feature Engineering pipeline.

This module does NOT produce the final production model — it uses XGBoost
as a proxy estimator to rank and select features. The selected feature list
is the primary artifact consumed by the Vertex Model Trainer module.

Public API
----------
``train_baseline_model(X_train, y_train, model_config)``
    Trains a baseline ``XGBClassifier`` with the ``initial_model`` config
    from ``config.yaml``. Used to establish a pre-selection performance
    benchmark.

``calculate_metrics(model, X_test, y_test, percentiles)``
    Computes ROC-AUC and, for each percentile in *percentiles*, calculates
    Lift, PPV (Precision), and Sensitivity (Recall) at the top-N cut.
    Returns ``(roc_auc, metrics_dict)``.

``run_undersampling_experiments(X_train, y_train, X_test, y_test, config)``
    Trains one model per (ratio, seed) combination using
    ``imblearn.RandomUnderSampler``, plus a no-resampling baseline and a
    class-weight baseline. Returns a list of ``(ratio, seed, lift)`` tuples
    for comparison.

``save_undersampling_results(results, config)``
    Saves the experiment results to a CSV file and renders a seaborn bar
    chart of 1% Lift across ratios and seeds.

``run_rfecv(X_train, y_train, config)``
    Fits ``sklearn.RFECV`` using the ``rfecv_model`` XGBoost config with
    stratified K-Fold CV. Prints the optimal feature count and returns the
    fitted ``RFECV`` object.

``plot_rfecv_results(rfecv)``
    Plots mean CV ROC-AUC vs. number of features selected and prints the
    underlying DataFrame.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import gc
from xgboost import XGBClassifier
from imblearn.under_sampling import RandomUnderSampler
from sklearn.feature_selection import RFECV
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import confusion_matrix, roc_auc_score


def calculate_metrics(model, X_test, y_test, percentiles):
    """Calculate comprehensive metrics for a model.
    
    Args:
        model: Trained model with predict_proba method
        X_test: Test features
        y_test: Test labels
        percentiles: List of percentiles to evaluate (e.g., [0.01, 0.10, 0.35])
        
    Returns:
        tuple: (roc_auc, metrics_dict)
    """
    y_pred_test = model.predict_proba(X_test)[:, 1]
    y_test_reset = y_test.reset_index(drop=True)
    roc_auc_test = roc_auc_score(y_test, y_pred_test)
    idx = np.argsort(y_pred_test)[::-1]
    
    def calculate_percentile_metrics(y_test_reset, idx, percentile):
        cutoff = int(percentile * len(y_test_reset))
        top_indices = idx[:cutoff]
        predictions_binary = np.zeros(len(y_test_reset), dtype=int)
        predictions_binary[top_indices] = 1
        tn, fp, fn, tp = confusion_matrix(y_test_reset, predictions_binary, labels=[0, 1]).ravel()
        ppv = 100 * (tp / (tp + fp)) if (tp + fp) > 0 else 0
        sensitivity = 100 * (tp / (tp + fn)) if (tp + fn) > 0 else 0
        actual_positives_top_perc = y_test_reset[top_indices].sum()
        expected_positives = y_test_reset.sum() * percentile
        lift = actual_positives_top_perc / expected_positives if expected_positives > 0 else 0
        return lift, ppv, sensitivity
    
    results = {}
    for p in percentiles:
        lift, ppv, sens = calculate_percentile_metrics(y_test_reset, idx, p)
        results[f'lift_{int(p*100)}_perc'] = lift
        results[f'ppv_{int(p*100)}_perc'] = ppv
        results[f'sensitivity_{int(p*100)}_perc'] = sens
    
    return roc_auc_test, results


def train_baseline_model(X_train, y_train, model_config):
    """Train baseline XGBoost model.
    
    Args:
        X_train: Training features
        y_train: Training labels
        model_config: Model configuration dictionary
        
    Returns:
        Trained XGBoost model
    """
    model = XGBClassifier(**model_config)
    model.fit(X_train, y_train, verbose=0)
    return model


def run_undersampling_experiments(X_train, y_train, X_test, y_test, config):
    """Run undersampling experiments with different ratios.
    
    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        config: Configuration dictionary
        
    Returns:
        list: List of tuples (ratio, seed, lift)
    """
    undersampling_config = config['undersampling']
    ratios = undersampling_config['ratios']
    seeds = undersampling_config['seeds']
    test_percentile = undersampling_config['test_percentile']
    model_config = config['model']['undersampling_model']
    
    results = []
    
    for r in ratios:
        for s in seeds:
            undersample = RandomUnderSampler(sampling_strategy=r, random_state=s)
            X_train_u, y_train_u = undersample.fit_resample(X_train, y_train)
            xgb_model = XGBClassifier(**model_config)
            xgb_model.fit(X_train_u, y_train_u, verbose=False)
            print("done fit")
            
            y_pred_test = xgb_model.predict_proba(X_test)[:, 1]
            idx = np.argsort(y_pred_test)[::-1]
            top_1_percent = int(test_percentile * len(y_test))
            predicted_top_1_percent = y_test.iloc[idx][:top_1_percent]
            actual_positives_top_1_percent = predicted_top_1_percent.sum()
            expected_positives = y_test.sum() * test_percentile
            lift = actual_positives_top_1_percent / expected_positives
            results.append((r, s, lift))
            print("one iteration", r, s, lift)
    
    # No undersampling test
    xgb_model = XGBClassifier(random_state=53, n_jobs=15, verbosity=0, enable_categorical=True)
    xgb_model.fit(X_train, y_train, verbose=False)
    print("done fit")
    
    y_pred_test = xgb_model.predict_proba(X_test)[:, 1]
    y_test_reset = y_test.reset_index(drop=True)
    idx = np.argsort(y_pred_test)[::-1]
    top_1_percent = int(test_percentile * len(y_test_reset))
    predicted_top_1_percent = y_test_reset.iloc[idx][:top_1_percent]
    actual_positives_top_1_percent = predicted_top_1_percent.sum()
    expected_positives = y_test_reset.sum() * test_percentile
    lift = actual_positives_top_1_percent / expected_positives
    results.append((0, 0, lift))
    print("one iteration, no sample")
    
    # Class weights test
    weights = np.where(y_train == 0, 1, len(y_train) / (2 * np.sum(y_train == 1)))
    xgb_model = XGBClassifier(random_state=53, n_jobs=15, verbosity=0, enable_categorical=True)
    xgb_model.fit(X_train, y_train, sample_weight=weights, verbose=False)
    print("done fit")
    
    y_pred_test = xgb_model.predict_proba(X_test)[:, 1]
    y_test_reset = y_test.reset_index(drop=True)
    idx = np.argsort(y_pred_test)[::-1]
    top_1_percent = int(test_percentile * len(y_test_reset))
    predicted_top_1_percent = y_test_reset.iloc[idx][:top_1_percent]
    actual_positives_top_1_percent = predicted_top_1_percent.sum()
    expected_positives = y_test_reset.sum() * test_percentile
    lift = actual_positives_top_1_percent / expected_positives
    results.append((999, 999, lift))
    print("one iteration, class weights")
    
    return results


def save_undersampling_results(results, config):
    """Save and visualize undersampling results.
    
    Args:
        results: List of tuples (ratio, seed, lift)
        config: Configuration dictionary
    """
    results_df = pd.DataFrame(results, columns=['Ratio', 'Seed', '1% Lift'])
    sns.barplot(data=results_df, x='Ratio', y='1% Lift')
    plt.title(config['output']['plot_title'])
    plt.show()
    results_df.to_csv(config['output']['results_file'], index=False)


def run_rfecv(X_train, y_train, config):
    """Run Recursive Feature Elimination with Cross-Validation.
    
    Args:
        X_train: Training features
        y_train: Training labels
        config: Configuration dictionary
        
    Returns:
        RFECV: Fitted RFECV object
    """
    rfecv_config = config['rfecv']
    model_config = config['model']['rfecv_model']
    
    xgb_model_rfe = XGBClassifier(**model_config)
    rfecv = RFECV(
        estimator=xgb_model_rfe,
        step=rfecv_config['step'],
        cv=StratifiedKFold(rfecv_config['cv_folds']),
        scoring=rfecv_config['scoring'],
        min_features_to_select=rfecv_config['min_features_to_select'],
        n_jobs=rfecv_config['n_jobs']
    )
    
    rfecv.fit(X_train, y_train)
    print(f"Optimal number of features: {rfecv.n_features_}")
    
    gc.collect()
    return rfecv


def plot_rfecv_results(rfecv):
    """Plot RFECV results.
    
    Args:
        rfecv: Fitted RFECV object
    """
    n_features = list(range(1, len(rfecv.cv_results_['mean_test_score']) + 1))
    mean_test_scores = rfecv.cv_results_['mean_test_score']
    cv_results = pd.DataFrame({
        'n_features': n_features,
        'mean_test_score': mean_test_scores
    })
    
    plt.figure()
    plt.xlabel("Number of features selected")
    plt.ylabel("Mean test accuracy")
    plt.plot(cv_results["n_features"], cv_results["mean_test_score"])
    plt.title("Recursive Feature Elimination \nwith correlated features")
    plt.show()
    print(cv_results[["n_features", "mean_test_score"]])



