#!/bin/bash
# =============================================================================
# Auto-Research Loop: ATP-Only Tennis XGBoost Prediction Pipeline
# =============================================================================
#
# ATP-focused Karpathy-style auto-research loop. Agent reads program-atp.md
# and COMBAT_LOG.md, forms hypotheses, implements changes in elo.py/features.py.
# Gate verifies ATP ROC-AUC improvement. Ratchet commits winners.
#
# Usage: bash run-research-atp.sh [max_iters]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MAX_ITERS=${1:-30}
CONSECUTIVE_FAILURES=0
CONSECUTIVE_KNOWLEDGE=0
KNOWLEDGE_CAP=5
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

# --- Directive rotation (round-robin from program-atp.md active directives) ---
# Order follows program-atp.md "Directive order for the next ATP loop" (lines 332-342).
# D5 already landed as a win; included so the agent can build on it or skip if exhausted.
# D6/D11 merged into one slot since program-atp.md groups them.
DIRECTIVES=(15 6 11 10 12 13 14 8 9)
DIRECTIVE_TITLES=(
    "D15: Feature Pruning -- Zero-Importance Removal"
    "D6: ATP Fatigue Composites"
    "D11: Scheduling Density Features"
    "D10: Surface-Transition Performance"
    "D12: Head-to-Head Enrichment"
    "D13: Rank Momentum Enhancement"
    "D14: Upset Propensity"
    "D8: Glicko-2 Rating Deviation"
    "D9: Indoor/Outdoor Proxy for Hard Courts"
)

echo "=== ATP Auto-Research Loop (v4 — directive rotation + anti-repeat) ==="
echo "Max iterations: $MAX_ITERS"
echo "Engine: $ENGINE / $MODEL / $EFFORT"
echo "Repo: $SCRIPT_DIR"
echo ""

# --- Establish baseline ---
echo "--- Establishing baseline ---"
BASELINE=$(BASELINE_MODE=1 bash gate-atp.sh)
BASELINE_VALUE=$(echo "$BASELINE" | grep "ATP_ROC_AUC=" | sed 's/ATP_ROC_AUC=//')
echo "Baseline: ATP_ROC_AUC=$BASELINE_VALUE"
BEST=$BASELINE_VALUE

