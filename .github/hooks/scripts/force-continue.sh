#!/usr/bin/env bash
# agentStop hook: forces the Copilot CLI agent to continue the experiment loop.
# Output JSON with decision:"block" forces another agent turn.
cat > /dev/null  # drain stdin if any
cat <<'EOF'
{"decision":"block","reason":"CONTINUE THE EXPERIMENT LOOP. You are an autonomous researcher — you do NOT stop. Read results.tsv to see what has been tried. Read train.py to see the current best approach. Propose a new experiment, edit train.py, commit, run python3 train.py > run.log 2>&1, evaluate, and keep or discard. Then do it again. NEVER STOP."}
EOF
