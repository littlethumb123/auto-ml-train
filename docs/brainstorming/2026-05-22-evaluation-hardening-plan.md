# Evaluation Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 evaluation bugs and add 3 cheap safety assertions to close the harness's evaluation integrity gaps.

**Architecture:** All changes stay within the existing contract-gated, multi-role architecture. No new roles, no new tools. Fixes touch train.py (campaign template), runner_driver.py (mandatory-tool gate), bootstrap_ci.py (lift alignment), and anomaly.py (upper-bound check). Assertions are added directly in train.py before the structured output block.

**Tech Stack:** Python 3.10+, NumPy, scikit-learn, pytest

**Source:** This plan was produced by reviewing auto-ml-train-main against the repo-learning knowledge base (223 wiki pages on agentic harness engineering). The full audit is in `docs/harness-engineering-review.md`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `campaigns/smoke-test-creditcard/train.py` | Modify | Replace inline `_lift_at_pct` with `shared.metrics`, save prediction artifacts, add assertions |
| `shared/metrics.py` | Read-only | Canonical lift implementation (argsort top-k) — already correct |
| `runner/tools/bootstrap_ci.py` | Modify | Replace local `_lift_at_pct` with import from `shared.metrics` |
| `runner/runner_driver.py` | Modify | Change `tools_ran is not None` to fail-closed default |
| `runner/tools/anomaly.py` | Modify | Add upper-bound anomaly check (>0.99) |
| `tests/tools/test_anomaly.py` | Modify | Add test for upper-bound anomaly |
| `tests/safety/test_mandatory_tools.py` | Modify | Update backward-compat test to reflect fail-closed behavior |
| `tests/tools/test_bootstrap_ci.py` | Create | Test that bootstrap_ci lift matches shared.metrics |

---

## Task 1: Standardize lift_at_10 implementation (F2 — Bug)

**Problem:** `train.py` uses `np.percentile` threshold (selects variable-count samples from score ties). `shared/metrics.py` and `bootstrap_ci.py` use `np.argsort` top-k (selects exactly k samples). The bootstrap CI therefore computes confidence intervals on a **different statistic** than the one reported by train.py.

**Fix:** Replace the inline `_lift_at_pct` in `train.py` with `shared.metrics.lift_at_percentage`.

**Files:**
- Modify: `campaigns/smoke-test-creditcard/train.py:22` (add import)
- Modify: `campaigns/smoke-test-creditcard/train.py:93-100` (delete inline function, use shared)

- [ ] **Step 1: Add the import to train.py**

At line 22 (after the `precision_recall_curve` import), add:

```python
from shared.metrics import lift_at_percentage
```

- [ ] **Step 2: Delete the inline `_lift_at_pct` function and replace usage**

Delete lines 93-100 (the `_lift_at_pct` function definition):
```python
# DELETE THIS BLOCK:
def _lift_at_pct(y_true: np.ndarray, y_score: np.ndarray, pct: float) -> float:
    thresh = np.percentile(y_score, 100.0 * (1.0 - pct))
    flagged = y_score >= thresh
    if flagged.sum() == 0:
        return 0.0
    return float(y_true[flagged].mean() / (y_true.mean() + 1e-12))
```

Replace the `lift_at_10` computation (was `_lift_at_pct(y_val_arr, y_prob_val, 0.10)`) with:
```python
lift_at_10 = lift_at_percentage(y_val_arr, y_prob_val, 0.10)
```

- [ ] **Step 3: Run existing tests to confirm nothing breaks**

Run: `python -m pytest tests/ -v --tb=short -q`
Expected: All existing tests PASS (no test currently asserts the percentile behavior)

- [ ] **Step 4: Commit**

```bash
git add campaigns/smoke-test-creditcard/train.py
git commit -m "fix(eval): standardize lift_at_10 to shared.metrics.lift_at_percentage

train.py used np.percentile threshold (variable sample count from ties).
shared/metrics.py and bootstrap_ci.py use np.argsort top-k (exact k).
CI bounds were computed on a different statistic than reported.
Now all three compute identical lift."
```

