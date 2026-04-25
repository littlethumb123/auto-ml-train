---
schema_version: 1
campaign_id: "ip-commercial-new-te"
count: 8
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
- **Any HP tuning or ensemble architecture change while keeping 5 base models fixed:** r32 and r35 both prove that 23.174 is a hard property of the 5 base-model predictions (LGBM_h, LGBM_t, LGBM_e, CB_h, CB_t). To beat 23.174, a base model must produce fundamentally different predictions.
