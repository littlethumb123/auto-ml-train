---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
data_sources:
  - path: "data/creditcard.csv"
    n_rows: 284807
    n_cols: 31
    primary_key: "implicit row index"
temporal:
  is_temporal: false
  order_column: null
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
  - name: "V2"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V3"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V4"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V5"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V6"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V7"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V8"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V9"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V10"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V11"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V12"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V13"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V14"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V15"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V16"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V17"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V18"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V19"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V20"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V21"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V22"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V23"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V24"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V25"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V26"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V27"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "V28"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "Class"
    dtype: "int64"
    role: "target"
    available_at_prediction: false
leakage_audit:
  performed_at: null
  flagged_columns: []
  notes: "Run tools/leakage_audit and fill performed_at before G2 sign-off."
splits:
  train: "stratified 60% of data (per prepare.py)"
  val: "stratified 20% of data (per prepare.py)"
  test: "stratified 20% of data (per prepare.py)"
  random_seed: 42
approved_at: null
approved_by: null
---

## 1. Schema summary

284,807 rows × 31 columns. Target `Class` is binary (0=legit, 1=fraud, ~0.17% positive). V1–V28 are PCA-transformed at source; Amount and Time are raw.

## 2. Availability table (narrative)

All features are synchronous with the transaction record — available at prediction time by construction. Time is elapsed seconds since the first observation in the dataset, not clock time.

## 3. Leakage audit summary

Run `python3 runner/tools/leakage_audit.py --data-contract-path runner/contracts/DATA_CONTRACT.md --data-path data/creditcard.csv --target-col Class` before G2 sign-off. No historical audit flagged features (legacy campaigns relied on the fixed prepare.py split).

## 4. Transformations applied pre-agent (if any)

V1–V28 were produced by PCA at data generation time; original columns are not accessible.

## 5. Known data quality issues

None known. Dataset loads cleanly in prepare.py.
