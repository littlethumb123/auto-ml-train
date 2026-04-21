#!/usr/bin/env python3
"""
XGBoost Training Script for Vertex AI Hyperparameter Tuning

This script trains an XGBoost model with hyperparameters provided by Vertex AI
Hyperparameter Tuning job. It handles data loading from BigQuery, preprocessing,
training, evaluation, and model saving.
"""

import argparse
import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from typing import Dict, Any

# ML libraries
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, roc_curve, accuracy_score

# Google Cloud libraries
from google.cloud import bigquery
from google.cloud import storage
import hypertune
import joblib
import tempfile

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='XGBoost Training Script')
    
    # Data arguments
    parser.add_argument('--project', type=str, required=True, help='GCP project ID')
    parser.add_argument('--training_table', type=str, required=True, help='training_ table name')
    parser.add_argument('--target_column', type=str, default='y', help='Target column name')
    
    # Model output arguments
    parser.add_argument('--model_dir', type=str, required=True, help='Model output directory')
    parser.add_argument('--job_dir', type=str, help='Job directory for outputs')
    
    # Hyperparameters (will be provided by Vertex AI Hyperparameter Tuning)
    parser.add_argument('--eta', type=float, default=0.01, help='Learning rate')
    parser.add_argument('--max_depth', type=int, default=4, help='Maximum tree depth')
    parser.add_argument('--subsample', type=float, default=0.5, help='Subsample ratio')
    parser.add_argument('--colsample_bytree', type=float, default=1.0, help='Column sampling ratio')
    parser.add_argument('--min_child_weight', type=int, default=1, help='Minimum child weight')
    parser.add_argument('--num_boost_round', type=int, default=1000, help='Number of boosting rounds')
    
    # Training arguments
    parser.add_argument('--test_size', type=float, default=0.3, help='Test set size ratio')
    parser.add_argument('--random_state', type=int, default=4321, help='Random state for reproducibility')
    
    return parser.parse_args()


