from pandas import MultiIndex, Int16Dtype
import xgboost as xgb
import pandas as pd
import numpy as np
import time
from google.cloud import bigquery
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, cross_validate, GridSearchCV, KFold, StratifiedKFold
from sklearn.metrics import f1_score, make_scorer, roc_auc_score
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from imblearn.pipeline import Pipeline
import matplotlib.pyplot as plt
from sklearn.feature_selection import RFECV
import random
#import torch
import os
import re

import os
# Set environment variables explicitly
os.environ['GOOGLE_CLOUD_PROJECT'] = 'anbc-dev-hcm-cm-de'
os.environ['GCLOUD_PROJECT'] = 'anbc-dev-hcm-cm-de'


def is_date_column(series, sample_size=1000):
    """
    Enhanced date detection for pandas Series.
    
    Args:
        series: pandas Series to check
        sample_size: number of values to sample for analysis
    
    Returns:
        bool: True if the series appears to contain dates
    """
    # Sample the data for faster processing
    sample_data = series.dropna().head(sample_size)
    
    if len(sample_data) == 0:
        return False
    
    # Method 1: Check pandas datetime dtype
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    
    # Method 1.5: Check for BigQuery/Google Cloud date types
    dtype_str = str(series.dtype)
    if 'DateDtype' in dtype_str or 'db_dtypes' in dtype_str:
        return True
    
    # Method 2: Check if column name suggests it's a date
    date_keywords = ['date', 'time', 'dt', 'timestamp', 'created', 'updated', 'dob', 'birth']
    col_name_lower = series.name.lower()
    if any(keyword in col_name_lower for keyword in date_keywords):
        return True
    
    # Method 3: Try to parse as datetime
    try:
        # Check if values look like dates (common formats)
        sample_str = sample_data.astype(str).iloc[0]
        
        # Common date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
            r'\d{8}',              # YYYYMMDD
        ]
        
        import re
        if any(re.match(pattern, sample_str) for pattern in date_patterns):
            # Try to convert a sample to datetime
            pd.to_datetime(sample_data.head(5), errors='raise')
            return True
            
    except (ValueError, TypeError, pd.errors.ParserError):
        pass
    
    # Method 4: Check if numeric values could be timestamps
    if pd.api.types.is_numeric_dtype(series):
        sample_values = sample_data.head(10)
        # Check if values look like Unix timestamps or Excel dates
        if (sample_values > 1000000000).all() and (sample_values < 2000000000).all():
            return True
        # Check if values look like Excel date serial numbers
        if (sample_values > 40000).all() and (sample_values < 50000).all():
            return True
    
    return False

def process_sql_file(sql_content, constants):
    # Find all variables in the SQL file
    variables_in_sql = re.findall(r'\{([^}]+)\}', sql_content)
    
    # Create a clean substitution dictionary from constants
    substitution_dict = {}
    
    for key, value in constants.items():
        # Skip nested dictionaries and non-string values that aren't useful for SQL
        if isinstance(value, dict):
            continue  # Skip LABELS and other nested objects
        elif isinstance(value, bool):
            substitution_dict[key] = str(value).upper()  # Convert True/False to TRUE/FALSE
        else:
            substitution_dict[key] = str(value)  # Convert everything to string
    
    # Add additional mappings for common SQL variable patterns
    additional_mappings = {
        'COST_CENTER': constants.get('COSTCENTER', ''),  # Map COSTCENTER to COST_CENTER
    }
    
    # Merge additional mappings
    substitution_dict.update(additional_mappings)
    
    # Check which variables can be substituted
    missing_variables = []
    available_substitutions = {}
    
    for var_name in variables_in_sql:
        if var_name in substitution_dict:
            available_substitutions[var_name] = substitution_dict[var_name]
        else:
            missing_variables.append(var_name)
    
    # Warn about missing variables but don't fail
    if missing_variables:
        print(f"Warning: Variables not found in constants: {missing_variables}")
        print(f"Available substitutions: {list(substitution_dict.keys())}")
        print(f"Variables in SQL: {variables_in_sql}")
    
    # Substitute variables using **kwargs
    try:
        sql_query = sql_content.format(**available_substitutions)
    except KeyError as e:
        print(f"Available substitutions: {list(available_substitutions.keys())}")
        raise
    
    return sql_query

