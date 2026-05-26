---
schema_version: 1
campaign_id: "ip-commercial-new-te"
problem_title: "Commercial inpatient admission prediction with new TE embeddings"
task_type: "binary_classification"
unit_of_observation: "member-month (individual_id + index_dt)"
target:
  name: "ip6"
  positive_class: 1
  definition: "1 if the member has >= 6 inpatient days in the 6-month window following index_dt, 0 otherwise."
success_criteria:
  - "val_lift_1pct >= 4.5 on the best model from each feature set (tabular_only, embedding_only, hybrid)"
  - "val_auc_roc >= 0.78 on the best configuration overall"
  - "embedding_only val_lift_1pct >= tabular_only val_lift_1pct (embeddings beat tabular alone)"
constraints:
  - "No modification of the BigQuery source tables or prepare.py."
  - "Total campaign compute <= 600s per experiment (hard timeout 1200s)."
  - "Keep/discard decisions use val set only (digit 8, in-time). Test and OOT are Reviewer-reported metrics only."
  - "EXCLUDE_COLUMNS list in prepare.py is frozen; add only via C3."
  - "Feature selection (tools/feature_selection.py) must be applied to each feature set before HP tuning commits to a feature subset."
non_goals:
  - "No deployment or inference service."
  - "No Medicare IP model (separate campaign)."
  - "No fairness / subgroup analysis in this campaign."
approved_at: "2026-04-24"
approved_by: "Zhaopeng-Xing_cvsh"
---

## 1. Task

Predict whether a commercial member will have ≥ 6 inpatient days in the 6 months following the observation anchor date (`index_dt`), given tabular clinical/claims features and/or new TE (text-embedding) features. The dataset covers 2024-11-20 → 2025-09-30, with an in-time training window of 2024-11-20 → 2025-06-30 and an OOT evaluation window of 2025-07-01 → 2025-09-30.

**Primary experimental questions (in priority order):**
1. **Can embedding-only features beat tabular-only features?** — establishes whether the new TE embeddings contain standalone predictive signal.
2. **What is the best achievable performance with hybrid (tabular + embedding) features?** — the ceiling question after feature selection and HP tuning across multiple model families.
3. **Which features within each set contribute most?** — answered by `tools/feature_selection` and `tools/shap_report` on each best-performing configuration.

**Evaluation protocol:**
- **Keep/discard decisions:** validation set only (digit 8, in-time ≤ 2025-06-30).
- **Test metrics** (digit 9, in-time) and **OOT metrics** (all digits, index_dt > 2025-06-30) are computed by the Reviewer for reporting and generalization assessment — never used in keep/discard verdicts.

## 2. Why the task matters

Commercial IP prediction is a core use case for care management outreach. The current production model uses RAP embeddings. The new TE embeddings are generated from the same formal-training cohort and share the same anchor date, making them directly comparable. This campaign validates the lift contribution of the new embeddings before a production switch decision.

## 3. Success criteria (detail)

Updated after rounds 1–2 established real baselines (C3 update):
- `val_lift_1pct (tabular_only best) = 21.578` — floor.
- `val_lift_1pct (hybrid default) = 22.213` — +0.635 vs tabular floor.
- **Campaign target:** val_lift_1pct >= 24.0 on the best optimized configuration (hybrid+feature_selection+HP_tuned).
- **Embedding standalone goal:** embedding_only val_lift_1pct >= 21.578 (beats tabular floor).
- Secondary: val_auc_roc >= 0.87 on the best configuration.
- Test and OOT metrics tracked for generalization; val is the decision metric.

## 4. Constraints (detail)

- 600s soft budget per experiment (hard timeout 1200s) — updated after discovering data pipeline takes ~80-320s for 10.3M-row × 824-col dataset.
- The prejoined BigQuery modeling table is read-only; prepare.py reads from a local parquet cache at campaigns/ip-commercial-new-te/.cache/new_te.parquet.
- `prepare.py` and `shared/` are human-owned; the Executor only edits `train.py`.
- `EXCLUDE_COLUMNS` in prepare.py is frozen. Any change requires C3.
- **Test data (digit 9) and OOT data (index_dt > 2025-06-30):** Reviewer loads and evaluates separately for reporting. Never used in training or keep/discard decisions. Train.py should compute and print test/OOT metrics for the Reviewer to include in REVIEW.md.
- **Feature selection:** Must run `tools/feature_selection.py` on the best model before committing to a reduced feature set for HP tuning. Do not skip this step.

## 5. Non-goals (detail)

- No Medicare IP model in this campaign (separate problem contract).
- No production deployment or inference pipeline.
- No fairness or subgroup analysis.
- No comparison to production RAP embeddings (handled in the notebook; not the agent's scope).
