# Orchestrator Implementation Prompt
**Date:** 2026-05-25
**Purpose:** Ready-to-paste prompt for a new Claude Code session to implement `runner/orchestrator.py` — the missing external loop for the auto-train harness.

---

## CONTEXT AND MISSION

You are working on `auto-ml-train-main` at `/home/jupyter/Thinkubator/auto_train/`. This is an autonomous ML experimentation harness with a 4-role architecture (Planner / Executor / Reviewer / Historian). The harness is well-built but has one critical foundational gap: **there is no outer loop that actually calls Claude as an LLM agent for each role per experiment round.** Your mission is to implement this outer loop as `runner/orchestrator.py`, plus integration tests at `tests/integration/test_orchestrator.py`.

**DO NOT** create a standalone Python script that replaces LLM roles with templates. That was tried in `campaigns/ip-commercial-new-te-round2/auto_run.py` and produced catastrophic results: 40 consecutive identical experiments, PATTERN_BOOK.md never filled, 0.875 performance regression vs the first campaign. The outer loop must call real Claude LLM instances for each role.

---

## READ THESE FILES FIRST (in this order)

1. `runner/RUNNER.md`
2. `runner/AGENTS.md`
3. `runner/runner_driver.py` — understand ALL state machine functions and their return shapes
4. `runner/run_round.sh` — understand the CLI stages
5. `runner/roles/planner.md` — §2 Inputs list and sentinel behavior
6. `runner/roles/executor.md` — §2 Inputs list, sentinel lines (`RUN_COMPLETE:`, `RUN_FAILED:`)
7. `runner/roles/reviewer.md` — §2 Inputs list, sentinel line (`VERDICT:`)
8. `runner/roles/historian.md` — §2 Inputs list, sentinel line (`HISTORIAN_COMPLETE:`)
9. `tests/test_runner_driver.py` — to understand the fixture contracts (PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL strings)
10. `tests/integration/test_happy_loop.py` — to understand how the driver functions chain together

---

## WHAT TO BUILD

### `runner/orchestrator.py`

A classical ReAct while-loop orchestrator using the Anthropic Python SDK (`import anthropic`). The `anthropic` package is already installed. Thin dispatcher — zero decision logic. Intelligence stays in role prompts.

**Usage:**

```
python runner/orchestrator.py --campaign-dir campaigns/<name>
python runner/orchestrator.py --campaign-dir campaigns/<name> --resume
python runner/orchestrator.py --campaign-dir campaigns/<name> --max-rounds 3
```

**The outer loop:**

```
while budget_used < budget_total:
    if historian_trigger_pending:
        run Historian phase
    run Planner phase → validate NEXT_EXPERIMENT.md → runner_driver.plan_check()
    run Executor phase → parse sentinel → runner_driver.execute_finalize()
    run Reviewer phase → parse sentinel → runner_driver.review_finalize()
    if should_rollback: git reset --hard HEAD~1
    if halt_loop or pause_loop: break
```

**LLM invocation pattern — tool-use loop per role:**

