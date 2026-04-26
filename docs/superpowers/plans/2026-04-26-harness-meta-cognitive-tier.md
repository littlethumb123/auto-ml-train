# Harness Meta-Cognitive Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reflective Historian role, Assumption Register, Pattern Book, evidence-first Reviewer, and token tracking to the autonomous ML harness to eliminate systematic multi-round blind spots.

**Architecture:** Four-role harness (Planner/Executor/Reviewer/Historian) with Historian triggering every K=10 rounds and on C2 plateau, replacing the `c2_pending_diagnose → A_diagnose` protocol with trajectory-level synthesis. New state artifacts (ASSUMPTION_REGISTER.md, PATTERN_BOOK.md, STRATEGY_MEMO.md) give the Planner assumption-aware, pattern-informed context. Token costs are tracked in results.tsv and surfaced as TOKEN_SUMMARY.txt — informational only, not a constraint.

**Tech Stack:** Python 3.10+, pytest, pathlib, json, existing runner_driver.py state machine

**Spec:** `docs/superpowers/specs/2026-04-26-harness-meta-cognitive-tier-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `runner/runner_driver.py` | Modify | v2 state init; historian_run/finalize; review_finalize token params + historian trigger |
| `log.py` | Modify | Token columns in results.tsv header and append_result |
| `runner/tools/token_summary.py` | **Create** | Reads results.tsv token columns, writes TOKEN_SUMMARY.txt |
| `runner/roles/historian.md` | **Create** | Full Historian role prompt (10-step procedure) |
| `runner/roles/reviewer.md` | Modify | Evidence-first order; assumption registration; discard falsification check |
| `runner/roles/planner.md` | Modify | New inputs; assumption-aware novelty check; pattern-informed strategy |
| `runner/run_round.sh` | Modify | New `historian` and `historian-finalize` stages |
| `runner/tools/schema.py` | Modify | validate_eval_protocol historian_interval; new validate_assumption_register |
| `runner/RUNNER.md` | Modify | Historian role; new state files |
| `runner/AGENTS.md` | Modify | Historian fossil record entry |
| `runner/contracts/EVAL_PROTOCOL.md` | Modify | historian_interval field; remove A_diagnose from action_types |
| `tests/test_runner_driver.py` | Modify | v2 init assertions; test_review_finalize token + historian trigger |
| `tests/test_historian_driver.py` | **Create** | Tests for historian_run, historian_finalize, v1→v2 migration |
| `tests/tools/test_token_summary.py` | **Create** | Tests for token_summary.py |
| `tests/test_log.py` | Modify | Token column assertions |
| `tests/safety/test_diagnose_after_c2.py` | **Delete** | Old c2_pending_diagnose protocol replaced |
| `tests/safety/test_historian_after_c2.py` | **Create** | New historian-trigger invariant tests |

---

## Task 1: CAMPAIGN_STATE.json v2 — New Fields at init + Skeleton Artifacts

**Files:**
- Modify: `runner/runner_driver.py` — `init_campaign()`, add two skeleton helpers
- Modify: `tests/test_runner_driver.py` — update init assertions

Context: `init_campaign()` currently builds a v1 state dict with `c2_pending_diagnose`. We bump to v2 by adding historian fields, removing `c2_pending_diagnose`, and writing skeleton ASSUMPTION_REGISTER.md and PATTERN_BOOK.md to the state dir.

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_runner_driver.py`:

```python
def test_init_creates_v2_state_fields(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["$schema_version"] == 2
    assert state["rounds_since_last_historian"] == 0
    assert "historian_interval" in state
    assert state["historian_interval"] >= 1
    assert state["historian_trigger_pending"] is False
    assert state["total_tokens"] == {"planner": 0, "executor": 0, "reviewer": 0, "historian": 0}
    assert "c2_pending_diagnose" not in state


def test_init_creates_assumption_register_skeleton(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    ar = (campaign / "state" / "ASSUMPTION_REGISTER.md")
    assert ar.exists()
    text = ar.read_text()
    assert "schema_version: 1" in text
    assert "count: 0" in text


def test_init_creates_pattern_book_skeleton(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    pb = (campaign / "state" / "PATTERN_BOOK.md")
    assert pb.exists()
    text = pb.read_text()
    assert "schema_version: 1" in text
    assert "count: 0" in text


def test_init_historian_interval_from_eval_protocol(tmp_path: Path):
    """When historian_interval is explicit in EVAL_PROTOCOL, use it."""
    ep_with_interval = EVAL_PROTOCOL.replace(
        "approved_at:", "historian_interval: 7\napproved_at:"
    )
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(ep_with_interval)
    runner_driver.init_campaign(campaign_dir=str(root))
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["historian_interval"] == 7


def test_init_historian_interval_default_for_small_budget(campaign: Path):
    """budget_total=3 < 50 → max(5, int(3 * 0.10)) = 5."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    # EVAL_PROTOCOL fixture has max_experiments: 3
    assert state["historian_interval"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/jupyter/Thinkubator/auto_train
python -m pytest tests/test_runner_driver.py::test_init_creates_v2_state_fields tests/test_runner_driver.py::test_init_creates_assumption_register_skeleton tests/test_runner_driver.py::test_init_creates_pattern_book_skeleton tests/test_runner_driver.py::test_init_historian_interval_from_eval_protocol tests/test_runner_driver.py::test_init_historian_interval_default_for_small_budget -v
```

Expected: FAIL — `KeyError: '$schema_version' != 2` or `AssertionError`

- [ ] **Step 3: Add skeleton helpers and update init_campaign**

In `runner/runner_driver.py`, add these two helper functions before `init_campaign`:

```python
def _assumption_register_skeleton(campaign_id: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        f'campaign_id: "{campaign_id}"\n'
        "count: 0\n"
        'last_updated: ""\n'
        "---\n\n"
        "<!-- Reviewer appends entries on every keep verdict. -->\n"
        "<!-- Format: ### A-<round>-<seq> — <short name> -->\n"
    )


def _pattern_book_skeleton(campaign_id: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        f'campaign_id: "{campaign_id}"\n'
        "count: 0\n"
        'last_updated: ""\n'
        "---\n\n"
        "<!-- Historian appends entries during periodic/C2 runs. -->\n"
        "<!-- Format: ### P-<seq> — <pattern name> -->\n"
    )
```

Replace the `state = { ... }` block in `init_campaign` (currently lines ~122–136) with this complete version:

```python
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # historian_interval: from EVAL_PROTOCOL if explicit, else compute from budget
    ep_historian_interval = eval_fm.get("historian_interval")
    if ep_historian_interval is not None:
        historian_interval = int(ep_historian_interval)
    elif int(budgets.get("max_experiments", 100)) < 50:
        historian_interval = max(5, int(int(budgets.get("max_experiments", 100)) * 0.10))
    else:
        historian_interval = 10

    state = {
        "$schema_version": 2,
        "campaign_id": problem_fm.get("campaign_id"),
        "round": 0,
        "exp_id_counter": 0,
        "last_commit": None,
        "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0,
        "rounds_since_last_historian": 0,
        "historian_interval": historian_interval,
        "last_historian_round": None,
        "historian_trigger_pending": False,
        "total_tokens": {"planner": 0, "executor": 0, "reviewer": 0, "historian": 0},
        "budget_used": 0,
        "budget_total": int(budgets.get("max_experiments", 100)),
        "created_at": now,
        "updated_at": now,
    }
    state_dir = camp / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "CAMPAIGN_STATE.json").write_text(json.dumps(state, indent=2) + "\n")

    results = state_dir / "results.tsv"
    if not results.exists():
        results_columns = list(eval_fm.get("results_columns") or []) or None
        results.write_text(log.make_header(results_columns))

    # Create skeleton state artifacts for the new meta-cognitive tier
    ar_path = state_dir / "ASSUMPTION_REGISTER.md"
    if not ar_path.exists():
        ar_path.write_text(_assumption_register_skeleton(state["campaign_id"]))
    pb_path = state_dir / "PATTERN_BOOK.md"
    if not pb_path.exists():
        pb_path.write_text(_pattern_book_skeleton(state["campaign_id"]))

    return state
```

Note: the `eval_fm, _` and `budgets` variables are already read above in the existing code. Remove the now-redundant second `budgets` extraction if present.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_runner_driver.py::test_init_creates_v2_state_fields tests/test_runner_driver.py::test_init_creates_assumption_register_skeleton tests/test_runner_driver.py::test_init_creates_pattern_book_skeleton tests/test_runner_driver.py::test_init_historian_interval_from_eval_protocol tests/test_runner_driver.py::test_init_historian_interval_default_for_small_budget -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All previously passing tests still pass. The `test_init_creates_campaign_state_and_results_header` test still passes because it only checks `campaign_id`, `round`, `budget_total`, and the results header prefix.

- [ ] **Step 6: Commit**

```bash
git add runner/runner_driver.py tests/test_runner_driver.py
git commit -m "feat(state): bump CAMPAIGN_STATE to schema_version 2 with historian fields and skeleton artifacts"
```

---

## Task 2: Token Columns in log.py

**Files:**
- Modify: `log.py` — `make_header()`, `append_result()`
- Modify: `tests/test_log.py` — token column assertions

Context: results.tsv gains 5 new trailing columns: `planner_tokens`, `executor_tokens`, `reviewer_tokens`, `historian_tokens`, `round_total_tokens`. The `append_result()` function gets 4 new optional int params. Existing tests use `startswith()` assertions and won't break.

- [ ] **Step 1: Write the failing tests**

Read `tests/test_log.py` first to see existing test structure, then add at the bottom:

