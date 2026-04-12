#!/bin/bash
# =============================================================================
# Auto-Research Loop: Tennis XGBoost Prediction Pipeline
# =============================================================================
#
# Karpathy-style auto-research loop. Agent reads program.md, forms its own
# hypotheses, implements changes. Gate verifies. Ratchet commits winners.
#
# Usage: bash run-research.sh [max_iters]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MAX_ITERS=${1:-50}
CONSECUTIVE_FAILURES=0
CIRCUIT_BREAKER=10

# --- Agent dispatch configuration ---
# agent-mux is a CLI wrapper for dispatching AI coding agents (github.com/buildoak/agent-mux).
# You can replace it with `codex` CLI, Claude Code, or any agent that accepts a prompt and
# edits files in the working directory. See README for adaptation instructions.
AGENT_MUX="${AGENT_MUX:-agent-mux}"
ENGINE="codex"
MODEL="gpt-5.4"          # Replace with your preferred model
EFFORT="xhigh"
SANDBOX="workspace-write"

echo "=== Auto-Research Loop (v2 — canonical Karpathy) ==="
echo "Max iterations: $MAX_ITERS"
echo "Engine: $ENGINE / $MODEL / $EFFORT"
echo "Repo: $SCRIPT_DIR"
echo ""

# --- Establish baseline ---
echo "--- Establishing baseline ---"
BASELINE=$(bash gate.sh)
BASELINE_VALUE=$(echo "$BASELINE" | grep "COMBINED_ROC_AUC=" | sed 's/COMBINED_ROC_AUC=//')
echo "Baseline: COMBINED_ROC_AUC=$BASELINE_VALUE"
BEST=$BASELINE_VALUE

for i in $(seq 1 "$MAX_ITERS"); do
    echo ""
    echo "=========================================="
    echo "--- Iteration $i / $MAX_ITERS ---"
    echo "=========================================="

    # Snapshot current state for rollback
    SNAPSHOT_SHA=$(git rev-parse HEAD)

    # --- Write prompt to temp file (avoids shell quoting issues with embedded docs) ---
    PROMPT_FILE=$(mktemp /tmp/tennis-prompt-XXXXXX.md)
    cat > "$PROMPT_FILE" <<PROMPT_EOF
You are an ML researcher optimizing a tennis match prediction pipeline.

## Objective
Maximize COMBINED_ROC_AUC (average of ATP and WTA ROC-AUC on 2026 validation).
Current best: $BEST. Baseline: $BASELINE_VALUE. This is iteration $i of $MAX_ITERS.

