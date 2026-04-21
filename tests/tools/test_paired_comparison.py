from __future__ import annotations

import pytest

from runner.tools import paired_comparison


def test_paired_comparison_a_better_wilcoxon():
    a = [0.85, 0.84, 0.86, 0.83, 0.87]
    b = [0.80, 0.79, 0.81, 0.78, 0.82]
    res = paired_comparison.paired_comparison(a, b, test="wilcoxon")
    assert res["direction"] == "a>b"
    assert res["p_value"] < 0.1


def test_paired_comparison_tie():
    a = [0.80, 0.81, 0.79]
    b = [0.80, 0.81, 0.79]
    res = paired_comparison.paired_comparison(a, b, test="wilcoxon")
    assert res["direction"] == "tie"


def test_paired_comparison_unknown_test_raises():
    with pytest.raises(ValueError):
        paired_comparison.paired_comparison([1.0, 2.0], [0.5, 1.5], test="magic")