---

## Task 2: Align bootstrap_ci lift with shared.metrics (F2 continued)

**Problem:** `bootstrap_ci.py` has its own local `_lift_at_pct` that duplicates `shared/metrics.py`. While both currently use the same argsort algorithm, dual implementations will drift.

**Files:**
- Modify: `runner/tools/bootstrap_ci.py:1-22` (replace local function with import)
- Create: `tests/tools/test_bootstrap_ci_lift.py`

- [ ] **Step 1: Write the failing test**

Create `tests/tools/test_bootstrap_ci_lift.py`:

```python
"""Verify bootstrap_ci's lift matches shared.metrics exactly."""
from __future__ import annotations

import numpy as np
import pytest

from runner.tools.bootstrap_ci import bootstrap_ci
from shared.metrics import lift_at_percentage


def test_bootstrap_lift10_matches_shared_metrics():
    """Point estimate from bootstrap_ci must equal shared.metrics.lift_at_percentage."""
    rng = np.random.default_rng(99)
    y_true = rng.integers(0, 2, size=500).astype(float)
    y_prob = rng.random(500)

    # bootstrap_ci point estimate
    result = bootstrap_ci(y_true, y_prob, metric="lift_10pct", n_boot=10)
    bc_point = result["point"]

    # shared.metrics direct call
    sm_point = lift_at_percentage(y_true, y_prob, 0.10)

    assert bc_point == pytest.approx(sm_point, abs=1e-12), (
        f"bootstrap_ci lift={bc_point} != shared.metrics lift={sm_point}"
    )
```

- [ ] **Step 2: Run the test to confirm it passes (since both currently use argsort)**

Run: `python -m pytest tests/tools/test_bootstrap_ci_lift.py -v`
Expected: PASS (both already use the same algorithm — this test locks it in)

- [ ] **Step 3: Replace local `_lift_at_pct` with shared.metrics import**

In `runner/tools/bootstrap_ci.py`, replace the local `_lift_at_pct` function (lines 14-20):

```python
# DELETE THIS BLOCK:
def _lift_at_pct(pct: float):
    def fn(y, s):
        k = max(1, int(len(y) * pct))
        top_k = np.argsort(np.asarray(s))[::-1][:k]
        base = np.asarray(y).mean()
        return float(np.asarray(y)[top_k].mean() / base) if base > 0 else 0.0
    return fn
```

Add import at top of file:
```python
from shared.metrics import lift_at_percentage
```

Update `_metric_fn` to use it:
```python
    if name == "lift_1pct":
        return lambda y, s: lift_at_percentage(y, s, 0.01)
    if name == "lift_5pct":
        return lambda y, s: lift_at_percentage(y, s, 0.05)
    if name == "lift_10pct":
        return lambda y, s: lift_at_percentage(y, s, 0.10)
```

- [ ] **Step 4: Re-run the test to confirm it still passes**

Run: `python -m pytest tests/tools/test_bootstrap_ci_lift.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runner/tools/bootstrap_ci.py tests/tools/test_bootstrap_ci_lift.py
git commit -m "fix(eval): deduplicate lift in bootstrap_ci — use shared.metrics

Removes local _lift_at_pct, imports lift_at_percentage from shared.metrics.
Adds regression test locking bootstrap_ci and shared.metrics to identical results."
```

---

## Task 3: Fix mandatory-tool gate bypass (F3 — Bug)

**Problem:** In `runner_driver.py:561`, when `tools_ran` is `None` (the default), the entire mandatory tool check is silently skipped. A Reviewer can return `verdict="keep"` without running any mandatory tools. The existing test suite explicitly validates this as "backward compat," but it undermines the safety contract.

**Fix:** Change from `tools_ran is not None` (opt-in) to default `tools_ran=[]` and always enforce.