```python
def test_make_header_includes_token_columns():
    header = log.make_header(["val_pr_auc"])
    cols = header.strip().split("\t")
    assert "planner_tokens" in cols
    assert "executor_tokens" in cols
    assert "reviewer_tokens" in cols
    assert "historian_tokens" in cols
    assert "round_total_tokens" in cols
    # Token columns come after description (last structural suffix)
    desc_idx = cols.index("description")
    pt_idx = cols.index("planner_tokens")
    assert pt_idx > desc_idx
    assert cols[-1] == "round_total_tokens"


def test_append_result_writes_token_columns(tmp_path: Path):
    # Build a minimal campaign dir
    camp = tmp_path / "runner"
    (camp / "contracts").mkdir(parents=True)
    (camp / "state").mkdir()
    # Write a minimal EVAL_PROTOCOL so get_results_columns works
    (camp / "contracts" / "EVAL_PROTOCOL.md").write_text(
        "---\nschema_version: 1\ncampaign_id: t\nresults_columns: [val_pr_auc]\napproved_at: 2026-04-26\n---\n"
    )
    state = {
        "$schema_version": 2, "campaign_id": "t", "round": 0, "exp_id_counter": 0,
        "last_commit": None, "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0, "budget_used": 0, "budget_total": 10,
        "created_at": "2026-04-26T00:00:00Z", "updated_at": "2026-04-26T00:00:00Z",
    }
    (camp / "state" / "CAMPAIGN_STATE.json").write_text(json.dumps(state) + "\n")
    (camp / "state" / "results.tsv").write_text(log.make_header(["val_pr_auc"]))

    log.append_result(
        commit="abc123",
        metrics={"val_pr_auc": 0.8},
        status="keep",
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lgbm",
        n_features=5,
        campaign_dir=str(camp),
        primary_metric_name="val_pr_auc",
        planner_tokens=100,
        executor_tokens=200,
        reviewer_tokens=150,
        historian_tokens=50,
    )

    lines = (camp / "state" / "results.tsv").read_text().splitlines()
    assert len(lines) == 2  # header + 1 data row
    headers = lines[0].split("\t")
    data = lines[1].split("\t")
    assert data[headers.index("planner_tokens")] == "100"
    assert data[headers.index("executor_tokens")] == "200"
    assert data[headers.index("reviewer_tokens")] == "150"
    assert data[headers.index("historian_tokens")] == "50"
    assert data[headers.index("round_total_tokens")] == "500"


def test_append_result_token_defaults_to_zero(tmp_path: Path):
    camp = tmp_path / "runner"
    (camp / "contracts").mkdir(parents=True)
    (camp / "state").mkdir()
    (camp / "contracts" / "EVAL_PROTOCOL.md").write_text(
        "---\nschema_version: 1\ncampaign_id: t\nresults_columns: [val_pr_auc]\napproved_at: 2026-04-26\n---\n"
    )
    state = {
        "$schema_version": 2, "campaign_id": "t", "round": 0, "exp_id_counter": 0,
        "last_commit": None, "last_verdict": None,
        "best_so_far": {"commit": None, "primary_metric": None},
        "consecutive_discards": 0, "budget_used": 0, "budget_total": 10,
        "created_at": "2026-04-26T00:00:00Z", "updated_at": "2026-04-26T00:00:00Z",
    }
    (camp / "state" / "CAMPAIGN_STATE.json").write_text(json.dumps(state) + "\n")
    (camp / "state" / "results.tsv").write_text(log.make_header(["val_pr_auc"]))

    # Call without token params — should default to 0
    log.append_result(
        commit="abc",
        metrics={"val_pr_auc": 0.8},
        status="keep",
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lgbm",
        n_features=5,
        campaign_dir=str(camp),
        primary_metric_name="val_pr_auc",
    )
    lines = (camp / "state" / "results.tsv").read_text().splitlines()
    headers = lines[0].split("\t")
    data = lines[1].split("\t")
    assert data[headers.index("round_total_tokens")] == "0"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_log.py::test_make_header_includes_token_columns tests/test_log.py::test_append_result_writes_token_columns tests/test_log.py::test_append_result_token_defaults_to_zero -v
```

Expected: FAIL — `AssertionError: 'planner_tokens' not in ...`

- [ ] **Step 3: Update log.py**

In `log.py`, add the token column list after `_LEGACY_METRIC_COLUMNS`:

```python
_TOKEN_COLUMNS = [
    "planner_tokens", "executor_tokens", "reviewer_tokens",
    "historian_tokens", "round_total_tokens",
]
```

Replace `make_header()` with:

```python
def make_header(results_columns: list[str] | None) -> str:
    metric_cols = results_columns if results_columns is not None else _LEGACY_METRIC_COLUMNS
    return "\t".join(_STRUCTURAL_PREFIX + metric_cols + _STRUCTURAL_SUFFIX + _TOKEN_COLUMNS) + "\n"
```

Replace `append_result()` signature and body. The new signature:

```python
def append_result(
    commit: str,
    metrics: dict,
    status: Verdict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
    primary_metric_name: str = "val_pr_auc",
    direction: Direction = "maximize",
    planner_tokens: int = 0,
    executor_tokens: int = 0,
    reviewer_tokens: int = 0,
    historian_tokens: int = 0,
) -> None:
```

In the row assembly section, add `token_cells` and append to each row variant. For the legacy schema path, replace the `row = "\t".join([...]) + "\n"` with:

```python
    round_total = planner_tokens + executor_tokens + reviewer_tokens + historian_tokens
    token_cells = [
        str(planner_tokens), str(executor_tokens), str(reviewer_tokens),
        str(historian_tokens), str(round_total),
    ]

    if results_columns is None:
        row = "\t".join([
            commit,
            f"{float(metrics.get('val_pr_auc', 0.0))}",
            f"{float(metrics.get('lift_at_10', 0.0))}",
            f"{float(metrics.get('macro_f1', 0.0))}",
            f"{float(metrics.get('val_f1', 0.0))}",
            status,
            str(int(n_features)),
            model_family,
            action_type,
            _clean(hypothesis),
            _clean(description),
        ] + token_cells) + "\n"
    else:
        metric_cells = [_metric_val(col) for col in results_columns]
        row = "\t".join(
            [commit]
            + metric_cells
            + [status, str(int(n_features)), model_family, action_type,
               _clean(hypothesis), _clean(description)]
            + token_cells
        ) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_log.py -v
```

Expected: All tests pass including the three new ones.

- [ ] **Step 5: Commit**

```bash
git add log.py tests/test_log.py
git commit -m "feat(log): add planner/executor/reviewer/historian token columns to results.tsv"
```

---

## Task 3: token_summary.py Tool

**Files:**
- Create: `runner/tools/token_summary.py`
- Create: `tests/tools/test_token_summary.py`

Context: After each `review_finalize`, the driver calls `write_token_summary()` to produce `state/TOKEN_SUMMARY.txt` — a one-line digest the Planner reads as informational signal.

- [ ] **Step 1: Write the failing tests**

Create `tests/tools/test_token_summary.py`:

```python
"""Tests for runner.tools.token_summary."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import token_summary


@pytest.fixture
def camp(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "state").mkdir(parents=True)
    return root


def test_write_token_summary_no_results_file(camp: Path):
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    assert "no results yet" in result
    assert (camp / "state" / "TOKEN_SUMMARY.txt").exists()


def test_write_token_summary_no_token_columns(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        "commit\tval_pr_auc\tstatus\n"
        "abc\t0.8\tkeep\n"
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    assert "not enabled" in result
    assert (camp / "state" / "TOKEN_SUMMARY.txt").exists()


def _tsv_with_tokens(rows: list[tuple]) -> str:
    header = (
        "commit\tval_pr_auc\tstatus\tn_features\tmodel_family\taction_type\t"
        "hypothesis\tdescription\tplanner_tokens\texecutor_tokens\t"
        "reviewer_tokens\thistorian_tokens\tround_total_tokens\n"
    )
    lines = []
    for commit, val, status, action, pt, et, rt, ht in rows:
        total = pt + et + rt + ht
        lines.append(
            f"{commit}\t{val}\t{status}\t10\tlgbm\t{action}\th\td\t{pt}\t{et}\t{rt}\t{ht}\t{total}\n"
        )
    return header + "".join(lines)


def test_write_token_summary_computes_totals(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        _tsv_with_tokens([
            ("abc", 0.80, "keep", "A_hp", 100, 200, 150, 0),
            ("def", 0.81, "keep", "A_hp", 120, 180, 130, 0),
        ])
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    # Total = 450 + 430 = 880
    assert "880" in result or "880" in (camp / "state" / "TOKEN_SUMMARY.txt").read_text()
    assert "avg/round" in result
    assert (camp / "state" / "TOKEN_SUMMARY.txt").read_text().strip() == result.strip()


def test_write_token_summary_historian_avg_excludes_zero_rounds(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        _tsv_with_tokens([
            ("r1", 0.80, "keep", "A_hp", 100, 200, 150, 300),   # historian ran
            ("r2", 0.81, "keep", "A_hp", 100, 200, 150, 0),      # no historian
            ("r3", 0.82, "keep", "A_hp", 100, 200, 150, 600),    # historian ran
        ])
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    # historian avg = (300 + 600) // 2 = 450
    assert "historian avg" in result
    # Avg should reflect only historian runs, not zeros
    # 450 → "450" in output
    assert "450" in result


def test_write_token_summary_format(camp: Path):
    (camp / "state" / "results.tsv").write_text(
        _tsv_with_tokens([("r1", 0.8, "keep", "A_hp", 1000, 2000, 1500, 0)])
    )
    result = token_summary.write_token_summary(campaign_dir=str(camp))
    assert "Campaign tokens" in result
    assert "total:" in result
    assert "avg/round:" in result
    assert "top cost:" in result
    assert "trend:" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/tools/test_token_summary.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'runner.tools.token_summary'`

- [ ] **Step 3: Create runner/tools/token_summary.py**

```python
"""runner/tools/token_summary.py — token cost digest for Planner consumption.

Reads results.tsv token columns and writes state/TOKEN_SUMMARY.txt.
Called after each review_finalize. Non-critical: caller should catch all exceptions.
"""
from __future__ import annotations

import csv
from pathlib import Path


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def write_token_summary(campaign_dir: str = "runner/") -> str:
    """Read results.tsv token columns and write TOKEN_SUMMARY.txt.

    Returns the summary line written (also written to file).
    """
    camp = Path(campaign_dir)
    results_path = camp / "state" / "results.tsv"
    summary_path = camp / "state" / "TOKEN_SUMMARY.txt"

    if not results_path.exists():
        summary = "Campaign tokens — no results yet"
        summary_path.write_text(summary + "\n")
        return summary

    rows: list[dict] = []
    with results_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if "round_total_tokens" in (reader.fieldnames or []):
                rows.append(row)

    if not rows or "round_total_tokens" not in (rows[0] if rows else {}):
        summary = "Campaign tokens — token tracking not enabled (no token columns in results.tsv)"
        summary_path.write_text(summary + "\n")
        return summary

    def _int(row: dict, col: str) -> int:
        try:
            return int(row.get(col, 0) or 0)
        except (TypeError, ValueError):
            return 0

    totals = [_int(r, "round_total_tokens") for r in rows]
    historian_cols = [_int(r, "historian_tokens") for r in rows]

    grand_total = sum(totals)
    n_rounds = len(totals)
    avg_per_round = grand_total // n_rounds if n_rounds else 0

    historian_runs = [t for t in historian_cols if t > 0]
    historian_avg = sum(historian_runs) // len(historian_runs) if historian_runs else 0

    max_idx = totals.index(max(totals)) if totals else 0
    top_round = max_idx + 1
    top_cost = totals[max_idx] if totals else 0
    top_action = rows[max_idx].get("action_type", "unknown") if rows else "unknown"

    recent = totals[-10:]
    recent_avg = sum(recent) // len(recent) if recent else 0
    if avg_per_round == 0:
        trend = "stable"
    elif abs(recent_avg - avg_per_round) < avg_per_round * 0.20:
        trend = "stable"
    elif recent_avg > avg_per_round:
        trend = "rising"
    else:
        trend = "falling"

    summary = (
        f"Campaign tokens — total: {_fmt(grand_total)} | avg/round: {_fmt(avg_per_round)} | "
        f"historian avg: {_fmt(historian_avg)} | "
        f"top cost: r{top_round} ({top_action}, {_fmt(top_cost)}) | "
        f"trend: {trend} (last {len(recent)} rounds avg={_fmt(recent_avg)})"
    )
    summary_path.write_text(summary + "\n")
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/tools/test_token_summary.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/token_summary.py tests/tools/test_token_summary.py
git commit -m "feat(tools): add token_summary.py — per-round cost digest for Planner"
```

