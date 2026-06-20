# auto_train Harness Self-Audit — 2026-06-19

**Scope.** Comprehensive inspection of `campaigns/ip-commercial-new-te-round2/` (most recent campaign), with comparison against `smoke-test-creditcard` and `ip-commercial-new-te`. Five parallel Opus audit agents, each on a focused angle: state schema drift, memory-artifact write paths, trajectory-ledger integrity, mandatory-gate enforcement, Historian + explore/exploit behavior.

**Headline finding.** The documented architecture (Plan → Execute → **Review** → **Historian**) is not what actually runs. The two roles that provide cross-round learning — Reviewer (memory artifacts) and Historian (synthesis) — are effectively stubbed out in `auto_run.py`. The harness ran 18 rounds without the LLM Reviewer ever being called and without the LLM Historian ever being called. **Most of what differentiates `auto_train` from a vanilla AutoML loop is not currently executing.**

This must be fixed before Kaggle benchmark validation, or the benchmarks will measure a degenerate version of the system.

---

## P0 findings (broken core functionality)

### P0-1 — Historian role is a no-op stub

**Location:** `campaigns/ip-commercial-new-te-round2/auto_run.py:991–1003`

```python
if new_state.get("historian_trigger_pending"):
    print("  [Historian trigger pending — running historian...]")
    # Simple historian: just reset the trigger
    runner_driver.historian_finalize(
        campaign_dir=str(CAMPAIGN_DIR),
        trigger="periodic",
        patterns_added=0,
        assumptions_flagged=0,
    )
```

The comment is explicit: "Simple historian: just reset the trigger." No LLM call. No `STRATEGY_MEMO.md` write. No `PATTERN_BOOK.md` update. The driver correctly flagged `historian_trigger_pending=true` 36 times across the campaign; every one fired this stub.

**Evidence:** 0 `historian_finalize` events in `driver_events.jsonl`, `STRATEGY_MEMO.md` absent, `total_tokens.historian = 0`, `PATTERN_BOOK.md` count = 0, `ASSUMPTION_REGISTER.md` count = 0.

**Maximum observed `consecutive_discards`: 8** (rounds 9–16). Eight straight discards with no synthesis intervention is exactly the failure mode the Historian was designed to prevent.

### P0-2 — Reviewer LLM was never invoked

**Evidence:** `reviewer_tokens = 0` for all 18 rounds in `state/results.tsv`. The orchestrator/driver called `review_finalize()` directly with hardcoded verdict arguments instead of routing through the LLM Reviewer.

**Impact:** The Reviewer is the sole writer of `CAMPAIGN_JOURNAL.md` (mandatory append per round per `reviewer.md:131`), `DEAD_ENDS.md` (on discard), `NOTEBOOK.md`, and `ASSUMPTION_REGISTER.md` entries on `keep`. Because the Reviewer never ran:
- `CAMPAIGN_JOURNAL.md`, `DEAD_ENDS.md`, `NOTEBOOK.md`, `UNEXPLORED_TECHNIQUES.md` are **absent**.
- `ASSUMPTION_REGISTER.md` and `PATTERN_BOOK.md` exist but have `count: 0` (skeleton only) — there were 4 `keep` verdicts that should have produced assumption entries.

### P0-3 — Mandatory-tool gate is trivially bypassable

The gate logic in `runner_driver.py:619–629` is correct on paper: `tools_ran = []` if None (fail-closed); missing mandatory tools flip `verdict = "malformed"`. The bypass is structural — the driver **trusts the caller's `tools_ran` list with no execution receipt.**

**Concrete instance:** Round 1 commit `07dddd2c` was first submitted at `20:37:15Z` and correctly downgraded to `malformed` (`mandatory_gate_reason: "missing normalized tool(s) ['runner.tools.anomaly', 'runner.tools.bootstrap_ci']"`). **11 seconds later** at `20:37:26Z` the same commit was re-submitted with `mandatory_gate_reason: null` and verdict `keep`. No tool could have run in 11 seconds on this dataset (~300s minimum). Two further `keep` verdicts (rounds 3, 9, and 18 — including the current campaign best) show no anomaly/bootstrap_ci evidence in `auto_run.log` or `driver_events.jsonl`.