for i in $(seq 1 "$MAX_ITERS"); do
    echo ""
    echo "=========================================="
    echo "--- Iteration $i / $MAX_ITERS ---"
    echo "=========================================="

    # Snapshot current state for rollback
    SNAPSHOT_SHA=$(git rev-parse HEAD)

    # --- Directive rotation: pick the directive for this iteration ---
    DIRECTIVE_IDX=$(( (i - 1) % ${#DIRECTIVES[@]} ))
    DIRECTIVE_NUM=${DIRECTIVES[$DIRECTIVE_IDX]}
    DIRECTIVE_TITLE="${DIRECTIVE_TITLES[$DIRECTIVE_IDX]}"
    echo "Assigned directive: $DIRECTIVE_TITLE (index $DIRECTIVE_IDX, D$DIRECTIVE_NUM)"

    # --- Write prompt to temp file (avoids shell quoting issues with embedded docs) ---
    PROMPT_FILE=$(mktemp /tmp/tennis-atp-prompt-XXXXXX.md)
    cat > "$PROMPT_FILE" <<PROMPT_EOF
You are an ML researcher optimizing an ATP tennis match prediction pipeline.

## Objective
Maximize ATP_ROC_AUC on 2026 validation data.
Current best: $BEST. Baseline: $BASELINE_VALUE. This is iteration $i of $MAX_ITERS.

## This iteration: implement $DIRECTIVE_TITLE
Focus exclusively on Directive $DIRECTIVE_NUM. See program-atp.md for the full specification and pseudocode.
You have freedom in HOW to implement, but WHAT to try is locked to this directive.

## Anti-Repeat Protocol
- Read COMBAT_LOG.md BEFORE starting. Do NOT retry any approach already documented there.
- Do NOT create features by recombining or reparameterizing existing features -- XGBoost already learns those splits from raw values. Your directive specifies a genuinely new signal axis. Implement it as specified.
- If your assigned directive ($DIRECTIVE_TITLE) has already been tried and failed (check COMBAT_LOG.md), document WHY you believe the previous attempt failed and propose a meaningfully different implementation angle. If no different angle exists, skip to the next untried directive and document the skip in COMBAT_LOG.md.

## How to work
1. Read COMBAT_LOG.md FIRST -- it contains the full history of 40+ iterations across 3 loops. What was tried, what worked, what failed, what is exhausted. Do NOT repeat exhausted strategies.
2. Read program-atp.md -- it defines what you can change, what is off limits, priority directives, and dead ends.
3. Read the source files you plan to modify. Understand what is there before changing anything.
4. Implement ONE change aligned with your assigned directive. Isolate variables. Do not combine multiple hypotheses.
5. models.py is FROZEN. Do not modify it. Focus on elo.py and features.py for new signal.
6. Run pytest to verify tests pass.
7. Do NOT modify immutable files: data.py, cli.py, evaluate.py, gate-atp.sh, run-research-atp.sh, data/raw/**, data/validation/**, tests/**
8. COMBAT LOG PROTOCOL: If your experiment regresses or produces no improvement, BEFORE reverting your code changes, append a detailed entry to COMBAT_LOG.md documenting:
   - What hypothesis you tested and why (referencing $DIRECTIVE_TITLE)
   - The exact score result (ATP_ROC_AUC achieved)
   - Why you think it regressed or failed to improve
   - Implications and lessons for future attempts
   Combat log entries must be substantive analysis, not just "tried X, failed."
9. After writing the combat log entry, THEN revert your code changes to elo.py/features.py. The combat log entry should survive the revert.
PROMPT_EOF
    AGENT_PROMPT=$(cat "$PROMPT_FILE")
    rm -f "$PROMPT_FILE"

    echo "Dispatching agent for iteration $i (directive: D$DIRECTIVE_NUM)..."

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
    GATE_OUTPUT=$(bash gate-atp.sh 2>&1) || {
        echo "GATE FAILED after iteration $i"
        echo "$GATE_OUTPUT" | tail -10
        git checkout -- src/ pyproject.toml
        git clean -fd src/
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))

        echo "" >> RESEARCH_LOG.md
        echo "## ATP Iteration $i -- GATE_FAILED" >> RESEARCH_LOG.md
        echo "- **Change:** (see agent output)" >> RESEARCH_LOG.md
        echo "- **Gate output:** ${GATE_OUTPUT:0:200}" >> RESEARCH_LOG.md
        echo "- **Committed:** no (rolled back)" >> RESEARCH_LOG.md

        if [[ $CONSECUTIVE_FAILURES -ge $CIRCUIT_BREAKER ]]; then
            echo "CIRCUIT BREAKER: $CIRCUIT_BREAKER consecutive failures. Stopping."
            break
        fi
        continue
    }

    # --- Check for knowledge-only iteration ---
    if echo "$GATE_OUTPUT" | grep -q "KNOWLEDGE_ITERATION"; then
        echo "KNOWLEDGE ITERATION: Combat log updated, no code landed. See COMBAT_LOG.md."
        git add COMBAT_LOG.md
        git commit -m "$(cat <<EOF
atp-research iter $i: knowledge iteration (combat log only)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
        )"
        CONSECUTIVE_KNOWLEDGE=$((CONSECUTIVE_KNOWLEDGE + 1))
        CONSECUTIVE_FAILURES=0

        cat >> RESEARCH_LOG.md <<LOG_EOF

## ATP Iteration $i -- KNOWLEDGE_ITERATION
- **Change:** Combat log entry only (experiment regressed or failed, knowledge preserved)
- **Committed:** yes (combat log only)
- **Consecutive knowledge iterations:** $CONSECUTIVE_KNOWLEDGE / $KNOWLEDGE_CAP
LOG_EOF

        if [[ $CONSECUTIVE_KNOWLEDGE -ge $KNOWLEDGE_CAP ]]; then
            echo "LOOP STOPPED: $KNOWLEDGE_CAP consecutive knowledge-only iterations. Hypothesis space may be exhausted. Review COMBAT_LOG.md for accumulated findings."
            break
        fi
        continue
    fi

    # --- Extract ATP ROC-AUC ---
    CURRENT=$(echo "$GATE_OUTPUT" | grep "ATP_ROC_AUC=" | sed 's/ATP_ROC_AUC=//')

    if [[ -z "$CURRENT" ]]; then
        echo "ERROR: Could not extract ATP_ROC_AUC from gate output"
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
        CONSECUTIVE_KNOWLEDGE=0

        ATP_ROC=$(echo "$GATE_OUTPUT" | grep "ATP: ROC_AUC=" | sed 's/.*ROC_AUC=//' | sed 's/ .*//')
        ATP_ACC=$(echo "$GATE_OUTPUT" | grep "Accuracy:" | sed 's/.*ATP=//' | sed 's/,.*//')

        git add src/ pyproject.toml
        git commit -m "$(cat <<EOF
atp-research iter $i: ATP_ROC_AUC=$BEST ($DELTA)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
        )"
        COMMIT_SHA=$(git rev-parse --short HEAD)

        cat >> RESEARCH_LOG.md <<LOG_EOF

## ATP Iteration $i -- IMPROVED
- **ATP ROC-AUC:** ${ATP_ROC:-$BEST}
- **Delta:** $DELTA from previous best $PREV_BEST
- **ATP Accuracy:** ${ATP_ACC:-N/A}
- **Committed:** yes ($COMMIT_SHA)
LOG_EOF

    else
        DELTA=$(python3 -c "print(f'{float(\"$CURRENT\") - float(\"$BEST\"):.4f}')")
        echo "No improvement: $CURRENT <= $BEST ($DELTA)"
        git checkout -- src/ pyproject.toml
        git clean -fd src/
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))

        ATP_ROC=$(echo "$GATE_OUTPUT" | grep "ATP: ROC_AUC=" | sed 's/.*ROC_AUC=//' | sed 's/ .*//')

        cat >> RESEARCH_LOG.md <<LOG_EOF

## ATP Iteration $i -- NO_CHANGE
- **ATP ROC-AUC:** ${ATP_ROC:-$CURRENT}
- **Delta:** $DELTA from best $BEST
- **Committed:** no (rolled back)
LOG_EOF

        if [[ $CONSECUTIVE_FAILURES -ge $CIRCUIT_BREAKER ]]; then
            echo "CIRCUIT BREAKER: $CIRCUIT_BREAKER consecutive failures. Stopping."
            break
        fi
    fi
done

echo ""
echo "=== ATP Auto-Research Complete ==="
echo "Best ATP_ROC_AUC: $BEST (baseline was $BASELINE_VALUE)"
python3 -c "print(f'Improvement: +{float(\"$BEST\") - float(\"$BASELINE_VALUE\"):.4f}')"