---

## Task 4: historian_run() and historian_finalize() in runner_driver.py

**Files:**
- Modify: `runner/runner_driver.py` — two new public functions
- Create: `tests/test_historian_driver.py`

Context: `historian_run()` reads state, determines trigger type, and returns metadata the outer loop passes to the Historian agent. `historian_finalize()` updates state after the Historian completes. `historian_run()` also migrates v1 state to v2 on first call.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_historian_driver.py`:

```python
"""Tests for historian_run() and historian_finalize() in runner_driver."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

EVAL_WITH_HISTORIAN_INTERVAL = EVAL_PROTOCOL.replace(
    "approved_at:", "historian_interval: 5\napproved_at:"
)


@pytest.fixture
def campaign_v2(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_HISTORIAN_INTERVAL)
    runner_driver.init_campaign(campaign_dir=str(root))
    return root


@pytest.fixture
def campaign_v1(tmp_path: Path) -> Path:
    """Campaign with manually-written v1 state (simulates pre-upgrade campaign)."""
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_HISTORIAN_INTERVAL)
    v1_state = {
        "$schema_version": 1,
        "campaign_id": "tiny",
        "round": 5,
        "exp_id_counter": 5,
        "last_commit": "abc",
        "last_verdict": "keep",
        "best_so_far": {"commit": "abc", "primary_metric": 0.8},
        "consecutive_discards": 0,
        "c2_pending_diagnose": False,
        "budget_used": 5,
        "budget_total": 3,
        "created_at": "2026-04-21T00:00:00Z",
        "updated_at": "2026-04-21T00:00:00Z",
    }
    (root / "state" / "CAMPAIGN_STATE.json").write_text(json.dumps(v1_state, indent=2) + "\n")
    return root


def test_historian_run_returns_periodic_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    # Force rounds_since to reach interval
    state["rounds_since_last_historian"] = state["historian_interval"]
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["status"] == "ok"
    assert result["trigger"] in ("periodic", "periodic+c2")


def test_historian_run_returns_c2_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 3  # plateau_trigger in fixture
    state["rounds_since_last_historian"] = 0  # periodic not yet reached
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["status"] == "ok"
    assert result["trigger"] == "c2"


def test_historian_run_returns_combined_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 3
    state["rounds_since_last_historian"] = state["historian_interval"]
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["trigger"] == "periodic+c2"


def test_historian_run_includes_rounds_covered(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["last_historian_round"] = 3
    state["round"] = 8
    state["rounds_since_last_historian"] = 5
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_run(campaign_dir=str(campaign_v2))
    assert result["rounds_covered"] == [4, 8]


def test_historian_finalize_resets_rounds_and_clears_trigger(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["rounds_since_last_historian"] = 5
    state["historian_trigger_pending"] = True
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    result = runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        patterns_added=2,
        assumptions_flagged=1,
        tokens_used=50_000,
    )
    assert result["status"] == "ok"

    state_after = json.loads(state_path.read_text())
    assert state_after["rounds_since_last_historian"] == 0
    assert state_after["historian_trigger_pending"] is False
    assert state_after["last_historian_round"] == state_after["round"]


def test_historian_finalize_stores_pending_tokens(campaign_v2: Path):
    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=75_000,
    )
    state = json.loads((campaign_v2 / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state.get("pending_historian_tokens") == 75_000
    assert state["total_tokens"]["historian"] == 75_000


def test_historian_finalize_c2_resets_consecutive_discards(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 5
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="c2",
        tokens_used=0,
    )
    state_after = json.loads(state_path.read_text())
    assert state_after["consecutive_discards"] == 0


def test_historian_finalize_periodic_only_does_not_reset_discards(campaign_v2: Path):
    state_path = campaign_v2 / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 2
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.historian_finalize(
        campaign_dir=str(campaign_v2),
        trigger="periodic",
        tokens_used=0,
    )
    state_after = json.loads(state_path.read_text())
    assert state_after["consecutive_discards"] == 2  # unchanged for periodic-only


def test_historian_run_migrates_v1_state(campaign_v1: Path):
    state_path = campaign_v1 / "state" / "CAMPAIGN_STATE.json"
    # Force trigger so historian_run runs (set consecutive_discards)
    state = json.loads(state_path.read_text())
    state["consecutive_discards"] = 3
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.historian_run(campaign_dir=str(campaign_v1))

    state_after = json.loads(state_path.read_text())
    assert state_after["$schema_version"] == 2
    assert "rounds_since_last_historian" in state_after
    assert "historian_interval" in state_after
    assert "total_tokens" in state_after
    assert "c2_pending_diagnose" not in state_after
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_historian_driver.py -v
```

Expected: FAIL — `AttributeError: module 'runner.runner_driver' has no attribute 'historian_run'`

- [ ] **Step 3: Add historian_run() and historian_finalize() to runner_driver.py**

Add these two functions after `resolve_c2()` in `runner/runner_driver.py`:

```python
def historian_run(campaign_dir: str = "runner/") -> dict[str, Any]:
    """Return metadata for the outer loop to pass to the Historian agent.

    Migrates v1 CAMPAIGN_STATE.json to v2 schema on first call if needed.
    """
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        raise DriverError("CAMPAIGN_STATE.json not found — run init first")

    state = json.loads(state_path.read_text())

    # Migrate v1 → v2 if needed
    if state.get("$schema_version", 1) < 2:
        import datetime as _dt

        eval_fm_mig, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
        budgets_mig = eval_fm_mig.get("budgets") or {}
        budget_total_mig = int(budgets_mig.get("max_experiments", 100))
        ep_interval = eval_fm_mig.get("historian_interval")
        if ep_interval is not None:
            hist_interval = int(ep_interval)
        elif budget_total_mig < 50:
            hist_interval = max(5, int(budget_total_mig * 0.10))
        else:
            hist_interval = 10

        state["$schema_version"] = 2
        state.setdefault("rounds_since_last_historian", int(state.get("round", 0)))
        state.setdefault("historian_interval", hist_interval)
        state.setdefault("last_historian_round", None)
        state.setdefault("historian_trigger_pending", False)
        state.setdefault(
            "total_tokens",
            {"planner": 0, "executor": 0, "reviewer": 0, "historian": 0},
        )
        state.pop("c2_pending_diagnose", None)
        state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    eval_fm, _ = parse_frontmatter(camp / "contracts" / "EVAL_PROTOCOL.md")
    plateau_trigger = int(
        (eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3)
    )

    is_periodic = (
        int(state.get("rounds_since_last_historian", 0))
        >= int(state.get("historian_interval", 10))
    )
    is_c2 = int(state.get("consecutive_discards", 0)) >= plateau_trigger

    if is_periodic and is_c2:
        trigger = "periodic+c2"
    elif is_c2:
        trigger = "c2"
    else:
        trigger = "periodic"

    last_historian_round = int(state.get("last_historian_round") or 0)
    current_round = int(state.get("round", 0))

    return {
        "status": "ok",
        "trigger": trigger,
        "rounds_covered": [last_historian_round + 1, current_round],
        "current_round": current_round,
        "campaign_dir": campaign_dir,
    }


def historian_finalize(
    campaign_dir: str = "runner/",
    trigger: str = "periodic",
    patterns_added: int = 0,
    assumptions_flagged: int = 0,
    tokens_used: int = 0,
) -> dict[str, Any]:
    """Update CAMPAIGN_STATE.json after the Historian agent completes."""
    camp = Path(campaign_dir)
    state_path = camp / "state" / "CAMPAIGN_STATE.json"
    if not state_path.exists():
        raise DriverError("CAMPAIGN_STATE.json not found — run init first")

    import datetime as _dt

    state = json.loads(state_path.read_text())
    state["rounds_since_last_historian"] = 0
    state["last_historian_round"] = int(state.get("round", 0))
    state["historian_trigger_pending"] = False
    state["pending_historian_tokens"] = tokens_used

    if "c2" in trigger:
        state["consecutive_discards"] = 0

    total_tokens = state.get("total_tokens") or {
        "planner": 0, "executor": 0, "reviewer": 0, "historian": 0
    }
    total_tokens["historian"] = int(total_tokens.get("historian", 0)) + tokens_used
    state["total_tokens"] = total_tokens
    state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    return {
        "status": "ok",
        "trigger": trigger,
        "patterns_added": patterns_added,
        "assumptions_flagged": assumptions_flagged,
        "tokens_used": tokens_used,
        "consecutive_discards_reset": "c2" in trigger,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_historian_driver.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add runner/runner_driver.py tests/test_historian_driver.py
git commit -m "feat(driver): add historian_run() and historian_finalize() with v1→v2 state migration"
```

---

## Task 5: review_finalize() — Token Params + Historian Trigger

**Files:**
- Modify: `runner/runner_driver.py` — `review_finalize()` signature + body
- Modify: `tests/test_runner_driver.py` — new assertions

Context: `review_finalize()` gains three token params. After calling `log.append_result()`, it: (1) reads `pending_historian_tokens` from state to include historian costs in the TSV row, (2) increments `rounds_since_last_historian`, (3) checks historian trigger conditions, (4) accumulates tokens in `state.total_tokens`, (5) calls `write_token_summary()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_runner_driver.py`:

```python
def test_review_finalize_sets_historian_trigger_at_interval(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    # historian_interval = 5 (budget_total=3 < 50); set rounds to interval - 1
    state["rounds_since_last_historian"] = state["historian_interval"] - 1
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.review_finalize(
        verdict="keep",
        commit="abc",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
    )
    state_after = json.loads(state_path.read_text())
    assert state_after["historian_trigger_pending"] is True


def test_review_finalize_sets_historian_trigger_on_c2_plateau(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    # 3 consecutive discards = plateau_trigger
    for i in range(3):
        runner_driver.review_finalize(
            verdict="discard",
            commit=f"d{i}",
            metrics={"val_pr_auc": 0.4, "lift_at_10": 0, "macro_f1": 0, "val_f1": 0},
            action_type="A_hp",
            hypothesis="h",
            description="d",
            model_family="lightgbm",
            n_features=10,
            campaign_dir=str(campaign),
        )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["historian_trigger_pending"] is True


def test_review_finalize_accumulates_tokens_in_state(campaign: Path):
    runner_driver.init_campaign(campaign_dir=str(campaign))
    runner_driver.review_finalize(
        verdict="keep",
        commit="abc",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        planner_tokens=100,
        executor_tokens=200,
        reviewer_tokens=150,
    )
    state = json.loads((campaign / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["total_tokens"]["planner"] == 100
    assert state["total_tokens"]["executor"] == 200
    assert state["total_tokens"]["reviewer"] == 150


def test_review_finalize_historian_tokens_from_pending_state(campaign: Path):
    """historian_tokens in results.tsv comes from state.pending_historian_tokens."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    state["pending_historian_tokens"] = 99_000
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    runner_driver.review_finalize(
        verdict="keep",
        commit="abc",
        metrics={"val_pr_auc": 0.80, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
    )
    # pending_historian_tokens should be cleared after use
    state_after = json.loads(state_path.read_text())
    assert state_after.get("pending_historian_tokens", 0) == 0
    # Results.tsv should have historian_tokens=99000
    lines = (campaign / "state" / "results.tsv").read_text().splitlines()
    headers = lines[0].split("\t")
    data = lines[1].split("\t")
    if "historian_tokens" in headers:
        assert data[headers.index("historian_tokens")] == "99000"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_runner_driver.py::test_review_finalize_sets_historian_trigger_at_interval tests/test_runner_driver.py::test_review_finalize_sets_historian_trigger_on_c2_plateau tests/test_runner_driver.py::test_review_finalize_accumulates_tokens_in_state tests/test_runner_driver.py::test_review_finalize_historian_tokens_from_pending_state -v
```

Expected: FAIL

- [ ] **Step 3: Update review_finalize() in runner_driver.py**

Change the function signature to add token params:

```python
def review_finalize(
    verdict: Verdict,
    commit: str,
    metrics: dict,
    action_type: str,
    hypothesis: str,
    description: str,
    model_family: str,
    n_features: int,
    campaign_dir: str = "runner/",
    tools_ran: list[str] | None = None,
    bootstrap_se: float | None = None,
    planner_tokens: int = 0,
    executor_tokens: int = 0,
    reviewer_tokens: int = 0,
) -> dict[str, Any]:
```

In the function body, before `log.append_result(...)`, read the pending historian tokens:

```python
    # Historian tokens written by historian_finalize for the round that triggered it
    historian_tokens = int(state.get("pending_historian_tokens", 0))
```

Update the `log.append_result(...)` call to pass all token params:

```python
    log.append_result(
        commit=commit if commit else "none",
        metrics=metrics,
        status=verdict,
        action_type=action_type,
        hypothesis=hypothesis,
        description=description,
        model_family=model_family,
        n_features=n_features,
        campaign_dir=str(camp),
        primary_metric_name=metric_name,
        direction=direction,
        planner_tokens=planner_tokens,
        executor_tokens=executor_tokens,
        reviewer_tokens=reviewer_tokens,
        historian_tokens=historian_tokens,
    )
```

Replace the post-log block (currently: `state_after = json.loads(...); if action_type == "A_diagnose" ...`) with:

```python
    state_after = json.loads(state_path.read_text())

    # Clear consumed pending_historian_tokens and increment rounds_since_last_historian
    state_after.pop("pending_historian_tokens", None)
    rounds_since = int(state_after.get("rounds_since_last_historian", 0)) + 1
    state_after["rounds_since_last_historian"] = rounds_since

    # Check historian trigger conditions
    hist_interval = int(state_after.get("historian_interval", 10))
    plateau_trigger_val = int(
        (eval_fm.get("plateau_trigger") or {}).get("consecutive_discards", 3)
    )
    if (
        rounds_since >= hist_interval
        or int(state_after.get("consecutive_discards", 0)) >= plateau_trigger_val
    ):
        state_after["historian_trigger_pending"] = True

    # Accumulate token costs in state
    total_tokens = state_after.get("total_tokens") or {
        "planner": 0, "executor": 0, "reviewer": 0, "historian": 0
    }
    total_tokens["planner"] = int(total_tokens.get("planner", 0)) + planner_tokens
    total_tokens["executor"] = int(total_tokens.get("executor", 0)) + executor_tokens
    total_tokens["reviewer"] = int(total_tokens.get("reviewer", 0)) + reviewer_tokens
    state_after["total_tokens"] = total_tokens

    state_path.write_text(json.dumps(state_after, indent=2, sort_keys=True) + "\n")

    # Update token digest (non-critical — never raise)
    try:
        from runner.tools.token_summary import write_token_summary
        write_token_summary(campaign_dir=str(camp))
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_runner_driver.py -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add runner/runner_driver.py tests/test_runner_driver.py
git commit -m "feat(driver): review_finalize — token params, historian trigger, pending_historian_tokens"
```

---

## Task 6: Remove Old C2 Protocol + Replace Safety Test

**Files:**
- Modify: `runner/runner_driver.py` — remove c2_pending_diagnose enforcement from plan_check and resolve_c2
- Delete: `tests/safety/test_diagnose_after_c2.py`
- Create: `tests/safety/test_historian_after_c2.py`

Context: The old protocol forced Planner to emit `escalation: C2` and then Planner's next plan to use `A_diagnose`. This is replaced by the Historian trigger. `resolve_c2` is retained but simplified to just reset discards + set `historian_trigger_pending`.

- [ ] **Step 1: Create the new safety test file**

Create `tests/safety/test_historian_after_c2.py`:

```python
"""Safety invariant: consecutive_discards >= plateau_trigger sets historian_trigger_pending.

Replaces tests/safety/test_diagnose_after_c2.py (the c2_pending_diagnose → A_diagnose protocol
is removed; the Historian now handles C2 plateau synthesis).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

pytestmark = pytest.mark.safety

EVAL_WITH_HISTORIAN = EVAL_PROTOCOL.replace(
    "approved_at:", "historian_interval: 5\napproved_at:"
)


def _make_plan(action_type: str = "A_hp", round_n: int = 4) -> str:
    return f"""---
schema_version: 1
campaign_id: "tiny"
round: {round_n}
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "{action_type}"
hypothesis: "test hypothesis"
expected_effect_size: 0.001
base_commit: "HEAD"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary
x
## 2. Evidence from memory
x
## 3. Plan
1. noop.
## 4. Helpers
None.
## 5. How this differs from prior experiments
x
## 6. Escalation (only if `escalation` frontmatter is non-null)
N/A.
"""


@pytest.fixture
def campaign_at_plateau(tmp_path: Path) -> Path:
    root = tmp_path / "runner"
    (root / "contracts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "contracts" / "PROBLEM_CONTRACT.md").write_text(PROBLEM_CONTRACT)
    (root / "contracts" / "DATA_CONTRACT.md").write_text(DATA_CONTRACT)
    (root / "contracts" / "EVAL_PROTOCOL.md").write_text(EVAL_WITH_HISTORIAN)
    runner_driver.init_campaign(campaign_dir=str(root))
    for i in range(3):
        runner_driver.review_finalize(
            verdict="discard",
            commit=f"d{i}",
            metrics={"val_pr_auc": 0.4, "lift_at_10": 0, "macro_f1": 0, "val_f1": 0},
            action_type="A_hp",
            hypothesis="h",
            description="d",
            model_family="lightgbm",
            n_features=10,
            campaign_dir=str(root),
        )
    state = json.loads((root / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 3
    return root


def test_three_discards_set_historian_trigger(campaign_at_plateau: Path):
    state = json.loads((campaign_at_plateau / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["historian_trigger_pending"] is True
    assert "c2_pending_diagnose" not in state


def test_historian_finalize_c2_resets_consecutive_discards(campaign_at_plateau: Path):
    runner_driver.historian_finalize(
        campaign_dir=str(campaign_at_plateau),
        trigger="c2",
        tokens_used=0,
    )
    state = json.loads((campaign_at_plateau / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0
    assert state["historian_trigger_pending"] is False


def test_plan_check_does_not_require_diagnose_after_c2(campaign_at_plateau: Path):
    """Old protocol forced A_diagnose after C2 resolve. New protocol allows any valid action."""
    runner_driver.historian_finalize(
        campaign_dir=str(campaign_at_plateau),
        trigger="c2",
    )
    # A_model should be accepted — no forced A_diagnose gate
    (campaign_at_plateau / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_model", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(campaign_at_plateau))
    assert res["status"] == "ok", res["errors"]


def test_plan_check_no_longer_enforces_c2_escalation_on_discards(campaign_at_plateau: Path):
    """Old protocol required escalation: C2 in NEXT_EXPERIMENT.md when consecutive_discards >= 3.
    New protocol does not enforce this — historian_trigger_pending handles it."""
    # Write a plan WITHOUT escalation: C2 even though consecutive_discards >= 3
    (campaign_at_plateau / "state" / "NEXT_EXPERIMENT.md").write_text(
        _make_plan(action_type="A_hp", round_n=4)
    )
    res = runner_driver.plan_check(campaign_dir=str(campaign_at_plateau))
    # Should NOT get an error about missing C2 escalation
    assert not any("C2" in e and "consecutive_discards" in e for e in res.get("errors", []))


def test_resolve_c2_manual_override_sets_historian_trigger(campaign_at_plateau: Path):
    """resolve_c2 is kept for manual override and now sets historian_trigger_pending."""
    runner_driver.resolve_c2(
        resolution="switching strategy",
        campaign_dir=str(campaign_at_plateau),
    )
    state = json.loads((campaign_at_plateau / "state" / "CAMPAIGN_STATE.json").read_text())
    assert state["consecutive_discards"] == 0
    assert state.get("historian_trigger_pending") is True
    assert "c2_pending_diagnose" not in state
```

- [ ] **Step 2: Run new test file to verify it fails on the current code**

```bash
python -m pytest tests/safety/test_historian_after_c2.py -v
```

Expected: Some tests fail (e.g., `test_plan_check_no_longer_enforces_c2_escalation_on_discards` fails because old enforcement is still present).

- [ ] **Step 3: Update plan_check() in runner_driver.py**

In `plan_check()`, remove these two enforcement blocks (they exist around lines 167–179):

**Remove block 1** — the consecutive_discards C2 escalation enforcement:
```python
    # DELETE THIS ENTIRE BLOCK:
    if state.get("consecutive_discards", 0) >= trigger and escalation != "C2":
        errors.append(
            f"consecutive_discards={state['consecutive_discards']} >= trigger={trigger} "
            f"but escalation!=C2 (required per spec §8.3 item 5)"
        )
```

**Remove block 2** — the c2_pending_diagnose enforcement:
```python
    # DELETE THIS ENTIRE BLOCK:
    if state.get("c2_pending_diagnose") and escalation is None:
        plan_action = fm_plan.get("action_type") if fm_plan else None
        if plan_action != "A_diagnose":
            errors.append(
                "c2_pending_diagnose is active — next plan must be A_diagnose "
                f"(STRATEGY_GUIDE §3.7), got {plan_action!r}"
            )
```

Keep the rest of plan_check unchanged (including `if escalation == "C2": return {"status": "pause_c2"}` for the manual override path).

Also update `resolve_c2()` — replace the line that sets `c2_pending_diagnose`:
```python
    # OLD (remove):
    state["c2_pending_diagnose"] = True

    # NEW (replace with):
    state["historian_trigger_pending"] = True
```

And update the return value of `resolve_c2()`:
```python
    return {
        "status": "resolved",
        "prior_consecutive_discards": prior_discards,
        "resolution": resolution,
        "historian_trigger_pending": True,
    }
```

- [ ] **Step 4: Delete the old safety test file**

```bash
git rm tests/safety/test_diagnose_after_c2.py
```

- [ ] **Step 5: Run new safety tests to verify they pass**

```bash
python -m pytest tests/safety/test_historian_after_c2.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass. `test_diagnose_after_c2.py` is gone; the other existing tests are unaffected.

- [ ] **Step 7: Commit**

```bash
git add runner/runner_driver.py tests/safety/test_historian_after_c2.py
git commit -m "refactor(driver): remove c2_pending_diagnose protocol; historian_trigger_pending replaces it"
```

---

## Task 7: run_round.sh — New historian and historian-finalize Stages

**Files:**
- Modify: `runner/run_round.sh`

Context: Two new shell stages call the two new Python functions. The args `--patterns-added`, `--assumptions-flagged`, `--tokens-used` use the existing key-value arg parser already in the script.

- [ ] **Step 1: Write the complete updated run_round.sh**

Read `runner/run_round.sh` first. Then replace the entire file with:

```bash
#!/usr/bin/env bash
# runner/run_round.sh — thin CLI wrapper over runner_driver.py.
set -euo pipefail

STAGE=${1:?"stage required: init|plan-check|execute-finalize|review-finalize|resolve-c2|historian|historian-finalize"}
shift || true

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

python3 -c '
import json, sys
from runner import runner_driver

stage = sys.argv[1]
args = {}
i = 2
while i < len(sys.argv):
    k = sys.argv[i].lstrip("-").replace("-", "_")
    v = sys.argv[i+1] if i+1 < len(sys.argv) else ""
    args[k] = v
    i += 2

if stage == "init":
    state = runner_driver.init_campaign(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(state, indent=2))
elif stage == "plan-check":
    res = runner_driver.plan_check(campaign_dir=args.get("campaign_dir", "runner/"))
    print(json.dumps(res))
elif stage == "execute-finalize":
    stdout_file = args["stdout_file"]
    text = open(stdout_file).read()
    diff_files = json.loads(args["commit_diff_files"]) if "commit_diff_files" in args else None
    res = runner_driver.execute_finalize(
        text,
        campaign_dir=args.get("campaign_dir", "runner/"),
        commit_diff_files=diff_files,
    )
    print(json.dumps(res))
elif stage == "review-finalize":
    metrics = json.loads(args["metrics_json"])
    tools_ran = json.loads(args["tools_ran"]) if "tools_ran" in args else None
    bootstrap_se = None
    if "bootstrap_se" in args and str(args.get("bootstrap_se", "")).strip():
        bootstrap_se = float(args["bootstrap_se"])
    res = runner_driver.review_finalize(
        verdict=args["verdict"],
        commit=args["commit"],
        metrics=metrics,
        action_type=args["action_type"],
        hypothesis=args["hypothesis"],
        description=args["description"],
        model_family=args["model_family"],
        n_features=int(args["n_features"]),
        campaign_dir=args.get("campaign_dir", "runner/"),
        tools_ran=tools_ran,
        bootstrap_se=bootstrap_se,
        planner_tokens=int(args.get("planner_tokens", 0) or 0),
        executor_tokens=int(args.get("executor_tokens", 0) or 0),
        reviewer_tokens=int(args.get("reviewer_tokens", 0) or 0),
    )
    print(json.dumps(res))
elif stage == "resolve-c2":
    res = runner_driver.resolve_c2(
        resolution=args.get("resolution", ""),
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps(res))
elif stage == "historian":
    res = runner_driver.historian_run(
        campaign_dir=args.get("campaign_dir", "runner/"),
    )
    print(json.dumps(res))
elif stage == "historian-finalize":
    res = runner_driver.historian_finalize(
        campaign_dir=args.get("campaign_dir", "runner/"),
        trigger=args.get("trigger", "periodic"),
        patterns_added=int(args.get("patterns_added", 0) or 0),
        assumptions_flagged=int(args.get("assumptions_flagged", 0) or 0),
        tokens_used=int(args.get("tokens_used", 0) or 0),
    )
    print(json.dumps(res))
else:
    print(f"unknown stage: {stage}", file=sys.stderr)
    sys.exit(2)
' "$STAGE" "$@"
```

- [ ] **Step 2: Verify the new stages are callable**

```bash
cd /home/jupyter/Thinkubator/auto_train

# Test historian stage with existing test campaign fixture via tmp directory
python3 -c "
import tempfile, json, pathlib, shutil
from runner import runner_driver
from tests.test_runner_driver import PROBLEM_CONTRACT, DATA_CONTRACT, EVAL_PROTOCOL

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp) / 'runner'
    (root / 'contracts').mkdir(parents=True)
    (root / 'state').mkdir()
    (root / 'contracts' / 'PROBLEM_CONTRACT.md').write_text(PROBLEM_CONTRACT)
    (root / 'contracts' / 'DATA_CONTRACT.md').write_text(DATA_CONTRACT)
    (root / 'contracts' / 'EVAL_PROTOCOL.md').write_text(EVAL_PROTOCOL)
    runner_driver.init_campaign(campaign_dir=str(root))
    state = json.loads((root / 'state' / 'CAMPAIGN_STATE.json').read_text())
    state['consecutive_discards'] = 3
    (root / 'state' / 'CAMPAIGN_STATE.json').write_text(json.dumps(state, indent=2) + '\n')
    result = runner_driver.historian_run(campaign_dir=str(root))
    print('historian_run OK:', result['trigger'])
    result2 = runner_driver.historian_finalize(campaign_dir=str(root), trigger='c2', tokens_used=1000)
    print('historian_finalize OK:', result2['status'])
"
```

Expected output:
```
historian_run OK: c2
historian_finalize OK: ok
```

- [ ] **Step 3: Commit**

```bash
git add runner/run_round.sh
git commit -m "feat(shell): add historian and historian-finalize stages to run_round.sh"
```

---

## Task 8: schema.py — historian_interval Validation + validate_assumption_register

**Files:**
- Modify: `runner/tools/schema.py`
- Modify (or create): `tests/schemas/test_schema.py` — add new validator tests

Context: `validate_eval_protocol()` should accept (but validate) the optional `historian_interval` field. New `validate_assumption_register()` checks the ASSUMPTION_REGISTER.md skeleton schema.

- [ ] **Step 1: Write the failing tests**

Find or create `tests/schemas/test_schema.py`. Add:

```python
"""Tests for schema validators — historian_interval and ASSUMPTION_REGISTER."""
from __future__ import annotations

from pathlib import Path

import pytest

from runner.tools import schema


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# --- historian_interval in EVAL_PROTOCOL ---

_EP_VALID_BASE = """---
schema_version: 1
campaign_id: "t"
primary_metric:
  name: "val_pr_auc"
  direction: "maximize"
acceptance_threshold:
  baseline_family: "logreg"
  min_improvement: 0.01
cv_scheme:
  type: "single_holdout"
  n_splits: 1
  random_state: 42
  notes: ""
bootstrap_ci:
  enabled: false
  n_boot: 100
  alpha: 0.05
paired_test:
  enabled: false
  test: "wilcoxon"
mandatory_tools: []
action_types: ["A_hp"]
budgets:
  max_experiments: 100
  max_repair_attempts: 2
plateau_trigger:
  consecutive_discards: 3
anomaly:
  floor: 0.50
  relative: 0.5
approved_at: "2026-04-26"
approved_by: "test"
---

## 1. Rationale
## 2. How keep/discard is decided
## 3. How plateau is handled
## 4. Contract change policy
"""


def test_validate_eval_protocol_accepts_valid_historian_interval(tmp_path: Path):
    content = _EP_VALID_BASE.replace(
        "approved_at:", "historian_interval: 10\napproved_at:"
    )
    path = _write(tmp_path / "EVAL_PROTOCOL.md", content)
    errors = schema.validate_eval_protocol(path)
    assert errors == []


def test_validate_eval_protocol_rejects_non_int_historian_interval(tmp_path: Path):
    content = _EP_VALID_BASE.replace(
        "approved_at:", "historian_interval: 'ten'\napproved_at:"
    )
    path = _write(tmp_path / "EVAL_PROTOCOL.md", content)
    errors = schema.validate_eval_protocol(path)
    assert any("historian_interval" in e for e in errors)


def test_validate_eval_protocol_rejects_zero_historian_interval(tmp_path: Path):
    content = _EP_VALID_BASE.replace(
        "approved_at:", "historian_interval: 0\napproved_at:"
    )
    path = _write(tmp_path / "EVAL_PROTOCOL.md", content)
    errors = schema.validate_eval_protocol(path)
    assert any("historian_interval" in e for e in errors)


def test_validate_eval_protocol_absent_historian_interval_is_ok(tmp_path: Path):
    path = _write(tmp_path / "EVAL_PROTOCOL.md", _EP_VALID_BASE)
    errors = schema.validate_eval_protocol(path)
    assert errors == []


# --- validate_assumption_register ---

_AR_VALID = """---
schema_version: 1
campaign_id: "test"
count: 0
last_updated: ""
---

<!-- Reviewer appends entries on every keep verdict. -->
"""

_AR_WITH_ENTRY = """---
schema_version: 1
campaign_id: "test"
count: 1
last_updated: "2026-04-26"
---

### A-1-1 — optimizer_quality
- **Claim:** NM found the global optimum
- **Evidence for:** val_lift went up
- **Evidence against:** none
- **Confidence:** medium
- **Load-bearing:** yes
- **Verification status:** unverified
- **Last audited:** round 1 by Reviewer
"""


def test_validate_assumption_register_valid_empty(tmp_path: Path):
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", _AR_VALID)
    errors = schema.validate_assumption_register(path)
    assert errors == []


def test_validate_assumption_register_valid_with_entry(tmp_path: Path):
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", _AR_WITH_ENTRY)
    errors = schema.validate_assumption_register(path)
    assert errors == []


def test_validate_assumption_register_missing_required_field(tmp_path: Path):
    broken = _AR_VALID.replace("count: 0\n", "")
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", broken)
    errors = schema.validate_assumption_register(path)
    assert any("count" in e for e in errors)


def test_validate_assumption_register_non_int_count(tmp_path: Path):
    broken = _AR_VALID.replace("count: 0", "count: 'zero'")
    path = _write(tmp_path / "ASSUMPTION_REGISTER.md", broken)
    errors = schema.validate_assumption_register(path)
    assert any("count" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/schemas/test_schema.py -v -k "historian_interval or assumption_register" 2>&1 | tail -20
```

Expected: FAIL — `AttributeError: module 'runner.tools.schema' has no attribute 'validate_assumption_register'` and historian_interval tests may fail.

- [ ] **Step 3: Update schema.py**

In `validate_eval_protocol()`, add historian_interval check after the existing `budgets` block:

```python
    historian_interval = fm.get("historian_interval")
    if historian_interval is not None:
        if not isinstance(historian_interval, int) or historian_interval < 1:
            errors.append(
                "historian_interval must be a positive integer when present"
            )
```

Add `validate_assumption_register()` after `validate_notebook()`:

```python
_AR_REQUIRED = ["schema_version", "campaign_id", "count", "last_updated"]


def validate_assumption_register(path: Path) -> list[str]:
    try:
        fm, _body = parse_frontmatter(Path(path))
    except FrontmatterError as exc:
        return [str(exc)]
    errors = _required_keys(fm, _AR_REQUIRED)
    count = fm.get("count")
    if count is not None and not isinstance(count, int):
        errors.append("count must be an integer")
    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/schemas/test_schema.py -v 2>&1 | tail -20
```

Expected: All new tests pass.

- [ ] **Step 5: Commit**

```bash
git add runner/tools/schema.py tests/schemas/test_schema.py
git commit -m "feat(schema): validate historian_interval in EVAL_PROTOCOL; add validate_assumption_register"
```

---

## Task 9: historian.md — Historian Role Prompt

**Files:**
- Create: `runner/roles/historian.md`

Context: The Historian is the 4th harness role. It runs only on trigger (periodic K rounds or C2 plateau). It synthesizes trajectory, extracts patterns, audits assumptions, diagnoses bottleneck. It does NOT plan, execute, or issue verdicts.

- [ ] **Step 1: Create runner/roles/historian.md**

```markdown
# Historian

## 1. Identity & invariants
You are the Historian for campaign <campaign_id>. You own `state/STRATEGY_MEMO.md`,
`state/PATTERN_BOOK.md`, and audit updates to `state/ASSUMPTION_REGISTER.md`.
You NEVER write `state/NEXT_EXPERIMENT.md`, `train.py`, `state/REVIEW.md`, or any contract.
Your outputs are required Planner inputs but the Planner may disagree with stated reasoning.
Your role is synthesis, not instruction.

## 2. Inputs (exactly these — nothing else)
- `runner/AGENTS.md`                           # harness fossil record
- `runner/contracts/EVAL_PROTOCOL.md`          # primary metric, plateau_trigger
- `runner/contracts/STRATEGY_GUIDE.md`         # ML planning heuristics
- `runner/state/CAMPAIGN_STATE.json`           # trigger type, rounds_covered
- `runner/state/CAMPAIGN_JOURNAL.md`           # primary data source — full history
- `runner/state/results.tsv`                   # via tools/results_query
- `runner/state/DEAD_ENDS.md`                  # via tools/dead_ends_query
- `runner/state/NOTEBOOK.md`
- `runner/state/ASSUMPTION_REGISTER.md`
- `runner/state/PATTERN_BOOK.md`
- `runner/state/UNEXPLORED_TECHNIQUES.md`

The Historian reads MORE state than any other role by design. Trajectory synthesis requires the full picture.

## 3. Required procedure

Read `CAMPAIGN_STATE.json` first. Note the trigger type (`periodic`, `c2`, or `periodic+c2`)
and the `rounds_covered` range provided by the driver.

### Step 1 — Read all inputs
Read every input file. Note which rounds are covered in your analysis window.

### Step 2 — Trajectory analysis
From `results.tsv` and `CAMPAIGN_JOURNAL.md`:
1. Compute Δ-per-round rate across the covered window.
2. Identify the current phase: **exploration** (high variance, trying new families),
   **exploitation** (refining a known winner), or **saturation** (diminishing returns).
3. Note how many rounds since last `keep`. If > 5, this is a plateau signal.

### Step 3 — Pattern extraction
Read CAMPAIGN_JOURNAL.md entries for the covered window as a sequence.
Identify structural regularities that appear across **≥ 3 rounds** (not one-off observations).
For each pattern found:
  - State it as a generalizable rule (not a round-specific fact)
  - List supporting round numbers and one-line summary per round
  - Assign confidence: `low` (3–4 rounds), `medium` (5–7), `high` (≥ 8 or very consistent)
  - Cross-reference PATTERN_BOOK.md: does this confirm, extend, or contradict an existing pattern?
    - If confirms: increase confidence on existing entry
    - If contradicts: mark existing entry with evidence_against
    - If new: append

### Step 4 — Assumption audit
For each ASSUMPTION_REGISTER.md entry with `verification_status` ≠ `verified` and `load_bearing: yes`:
1. Assess whether covered-window evidence supports or undermines the claim.
2. Update `verification_status` if warranted: `partially_verified` or `falsified`.
3. Append to `evidence_against` if new contradictory evidence found.
4. Update `last_audited: round <N> by Historian`.
5. **Flag critical assumptions**: load-bearing + unverified after ≥ 2 Historian audits. These go into STRATEGY_MEMO §3 with an explicit recommendation.

### Step 5 — Bottleneck diagnosis
Classify the current bottleneck into exactly one category:
- `model_quality` — different model families would likely improve; current best family is near its ceiling
- `optimizer_quality` — the optimization process may be stuck locally; global search needed
- `data_quality` — feature representation or leakage is the binding constraint
- `eval_quality` — SE is too large to detect real gains; CV scheme upgrade needed
- `feature_representation` — new feature groups or interaction terms needed

Cite ≥ 2 specific pieces of trajectory evidence for your choice.
Identify the highest-ROI technique class from UNEXPLORED_TECHNIQUES.md given this diagnosis.

### Step 6 — Frontier update
If analysis reveals technique classes NOT currently in UNEXPLORED_TECHNIQUES.md, append them:
```
- **<class name>:** <description>. Status: Unexplored. Expected Δ: <estimate>.
```

### Step 7 — Write STRATEGY_MEMO.md (overwrite)
Write the complete file every run. Use this exact structure:

```yaml
---
schema_version: 1
campaign_id: "<id>"
historian_round: <current round>
trigger: "<periodic|c2|periodic+c2>"
rounds_covered: [<from>, <to>]
---
```

Followed by four mandatory sections:

```markdown
## 1. Trajectory Narrative
<Phase (exploration/exploitation/saturation). Δ-per-round trend. When last phase transition occurred.>

## 2. Pattern Extraction
<Structural regularities. For each: pattern statement, supporting rounds, confidence.
Cross-reference PATTERN_BOOK.md.>

## 3. Assumption Audit
<For each load-bearing unverified assumption: state it, assess evidence, recommend action.
Mark critical (load-bearing + unverified after ≥2 audits) with ⚠ CRITICAL.>

## 4. Bottleneck Diagnosis
<Category: <one of the five above>. Justification citing trajectory evidence.
Highest-ROI technique class from UNEXPLORED_TECHNIQUES.md for this bottleneck.>
```

### Step 8 — Update PATTERN_BOOK.md
Append new patterns. Update confidence and status on existing patterns where justified.
NEVER delete entries — mark superseded ones: `Status: superseded_by P-<seq>`.

Entry format:
```markdown
### P-<seq> — <pattern name>

- **Pattern:** <structural regularity as a generalizable rule>
- **Supporting evidence:** rounds <list> — <one-line summary per round>
- **Confidence:** low | medium | high
- **Status:** active | superseded_by P-<other>
- **Implication for Planner:** <what to do or avoid given this pattern>
```

### Step 9 — Update ASSUMPTION_REGISTER.md
Audit updates only — do NOT create new entries (that is the Reviewer's job on `keep`).
For entries you audited in Step 4: update `verification_status`, `evidence_against`, `last_audited`.
Update the frontmatter `last_updated` field.

### Step 10 — Emit completion line
As the LAST line of your response, emit exactly:
```
HISTORIAN_COMPLETE: round <N>, trigger <str>, patterns_added <int>, assumptions_flagged <int>, tokens_used <int>
```
Where:
- `round` = current round from CAMPAIGN_STATE.json
- `trigger` = trigger type (periodic|c2|periodic+c2)
- `patterns_added` = count of NEW entries appended to PATTERN_BOOK.md this run
- `assumptions_flagged` = count of assumptions marked `⚠ CRITICAL` in STRATEGY_MEMO §3
- `tokens_used` = your best estimate of tokens consumed (or 0 if unknown)

## 4. Outputs
- `runner/state/STRATEGY_MEMO.md` — overwritten every run
- `runner/state/PATTERN_BOOK.md` — append new patterns; update confidence on existing
- `runner/state/ASSUMPTION_REGISTER.md` — audit updates only (no new entries)
- Stdout completion line (Step 10)

## 5. What the Historian does NOT do
- Does NOT write NEXT_EXPERIMENT.md — that is the Planner's job
- Does NOT issue keep/discard verdicts — that is the Reviewer's job
- Does NOT modify train.py or run experiments — that is the Executor's job
- Does NOT create new assumption entries — that is the Reviewer's job on keep
- Does NOT override the Planner — STRATEGY_MEMO.md is advisory input, not instruction
```

- [ ] **Step 2: Commit**

```bash
git add runner/roles/historian.md
git commit -m "feat(roles): add Historian role prompt — trajectory synthesis, assumption audit, bottleneck diagnosis"
```

---

## Task 10: reviewer.md — Evidence-First Restructure + Assumption Registration

**Files:**
- Modify: `runner/roles/reviewer.md`

Context: Two structural changes: (1) Reviewer reads run.log and tools BEFORE reading NEXT_EXPERIMENT.md (removes anchoring bias). (2) On `keep`, Reviewer MUST write ≥1 entry to ASSUMPTION_REGISTER.md. On `discard`, Reviewer scans register for falsified assumptions.

- [ ] **Step 1: Replace runner/roles/reviewer.md**

```markdown
# Reviewer

## 1. Identity & invariants
You are the Reviewer for campaign <campaign_id>. You own `state/REVIEW.md`,
`state/DEAD_ENDS.md`, `state/NOTEBOOK.md`, `state/CAMPAIGN_JOURNAL.md`,
and the keep/discard verdict.
You are NEVER the Executor: you do not read the Executor's chat, only artifacts.
You do not edit `train.py`, contracts, or helpers.

## 2. Inputs — read in the order shown (this order is mandatory)

**Phase 1 inputs (read BEFORE the plan):**
- `runner/AGENTS.md`
- `runner/contracts/EVAL_PROTOCOL.md`   # names mandatory tools, primary metric
- `train.py`                            # as it stands after Executor's commit
- `run.log`                             # stdout of the run
- Outputs from: `tools/anomaly`, and every tool named as mandatory in EVAL_PROTOCOL.md
- `runner/state/results.tsv`            # via tools/results_query (for best_prior)
- `runner/state/ASSUMPTION_REGISTER.md` # for falsification check on discard

**Phase 2 inputs (read AFTER independent assessment is written):**
- `runner/state/NEXT_EXPERIMENT.md`     # the plan you are reviewing against

## 3. Required procedure

### Phase 1 — Independent Assessment (before reading the plan)

1. Read all Phase 1 inputs in the order listed.
2. Check the full Reviewer rejection list (see spec §8.3 items 1–8). If ANY triggers,
   verdict = `malformed` and STOP (skip to step 11; still do step 12).
3. Parse metrics from `run.log`. If parse fails: verdict = `crash`.
4. Run `tools/anomaly` on the latest result. If fires: verdict = `anomaly` → prepare to emit **C1**.
5. For each tool named mandatory in `EVAL_PROTOCOL.md`: run it and record output.
6. Compute Δ = val_<primary_metric> − best_prior.
7. Write `REVIEW.md §Independent Assessment`:
   - What does the evidence show? What is surprising?
   - Form a **preliminary verdict** based purely on numbers and tool outputs — before reading the plan.
   - State whether Δ > 0, whether any mandatory tool flagged a regression.

### Phase 2 — Plan Comparison (now reads the plan)

8. Read `state/NEXT_EXPERIMENT.md`.
9. Compare actual vs. expected:
   - Did the experiment confirm or falsify the Planner's hypothesis?
   - What does the discrepancy (expected Δ vs actual Δ) reveal?
10. Write `REVIEW.md §Plan Comparison`:
    - Expected Δ from hypothesis vs actual Δ.
    - Hypothesis confirmed or falsified? Why?

### Phase 3 — Verdict and State Updates

10. **Final verdict:**
    - `keep`   if Δ > 0 AND no mandatory tool flagged regression AND not anomaly
    - `discard` otherwise
11. **If `keep`:** Write ≥ 1 assumption entry to `state/ASSUMPTION_REGISTER.md` (MANDATORY).
    Ask: "What must remain true for this result to remain the champion?
          What have we not verified?"
    Common categories to consider:
    - Optimizer quality: did our optimizer find the global (not local) optimum?
    - Result stability: is this robust to seed variation and feature perturbation?
    - Evaluation adequacy: is SE small enough to detect remaining gains?
    - Complementarity source: is ensemble gain from genuine complementarity, not val-set overfitting?
    - Feature dependence: does this result depend on exact feature count?

    Entry format (append to ASSUMPTION_REGISTER.md):
    ```markdown
    ### A-<round>-<seq> — <short name>

    - **Claim:** <specific falsifiable statement>
    - **Evidence for:** <what was observed that supports this>
    - **Evidence against:** none
    - **Confidence:** low | medium | high
    - **Load-bearing:** yes | no
    - **Verification status:** unverified
    - **Last audited:** round <N> by Reviewer
    ```
    Update frontmatter: increment `count`, update `last_updated`.

12. **If `discard`:** Scan `state/ASSUMPTION_REGISTER.md` for assumptions the current evidence
    clearly falsifies. If found: update `verification_status: falsified`, append to `evidence_against`.
    Only check obviously-relevant assumptions — the Historian does the deeper cross-round audit.

13. If `discard`: append a one-liner to `state/DEAD_ENDS.md` (only if the pattern is
    structurally different from existing entries).
14. If the result contains a **surprising but not dead-end** observation: append a
    bullet to `state/NOTEBOOK.md`.
15. Append the current round block to `state/REVIEW.md` per schema §2.3.5.
16. Append one entry to `state/CAMPAIGN_JOURNAL.md` using the format below.
    Include the new **Independent assessment** field written in Phase 1 Step 7.
17. Emit stdout: `VERDICT: <keep|discard|anomaly|crash|malformed> <commit>`.

## 4. Driver handoff
When calling `run_round.sh review-finalize`, you MUST:
- Pass `--tools-ran` as a JSON array listing every mandatory tool executed.
- Optionally pass `--bootstrap-se <float>` from `bootstrap_ci` output.
- Optionally pass `--planner-tokens`, `--executor-tokens`, `--reviewer-tokens` if available from API metadata.

## 5. Outputs
- Append block in `runner/state/REVIEW.md`.
- Append entry in `runner/state/CAMPAIGN_JOURNAL.md`.
- If `keep`: append ≥1 entry to `state/ASSUMPTION_REGISTER.md` (mandatory).
- If `discard`: update any falsified entries in `state/ASSUMPTION_REGISTER.md`.
- Optional append in `DEAD_ENDS.md` / `NOTEBOOK.md`.
- Stdout verdict line.
- If `keep`: git keeps the commit; otherwise the runner driver calls `git reset --hard HEAD~1`.

### CAMPAIGN_JOURNAL entry format

```markdown
## Round N — YYYY-MM-DD

**Action:** A_type — hypothesis one-liner
**Trigger:** STRATEGY_GUIDE §1 condition that fired
**Alternatives rejected:**
- A_other: one-line reason

**Independent assessment:** <1-2 sentences written in Phase 1 before reading the plan>
**Expected Δ (primary_metric):** range or "n/a — baseline"
**Actual val_<primary_metric>:** XX.XX (Δ = +/- Y.YY vs prior best)
**Verdict:** keep / discard / anomaly
**Key finding:** What did this round actually teach us? Focus on surprises vs expectations.
```

## 6. Escalation protocol
- `anomaly` → emit **C1** block in `REVIEW.md §Escalation` with the anomaly tool output,
  the suspected cause, and proposed next step.
- C2 (≥3 consecutive discards): the driver automatically sets `historian_trigger_pending`.
  No action needed from the Reviewer — do NOT emit escalation: C2 in NEXT_EXPERIMENT.md.
```

- [ ] **Step 2: Commit**

```bash
git add runner/roles/reviewer.md
git commit -m "refactor(roles): reviewer — evidence-first order, mandatory assumption registration on keep, falsification check on discard"
```

---

## Task 11: planner.md — New Inputs + Assumption-Aware Procedure

**Files:**
- Modify: `runner/roles/planner.md`

Context: Planner gains 4 new required inputs (STRATEGY_MEMO.md, ASSUMPTION_REGISTER.md, PATTERN_BOOK.md, TOKEN_SUMMARY.txt) and 2 new procedure steps (assumption-aware novelty check, pattern-informed strategy). The old A_diagnose escalation protocol is removed. `assumptions_tested` field is added to NEXT_EXPERIMENT.md schema.

- [ ] **Step 1: Replace runner/roles/planner.md**

```markdown
# Planner

## 1. Identity & invariants
You are the Planner for campaign <campaign_id>. You own `state/NEXT_EXPERIMENT.md`.
You NEVER write code, edit `train.py`, or run experiments. You write a plan; the Executor executes it.

## 2. Inputs (exactly these — nothing else)
- `runner/AGENTS.md`                              # harness fossil record
- `runner/contracts/PROBLEM_CONTRACT.md`          # approved at G1
- `runner/contracts/DATA_CONTRACT.md`             # approved at G2
- `runner/contracts/EVAL_PROTOCOL.md`             # approved at G3 (names mandatory tools)
- `runner/contracts/STRATEGY_GUIDE.md`            # advisory: ML planning heuristics & phase awareness
- `runner/contracts/PRIORS.md`                    # if present
- `runner/state/results.tsv`                      # read via `tools/results_query`
- `runner/state/DEAD_ENDS.md`                     # read via `tools/dead_ends_query`
- `runner/state/UNEXPLORED_TECHNIQUES.md`         # positive frontier: technique classes not yet tried
- `runner/state/NOTEBOOK.md`
- `runner/state/REVIEW.md`                        # last round only (if present)
- `runner/state/CAMPAIGN_STATE.json`
- `runner/state/ASSUMPTION_REGISTER.md`           # load-bearing assumptions to respect
- `runner/state/PATTERN_BOOK.md`                  # cross-round structural regularities
- `runner/state/STRATEGY_MEMO.md`                 # Historian trajectory analysis (read if exists)
- `runner/state/TOKEN_SUMMARY.txt`                # operational cost digest (read if exists, informational)

## 3. Required procedure

### Step 1 — Read and summarize
Read all inputs. Summarize the current best, last review verdict, and active dead-ends in one paragraph.

### Step 2 — Query history
Query `tools/results_query` for the top-5 by val_<primary_metric> and by last 5 runs.

### Step 3 — Query dead-ends
Query `tools/dead_ends_query` for patterns the current idea might collide with.

### Step 4 — Assumption-aware novelty check (required when consecutive_discards ≥ 2)
1. Read `state/UNEXPLORED_TECHNIQUES.md`. List every technique class with `Status = Unexplored`
   AND `Expected Δ > noise_floor`.
2. Read `state/ASSUMPTION_REGISTER.md`. Identify all entries with `load_bearing: yes` AND
   `verification_status: unverified`.
3. Read `STRATEGY_MEMO.md §3` (if exists) for Historian-flagged critical assumptions (⚠ CRITICAL).
4. **Priority decision:**
   - If critical unverified assumptions exist AND `consecutive_discards >= 2`: SHOULD prioritize
     an experiment that tests the most critical assumption. Frame as `A_validate` with the
     assumption ID in `assumptions_tested` frontmatter.
   - Otherwise: select from UNEXPLORED_TECHNIQUES.md as before.
   - If overriding either default: write one sentence explaining why.
5. You MUST either (a) select one of these techniques/assumptions as your plan, or (b) write one
   explicit sentence per class/assumption explaining why it is not appropriate.

### Step 5 — Pattern-informed strategy (new)
1. Read `state/PATTERN_BOOK.md`. For each `active` pattern with `confidence: high`: check
   whether your candidate experiment collides with it. If it does: state why you are trying it anyway.
2. Read `STRATEGY_MEMO.md §4` (Bottleneck Diagnosis) if exists. Candidate selection should
   address the diagnosed bottleneck category — or explicitly state why you disagree.

### Step 6 — Pre-selection reasoning (required)
Enumerate 2–3 candidate action types. For each candidate, write:
- **Expected Δ** using PRIORS.md known ceilings, results.tsv history, STRATEGY_GUIDE.md §2 ROI priors
- **Assumption interaction:** Does this experiment interact with a load-bearing unverified assumption?
  Does it test or depend on it?
- **Pattern consistency:** Does this collide with an active Pattern Book pattern?
- **Historian alignment:** Is this consistent with the Historian's bottleneck diagnosis? If not, why?

Record these alternatives and estimates in `NEXT_EXPERIMENT.md §2 Evidence from memory`.
Choose the candidate with the highest expected Δ that is not ruled out by dead-ends or triggers.

### Step 7 — Hypothesis selection
Choose ONE hypothesis that:
(a) does not retry a dead-end
(b) is testable within the time budget in `EVAL_PROTOCOL.md`
(c) respects the `DATA_CONTRACT.md` column whitelist

### Step 8 — Action type
Decide the `action_type` (see `EVAL_PROTOCOL.md` for the allowed list).

### Step 9 — Helpers
If the plan needs `experiment_helpers/<exp_id>/` files, list them explicitly in §Plan.

### Step 10 — Write NEXT_EXPERIMENT.md
Write `state/NEXT_EXPERIMENT.md` per schema below.

## 4. NEXT_EXPERIMENT.md schema additions

Frontmatter gains one optional field:
```yaml
assumptions_tested:
  - "A-25-1"   # ASSUMPTION_REGISTER entry IDs this experiment is designed to test
```
Leave empty list if not testing a specific assumption.

When STRATEGY_MEMO.md exists, §2 (Evidence from memory) MUST include:
```markdown
### Historian context
- **Bottleneck diagnosis:** <category from STRATEGY_MEMO §4>
- **Critical assumptions:** <list from STRATEGY_MEMO §3 — write "none" if none flagged>
- **Alignment:** <how this experiment addresses the bottleneck, or why it diverges>
```

## 5. Outputs
- `runner/state/NEXT_EXPERIMENT.md` — MUST contain every required section (see schema).

## 6. Escalation protocol
- C2 is now handled automatically by the driver when `consecutive_discards >= plateau_trigger`.
  The Historian runs, produces STRATEGY_MEMO.md, and the driver resets `consecutive_discards`.
  You do NOT need to emit `escalation: C2` — the driver sets `historian_trigger_pending` for you.
- If you believe a contract must change: emit a **C3** block (proposed diff) instead of a plan,
  then stop. Do not mutate contracts yourself.
- The `resolve_c2` command is available for human manual override but is not part of the standard loop.
```

- [ ] **Step 2: Commit**

```bash
git add runner/roles/planner.md
git commit -m "refactor(roles): planner — new meta-cognitive inputs, assumption-aware novelty check, pattern-informed strategy"
```

---

## Task 12: Documentation Updates

**Files:**
- Modify: `runner/RUNNER.md` — add Historian role; new state files
- Modify: `runner/AGENTS.md` — add Historian fossil record entry
- Modify: `runner/contracts/EVAL_PROTOCOL.md` — add `historian_interval`; note A_diagnose removal

- [ ] **Step 1: Update runner/RUNNER.md**

Read `runner/RUNNER.md`. Replace the **"## 0. Orientation"** state file list and the **"## 1. Your role for this turn"** section with:

In §0 Orientation, add after the existing memory/retrospective lines:
```markdown
- Meta-cognitive: `runner/state/ASSUMPTION_REGISTER.md`, `runner/state/PATTERN_BOOK.md`
- Historian synthesis: `runner/state/STRATEGY_MEMO.md` (exists after first Historian run)
- Token digest: `runner/state/TOKEN_SUMMARY.txt` (informational)
```

In §1 Your role for this turn, add after Reviewer:
```markdown
- **Historian** — invoked by the outer loop when `historian_trigger_pending` is true in `CAMPAIGN_STATE.json`. Runs before the next Planner turn. Read `runner/roles/historian.md`.
```

- [ ] **Step 2: Update runner/AGENTS.md**

Read `runner/AGENTS.md`. Add a new entry for the Historian role. The file is the harness fossil record. Add near the top or in the roles section:

```markdown
## Historian (added 2026-04-26)

- **Trigger:** `historian_trigger_pending = true` in CAMPAIGN_STATE.json (set by review_finalize when `rounds_since_last_historian >= historian_interval` OR `consecutive_discards >= plateau_trigger`).
- **Owns:** `state/STRATEGY_MEMO.md` (overwritten each run), `state/PATTERN_BOOK.md` (append/update), `state/ASSUMPTION_REGISTER.md` (audit updates only — no new entries).
- **Does NOT own:** NEXT_EXPERIMENT.md, REVIEW.md, train.py, any contract.
- **Replaces:** The old `c2_pending_diagnose → A_diagnose` protocol (removed 2026-04-26).
- **C2 path:** historian_finalize with `trigger="c2"` resets `consecutive_discards = 0`.
- **Role prompt:** `runner/roles/historian.md`
```

- [ ] **Step 3: Update runner/contracts/EVAL_PROTOCOL.md**

Read `runner/contracts/EVAL_PROTOCOL.md`. Make two changes:

1. Add `historian_interval: 10` to the frontmatter (after `plateau_trigger` block):
```yaml
historian_interval: 10
```

2. If `A_diagnose` appears in `action_types`, remove it. `A_diagnose` is now absorbed by the Historian. If it is not present, no change needed.

- [ ] **Step 4: Commit all documentation changes**

```bash
git add runner/RUNNER.md runner/AGENTS.md runner/contracts/EVAL_PROTOCOL.md
git commit -m "docs(runner): add Historian role to RUNNER.md and AGENTS.md; historian_interval in EVAL_PROTOCOL"
```

---

## Self-Review

### Spec coverage check

| Spec section | Covered by task |
|---|---|
| §1.1 ASSUMPTION_REGISTER.md skeleton | Task 1 (init creates it) |
| §1.2 STRATEGY_MEMO.md (written by Historian) | Task 9 (historian.md §3 Step 7) |
| §1.3 PATTERN_BOOK.md skeleton | Task 1 (init creates it) |
| §2 Historian role (identity, inputs, procedure, trigger) | Task 9 (historian.md) |
| §3.1 Evidence-first Reviewer | Task 10 (reviewer.md) |
| §3.2 Mandatory assumption registration on keep | Task 10 (reviewer.md §3 Phase 3 step 11) |
| §3.3 Discard → falsification check | Task 10 (reviewer.md §3 Phase 3 step 12) |
| §4.1 New Planner inputs | Task 11 (planner.md §2) |
| §4.2 Assumption-aware novelty check | Task 11 (planner.md §3 Step 4) |
| §4.2 Pattern-informed strategy | Task 11 (planner.md §3 Step 5) |
| §4.3 assumptions_tested field in NEXT_EXPERIMENT.md | Task 11 (planner.md §4) |
| §4.4 A_diagnose removed | Task 6 (plan_check enforcement removed); Task 12 (EVAL_PROTOCOL) |
| §5.1 CAMPAIGN_STATE.json v2 fields | Task 1 (init_campaign); Task 4 (migration) |
| §5.2 historian_run() + historian_finalize() | Task 4 |
| §5.3 Revised C2 protocol | Task 6 (remove old gates; resolve_c2 update) |
| §5.4 Revised loop sequence | Task 7 (run_round.sh new stages) |
| §5.5 init_campaign skeleton creation | Task 1 |
| §6.1 Token columns in results.tsv | Task 2 (log.py) |
| §6.2 Token params in review_finalize / historian_finalize | Task 5 + Task 4 |
| §6.3 TOKEN_SUMMARY.txt | Task 3 |
| §7 historian_interval validation | Task 8 (schema.py) |
| Documentation (RUNNER.md, AGENTS.md) | Task 12 |

All spec sections are covered. No gaps.

### Placeholder scan

No TBD, TODO, or "implement later" items. All code blocks are complete. All commands include expected output.

### Type consistency check

- `historian_run()` returns `dict[str, Any]` with keys: `status`, `trigger`, `rounds_covered`, `current_round`, `campaign_dir`
- `historian_finalize()` params: `trigger: str`, `patterns_added: int`, `assumptions_flagged: int`, `tokens_used: int`
- `review_finalize()` new params: `planner_tokens: int`, `executor_tokens: int`, `reviewer_tokens: int`
- `append_result()` new params: `planner_tokens: int`, `executor_tokens: int`, `reviewer_tokens: int`, `historian_tokens: int`
- `write_token_summary()` returns `str` (the summary line)
- `validate_assumption_register()` returns `list[str]`

All cross-task references are consistent.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-26-harness-meta-cognitive-tier.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
