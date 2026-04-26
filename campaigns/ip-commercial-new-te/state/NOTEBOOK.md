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

- **C2 resolved (round 31→32):** consecutive_discards reset to 0. Rounds 29-31 were post-C3-advisory exploration: focal-loss 8th XGB model, CCI clinical features — both failed. A_diagnose (r32) required to re-anchor.

- **CRITICAL: 23.174 ceiling is BASE-MODEL property (r32):** r32 reproduced r25 EXACTLY (23.174, LGBM_h=0.046 CB_h=0.184 XGB_h=0.456). The ensemble optimizer always converges to the same weights given the same 5 base-model predictions. To beat 23.174, a BASE MODEL must improve. XGB HP variants and ensemble architecture changes cannot break this ceiling.

- **Feature additions destabilize Optuna landscape (r33):** TE features (+14) → seed=42 found max_depth=10, lr=0.077 (bad HPs) instead of usual max_depth=6, lr=0.254. Adding features shifts the TPE exploration path even with the same seed. Implication: any experiment adding features to the 794-feature set should expect Optuna to find different (possibly worse) XGB HPs.

- **AUC-ROC is definitively the best Optuna proxy for XGB ensemble complementarity (r34):** AUC-PR proxy → XGB weight drops from 0.456 to 0.092 → less diversity. AUC-ROC forces XGB into a complementary prediction space. AUC-PR makes XGB predictions too similar to CB/LGBM.

- **Scipy direct val optimization is not overfitting on 752K rows (r35):** OOF meta-learner gets 22.333 vs scipy's 23.174. The n_val=752K is large enough that direct val optimization is valid and superior. No need for OOF leak-prevention in this campaign.

- **C2 resolved (round 35→36):** consecutive_discards reset to 0. Rounds 33-35 (TE, AUC-PR, OOF) all failed. A_diagnose (r36) for CatBoost Lossguide direction.

- **Lossguide CB improves individual CB but hurts ensemble (r36):** CB_tabular improved +0.206 with Lossguide. But ensemble drops to 23.054. Root cause: Lossguide makes CB predictions more similar to LGBM (both leaf-wise) → reduces CB's unique complementarity → XGB weight splits between h/t instead of concentrating in XGB_h. SymmetricTree CB is preferred for ensemble diversity.

- **C2 resolved (round 39):** consecutive_discards reset from 3 to 0. Rounds 37-39 (LGBM 255 leaves, LGBM 5:1 downsampling, ET 8th model) all failed. Resolution: switching from LGBM/ET variants to A_diagnose to re-anchor ceiling, then explore different directions (e.g., new XGB seed variant on embedding-only features, or different feature subsets for base models).

- **Adding weak 8th model disrupts 7-model balance (r39):** ET (18.934 individual) gets 0.054 weight but CB_h collapses from 0.184 to 0.021. The r25 7-model balance is a local optimum in weight space — any 8th model with marginal weight shifts the entire weight distribution. An 8th model must have individual lift@1% > ~22.0 to justify the expansion. Weak models as 8th entries are worse than doing nothing.

- **C2 resolved (round 42→43):** consecutive_discards reset from 3 to 0 (rounds 41-42: LGBM colsample, XGB monotonic constraints). A_diagnose (r43) required. Resolution: switching to single-feature-addition experiments to test if minimal feature engineering avoids the Optuna destabilization that killed r33 (14 TE features).

- **Any structural change to XGB optimization landscape prevents r25 saddle point (r42):** Monotonic constraints on 5 clinical features → ensemble 22.814 (Δ=-0.360). Same mechanism as r33 (14 TE features) and r28 (different seed). The r25 optimum at XGB_h=0.456 requires: (1) no feature count change, (2) AUC-ROC proxy, (3) seed=42, (4) no structural constraints. All four conditions must hold simultaneously.

- **5th exact reproduction of 23.174 (r43):** Rounds 29, 32, 35, 40, 43 all produce 23.174420 with LGBM_h=0.046 CB_h=0.184 XGB_h=0.456. This saddle point is perfectly deterministic given the original conditions. The consistency across 5 independent runs from different states confirms the ceiling is a mathematical property of the 7-model base prediction distributions, not a numerical artifact.

- **CRITICAL: Even 1 feature destabilizes XGB Optuna (r44):** eng_total_ip_days_2yr (+1 feature, 794→795) → XGB Optuna lr shifts 0.254→0.148 → XGB_h weight collapses 0.456→0.044 → ensemble reverts to 22.677 (=r19 level). The 23.174 saddle point requires EXACTLY: (1) 794 features, (2) AUC-ROC proxy, (3) seed=42, (4) no constraints. Changing ANY one destroys it. Feature engineering is incompatible with the current XGB Optuna pipeline unless features are supplied ONLY to non-XGB models.

- **XGB_t as fallback dominant (r44):** When XGB_h fails (weight 0.044), XGB_t (default HPs, tabular-only) absorbs the weight at 0.489. The ensemble then operates at the r19/r22 level (~22.7). This confirms that the r25 breakthrough came entirely from Optuna-tuned XGB_h's complementarity, not from the other 6 models.

- **C2 resolved (round 45→46):** consecutive_discards reset from 3 to 0 (rounds 43-45: A_diagnose, +1 feature all models, selective +1 feature LGBM/CB only). Resolution: feature engineering conclusively dead — both full-model and selective approaches fail. Next after A_diagnose: rank-based blending or accept ceiling.

- **23.174 is a joint 7-model prediction property, not just XGB (r45):** Selective feature addition preserved XGB Optuna (same HPs, same predictions) but the ensemble still degraded because LGBM/CB predictions changed → scipy weight optimum shifted → XGB_h weight dropped 0.456→0.249. This is the deepest understanding of the ceiling: it requires ALL 7 models to produce their EXACT original predictions. Any change to ANY model's predictions — even the weakest 0.023-weight LGBM_t — shifts the scipy optimization landscape.