**Files:**
- Modify: `runner/runner_driver.py:561` (change guard condition)
- Modify: `tests/safety/test_mandatory_tools.py` (update backward-compat expectations)

- [ ] **Step 1: Find the `review_finalize` function signature**

In `runner/runner_driver.py`, locate the `review_finalize` function signature. The `tools_ran` parameter will have `tools_ran=None`. Change the default:

```python
# BEFORE:
def review_finalize(
    ...
    tools_ran=None,
    ...
):

# AFTER:
def review_finalize(
    ...
    tools_ran=None,  # Keep None default for signature compatibility
    ...
):
```

- [ ] **Step 2: Change the guard at line 561 to fail-closed**

Replace:
```python
    if tools_ran is not None and mandatory_raw and verdict == "keep":
```

With:
```python
    if mandatory_raw and verdict == "keep":
        if tools_ran is None:
            tools_ran = []  # fail-closed: missing tools_ran treated as no tools run
```

The rest of the block (normalizing and checking `mandatory_norm - ran_norm`) stays unchanged.

- [ ] **Step 3: Write test for the new fail-closed behavior**

Add to `tests/safety/test_mandatory_tools.py`:

```python
def test_keep_rejected_when_tools_ran_is_none(campaign: Path):
    """Fail-closed: tools_ran=None with mandatory tools must reject keep."""
    runner_driver.init_campaign(campaign_dir=str(campaign))
    res = runner_driver.review_finalize(
        verdict="keep",
        commit="c1",
        metrics={"val_pr_auc": 0.90, "lift_at_10": 5.0, "macro_f1": 0.8, "val_f1": 0.7},
        action_type="A_hp",
        hypothesis="h",
        description="d",
        model_family="lightgbm",
        n_features=10,
        campaign_dir=str(campaign),
        # tools_ran intentionally omitted (defaults to None)
    )
    assert res["verdict"] == "malformed", (
        "Mandatory tools configured but tools_ran=None should reject keep"
    )
```

- [ ] **Step 4: Remove or update the old backward-compat test**

If there is a test that asserts `tools_ran=None` bypasses the gate, update it to expect `malformed` instead of `keep`. Search for tests that call `review_finalize` without `tools_ran` and expect `keep` when mandatory tools are configured.

- [ ] **Step 5: Run the full safety test suite**

Run: `python -m pytest tests/safety/ -v --tb=short`
Expected: All PASS, including the new fail-closed test

- [ ] **Step 6: Commit**

```bash
git add runner/runner_driver.py tests/safety/test_mandatory_tools.py
git commit -m "fix(safety): mandatory tool gate now fail-closed

tools_ran=None with mandatory_tools configured now rejects keep verdict
instead of silently bypassing the check. Prevents Reviewer from accepting
experiments without running required validation tools."
```

---

## Task 4: Save prediction artifacts for bootstrap CI (F9 — Bug)

**Problem:** `bootstrap_ci.py` requires `y_true` and `y_prob_or_pred` arrays. But `train.py` never saves these — it only prints scalar metrics. The Reviewer cannot run bootstrap CI on the actual predictions. This makes the entire CI tool dead code for the smoke-test campaign.

**Fix:** Save `y_val_true.npy` and `y_val_prob.npy` from train.py so tools can load them.

**Files:**
- Modify: `campaigns/smoke-test-creditcard/train.py` (add np.save calls)
- Modify: `runner/contracts/EVAL_PROTOCOL.md` (document artifact paths — if exists)

- [ ] **Step 1: Add prediction artifact saving to train.py**

After `y_prob_val = model.predict_proba(X_val)[:, 1]` (line 86), add:

```python
# Save prediction artifacts for Reviewer tools (bootstrap CI, metric re-computation)
_artifact_dir = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(_artifact_dir, exist_ok=True)
np.save(os.path.join(_artifact_dir, "y_val_true.npy"), y_val_arr)
np.save(os.path.join(_artifact_dir, "y_val_prob.npy"), y_prob_val)
```

