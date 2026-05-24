"""Tests for runner.strategy.tree_search — experiment tree + UCB1 scoring."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from runner.strategy.tree_search import (
    ExperimentTree,
    STRATEGY_CLASSES,
)


class TestExperimentTree:
    def test_init_creates_root(self):
        tree = ExperimentTree()
        assert tree.root is not None
        assert tree.root["commit"] == "ROOT"
        assert tree.root["children"] == []

    def test_add_experiment_to_root(self):
        tree = ExperimentTree()
        tree.add_experiment(
            commit="abc123",
            parent_commit="ROOT",
            strategy_class="A_model",
            metric_value=0.82,
            verdict="keep",
        )
        assert len(tree.root["children"]) == 1
        child = tree.get_node("abc123")
        assert child is not None
        assert child["strategy_class"] == "A_model"
        assert child["metric_value"] == 0.82

    def test_add_experiment_to_non_root_parent(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        node_b = tree.get_node("b")
        assert node_b is not None
        assert node_b["parent_commit"] == "a"

    def test_branching_from_same_parent(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "a", "A_feature", 0.83, "keep")
        node_a = tree.get_node("a")
        assert len(node_a["children"]) == 2

    def test_get_strategy_class_stats(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.845, "keep")
        tree.add_experiment("d", "c", "A_feature", 0.83, "discard")
        stats = tree.get_strategy_stats()
        assert stats["A_model"]["n_attempts"] == 1
        assert stats["A_hp"]["n_attempts"] == 2
        assert stats["A_feature"]["n_attempts"] == 1

    def test_compute_ucb1_scores(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.841, "keep")
        scores = tree.compute_ucb1(exploration_constant=1.0)
        # A_model tried 1x, A_hp tried 2x
        # Untried classes should have highest score (infinity)
        for cls in STRATEGY_CLASSES:
            assert cls in scores
        # A_feature never tried → score should be inf
        assert scores["A_feature"] == float("inf")
        # A_hp tried 2x → finite score
        assert math.isfinite(scores["A_hp"])

    def test_ucb1_untried_classes_are_infinite(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        scores = tree.compute_ucb1()
        untried = [c for c in STRATEGY_CLASSES if c != "A_model"]
        for cls in untried:
            assert scores[cls] == float("inf"), f"{cls} should be inf (untried)"

    def test_diminishing_returns_flag(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_hp", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.821, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.8215, "discard")
        dr = tree.detect_diminishing_returns(epsilon=0.005)
        assert "A_hp" in dr

    def test_no_diminishing_returns_when_improving(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_hp", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.86, "keep")
        dr = tree.detect_diminishing_returns(epsilon=0.005)
        assert "A_hp" not in dr

    def test_get_best_branch_point(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        tree.add_experiment("c", "b", "A_hp", 0.841, "discard")
        # Best branch point should be 'b' (highest metric with keep verdict)
        best = tree.get_best_branch_point()
        assert best == "b"

    def test_get_phase(self):
        tree = ExperimentTree()
        assert tree.get_phase(budget_total=20, budget_used=0) == "diversify"
        assert tree.get_phase(budget_total=20, budget_used=5) == "diversify"
        assert tree.get_phase(budget_total=20, budget_used=7) == "deepen"
        assert tree.get_phase(budget_total=20, budget_used=15) == "exploit"

    def test_serialize_deserialize(self, tmp_path):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")

        path = tmp_path / "tree.json"
        tree.save(path)
        assert path.exists()

        loaded = ExperimentTree.load(path)
        assert loaded.get_node("a") is not None
        assert loaded.get_node("b") is not None
        assert loaded.get_node("b")["parent_commit"] == "a"

    def test_get_planner_context(self):
        tree = ExperimentTree()
        tree.add_experiment("a", "ROOT", "A_model", 0.82, "keep")
        tree.add_experiment("b", "a", "A_hp", 0.84, "keep")
        ctx = tree.get_planner_context(budget_total=20, budget_used=2, noise_floor=0.005)
        assert "phase" in ctx
        assert "ucb1_scores" in ctx
        assert "diminishing_returns" in ctx
        assert "best_branch_point" in ctx
        assert "strategy_stats" in ctx
