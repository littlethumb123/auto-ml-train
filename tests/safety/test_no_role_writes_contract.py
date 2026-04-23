"""Invariant: no role is allowed to mutate runner/contracts/*.md (spec §1 Executor write scope)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety


def test_driver_never_writes_contracts(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    for name, text in (
        ("PROBLEM_CONTRACT.md", PROBLEM_CONTRACT),
        ("DATA_CONTRACT.md", DATA_CONTRACT),
        ("EVAL_PROTOCOL.md", EVAL_PROTOCOL),
    ):
        (root / "contracts" / name).write_text(text)

    orig_mtimes = {p.name: p.stat().st_mtime_ns for p in (root / "contracts").iterdir()}

    runner_driver.init_campaign(campaign_dir=str(root))
    runner_driver.review_finalize(
        verdict="keep", commit="c1",
        metrics={"val_pr_auc": 0.7, "lift_at_10": 4.0, "macro_f1": 0.7, "val_f1": 0.6},
        action_type="A_hp", hypothesis="h", description="d",
        model_family="lightgbm", n_features=10,
        campaign_dir=str(root),
    )

    for p in (root / "contracts").iterdir():
        assert p.stat().st_mtime_ns == orig_mtimes[p.name], f"{p} was mutated by driver"
