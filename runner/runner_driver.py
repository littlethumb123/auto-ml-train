"""Runner driver (spec §3.2) — state machine for the autonomous loop.

Split into four stages, each invoked by `runner/run_round.sh <stage>`:

  1. init              — bootstrap CAMPAIGN_STATE.json from approved contracts
  2. plan-check        — validate NEXT_EXPERIMENT.md and branch on escalation
  3. execute-finalize  — parse Executor stdout into a {channel, synthetic_verdict}
  4. review-finalize   — apply verdict: update state, decide rollback/pause/halt

The driver is intentionally stateless between stages. State lives in
runner/state/CAMPAIGN_STATE.json and on disk in the other artifacts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

import log
from runner.tools import schema
from runner.tools._common import FrontmatterError, parse_frontmatter

Channel = Literal["RUN_COMPLETE", "RUN_FAILED", "REVIEW_REQUIRED"]
Verdict = Literal["keep", "discard", "anomaly", "crash", "malformed"]


class GateError(Exception):
    """Raised when G1/G2/G3 are not signed at init."""


class DriverError(Exception):
    """Raised on structural driver failures (missing state, schema drift)."""


_STDOUT_RE = re.compile(
    r"^(?P<channel>RUN_COMPLETE|RUN_FAILED|REVIEW_REQUIRED):\s*(?P<rest>.*)$",
    re.MULTILINE,
)


def init_campaign(campaign_dir: str = "runner/") -> dict[str, Any]:
    camp = Path(campaign_dir)
    contracts = {
        "PROBLEM_CONTRACT.md": schema.validate_problem_contract,
        "DATA_CONTRACT.md": schema.validate_data_contract,
        "EVAL_PROTOCOL.md": schema.validate_eval_protocol,
    }
    for fname, validator in contracts.items():
        path = camp / "contracts" / fname
        if not path.exists():
            raise GateError(f"{fname} is missing (G1/G2/G3 unsigned)")
        errors = validator(path)
        if errors:
            raise GateError(f"{fname} schema errors: {errors}")
        fm, _ = parse_frontmatter(path)
        if fm.get("approved_at") in (None, ""):
            raise GateError(f"{fname}.approved_at is null — human sign-off missing")

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    budgets = eval_fm.get("budgets") or {}
    problem_fm, _ = parse_frontmatter(camp / "contracts" / "PROBLEM_CONTRACT.md")

    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = {
        "$schema_version": 1,
        "campaign_id": problem_fm.get("campaign_id"),
        "round": 0,
        "exp_id_counter": 0,
        "last_commit": None,
        "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0,
        "budget_used": 0,
        "budget_total": int(budgets.get("max_experiments", 100)),
        "created_at": now,
        "updated_at": now,
    }
    state_dir = camp / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "CAMPAIGN_STATE.json").write_text(json.dumps(state, indent=2) + "\n")

    results = state_dir / "results.tsv"
    if not results.exists():
        results.write_text(
            "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
            "model_family\taction_type\thypothesis\tdescription\n"
        )
    return state


def plan_check(campaign_dir: str = "runner/") -> dict[str, Any]:
    camp = Path(campaign_dir)
    plan_path = camp / "state" / "NEXT_EXPERIMENT.md"
    if not plan_path.exists():
        return {"status": "missing", "errors": ["NEXT_EXPERIMENT.md not found"]}

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    allowed = list(eval_fm.get("action_types") or [])
    errors = schema.validate_next_experiment(plan_path, allowed_action_types=allowed)

    state = json.loads((camp / "state" / "CAMPAIGN_STATE.json").read_text())
    trigger = int((eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3))
    try:
        fm, _ = parse_frontmatter(plan_path)
        escalation = fm.get("escalation")
    except FrontmatterError:
        escalation = None
    if state.get("consecutive_discards", 0) >= trigger and escalation != "C2":
        errors.append(
            f"consecutive_discards={state['consecutive_discards']} >= trigger={trigger} "
            f"but escalation!=C2 (required per spec §8.3 item 5)"
        )

    if errors:
        return {"status": "malformed", "errors": errors}
    if escalation == "C2":
        return {"status": "pause_c2", "errors": []}
    if escalation == "C3":
        return {"status": "pause_c3", "errors": []}
    return {"status": "ok", "errors": []}


def resolve_c2(
    resolution: str,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    """Acknowledge a C2 plateau pause and reset consecutive_discards.

    Called after the human/agent reviews the C2 escalation, decides
    a new direction, and wants to resume normal planning.

    Args:
        resolution: Free-text description of the decided strategy shift
                    (e.g., "switching from XGBoost to LightGBM family").
        campaign_dir: Path to runner directory.

    Returns:
        Updated state dict with consecutive_discards reset to 0.
    """
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        raise DriverError("CAMPAIGN_STATE.json not found — run init first")
    state = json.loads(state_path.read_text())

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    trigger = int((eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3))

    if state.get("consecutive_discards", 0) < trigger:
        return {
            "status": "no_plateau",
            "message": f"consecutive_discards={state['consecutive_discards']} < trigger={trigger}; "
                       "no C2 plateau active — nothing to resolve",
        }

    import datetime as _dt

    prior_discards = state["consecutive_discards"]
    state["consecutive_discards"] = 0
    state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    # Append resolution to NOTEBOOK.md for audit trail
    notebook_path = camp / "state" / "NOTEBOOK.md"
    entry = (
        f"\n- **C2 resolved (round {state['round']}):** "
        f"consecutive_discards reset from {prior_discards} to 0. "
        f"Resolution: {resolution}\n"
    )
    if notebook_path.exists():
        with open(notebook_path, "a") as f:
            f.write(entry)
    else:
        notebook_path.write_text(entry)

    return {
        "status": "resolved",
        "prior_consecutive_discards": prior_discards,
        "resolution": resolution,
    }


def execute_finalize(
    executor_stdout: str,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    matches = list(_STDOUT_RE.finditer(executor_stdout))
    if not matches:
        return {
            "channel": None,
            "commit": None,
            "synthetic_verdict": "malformed",
            "reason": "Executor emitted no recognized channel line",
        }
    m = matches[-1]
    channel = m.group("channel")
    rest = m.group("rest").strip()

    if channel == "RUN_COMPLETE":
        commit = rest.split()[0] if rest else None
        return {"channel": channel, "commit": commit, "synthetic_verdict": None, "reason": ""}
    if channel == "RUN_FAILED":
        parts = rest.split(maxsplit=1)
        commit = parts[0] if parts else None
        reason = parts[1] if len(parts) > 1 else ""
        return {"channel": channel, "commit": commit, "synthetic_verdict": "crash", "reason": reason}
    if channel == "REVIEW_REQUIRED":
        return {"channel": channel, "commit": None, "synthetic_verdict": "malformed", "reason": rest}
    raise DriverError(f"unhandled channel: {channel}")


def review_finalize(
    verdict: Verdict,
    commit: str,
    metrics: dict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
) -> dict[str, Any]:
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    prior_verdict = state.get("last_verdict")
    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    pm = (eval_fm.get("primary_metric") or {})
    metric_name = pm.get("name", "val_pr_auc")
    direction = pm.get("direction", "maximize")

    log.append_result(
        commit=commit if commit else "none",
        metrics=metrics,
        status=verdict,
        action_type=action_type,
        hypothesis=hypothesis,
        description=description,
        model_family=model_family,
        n_features=n_features,
        campaign_dir=str(camp),
        primary_metric_name=metric_name,
        direction=direction,
    )
    state_after = json.loads(state_path.read_text())

    should_rollback = verdict in {"discard", "crash", "malformed"}
    pause_loop = verdict == "anomaly"

    halt_loop = False
    halt_reason = ""
    if verdict == "malformed" and prior_verdict == "malformed":
        halt_loop = True
        halt_reason = "two consecutive malformed verdicts — BUG: role producing malformed artifacts"
    if state_after.get("round", 0) >= state_after.get("budget_total", 0):
        halt_loop = True
        halt_reason = halt_reason or "budget_exhausted"

    return {
        "verdict": verdict,
        "should_rollback": should_rollback,
        "pause_loop": pause_loop,
        "halt_loop": halt_loop,
        "halt_reason": halt_reason,
    }
