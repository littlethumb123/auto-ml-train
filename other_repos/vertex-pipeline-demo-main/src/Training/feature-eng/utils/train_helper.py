import os
import re
import pandas as pd
import numpy as np

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