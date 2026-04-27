---
schema_version: 1
campaign_id: "smoke-test-creditcard"
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
    description: "Seconds elapsed since first transaction in dataset"
  - name: "V1-V28"
    dtype: "float64"
    description: "PCA-transformed features (original columns inaccessible)"
  - name: "Amount"
    dtype: "float64"
    description: "Transaction amount in currency units"
  - name: "Class"
    dtype: "int64"
    description: "Target: 1=fraud, 0=legitimate. Positive rate ~0.173%"
leakage_audit:
  performed_at: "2026-04-22"
  flagged_columns: []
  notes: "No leakage risk. V1-V28 are PCA-transformed; original features inaccessible. Time is raw elapsed seconds with no future info."
splits:
  train: "60%"
  val: "20%"
  test: "20%"
  strategy: "stratified by Class, seed=42, fixed in train.py"
approved_at: "2026-04-27"
approved_by: "human"
---

## 1. Schema summary

31 columns: Time, V1-V28 (28 PCA features), Amount, Class (target).
All float64 except Class (int64). No missing values in the original dataset.

## 2. Availability table (narrative)

Single CSV file at `data/creditcard.csv`. No external dependencies, no BigQuery access required.
Fully local.

## 3. Leakage audit summary

Leakage audit performed 2026-04-22. Zero flagged columns. V1–V28 are PCA-transformed at source
(original column names and meanings are inaccessible), so no engineered leakage is possible from
them. `Time` is raw elapsed seconds — not a clock time, not correlated with the target beyond
temporal ordering, and not a leakage risk for this campaign.

## 4. Transformations applied pre-agent (if any)

None. train.py loads the raw CSV and performs all transformations inline.

## 5. Known data quality issues

Extreme class imbalance: 492 fraud cases out of 284,807 (0.173%). All models must account for
this via scale_pos_weight, class_weight="balanced", or resampling techniques.
