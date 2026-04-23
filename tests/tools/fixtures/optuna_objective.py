"""Tiny Optuna objective for tests — parabola with known optimum at x=0.5."""
import optuna


def objective(trial: optuna.trial.Trial) -> float:
    x = trial.suggest_float("x", 0.0, 1.0)
    return -((x - 0.5) ** 2)
