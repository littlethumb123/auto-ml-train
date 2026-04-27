# Autonomous ML runner — operator guide

This folder is the **experiment harness**: contracts, state, tools, and a small driver. Humans or agents follow **Planner → Executor → Reviewer** using the prompts in `roles/`. The driver validates artifacts and updates `state/results.tsv` + `state/CAMPAIGN_STATE.json`.

**Agent-oriented overview:** `RUNNER.md`  
**Design spec:** `docs/superpowers/specs/2026-04-21-autonomous-ml-runner-design.md`

---

## Prerequisites

1. **Python 3.10+** (matches project usage).
2. **Dependencies** (repo root):

   ```bash
   pip install -r requirements.txt
   ```

3. **Data** at `data/creditcard.csv` (or paths declared in `contracts/DATA_CONTRACT.md`). If needed, from repo root:

   ```bash
   python3 prepare.py
   ```

4. **Repo root** as working directory for `run_round.sh` (the script `cd`s there so imports work).

---

## One-time: gates G1–G3 (sign contracts)

The driver **refuses `init`** until the three contracts are valid **and** each has a non-null `approved_at` / `approved_by` in YAML frontmatter. `DATA_CONTRACT.md` also requires `leakage_audit.performed_at` before init (schema + driver).

Typical order:

1. **Create a campaign branch** (keeps `main` clean; discards rollback safely):

   ```bash
   git checkout -b campaign/<campaign_id>
   ```

2. Edit `contracts/PROBLEM_CONTRACT.md`, `contracts/DATA_CONTRACT.md`, `contracts/EVAL_PROTOCOL.md` — set `approved_at` and `approved_by` when you accept them.
3. Run leakage tooling and set `leakage_audit.performed_at` on the data contract, for example:

   ```bash
   python3 -m runner.tools.leakage_audit \
     --data-contract-path runner/contracts/DATA_CONTRACT.md \
     --data-path data/creditcard.csv \
     --target-col Class
   ```

   Then set `performed_at` in the contract to the date you sign off G2.

4. **Initialize campaign state** (creates `state/CAMPAIGN_STATE.json` and header-only `state/results.tsv` if missing):

   ```bash
   ./runner/run_round.sh init --campaign-dir runner/
   ```

You should see JSON with `"round": 0` and `"budget_total"` from `EVAL_PROTOCOL.md` budgets.

---

## One experiment round (loop)

Work **from repo root**. Replace paths if your campaign dir is not `runner/`.

### 1. Planner

- Read `runner/roles/planner.md` and inputs it lists.
- Write **`runner/state/NEXT_EXPERIMENT.md`** (schema enforced by the driver).

### 2. Plan check

```bash
./runner/run_round.sh plan-check --campaign-dir runner/
```

Expect `{"status": "ok", "errors": []}`. Other statuses: `malformed`, `pause_c2`, `pause_c3`, `missing` — fix artifacts or follow escalation before executing.

#### Handling `pause_c2` (plateau)

If `plan-check` returns `{"status": "pause_c2", ...}`, the campaign has hit a plateau
(`consecutive_discards >= trigger`). To resume:

1. Review the C2 escalation block in `NEXT_EXPERIMENT.md` and decide a strategy shift.
2. Resolve the plateau:

   ```bash
   ./runner/run_round.sh resolve-c2 \
     --resolution "switching from XGBoost to LightGBM after 3 consecutive discards" \
     --campaign-dir runner/
   ```

3. Write a new `NEXT_EXPERIMENT.md` reflecting the decided strategy shift, then re-run `plan-check`.

### 3. Executor

- Read `runner/roles/executor.md`.
- Edit **only** `train.py` (and optional `runner/experiment_helpers/<exp_id>/` if the plan declares it).
- Commit, run `python3 train.py > run.log 2>&1`, and end with **exactly one** line on stdout:

  - `RUN_COMPLETE: <git_commit_sha>`
  - or `RUN_FAILED: <sha> <reason>`
  - or `REVIEW_REQUIRED: <reason>`

Capture executor stdout to a file, e.g. `/tmp/executor_out.txt`.

### 4. Execute finalize

Minimal (parse stdout only):

```bash
./runner/run_round.sh execute-finalize \
  --stdout-file /tmp/executor_out.txt \
  --campaign-dir runner/
```

With **write-scope enforcement** (recommended): pass the paths touched by the Executor commit so the driver rejects anything outside `train.py` plus `helpers_declared` in `NEXT_EXPERIMENT.md`. From repo root, after `RUN_COMPLETE` (replace `<sha>` with the Executor commit; `<parent>` is usually `HEAD~1` on a single-child branch):

```bash
DIFF_JSON=$(git diff --name-only <parent>..<sha> | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
./runner/run_round.sh execute-finalize \
  --stdout-file /tmp/executor_out.txt \
  --commit-diff-files "$DIFF_JSON" \
  --campaign-dir runner/
```

### 5. Reviewer

