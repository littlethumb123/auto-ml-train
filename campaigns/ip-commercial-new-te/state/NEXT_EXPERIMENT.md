---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 6
planner_invocation_at: "2026-04-24T08:00:00Z"
action_type: "A_diagnose"
hypothesis: "SHAP analysis on the current hybrid best (round 2) will reveal which embeddings contribute real signal, quantify the embedding-vs-tabular split, and confirm whether bootstrap SE allows reliable detection of HP improvements."
expected_effect_size: "~0 (diagnostic only — informs next experiment strategy)"
base_commit: "f916809"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 6. c2_pending_diagnose=True (A_diagnose mandatory per STRATEGY_GUIDE §3.7 and RUNNER.md invariant). Three consecutive discards resolved:
- Round 3: embedding_only baseline (informative, expected)
- Round 4: feature selection (small regression, revealed _index_dt_parsed bug)
- Round 5: Optuna HP (noise-level result, root cause = too few trials/too slow proxy)

## 2. Evidence from memory

- **Best model**: hybrid CatBoost default params, lift@1%=22.213, round 2 commit 1171906
- **NOTEBOOK**: Optuna proxy takes ~71s/trial (200 iter × 0.35s/iter). Fix: 50-iter proxy → 17s/trial → ~28 trials/500s.
- **NOTEBOOK**: Split cache ready — all future rounds load data in 27s.
- **Bootstrap SE**: 0.496 consistently across rounds. Target gap to goal (24.0): 24.0 - 22.213 = 1.787. 1.787 / (2 × 0.496) = 1.80 — target gap is 1.80 SE, detectable but requires improvement > ~1.0 lift points to be reliable.

## 3. Plan

A_diagnose produces:
1. **SHAP analysis**: retrain hybrid CatBoost (default, round 2 config) → run shap_report on X_val → get embedding vs tabular proportion in top-10/20/50. Key question: which of 256 embeddings drive predictions?
2. **Feature importance ranking**: top-10 features by SHAP — informs round 7 feature selection strategy.
3. **Bootstrap CI check**: SE=0.496, target gap=1.787 — confirm gap is detectable (yes, 1.80 SE > 1.0).
4. **Error analysis**: score distribution on val positives vs negatives. Check for miscalibration.
5. **Proxy speed recommendation**: document 50-iter proxy plan for round 7.

## 4. Helpers

No helpers needed.

## 5. How this differs from current train.py

Retrain round 2 model (FEATURE_SET="hybrid", default params: depth=6, lr=0.05, 500 iter). Run SHAP on X_val via tools/shap_report (Python API). Print SHAP summary. Evaluate model for error analysis.

## 6. Escalation

### No escalation

A_diagnose round per protocol. After review, C2 cleared and round 7 proceeds with A_hp using faster 50-iter proxy.