def load_data_from_bigquery(project,training_table) -> pd.DataFrame:
    """Load data from BigQuery table."""
    client = bigquery.Client(project=project)
    
    sql = f"""
    SELECT *
    FROM `{training_table}` limit 10000
    """
    
    print(f"Loading data from {training_table}")
    df = client.query(sql).to_dataframe()
    print(f"Data loaded: {df.shape}")
    
    return df


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocess the data similar to the notebook."""
    print("Starting data preprocessing...")
    
    # Convert target column to int
    df['y'] = df['y'].astype('int')
    
    # Handle missing values and data types
    float64_columns = df.select_dtypes(include=['float64']).columns
    df[float64_columns] = df[float64_columns].fillna(0.0)
    for col in float64_columns:
        df[col] = df[col].astype('float')
    
    int64_columns = df.select_dtypes(include=['int64']).columns
    df[int64_columns] = df[int64_columns].fillna(0)
    for col in int64_columns:
        df[col] = df[col].astype('int')
    
    print(f"Data preprocessing completed: {df.shape}")
    return df


def get_feature_columns(df: pd.DataFrame) -> list:
    """Get feature columns, excluding target and ID columns."""
    # Define columns to drop (similar to the notebook)
    drop_col = [
        'y', 'individual_id', 'mm_cnt_3mo', 'mm_cnt_6mo', 'mm_cnt_2yr', 'mm_cnt_1yr',
        'busln_cp', 'busln_me', 'busln_e2', 'fund_si', 
        'prd_hmo', 'prd_ppo', 'prd_managedchoice', 'prd_indemnity',
        'custsubAGB', 'custsubARP', 'custsubBOA', 'custsubCRC', 'custsubFED', 'custsubHIX', 
        'custsubICV', 'custsubIPP', 'custsubIVL', 'custsubJCA', 'custsubKEY', 'custsubMDR', 
        'custsubNA', 'custsubNAG', 'custsubOTH', 'custsubSEL', 'custsubSG', 'custsubSH',
        'custIND', 'custNA2', 'custGOV', 'custASM'
    ]

    # Get available columns (some might not exist in the dataset)
    available_drop_cols = [col for col in drop_col if col in df.columns]
    feature_columns = [col for col in df.columns if col not in available_drop_cols]
    
    print(f"Feature columns selected: {len(feature_columns)}")
    return feature_columns


def train_model(args) -> Dict[str, Any]:
    """Train the XGBoost model."""
    print("Starting model training...")
    
    # Load and preprocess data
    df = load_data_from_bigquery(args.project,args.training_table)
    df = preprocess_data(df)
    
    # Prepare features and target
    feature_columns = ['hcc_sum',
         'past_fall_ts4',
         'past_fall_ts3',
         'er_clm_cnt_ts3',
         'anticonvulsants_flag_ts2',
         'past_fall_ts5',
         'antidepressants_flag_ts2',
         'dep',
         'age_nbr',
         'antidepressants_flag_ts3',
         'clm_ln_cnt_ts3',
         'uniq_dx_cd_cnt_ts2',
         'uniq_dx_cd_cnt_ts1',
         'antidepressants_days_ts1',
         'anticonvulsants_days_ts2',
         'uniq_rev_cd_cnt_ts3',
         'rmor_hcc_dscon_52',
         'uniq_rev_cd_cnt_ts2',
         'cv_cond',
         'prc155_cnt_ts2',
         'prcc1115_cnt_ts1',
         'er_clm_cnt_ts1',
         'anticonvulsants_days_ts1',
         'dxc1065_cnt_ts3',
         'lbp',
         'dxc1065_cnt_ts2',
         'e_wrkcoup1',
         'psychotherapeutic_neurological_agents_flag_ts3',
         'e_ntlincpctl',
         'er_clm_cnt_ts4',
         'uniq_dx_cd_cnt_ts3',
         'female',
         'rev450_cnt_ts4',
         'er_clm_cnt_ts2',
         'dem',
         'dx195_cnt_ts2',
         'pim_ts1',
         'par',
         'antidementia_agents_flag_ts3',
         'ylm_homeagesourceR',
         'e_estcurrhmval',
         'psychotherapeutic_neurological_agents_days_ts2',
         'ylm_orent',
         'prc155_cnt_ts1',
         'e_hmtotval',
         'prc92_cnt_ts4',
         'ngd',
         'aff',
         'antidementia_agents_days_ts2',
         'psychotherapeutic_neurological_agents_days_ts3',
         'uniq_rev_cd_cnt_ts1',
         'psychotherapeutic_neurological_agents_days_ts1',
         'dx136_cnt_ts1',
         'cbd',
         'ylm_tw_lifeins',
         'anticonvulsants_days_ts3',
         'e_avgopntrdrp6',
         'dxc1065_cnt_ts1',
         'dxc1065_cnt_ts4',
         'ipevt_cnt_ts1',
         'e_yownhomey',
         'ost',
         'alc',
         'lab_max_cholest_ts5',
         'spcclmVVPD_cnt_ts3',
         'e_pctmercecar',
         'antiparkinson_dopaminergics_flag_ts3',
         'loop_diuretics_days_ts3',
         'dx195_cnt_ts1',
         'lab_max_ldl_ts4',
         'antiparkinson_dopaminergics_flag_ts4',
         'dx77_cnt_ts3',
         'rmor_hcc_dscon_51',
         'prcc1055_cnt_ts3',
         'prc155_cnt_ts4',
         'dxc1060_cnt_ts1',
         'ylm_tw_luxcarbuy',
         'ylm_ind_maritalstatusM',
         'e_avgtrdnvrdeldrg24m',
         'spcclmVVDM_cnt_ts1',
         'lab_max_ldl_ts5',
         'lab_max_triglyc_ts4',
         'prc92_cnt_ts5',
         'antidepressants_flag_ts4',
         'gpi2_58_pdc_ts2',
         'prcc1055_cnt_ts2',
         'lab_max_altsgpt_ts5',
         'urinary_antispasmodics_days_ts3',
         'loop_diuretics_days_ts2',
         'NON_URGENT_REFERRAL_QUE_yes',
         'ercs_cnt_ts5',
         'urinary_antispasmodics_days_ts2',
         'e_avgopn2trdwbexcdrgrp6',
         'e_pctupsccar',
         'anx',
         'lab_max_psa_ts5',
         'dx77_cnt_ts4',
         'selective_serotonin_reuptake_inhibitors_ssris_days_ts1',
         'lab_max_triglyc_ts5',
         'chr_flag',
         'psychotherapeutic_neurological_agents_flag_ts4',
         'e_avgmpmtomtfrp6',
         'e_dwelluszcda',
         'urinary_antispasmodics_days_ts1',
         'uniq_dx_cd_cnt_ts5',
         'antidementia_agents_days_ts3',
         'e_pctimpcarmk',
         'antiparkinson_dopaminergics_days_ts2',
         'antiparkinson_agents_days_ts1',
         'analgesics_opioid_days_ts1',
         'ylm_tw_rentcar',
         'dxc1048_cnt_ts2',
         'air_pollution_index_bg',
         'spcclmVVPD_cnt_ts2',
         'ylm_tw_avidcelluser',
         'osp',
         'e_combhmownh',
         'dxc1060_cnt_ts2',
         'GINI_INDEX_OF_INCOME_INEQUALITY',
         'ylm_tw_cell_only_mdl']
    X = df[feature_columns]
    y = df[[args.target_column]]
    
    print(f"Features shape: {X.shape}")
    print(f"Target shape: {y.shape}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=args.test_size, 
        random_state=args.random_state
    )
    
    print(f"Train set: {X_train.shape}, Test set: {X_test.shape}")
    
    # Prepare XGBoost matrices
    dtrain = xgb.DMatrix(X_train, y_train)
    dtest = xgb.DMatrix(X_test, y_test)
    
    # Set up XGBoost parameters
    params = {
        'objective': 'binary:logistic',
        'tree_method': 'hist',
        'grow_policy': 'lossguide',
        'eta': args.eta,
        'max_depth': args.max_depth,
        'subsample': args.subsample,
        'colsample_bytree': args.colsample_bytree,
        'min_child_weight': args.min_child_weight,
        'verbosity': 1
    }
    
    print(f"Training parameters: {params}")
    
    # Train the model
    bst = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=args.num_boost_round,
        evals=[(dtrain, 'train'), (dtest, 'eval')],
        early_stopping_rounds=50,
        verbose_eval=100
    )
    
    # Make predictions
    y_pred = bst.predict(dtest)
    y_pred_binary = (y_pred > 0.5).astype(int)
    
    # Calculate metrics
    roc_auc = roc_auc_score(y_test, y_pred)
    accuracy = accuracy_score(y_test, y_pred_binary)
    
    print(f"ROC AUC: {roc_auc:.4f}")
    print(f"Accuracy: {accuracy:.4f}")
    
    # Save the model
    local_model_path = 'model.bst'
    bst.save_model(local_model_path)
    # Upload to GCS if model_dir is a GCS path
   
    client = storage.Client()
    bucket_name = args.model_dir.replace('gs://', '').split('/')[0]
    prefix = '/'.join(args.model_dir.replace('gs://', '').split('/')[1:])
    blob = client.bucket(bucket_name).blob(f"{prefix}/model.bst")
    blob.upload_from_filename(local_model_path)
    print(f"Model saved to: {args.model_dir}")
    
    # Save feature importance
#     feature_importance = bst.get_score(importance_type='gain')
#     feature_importance_sorted = sorted(
#         [(k, v) for k, v in feature_importance.items()], 
#         key=lambda x: x[1], 
#         reverse=True
#     )
    
#     # Save feature importance to file
#     importance_path = os.path.join(args.model_dir, 'feature_importance.pkl')
#     with open(importance_path, 'wb') as f:
#         pickle.dump(feature_importance_sorted, f)
    
    # Save predictions for evaluation
#     predictions_df = pd.DataFrame({
#         'y_true': y_test[args.target_column].values,
#         'y_pred': y_pred,
#         'y_pred_binary': y_pred_binary
#     })
#     predictions_path = os.path.join(args.model_dir, 'predictions.csv')
#     predictions_df.to_csv(predictions_path, index=False)
    
    # Save model metadata
    metadata = {
        'roc_auc': float(roc_auc),
        'accuracy': float(accuracy),
        'num_features': len(feature_columns),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'hyperparameters': params,
        'feature_columns': feature_columns
    }
    
    # Save locally first
    with tempfile.NamedTemporaryFile("w", delete=False) as tmpf:
        json.dump(metadata, tmpf, indent=2)
        local_metadata_path = tmpf.name

    return {
        'roc_auc': roc_auc,
        'accuracy': accuracy,
        'model': bst
    }



args = parse_arguments()
print("Arguments received:", sys.argv)

print("Starting XGBoost training with hyperparameter tuning...")
print(f"Arguments: {vars(args)}")

try:
    # Train the model
    results = train_model(args)

    # Report metrics to Vertex AI Hyperparameter Tuning
    hpt = hypertune.HyperTune()
    hpt.report_hyperparameter_tuning_metric(
        hyperparameter_metric_tag='roc_auc',
        metric_value=results['roc_auc']
    )

    print(f"Training completed successfully!")
    print(f"Final ROC AUC: {results['roc_auc']:.4f}")
    print(f"Final Accuracy: {results['accuracy']:.4f}")

except Exception as e:
    print(f"Training failed with error: {str(e)}")
    sys.exit(1)