def auto_classify_features(df, unique_threshold_binary=2, unique_threshold_categorical=20, 
                          exclude_cols=['asdb_member_key', 'index_date', 'index_dt'], 
                          sample_size=100000, manual_overrides=None, verbose=False):
    """
    Automatically classify dataframe columns into:
    0 := categorical (discrete values, typically strings or low cardinality)
    1 := continuous (numeric with many unique values)
    2 := binary (exactly 2 unique values or boolean-like)
    3 := datetime (date/time columns)
    
    Args:
        df: pandas DataFrame to analyze
        unique_threshold_binary: max unique values to be considered binary (default: 2)
        unique_threshold_categorical: max unique values to be considered categorical (default: 20)
        exclude_cols: list of columns to exclude from classification
        sample_size: number of rows to sample for faster processing on large datasets
        manual_overrides: dict of manual overrides {column_name: type}
        verbose: print detailed information
    
    Returns:
        dict: mapping of feature_name -> type (0, 1, 2, or 3)
    """
    
    feature_types = {}
    
    # Sample if dataframe is large
    if len(df) > sample_size:
        df_sample = df.sample(n=sample_size, random_state=42)
    else:
        df_sample = df
    
    for col in df.columns:
        # Skip excluded columns
        if col in exclude_cols:
            feature_types[col] = 1  # or you can skip entirely
            continue
        
        # Apply manual overrides first
        if manual_overrides and col in manual_overrides:
            feature_types[col] = manual_overrides[col]
            if verbose:
                print(f"Manual override: {col} -> {manual_overrides[col]}")
            continue

        # Check for emb or _amt in column name - force continuous
        if 'emb' in col.lower() or '_amt' in col.lower():
            feature_types[col] = 1
            if verbose:
                print(f"Embedding/amount detected: {col} -> 1 (continuous)")
            continue        
        # Get non-null values for analysis
        non_null_values = df_sample[col].dropna()
        
        if len(non_null_values) == 0:
            feature_types[col] = 1  # Default for empty columns
            continue
        
        n_unique = non_null_values.nunique()
        dtype = df[col].dtype
        
        # Step 1: Check for DATETIME (3) - ENHANCED DETECTION
        if is_date_column(df[col]):
            feature_types[col] = 3
            if verbose:
                print(f"Date detected: {col} -> 3 (datetime)")
            continue
        
        # Step 2: Check for BINARY (2)
        if n_unique <= unique_threshold_binary:
            unique_vals = set(non_null_values.unique())
            if (unique_vals <= {0, 1} or 
                unique_vals <= {0.0, 1.0} or 
                unique_vals <= {True, False} or
                unique_vals <= {'Yes', 'No'} or
                unique_vals <= {'Y', 'N'} or
                unique_vals <= {1, 2}):
                feature_types[col] = 2
                if verbose:
                    print(f"Binary detected: {col} -> 2 (binary)")
                continue
        
        # Step 3: Check for CATEGORICAL (0)
        if dtype == 'object' or dtype.name == 'category':
            feature_types[col] = 0
            if verbose:
                print(f"Categorical detected: {col} -> 0 (categorical)")
        elif n_unique <= unique_threshold_categorical:
            # Low cardinality numeric could be categorical
            feature_types[col] = 0
            if verbose:
                print(f"Low cardinality categorical: {col} -> 0 (categorical, {n_unique} unique values)")
        else:
            # Step 4: CONTINUOUS (1)
            feature_types[col] = 1
            if verbose:
                print(f"Continuous detected: {col} -> 1 (continuous)")
    
    return feature_types

user_constants = {
    # SQL Variables for BigQuery queries
    "GCP_PROJECT": "anbc-hcb-dev",
    "GCP_DB": "cm_medicaid_hcb_dev", 
    "PREFIX": "a974930_sahil_test",
    "DEFAULT_EXP": "INTERVAL 2 DAY",
    "ST": "{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st",
    "SDOH_YEAR":'2023'
}

sql = """
SELECT
  -- a.mom_key AS asdb_member_key,
  a.index_date,
  a.gest_age,
  a.pre_term as pre_term_max,
  p.* EXCEPT(
    asdb_member_key,
    index_date,
    baby_dob,
    nicu_lvl,
    pre_term_labor_clm,
    pre_term_delivery_clm,
    nicu_flag,
    pre_term_max,
    post_mnths,
    agenbr,
    ethnicity_desc,
    ethnicity_code,
    primarylanguage_desc,
    first_prv_dt,
    last_prv_dt,
    index_dt
  )
FROM `anbc-hcb-dev.cm_medicaid_hcb_dev.a534354_mlops_test_longitudinal` AS a
JOIN `anbc-hcb-dev.cm_medicaid_hcb_dev.a534354_mlops_test_all_predictors` AS p
  ON p.asdb_member_key = a.mom_key
 AND p.index_date = a.index_date
WHERE a.mom_key IN (
  SELECT mom_key
  FROM `anbc-hcb-dev.cm_medicaid_hcb_dev.a534354_mlops_test_training_ids`
)
AND a.pre_term_at_index = 0;
"""

# Get features
sql2 = """
SELECT
  -- a.mom_key AS asdb_member_key,
  a.index_date,
  a.gest_age,
  a.pre_term as pre_term_max,
  p.* EXCEPT(
    asdb_member_key,
    index_date,
    baby_dob,
    nicu_lvl,
    pre_term_labor_clm,
    pre_term_delivery_clm,
    nicu_flag,
    pre_term_max,
    post_mnths,
    agenbr,
    ethnicity_desc,
    ethnicity_code,
    primarylanguage_desc,
    first_prv_dt,
    last_prv_dt,
    index_dt
  )
FROM `anbc-hcb-dev.cm_medicaid_hcb_dev.a534354_mlops_test_longitudinal` AS a
JOIN `anbc-hcb-dev.cm_medicaid_hcb_dev.a534354_mlops_test_all_predictors` AS p
  ON p.asdb_member_key = a.mom_key
 AND p.index_date = a.index_date
WHERE a.mom_key IN (
  SELECT mom_key
  FROM `anbc-hcb-dev.cm_medicaid_hcb_dev.a534354_mlops_test_testing_ids`
)
AND a.pre_term_at_index = 0;
"""

