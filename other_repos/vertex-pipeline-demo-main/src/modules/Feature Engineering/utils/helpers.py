"""Shared utility functions for the Feature Engineering pipeline.

Public API
----------
``is_date_column(series, sample_size)``
    Heuristic date detector. Returns ``True`` if the Series is a datetime
    dtype, has a date-like column name, or its values match common date
    string patterns. Used by ``auto_classify_features`` to assign type 3.

``process_sql_file(sql_content, constants)``
    Substitutes ``{VARIABLE}`` placeholders in a SQL string using the
    *constants* dict produced by ``get_constants_from_config``. Logs any
    placeholders that could not be resolved, then returns the final query.

``sanitize_column_names(df)``
    Renames DataFrame columns to be safe for XGBoost and BigQuery:
    dots → underscores, non-alphanumeric → underscores, digit-prefixed
    columns are prefixed with ``col_``.

``check_label_distribution(y)``
    Prints and returns ``(count_0, count_1, ratio_1_to_0)`` for a binary
    label Series. Used to monitor class imbalance before and after
    undersampling.
"""
import pandas as pd
import re


def is_date_column(series, sample_size=1000):
    """Enhanced date detection for pandas Series.
    
    Args:
        series: pandas Series to check
        sample_size: number of values to sample for analysis
    
    Returns:
        bool: True if the series appears to contain dates
    """
    sample_data = series.dropna().head(sample_size)
    
    if len(sample_data) == 0:
        return False
    
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    
    dtype_str = str(series.dtype)
    if 'DateDtype' in dtype_str or 'db_dtypes' in dtype_str:
        return True
    
    date_keywords = ['date', 'time', 'dt', 'timestamp', 'created', 'updated', 'dob', 'birth']
    col_name_lower = series.name.lower()
    if any(keyword in col_name_lower for keyword in date_keywords):
        return True
    
    try:
        sample_str = sample_data.astype(str).iloc[0]
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{4}/\d{2}/\d{2}',
            r'\d{8}',
        ]
        if any(re.match(pattern, sample_str) for pattern in date_patterns):
            pd.to_datetime(sample_data.head(5), errors='raise')
            return True
    except (ValueError, TypeError, pd.errors.ParserError):
        pass
    
    if pd.api.types.is_numeric_dtype(series):
        sample_values = sample_data.head(10)
        if (sample_values > 1000000000).all() and (sample_values < 2000000000).all():
            return True
        if (sample_values > 40000).all() and (sample_values < 50000).all():
            return True
    
    return False


def process_sql_file(sql_content, constants):
    """Process SQL file with variable substitution.
    
    Args:
        sql_content: SQL query string with {VARIABLE} placeholders
        constants: Dictionary of constants for substitution
        
    Returns:
        str: Processed SQL query with variables substituted
    """
    variables_in_sql = re.findall(r'\{([^}]+)\}', sql_content)
    substitution_dict = {}
    
    for key, value in constants.items():
        if isinstance(value, dict):
            continue
        elif isinstance(value, bool):
            substitution_dict[key] = str(value).upper()
        else:
            substitution_dict[key] = str(value)
    
    substitution_dict['COST_CENTER'] = constants.get('COSTCENTER', '')
    
    missing_variables = []
    available_substitutions = {}
    
    for var_name in variables_in_sql:
        if var_name in substitution_dict:
            available_substitutions[var_name] = substitution_dict[var_name]
        else:
            missing_variables.append(var_name)
    
    if missing_variables:
        print(f"Warning: Variables not found: {missing_variables}")
    
    try:
        sql_query = sql_content.format(**available_substitutions)
    except KeyError as e:
        print(f"Available substitutions: {list(available_substitutions.keys())}")
        raise
    
    return sql_query


def sanitize_column_names(df):
    """Sanitize column names for BigQuery compatibility.
    
    Args:
        df: DataFrame to sanitize
        
    Returns:
        pandas DataFrame: DataFrame with sanitized column names
    """
    sanitized_columns = []
    for col in df.columns:
        sanitized_col = col.replace('.', '_')
        sanitized_col = re.sub(r'[^a-zA-Z0-9_]', '_', sanitized_col)
        if sanitized_col[0].isdigit():
            sanitized_col = 'col_' + sanitized_col
        sanitized_columns.append(sanitized_col)
    
    df.columns = sanitized_columns
    return df


def check_label_distribution(y):
    """Check and print label distribution.
    
    Args:
        y: pandas Series or array with labels
        
    Returns:
        tuple: (count_0, count_1, ratio)
    """
    count_0 = (y == 0).sum()
    count_1 = (y == 1).sum()
    ratio = count_1 / count_0 if count_0 != 0 else float('inf')
    print(count_0, count_1, ratio)
    return count_0, count_1, ratio



