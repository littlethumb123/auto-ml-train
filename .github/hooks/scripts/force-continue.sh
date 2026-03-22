#!/usr/bin/env bash
# agentStop hook: forces the Copilot CLI agent to continue OR stop based on limits.
# Reads MAX_EXPERIMENTS from environment (default: 20) and checks results.tsv line count.
# Output JSON with decision:"block" forces another turn; decision:"allow" lets it stop.

cat > /dev/null  # drain stdin if any

MAX_EXPERIMENTS="${MAX_EXPERIMENTS:-20}"
RESULTS_FILE="results.tsv"

# Count experiments (lines minus header, or 0 if file doesn't exist)
if [[ -f "$RESULTS_FILE" ]]; then
    EXPERIMENT_COUNT=$(($(wc -l < "$RESULTS_FILE") - 1))
    [[ $EXPERIMENT_COUNT -lt 0 ]] && EXPERIMENT_COUNT=0
else
    EXPERIMENT_COUNT=0
fi

# Check for plateau (3+ consecutive discards = likely stuck)
if [[ -f "$RESULTS_FILE" ]] && [[ $EXPERIMENT_COUNT -ge 3 ]]; then
    LAST_THREE=$(tail -3 "$RESULTS_FILE" | cut -f4)
    if echo "$LAST_THREE" | grep -qv "keep"; then
        # All last 3 were discard/crash — might be at a plateau
        PLATEAU_WARNING="(Note: last 3 experiments did not improve — consider trying a radically different approach or stopping if satisfied)"
    fi
fi

if [[ $EXPERIMENT_COUNT -ge $MAX_EXPERIMENTS ]]; then
    cat <<EOF
{"decision":"allow","reason":"EXPERIMENT LIMIT REACHED. You have completed $EXPERIMENT_COUNT experiments (max: $MAX_EXPERIMENTS). Stop here. Summarize results: read results.tsv, report the best val_pr_auc achieved, and list the top 3 approaches."}
EOF
else
    REMAINING=$((MAX_EXPERIMENTS - EXPERIMENT_COUNT))
    cat <<EOF
{"decision":"block","reason":"CONTINUE ($EXPERIMENT_COUNT/$MAX_EXPERIMENTS experiments done, $REMAINING remaining). ${PLATEAU_WARNING:-Read results.tsv to see what has been tried. Read train.py to see the current best approach. Propose a new experiment, edit train.py, commit, run python3 train.py > run.log 2>&1, evaluate, and keep or discard.}"}
EOF
fi
