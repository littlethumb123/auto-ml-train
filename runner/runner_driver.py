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

_SUCCESS_METRIC_RE = re.compile(r"(\w+)\s*>=?\s*([\d.]+)", re.IGNORECASE)


def _parse_success_target(problem_contract_path: Path, primary_metric_name: str) -> float | None:
    """Best-effort parse of the first success_criteria entry for a numeric target."""
    try:
        fm, _ = parse_frontmatter(problem_contract_path)
    except (FrontmatterError, OSError):
        return None
    criteria = fm.get("success_criteria") or []
    for crit in criteria:
        m = _SUCCESS_METRIC_RE.search(str(crit))
        if m and m.group(1).lower() == primary_metric_name.lower():
            return float(m.group(2))
    return None


_READ_ONLY_PREFIXES = (
    "prepare.py",
    "data/",
    "runner/contracts/",
    "runner/roles/",
    "runner/tools/",
    "log.py",
)


def _path_in_write_scope(path: str, allowed: set[str]) -> bool:
    if path == "train.py":
        return True
    if path in allowed:
        return True
    return any(path.startswith(a + "/") for a in allowed if a != "train.py")


def _normalize_mandatory_tool_name(name: str) -> str:
    """Map contract entries (e.g. tools/anomaly.py) to dotted module form for comparison."""
    n = name.strip()
    if not n:
        return ""
    if n.endswith(".py"):
        n = n[:-3]
    n = n.replace("\\", "/")
    if n.startswith("runner.tools."):
        return n
    if n.startswith("runner/tools/"):
        rest = n[len("runner/tools/") :].replace("/", ".")
        return "runner.tools." + rest
    if n.startswith("tools/"):
        rest = n[len("tools/") :].replace("/", ".")
        return "runner.tools." + rest
    if "/" in n:
        return n.replace("/", ".")
    return n


def _assumption_register_skeleton(campaign_id: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        f'campaign_id: "{campaign_id}"\n'
        "count: 0\n"
        'last_updated: ""\n'
        "---\n\n"
        "<!-- Reviewer appends entries on every keep verdict. -->\n"
        "<!-- Format: ### A-<round>-<seq> — <short name> -->\n"
    )


def _pattern_book_skeleton(campaign_id: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        f'campaign_id: "{campaign_id}"\n'
        "count: 0\n"
        'last_updated: ""\n'
        "---\n\n"
        "<!-- Historian appends entries during periodic/C2 runs. -->\n"
        "<!-- Format: ### P-<seq> — <pattern name> -->\n"
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

    # historian_interval: explicit from EVAL_PROTOCOL, or compute from budget
    budget_total = int(budgets.get("max_experiments", 100))
    ep_historian_interval = eval_fm.get("historian_interval")
    if ep_historian_interval is not None:
        historian_interval = int(ep_historian_interval)
    elif budget_total < 50:
        historian_interval = max(5, int(budget_total * 0.10))
    else:
        historian_interval = 10  # >=50 round campaigns: fixed 10-round cadence

    state = {
        "$schema_version": 2,
        "campaign_id": problem_fm.get("campaign_id"),
        "round": 0,
        "exp_id_counter": 0,
        "last_commit": None,
        "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0,
        "rounds_since_last_historian": 0,
        "historian_interval": historian_interval,
        "last_historian_round": None,
        "historian_trigger_pending": False,
        "total_tokens": {"planner": 0, "executor": 0, "reviewer": 0, "historian": 0},
        "budget_used": 0,
        "budget_total": budget_total,
        "created_at": now,
        "updated_at": now,
    }
    state_dir = camp / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "CAMPAIGN_STATE.json").write_text(json.dumps(state, indent=2) + "\n")

    results = state_dir / "results.tsv"
    if not results.exists():
        results_columns = list(eval_fm.get("results_columns") or []) or None
        results.write_text(log.make_header(results_columns))

    # Create skeleton state artifacts for the new meta-cognitive tier
    ar_path = state_dir / "ASSUMPTION_REGISTER.md"
    if not ar_path.exists():
        ar_path.write_text(_assumption_register_skeleton(state["campaign_id"]))
    pb_path = state_dir / "PATTERN_BOOK.md"
    if not pb_path.exists():
        pb_path.write_text(_pattern_book_skeleton(state["campaign_id"]))

    return state


def plan_check(campaign_dir: str = "runner/") -> dict[str, Any]:
    camp = Path(campaign_dir)
    plan_path = camp / "state" / "NEXT_EXPERIMENT.md"
    if not plan_path.exists():
        return {"status": "missing", "errors": ["NEXT_EXPERIMENT.md not found"]}

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    allowed = list(eval_fm.get("action_types") or [])
    errors = schema.validate_next_experiment(plan_path, allowed_action_types=allowed)

    fm_plan: dict[str, Any] | None = None
    escalation = None
    try:
        fm_plan, _ = parse_frontmatter(plan_path)
        escalation = fm_plan.get("escalation")
    except FrontmatterError:
        pass
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
    state["historian_trigger_pending"] = True
    state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

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
        "historian_trigger_pending": True,
    }


