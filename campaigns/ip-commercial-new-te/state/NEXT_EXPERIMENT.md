---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 18
planner_invocation_at: "2026-04-24T10:50:00Z"
action_type: "A_ensemble"
hypothesis: "Adding an embedding-only LGBM (256 embedding features, no tabular) to the 4-model ensemble creates the most structurally diverse fifth component — predictions should correlate ~0.85 with hybrid models, lower than tabular-only LGBM's 0.909."
expected_effect_size: "Δval_lift_1pct: +0.02 to +0.15 (diminishing returns expected)"
base_commit: "1656560"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 18. Best: 4-model ensemble 22.642 (round 17). Gains are shrinking (+0.034). Adding embedding-only LGBM (corr ~0.85 with hybrid — lowest correlation yet) as a 5th model may add marginal signal, particularly for members where embeddings alone drive predictions.

## 2. Evidence from memory

- Round 3: CatBoost embedding_only=18.162 (too weak for standalone). But as ensemble component at low weight it may add diversity.
- LGBM embedding_only expected ~18-20 lift@1% (standalone weak, but may correct specific errors).
- Corr(emb_only, hybrid) expected ~0.85-0.90.

## 3. Plan

5-model ensemble: LGBM_hybrid + LGBM_tabular + LGBM_emb + CB + XGB. Scipy-optimize 5 weights. LGBM_emb trained on embedding_ columns only from X_train.

## 4. Helpers

None.

## 5. How this differs

Add LGBM_emb (embedding-only column subset of X_train) alongside existing 4 models; optimize 5 weights.

## 6. Escalation

### No escalation