- [ ] **Step 2: Add artifact paths to structured output**

After the existing structured output block (the `print("---")` section), add:

```python
print(f"y_val_true_path:  artifacts/y_val_true.npy")
print(f"y_val_prob_path:  artifacts/y_val_prob.npy")
```

- [ ] **Step 3: Add artifacts/ to .gitignore**

Ensure `campaigns/*/artifacts/` is in `.gitignore` so binary prediction arrays are not committed:

```bash
echo "campaigns/*/artifacts/" >> .gitignore
```

- [ ] **Step 4: Run train.py to verify artifacts are created**

```bash
cd campaigns/smoke-test-creditcard
python train.py
ls -la artifacts/
```

Expected: `y_val_true.npy` and `y_val_prob.npy` exist, each ~200-400KB

- [ ] **Step 5: Verify bootstrap_ci can load and run**

```python
import numpy as np
from runner.tools.bootstrap_ci import bootstrap_ci

y_true = np.load("campaigns/smoke-test-creditcard/artifacts/y_val_true.npy")
y_prob = np.load("campaigns/smoke-test-creditcard/artifacts/y_val_prob.npy")
result = bootstrap_ci(y_true, y_prob, metric="pr_auc")
print(result)  # Should show point, lo, hi, se keys
```

- [ ] **Step 6: Commit**

```bash
git add campaigns/smoke-test-creditcard/train.py .gitignore
git commit -m "feat(eval): save y_val_true/y_val_prob for Reviewer tools

train.py now saves prediction arrays to artifacts/ so bootstrap_ci
and future metric re-computation tools can operate on actual predictions
instead of being dead code."
```

---

## Task 5: Add probability range validation (F5 — Cheap Win)

**Problem:** If `predict_proba` returns NaN, values outside [0,1], or all-identical values, downstream metrics silently produce garbage. No assertion catches this.

**Files:**
- Modify: `campaigns/smoke-test-creditcard/train.py` (add 3 assertions after predict_proba)

- [ ] **Step 1: Add assertions after predict_proba**

After `y_prob_val = model.predict_proba(X_val)[:, 1]` and after the np.save block (from Task 4), add:

```python
# Sanity: probability output must be valid
assert not np.isnan(y_prob_val).any(), "predict_proba returned NaN"
assert y_prob_val.min() >= 0.0 and y_prob_val.max() <= 1.0, (
    f"predict_proba out of [0,1]: min={y_prob_val.min():.6f}, max={y_prob_val.max():.6f}"
)
assert y_prob_val.std() > 1e-8, (
    f"predict_proba is near-constant (std={y_prob_val.std():.2e}) — model may not have learned"
)
```

- [ ] **Step 2: Run train.py to verify assertions pass on current model**

Run: `cd campaigns/smoke-test-creditcard && python train.py`
Expected: No assertion error — the LightGBM model produces valid probabilities

- [ ] **Step 3: Commit**

```bash
git add campaigns/smoke-test-creditcard/train.py
git commit -m "fix(eval): add probability range validation after predict_proba

Catches NaN, out-of-[0,1], and constant predictions before they corrupt
downstream metrics with silent garbage."
```

---

## Task 6: Add upper-bound anomaly detection (F7 — Cheap Win)

**Problem:** The anomaly detector catches suspiciously **low** results but lets suspiciously **perfect** results (>0.99 PR-AUC) pass without flagging. A leaking feature or a label-in-features bug would show as a perfect score and slip through.

**Files:**
- Modify: `runner/tools/anomaly.py` (add upper-bound check)
- Modify: `tests/tools/test_anomaly.py` (add test for upper-bound)

- [ ] **Step 1: Write the failing test**

Add to `tests/tools/test_anomaly.py`:

```python
def test_anomaly_fires_suspiciously_perfect():
    """Scores > 0.99 should be flagged as potential leakage."""
    res = anomaly.check_anomaly(
        latest_row={"val_pr_auc": 0.999, "status": "keep", "model_family": "lgb"},
        history=[{"val_pr_auc": 0.80, "status": "keep"}],
        floor=0.75,
        primary_metric="val_pr_auc",
    )
    assert res["fired"] is True
    assert "perfect" in res["reason"].lower() or "suspicious" in res["reason"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/tools/test_anomaly.py::test_anomaly_fires_suspiciously_perfect -v`
Expected: FAIL — current code does not flag high values

- [ ] **Step 3: Add upper-bound check to anomaly.py**

In `runner/tools/anomaly.py`, in the `check_anomaly` function, add this block **before** the existing lower-bound check (before `if 0 < value < threshold:`):

```python
    # Upper-bound: suspiciously perfect results suggest leakage
    if value > 0.99:
        family = latest_row.get("model_family", "unknown")
        return {
            "fired": True,
            "reason": f"{primary_metric}={value:.6f} suspiciously perfect (>0.99) — potential data leakage",
            "proposed_diagnostic": (
                f"Check for target leakage: inspect feature correlations with target, "
                f"verify train/val split has no row overlap, check for future-peeking features."
            ),
        }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/tools/test_anomaly.py -v`
Expected: All tests PASS, including the new upper-bound test

- [ ] **Step 5: Commit**

```bash
git add runner/tools/anomaly.py tests/tools/test_anomaly.py
git commit -m "fix(eval): anomaly detector now flags suspiciously perfect results

Scores >0.99 are flagged as potential data leakage. Previously only
low scores triggered the anomaly check."
```

---

## Task 7: Add minimum positives assertion (F8 — Cheap Win)

**Problem:** If the validation split has <30 positive cases, metrics like lift-at-10% and PR-AUC are statistically unreliable. No assertion catches this.

**Files:**
- Modify: `campaigns/smoke-test-creditcard/train.py` (add 1 assertion after split)

- [ ] **Step 1: Add assertion after the train/val split**

In `train.py`, after `y_val_arr` is defined (after the `train_test_split` calls), add:

```python
# Sanity: validation split must have enough positives for reliable metrics
assert y_val_arr.sum() >= 30, (
    f"Validation split has only {int(y_val_arr.sum())} positives — need ≥30 for reliable lift/PR-AUC"
)
```

- [ ] **Step 2: Run train.py to verify assertion passes**

Run: `cd campaigns/smoke-test-creditcard && python train.py`
Expected: No assertion error — creditcard.csv has ~492 positives total, ~98 in 20% val split

- [ ] **Step 3: Commit**

```bash
git add campaigns/smoke-test-creditcard/train.py
git commit -m "fix(eval): assert ≥30 positives in validation split

Prevents silently unreliable metrics when positive class is too sparse
for meaningful lift or PR-AUC computation."
```

---

## Summary

| Task | Finding | Tier | Estimated Effort | Risk if Skipped |
|------|---------|------|-----------------|-----------------|
| 1 | Standardize lift in train.py | A (Bug) | 10 min | CI bounds on wrong statistic |
| 2 | Deduplicate lift in bootstrap_ci | A (Bug) | 15 min | Future drift between implementations |
| 3 | Fail-closed mandatory tool gate | A (Bug) | 20 min | Reviewer can skip mandatory tools |
| 4 | Save prediction artifacts | A (Bug) | 30 min | bootstrap_ci is dead code |
| 5 | Probability range validation | B (Cheap) | 5 min | Silent garbage from broken model |
| 6 | Upper-bound anomaly detection | B (Cheap) | 10 min | Leakage goes undetected |
| 7 | Minimum positives assertion | B (Cheap) | 3 min | Unreliable metrics on sparse data |

**Total: ~1.5 hours. Zero new dependencies. Zero architectural changes.**

**Execution order:** Tasks 1→2 (lift fix), then 4→5→7 (train.py changes), then 3 (gate fix), then 6 (anomaly). This minimizes merge conflicts in train.py by batching related changes.
