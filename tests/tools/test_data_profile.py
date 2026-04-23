from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from runner.tools import data_profile
from tests.fixtures.tiny_dataset import make_tiny_binary


@pytest.fixture
def tiny_csv(tmp_path: Path) -> Path:
    X, y = make_tiny_binary()
    df = X.copy()
    df["Class"] = y
    path = tmp_path / "tiny.csv"
    df.to_csv(path, index=False)
    return path


def test_data_profile_returns_expected_keys(tiny_csv: Path, tmp_path: Path):
    out_md = tmp_path / "profile.md"
    res = data_profile.data_profile(
        data_path=str(tiny_csv), target_col="Class", output_md=str(out_md),
    )
    assert res["n_rows"] == 500
    assert res["n_cols"] == 6
    assert "target_distribution" in res
    assert out_md.exists()
    assert "# Data profile" in out_md.read_text()


def test_data_profile_missing_target_raises(tiny_csv: Path, tmp_path: Path):
    out_md = tmp_path / "profile.md"
    with pytest.raises(ValueError):
        data_profile.data_profile(
            data_path=str(tiny_csv), target_col="nonexistent", output_md=str(out_md),
        )


def test_data_profile_missing_file_raises(tmp_path: Path):
    out_md = tmp_path / "profile.md"
    with pytest.raises(FileNotFoundError):
        data_profile.data_profile(
            data_path=str(tmp_path / "nope.csv"), target_col="Class", output_md=str(out_md),
        )


def test_data_profile_determinism(tiny_csv: Path, tmp_path: Path):
    r1 = data_profile.data_profile(str(tiny_csv), "Class", str(tmp_path / "a.md"))
    r2 = data_profile.data_profile(str(tiny_csv), "Class", str(tmp_path / "b.md"))
    assert r1 == r2