**Implication:** Every "validated" experiment in this campaign is unverified. The campaign's nominal best (`69fa2631`, val_lift_1pct=22.814) has no integrity proof.

### P0-4 — `EXPERIMENT_TREE.json` is missing 16 of 17 nodes

The tree was wiped at the `b18c236` "fresh restart" commit (419 lines deleted) and **never rebuilt from history**. Only the final keep round (`69fa263`) is present. UCB1 strategy scoring is operating on near-empty data — the strategy module is effectively blind.

### P0-5 — `results.tsv` and `driver_events.jsonl` mix two campaign runs

13 rows in the TSV correspond to commits on an **abandoned branch fork** (commit `749c93f` is a dangling git object per `git fsck --lost-found`). Plus 4 rows from the surviving 5-commit lineage. Plus 1 malformed duplicate of row 1. **Any downstream analysis treating the TSV as a single coherent campaign will silently include cross-contaminated data.**

### P0-6 — One partial round, silently lost

Commit `d7f286f` ("3-model CB+LGB+XGB rank-percentile ensemble") is on the current branch as an `experiment:` commit but has **zero** matching `review_finalize` events and **zero** rows in `results.tsv`. Staged but never executed/finalized.

---

## P1 findings (degraded learning, recoverable)

| ID | Finding | Evidence |
|---|---|---|
| P1-1 | `reviewer_tokens` = 0 for all 18 rounds; auto-estimation only fires when all three roles are zero. Reviewer cost silently dropped from `TOKEN_SUMMARY.txt`. | `state/results.tsv`; `_auto_estimate_round_tokens()` in driver |
| P1-2 | `UNEXPLORED_TECHNIQUES.md` not seeded at `init_campaign`; Planner's mandatory-when-consecutive_discards≥2 read silently fails. | `runner/campaign_template/state/` lacks the file; `runner_driver.init_campaign()` doesn't create it |
| P1-3 | `CAMPAIGN_STATE.json` was **manually patched** outside the driver in commit `cef2898` (consecutive_discards reset 8→0). State integrity is compromised. | `git show cef2898 -- state/CAMPAIGN_STATE.json` |
| P1-4 | `baseline_results/` campaign (50 rounds) has no token columns — entire prior run has zero cost attribution. | `baseline_results/results.tsv` schema |
| P1-5 | `bootstrap_ci: not run (discard, below threshold)` in baseline rounds 39, 41–42, 44–47 — driver only enforces gate on `keep`, but `EVAL_PROTOCOL.md` prose implies always required. Documentation ambiguity. | `baseline_results/REVIEW.md`; `runner_driver.py:619` |

---

## P2 findings (cosmetic/audit-trail)

- `REVIEW.md` body has zero entries; driver only updates frontmatter via regex (`runner_driver.py:731–744`).
- `driver_events.jsonl` has zero `historian_finalize` events — anyone querying the event log will (correctly but misleadingly) infer Historian never ran without seeing the stub-vs-trigger distinction.
- Schema drift: `EXPERIMENT_TREE.json` and `driver_events.jsonl` exist in round2 but not in older campaigns; older campaigns have `STRATEGY_MEMO.md` etc. that round2 lacks. No migration path.

---

## State-file inventory matrix

| File | smoke-test | te (older) | round2 (latest) |
|---|---|---|---|
| CAMPAIGN_STATE.json | ✅ | ✅ | ✅ |
| results.tsv | ✅ | ✅ | ✅ (mixed runs) |
| ASSUMPTION_REGISTER.md | ✅ | ❌ | ✅ (empty, count:0) |
| PATTERN_BOOK.md | ✅ | ❌ | ✅ (empty, count:0) |
| EXPERIMENT_TREE.json | ❌ | ❌ | ✅ (16/17 nodes missing) |
| REVIEW.md | ✅ | ✅ | ✅ (frontmatter only) |
| NEXT_EXPERIMENT.md | ✅ | ✅ | ✅ |
| **DEAD_ENDS.md** | ✅ | ✅ | **❌** |
| **NOTEBOOK.md** | ✅ | ✅ | **❌** |
| **CAMPAIGN_JOURNAL.md** | ✅ | ✅ | **❌** |
| **UNEXPLORED_TECHNIQUES.md** | ✅ | ✅ | **❌** |
| **STRATEGY_MEMO.md** | ✅ | ❌ | **❌** |
| TOKEN_SUMMARY.txt | ✅ | ❌ | ✅ (under-counts) |
| driver_events.jsonl | ❌ | ❌ | ✅ (mixed runs) |