os.environ['KMP_DUPLICATE_LIB_OK']='True'
random.seed(35)
np.random.seed(35)
constants = user_constants
client = bigquery.Client(project="anbc-dev-hcm-cm-de")
import pandas_gbq
import tqdm


print("Successfully read data from BigQuery...")
print(sql)
pd.set_option('mode.chained_assignment', None)
pd.set_option('compute.use_bottleneck', True)
pd.set_option('compute.use_numexpr', True)
# The SQL query is the FIRST POSITIONAL argument, not query=
df = pandas_gbq.read_gbq(
    process_sql_file(sql, constants),  # First argument - the SQL query
    project_id="anbc-dev-hcm-cm-de",
    use_bqstorage_api=True,  # CRITICAL for speed
    progress_bar_type='tqdm',
    configuration={
        'query': {
            'useQueryCache': False,
            'useLegacySql': False,
        }
    },
    dialect='standard',
    auth_local_webserver=False
)
print("Training data shape: ", df.shape)
print(sql2)
df2 = pandas_gbq.read_gbq(
    process_sql_file(sql2, constants),  # First argument - the SQL query
    project_id="anbc-dev-hcm-cm-de",
    use_bqstorage_api=True,  # CRITICAL for speed
    progress_bar_type='tqdm',
    configuration={
        'query': {
            'useQueryCache': False,
            'useLegacySql': False,
        }
    },
    dialect='standard',
    auth_local_webserver=False
)
print("Test data shape: ", df2.shape)

from pandas.api.types import is_integer_dtype as is_integer
from pandas.api.types import is_float_dtype as is_float
import re

emb_pattern = r'emb[0-255]+'
emb_col = [col for col in df.columns if re.match(emb_pattern ,col)]
df[emb_col] = df[emb_col].fillna(0)
for c in df.columns: 
    dt = df[c].dtype
    if is_integer(dt) or is_float(dt):
        df[c]=df[c].fillna(0) 
        # print("Floatint:", dt)
    else:
        try:
            df[c]= df[c].fillna('')
        except:
            print("ERROR - DATE VARIABLE FOUND", dt)
            
emb_pattern = r'emb[0-255]+'
emb_col = [col for col in df2.columns if re.match(emb_pattern ,col)]
df2[emb_col] = df2[emb_col].fillna(0)
for c in df2.columns: 
    dt = df2[c].dtype
    if is_integer(dt) or is_float(dt):
        df2[c]=df2[c].fillna(0) 
        # print("Floatint:", dt)
    else:
        try:
            df2[c]= df2[c].fillna('')
        except:
            print("ERROR - DATE VARIABLE FOUND", dt)

from pandas.api.types import is_integer_dtype as is_integer
from pandas.api.types import is_float_dtype as is_float

numeric_train_cols = [col for col in df.columns if is_integer(df[col].dtype) or is_float(df[col].dtype)]
# Exclude target and ID columns from variance check
exclude_for_variance = ['pre_term_max']  # Add your target and ID columns
numeric_to_check = [col for col in numeric_train_cols if col not in exclude_for_variance]

print(f"Checking variance on {len(numeric_to_check)} numeric features...")

# Calculate variance on training data
variance = df[numeric_to_check].var()
low_variance_cols = variance[variance < 0.001].index.tolist()

if low_variance_cols:
    print(f"Dropping {len(low_variance_cols)} columns with low variance: {list(low_variance_cols)}")
    df = df.drop(columns=low_variance_cols)
    df2 = df2.drop(columns=[col for col in low_variance_cols if col in df2.columns])
else:
    print("No low variance columns found")

print(f"Training data shape after variance filter: {df.shape}")
print(f"Test data shape after variance filter: {df2.shape}")

manual_fixes = {
    'gender': 0,  # Force categorical
    'PUD': 2,     # Force categorical (as in your original)
    'some_field': 2  # Force binary
}

nem_to_type = auto_classify_features(
    df,
    unique_threshold_binary=2,
    unique_threshold_categorical=5,
    exclude_cols=[],
    sample_size=100000,
    manual_overrides=manual_fixes,
    verbose=True
)

index_to_feature = dict(enumerate(df2.columns))
feature_to_index = {value: key for key, value in index_to_feature.items()}
categorical_features = [feature for feature in nem_to_type if nem_to_type[feature] == 0]
categorical_indices = [feature_to_index[feature] for feature in categorical_features if feature in feature_to_index]
len(categorical_features)

def sanitize_column_names(df):
    """Sanitize column names for BigQuery compatibility"""
    sanitized_columns = []
    for col in df.columns:
        # Replace periods with underscores
        sanitized_col = col.replace('.', '_')
        # Replace other problematic characters
        sanitized_col = re.sub(r'[^a-zA-Z0-9_]', '_', sanitized_col)
        # Ensure it starts with letter or underscore
        if sanitized_col[0].isdigit():
            sanitized_col = 'col_' + sanitized_col
        sanitized_columns.append(sanitized_col)
    
    df.columns = sanitized_columns
    return df
