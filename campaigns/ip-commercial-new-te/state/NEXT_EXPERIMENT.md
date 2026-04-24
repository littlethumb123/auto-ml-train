---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 7
planner_invocation_at: "2026-04-24T08:30:00Z"
action_type: "A_hp"
hypothesis: "Using a 50-iter proxy (vs 200-iter) enables ~28 Optuna trials in the same 500s budget, giving systematic coverage of the HP space that round 5's 7-trial search could not provide."
expected_effect_size: "Δval_lift_1pct: +0.5 to +2.0 (STRATEGY_GUIDE §2: first adequate HP search)"
base_commit: "aca68fa"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 7. Best: hybrid 22.213 (round 2). c2_pending_diagnose=False (A_diagnose completed). Round 5 A_hp failed because 200-iter proxy took 71s/trial → only 7 trials. Round 6 A_diagnose confirmed:
1. Embeddings and tabular are complementary (50/50 SHAP split) — keep full hybrid
2. Target gap (1.787) is detectable (1.8 SE) — HP search can find real improvement
3. Root cause: too-slow proxy. Fix: 50-iter proxy → 17s/trial → ~28 trials in 500s

## 2. Evidence from memory

- **Round 5 best proxy**: depth=7, lr=0.084 → full model 22.162 (noise-level discard)
- **Round 5 problem**: 7 trials, no convergence
- **Round 7 target**: 28+ trials, systematic coverage of 6D HP space
- **SHAP**: 50/50 embedding/tabular. Don't use feature-selected subset — full 789 features.
- **Split cache**: loaded in 27s. All future rounds fast.

## 3. Plan

Same HP search space as round 5. Only change: proxy `iterations=50` (was 200). Full model stays at 800 iterations. Auto-budget remains capped at 500s.
Expected timing: 27s cache + 500s Optuna (28 trials × 17s/trial) + 200s full retrain = 727s ✓ within 1800s.

## 4. Helpers

None.

## 5. How this differs from current train.py

Single change in model block: proxy `iterations=200` → `iterations=50`.

## 6. Escalation

### No escalation
