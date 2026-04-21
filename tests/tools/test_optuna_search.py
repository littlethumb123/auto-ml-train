from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import optuna_search

OBJECTIVE_FILE = Path(__file__).parent / "fixtures" / "optuna_objective.py"


def test_optuna_search_finds_parabola_peak():
    res = optuna_search.optuna_search(
        objective_py_path=str(OBJECTIVE_FILE),
        n_trials=30,
        timeout_s=10,
        direction="maximize",
        seed=42,
    )
    assert res["n_completed"] >= 1
    assert abs(res["best_params"]["x"] - 0.5) < 0.2
    assert res["best_value"] < 0


def test_optuna_search_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        optuna_search.optuna_search(
            objective_py_path=str(tmp_path / "nope.py"),
            n_trials=5,
            timeout_s=5,
        )
