"""Setup script for feature engineering training package."""
from setuptools import setup, find_packages
from pathlib import Path

setup(
    name="feature-engineering-trainer",
    version="0.1.0",
    description="Feature engineering pipeline for Vertex AI custom training",
    author="Your Name",
    packages=find_packages(),
    include_package_data=True,  # Include files specified in MANIFEST.in
    install_requires=[
        # Core data processing
        # Note: pandas, numpy, matplotlib may be pre-installed in base image
        # Using flexible constraints to avoid conflicts
        "google-cloud-bigquery",
        "google-cloud-bigquery-storage",
        "google-cloud-aiplatform", 
        "google-cloud-storage",
        "pandas",
        "numpy==1.26.4",              
        "xgboost==2.1.4",             
        "scikit-learn==1.5.2",        
        "scipy==1.15.3",              
        "joblib==1.4.2",
        "shap==0.44.1",
        "imbalanced-learn",
        "optuna",
        "cytoolz",
        "db-dtypes",
        "matplotlib",
        "seaborn", 
        "tqdm",
        "pandas_gbq",
        "pyyaml",  # Required for config.yaml loading
        "cloudml-hypertune",  # Required for hyperparameter tuning
    ],
    python_requires=">=3.8",
)

