#!/bin/bash
# Session exit reminder — prompts to commit and log experiments.
INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

DIRTY=$(cd "$PROJECT_DIR" && git status --short 2>/dev/null | wc -l)
if [ "$DIRTY" -gt 0 ]; then
    echo "Reminder: $DIRTY uncommitted file(s). Consider committing your work."
fi

BRANCH=$(cd "$PROJECT_DIR" && git branch --show-current 2>/dev/null)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo "Reminder: You're on '$BRANCH'. Endpoint work should be on an endpoint/* branch."
fi

exit 0
