"""Invariant: a plan that declares touches_helpers must list helpers_declared (schema enforces)."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema

pytestmark = pytest.mark.safety

PLAN_BAD = """---
schema_version: 1
campaign_id: "x"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "h"
expected_effect_size: 0.0
base_commit: "HEAD"
touches_helpers: true
helpers_declared: []
escalation: null
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
x
## 4. Helpers
x
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)
x
"""


def test_touches_helpers_without_declaration_is_rejected(tmp_path: Path):
    p = tmp_path / "ne.md"
    p.write_text(PLAN_BAD)
    errors = schema.validate_next_experiment(p)
    assert any("helpers_declared" in e for e in errors)
