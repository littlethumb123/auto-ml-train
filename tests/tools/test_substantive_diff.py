"""Tests for runner/tools/substantive_diff.py."""
from __future__ import annotations

import pytest
from runner.tools.substantive_diff import check_substantive, _count_substantive_lines


# ── Substantive line counting ─────────────────────────────────────────

class TestSubstantiveLineCounting:
    def test_real_code_change(self):
        diff = (
            "--- a/train.py\n"
            "+++ b/train.py\n"
            "@@ -10,3 +10,4 @@\n"
            "-model = LGBMClassifier(n_estimators=100)\n"
            "+model = LGBMClassifier(n_estimators=500, learning_rate=0.05)\n"
            "+model.fit(X_train, y_train)\n"
        )
        assert _count_substantive_lines(diff) == 3

    def test_comment_only_diff(self):
        diff = (
            "--- a/train.py\n"
            "+++ b/train.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-# old comment\n"
            "+# new comment\n"
        )
        assert _count_substantive_lines(diff) == 0

    def test_whitespace_only_diff(self):
        diff = (
            "--- a/train.py\n"
            "+++ b/train.py\n"
            "@@ -5,3 +5,3 @@\n"
            "-   \n"
            "+\n"
        )
        assert _count_substantive_lines(diff) == 0

    def test_mixed_diff(self):
        diff = (
            "--- a/train.py\n"
            "+++ b/train.py\n"
            "@@ -1,4 +1,5 @@\n"
            "-# old comment\n"
            "+# new comment\n"
            "-x = 1\n"
            "+x = 2\n"
            "+y = 3\n"
        )
        # 3 substantive lines: -x=1, +x=2, +y=3
        assert _count_substantive_lines(diff) == 3


# ── Full check_substantive ────────────────────────────────────────────

class TestCheckSubstantive:
    def test_substantive_diff_passes(self):
        diff = (
            "@@ -10,1 +10,1 @@\n"
            "-lr = 0.1\n"
            "+lr = 0.01\n"
        )
        result = check_substantive(diff)
        assert result["substantive"] is True
        assert result["substantive_lines"] == 2
        assert result["issues"] == []

    def test_empty_diff_fails(self):
        result = check_substantive("")
        assert result["substantive"] is False
        assert len(result["issues"]) == 1
        assert "no-op" in result["issues"][0].lower()

    def test_comment_only_diff_fails(self):
        diff = "-# old\n+# new\n"
        result = check_substantive(diff)
        assert result["substantive"] is False

    def test_helpers_wired_when_referenced(self):
        diff = "+from helpers import config\n"
        train_py = "from helpers import config\nx = config.load()\n"
        result = check_substantive(diff, train_py, ["experiment_helpers/e1/config.py"])
        assert result["helpers_wired"] is True
        assert result["unwired_helpers"] == []

    def test_helpers_unwired_detected(self):
        diff = "+x = 1\n"
        train_py = "x = 1\nmodel.fit(X, y)\n"
        result = check_substantive(diff, train_py, ["experiment_helpers/e1/lookup.csv"])
        assert result["helpers_wired"] is False
        assert "experiment_helpers/e1/lookup.csv" in result["unwired_helpers"]
        assert any("not referenced" in i for i in result["issues"])

    def test_no_helpers_declared_passes(self):
        diff = "+x = 1\n"
        result = check_substantive(diff, "x = 1\n", [])
        assert result["helpers_wired"] is True

    def test_helpers_without_train_py_skips(self):
        diff = "+x = 1\n"
        result = check_substantive(diff, None, ["experiment_helpers/e1/foo.py"])
        assert result["helpers_wired"] is True  # can't check without train_py


# ── CLI main ──────────────────────────────────────────────────────────

class TestMain:
    def test_main_substantive(self):
        from runner.tools.substantive_diff import main
        rc = main(["--diff-text", "+x = 1\n", "--json"])
        assert rc == 0

    def test_main_not_substantive(self):
        from runner.tools.substantive_diff import main
        rc = main(["--diff-text", "+# comment\n", "--json"])
        assert rc == 1