# ONE HOT ENCODING - FIXED VERSION
from tqdm import tqdm
from sklearn.preprocessing import OneHotEncoder
import pandas as pd

min_occurrence = 2000

# Step 1: Fit encoders on TRAINING data only
encoders = {}
categories_to_keep_per_feature = {}

for feature in tqdm(categorical_features, desc="Fitting encoders on training data"):
    counts = df[feature].value_counts()
    categories_to_keep = counts[counts >= min_occurrence].index
    categories_to_keep_per_feature[feature] = categories_to_keep
    
    if len(categories_to_keep) > 0:
        encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        # Fit on training data only
        encoder.fit(df[df[feature].isin(categories_to_keep)][[feature]])
        encoders[feature] = encoder

# Step 2: Transform TRAINING data
for feature in tqdm(categorical_features, desc="Transforming training data"):
    if feature in encoders:
        categories_to_keep = categories_to_keep_per_feature[feature]
        filtered_df = df[df[feature].isin(categories_to_keep)]
        
        if not filtered_df.empty:
            encoded_data = encoders[feature].transform(filtered_df[[feature]])
            encoded_df = pd.DataFrame(encoded_data, columns=encoders[feature].get_feature_names_out([feature]))
            
            # Handle rows that weren't in categories_to_keep by filling with zeros
            full_encoded_df = pd.DataFrame(0, index=df.index, columns=encoders[feature].get_feature_names_out([feature]))
            full_encoded_df.loc[filtered_df.index] = encoded_df
            
            df = df.drop(feature, axis=1)
            df = pd.concat([df, full_encoded_df], axis=1)

# Step 3: Transform TEST data using the same encoders
for feature in tqdm(categorical_features, desc="Transforming test data"):
    if feature in encoders:
        categories_to_keep = categories_to_keep_per_feature[feature]
        filtered_df = df2[df2[feature].isin(categories_to_keep)]
        
        if not filtered_df.empty:
            encoded_data = encoders[feature].transform(filtered_df[[feature]])
            encoded_df = pd.DataFrame(encoded_data, columns=encoders[feature].get_feature_names_out([feature]))
            
            # Handle rows that weren't in categories_to_keep by filling with zeros
            full_encoded_df = pd.DataFrame(0, index=df2.index, columns=encoders[feature].get_feature_names_out([feature]))
            full_encoded_df.loc[filtered_df.index] = encoded_df
            
            df2 = df2.drop(feature, axis=1)
            df2 = pd.concat([df2, full_encoded_df], axis=1)
        else:
            # If no categories match, create zero-filled columns
            encoded_df = pd.DataFrame(0, index=df2.index, columns=encoders[feature].get_feature_names_out([feature]))
            df2 = df2.drop(feature, axis=1)
            df2 = pd.concat([df2, encoded_df], axis=1)

print("Sanitizing column names for BigQuery compatibility...")
df = sanitize_column_names(df)
df2 = sanitize_column_names(df2)
print("✅ Column names sanitized")
# Get column names
train_cols = set(df.columns)
test_cols = set(df2.columns)

# Find differences
cols_only_in_train = train_cols - test_cols
cols_only_in_test = test_cols - train_cols
common_cols = train_cols & test_cols

# Print results
print(f"Total columns in train (df): {len(train_cols)}")
print(f"Total columns in test (df2): {len(test_cols)}")
print(f"Common columns: {len(common_cols)}")
print(f"Columns only in train: {len(cols_only_in_train)}")
print(f"Columns only in test: {len(cols_only_in_test)}")

print("\n" + "=" * 40)
print("COLUMNS ONLY IN TRAIN DATAFRAME:")
print("=" * 40)
if cols_only_in_train:
    for col in sorted(cols_only_in_train):
        print(f"  - {col}")
else:
    print("  None")

print("\n" + "=" * 40)
print("COLUMNS ONLY IN TEST DATAFRAME:")
print("=" * 40)
if cols_only_in_test:
    for col in sorted(cols_only_in_test):
        print(f"  - {col}")
else:
    print("  None")


# Get only numeric columns (integers and floats)
numeric_cols = [col for col in df.columns 
                if is_integer(df[col].dtype) or is_float(df[col].dtype)]

# Exclude target and other unwanted columns
exclude_cols = ['pre_term_max']
predictors = [col for col in numeric_cols if col not in exclude_cols]

X_train = df[predictors]
y_train = df['pre_term_max']

X_test = df2[predictors]
y_test = df2['pre_term_max']
# 80:10:10 split

y_train = y_train.astype('int')
y_test = y_test.astype('int')

import xgboost as xgb
#model = XGBRegressor(n_estimators=10, max_depth=20, enable_categorical=True, verbosity=2)
# Optimal model hyperparameters
model = xgb.XGBClassifier()
model.fit(X_train, y_train, verbose=0)

from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

