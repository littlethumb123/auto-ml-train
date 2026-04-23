from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import results_query

HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)
ROWS = [
    "a1\t0.80\t5.0\t0.8\t0.7\tkeep\t10\txgboost\tA_model\thyp\tdesc\n",
    "b2\t0.50\t2.0\t0.4\t0.3\tdiscard\t10\tlightgbm\tA_hp\thyp\tdesc\n",
    "c3\t0.00\t0.0\t0.0\t0.0\tcrash\t10\tlightgbm\tA_hp\thyp\tdesc\n",
    "d4\t0.85\t6.0\t0.85\t0.8\tkeep\t12\txgboost\tA_feature\thyp\tdesc\n",
]


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text(HEADER + "".join(ROWS))
    return root


def test_results_query_top_k_desc(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign), order_by="val_pr_auc", limit=2,
    )
    assert [r["commit"] for r in rows] == ["d4", "a1"]


def test_results_query_filter_excludes_crash(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign),
        filter_expr="status != 'crash'",
        limit=10,
    )
    assert "c3" not in [r["commit"] for r in rows]


def test_results_query_filter_by_family(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign),
        filter_expr="model_family == 'xgboost'",
        limit=5,
    )
    assert sorted(r["commit"] for r in rows) == ["a1", "d4"]


def test_results_query_returns_empty_on_no_match(campaign: Path):
    rows = results_query.results_query(
        campaign_dir=str(campaign),
        filter_expr="model_family == 'catboost'",
    )
    assert rows == []


def test_results_query_schema_mismatch_raises(tmp_path: Path):
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text("wrong\theader\n")
    with pytest.raises(results_query.SchemaMismatchError):
        results_query.results_query(campaign_dir=str(root))
