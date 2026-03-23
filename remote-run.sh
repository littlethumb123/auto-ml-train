#!/usr/bin/env bash
# Remote execution wrapper for auto_train experiments.
# This script is called by the agent to run train.py on the remote Vertex AI server.
#
# Usage (from local machine with Copilot CLI):
#   ./remote-run.sh [REMOTE_HOST] [REMOTE_PATH]
#
# Environment variables:
#   REMOTE_HOST  - SSH host (e.g., jupyter@vertex-ai-ip or vertex-workbench)
#   REMOTE_PATH  - Path to auto_train on remote (default: /home/jupyter/Thinkubator/auto_train)
#
# The script:
#   1. Syncs local train.py to remote
#   2. Runs python3 train.py on remote
#   3. Syncs run.log back to local
#   4. Syncs results.tsv back to local (if exists)

set -e

REMOTE_HOST="${REMOTE_HOST:-${1:-}}"
REMOTE_PATH="${REMOTE_PATH:-${2:-/home/jupyter/Thinkubator/auto_train}}"

if [[ -z "$REMOTE_HOST" ]]; then
    echo "ERROR: REMOTE_HOST not set. Usage: REMOTE_HOST=user@ip ./remote-run.sh"
    echo "Or configure in ~/.ssh/config and use: REMOTE_HOST=vertex-workbench ./remote-run.sh"
    exit 1
fi

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[remote-run] Syncing train.py to $REMOTE_HOST:$REMOTE_PATH/"
rsync -az "$LOCAL_DIR/train.py" "$REMOTE_HOST:$REMOTE_PATH/train.py"

echo "[remote-run] Running experiment on remote..."
ssh "$REMOTE_HOST" "cd $REMOTE_PATH && python3 train.py > run.log 2>&1; exit 0"

echo "[remote-run] Syncing run.log back..."
rsync -az "$REMOTE_HOST:$REMOTE_PATH/run.log" "$LOCAL_DIR/run.log"

# Sync results.tsv if it exists on remote
ssh "$REMOTE_HOST" "test -f $REMOTE_PATH/results.tsv" && \
    rsync -az "$REMOTE_HOST:$REMOTE_PATH/results.tsv" "$LOCAL_DIR/results.tsv" || true

echo "[remote-run] Done. Results:"
grep "^val_pr_auc:\|^val_f1:\|^n_features:" "$LOCAL_DIR/run.log" || echo "(no metrics found - check run.log for errors)"