def calculate_metrics(model):
    # Probabilities of the positive class
    y_pred_test = model.predict_proba(X_test)[:, 1]

    # Resetting the index of y_test for alignment
    y_test_reset = y_test.reset_index(drop=True)

    # ROC AUC Score
    roc_auc_test = roc_auc_score(y_test, y_pred_test)

    # Sorting indices by predicted probabilities in descending order
    idx = np.argsort(y_pred_test)[::-1]

    # Function to calculate metrics for a given cutoff percentile
    def calculate_percentile_metrics(y_test_reset, idx, percentile):
        cutoff = int(percentile * len(y_test_reset))  # Number of data points in the top percentile
        top_indices = idx[:cutoff]  # Indices of the top percentile predictions

        # Binary predictions for the top percentile
        predictions_binary = np.zeros(len(y_test_reset), dtype=int)
        predictions_binary[top_indices] = 1

        # Confusion matrix calculation
        tn, fp, fn, tp = confusion_matrix(y_test_reset, predictions_binary, labels=[0, 1]).ravel()

        # Performance metrics
        ppv = 100 * (tp / (tp + fp)) if (tp + fp) > 0 else 0  # Positive Predictive Value
        sensitivity = 100 * (tp / (tp + fn)) if (tp + fn) > 0 else 0  # Sensitivity or Recall

        # Lift calculation
        actual_positives_top_perc = y_test_reset[top_indices].sum()
        expected_positives = y_test_reset.sum() * percentile
        lift = actual_positives_top_perc / expected_positives if expected_positives > 0 else 0

        return lift, ppv, sensitivity

    lift_1_perc, ppv_1_perc, sensitivity_1_perc = calculate_percentile_metrics(y_test_reset, idx, 0.01)
    lift_10_perc, ppv_10_perc, sensitivity_10_perc = calculate_percentile_metrics(y_test_reset, idx, 0.10)
    lift_35_perc, ppv_35_perc, sensitivity_35_perc = calculate_percentile_metrics(y_test_reset, idx, 0.35)

    return roc_auc_test, lift_1_perc, lift_10_perc, ppv_1_perc, sensitivity_1_perc, ppv_10_perc, sensitivity_10_perc, lift_35_perc, ppv_35_perc, sensitivity_35_perc 
roc, lift_1_perc, lift_10_perc, ppv_1_perc, sensitivity_1_perc, ppv_10_perc, sensitivity_10_perc, lift_35_perc, ppv_35_perc, sensitivity_35_perc = calculate_metrics(model)
print("ROC: ",roc)
print("1% Lift: ",lift_1_perc)
print("1% PPV: ",ppv_1_perc)
print("1% Sensitivity: ",sensitivity_1_perc)
print("10% Lift: ",lift_10_perc)
print("10% PPV: ",ppv_10_perc)
print("10% Sensitivity: ",sensitivity_10_perc)
print("35% Lift: ",lift_35_perc)
print("35% PPV: ",ppv_35_perc)
print("35% Sensitivity: ",sensitivity_35_perc)


ratios = [0.2, 0.3, 0.4, 0.5]  # FILL IN RATIOS TO TEST
seeds = [53]  # Random seeds for reproducibility
results = []  # Store results

for r in ratios:
    for s in seeds:
        # Setup undersampler
        undersample = RandomUnderSampler(sampling_strategy=r, random_state=s)
        X_train_u, y_train_u = undersample.fit_resample(X_train, y_train)

        # Initialize and train XGBoost model
        xgb_model = XGBClassifier(seed=53, n_jobs=15, verbosity=0, enable_categorical=True)
        xgb_model.fit(X_train_u, y_train_u, verbose=False)
        print("done fit")

        # Predict probabilities
        y_pred_test = xgb_model.predict_proba(X_test)[:, 1]

        idx = np.argsort(y_pred_test)[::-1]
        top_1_percent = int(0.35 * len(y_test))  # 1% of test data size

        predicted_top_1_percent = y_test.iloc[idx][:top_1_percent]
        actual_positives_top_1_percent = predicted_top_1_percent.sum()

        expected_positives = y_test.sum() * 0.35

        lift = actual_positives_top_1_percent / expected_positives

        results.append((r, s, lift))
        print("one iteration", r, s, lift)

# No undersampling test
xgb_model = XGBClassifier(random_state=53, n_jobs=15, verbosity=0, enable_categorical=True)
xgb_model.fit(X_train, y_train, verbose=False)

print("done fit")

# Prediction and calculate lift
y_pred_test = xgb_model.predict_proba(X_test)[:, 1]
y_test_reset = y_test.reset_index(drop=True)
idx = np.argsort(y_pred_test)[::-1]
top_1_percent = int(0.35 * len(y_test_reset))

predicted_top_1_percent = y_test_reset.iloc[idx][:top_1_percent]
actual_positives_top_1_percent = predicted_top_1_percent.sum()
expected_positives = y_test_reset.sum() * 0.35
lift = actual_positives_top_1_percent / expected_positives

results.append((0, 0, lift))
print("one iteration, no sample")

# No undersampling but with class weights test
weights = np.where(y_train == 0, 1, len(y_train) / (2 * np.sum(y_train == 1)))

xgb_model = XGBClassifier(random_state=53, n_jobs=15, verbosity=0, enable_categorical=True)
xgb_model.fit(X_train, y_train, sample_weight=weights, verbose=False)

print("done fit")

