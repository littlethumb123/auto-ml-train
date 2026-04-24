---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 2
planner_invocation_at: "2026-04-24T04:25:00Z"
action_type: "A_validate"
hypothesis: "Adding 256 new TE embedding features (hybrid) to the tabular_only baseline measures the embedding lift at 1% with a controlled A/B comparison."
expected_effect_size: "Δval_lift_1pct: +0.5 to +3.0 (directional — embeddings add signal not in tabular)"
base_commit: "322a4f3"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 2. Best: tabular_only CatBoost lift@1%=21.578. STRATEGY_GUIDE §1 trigger: "tabular_only baseline exists; no hybrid baseline" → A_validate hybrid. This is the single most important experiment of the campaign: it measures the standalone contribution of the new TE embeddings.

## 2. Evidence from memory

- **results.tsv row 1**: tabular_only, lift@1%=21.578, auc_roc=0.853, 534 features, 300.7s total.
- **DEAD_ENDS.md**: empty.
- **PRIORS.md**: No prior embedding-vs-tabular comparison for this embedding source. The notebook showed positive embedding lift for the production RAP embeddings; new TE is expected to be at least as strong.
- **STRATEGY_GUIDE §1**: Must test hybrid before committing to HP search on either feature set. Cannot know which feature set to invest HP search in without this comparison.

**Candidate actions:**
1. **A_validate hybrid** (chosen): Direct comparison with round 1. Same model config, only change = FEATURE_SET. Δ is fully attributable to embeddings. Expected Δ: +0.5–3.0 lift points.
2. **A_hp on tabular_only**: Premature — need hybrid comparison first before deciding which feature set to optimize.
3. **A_feature**: Premature — should know embedding contribution before engineering additional features.

## 3. Plan

**One change from round 1 train.py:** `FEATURE_SET = "hybrid"` (was `"tabular_only"`).

All other parameters identical to round 1:
- iterations=500, depth=6, lr=0.05, od_wait=50, auto_class_weights='Balanced'
- Same CatBoost config ensures any Δ is attributable to the feature set change only.

Expected timing: ~400s total (hybrid reads all 824 cols vs 566 for tabular_only).

## 4. Helpers

No helpers needed.

## 5. How this differs from current train.py

Single line change: `FEATURE_SET = "hybrid"` → reads 790 features (534 tabular + 256 embedding) instead of 534.

## 6. Escalation

### No escalation

Normal progression per STRATEGY_GUIDE.