def historian_run(campaign_dir: str = "runner/") -> dict[str, Any]:
    """Return metadata for the outer loop to pass to the Historian agent.

    Migrates v1 CAMPAIGN_STATE.json to v2 schema on first call if needed.
    """
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        raise DriverError("CAMPAIGN_STATE.json not found — run init first")

    state = json.loads(state_path.read_text())

    # Migrate v1 → v2 if needed
    if state.get("$schema_version", 1) < 2:
        import datetime as _dt

        eval_fm_mig, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
        budgets_mig = eval_fm_mig.get("budgets") or {}
        budget_total_mig = int(budgets_mig.get("max_experiments", 100))
        ep_interval = eval_fm_mig.get("historian_interval")
        if ep_interval is not None:
            hist_interval = int(ep_interval)
        elif budget_total_mig < 50:
            hist_interval = max(5, int(budget_total_mig * 0.10))
        else:
            hist_interval = 10

        state["$schema_version"] = 2
        state.setdefault("rounds_since_last_historian", int(state.get("round", 0)))
        state.setdefault("historian_interval", hist_interval)
        state.setdefault("last_historian_round", None)
        state.setdefault("historian_trigger_pending", False)
        state.setdefault(
            "total_tokens",
            {"planner": 0, "executor": 0, "reviewer": 0, "historian": 0},
        )
        state.pop("c2_pending_diagnose", None)
        state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    plateau_trigger = int(
        (eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3)
    )

    is_periodic = (
        int(state.get("rounds_since_last_historian", 0))
        >= int(state.get("historian_interval", 10))
    )
    is_c2 = int(state.get("consecutive_discards", 0)) >= plateau_trigger

    if is_periodic and is_c2:
        trigger = "periodic+c2"
    elif is_c2:
        trigger = "c2"
    else:
        # Callers must pre-check historian_trigger_pending; this path
        # assumes the periodic interval was the trigger when c2 is not active.
        trigger = "periodic"

    last_historian_round = int(state.get("last_historian_round") or 0)
    current_round = int(state.get("round", 0))

    return {
        "status": "ok",
        "trigger": trigger,
        "rounds_covered": [last_historian_round + 1, current_round],
        "current_round": current_round,
        "campaign_dir": campaign_dir,
    }


def historian_finalize(
    campaign_dir: str = "runner/",
    trigger: str = "periodic",
    patterns_added: int = 0,
    assumptions_flagged: int = 0,
    tokens_used: int = 0,
) -> dict[str, Any]:
    """Update CAMPAIGN_STATE.json after the Historian agent completes."""
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        raise DriverError("CAMPAIGN_STATE.json not found — run init first")

    import datetime as _dt

    state = json.loads(state_path.read_text())
    state["rounds_since_last_historian"] = 0
    state["last_historian_round"] = int(state.get("round", 0))
    state["historian_trigger_pending"] = False
    state["pending_historian_tokens"] = tokens_used

    if "c2" in trigger:
        state["consecutive_discards"] = 0

    total_tokens = state.get("total_tokens") or {
        "planner": 0, "executor": 0, "reviewer": 0, "historian": 0
    }
    total_tokens["historian"] = int(total_tokens.get("historian", 0)) + tokens_used
    state["total_tokens"] = total_tokens
    state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    return {
        "status": "ok",
        "trigger": trigger,
        "patterns_added": patterns_added,
        "assumptions_flagged": assumptions_flagged,
        "tokens_used": tokens_used,
        "consecutive_discards_reset": "c2" in trigger,
    }


