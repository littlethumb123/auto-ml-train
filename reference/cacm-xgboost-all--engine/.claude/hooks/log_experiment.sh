#!/bin/bash
# Auto-populate EXPERIMENTATION.md stub after training or validation completes.
# Fires PostToolUse on Bash. Full entries are written by /log-exp skill.
INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
EXPLOG="$PROJECT_DIR/docs/EXPERIMENTATION.md"

EXIT_CODE="${CLAUDE_TOOL_EXIT_CODE:-0}"
if [ "$EXIT_CODE" != "0" ]; then
    exit 0
fi

# Extract the command that was run
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

# Only fire for training (step 4) or validation (step 5) scripts
if ! echo "$COMMAND" | grep -qE "4_train_model\.py|5_validate_run\.py"; then
    exit 0
fi

# Extract tag from command
TAG=$(echo "$COMMAND" | grep -oP -- '--tag\s+\K\S+')
if [ -z "$TAG" ]; then
    exit 0
fi

DATE=$(date +%Y-%m-%d)
ENTRY_KEY="## ${DATE} — Tag: ${TAG}"

# Dedup: skip if this entry already exists
if grep -qF "$ENTRY_KEY" "$EXPLOG" 2>/dev/null; then
    exit 0
fi

# Extract method if specified
METHOD=$(echo "$COMMAND" | grep -oP -- '--method\s+\K\S+' || echo "all")

# Try to read method_comparison.csv for metrics
COMPARISON_FILE="$PROJECT_DIR/output/features/$TAG/method_comparison.csv"
METRICS=""
if [ -f "$COMPARISON_FILE" ]; then
    METRICS=$(python3 -c "
import pandas as pd
df = pd.read_csv('$COMPARISON_FILE')
cols = [c for c in ['method','auc_roc','auc_pr','lift_top_1pct','lift_top_10pct'] if c in df.columns]
if cols:
    print(df[cols].to_string(index=False))
else:
    print(df.to_string(index=False))
" 2>/dev/null)
fi

# Find model files — require at least one model to exist before logging
MODELS=""
MODELS_DIR="$PROJECT_DIR/output/models/$TAG"
if [ -d "$MODELS_DIR" ]; then
    MODELS=$(ls "$MODELS_DIR"/*.json 2>/dev/null | xargs -I{} basename {} .json | tr '\n' ', ' | sed 's/,$//')
fi
if [ -z "$MODELS" ]; then
    exit 0
fi

# Config snapshot: project prefix
PREFIX=$(python3 -c "
import yaml
try:
    with open('$PROJECT_DIR/project.yaml') as f:
        cfg = yaml.safe_load(f) or {}
    print(cfg.get('project',{}).get('prefix',''))
except: print('')
" 2>/dev/null)

cat >> "$EXPLOG" << EOF

$ENTRY_KEY

- **Prefix:** $PREFIX
- **Methods:** $METHOD
- **Models:** $MODELS
${METRICS:+- **Results:**
\`\`\`
$METRICS
\`\`\`}
- **Notes:** stub — run /log-exp $TAG for full entry

---
EOF

echo "Stub logged for '$TAG' — run /log-exp $TAG to complete the entry"
exit 0