The `anthropic` package supports tool use. Each role gets:
- A system prompt (the role's `.md` file content, read at runtime)
- A user message (all §2 inputs injected as text by the orchestrator)
- Three tools: `read_file`, `write_file`, `run_bash`

The tool-use loop runs until `stop_reason == "end_turn"`. Safety cap: 60 tool calls per role invocation.

```python
client = anthropic.Anthropic()

response = client.messages.create(
    model=model,
    max_tokens=8192,
    system=system_prompt,
    messages=messages,
    tools=[READ_FILE_TOOL, WRITE_FILE_TOOL, RUN_BASH_TOOL],
)
# Loop on tool_use stop_reason; break on end_turn
```

**Model tiering:**
- Planner: `claude-opus-4-6`
- Executor: `claude-sonnet-4-6`
- Reviewer: `claude-opus-4-6`
- Historian: `claude-opus-4-6`

**Tool definitions:**

```python
READ_FILE_TOOL = {
    "name": "read_file",
    "description": "Read a file. Path relative to repo root or absolute.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer"},
        },
        "required": ["path"],
    },
}

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write content to a file. Creates parent dirs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
}

RUN_BASH_TOOL = {
    "name": "run_bash",
    "description": "Run a bash command from repo root. Returns stdout+stderr. Timeout: 600s.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
        },
        "required": ["command"],
    },
}
```

**Context construction (Controller-Curated Context Isolation — inject §2 inputs as text):**

For **Planner**, user message includes:
- Contents of `runner/AGENTS.md`
- Contents of `contracts/PROBLEM_CONTRACT.md`, `DATA_CONTRACT.md`, `EVAL_PROTOCOL.md`, `STRATEGY_GUIDE.md`, `PRIORS.md`
- Contents of `state/CAMPAIGN_STATE.json`, `state/results.tsv` (last 10 rows), `state/DEAD_ENDS.md`, `state/UNEXPLORED_TECHNIQUES.md`, `state/NOTEBOOK.md`, `state/REVIEW.md`, `state/ASSUMPTION_REGISTER.md`, `state/PATTERN_BOOK.md`, `state/STRATEGY_MEMO.md`, `state/EXPERIMENT_TREE.json`, `state/TOKEN_SUMMARY.txt`
- Any stuck-detection warnings (see below)
- Explicit instruction: "Write state/NEXT_EXPERIMENT.md using the write_file tool at full path: `<campaign_dir>/state/NEXT_EXPERIMENT.md`"

For **Executor**, user message includes:
- Contents of `runner/AGENTS.md`
- Contents of `contracts/PROBLEM_CONTRACT.md`, `DATA_CONTRACT.md`, `EVAL_PROTOCOL.md`
- Contents of `state/NEXT_EXPERIMENT.md`, `state/CAMPAIGN_STATE.json`
- Full content of `train.py`
- Explicit instructions: edit train.py at full path, git commit, run `python3 <campaign_dir>/train.py > <campaign_dir>/run.log 2>&1`, emit `RUN_COMPLETE: <sha>` as final line

For **Reviewer**, user message includes:
- Contents of `runner/AGENTS.md`
- Contents of `contracts/EVAL_PROTOCOL.md`
- Contents of `state/CAMPAIGN_STATE.json`, `run.log` (full), `state/results.tsv` (last 5 rows), `state/ASSUMPTION_REGISTER.md`, `state/DEAD_ENDS.md`, `state/NEXT_EXPERIMENT.md`
- Explicit instructions: run mandatory tools via `run_bash`, write state files at full paths, emit `VERDICT: <keep|discard|anomaly|crash|malformed> <commit>` as final line

For **Historian**, user message includes:
- Contents of `runner/AGENTS.md`
- Contents of `contracts/EVAL_PROTOCOL.md`, `contracts/STRATEGY_GUIDE.md`
- Contents of `state/CAMPAIGN_STATE.json`, `state/CAMPAIGN_JOURNAL.md`, `state/results.tsv` (all rows), `state/DEAD_ENDS.md`, `state/NOTEBOOK.md`, `state/ASSUMPTION_REGISTER.md`, `state/PATTERN_BOOK.md`, `state/UNEXPLORED_TECHNIQUES.md`
- Trigger metadata from `runner_driver.historian_run()`
- Explicit instructions: write STRATEGY_MEMO.md and PATTERN_BOOK.md at full paths, emit `HISTORIAN_COMPLETE: round N, trigger T, patterns_added P, assumptions_flagged A, tokens_used T` as final line

**Sentinel detection — parse from model's accumulated response text:**

```python
import re

RUN_COMPLETE_RE    = re.compile(r"RUN_COMPLETE:\s*(\S+)")
RUN_FAILED_RE      = re.compile(r"RUN_FAILED:\s*(\S+)(?:\s+(.+))?")
REVIEW_REQUIRED_RE = re.compile(r"REVIEW_REQUIRED:\s*(.+)")
VERDICT_RE         = re.compile(r"VERDICT:\s*(keep|discard|anomaly|crash|malformed)\s+(\S+)", re.I)
HISTORIAN_RE       = re.compile(
    r"HISTORIAN_COMPLETE:\s*round\s+(\d+),\s*trigger\s+(\S+),\s*"
    r"patterns_added\s+(\d+),\s*assumptions_flagged\s+(\d+),\s*tokens_used\s+(\d+)", re.I
)
```

Accumulate all text blocks from the response across the tool-use loop iterations. Search for sentinels in the final `end_turn` response text.

**Metrics parsing from run.log:**

Parse `val_<metric>: <float>` lines. Also look for `---\n...\n---` key-value block. Return as `dict[str, float]`.

**Driver integration:**

After Planner: call `runner_driver.plan_check(campaign_dir=str(campaign_dir))` — check `status == "ok"`.

After Executor sentinel parsing: call `runner_driver.execute_finalize(executor_stdout="RUN_COMPLETE: <sha>\n", campaign_dir=..., commit_diff_files=<list>)`. Get diff files with `git diff --name-only <sha>^ <sha>`.

After Reviewer sentinel: call `runner_driver.review_finalize(verdict=..., commit=..., metrics=..., action_type=..., hypothesis=..., description=..., model_family=..., n_features=..., campaign_dir=..., tools_ran=..., bootstrap_se=..., planner_tokens=0, executor_tokens=0, reviewer_tokens=result.tokens_used)`.

After Historian: call `runner_driver.historian_finalize(campaign_dir=..., trigger=..., patterns_added=..., assumptions_flagged=..., tokens_used=...)`.

**Rollback:** When `review_result["should_rollback"]` is True: `subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=REPO_ROOT)`.

**Stuck detection — inject warnings into next Planner context:**

Parse `action_type` column from `state/results.tsv`. Emit warnings when:
1. Same `action_type` for last 3 consecutive rows → warn "You MUST try a different action_type"
2. A-B-A-B alternation in last 4 action_type values → warn "Break this pattern"
3. `train.py` SHA-256 identical before/after Executor → record as duplicate, treat as crash verdict

**Crash recovery (`--resume` flag):**

Determine resume phase from file presence:
- `state/CAMPAIGN_JOURNAL.md` has `## Round {current_round}` entry → Reviewer done → if `historian_trigger_pending`: go to historian, else go to next round
- `run.log` exists with `RUN_COMPLETE:` or `RUN_FAILED:` but no journal entry → go to reviewer
- `state/NEXT_EXPERIMENT.md` frontmatter has `round: {current_round}` but no run.log → go to executor
- Otherwise → go to planner

**Halt/pause conditions (from `review_finalize` return value):**
- `halt_loop == True` → print reason, break
- `pause_loop == True` → print "Anomaly (C1) — human review required at state/REVIEW.md", break
- `status == "pause_c2"` or `"pause_c3"` from `plan_check` → print, break

**HARD CONSTRAINTS (enforce in write_file tool handler):**

The write_file tool must enforce write scope. For Executor role invocations:
- Allow: `train.py` (relative to campaign dir), `runner/experiment_helpers/<exp_id>/*`
- Block everything else: return `[BLOCKED] write_scope_violation: <path>`

For all other roles: allow writes only under `<campaign_dir>/state/` and `<campaign_dir>/run.log`. Block `contracts/`, `runner/roles/`, `runner/tools/`, `prepare.py`, `log.py`.

---

### `tests/integration/test_orchestrator.py`

Write these 5 tests. Mock the Anthropic client — no real API calls.

**Test 1: Planner writes NEXT_EXPERIMENT.md**

Set up a tmp campaign with signed contracts (copy the PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL fixture strings from `tests/test_runner_driver.py`). Run `runner_driver.init_campaign()`. Mock `anthropic.Anthropic` so `messages.create()` returns a tool-use response that calls `write_file` with a valid NEXT_EXPERIMENT.md frontmatter, then `end_turn`. Assert `state/NEXT_EXPERIMENT.md` exists and `runner_driver.plan_check()` returns `{"status": "ok", "errors": []}`.

**Test 2: Historian runs when `historian_trigger_pending=True`**

Set up campaign state with `historian_trigger_pending: true`. Mock the historian LLM call to write minimal STRATEGY_MEMO.md and PATTERN_BOOK.md via write_file, then emit `HISTORIAN_COMPLETE: round 5, trigger periodic, patterns_added 1, assumptions_flagged 0, tokens_used 500` as end_turn text. Call `run_historian_phase()`. Assert STRATEGY_MEMO.md exists and `CAMPAIGN_STATE.json` has `historian_trigger_pending: false`.

**Test 3: Stuck detection fires after 3 same action_types**

Write a `state/results.tsv` with header + 4 data rows all having `action_type=A_hp`. Call `detect_stuck(campaign_dir)`. Assert returned list is non-empty and contains the string "STUCK WARNING".

**Test 4: Crash recovery determines correct resume phase**

Four sub-cases for `_determine_resume_phase(campaign_dir, state)` where `state["round"] == 5`:
- Case A: journal has `## Round 5` → returns `"next_round"` (or `"historian"` if pending)
- Case B: `run.log` has `RUN_COMPLETE: abc` but no journal entry → returns `"reviewer"`
- Case C: `NEXT_EXPERIMENT.md` has `round: 5` in frontmatter, no run.log → returns `"executor"`
- Case D: no files present → returns `"planner"`

**Test 5: `tools_ran` inferred from Reviewer text**

Mock Reviewer LLM to return text containing the words "anomaly" and "bootstrap_ci" plus `VERDICT: keep abc123def`. Call `run_reviewer_phase()`. Mock `runner_driver.review_finalize` and assert it is called with `tools_ran` containing both `"runner.tools.anomaly"` and `"runner.tools.bootstrap_ci"`.

---

## WHAT NOT TO BUILD

- No template-based experiment generation
- No hardcoded experiment sequences
- No Python code that decides what experiment to run — that is the Planner's job
- No stub historian that just resets trigger with `patterns_added=0`
- No auto_run.py-style scripts that bypass role prompts
- Do NOT inline role prompt content — read `.md` files as strings at runtime

---

## VALIDATION AFTER IMPLEMENTING

```bash
# Run the new integration tests
python -m pytest tests/integration/test_orchestrator.py -v

# Full test suite must stay green
python -m pytest tests/ -q

# Smoke test (costs real API tokens — optional)
python runner/orchestrator.py --campaign-dir campaigns/smoke-test-creditcard --max-rounds 3
```

Expected signal for smoke test: `state/NEXT_EXPERIMENT.md` contains rich multi-paragraph Planner reasoning referencing actual results from `results.tsv` and entries from `DEAD_ENDS.md` — NOT boilerplate like "UCB1-guided selection. Phase: diversify."

---

## REPO LAYOUT REMINDER

```
/home/jupyter/Thinkubator/auto_train/
├── runner/
│   ├── RUNNER.md
│   ├── AGENTS.md
│   ├── run_round.sh
│   ├── runner_driver.py          ← state machine (do not modify)
│   ├── orchestrator.py           ← CREATE THIS
│   ├── roles/
│   │   ├── planner.md
│   │   ├── executor.md
│   │   ├── reviewer.md
│   │   └── historian.md
│   └── tools/
└── tests/
    └── integration/
        └── test_orchestrator.py  ← CREATE THIS
```
