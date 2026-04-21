---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
count: 8
last_updated: "2026-04-21"
---

# Dead ends — do NOT retry

- SMOTE + scale_pos_weight — double-counts imbalance (mar30)
- QuantileTransformer on tree models — monotonic transform can't change splits (mar30)
- BaggingClassifier wrapping XGBoost — redundant with subsample/colsample (mar30)
- `aucpr` as early stopping metric — too noisy; use logloss (mar30)
- LightGBM `is_unbalance=True` — inverts probabilities (mar30+apr01)
- DART booster — exceeds 90s timeout at 500 trees (apr01)
- `tree_method=approx` — exceeds 90s timeout on 170K rows (apr01)
- sklearn GBM (GradientBoostingClassifier) — exceeds 90s at 100 trees (apr01)