## How to work
1. Read program.md -- it defines what you can change, what is off limits, and dead ends to avoid.
2. Read RESEARCH_LOG.md -- it shows what was tried before and what worked. Learn from it. Do not repeat failures. Build on successes.
3. Read the source files you plan to modify. Understand what is there before changing anything.
4. Form your own hypothesis about what will improve ROC-AUC. You decide what to try.
5. Implement your change. Be bold -- structural changes often beat parameter tweaks.
6. Run pytest to verify tests pass.
7. Do NOT modify immutable files: data.py, cli.py, gate.sh, run-research.sh, RESEARCH_LOG.md, data/raw/**, data/validation/**, tests/**
PROMPT_EOF
    AGENT_PROMPT=$(cat "$PROMPT_FILE")
    rm -f "$PROMPT_FILE"

    echo "Dispatching agent for iteration $i..."

    # --- Dispatch via agent-mux ---
    AGENT_OUTPUT=$("$AGENT_MUX" \
        --engine "$ENGINE" \
        --model "$MODEL" \
        --effort "$EFFORT" \
        --reasoning xhigh \
        --sandbox "$SANDBOX" \
        --cwd "$SCRIPT_DIR" \
        "$AGENT_PROMPT" 2>&1) || {
        echo "AGENT DISPATCH FAILED for iteration $i"
        echo "$AGENT_OUTPUT" | tail -20
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        if [[ $CONSECUTIVE_FAILURES -ge $CIRCUIT_BREAKER ]]; then
            echo "CIRCUIT BREAKER: $CIRCUIT_BREAKER consecutive failures. Stopping."
            break
        fi
        continue
    }

    echo "Agent completed. Running gate..."

    # --- Run gate ---
    GATE_OUTPUT=$(bash gate.sh 2>&1) || {
        echo "GATE FAILED after iteration $i"
        echo "$GATE_OUTPUT" | tail -10
        git checkout -- src/ pyproject.toml
        git clean -fd src/
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))

        echo "" >> RESEARCH_LOG.md
        echo "## Iteration $i -- GATE_FAILED" >> RESEARCH_LOG.md
        echo "- **Change:** (see agent output)" >> RESEARCH_LOG.md
        echo "- **Gate output:** ${GATE_OUTPUT:0:200}" >> RESEARCH_LOG.md
        echo "- **Committed:** no (rolled back)" >> RESEARCH_LOG.md

        if [[ $CONSECUTIVE_FAILURES -ge $CIRCUIT_BREAKER ]]; then
            echo "CIRCUIT BREAKER: $CIRCUIT_BREAKER consecutive failures. Stopping."
            break
        fi
        continue
    }

    # --- Extract combined ROC-AUC ---
    CURRENT=$(echo "$GATE_OUTPUT" | grep "COMBINED_ROC_AUC=" | sed 's/COMBINED_ROC_AUC=//')

    if [[ -z "$CURRENT" ]]; then
        echo "ERROR: Could not extract COMBINED_ROC_AUC from gate output"
        git checkout -- src/ pyproject.toml
        git clean -fd src/
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        continue
    fi

    # --- Compare ---
    IMPROVED=$(python3 -c "print(1 if float('$CURRENT') > float('$BEST') else 0)")

    if [[ "$IMPROVED" == "1" ]]; then
        DELTA=$(python3 -c "print(f'+{float(\"$CURRENT\") - float(\"$BEST\"):.4f}')")
        echo "IMPROVEMENT: $BEST -> $CURRENT ($DELTA)"
        PREV_BEST=$BEST
        BEST=$CURRENT
        CONSECUTIVE_FAILURES=0

        ATP_ROC=$(echo "$GATE_OUTPUT" | grep "ATP: ROC_AUC=" | sed 's/.*ROC_AUC=//' | sed 's/ .*//')
        WTA_ROC=$(echo "$GATE_OUTPUT" | grep "WTA: ROC_AUC=" | sed 's/.*ROC_AUC=//' | sed 's/ .*//')
        ATP_ACC=$(echo "$GATE_OUTPUT" | grep "Accuracy:" | sed 's/.*ATP=//' | sed 's/,.*//')
        WTA_ACC=$(echo "$GATE_OUTPUT" | grep "Accuracy:" | sed 's/.*WTA=//' | sed 's/ .*//')

        git add src/ pyproject.toml
        git commit -m "$(cat <<EOF
auto-research iter $i: COMBINED_ROC_AUC=$BEST ($DELTA)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
        )"
        COMMIT_SHA=$(git rev-parse --short HEAD)

        cat >> RESEARCH_LOG.md <<LOG_EOF

## Iteration $i -- IMPROVED
- **ATP ROC-AUC:** ${ATP_ROC:-N/A}
- **WTA ROC-AUC:** ${WTA_ROC:-N/A}
- **Combined ROC-AUC:** $BEST (delta: $DELTA from previous best $PREV_BEST)
- **ATP Accuracy:** ${ATP_ACC:-N/A}
- **WTA Accuracy:** ${WTA_ACC:-N/A}
- **Committed:** yes ($COMMIT_SHA)
LOG_EOF

    else
        DELTA=$(python3 -c "print(f'{float(\"$CURRENT\") - float(\"$BEST\"):.4f}')")
        echo "No improvement: $CURRENT <= $BEST ($DELTA)"
        git checkout -- src/ pyproject.toml
        git clean -fd src/
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))

        ATP_ROC=$(echo "$GATE_OUTPUT" | grep "ATP: ROC_AUC=" | sed 's/.*ROC_AUC=//' | sed 's/ .*//')
        WTA_ROC=$(echo "$GATE_OUTPUT" | grep "WTA: ROC_AUC=" | sed 's/.*ROC_AUC=//' | sed 's/ .*//')

        cat >> RESEARCH_LOG.md <<LOG_EOF

## Iteration $i -- NO_CHANGE
- **ATP ROC-AUC:** ${ATP_ROC:-N/A}
- **WTA ROC-AUC:** ${WTA_ROC:-N/A}
- **Combined ROC-AUC:** $CURRENT (delta: $DELTA from best $BEST)
- **Committed:** no (rolled back)
LOG_EOF

        if [[ $CONSECUTIVE_FAILURES -ge $CIRCUIT_BREAKER ]]; then
            echo "CIRCUIT BREAKER: $CIRCUIT_BREAKER consecutive failures. Stopping."
            break
        fi
    fi
done

echo ""
echo "=== Auto-Research Complete ==="
echo "Best COMBINED_ROC_AUC: $BEST (baseline was $BASELINE_VALUE)"
python3 -c "print(f'Improvement: +{float(\"$BEST\") - float(\"$BASELINE_VALUE\"):.4f}')"