# Prediction and calculate lift
y_pred_test = xgb_model.predict_proba(X_test)[:, 1]
y_test_reset = y_test.reset_index(drop=True)
idx = np.argsort(y_pred_test)[::-1]
top_1_percent = int(0.35 * len(y_test_reset))

predicted_top_1_percent = y_test_reset.iloc[idx][:top_1_percent]
actual_positives_top_1_percent = predicted_top_1_percent.sum()
expected_positives = y_test_reset.sum() * 0.35
lift = actual_positives_top_1_percent / expected_positives

results.append((999, 999, lift))
print("one iteration, class weights")

results_df = pd.DataFrame(results, columns=['Ratio', 'Seed', '1% Lift'])

import seaborn as sns
import matplotlib.pyplot as plt

sns.barplot(data=results_df, x='Ratio', y='1% Lift')
plt.title('1% Lift Across Different Ratios and Seeds')
plt.show()

results_df.to_csv('lift_results.csv', index=False)

def check_label_distribution(y):
    # Count the number of occurrences of each label 
    count_0 = (y == 0).sum()
    count_1 = (y == 1).sum()
    ratio = count_1 / count_0 if count_0 != 0 else np.inf
    print(count_0, count_1, ratio)
    return count_0, count_1, ratio

print("Training Set:")
check_label_distribution(y_train)

print("\nTest Set:")
check_label_distribution(y_test)

import gc
from xgboost import XGBClassifier
from sklearn.feature_selection import RFECV
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import roc_auc_score, confusion_matrix
import shap
import xgboost as xgb
del filtered_df, encoded_data, encoded_df, full_encoded_df
gc.collect()
import warnings
warnings.filterwarnings("ignore")
pd.set_option('mode.chained_assignment', None)

print("Memory freed")
# Check if GPU is available

#gpus = tf.config.experimental.list_physical_devices('GPU')
#if not gpus:
#    raise SystemError("No GPUs found. Please ensure your environment has a GPU available.")

# Initialize the GPU-enabled XGBoost classifier
def can_use_gpu():
    try:
        params = {"device": "cuda", "objective": "binary:logistic", "eval_metric": "auc"}
        dtrain = xgb.DMatrix(X_train.iloc[:50], label=y_train.iloc[:50])
        booster = xgb.train(params, dtrain, num_boost_round=1)
        print("GPU is available for XGBoost.")
        return True
    except Exception:
        print("GPU not available. Falling back to CPU.")
        return False

def make_xgb_params(learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8, random_state=53, scale_pos_weight=None):
    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "eta": learning_rate,
        "max_depth": max_depth,
        "subsample": subsample,
        "colsample_bytree": colsample_bytree,
        "device": "cuda" if can_use_gpu() else "cpu",
        "seed": random_state,
    }
    if scale_pos_weight is not None:
        params["scale_pos_weight"] = float(scale_pos_weight)
    return params

def booster_predict_proba_fast(booster, X):
    # Use inplace_predict on NumPy to avoid DMatrix overhead
    X_np = X.to_numpy(copy=False) if isinstance(X, pd.DataFrame) else np.asarray(X)
    if hasattr(booster, "inplace_predict"):
        return booster.inplace_predict(X_np)
    return booster.predict(xgb.DMatrix(X_np))

def permutation_importance_booster_fast(
    booster, X_val_df, y_val, baseline=None, n_repeats=3, random_state=53,
    features_to_eval=None, log_every=10
):
    rng = np.random.RandomState(random_state)
    if not isinstance(X_val_df, pd.DataFrame):
        X_val_df = pd.DataFrame(X_val_df)
    cols = list(X_val_df.columns)
    if features_to_eval is None:
        features = cols
    else:
        features = [c for c in features_to_eval if c in cols]

    X_np = X_val_df.to_numpy(copy=True)
    y_np = y_val.to_numpy(copy=False) if isinstance(y_val, pd.Series) else np.asarray(y_val)

    if baseline is None:
        baseline = roc_auc_score(y_np, booster_predict_proba_fast(booster, X_np))

    importances = np.zeros(len(features), dtype=float)
    start = time.time()

    for j, col in enumerate(tqdm(features, desc=f"PI fast ({len(features)} feats, repeats={n_repeats})", ncols=100)):
        col_idx = X_val_df.columns.get_loc(col)
        original = X_np[:, col_idx].copy()
        scores = []
        for r in range(n_repeats):
            rng.shuffle(X_np[:, col_idx])
            auc_perm = roc_auc_score(y_np, booster_predict_proba_fast(booster, X_np))
            scores.append(baseline - auc_perm)
            X_np[:, col_idx] = original
        importances[j] = np.mean(scores) if scores else 0.0

        if (j + 1) % log_every == 0:
            print(f"[PI fast] {j+1}/{len(features)} done, {((time.time()-start)/60):.1f} min")

    return pd.Series(importances, index=features).sort_values(ascending=False)

