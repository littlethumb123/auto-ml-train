#!/bin/bash
# Session context — runs on every prompt to provide project state.
INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Project name from project.yaml
PROJECT_NAME=$(python3 -c "
import yaml
try:
    with open('$PROJECT_DIR/project.yaml') as f:
        cfg = yaml.safe_load(f) or {}
    print(cfg.get('project', {}).get('name', 'NOT CONFIGURED'))
except: print('NOT CONFIGURED')
" 2>/dev/null)

echo "=== XGBoost Session Context ==="
echo "Project: $PROJECT_NAME"

# Branch
BRANCH=$(cd "$PROJECT_DIR" && git branch --show-current 2>/dev/null)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ] || [ "$BRANCH" = "engine" ]; then
    echo "WARNING: On '$BRANCH' — endpoint work should be on an endpoint/* branch"
else
    echo "Branch: $BRANCH"
fi

# GPU
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "No GPU detected"

# Training processes
PROCS=$(ps aux | grep -E "4_train_model\.py|3_select_features\.py|5_validate_run\.py|3b_tune_hyperparams\.py|3c_rfe\.py" | grep -v grep)
if [ -n "$PROCS" ]; then
    echo "Active training: $(echo "$PROCS" | wc -l) process(es)"
else
    echo "No training processes running."
fi

# Last experiment
EXPLOG="$PROJECT_DIR/docs/EXPERIMENTATION.md"
if [ -f "$EXPLOG" ]; then
    LAST=$(grep "^## " "$EXPLOG" | tail -1)
    if [ -n "$LAST" ]; then
        echo "Last experiment: $LAST"
    fi
fi

# Latest model tag
LATEST_MODEL_DIR=$(ls -td "$PROJECT_DIR"/output/models/*/ 2>/dev/null | head -1)
if [ -n "$LATEST_MODEL_DIR" ]; then
    echo "Latest model tag: $(basename "$LATEST_MODEL_DIR")"
fi

exit 0
