from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import dead_ends_query

DEAD_ENDS = """---
schema_version: 1
campaign_id: "tiny-binary-test"
count: 3
last_updated: "2026-04-21"
---

# Dead ends — do NOT retry

- SMOTE + scale_pos_weight — double-counts imbalance (mar30)
- QuantileTransformer on tree models — monotonic transform can't change splits (mar30)
- LightGBM is_unbalance=True — inverts probabilities (mar30+apr01)
"""


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "DEAD_ENDS.md").write_text(DEAD_ENDS)
    return root


def test_dead_ends_query_all(campaign: Path):
    items = dead_ends_query.dead_ends_query(campaign_dir=str(campaign))
    assert len(items) == 3
    assert any("SMOTE" in item for item in items)


def test_dead_ends_query_substring(campaign: Path):
    items = dead_ends_query.dead_ends_query(pattern="SMOTE", campaign_dir=str(campaign))
    assert len(items) == 1
    assert "SMOTE" in items[0]


def test_dead_ends_query_regex(campaign: Path):
    items = dead_ends_query.dead_ends_query(pattern=r"LightGBM|Quantile", campaign_dir=str(campaign))
    assert len(items) == 2


def test_dead_ends_query_missing_file(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    items = dead_ends_query.dead_ends_query(campaign_dir=str(root))
    assert items == []
