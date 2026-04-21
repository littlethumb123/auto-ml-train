from setuptools import find_packages
from setuptools import setup

REQUIRED_PACKAGES = [
    'db-dtypes==1.2.0',
    'xgboost',
    'joblib',
    'pandas',
    'numpy',
    'scikit-learn',
    'google-cloud-bigquery',
    'google-cloud-storage',
    'pandas-gbq',
    'tqdm',
    'cloudml-hypertune'
]

setup(
    name='trainer',
    version='0.1',
    install_requires=REQUIRED_PACKAGES,
    packages=find_packages(),
    include_package_data=True,
    description='My training application.',
    python_requires='>=3.8',
)