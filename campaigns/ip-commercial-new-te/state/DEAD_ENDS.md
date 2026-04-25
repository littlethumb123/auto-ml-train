---
schema_version: 1
campaign_id: "ip-commercial-new-te"
count: 11
last_updated: "2026-04-25"
---

# Dead ends — do NOT retry

- **XGB HP tuning beyond AUC-ROC seed=42:** All variants (seed=7, CB+XGB dual AUC-ROC, LGBM AUC-ROC, AUC-PR proxy) fail to beat r25. AUC-ROC seed=42 is the global optimum for XGB. (r26-r28, r34)
- **8th ensemble model (focal loss XGB):** Adding a second XGB variant dilutes the weight budget without new prediction diversity. The AUC-ROC XGB already monopolizes the complementarity the ensemble needs from the XGB family. (r30)
- **Aggregate clinical feature scores (CCI, ER×IP interaction):** 794-feature set already encodes all individual flags; CCI and ER×IP are correlated aggregates that add noise. (r31)
- **Target encoding of categorical columns:** Adds 14+ features, destabilizes Optuna TPE landscape, Optuna finds bad XGB HPs. TE preprocessing is structurally incompatible with the Optuna-in-ensemble pipeline at this feature count. (r33)
- **AUC-PR as Optuna proxy:** Finds XGB HPs that reduce ensemble complementarity (XGB weight drops to 0.092 vs 0.456 with AUC-ROC). AUC-ROC proxy is definitively superior for this ensemble. (r34)
- **OOF stacking with Ridge meta-learner:** 752K val rows are large enough that scipy direct optimization does not overfit. OOF meta-learner gets 22.333 vs scipy's 23.174. OOF is strictly worse here. (r35)
- **CatBoost Lossguide grow_policy:** Individual CB models improve but ensemble degrades (23.054 vs 23.174). Lossguide makes CB more similar to LGBM (both leaf-wise), reducing CB's unique complementarity. SymmetricTree CB provides better ensemble diversity. (r36)
- **LGBM num_leaves increase (127→255):** More leaves causes faster overfitting → earlier stopping → WEAKER individual model (21.853 vs 22.162). 508K train rows do not support >127 leaves at lr=0.05. Increasing LGBM capacity hurts. (r37)
- **Any HP tuning or ensemble architecture change while keeping 5 base models fixed:** r32 and r35 both prove that 23.174 is a hard property of the 5 base-model predictions (LGBM_h, LGBM_t, LGBM_e, CB_h, CB_t). To beat 23.174, a base model must produce fundamentally different predictions.
- **LGBM training data downsampling (5:1 vs 10:1):** 5:1 makes LGBM individually strongest ever (22.385 vs 22.162) but ensemble is WORSE (23.089 vs 23.174). LGBM_h weight barely moves (0.050 vs 0.046). Root cause: LGBM and XGB are both leaf-wise gradient boosters — their prediction manifolds are structurally correlated regardless of training distribution. No training-data manipulation can decouple them. (r38)
- **Adding weak 8th model (ExtraTreesClassifier) to 7-model ensemble:** ET individually 18.934 (weak); ET gets 0.054 weight but CB_h collapses from 0.184 to 0.021. Ensemble degrades to 22.848. The r25 7-model balance is fragile — any 8th model that gets marginal weight disrupts the CB/XGB complementarity distribution. An 8th model must have individual lift@1% > ~22.0 to justify the weight budget expansion. (r39)
