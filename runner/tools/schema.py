"""Schema validators for all runner artifacts.

Each validator returns a list of error strings. Empty list means valid.
The error messages are human-readable and include the field or section name
so the Reviewer / driver can surface them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runner.tools._common import FrontmatterError, parse_frontmatter

_ALLOWED_TASK_TYPES = {
    "binary_classification",
    "multiclass_classification",
    "regression",
    "clustering",
    "anomaly_detection",
}

_H2_NUMBERED = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)


def _required_keys(d: dict, keys: list[str], prefix: str = "") -> list[str]:
    errors = []
    for k in keys:
        if k not in d or d[k] is None:
            errors.append(f"missing required frontmatter field: {prefix}{k}")
    return errors


def _check_numbered_sections(body: str, expected: list[tuple[int, str]]) -> list[str]:
    found = {int(m.group(1)): m.group(2).strip() for m in _H2_NUMBERED.finditer(body)}
    errors = []
    for num, title_prefix in expected:
        if num not in found:
            errors.append(f"missing required section: ## {num}.")
            continue
        title = found[num].lower()
        if not title.startswith(title_prefix.lower()):
            errors.append(
                f"section ## {num}. has wrong title: expected prefix '{title_prefix}', "
                f"found '{found[num]}'"
            )
    return errors


_PC_REQUIRED = [
    "schema_version",
    "campaign_id",
    "problem_title",
    "task_type",
    "unit_of_observation",
    "target",
    "success_criteria",
    "constraints",
    "non_goals",
]
_PC_SECTIONS = [
    (1, "Task"),
    (2, "Why"),
    (3, "Success"),
    (4, "Constraints"),
    (5, "Non-goals"),
]


def validate_problem_contract(path: Path) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _PC_REQUIRED)
    if fm.get("task_type") is not None and fm["task_type"] not in _ALLOWED_TASK_TYPES:
        errors.append(f"task_type {fm['task_type']!r} not in {sorted(_ALLOWED_TASK_TYPES)}")
    tgt = fm.get("target") or {}
    if isinstance(tgt, dict):
        for k in ("name", "definition"):
            if k not in tgt or tgt[k] is None:
                errors.append(f"missing required frontmatter field: target.{k}")
    errors += _check_numbered_sections(body, _PC_SECTIONS)
    return errors


_DC_REQUIRED = [
    "schema_version",
    "campaign_id",
    "data_sources",
    "temporal",
    "columns",
    "leakage_audit",
    "splits",
]
_DC_SECTIONS = [
    (1, "Schema"),
    (2, "Availability"),
    (3, "Leakage"),
    (4, "Transformations"),
    (5, "Known"),
]


def validate_data_contract(path: Path) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _DC_REQUIRED)
    la = fm.get("leakage_audit") or {}
    if isinstance(la, dict) and la.get("performed_at") in (None, ""):
        errors.append("leakage_audit.performed_at must be set before G2 sign-off")
    errors += _check_numbered_sections(body, _DC_SECTIONS)
    return errors


_EP_REQUIRED = [
    "schema_version",
    "campaign_id",
    "primary_metric",
    "acceptance_threshold",
    "cv_scheme",
    "bootstrap_ci",
    "paired_test",
    "mandatory_tools",
    "action_types",
    "budgets",
    "plateau_trigger",
    "anomaly",
]
_EP_SECTIONS = [
    (1, "Rationale"),
    (2, "How keep/discard"),
    (3, "How plateau"),
    (4, "Contract change"),
]
_ALLOWED_DIRECTIONS = {"maximize", "minimize"}


def validate_eval_protocol(path: Path) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _EP_REQUIRED)
    pm = fm.get("primary_metric") or {}
    if isinstance(pm, dict):
        if pm.get("direction") not in _ALLOWED_DIRECTIONS:
            errors.append(
                f"primary_metric.direction must be one of {sorted(_ALLOWED_DIRECTIONS)}"
            )
        if "name" not in pm:
            errors.append("missing required frontmatter field: primary_metric.name")
    budgets = fm.get("budgets") or {}
    if isinstance(budgets, dict):
        mra = budgets.get("max_repair_attempts")
        if mra is not None and (not isinstance(mra, int) or mra != 2):
            errors.append("budgets.max_repair_attempts is a hard invariant (must be 2)")
    errors += _check_numbered_sections(body, _EP_SECTIONS)
    return errors


_NE_REQUIRED = [
    "schema_version",
    "campaign_id",
    "round",
    "planner_invocation_at",
    "action_type",
    "hypothesis",
    "expected_effect_size",
    "base_commit",
    "touches_helpers",
    "helpers_declared",
    "escalation",
]
_NE_SECTIONS = [
    (1, "Context"),
    (2, "Evidence"),
    (3, "Plan"),
    (4, "Helpers"),
    (5, "How this differs"),
    (6, "Escalation"),
]
_ALLOWED_ESCALATIONS = {None, "C2", "C3"}


def validate_next_experiment(
    path: Path,
    allowed_action_types: list[str] | None = None,
) -> list[str]:
    try:
        fm, body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors: list[str] = []
    for k in _NE_REQUIRED:
        if k not in fm:
            errors.append(f"missing required frontmatter field: {k}")
    if allowed_action_types is not None and fm.get("action_type") not in allowed_action_types:
        errors.append(
            f"action_type {fm.get('action_type')!r} not in allowed {allowed_action_types}"
        )
    if fm.get("touches_helpers") is True and not (fm.get("helpers_declared") or []):
        errors.append("touches_helpers=true but helpers_declared is empty")
    esc = fm.get("escalation")
    if esc not in _ALLOWED_ESCALATIONS:
        errors.append(f"escalation must be null|'C2'|'C3', got {esc!r}")
    errors += _check_numbered_sections(body, _NE_SECTIONS)
    if esc in {"C2", "C3"}:
        if "### For " not in body:
            errors.append(
                f"escalation={esc} set but §6 lacks '### For C2' or '### For C3' subsection"
            )
    return errors


_CS_REQUIRED_KEYS = [
    "$schema_version",
    "campaign_id",
    "round",
    "exp_id_counter",
    "last_commit",
    "last_verdict",
    "best_so_far",
    "consecutive_discards",
    "budget_used",
    "budget_total",
    "created_at",
    "updated_at",
]


def validate_campaign_state(path: Path) -> list[str]:
    try:
        data = json.loads(Path(path).read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return [f"cannot read campaign_state: {exc}"]
    errors: list[str] = []
    for k in _CS_REQUIRED_KEYS:
        if k not in data:
            errors.append(f"missing required key: {k}")
    for k in ("round", "exp_id_counter", "consecutive_discards", "budget_used", "budget_total"):
        if k in data and not isinstance(data[k], int):
            errors.append(f"{k} must be int, got {type(data[k]).__name__}")
    return errors


_REVIEW_REQUIRED = ["schema_version", "campaign_id", "last_round", "last_verdict"]
_ALLOWED_VERDICTS = {"keep", "discard", "anomaly", "crash", "malformed"}


def validate_review(path: Path) -> list[str]:
    try:
        fm, _body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _REVIEW_REQUIRED)
    if fm.get("last_verdict") not in _ALLOWED_VERDICTS and fm.get("last_verdict") is not None:
        errors.append(
            f"last_verdict {fm.get('last_verdict')!r} not in {sorted(_ALLOWED_VERDICTS)}"
        )
    return errors
