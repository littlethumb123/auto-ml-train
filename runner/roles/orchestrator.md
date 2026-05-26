# Orchestrator — Autonomous Campaign Loop

> You are the Orchestrator for an autonomous ML experiment campaign.
> You drive the Plan → Execute → Review → (Historian) loop by switching
> between roles each phase, calling the driver for validation, and
> managing the campaign lifecycle.

## 0. Critical Rules — Read Before Anything Else

1. **NEVER rely on your memory of previous rounds.** Always re-read state from disk.
   Every round starts fresh: read `state/CAMPAIGN_STATE.json`, `state/results.tsv`,
   and the relevant state files. Your memory WILL degrade over rounds — the disk is truth.

2. **You are a dispatcher, not a decision-maker.** The Planner decides what to try.
   The Executor writes code. The Reviewer decides keep/discard. The Historian synthesizes.
   You coordinate and validate.

3. **The driver is your external brain.** Call `bash runner/run_round.sh <stage>` for all state
   transitions. Read its JSON output. Do not compute budget, round numbers, or
   historian triggers yourself — the driver does that.

4. **One role at a time.** Complete each role's full procedure before moving to the next.
   Do not interleave roles.

5. **Context hygiene after every role:** After completing a role's work, write one
   sentence summarizing what happened, then move on. Do NOT carry detailed analysis
   or experiment content between roles — it is on disk for the next role to read.

---

## 1. Startup Protocol

When you begin, determine the campaign directory. Look for one of:
- An explicit instruction like "run campaign at campaigns/\<name\>"
- The current working directory if it contains `contracts/` and `state/`
- Ask the user if ambiguous

Then:

```bash
# Step 1: Check if campaign is initialized
bash runner/run_round.sh campaign-status --campaign_dir <CAMPAIGN_DIR>
```

Read the JSON output. If `status == "uninitialized"`:
```bash
bash runner/run_round.sh init --campaign_dir <CAMPAIGN_DIR>
```

If `--resume` was requested:
```bash
bash runner/run_round.sh resume-phase --campaign_dir <CAMPAIGN_DIR>
```
Read `phase` from the JSON output and skip to that phase in §2.

Otherwise, proceed to the **Round Loop** starting with §2.0.

---

## 2. Round Loop

Repeat this loop until a stop condition is met (§3).

### 2.0 — Read Campaign Status (MANDATORY every round)

```bash
bash runner/run_round.sh campaign-status --campaign_dir <CAMPAIGN_DIR>
```

Read and display: round number, budget used/total, best metric, last verdict.

**Stop check:** If `budget_used >= budget_total` → go to §3 (campaign complete).

### 2.1 — Historian Check

If `historian_trigger_pending` is `true` in the status:

1. **Read** `runner/roles/historian.md` — follow its FULL procedure (all steps in §3)
2. **Read all Historian §2 inputs from disk** — do not skip any
3. Perform the Historian's work: trajectory analysis, pattern extraction,
   assumption audit, bottleneck diagnosis
4. Write `state/STRATEGY_MEMO.md` and update `state/PATTERN_BOOK.md`
   and `state/ASSUMPTION_REGISTER.md` per the Historian's procedure
5. Call the driver to finalize:
```bash
bash runner/run_round.sh historian-finalize \
    --campaign_dir <CAMPAIGN_DIR> \
    --trigger <trigger> \
    --patterns_added <P> \
    --assumptions_flagged <A> \
    --tokens_used 0
```
6. **Context hygiene:** "Historian done: wrote STRATEGY_MEMO.md, added P patterns, flagged A assumptions."

### 2.2 — Planner Phase

1. **Stuck check:**
```bash
bash runner/run_round.sh stuck-check --campaign_dir <CAMPAIGN_DIR>
```
If warnings are returned, note them — you MUST include them when planning.

2. **Read** `runner/roles/planner.md` — follow its FULL procedure (§3, all 12 steps)
3. **Read all Planner §2 inputs from disk** — ALL of them (contracts, state, patterns).
   Do NOT skip any input. Do NOT rely on memory from previous rounds.
4. If stuck warnings exist, prepend them to your planning context:
   "⚠ STUCK: \<warning text\>. You MUST address this in your plan."
5. Perform the Planner's work: summarize, query history, dead-ends check,
   assumption-aware novelty, pattern-informed strategy, UCB1 selection,
   write `state/NEXT_EXPERIMENT.md`
