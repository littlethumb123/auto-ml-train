---
schema_version: 1
problem_id: "commercial-ip-new-te"
last_campaign: "none (first campaign for this embedding source)"
updated_at: "2026-04-24"
---

## Known good

- CatBoost with `auto_class_weights='Balanced'` is a strong default for imbalanced IP prediction.
- `od_wait=80` with `use_best_model=True` prevents overfitting in early stopping.
- Digit-based splits are deterministic: the same member always lands in the same bucket across all experiment rounds, ensuring fair comparisons.
- Parquet cache eliminates BQ load time on rounds 2+; first round will be ~20-30s slower.

## Known bad

- Do not combine two imbalance corrections simultaneously (e.g., auto_class_weights + SMOTE).
- `embedding_only` as a primary experiment target is low-value — embeddings need tabular anchors to be interpretable for model debugging.
- Changing both the feature_set and model HPs in the same round makes attribution impossible.

## Known ceilings

- No baseline yet. Update this section after round 1 (tabular_only) and round 2 (hybrid).
- Prior campaigns (notebook `commercial_ip_formal_training_downstream_eval.ipynb`) used the production RAP embeddings, not new TE. Results are not directly comparable.

## Open questions (for this campaign)

- What is the lift@1% of the tabular-only CatBoost baseline with 10:1 downsampling?
- Does the hybrid feature set improve lift@1% over tabular-only, and by how much?
- What fraction of top-10 SHAP features are embeddings vs. tabular in the hybrid model?
- Does the embedding addition help more in the OOT period (2025-07 to 2025-09) than in-time?
