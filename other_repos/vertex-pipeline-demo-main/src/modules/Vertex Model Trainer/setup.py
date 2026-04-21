"""Setup script for the ss-models XGBoost training package."""
from setuptools import setup, find_packages

setup(
    name="ss-models-trainer",
    version="0.1.0",
    description="XGBoost model training pipeline for Vertex AI custom training (ss-models)",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        # GCP
        "google-cloud-bigquery",
        "google-cloud-bigquery-storage",
        "google-cloud-storage",
        "google-cloud-aiplatform",
        "db-dtypes",
        "pandas-gbq",
        "requests",
        # Data
        "pandas",
        "numpy==1.26.4",
        "pyarrow",
        # ML
        "xgboost==2.1.4",
        "scikit-learn==1.5.2",
        "imbalanced-learn",
        "joblib==1.4.2",
        "scipy==1.15.3",
        # Utilities
        "tqdm",
        "pyyaml",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "ss-models-train=trainer.task:main",
        ]
    },
)

