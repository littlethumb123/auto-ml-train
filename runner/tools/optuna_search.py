"""Optuna search wrapper (spec §2.2.2)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import optuna


def _load_objective(py_path: str):
    path = Path(py_path)
    if not path.exists():
        raise FileNotFoundError(f"objective file not found: {py_path}")
    spec = importlib.util.spec_from_file_location("runner_objective", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if not hasattr(module, "objective"):
        raise ValueError(f"{py_path} does not define `objective(trial)`")
    return module.objective


def optuna_search(
    objective_py_path: str,
    n_trials: int,
    timeout_s: int,
    direction: str = "maximize",
    study_name: str | None = None,
    seed: int = 13,
) -> dict[str, Any]:
    objective = _load_objective(objective_py_path)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction=direction, sampler=sampler, study_name=study_name)
    study.optimize(objective, n_trials=n_trials, timeout=timeout_s)
    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    pruned = [t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]
    return {
        "best_params": dict(study.best_params) if completed else {},
        "best_value": float(study.best_value) if completed else float("nan"),
        "n_completed": len(completed),
        "pruned": len(pruned),
    }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--objective", required=True)
    p.add_argument("--n-trials", type=int, default=30)
    p.add_argument("--timeout", type=int, default=10)
    args = p.parse_args()
    print(optuna_search(args.objective, args.n_trials, args.timeout))
