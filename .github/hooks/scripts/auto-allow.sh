#!/usr/bin/env bash
# preToolUse hook: auto-allow python3, git, grep, tail, cat, and file operations.
# This prevents --yolo pauses on critical tools (Copilot CLI issue #1652).
INPUT=$(cat)
TOOL=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('toolName',''))" 2>/dev/null)

case "$TOOL" in
  bash|shell|view|edit|create|glob|grep)
    echo '{"permissionDecision":"allow"}'
    ;;
  *)
    # Default: let Copilot decide
    echo '{}'
    ;;
esac
