---
schema_version: 1
campaign_id: "ip-commercial-new-te"
count: 0
last_updated: "2026-04-24"
---

# Observations worth remembering (non-dead-end)

(None recorded yet. Reviewer appends surprising-but-not-dead-end observations here.)

- embedding_only baseline: lift@1%=18.162 — does NOT beat tabular_only (21.578). Embeddings only add value combined with tabular (+0.635 in hybrid). Round 3.
- embedding_only trains 6× faster than tabular_only (24s vs 143s) — useful for rapid ablations.

- Round 4: top-150 feature selection (73 emb, 77 tab) gives lift@1%=21.767 vs full hybrid 22.213. Training 1.8× faster. _index_dt_parsed appeared in top-10 — temporal leakage risk, exclude in future rounds.

- Round 5 A_hp: Optuna had only 7 trials in 500s (71s/trial with 200-iter CatBoost on 789 feats × 508K rows). Fix: use 50-iter proxy (~17s/trial → 28+ trials). Or switch to LightGBM proxy for faster iteration.
- Split cache loads in 27s (down from 250s data pipeline). Major infrastructure win for rounds 6-100.
- Round 5 result (22.162) is within 0.1 SE of prior best (22.213) — noise, not regression.

- **C2 resolved (round 5):** consecutive_discards reset from 3 to 0. Resolution: 3 discards were informative baselines and infrastructure fixes, not a true plateau. Root cause: Optuna proxy too slow (71s/trial). Resolution: use 50-iter proxy and/or LightGBM for faster HP search. A_diagnose follows as protocol requires.

- Round 6 SHAP: 50/50 embedding/tabular split in top-50 features. Embeddings and tabular are complementary, not redundant. Hybrid is confirmed right feature set.
- Round 6 error analysis: 75.5% of positives below neg-p99. Task is inherently hard for lower-risk positives. Model is well-calibrated overall.
- CI check: target gap 1.787 > 2×SE=0.990. Gap is detectable. No CV upgrade needed.

- **C2 resolved (round 13):** consecutive_discards reset from 3 to 0. Resolution: HP search cannot outperform LGBM defaults (same params found repeatedly). Abandoning proxy-based HP search. Next: three-family mean ensemble (LGBM+CatBoost+XGBoost, no meta-learner) to avoid in-sample leakage.

- **C2 resolved (round 28):** consecutive_discards reset from 3 to 0. Resolution: 3 discards were exploratory XGB HP experiments (seeds 42/7, CB/LGBM AUC-ROC). All confirm 23.174 is the genuine ceiling for this 7-model ensemble approach. A_diagnose will verify CI and target gap. Next: try wider XGB search space.
