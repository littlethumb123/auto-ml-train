"""Tests for runner.tools.token_summary."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import token_summary


@pytest.fixture
def camp(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    return root


def test_write_token_summary_no_results_file(camp: Path):
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    assert "no results yet" in result
    assert (camp / "state" / "TOKEN_SUMMARY.txt").exists()


def test_write_token_summary_no_token_columns(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        "commit\tval_pr_auc\tstatus\n"
        "abc\t0.8\tkeep\n"
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    assert "not enabled" in result
    assert (camp / "state" / "TOKEN_SUMMARY.txt").exists()


def _tsv_with_tokens(rows: list[tuple]) -> str:
    header = (
        "commit\tval_pr_auc\tstatus\tn_features\tmodel_family\taction_type\t"
        "hypothesis\tdescription\tplanner_tokens\texecutor_tokens\t"
        "reviewer_tokens\thistorian_tokens\tround_total_tokens\n"
    )
    lines = []
    for commit, val, status, action, pt, et, rt, ht in rows:
        total = pt + et + rt + ht
        lines.append(
            f"{commit}\t{val}\t{status}\t10\tlgbm\t{action}\th\td\t{pt}\t{et}\t{rt}\t{ht}\t{total}\n"
        )
    return header + "".join(lines)


def test_write_token_summary_computes_totals(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        _tsv_with_tokens([
            ("abc", 0.80, "keep", "A_hp", 100, 200, 150, 0),
            ("def", 0.81, "keep", "A_hp", 120, 180, 130, 0),
        ])
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    # Total = 450 + 430 = 880
    assert "880" in result or "880" in (camp / "state" / "TOKEN_SUMMARY.txt").read_text()
    assert "avg/round" in result
    assert (camp / "state" / "TOKEN_SUMMARY.txt").read_text().strip() == result.strip()


def test_write_token_summary_historian_avg_excludes_zero_rounds(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        _tsv_with_tokens([
            ("r1", 0.80, "keep", "A_hp", 100, 200, 150, 300),   # historian ran
            ("r2", 0.81, "keep", "A_hp", 100, 200, 150, 0),      # no historian
            ("r3", 0.82, "keep", "A_hp", 100, 200, 150, 600),    # historian ran
        ])
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    # historian avg = (300 + 600) // 2 = 450
    assert "historian avg" in result
    assert "450" in result


def test_write_token_summary_format(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        _tsv_with_tokens([("r1", 0.8, "keep", "A_hp", 1000, 2000, 1500, 0)])
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    assert "Campaign tokens" in result
    assert "total:" in result
    assert "avg/round:" in result
    assert "top cost:" in result
    assert "trend:" in result


def test_fmt_boundaries():
    from runner.tools.token_summary import _fmt
    assert _fmt(0) == "0"
    assert _fmt(999) == "999"
    assert _fmt(1000) == "1K"
    assert _fmt(999_499) == "999K"
    assert _fmt(999_500) == "1.0M"  # was previously "1000K" — fixed
    assert _fmt(1_000_000) == "1.0M"
