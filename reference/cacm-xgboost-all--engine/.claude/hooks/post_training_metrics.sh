#!/bin/bash
# Post-training metric extraction — surfaces AUC/lift from training or validation output.
INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

EXIT_CODE="${CLAUDE_TOOL_EXIT_CODE:-0}"
if [ "$EXIT_CODE" != "0" ]; then
    exit 0
fi

# Only fire if the command was a training, validation, or feature-selection script
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
if ! echo "$COMMAND" | grep -qE "4_train_model\.py|5_validate_run\.py|3_select_features\.py"; then
    exit 0
fi

# Extract tag from command
TAG=$(echo "$COMMAND" | grep -oP -- '--tag\s+\K\S+')
if [ -z "$TAG" ]; then
    exit 0
fi

# Check for method_comparison.csv (written by step 4 with multiple methods)
COMPARISON="$PROJECT_DIR/output/features/$TAG/method_comparison.csv"
if [ -f "$COMPARISON" ]; then
    # Only report if modified in last 4 hours
    MOD=$(stat -c '%Y' "$COMPARISON" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$(( NOW - MOD ))
    if [ "$AGE" -lt 14400 ]; then
        echo "=== XGBoost Results (tag: $TAG) ==="
        python3 -c "
import pandas as pd
df = pd.read_csv('$COMPARISON')
cols = [c for c in ['method','auc_roc','auc_pr','brier','lift_top_1pct','lift_top_5pct','lift_top_10pct'] if c in df.columns]
if not cols:
    cols = df.columns.tolist()
print(df[cols].to_string(index=False))
" 2>/dev/null
    fi
fi

exit 0