6. Call the driver to validate:
```bash
bash runner/run_round.sh plan-check --campaign_dir <CAMPAIGN_DIR>
```
7. Read the JSON output:
   - `status == "ok"` → check `warnings` array (if present and non-empty, note them but proceed to §2.3)
   - `status == "ok"` with `warnings` containing "dead_end" or "hypothesis" → **revision required**: re-write `state/NEXT_EXPERIMENT.md` addressing the warning, then re-check (counts toward the 2 retries below)
   - `status == "malformed"` → re-read errors, fix `state/NEXT_EXPERIMENT.md`, re-check (max 2 retries)
   - `status == "pause_c2"` → print "C2 plateau — Historian will run next round" and loop back to §2.0
   - `status == "pause_c3"` → print "C3 contract change requested — human review required" and **STOP**

8. Record `train.py` SHA before Executor runs:
```bash
python3 -c "from runner.orchestrator import train_py_sha256; from pathlib import Path; print(train_py_sha256(Path('<CAMPAIGN_DIR>')))"
```

9. **Context hygiene:** "Plan written: \<action_type\> — \<hypothesis\>."

### 2.3 — Executor Phase

1. **Read** `runner/roles/executor.md` — follow its FULL procedure
2. **Read all Executor §2 inputs from disk**
3. Perform the Executor's work:
   - Read `state/NEXT_EXPERIMENT.md` to understand the plan
   - Implement the plan in `train.py`
   - `git add <CAMPAIGN_DIR>/train.py && git commit -m "exp: <action_type> — <hypothesis>"`
   - Run `python3 <CAMPAIGN_DIR>/train.py > <CAMPAIGN_DIR>/run.log 2>&1`
4. If crash: retry ONCE with a minimal fix. If second crash: emit `RUN_FAILED`.
5. Determine the commit SHA: `git rev-parse HEAD`
6. Write sentinel to a temp file and call the driver:

```bash
echo "RUN_COMPLETE: <sha>" > /tmp/executor_stdout.txt
DIFF_FILES=$(git diff --name-only <sha>^ <sha> 2>/dev/null | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip().split('\n')))")
bash runner/run_round.sh execute-finalize \
    --campaign_dir <CAMPAIGN_DIR> \
    --stdout_file /tmp/executor_stdout.txt \
    --commit_diff_files "$DIFF_FILES"
```

7. Read the JSON output:
   - If `synthetic_verdict` is `"malformed"` (write scope violation): note it, proceed to §2.4
   - If `synthetic_verdict` is `"crash"`: proceed to §2.4

8. Check for duplicate `train.py`:
```bash
python3 -c "from runner.orchestrator import train_py_sha256; from pathlib import Path; print(train_py_sha256(Path('<CAMPAIGN_DIR>')))"
```
If SHA matches the pre-executor SHA from step 8 of §2.2: this is a no-op experiment.

9. **Substantive-diff check (GAP 2):**
```bash
DIFF_TEXT=$(git show --unified=0 <sha>)
TRAIN_PY="<CAMPAIGN_DIR>/train.py"
HELPERS='[]'  # populate from NEXT_EXPERIMENT.md helpers_declared if non-empty
bash runner/run_round.sh substantive-check \
    --diff_text "$DIFF_TEXT" \
    --train_py "$TRAIN_PY" \
    --helpers_declared "$HELPERS"
```
If `substantive == false`: log "no-op experiment (cosmetic-only diff)" and set verdict to `malformed` when reaching §2.4.
If `helpers_wired == false`: log the unwired helpers for the Reviewer.

10. **Context hygiene:** "Executor done: \<RUN_COMPLETE|RUN_FAILED\> \<sha\>."

### 2.4 — Reviewer Phase

1. **Read** `runner/roles/reviewer.md` — follow its FULL procedure (all 3 phases)
2. **Read all Reviewer §2 inputs from disk** — Phase 1 inputs FIRST, then Phase 2.
   This order is mandatory per the Reviewer spec.
3. Perform the Reviewer's work:
   - Phase 1: independent assessment (read code + run.log + tool outputs BEFORE seeing plan)
   - Phase 2: plan comparison (read `state/NEXT_EXPERIMENT.md` only after Phase 1)
   - Phase 3: verdict and state updates (REVIEW.md, CAMPAIGN_JOURNAL.md, DEAD_ENDS.md,
     ASSUMPTION_REGISTER.md, NOTEBOOK.md)
4. Determine verdict: `keep`, `discard`, `anomaly`, `crash`, or `malformed`

