#!/usr/bin/env bash
# runner/run_round.sh — thin CLI wrapper over runner_driver.py.
set -euo pipefail

STAGE=${1:?"stage required: init|plan-check|execute-finalize|review-finalize|resolve-c2"}
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
    res = runner_driver.execute_finalize(text, campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res))
elif stage == "review-finalize":
    metrics = json.loads(args["metrics_json"])
    tools_ran = json.loads(args["tools_ran"]) if "tools_ran" in args else None
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
    )
    print(json.dumps(res))
elif stage == "resolve-c2":
    res = runner_driver.resolve_c2(
        resolution=args.get("resolution", ""),
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps(res))
else:
    print(f"unknown stage: {stage}", file=sys.stderr)
    sys.exit(2)
' "$STAGE" "$@"