- Read `runner/roles/reviewer.md`, mandatory tools, `run.log`, etc.
- Decide verdict and metrics; then call **review-finalize** (example):

```bash
./runner/run_round.sh review-finalize \
  --verdict keep \
  --commit <sha> \
  --metrics-json '{"val_pr_auc":0.80,"lift_at_10":5.0,"macro_f1":0.8,"val_f1":0.7}' \
  --action-type A_hp \
  --hypothesis "short label" \
  --description "longer text" \
  --model-family lightgbm \
  --n-features 30 \
  --campaign-dir runner/
```

**Mandatory-tools enforcement (recommended for `keep`):** pass every tool you actually ran, using names that normalize to the same dotted form as `EVAL_PROTOCOL.mandatory_tools` (e.g. `runner.tools.anomaly` matches `tools/anomaly.py` in the contract). If any mandatory tool is missing from this list, the driver **overrides** `keep` → `malformed`.

```bash
./runner/run_round.sh review-finalize \
  --verdict keep \
  --commit <sha> \
  --metrics-json '{"val_pr_auc":0.80,"lift_at_10":5.0,"macro_f1":0.8,"val_f1":0.7}' \
  --action-type A_hp \
  --hypothesis "short label" \
  --description "longer text" \
  --model-family lightgbm \
  --n-features 30 \
  --tools-ran '["runner.tools.anomaly","runner.tools.bootstrap_ci"]' \
  --bootstrap-se 0.035 \
  --campaign-dir runner/
```

`--bootstrap-se` is optional; when set, JSON output may include `c3_advisory` / `c3_advisory_reason` when the gap to `PROBLEM_CONTRACT` success criteria is within `2×` that SE (STRATEGY_GUIDE §1).

On **discard / crash / malformed**, your process should **`git reset --hard HEAD~1`** after logging (per harness rules). On **anomaly**, pause and investigate (C1).

Repeat from step 1 for the next round until budget or stop condition in `EVAL_PROTOCOL.md`.

### Campaign conclusion

When the campaign ends (budget exhausted, plateau, or success criteria met):

```bash
git checkout main
git merge campaign/<campaign_id> --no-ff -m "Merge campaign <campaign_id> — best val_pr_auc=X.XXX"
```

---

## Driver CLI reference

| Stage | Purpose |
|--------|--------|
| `init` | Validate signed contracts; write `CAMPAIGN_STATE.json` + `results.tsv` header |
| `plan-check` | Validate `NEXT_EXPERIMENT.md` |
| `execute-finalize` | Parse executor stdout (`RUN_COMPLETE` / `RUN_FAILED` / `REVIEW_REQUIRED`) |
| `review-finalize` | Append `results.tsv`, update `CAMPAIGN_STATE.json`, return rollback/pause/halt hints |
| `resolve-c2` | Acknowledge C2 plateau pause, reset `consecutive_discards`, resume normal planning |

All stages accept `--campaign-dir <path>` (default `runner/`).

Optional flags (passed through to the driver when present):

- `--tools-ran` (`review-finalize`): JSON array of tools the Reviewer ran; required for mechanical `mandatory_tools` check on **`keep`** (omit = no check).
- `--bootstrap-se` (`review-finalize`): float; optional input for C3 measurement-bottleneck advisory in JSON response.
- `--commit-diff-files` (`execute-finalize`): JSON array of paths changed in the Executor commit; optional write-scope gate vs `train.py` + `helpers_declared`.

**After `./runner/run_round.sh resolve-c2`:** the driver automatically triggers the Historian role before the next Planner turn. The Historian writes `state/STRATEGY_MEMO.md`; the Planner reads it before writing the next plan. (The old `c2_pending_diagnose → A_diagnose` protocol has been removed.)

---

## Tactical tools (examples)

Each module under `runner/tools/` is importable and has a CLI via `python3 -m runner.tools.<name> --help`.

> **Why module-style?** All tools use `from runner.tools._common import ...` (package-relative
> imports). Direct file invocation (`python3 runner/tools/<name>.py`) fails because Python
> doesn't recognize `runner` as a package when the script path is used. Module invocation
> (`python3 -m runner.tools.<name>`) runs with the repo root on `sys.path`, so package
> imports resolve correctly.

Examples:

```bash
python3 -m runner.tools.results_query --campaign-dir runner/ --limit 5
python3 -m runner.tools.dead_ends_query --campaign-dir runner/
python3 -m runner.tools.anomaly \
  --latest-json '{"val_pr_auc":0.4,"status":"keep","model_family":"lgb"}' \
  --history-json '[]' \
  --floor 0.75
```

---

## Tests

From repo root:

```bash
pip install -r requirements.txt
pytest
```

---

## Next step after reading this

1. Sign **G1–G3** on the three contracts (and stamp leakage audit on the data contract).  
2. Run **`./runner/run_round.sh init --campaign-dir runner/`**.  
3. Open **`runner/roles/planner.md`** and produce **`runner/state/NEXT_EXPERIMENT.md`**, then continue the loop above.
