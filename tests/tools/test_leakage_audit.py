from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from runner.tools import leakage_audit
from tests.fixtures.tiny_dataset import make_tiny_binary

DATA_CONTRACT_SIMPLE = """---
schema_version: 1
campaign_id: "tiny"
data_sources:
  - path: "data/tiny.csv"
    n_rows: 500
    n_cols: 6
    primary_key: "row"
temporal:
  is_temporal: false
  order_column: null
  prediction_time_column: null
columns:
  - name: "x1"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x2"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x3"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x4"
    dtype: "float64"
    role: "feature"
    available_at_prediction: true
  - name: "x5"
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
  notes: ""
splits:
  train: "60%"
  val: "20%"
  test: "20%"
  random_seed: 42
---

## 1. Schema summary
## 2. Availability table (narrative)
## 3. Leakage audit summary
## 4. Transformations applied pre-agent (if any)
## 5. Known data quality issues
"""


@pytest.fixture
def clean_csv(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    df = X.copy()
    df["Class"] = y
    path = tmp_path / "tiny.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def leaky_csv(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    rng = np.random.default_rng(0)
    X = X.copy()
    X["leaky"] = y.values + rng.normal(0, 0.001, size=len(y))
    df = X.copy()
    df["Class"] = y
    path = tmp_path / "leaky.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def contract_path(tmp_path: Path) -> Path:
    p = tmp_path / "DATA_CONTRACT.md"
    p.write_text(DATA_CONTRACT_SIMPLE)
    return p


def test_leakage_audit_clean(clean_csv: Path, contract_path: Path):
    res = leakage_audit.leakage_audit(
        data_contract_path=str(contract_path),
        data_path=str(clean_csv),
        target_col="Class",
    )
    assert res["flagged"] == []


def test_leakage_audit_catches_leaky_feature(leaky_csv: Path, contract_path: Path):
    src = contract_path.read_text()
    src = src.replace(
        '  - name: "Class"',
        '  - name: "leaky"\n    dtype: "float64"\n    role: "feature"\n    available_at_prediction: true\n  - name: "Class"',
    )
    contract_path.write_text(src)
    res = leakage_audit.leakage_audit(
        data_contract_path=str(contract_path),
        data_path=str(leaky_csv),
        target_col="Class",
    )
    assert "leaky" in res["flagged"]


def test_leakage_audit_constant_column_flagged(clean_csv: Path, contract_path: Path, tmp_path: Path):
    df = pd.read_csv(clean_csv)
    df["constant"] = 7.0
    new_csv = tmp_path / "with_const.csv"
    df.to_csv(new_csv, index=False)
    src = contract_path.read_text().replace(
        '  - name: "Class"',
        '  - name: "constant"\n    dtype: "float64"\n    role: "feature"\n    available_at_prediction: true\n  - name: "Class"',
    )
    contract_path.write_text(src)
    res = leakage_audit.leakage_audit(
        data_contract_path=str(contract_path),
        data_path=str(new_csv),
        target_col="Class",
    )
    assert "constant" in res["flagged"]
