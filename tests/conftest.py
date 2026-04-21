"""Shared pytest fixtures for the runner test suite."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_campaign_dir(tmp_path: Path) -> Path:
    """A temporary `runner/` workspace with the directory tree created and
    empty placeholder artifacts. Does NOT create valid contracts; individual
    tests populate what they need."""
    root = tmp_path / "runner"
    for sub in ("contracts", "state", "tools", "roles", "experiment_helpers"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    header = (
        "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
        "model_family\taction_type\thypothesis\tdescription\n"
    )
    (root / "state" / "results.tsv").write_text(header)
    return root


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """A temporary initialized git repo with an initial commit. Used by
    driver tests that exercise `git reset --hard HEAD~1`."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path
