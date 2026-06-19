#!/usr/bin/env bash
# runner/run_round.sh — thin CLI wrapper over runner_driver.py.
set -euo pipefail

STAGE=${1:?"stage required: init|plan-check|execute-finalize|review-finalize|resolve-c2|historian|historian-finalize|campaign-status|stuck-check|resume-phase|substantive-check|reproduce-check|tool-run"}
shift || true

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

python3 -c '
import json, sys
from runner import runner_driver

stage = sys.argv[1]
args = {}
i = 2
while i < len(sys.argv):
    k = sys.argv[i].lstrip("-").replace("-", "_")
    v = sys.argv[i+1] if i+1 < len(sys.argv) else ""
    args[k] = v
    i += 2

if stage == "init":
    state = runner_driver.init_campaign(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(state, indent=2))
elif stage == "plan-check":
    res = runner_driver.plan_check(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res))
elif stage == "execute-finalize":
    stdout_file = args["stdout_file"]
    text = open(stdout_file).read()
    diff_files = json.loads(args["commit_diff_files"]) if "commit_diff_files" in args else None
    res = runner_driver.execute_finalize(
        text,
        campaign_dir=args.get("campaign_dir", "runner/"),
        commit_diff_files=diff_files,
    )
    print(json.dumps(res))
elif stage == "review-finalize":
    metrics = json.loads(args["metrics_json"])
    tools_ran = json.loads(args["tools_ran"]) if "tools_ran" in args else None
    bootstrap_se = None
    if "bootstrap_se" in args and str(args.get("bootstrap_se", "")).strip():
        bootstrap_se = float(args["bootstrap_se"])
    res = runner_driver.review_finalize(
        verdict=args["verdict"],
        commit=args["commit"],
        metrics=metrics,
        action_type=args["action_type"],
        hypothesis=args["hypothesis"],
        description=args["description"],
        model_family=args["model_family"],
        n_features=int(args["n_features"]),
        campaign_dir=args.get("campaign_dir", "runner/"),
        tools_ran=tools_ran,
        bootstrap_se=bootstrap_se,
        planner_tokens=int(args.get("planner_tokens", 0) or 0),
        executor_tokens=int(args.get("executor_tokens", 0) or 0),
        reviewer_tokens=int(args.get("reviewer_tokens", 0) or 0),
    )
    print(json.dumps(res))
elif stage == "resolve-c2":
    res = runner_driver.resolve_c2(
        resolution=args.get("resolution", ""),
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps(res))
elif stage == "historian":
    res = runner_driver.historian_run(
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps(res))
elif stage == "historian-finalize":
    res = runner_driver.historian_finalize(
        campaign_dir=args.get("campaign_dir", "runner/"),
        trigger=args.get("trigger", "periodic"),
        patterns_added=int(args.get("patterns_added", 0) or 0),
        assumptions_flagged=int(args.get("assumptions_flagged", 0) or 0),
        tokens_used=int(args.get("tokens_used", 0) or 0),
    )
    print(json.dumps(res))
elif stage == "campaign-status":
    res = runner_driver.get_campaign_status(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res, indent=2))
elif stage == "stuck-check":
    from runner.orchestrator import detect_stuck
    from pathlib import Path
    warnings = detect_stuck(Path(args.get("campaign_dir", "runner/")))
    print(json.dumps({"warnings": warnings}))
elif stage == "resume-phase":
    from runner.orchestrator import determine_resume_phase
    from pathlib import Path
    camp = Path(args.get("campaign_dir", "runner/"))
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(open(state_path).read()) if state_path.exists() else {"round": 0}
    phase = determine_resume_phase(camp, state)
    print(json.dumps({"phase": phase}))
elif stage == "substantive-check":
    from runner.tools.substantive_diff import check_substantive
    from pathlib import Path
    diff_text = args.get("diff_text", "")
    train_py_path = args.get("train_py")
    helpers = json.loads(args.get("helpers_declared", "[]"))
    train_text = None
    if train_py_path:
        train_text = Path(train_py_path).read_text()
    res = check_substantive(diff_text, train_text, helpers)
    print(json.dumps(res))
elif stage == "reproduce-check":
    from runner.tools.reproduce_check import reproduce_check
    res = reproduce_check(
        y_true_path=args.get("y_true"),
        y_prob_path=args.get("y_prob"),
        run_log_path=args.get("run_log"),
        tolerance=float(args.get("tolerance", "0.001")),
    )
    print(json.dumps(res))
elif stage == "tool-run":
    from runner.tools.run import execute as _tool_execute
    rc = _tool_execute(
        name=args["name"],
        args=json.loads(args.get("args_json", "[]")),
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps({"exit_code": rc}))
    sys.exit(rc)
else:
    print(f"unknown stage: {stage}", file=sys.stderr)
    sys.exit(2)
' "$STAGE" "$@"
