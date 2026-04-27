---
schema_version: 1
campaign_id: "smoke-test-creditcard"
round: 2
planner_invocation_at: "2026-04-27T04:00:00Z"
action_type: "A_model"
hypothesis: "XGBoost with default hyperparameters will match or exceed LightGBM's val_pr_auc of 0.815530 on the creditcard fraud dataset"
expected_effect_size: 0.010
base_commit: "2023897d3a544060477463e9e9cc7af70d25dcaf"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: []
---

## 1. Context

**Current champion:** LightGBM, spw=578, n_estimators=600, lr=0.02, num_leaves=63 → val_pr_auc=0.815530 (round 1)
**Last verdict:** keep
**Consecutive discards:** 0
**Rounds remaining:** 9 (including this one)

## 2. Evidence from memory

**Strategy Guide trigger:** "Fewer than 2 distinct model families in results.tsv" → Try ≥1 alternative family before investing in tuning.

**Candidate actions evaluated:**

1. **A_model (XGBoost):** Expected Δ: 0.005–0.015. Condition: "Early campaign; alternative families not yet compared" → HIGH ROI. No dead-ends. Families untested. Strategy Guide priority: must compare families before committing to HP tuning.

2. **A_feature (log1p(Amount), interactions):** Expected Δ: 0.005–0.020. Condition: "Champion model trained and tuned; feature coverage not inspected." Viable but Strategy Guide says compare families FIRST before feature engineering, since family rankings can reverse after tuning.

3. **A_hp (LightGBM HP tuning):** Expected Δ: 0.001–0.008. Condition: "First systematic tune of a new champion family." Viable but lower priority than family comparison — we need to know if XGBoost could be the better base before investing in LGBM tuning.

**Decision:** A_model (XGBoost) selected. Strategy Guide §1 explicitly states: "Fewer than 2 distinct model families in results.tsv → Try ≥1 alternative family before investing in tuning." This is the highest-priority trigger currently firing.

**No STRATEGY_MEMO.md exists** (Historian not yet triggered — round 2).

**Assumption interaction:** A-1-2 (LightGBM is viable) — this experiment tests whether an alternative family can match or beat it. A-1-1 (spw has minimal effect on PR-AUC) is not directly tested here.

**Pattern consistency:** No active patterns in PATTERN_BOOK.md (empty). No collision.

**Dead-ends:** None applicable.

## 3. Plan

Implement XGBoost with:
- `n_estimators=200` (XGBoost slower than LGBM; keep below 300 for 90s timeout safety)
- `learning_rate=0.05` (faster convergence given lower n_estimators)
- `max_depth=6` (default, reasonable for this feature space)
- `scale_pos_weight=578` (class ratio — carry over from round 1 baseline)
- `tree_method='hist'` (fast GPU-free tree method)
- `use_label_encoder=False`, `verbosity=0`
- Same 60/20/20 stratified split (seed=42, no change)
- Same metric computation code (no change)

One controlled change: model family switch from LightGBM to XGBoost. All evaluation code stays identical.

## 4. Helpers

None needed.

## 5. How this differs from prior experiments

Round 1 used LightGBM (spw=578). This round replaces the entire model with XGBoost (n_estimators=200, lr=0.05, max_depth=6, spw=578, tree_method='hist'). All data loading, split logic, and metric computation code remain identical.

## 6. Escalation

*(Escalation frontmatter is null — no escalation block required.)*
