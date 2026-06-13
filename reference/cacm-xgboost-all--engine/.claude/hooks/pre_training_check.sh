#!/bin/bash
# Pre-training check: verify GPU availability and warn about zombie training processes.
# Only runs when a training or feature-selection script is about to execute.
INPUT=$(cat)

# Guard: only fire for training/selection scripts
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
if ! echo "$COMMAND" | grep -qE "3_select_features\.py|4_train_model\.py|5_validate_run\.py"; then
    exit 0
fi

echo "=== Pre-training check ==="

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
    GPU_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    echo "GPU memory: ${GPU_MEM}/${GPU_TOTAL} MiB"

    # Check for zombie training processes
    ZOMBIES=$(pgrep -f "train_model.py|select_features.py" 2>/dev/null)
    if [ -n "$ZOMBIES" ]; then
        echo "WARNING: Found running training processes: $ZOMBIES"
        echo "Kill them with: kill $ZOMBIES"
    fi
else
    echo "No GPU detected — training will use CPU"
fi

echo "=== Check complete ==="
