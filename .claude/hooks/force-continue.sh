#!/usr/bin/env bash
# Stop hook for Claude Code: forces the agent to continue the experiment loop
# until MAX_EXPERIMENTS is reached or a plateau is detected.
#
# Claude Code Stop hook contract:
#   - Receives JSON on stdin (includes stop_hook_active field)
#   - Exit 0 = allow stop (or output JSON to block)
#   - Output {"decision":"block","reason":"..."} to force continuation
#
# IMPORTANT: If stop_hook_active is true, we already blocked once on this turn.
# We must allow the stop to avoid an infinite loop.

set -euo pipefail

INPUT=$(cat)

# Only activate on autotrain/* branches — normal conversations are not blocked
BRANCH=$(git -C "${CLAUDE_PROJECT_DIR:-$(pwd)}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [[ "$BRANCH" != autotrain/* ]]; then
    exit 0
fi

# Check if we already blocked this turn (avoid infinite loop)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null || echo "False")
if [[ "$STOP_HOOK_ACTIVE" == "True" || "$STOP_HOOK_ACTIVE" == "true" ]]; then
    # Already blocked once — let Claude stop this turn, it will resume next turn
    exit 0
fi

MAX_EXPERIMENTS="${MAX_EXPERIMENTS:-20}"
RESULTS_FILE="${CLAUDE_PROJECT_DIR:-$(pwd)}/results.tsv"

# Count experiments (lines minus header, or 0 if file doesn't exist)
if [[ -f "$RESULTS_FILE" ]]; then
    EXPERIMENT_COUNT=$(($(wc -l < "$RESULTS_FILE") - 1))
    [[ $EXPERIMENT_COUNT -lt 0 ]] && EXPERIMENT_COUNT=0
else
    EXPERIMENT_COUNT=0
fi

# Check for plateau (3+ consecutive non-keeps = likely stuck)
PLATEAU_WARNING=""
if [[ -f "$RESULTS_FILE" ]] && [[ $EXPERIMENT_COUNT -ge 3 ]]; then
    # Plateau = all 3 of the last 3 experiments were non-keeps (discard or crash)
    if ! tail -3 "$RESULTS_FILE" | cut -f6 | grep -q "keep"; then
        PLATEAU_WARNING="(Warning: last 3 experiments did not improve — consider a radically different approach or stopping if satisfied)"
    fi
fi

if [[ $EXPERIMENT_COUNT -ge $MAX_EXPERIMENTS ]]; then
    # Limit reached — allow Claude to stop, but tell it to summarize
    cat <<EOF
{"decision":"allow","reason":"EXPERIMENT LIMIT REACHED ($EXPERIMENT_COUNT/$MAX_EXPERIMENTS). Stop here. Read results.tsv, report the best val_pr_auc achieved, and list the top 3 approaches."}
EOF
else
    # Under limit — block the stop, force continuation
    REMAINING=$((MAX_EXPERIMENTS - EXPERIMENT_COUNT))
    cat <<EOF
{"decision":"block","reason":"CONTINUE EXPERIMENTING ($EXPERIMENT_COUNT/$MAX_EXPERIMENTS done, $REMAINING remaining). ${PLATEAU_WARNING:-Read results.tsv to see what has been tried. Read train.py to see the current best approach. Propose a new experiment, edit train.py, commit, run python3 train.py > run.log 2>&1, evaluate, and keep or discard.}"}
EOF
fi
