#!/bin/bash
# =============================================================================
# Verification Gate: ATP-Only Tennis XGBoost Auto-Research
# =============================================================================
#
# Runs the ATP pipeline only, extracts ROC-AUC, and enforces guard rails.
# Threshold: must exceed 0.7594 (current ATP plateau).
#
# Usage:   bash gate-atp.sh
# Output:  ATP_ROC_AUC=0.XXXX or KNOWLEDGE_ITERATION
# Exit:    0 on success or knowledge iteration, 1 on any failure
# Time:    < 5 minutes
#
# Diagnostics are printed to stderr. Stdout emits ATP_ROC_AUC on normal success,
# or KNOWLEDGE_ITERATION when only COMBAT_LOG.md changed.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ATP_THRESHOLD="0.7594"

# --- Pre-flight checks ---

if [[ ! -d ".venv" ]]; then
    echo "ERROR: .venv not found. Run 'make install' first." >&2
    exit 1
fi

# --- Log what the agent changed (diagnostic, survives rollback) ---
echo "--- Agent diff ---" >&2
git diff --stat 2>/dev/null >&2 || true
echo "--- End diff ---" >&2

# Verify data.py has not been modified (immutable guard rail)
DATA_PY_STATUS=$(git diff --name-only -- src/tennis_predict/data.py 2>/dev/null || echo "")
if [[ -n "$DATA_PY_STATUS" ]]; then
    echo "ERROR: data.py has been modified. This file is IMMUTABLE." >&2
    echo "Revert changes to data.py before running the gate." >&2
    exit 1
fi

# Verify cli.py has not been modified (immutable guard rail)
CLI_PY_STATUS=$(git diff --name-only -- src/tennis_predict/cli.py 2>/dev/null || echo "")
if [[ -n "$CLI_PY_STATUS" ]]; then
    echo "ERROR: cli.py has been modified. This file is IMMUTABLE." >&2
    echo "Revert changes to cli.py before running the gate." >&2
    exit 1
fi

# Verify tests/ has not been modified (immutable guard rail)
TESTS_STATUS=$(git diff --name-only -- tests/ 2>/dev/null || echo "")
if [[ -n "$TESTS_STATUS" ]]; then
    echo "ERROR: tests/ has been modified. Test files are IMMUTABLE." >&2
    exit 1
fi

# Verify evaluate.py has not been modified (immutable guard rail)
EVAL_PY_STATUS=$(git diff --name-only -- src/tennis_predict/evaluate.py 2>/dev/null || echo "")
if [[ -n "$EVAL_PY_STATUS" ]]; then
    echo "ERROR: evaluate.py has been modified. This file is IMMUTABLE." >&2
    echo "Revert changes to evaluate.py before running the gate." >&2
    exit 1
fi

# In baseline mode, skip diff-requirement checks (clean tree is expected)
if [[ "${BASELINE_MODE:-0}" != "1" ]]; then
    # Require at least one change in elo.py or features.py (where untapped value lives)
    # models.py changes are allowed ONLY when accompanied by elo.py or features.py changes
    # COMBAT_LOG.md changes alone are a "knowledge iteration" -- allowed as secondary gate
    ELO_CHANGED=$(git diff --name-only -- src/tennis_predict/elo.py 2>/dev/null || echo "")
    FEATURES_CHANGED=$(git diff --name-only -- src/tennis_predict/features.py 2>/dev/null || echo "")
    MODELS_CHANGED=$(git diff --name-only -- src/tennis_predict/models.py 2>/dev/null || echo "")
    COMBAT_LOG_CHANGED=$(git diff --name-only -- COMBAT_LOG.md 2>/dev/null || echo "")
    if [[ -z "$ELO_CHANGED" && -z "$FEATURES_CHANGED" ]]; then
        if [[ -n "$MODELS_CHANGED" ]]; then
            echo "ERROR: models.py changed without elo.py or features.py changes." >&2
            echo "Hyperparameters alone are exhausted. Add new signals first." >&2
            exit 1
        elif [[ -n "$COMBAT_LOG_CHANGED" ]]; then
            echo "KNOWLEDGE_ITERATION" >&2
            echo "KNOWLEDGE_ITERATION"
            exit 0
        else
            echo "ERROR: No changes to elo.py or features.py detected." >&2
            echo "Every iteration must introduce new signals via elo.py or features.py." >&2
            exit 1
        fi
    fi
fi

# --- Run tests first (fast gate) ---

echo "Running pytest..." >&2
if ! (. .venv/bin/activate && pytest -q 2>&1) >&2; then
    echo "ERROR: pytest failed. Fix tests before running the gate." >&2
    exit 1
fi
echo "Tests passed." >&2

# --- Run ATP pipeline ---

echo "Running ATP pipeline..." >&2
START_ATP=$(date +%s)

