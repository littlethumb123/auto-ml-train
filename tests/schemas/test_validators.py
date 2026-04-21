"""Schema validation tests for all runner artifacts (spec §2.3 / §5.2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema

FIXTURES = Path(__file__).parent / "fixtures"


def test_problem_contract_good(tmp_path: Path):
    path = FIXTURES / "problem_contract_good.md"
    errors = schema.validate_problem_contract(path)
    assert errors == []


def test_problem_contract_missing_task_type(tmp_path: Path):
    src = (FIXTURES / "problem_contract_good.md").read_text()
    broken = "\n".join(line for line in src.splitlines() if not line.startswith("task_type:"))
    path = tmp_path / "pc.md"
    path.write_text(broken)
    errors = schema.validate_problem_contract(path)
    assert any("task_type" in e for e in errors)


def test_problem_contract_bad_task_type(tmp_path: Path):
    src = (FIXTURES / "problem_contract_good.md").read_text()
    broken = src.replace('task_type: "binary_classification"', 'task_type: "magic"')
    path = tmp_path / "pc.md"
    path.write_text(broken)
    errors = schema.validate_problem_contract(path)
    assert any("task_type" in e and "magic" in e for e in errors)


def test_problem_contract_missing_section(tmp_path: Path):
    src = (FIXTURES / "problem_contract_good.md").read_text()
    broken = src.replace("## 3. Success criteria (detail)", "## 3. Something else")
    path = tmp_path / "pc.md"
    path.write_text(broken)
    errors = schema.validate_problem_contract(path)
    assert any("section" in e.lower() and "3" in e for e in errors)


def test_next_experiment_good():
    errors = schema.validate_next_experiment(FIXTURES / "next_experiment_good.md")
    assert errors == []


def test_next_experiment_bad_action_type(tmp_path: Path):
    src = (FIXTURES / "next_experiment_good.md").read_text()
    broken = src.replace('action_type: "A_hp"', 'action_type: "A_nonsense"')
    path = tmp_path / "ne.md"
    path.write_text(broken)
    allowed = ["A_hp", "A_model", "A_feature"]
    errors = schema.validate_next_experiment(path, allowed_action_types=allowed)
    assert any("action_type" in e for e in errors)


def test_next_experiment_helpers_declared_mismatch(tmp_path: Path):
    src = (FIXTURES / "next_experiment_good.md").read_text()
    broken = src.replace(
        "touches_helpers: false",
        "touches_helpers: true",
    )
    path = tmp_path / "ne.md"
    path.write_text(broken)
    errors = schema.validate_next_experiment(path)
    assert any("helpers_declared" in e for e in errors)


def test_next_experiment_escalation_without_section(tmp_path: Path):
    src = (FIXTURES / "next_experiment_good.md").read_text()
    broken = src.replace("escalation: null", 'escalation: "C2"')
    path = tmp_path / "ne.md"
    path.write_text(broken)
    errors = schema.validate_next_experiment(path)
    assert any("§6" in e or "Escalation" in e for e in errors)


def test_eval_protocol_good():
    errors = schema.validate_eval_protocol(FIXTURES / "eval_protocol_good.md")
    assert errors == []


def test_eval_protocol_bad_direction(tmp_path: Path):
    src = (FIXTURES / "eval_protocol_good.md").read_text()
    broken = src.replace('direction: "maximize"', 'direction: "sideways"')
    path = tmp_path / "ep.md"
    path.write_text(broken)
    errors = schema.validate_eval_protocol(path)
    assert any("direction" in e for e in errors)


def test_campaign_state_good():
    errors = schema.validate_campaign_state(FIXTURES / "campaign_state_good.json")
    assert errors == []


def test_campaign_state_bad_round_type(tmp_path: Path):
    import json as j

    data = j.loads((FIXTURES / "campaign_state_good.json").read_text())
    data["round"] = "seven"
    path = tmp_path / "cs.json"
    path.write_text(j.dumps(data))
    errors = schema.validate_campaign_state(path)
    assert any("round" in e for e in errors)
