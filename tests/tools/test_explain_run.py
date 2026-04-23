from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import explain_run

HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)
ROW = "deadbeef\t0.80\t5.0\t0.8\t0.7\tkeep\t10\txgboost\tA_model\ttry xgb\tbaseline\n"


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    (root / "state" / "results.tsv").write_text(HEADER + ROW)
    return root


def test_explain_run_writes_card(campaign: Path):
    out = campaign / "state" / "run_card.md"
    path = explain_run.explain_run(commit="deadbeef", output_path=str(out), campaign_dir=str(campaign))
    assert Path(path).exists()
    text = Path(path).read_text()
    assert "deadbeef" in text
    assert "try xgb" in text
    assert "## Metrics" in text


def test_explain_run_missing_commit_raises(campaign: Path):
    with pytest.raises(LookupError):
        explain_run.explain_run(commit="nope", output_path=str(campaign / "state" / "x.md"), campaign_dir=str(campaign))
