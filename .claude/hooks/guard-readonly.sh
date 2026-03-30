#!/usr/bin/env bash
# PreToolUse hook for Claude Code: blocks edits to prepare.py and data/ files.
#
# Claude Code PreToolUse hook contract:
#   - Receives JSON on stdin with tool_name and tool_input
#   - Exit 0 with no output = allow
#   - Exit 2 with stderr message = block the tool call
#   - Exit 0 with JSON permissionDecision = explicit allow/deny

set -euo pipefail

INPUT=$(cat)

# Extract file_path from tool_input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
print(ti.get('file_path', ti.get('filePath', '')))
" 2>/dev/null || echo "")

# Guard: block edits to prepare.py or anything under data/
if [[ -n "$FILE_PATH" ]]; then
    BASENAME=$(basename "$FILE_PATH")
    if [[ "$BASENAME" == "prepare.py" ]]; then
        echo "BLOCKED: prepare.py is READ-ONLY. It contains the frozen evaluation contract. Only edit train.py." >&2
        exit 2
    fi
    if echo "$FILE_PATH" | grep -qE '(^|/)data/'; then
        echo "BLOCKED: data/ directory is READ-ONLY. The dataset must not be modified." >&2
        exit 2
    fi
fi

# Allow everything else
exit 0
