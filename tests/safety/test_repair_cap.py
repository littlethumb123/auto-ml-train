"""Invariant: EVAL_PROTOCOL.budgets.max_repair_attempts must be exactly 2 (hard invariant)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema
from tests.test_runner_driver import EVAL_PROTOCOL

pytestmark = pytest.mark.safety


def test_schema_rejects_non_two_repair_cap(tmp_path: Path):
    src = EVAL_PROTOCOL.replace("max_repair_attempts: 2", "max_repair_attempts: 5")
    p = tmp_path / "EP.md"
    p.write_text(src)
    errors = schema.validate_eval_protocol(p)
    assert any("max_repair_attempts" in e for e in errors)


def test_schema_accepts_two_repair_cap(tmp_path: Path):
    p = tmp_path / "EP.md"
    p.write_text(EVAL_PROTOCOL)
    errors = schema.validate_eval_protocol(p)
    assert not any("max_repair_attempts" in e for e in errors)
