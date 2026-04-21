"""Feature engineering utilities."""
import pandas as pd
from tqdm import tqdm
from sklearn.preprocessing import OneHotEncoder
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import is_date_column


def auto_classify_features(df, unique_threshold_binary=2, unique_threshold_categorical=20, 
                          exclude_cols=None, sample_size=100000, manual_overrides=None, verbose=False):
    """Automatically classify dataframe columns into types.
    
    Classifies columns into:
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
    if exclude_cols is None:
        exclude_cols = []
    
    feature_types = {}
    
    if len(df) > sample_size:
        df_sample = df.sample(n=sample_size, random_state=42)
    else:
        df_sample = df
    
    for col in df.columns:
        if col in exclude_cols:
            feature_types[col] = 1
            continue
        
        if manual_overrides and col in manual_overrides:
            feature_types[col] = manual_overrides[col]
            if verbose:
                print(f"Manual override: {col} -> {manual_overrides[col]}")
            continue

        if 'emb' in col.lower() or '_amt' in col.lower():
            feature_types[col] = 1
            if verbose:
                print(f"Embedding/amount detected: {col} -> 1 (continuous)")
            continue
        
        non_null_values = df_sample[col].dropna()
        
        if len(non_null_values) == 0:
            feature_types[col] = 1
            continue
        
        n_unique = non_null_values.nunique()
        dtype = df[col].dtype
        
        if is_date_column(df[col]):
            feature_types[col] = 3
            if verbose:
                print(f"Date detected: {col} -> 3 (datetime)")
            continue
        
        if n_unique <= unique_threshold_binary:
            unique_vals = set(non_null_values.unique())
            if (unique_vals <= {0, 1} or unique_vals <= {0.0, 1.0} or 
                unique_vals <= {True, False} or unique_vals <= {'Yes', 'No'} or
                unique_vals <= {'Y', 'N'} or unique_vals <= {1, 2}):
                feature_types[col] = 2
                if verbose:
                    print(f"Binary detected: {col} -> 2 (binary)")
                continue
        
        if dtype == 'object' or dtype.name == 'category':
            feature_types[col] = 0
            if verbose:
                print(f"Categorical detected: {col} -> 0 (categorical)")
        elif n_unique <= unique_threshold_categorical:
            feature_types[col] = 0
            if verbose:
                print(f"Low cardinality categorical: {col} -> 0 (categorical, {n_unique} unique values)")
        else:
            feature_types[col] = 1
            if verbose:
                print(f"Continuous detected: {col} -> 1 (continuous)")
    
    return feature_types


def fit_one_hot_encoders(df, categorical_features, min_occurrence=2000):
    """Fit one-hot encoders on training data.
    
    Args:
        df: Training DataFrame
        categorical_features: List of categorical feature names
        min_occurrence: Minimum occurrence threshold for categories
        
    Returns:
        tuple: (encoders_dict, categories_to_keep_per_feature_dict)
    """
    encoders = {}
    categories_to_keep_per_feature = {}
    
    for feature in tqdm(categorical_features, desc="Fitting encoders"):
        counts = df[feature].value_counts()
        categories_to_keep = counts[counts >= min_occurrence].index
        categories_to_keep_per_feature[feature] = categories_to_keep
        
        if len(categories_to_keep) > 0:
            encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
            encoder.fit(df[df[feature].isin(categories_to_keep)][[feature]])
            encoders[feature] = encoder
    
    return encoders, categories_to_keep_per_feature


def apply_one_hot_encoding(df, categorical_features, encoders, categories_to_keep_per_feature):
    """Apply one-hot encoding to a dataframe.
    
    Args:
        df: DataFrame to transform
        categorical_features: List of categorical feature names
        encoders: Dictionary of fitted encoders
        categories_to_keep_per_feature: Dictionary of categories to keep per feature
        
    Returns:
        pandas DataFrame: Transformed DataFrame
    """
    for feature in tqdm(categorical_features, desc="Transforming data"):
        if feature in encoders:
            categories_to_keep = categories_to_keep_per_feature[feature]
            filtered_df = df[df[feature].isin(categories_to_keep)]
            
            if not filtered_df.empty:
                encoded_data = encoders[feature].transform(filtered_df[[feature]])
                encoded_df = pd.DataFrame(
                    encoded_data, 
                    columns=encoders[feature].get_feature_names_out([feature])
                )
                full_encoded_df = pd.DataFrame(
                    0, 
                    index=df.index, 
                    columns=encoders[feature].get_feature_names_out([feature])
                )
                full_encoded_df.loc[filtered_df.index] = encoded_df
                df = df.drop(feature, axis=1)
                df = pd.concat([df, full_encoded_df], axis=1)
            else:
                encoded_df = pd.DataFrame(
                    0, 
                    index=df.index, 
                    columns=encoders[feature].get_feature_names_out([feature])
                )
                df = df.drop(feature, axis=1)
                df = pd.concat([df, encoded_df], axis=1)
    
    return df