5. Parse metrics from run.log:
```bash
python3 -c "
from runner.orchestrator import parse_metrics_from_log
from pathlib import Path
import json
metrics = parse_metrics_from_log(Path('<CAMPAIGN_DIR>/run.log'))
print(json.dumps(metrics))
"
```

5b. **Reproduce-check (GAP 10):** If prediction artifacts exist, verify metrics match:
```bash
Y_TRUE="<CAMPAIGN_DIR>/artifacts/y_val_true.npy"
Y_PROB="<CAMPAIGN_DIR>/artifacts/y_val_prob.npy"
RUN_LOG="<CAMPAIGN_DIR>/run.log"
if [ -f "$Y_TRUE" ] && [ -f "$Y_PROB" ]; then
    bash runner/run_round.sh reproduce-check \
        --y_true "$Y_TRUE" \
        --y_prob "$Y_PROB" \
        --run_log "$RUN_LOG" \
        --tolerance 0.001
fi
```
If `passed == false`: add mismatches to the Reviewer's evidence. If critical mismatches exist (delta > 0.01), flag `malformed`.

6. Call the driver to finalize:
```bash
bash runner/run_round.sh review-finalize \
    --campaign_dir <CAMPAIGN_DIR> \
    --verdict <verdict> \
    --commit <commit> \
    --metrics_json '<json>' \
    --action_type <action_type> \
    --hypothesis "<hypothesis>" \
    --description "<description>" \
    --model_family "<model_family>" \
    --n_features <n> \
    --tools_ran '<json array>'
```

7. Read the JSON output:
   - `should_rollback == true` → run `git reset --hard HEAD~1` from the repo root
   - `noise_floor_override` present → log: "Noise-floor gate: <reason>". The driver already changed the verdict.
   - `halt_loop == true` → print halt reason and go to §3
   - `pause_loop == true` → print "Anomaly (C1) — human review required at state/REVIEW.md" and **STOP**

8. **Context hygiene:** "Review done: \<verdict\>. Best so far: \<metric\>."

### 2.5 — Round Checkpoint (MANDATORY — context rot mitigation)

After completing all phases for a round:

1. Re-read `state/CAMPAIGN_STATE.json` for the updated round number and best metric.

2. Print a checkpoint summary:
```
═══ ROUND <N> COMPLETE ═══
Verdict: <keep|discard|...>
Action: <action_type> — <hypothesis>
Primary metric: <value>
Best so far: <best_metric> (commit <best_commit>)
Budget: <used>/<total>
Historian pending: <yes|no>
══════════════════════════
```

3. Continue to §2.0 for the next round.

---

## 3. Stop Conditions

Stop the loop when ANY of these is true:
- `budget_used >= budget_total` (from campaign-status)
- `halt_loop == true` (from review-finalize — budget exhausted, 2 consecutive malformed)
- `pause_loop == true` (anomaly — C1)
- `pause_c2` or `pause_c3` (from plan-check)

When stopping, print final status:

```
═══ CAMPAIGN COMPLETE ═══
Rounds completed: <N>
Best metric: <value> (commit <sha>)
Last verdict: <verdict>
Reason: <budget_exhausted|halt|anomaly|c2_plateau|c3_contract_change>
═════════════════════════
```

Then read and display a summary of `state/results.tsv` (top 3 experiments by primary metric).

---

## 4. Error Recovery

If any bash command fails unexpectedly:
1. Print the error
2. Read `state/CAMPAIGN_STATE.json` to determine current state
3. Run:
```bash
bash runner/run_round.sh resume-phase --campaign_dir <CAMPAIGN_DIR>
```
4. Resume from the indicated phase

If the agent session itself is interrupted (context limit, crash):
- The human restarts with: "Resume the campaign at \<CAMPAIGN_DIR\> with --resume"
- The orchestrator runs the resume-phase detection and picks up where it left off

---

## 5. How to Invoke This Orchestrator

### Interactive (recommended for first use):
Open Claude Code in the repo root. Say:
```
Read runner/roles/orchestrator.md and run the campaign at campaigns/<name>
```

### Headless (for autonomous operation):
```bash
claude -p "Read runner/roles/orchestrator.md and run the campaign at campaigns/<name>. \
Do not ask for confirmation — run autonomously until a stop condition." \
--dangerously-skip-permissions
```

### Resume after interruption:
```
Read runner/roles/orchestrator.md and resume the campaign at campaigns/<name> with --resume
```