def compute_cv_shap_importance(
    X, y,
    n_splits=5,
    random_state=53,
    num_boost_round=1200,
    early_stopping_rounds=50,
    scale_pos_weight=None,
    X_test=None,
    y_test=None,
    test_sample=None,            # set None to use full test
    background_sample=5000,      # background rows for masker
    repeats=3                    # multiple SHAP samples per fold
):
    if X_test is None or y_test is None:
        raise ValueError("X_test and y_test must be provided for SHAP importance.")

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    params = make_xgb_params(random_state=random_state, scale_pos_weight=scale_pos_weight)
    fold_importances = []

    for fold, (train_idx, _) in enumerate(skf.split(X, y), 1):
        print(f"[Fold {fold}/{n_splits}] Preparing data")
        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_val_full, y_val_full = X_test, y_test

        # Ensure numeric types
        X_tr = X_tr.apply(pd.to_numeric, errors="coerce")
        X_val_full = X_val_full.apply(pd.to_numeric, errors="coerce")

        # Optional sample for SHAP evaluation
        if test_sample and len(X_val_full) > test_sample:
            X_val = X_val_full.sample(test_sample, random_state=random_state)
            y_val = y_val_full.loc[X_val.index]
        else:
            X_val, y_val = X_val_full, y_val_full

        # Background dataset for masker (float64 NumPy)
        bg_df = X_tr.sample(min(len(X_tr), background_sample), random_state=random_state)
        bg_np = bg_df.to_numpy(dtype=np.float64, copy=False)

        booster = xgb.train(
            params,
            xgb.DMatrix(X_tr, label=y_tr),
            num_boost_round=num_boost_round,
            evals=[(xgb.DMatrix(X_val, label=y_val), "validation")],
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=50
        )

        print(f"[Fold {fold}/{n_splits}] Computing SHAP importance with repeats={repeats}")
        masker = shap.maskers.Independent(bg_np)
        explainer = shap.Explainer(booster, masker=masker, model_output="probability")

        # Repeat SHAP on different samples to stabilize importance
        imps = []
        for r in range(repeats):
            if test_sample:
                n = min(len(X_val), test_sample)
                X_eval = X_val.sample(n, random_state=random_state + r)
            else:
                X_eval = X_val
            X_eval_np = X_eval.to_numpy(dtype=np.float64, copy=False)
            shap_exp = explainer(X_eval_np)            # Explanation object
            shap_vals = shap_exp.values                # (n_samples, n_features)
            mean_abs = np.mean(np.abs(shap_vals), axis=0)

            imps.append(pd.Series(mean_abs, index=X_eval.columns))

        # Fold-level importance: mean across repeats, sorted descending
        imp = pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)
        imp.name = f"fold_{fold}"
        fold_importances.append(imp)

        # Cleanup per fold
        del booster, explainer, masker
        gc.collect()

    # Aggregate across folds and return mean importance
    importance_df = pd.concat(fold_importances, axis=1).fillna(0.0)
    return importance_df.mean(axis=1).sort_values(ascending=False)

def select_features_by_cumulative(importance_series, threshold=0.95, min_features=20):
    importance = importance_series.clip(lower=0)
    total = importance.sum()
    if total <= 0:
        return importance.head(min_features).index.tolist()
    cum = (importance / total).cumsum()
    selected = cum[cum <= threshold].index.tolist()
    if len(selected) < min_features:
        selected = importance.head(min_features).index.tolist()
    return selected

def fit_final_model(X_train_sel, y_train, X_val=None, y_val=None, early_stopping_rounds=100, scale_pos_weight=None, num_boost_round=2000):
    params = make_xgb_params(scale_pos_weight=scale_pos_weight)
    dtrain = xgb.DMatrix(X_train_sel, label=y_train)
    if X_val is not None and y_val is not None:
        dval = xgb.DMatrix(X_val, label=y_val)
        booster = xgb.train(
            params,
            dtrain,
            num_boost_round=num_boost_round,
            evals=[(dval, "validation")],
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=False
        )
    else:
        booster = xgb.train(
            params,
            dtrain,
            num_boost_round=num_boost_round,
            verbose_eval=False
        )
    return booster

def evaluate_with_lift(booster, X_test_sel, y_test, top_percentiles=(0.01, 0.10, 0.35)):
    y_pred_test = booster_predict_proba_fast(booster, X_test_sel)
    roc = roc_auc_score(y_test, y_pred_test)
    idx = np.argsort(y_pred_test)[::-1]
    y_test_reset = y_test.reset_index(drop=True)

    metrics = {"roc_auc": roc}
    for p in top_percentiles:
        cutoff = int(p * len(y_test_reset))
        top_indices = idx[:cutoff]
        predictions_binary = np.zeros(len(y_test_reset), dtype=int)
        predictions_binary[top_indices] = 1

        tn, fp, fn, tp = confusion_matrix(y_test_reset, predictions_binary, labels=[0, 1]).ravel()
        ppv = 100 * (tp / (tp + fp)) if (tp + fp) > 0 else 0
        sensitivity = 100 * (tp / (tp + fn)) if (tp + fn) > 0 else 0
        actual_positives_top = y_test_reset[top_indices].sum()
        expected_positives = y_test_reset.sum() * p
        lift = actual_positives_top / expected_positives if expected_positives > 0 else 0

        metrics[f"lift_{int(p*100)}"] = lift
        metrics[f"ppv_{int(p*100)}"] = ppv
        metrics[f"sens_{int(p*100)}"] = sensitivity

    return metrics

