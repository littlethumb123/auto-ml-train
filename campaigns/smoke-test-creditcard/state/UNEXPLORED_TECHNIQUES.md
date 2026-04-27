---
schema_version: 1
campaign_id: "smoke-test-creditcard"
last_updated: "2026-04-27"
---

## Unexplored Technique Classes

- **Imbalance handling variants:** SMOTE, ADASYN, focal loss, class_weight vs scale_pos_weight comparison. Status: Unexplored. Expected Δ: 0.02–0.05 (imbalance is extreme at 0.17%).
- **Feature engineering:** log1p(Amount), Amount×V1, Amount×V2 interaction terms. Status: Unexplored. Expected Δ: 0.01–0.03.
- **XGBoost family:** scale_pos_weight tuning with Optuna, hist tree method. Status: Unexplored. Expected Δ: 0.01–0.02.
- **Threshold optimization:** PR-curve optimal threshold vs fixed 0.5 for F1 improvement. Status: Unexplored. Expected Δ: 0.01 (on macro_f1).
- **Ensemble:** Averaging LGBM + XGBoost predictions. Status: Unexplored. Expected Δ: 0.01–0.02.
- **Time-based features:** Rolling transaction count, time-since-last transaction per card proxy (limited since card ID is unavailable). Status: Unexplored. Expected Δ: 0.005–0.015.
- **Regularization tuning:** min_child_samples, lambda, alpha for LGBM to reduce overfitting on small fraud class. Status: Unexplored. Expected Δ: 0.005–0.01.
