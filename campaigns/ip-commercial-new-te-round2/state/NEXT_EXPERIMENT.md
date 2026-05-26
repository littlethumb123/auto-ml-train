---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 1
planner_invocation_at: "2026-05-26T15:05:00Z"
action_type: "A_validate"
hypothesis: "Tabular-only CatBoost baseline — establish val_lift_1pct floor (~21.578 expected from prior campaign)"
expected_effect_size: 0.0
base_commit: "9eb8e68e7a57d5c1b10f87e2d3a4b5c6d7e8f9a0"
touches_helpers: false
helpers_declared: []
escalation: null
assumptions_tested: []
---

## 1. Context summary

Round 1 of 50. Campaign is freshly initialized. No experiments have run in this campaign instance. Target: val_lift_1pct >= 24.0. Primary metric: val_lift_1pct. Noise floor: 0.3. Budget: 0/50 used.

STRATEGY_GUIDE mandates a three-way comparison (tabular_only → embedding_only → hybrid) before any HP tuning. The tabular_only CatBoost baseline (~21.578) and hybrid (~22.213) are known from a prior campaign run, but must be re-established here as the official results.tsv floor. embedding_only is completely untested.

The existing train.py is already correctly configured for this experiment: `A_validate: tabular_only CatBoost baseline`, FEATURE_SET="tabular_only", _USE_ENGINEERED=False, CatBoost defaults (depth=6, lr=0.05, od_wait=80, auto_class_weights=Balanced, use_best_model=True). The Executor only needs to commit and run it.

## 2. Evidence from memory

**No prior results.** Results.tsv is empty. PATTERN_BOOK is empty. ASSUMPTION_REGISTER is empty.

PRIORS.md known facts:
- tabular_only prior: ~21.578 val_lift_1pct (from prior campaign)
- hybrid prior: ~22.213 val_lift_1pct
- embedding_only: unknown — open question in PRIORS.md

### Rationalization table

| Candidate | Action | UCB1 | Expected Δ | Dead-end? | Assumption risk | Selection rationale |
|-----------|--------|------|-----------|-----------|-----------------|---------------------|
| 1 | A_validate tabular_only CatBoost | ∞ | 0 (floor) | No | None — establishes baseline | **Mandatory: STRATEGY_GUIDE three-way comparison step 1** |
| 2 | A_validate embedding_only CatBoost | ∞ | 0 (floor) | No | None | Blocked: must come after tabular_only |
| 3 | A_validate hybrid CatBoost | ∞ | +0.6 vs tabular | No | None | Blocked: three-way comparison order |
| **Selected** | **A_validate tabular_only** | | | | | **First mandatory step; train.py already staged** |

## 3. Plan

The existing `train.py` is correctly configured. The Executor MUST NOT change it. Steps:

1. **Verify** DESCRIPTION="A_validate: tabular_only CatBoost baseline — establish floor", FEATURE_SET="tabular_only", _USE_ENGINEERED=False, HARD_TIMEOUT=1800
2. **git add + commit** the current train.py
3. **Run**: `python3 campaigns/ip-commercial-new-te-round2/train.py > campaigns/ip-commercial-new-te-round2/run.log 2>&1`
4. **Expected output:** val_lift_1pct ≈ 21.578 (±0.3 per prior campaign), val_auc_roc ≈ 0.853

The split cache at `campaigns/ip-commercial-new-te/.cache/splits_tabular_only_20250630.npz` likely already exists from prior runs (saves ~30s rebuild time).

## 4. Helpers

None.

## 5. How this differs from prior experiments

This is the first experiment in this campaign instance. train.py has not been modified — the Executor just commits and runs the pre-staged baseline.

## 6. Escalation

null — mandatory baseline step.