---

## Implications for Kaggle benchmark validation

**Cannot be measured from the current state of the harness:**
- Historian bottleneck diagnosis quality
- Whether `STRATEGY_MEMO.md §4` causes Planner strategy pivots at plateau
- Whether `UNEXPLORED_TECHNIQUES.md` frontier reasoning diversifies experiment selection
- Whether C2 triggers lead to genuine strategy shifts vs. continued exploitation
- Cross-round learning of any kind (because Reviewer + Historian don't run)
- True token cost (Reviewer cost is dropped systematically)

**Can be measured (these worked):**
- Inline Planner experiment-selection quality (planning happens inside `auto_run.py` directly, not via the role file)
- Executor code generation reliability
- Verdict gate firing on first submission (the bypass is on re-submission)
- Trigger detection (the trigger fires; the action is the stub)

If we run Kaggle benchmarks now, we'd be measuring "auto_train without its differentiating components." The story would be weaker than the system's actual potential.

---

## Closure — fixes landed 2026-06-20

All five P0 audit findings have been remediated on branch `fix/p0-harness-audit`,
in dependency order F4 → F5 → F3 → F1 → F2 plus a follow-up commit addressing
five critical code-review findings before the smoke validation:

| Fix | Commit | Summary |
|-----|--------|---------|
| F4 | `dfd4ecd` | Seed memory-artifact skeletons (UNEXPLORED_TECHNIQUES, DEAD_ENDS, NOTEBOOK, CAMPAIGN_JOURNAL) at init |
| F5 | `f4bcde1` | Rebuild EXPERIMENT_TREE.json from results.tsv on init/restart |
| F3 | `d387cb5` | Tool-execution receipts + receipt cross-check in review_finalize |
| F1 | `b05b44e` | historian_finalize asserts STRATEGY_MEMO.md was written this round |
| F2 | `169e823` | review_finalize asserts CAMPAIGN_JOURNAL/REVIEW.md/ASSUMPTION_REGISTER written this round |
| Code-review | `0a1f5bc` | Substring matching, regex `...` literal, bare-tool normalize, blank-line tolerance, role-md wrapper docs |

### Reinterpretation note

The audit cited `campaigns/ip-commercial-new-te-round2/auto_run.py:991–1003` as
the Historian stub site. That file was deleted in commit `6c8bcfc` ("refactor:
replace auto_run.py with orchestrator harness"); on `main`, no programmatic
LLM-call layer exists — the Claude orchestrator agent is the loop. F1 and F2
were therefore implemented as **post-finalize artifact assertions** (per the
audit's own closing recommendation): the driver verifies the role's required
writes happened in this round, rejecting the finalize call otherwise. F3, F4,
F5 applied as audit-literal code defects.

### Smoke campaign — `campaigns/p0-fix-smoke/` (3 rounds, 2026-06-20)

Round-by-round outcome:

- **Round 1 (A_imbalance):** LightGBM n_est=600, lr=0.02, scale_pos_weight=578.
  val_pr_auc=0.8156, anomaly clean, bootstrap CI=[0.747, 0.889]. **Verdict: keep.**
  F2/F3/F4/F5 all enforced and accepted.
- **Round 2 (A_hp, n_est=100):** Δ=-0.094 (clear undertraining). Reviewer
  submitted discard; tools clean. **Verdict: discard, rolled back.** F2 verified
  the discard-mode artifacts (journal + review body).
- **Round 3 (A_hp, n_est=650):** Δ=+0.0013 (within noise_floor=0.005).
  Reviewer claimed keep; **driver mechanically overrode to discard via
  noise_floor_gate.** F2 verified the discard-mode artifacts. budget exhausted,
  halt fired.

State verification (all green):

- `CAMPAIGN_JOURNAL.md`: 3 `## Round N` entries.
- `DEAD_ENDS.md`: 1 entry (round 2).
- `ASSUMPTION_REGISTER.md`: count=2 (A-1-1, A-3-1).
- `results.tsv`: reviewer_tokens > 0 for every row (6000, 5500, 5800).
- `EXPERIMENT_TREE.json`: 4 nodes (ROOT + 3 commits with strategy_class set).
- `driver_events.jsonl`: 3 plan_check, 8 tool_run, 3 review_finalize.

Live adversarial test from a Python REPL: a `review_finalize` call with
`tools_ran=[runner.tools.anomaly, runner.tools.bootstrap_ci]` and verdict=keep
was issued AFTER stamping a fresh `round_started_at` but WITHOUT staging any
new tool_run receipts. The driver flipped verdict → malformed with reason
`mandatory_tools: claimed-but-no-receipt [...] since round_started_at=...`,
emitted a `tools_ran_unverified` event, and refused the keep. F3 enforcement
is structurally sound.

Live F1 test: three sub-cases — missing memo, memo with missing section,
complete memo — verified rejection on the first two and acceptance on the
third. F1 enforcement is structurally sound.

### Test suite

`python -m pytest tests/ --ignore=tests/tools/test_optuna_search.py
--ignore=tests/tools/test_feature_selection.py --ignore=tests/tools/test_shap_report.py`
— **299 passing** (was 259 baseline pre-F4). 36 new tests added across F1–F5
plus 4 for the code-review fixes.

### Outstanding (P1 follow-up)

The audit's P1 findings (F6 cross-branch refuse, F7 state-edit stamping,
F8 orphan-round reconcile) and the 10 lower-severity code-review findings
(timeout on subprocess, ISO-Z lex-format hardening, log.py helper reuse,
single-source-of-truth for role headings, etc.) are tracked for a follow-up
branch `fix/p1-state-integrity`.

---

## Recommended fixes before Kaggle validation

| # | Fix | Severity | Effort |
|---|---|---|---|
| F1 | Replace Historian stub in `auto_run.py:991–1003` with a real LLM invocation that reads `runner/roles/historian.md` and writes `STRATEGY_MEMO.md`, `PATTERN_BOOK.md`, `ASSUMPTION_REGISTER.md` updates | P0 | 0.5 day |
| F2 | Wire the LLM Reviewer into the orchestrator so `CAMPAIGN_JOURNAL.md`, `DEAD_ENDS.md`, `NOTEBOOK.md`, `ASSUMPTION_REGISTER.md` actually get written; populate `reviewer_tokens` from real usage | P0 | 1 day |
| F3 | Add tool-execution receipts to `driver_events.jsonl` (one event per actual subprocess run), and have `review_finalize` cross-check `tools_ran` against receipts | P0 | 0.5 day |
| F4 | Seed `UNEXPLORED_TECHNIQUES.md`, `DEAD_ENDS.md`, `NOTEBOOK.md`, `CAMPAIGN_JOURNAL.md` skeletons in `init_campaign()` so absent-file silent-skip stops happening | P0 | 1 hour |
| F5 | Rebuild `EXPERIMENT_TREE.json` from `results.tsv` on `init` / restart so UCB1 has real history | P0 | 2 hours |
| F6 | Refuse to start a new round if `results.tsv` and `driver_events.jsonl` contain commits not reachable from the current branch tip — forces clean restarts | P1 | 1 hour |
| F7 | Forbid manual edits to `CAMPAIGN_STATE.json` (or stamp every change with a driver event) | P1 | 1 hour |
| F8 | Fix the orphan partial round (`d7f286f`) — either run it or revert the commit | P2 | 30 min |

**Total estimated effort: ~3.5 days** before benchmarks are meaningful.

---

## What this means strategically

You were going to validate before borrowing. The audit reinforces that decision and adds urgency: **fix the harness to actually execute its documented architecture before you run any benchmark whose results you'll cite externally.** Otherwise, the receipts you build will be receipts for a degenerate version of the system, and you'll have to re-run them after the fixes anyway.

The borrowing brainstorm (task #3) should now also consider: which cacm patterns specifically help guard against this class of failure? Hooks that emit "this artifact must exist after this phase" assertions are exactly what would have caught the Historian stub and Reviewer-not-invoked issues at round 1.
