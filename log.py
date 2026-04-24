"""log.py — results.tsv append + CAMPAIGN_STATE.json update.

Owned utility invoked by the runner driver after a Reviewer verdict. Kept
intentionally small per spec §2.4. Supports campaign-configurable results
columns via EVAL_PROTOCOL.results_columns; falls back to legacy schema when
that field is absent (preserves the abes_engine creditcard campaign schema).
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Literal

Verdict = Literal["keep", "discard", "anomaly", "crash", "malformed"]
Direction = Literal["maximize", "minimize"]

# Fixed structural columns that appear in every campaign's results.tsv.
_STRUCTURAL_PREFIX = ["commit"]
_STRUCTURAL_SUFFIX = ["status", "n_features", "model_family", "action_type", "hypothesis", "description"]

# Legacy metric columns (creditcard campaign and any campaign without results_columns).
_LEGACY_METRIC_COLUMNS = ["val_pr_auc", "lift_at_10", "macro_f1", "val_f1"]

# Kept for backward compatibility with anything that imported this name directly.
_RESULTS_HEADER = (
    "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
    "model_family\taction_type\thypothesis\tdescription\n"
)


def make_header(results_columns: list[str] | None) -> str:
    """Return the TSV header line for results.tsv.

    Args:
        results_columns: Campaign-specific metric column names from
            EVAL_PROTOCOL.results_columns.  ``None`` → legacy schema.
    """
    metric_cols = results_columns if results_columns is not None else _LEGACY_METRIC_COLUMNS
    return "\t".join(_STRUCTURAL_PREFIX + metric_cols + _STRUCTURAL_SUFFIX) + "\n"


def get_results_columns(campaign_dir: str) -> list[str] | None:
    """Read results_columns from EVAL_PROTOCOL frontmatter for *campaign_dir*.

    Returns the list when present and non-empty; ``None`` otherwise (→ legacy schema).
    Silently ignores any IO or parse error so campaigns without EVAL_PROTOCOL work.
    """
    try:
        from runner.tools._common import parse_frontmatter, FrontmatterError
        path = Path(campaign_dir) / "contracts" / "EVAL_PROTOCOL.md"
        fm, _ = parse_frontmatter(path)
        cols = fm.get("results_columns")
        return list(cols) if cols else None
    except Exception:
        return None


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
    The results.tsv schema is determined by EVAL_PROTOCOL.results_columns when
    present; otherwise the legacy creditcard schema is used.
    """
    camp = Path(campaign_dir)
    results_path = camp / "state" / "results.tsv"
    state_path = camp / "state" / "CAMPAIGN_STATE.json"

    results_columns = get_results_columns(campaign_dir)

    if not results_path.exists():
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(make_header(results_columns))

    def _clean(s: str) -> str:
        return str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")

    def _metric_val(col: str) -> str:
        v = metrics.get(col, 0.0)
        try:
            return str(float(v))
        except (TypeError, ValueError):
            return _clean(str(v))

    if results_columns is None:
        # Legacy fixed schema (creditcard campaign and any without results_columns).
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
    else:
        metric_cells = [_metric_val(col) for col in results_columns]
        row = "\t".join(
            [commit]
            + metric_cells
            + [status, str(int(n_features)), model_family, action_type,
               _clean(hypothesis), _clean(description)]
        ) + "\n"

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
