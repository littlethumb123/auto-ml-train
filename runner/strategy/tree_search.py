"""Experiment tree with UCB1 exploration/exploitation scoring.

Maintains a tree of experiments where each node tracks:
- Which experiment (commit) it represents
- Its parent (which state it branched from)
- Its strategy class (A_model, A_hp, A_feature, etc.)
- Its metric value and verdict

The tree supports:
- UCB1 scoring per strategy class (guides Planner's next choice)
- Diminishing returns detection (prune exhausted directions)
- Phase detection (diversify → deepen → exploit)
- Best branch point identification (where to branch from for new directions)
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

STRATEGY_CLASSES = [
    "A_model",
    "A_feature",
    "A_hp",
    "A_imbalance",
    "A_ensemble",
    "A_validate",
    "A_error_analysis",
]

# Phase thresholds as fraction of total budget
_DIVERSIFY_END = 0.30
_DEEPEN_END = 0.70


def _make_node(
    commit: str,
    parent_commit: str | None,
    strategy_class: str | None = None,
    metric_value: float | None = None,
    verdict: str | None = None,
) -> dict:
    return {
        "commit": commit,
        "parent_commit": parent_commit,
        "strategy_class": strategy_class,
        "metric_value": metric_value,
        "verdict": verdict,
        "children": [],
    }


class ExperimentTree:
    """Tree of experiments with UCB1-guided strategy selection."""

    def __init__(self):
        self.root = _make_node(commit="ROOT", parent_commit=None)
        self._index: dict[str, dict] = {"ROOT": self.root}

    def add_experiment(
        self,
        commit: str,
        parent_commit: str,
        strategy_class: str,
        metric_value: float | None,
        verdict: str,
    ) -> None:
        """Add a new experiment node to the tree."""
        node = _make_node(
            commit=commit,
            parent_commit=parent_commit,
            strategy_class=strategy_class,
            metric_value=metric_value,
            verdict=verdict,
        )
        self._index[commit] = node

        parent = self._index.get(parent_commit)
        if parent is not None:
            parent["children"].append(commit)

    def get_node(self, commit: str) -> dict | None:
        return self._index.get(commit)

    def get_all_experiments(self) -> list[dict]:
        """Return all non-ROOT nodes."""
        return [n for c, n in self._index.items() if c != "ROOT"]

    def get_strategy_stats(self) -> dict[str, dict]:
        """Compute per-strategy-class statistics.

        Returns dict of {strategy_class: {n_attempts, n_keeps, deltas, mean_delta}}.
        """
        stats: dict[str, dict] = {}
        for cls in STRATEGY_CLASSES:
            stats[cls] = {"n_attempts": 0, "n_keeps": 0, "deltas": []}

        experiments = self.get_all_experiments()
        for exp in experiments:
            cls = exp.get("strategy_class")
            if cls not in stats:
                stats[cls] = {"n_attempts": 0, "n_keeps": 0, "deltas": []}

            stats[cls]["n_attempts"] += 1
            if exp.get("verdict") == "keep":
                stats[cls]["n_keeps"] += 1

            # Compute delta from parent
            parent = self._index.get(exp.get("parent_commit", ""))
            if (
                parent is not None
                and parent.get("metric_value") is not None
                and exp.get("metric_value") is not None
            ):
                delta = exp["metric_value"] - parent["metric_value"]
                stats[cls]["deltas"].append(delta)

        for cls in stats:
            deltas = stats[cls]["deltas"]
            stats[cls]["mean_delta"] = float(sum(deltas) / len(deltas)) if deltas else 0.0

        return stats

    def compute_ucb1(self, exploration_constant: float = 1.414) -> dict[str, float]:
        """Compute UCB1 score for each strategy class.

        UCB1_i = mean_delta_i + c * sqrt(ln(N) / n_i)

        Untried classes get score = inf (must be tried first).
        """
        stats = self.get_strategy_stats()
        total_n = sum(s["n_attempts"] for s in stats.values())

        scores: dict[str, float] = {}
        for cls in STRATEGY_CLASSES:
            s = stats.get(cls, {"n_attempts": 0, "mean_delta": 0.0})
            n_i = s["n_attempts"]
            if n_i == 0:
                scores[cls] = float("inf")
            elif total_n == 0:
                scores[cls] = float("inf")
            else:
                mean_d = s["mean_delta"]
                exploration_bonus = exploration_constant * math.sqrt(
                    math.log(total_n) / n_i
                )
                scores[cls] = mean_d + exploration_bonus

        return scores

    def detect_diminishing_returns(self, epsilon: float = 0.005) -> list[str]:
        """Return strategy classes where the last 2+ experiments all improved by < epsilon.

        These classes are candidates for pruning (stop deepening this branch).
        """
        stats = self.get_strategy_stats()
        flagged = []
        for cls, s in stats.items():
            deltas = s["deltas"]
            if len(deltas) >= 2 and all(abs(d) < epsilon for d in deltas[-2:]):
                flagged.append(cls)
        return flagged

    def get_best_branch_point(self) -> str:
        """Return the commit of the experiment with the highest metric among keeps.

        This is where the agent should branch from to try a new direction.
        """
        best_commit = "ROOT"
        best_metric = float("-inf")
        for exp in self.get_all_experiments():
            if exp.get("verdict") == "keep" and exp.get("metric_value") is not None:
                if exp["metric_value"] > best_metric:
                    best_metric = exp["metric_value"]
                    best_commit = exp["commit"]
        return best_commit

    def get_phase(self, budget_total: int, budget_used: int) -> str:
        """Determine current exploration/exploitation phase.

        Returns one of: "diversify", "deepen", "exploit".
        """
        if budget_total <= 0:
            return "exploit"
        frac = budget_used / budget_total
        if frac <= _DIVERSIFY_END:
            return "diversify"
        elif frac <= _DEEPEN_END:
            return "deepen"
        else:
            return "exploit"

    def get_planner_context(
        self,
        budget_total: int,
        budget_used: int,
        noise_floor: float = 0.005,
    ) -> dict[str, Any]:
        """Generate the full context block that gets injected into the Planner prompt.

        Returns a dict with all the information the Planner needs for strategy selection.
        """
        phase = self.get_phase(budget_total, budget_used)
        ucb1 = self.compute_ucb1()
        dr = self.detect_diminishing_returns(epsilon=noise_floor)
        best_bp = self.get_best_branch_point()
        stats = self.get_strategy_stats()

        # Penalize diminishing-returns classes
        for cls in dr:
            if cls in ucb1 and math.isfinite(ucb1[cls]):
                ucb1[cls] *= 0.5  # Halve score for exhausted classes

        # Sort by UCB1 score descending
        ranked = sorted(ucb1.items(), key=lambda x: x[1], reverse=True)

        return {
            "phase": phase,
            "phase_description": {
                "diversify": "MANDATORY DIVERSIFICATION: Try at least one experiment from each untried strategy class before deepening any.",
                "deepen": "UCB1-GUIDED DEEPENING: Select the strategy class with the highest UCB1 score. Refine promising directions.",
                "exploit": "EXPLOITATION: Ensemble, stack, final HP tune. Reserve 1-2 experiments for a moonshot.",
            }[phase],
            "ucb1_scores": {cls: round(s, 4) if math.isfinite(s) else "inf (must try)" for cls, s in ranked},
            "diminishing_returns": dr,
            "best_branch_point": best_bp,
            "strategy_stats": {
                cls: {
                    "n_attempts": s["n_attempts"],
                    "n_keeps": s["n_keeps"],
                    "mean_delta": round(s["mean_delta"], 6),
                }
                for cls, s in stats.items()
                if s["n_attempts"] > 0
            },
            "budget_remaining": budget_total - budget_used,
            "budget_fraction_used": round(budget_used / max(budget_total, 1), 2),
        }

    def save(self, path: Path) -> None:
        """Serialize tree to JSON file."""
        data = {
            "schema_version": 1,
            "nodes": {commit: node for commit, node in self._index.items()},
        }
        path.write_text(json.dumps(data, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> ExperimentTree:
        """Deserialize tree from JSON file."""
        data = json.loads(path.read_text())
        tree = cls.__new__(cls)
        tree._index = {}

        nodes = data.get("nodes", {})
        for commit, node_data in nodes.items():
            tree._index[commit] = node_data

        tree.root = tree._index.get("ROOT", _make_node("ROOT", None))
        return tree

    @classmethod
    def rebuild_from_results(
        cls,
        results_tsv_path: Path,
        primary_metric: str,
        direction: str = "maximize",
    ) -> tuple[ExperimentTree, bool]:
        """Reconstruct an ExperimentTree from a TSV history (F5).

        Walks results.tsv in row order, parenting each row to the running-best
        commit at the time it appeared. Used to restore UCB1 history after a
        tree wipe or fresh init on top of existing results.

        Args:
            results_tsv_path: Path to state/results.tsv.
            primary_metric: Column name of the primary metric (from EVAL_PROTOCOL).
            direction: "maximize" or "minimize".

        Returns:
            (tree, degraded) — degraded=True if action_type column was missing
            from the TSV header (older schemas) and every node was assigned
            strategy_class="unknown".
        """
        tree = cls()
        degraded = False
        if not results_tsv_path.exists():
            return tree, degraded

        text = results_tsv_path.read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return tree, degraded

        header = lines[0].split("\t")
        try:
            commit_idx = header.index("commit")
        except ValueError:
            return tree, degraded

        status_idx = header.index("status") if "status" in header else None
        action_idx = header.index("action_type") if "action_type" in header else None
        metric_idx = header.index(primary_metric) if primary_metric in header else None
        if action_idx is None:
            degraded = True

        running_best_commit: str = "ROOT"
        running_best_metric: float = float("-inf") if direction == "maximize" else float("inf")

        def _improves(new_val: float) -> bool:
            if direction == "maximize":
                return new_val > running_best_metric
            return new_val < running_best_metric

        for raw in lines[1:]:
            cols = raw.split("\t")
            if len(cols) <= commit_idx:
                continue
            commit = cols[commit_idx].strip()
            if not commit:
                continue

            verdict = cols[status_idx].strip() if status_idx is not None and len(cols) > status_idx else ""
            strategy_class = (
                cols[action_idx].strip()
                if action_idx is not None and len(cols) > action_idx
                else "unknown"
            )
            if not strategy_class:
                strategy_class = "unknown"

            metric_value: float | None = None
            if metric_idx is not None and len(cols) > metric_idx:
                try:
                    metric_value = float(cols[metric_idx])
                except (ValueError, TypeError):
                    metric_value = None

            tree.add_experiment(
                commit=commit,
                parent_commit=running_best_commit,
                strategy_class=strategy_class,
                metric_value=metric_value,
                verdict=verdict,
            )

            if verdict == "keep" and metric_value is not None and _improves(metric_value):
                running_best_metric = metric_value
                running_best_commit = commit

        return tree, degraded