# Optional: imbalance handling via scale_pos_weight
neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
scale_pos_weight = (neg / pos) if pos > 0 else None

# 1) CV permutation importance on training data
importance_mean = compute_cv_shap_importance(
    X_train, y_train,
    n_splits=5,
    random_state=53,
    num_boost_round=1200,
    early_stopping_rounds=50,
    scale_pos_weight=scale_pos_weight,
    X_test=X_test,
    y_test=y_test,
    test_sample=None,      # None => use full X_test
    background_sample=5000,
    repeats=3
)
print("Top 20 by mean permutation importance:")
print(importance_mean.head(20))

# 2) Select features by 95% cumulative importance with a floor of 20 features
selected_features = select_features_by_cumulative(importance_mean, threshold=0.95, min_features=20)
print(f"Selected {len(selected_features)} features")

# 3) Build selected datasets
X_train_sel = X_train[selected_features]
X_test_sel = X_test[selected_features]

# 4) Fit final model with early stopping on a small validation split
X_tr, X_val, y_tr, y_val = train_test_split(X_train_sel, y_train, test_size=0.1, stratify=y_train, random_state=53)
final_booster = fit_final_model(X_tr, y_tr, X_val, y_val, early_stopping_rounds=100, scale_pos_weight=scale_pos_weight, num_boost_round=2000)

# 5) Evaluate on external test set
metrics = evaluate_with_lift(final_booster, X_test_sel, y_test, top_percentiles=(0.01, 0.10, 0.35))
print(metrics)

# Persist selected features and upload (same as before)
import datetime
timestamp = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
local_filename = f"test_gdm_selected_features_update_{timestamp}.txt"
with open(local_filename, 'w') as file:
    file.write('\n'.join(selected_features))

from google.cloud import storage
def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}")

bucket_name = "hcm-cm-de-code-hcb-dev"
destination_path = f"vertex-test/codecode/{local_filename}"
upload_to_gcs(bucket_name, local_filename, destination_path)

train_df_selected = df[selected_features + ['pre_term_max']].copy()
test_df_selected = df2[selected_features + ['pre_term_max']].copy()

print(f"Original training data shape: {df.shape}")
print(f"Selected training data shape: {train_df_selected.shape}")
print(f"Original test data shape: {df2.shape}")
print(f"Selected test data shape: {test_df_selected.shape}")

destination_table = f"{constants['GCP_PROJECT']}.{constants['GCP_DB']}.{constants['PREFIX']}_selected_features_train_{timestamp}"
bq_client = bigquery.Client(project=constants['GCP_PROJECT'])

try:
    try:
        bq_client.delete_table(destination_table, not_found_ok=True)
        print(f"✅ Dropped existing table: {destination_table}")
    except Exception as e:
        print(f"Table {destination_table} doesn't exist or couldn't be dropped: {e}")

    train_df_selected.to_gbq(
        destination_table=destination_table,
        project_id=constants['GCP_PROJECT'],
        if_exists='replace',
        table_schema=None,
        location='US'
    )
    print(f"Successfully uploaded selected features to {destination_table}")

    query = f"""
    ALTER TABLE `{destination_table}` 
    SET OPTIONS (
        labels=[
            ("owner", "{constants.get('OWNER', 'sahil_gadge_aetna_com')}"), 
            ("cost_center", "{constants.get('COSTCENTER', '13070')}"), 
            ("unique_id", "hcm-cm-gen-me-prod"),
            ("pipeline_type", "feature_engineering"),
            ("lob", "hcb")
        ],
        expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    )
    """
    query_job = bq_client.query(query)
    query_job.result()
    print(f"✅ Added labels and 7-day expiry to {destination_table}")
except Exception as e:
    print(f"Error uploading to BigQuery: {e}")

destination_table_test = f"{constants['GCP_PROJECT']}.{constants['GCP_DB']}.{constants['PREFIX']}_selected_features_test_{timestamp}"

try:
    try:
        bq_client.delete_table(destination_table_test, not_found_ok=True)
        print(f"✅ Dropped existing table: {destination_table_test}")
    except Exception as e:
        print(f"Table {destination_table_test} doesn't exist or couldn't be dropped: {e}")

    test_df_selected.to_gbq(
        destination_table=destination_table_test,
        project_id=constants['GCP_PROJECT'],
        if_exists='replace',
        table_schema=None,
        location='US'
    )
    print(f"Successfully uploaded selected features to {destination_table_test}")

    query = f"""
    ALTER TABLE `{destination_table_test}` 
    SET OPTIONS (
        labels=[
            ("owner", "{constants.get('OWNER', 'sahil_gadge_aetna_com')}"), 
            ("cost_center", "{constants.get('COSTCENTER', '13070')}"), 
            ("unique_id", "hcm-cm-gen-me-prod"),
            ("pipeline_type", "feature_engineering"),
            ("lob", "hcb")
        ],
        expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    )
    """
    query_job = bq_client.query(query)
    query_job.result()
    print(f"✅ Added labels and 7-day expiry to {destination_table_test}")
except Exception as e:
    print(f"Error uploading test data to BigQuery: {e}")
    