ATP_OUTPUT=$(. .venv/bin/activate && tennis-predict --tour atp run-pipeline 2>&1) || {
    echo "ERROR: ATP pipeline failed:" >&2
    echo "$ATP_OUTPUT" >&2
    exit 1
}

END_ATP=$(date +%s)
ATP_TIME=$((END_ATP - START_ATP))

ATP_ROC_LINE=$(echo "$ATP_OUTPUT" | grep "^ROC_AUC=" | tail -1)
if [[ -z "$ATP_ROC_LINE" ]]; then
    echo "ERROR: No ROC_AUC output from ATP pipeline" >&2
    echo "$ATP_OUTPUT" >&2
    exit 1
fi

ATP_ROC=$(echo "$ATP_ROC_LINE" | sed 's/ROC_AUC=//')
echo "ATP: ROC_AUC=$ATP_ROC (${ATP_TIME}s)" >&2

# Guard rail: training time < 10 min
if [[ $ATP_TIME -gt 600 ]]; then
    echo "ERROR: ATP training exceeded 10-minute guard rail (${ATP_TIME}s)" >&2
    exit 1
fi

# --- Guard rail: prediction sanity checks ---

PRED_FILE="models/atp/xgboost/predictions.csv"
if [[ ! -f "$PRED_FILE" ]]; then
    echo "ERROR: ATP predictions file not found at ${PRED_FILE}" >&2
    exit 1
fi

SANITY_RESULT=$(. .venv/bin/activate && python -c "
import sys
import pandas as pd
import numpy as np

df = pd.read_csv('${PRED_FILE}')
probs = df['prob_player_a_wins'].values

# Check 1: No extreme probabilities (catches hardcoded overrides)
max_prob = float(np.max(probs))
min_prob = float(np.min(probs))
if max_prob > 0.99:
    print(f'FAIL: max prediction {max_prob:.4f} > 0.99 (hardcoded override?)')
    sys.exit(1)
if min_prob < 0.01:
    print(f'FAIL: min prediction {min_prob:.4f} < 0.01 (hardcoded override?)')
    sys.exit(1)

# Check 2: Mean prediction in reasonable range (catches systematic bias)
mean_prob = float(np.mean(probs))
if mean_prob < 0.35 or mean_prob > 0.65:
    print(f'FAIL: mean prediction {mean_prob:.4f} outside [0.35, 0.65] (systematic bias?)')
    sys.exit(1)

# Check 3: Non-degenerate distribution (catches constant models)
std_prob = float(np.std(probs))
if std_prob < 0.05:
    print(f'FAIL: prediction std {std_prob:.4f} < 0.05 (degenerate model?)')
    sys.exit(1)

print(f'OK: range=[{min_prob:.4f}, {max_prob:.4f}], mean={mean_prob:.4f}, std={std_prob:.4f}')
" 2>&1) || {
    echo "ERROR: ATP prediction sanity check failed:" >&2
    echo "$SANITY_RESULT" >&2
    exit 1
}

if [[ "$SANITY_RESULT" == FAIL* ]]; then
    echo "ERROR: ATP prediction sanity check failed: ${SANITY_RESULT}" >&2
    exit 1
fi
echo "ATP predictions: ${SANITY_RESULT}" >&2

# --- Guard rail: model size < 100MB ---

MODEL_FILE="models/atp/xgboost/model.joblib"
if [[ -f "$MODEL_FILE" ]]; then
    MODEL_SIZE=$(wc -c < "$MODEL_FILE" | tr -d ' ')
    MAX_SIZE=$((100 * 1024 * 1024))  # 100MB
    if [[ $MODEL_SIZE -gt $MAX_SIZE ]]; then
        echo "ERROR: ATP model exceeds 100MB guard rail ($(( MODEL_SIZE / 1024 / 1024 ))MB)" >&2
        exit 1
    fi
fi

# --- Guard rail: feature count < 500 ---

PARQUET_FILE="data/processed/atp_features_strict.parquet"
if [[ -f "$PARQUET_FILE" ]]; then
    NCOLS=$(. .venv/bin/activate && python -c "
import pandas as pd
from tennis_predict.config import META_COLUMNS
df = pd.read_parquet('${PARQUET_FILE}')
feature_cols = [c for c in df.columns if c not in set(META_COLUMNS)]
print(len(feature_cols))
" 2>/dev/null || echo "0")
    if [[ $NCOLS -gt 500 ]]; then
        echo "ERROR: ATP feature count ($NCOLS) exceeds 500 guard rail" >&2
        exit 1
    fi
    echo "ATP: ${NCOLS} features" >&2
fi

# --- Extract additional diagnostics ---

ATP_ACC=$(echo "$ATP_OUTPUT" | grep "accuracy:" | head -1 | awk '{print $2}' || echo "N/A")
echo "Accuracy: ATP=${ATP_ACC}" >&2
echo "Time: ${ATP_TIME}s" >&2

# --- Output the single scalar (ONLY stdout output) ---

echo "ATP_ROC_AUC=${ATP_ROC}"
