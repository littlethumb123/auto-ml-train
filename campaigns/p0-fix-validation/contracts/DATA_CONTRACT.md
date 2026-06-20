---
schema_version: 1
campaign_id: "p0-fix-validation"
data_sources:
  - path: "data/creditcard.csv"
    n_rows: 284807
    n_cols: 31
    primary_key: "row_index"
temporal:
  is_temporal: false
  order_column: "Time"
  prediction_time_column: null
columns:
  - name: "Time"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "Amount"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V1"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "Class"
    dtype: "int64"
    role: "target"
    available_at_prediction: false
leakage_audit:
  performed_at: "2026-06-20"
  flagged_columns: []
  notes: "PCA features V1-V28 anonymize originals; Time is raw seconds."
splits:
  train: "60%"
  val: "20%"
  test: "20%"
  random_seed: 42
  strategy: "stratified by Class, seed=42, fixed in train.py"
approved_at: "2026-06-20"
approved_by: "human"
---

## 1. Schema summary

31 columns: Time, V1-V28 (28 PCA features), Amount, Class (target).

## 2. Availability table (narrative)

Single CSV at `data/creditcard.csv`. Local only.

## 3. Leakage audit summary

No leakage: V1-V28 PCA-transformed; Time is raw elapsed seconds.

## 4. Transformations applied pre-agent (if any)

None — train.py loads raw CSV inline.

## 5. Known data quality issues

Extreme imbalance (492/284807 ≈ 0.173% fraud).