def execute_finalize(
    executor_stdout: str,
    campaign_dir: str = "runner/",
    commit_diff_files: list[str] | None = None,
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

        if commit_diff_files is not None:
            camp = Path(campaign_dir)
            plan_path = camp / "state" / "NEXT_EXPERIMENT.md"
            allowed: set[str] = {"train.py"}
            try:
                fm, _ = parse_frontmatter(plan_path)
                for h in fm.get("helpers_declared") or []:
                    if h:
                        allowed.add(str(h))
            except (FrontmatterError, OSError):
                pass
            violations = [f for f in commit_diff_files if not _path_in_write_scope(f, allowed)]
            if violations:
                read_hits = [
                    f
                    for f in violations
                    if any(f == p or f.startswith(p) for p in _READ_ONLY_PREFIXES)
                ]
                detail = read_hits if read_hits else violations
                return {
                    "channel": channel,
                    "commit": commit,
                    "synthetic_verdict": "malformed",
                    "reason": f"write_scope_violation: {detail}",
                }

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
    tools_ran: list[str] | None = None,
    bootstrap_se: float | None = None,
    planner_tokens: int = 0,
    executor_tokens: int = 0,
    reviewer_tokens: int = 0,
) -> dict[str, Any]:
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    prior_verdict = state.get("last_verdict")
    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    pm = (eval_fm.get("primary_metric") or {})
    metric_name = pm.get("name", "val_pr_auc")
    direction = pm.get("direction", "maximize")

    mandatory_gate_reason = ""
    mandatory_raw = list(eval_fm.get("mandatory_tools") or [])
    if tools_ran is not None and mandatory_raw and verdict == "keep":
        mandatory_norm = {_normalize_mandatory_tool_name(m) for m in mandatory_raw if m}
        ran_norm = {_normalize_mandatory_tool_name(t) for t in tools_ran if t}
        missing = mandatory_norm - ran_norm
        if missing:
            verdict = "malformed"
            mandatory_gate_reason = (
                f"mandatory_tools: missing normalized tool(s) {sorted(missing)} (spec §8.3 item 8)"
            )

    # Historian tokens stored by historian_finalize for the round that triggered it
    historian_tokens = int(state.get("pending_historian_tokens", 0))

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
        planner_tokens=planner_tokens,
        executor_tokens=executor_tokens,
        reviewer_tokens=reviewer_tokens,
        historian_tokens=historian_tokens,
    )
    state_after = json.loads(state_path.read_text())

    # Clear consumed pending_historian_tokens; increment rounds_since_last_historian
    state_after.pop("pending_historian_tokens", None)
    rounds_since = int(state_after.get("rounds_since_last_historian", 0)) + 1
    state_after["rounds_since_last_historian"] = rounds_since

    # Check historian trigger conditions
    hist_interval = int(state_after.get("historian_interval", 10))
    plateau_trigger_val = int(
        (eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3)
    )
    if (
        rounds_since >= hist_interval
        or int(state_after.get("consecutive_discards", 0)) >= plateau_trigger_val
    ):
        state_after["historian_trigger_pending"] = True

    # Accumulate token costs in state
    total_tokens = state_after.get("total_tokens") or {
        "planner": 0, "executor": 0, "reviewer": 0, "historian": 0
    }
    total_tokens["planner"] = int(total_tokens.get("planner", 0)) + planner_tokens
    total_tokens["executor"] = int(total_tokens.get("executor", 0)) + executor_tokens
    total_tokens["reviewer"] = int(total_tokens.get("reviewer", 0)) + reviewer_tokens
    state_after["total_tokens"] = total_tokens

    state_path.write_text(json.dumps(state_after, indent=2, sort_keys=True) + "\n")

    # Update token digest (non-critical — never raise)
    try:
        from runner.tools.token_summary import write_token_summary
        write_token_summary(campaign_dir=str(camp))
    except Exception:
        pass

    should_rollback = verdict in {"discard", "crash", "malformed"}
    pause_loop = verdict == "anomaly"

    halt_loop = False
    halt_reason = ""
    if verdict == "malformed" and prior_verdict == "malformed":
        halt_loop = True
        halt_reason = "two consecutive malformed verdicts — BUG: role producing malformed artifacts"
    elif mandatory_gate_reason:
        halt_reason = mandatory_gate_reason
    if state_after.get("round", 0) >= state_after.get("budget_total", 0):
        halt_loop = True
        halt_reason = halt_reason or "budget_exhausted"

    c3_advisory = False
    c3_advisory_reason = ""
    if (
        bootstrap_se is not None
        and bootstrap_se > 0
        and verdict in ("keep", "discard")
    ):
        problem_path = camp / "contracts" / "PROBLEM_CONTRACT.md"
        success_target = _parse_success_target(problem_path, metric_name)
        best_metric = (state_after.get("best_so_far") or {}).get("primary_metric")
        if success_target is not None and best_metric is not None:
            target_gap = success_target - best_metric
            if target_gap > 0 and target_gap <= 2 * bootstrap_se:
                c3_advisory = True
                c3_advisory_reason = (
                    f"target_gap={target_gap:.4f} <= 2*bootstrap_se={2 * bootstrap_se:.4f} — "
                    "bottleneck is measurement, not modeling; consider C3 to upgrade CV scheme"
                )

    result: dict[str, Any] = {
        "verdict": verdict,
        "should_rollback": should_rollback,
        "pause_loop": pause_loop,
        "halt_loop": halt_loop,
        "halt_reason": halt_reason,
    }
    if c3_advisory:
        result["c3_advisory"] = True
        result["c3_advisory_reason"] = c3_advisory_reason
    return result
