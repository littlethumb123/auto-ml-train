"""log.py — results.tsv append + CAMPAIGN_STATE.json update.

Owned utility invoked by the runner driver after a Reviewer verdict. Kept
intentionally small (~100 LOC with docstrings) per spec §2.4 — preserves
the legacy abes_engine results.tsv schema exactly.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Literal

Verdict = Literal["keep", "discard", "anomaly", "crash", "malformed"]
Direction = Literal["maximize", "minimize"]

_RESULTS_HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_better(candidate: float, incumbent: float | None, direction: Direction) -> bool:
    if incumbent is None:
        return True
    if direction == "maximize":
        return candidate > incumbent
    return candidate < incumbent


def append_result(
    commit: str,
    metrics: dict,
    status: Verdict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
    primary_metric_name: str = "val_pr_auc",
    direction: Direction = "maximize",
) -> None:
    """Append one row to `<campaign_dir>/state/results.tsv` and update
    `<campaign_dir>/state/CAMPAIGN_STATE.json`.

    Safe to call with metrics set to zeros when status == "crash" or "malformed".
    """
    camp = Path(campaign_dir)
    results_path = camp / "state" / "results.tsv"
    state_path = camp / "state" / "CAMPAIGN_STATE.json"

    if not results_path.exists():
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(_RESULTS_HEADER)

    def _clean(s: str) -> str:
        return str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")

    row = "\t".join([
        commit,
        f"{float(metrics.get('val_pr_auc', 0.0))}",
        f"{float(metrics.get('lift_at_10', 0.0))}",
        f"{float(metrics.get('macro_f1', 0.0))}",
        f"{float(metrics.get('val_f1', 0.0))}",
        status,
        str(int(n_features)),
        model_family,
        action_type,
        _clean(hypothesis),
        _clean(description),
    ]) + "\n"
    with results_path.open("a", encoding="utf-8") as fp:
        fp.write(row)

    state = json.loads(state_path.read_text())
    primary = float(metrics.get(primary_metric_name, 0.0))

    state["round"] = int(state.get("round", 0)) + 1
    state["exp_id_counter"] = int(state.get("exp_id_counter", 0)) + 1
    state["last_commit"] = commit
    state["last_verdict"] = status
    state["budget_used"] = int(state.get("budget_used", 0)) + 1
    state["updated_at"] = _now_iso()

    if status == "keep":
        state["consecutive_discards"] = 0
    elif status in ("discard", "crash", "malformed"):
        state["consecutive_discards"] = int(state.get("consecutive_discards", 0)) + 1

    if status == "keep":
        incumbent = (state.get("best_so_far") or {}).get("primary_metric")
        if _is_better(primary, incumbent, direction):
            state["best_so_far"] = {"commit": commit, "primary_metric": primary}

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
