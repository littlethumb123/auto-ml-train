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
  - "val_lift_1pct >= 4.5"
  - "val_auc_roc >= 0.78"
constraints:
  - "No modification of the BigQuery source tables or prepare.py."
  - "Total campaign compute <= 90s per experiment (hard timeout 150s)."
  - "Do not use OOT data for training or validation decisions."
  - "EXCLUDE_COLUMNS list in prepare.py is frozen; add only via C3."
non_goals:
  - "No deployment or inference service."
  - "No Medicare IP model (separate campaign)."
  - "No fairness / subgroup analysis in this campaign."
approved_at: "2026-04-24"
approved_by: "Zhaopeng-Xing_cvsh"
---

## 1. Task

Predict whether a commercial member will have ≥ 6 inpatient days in the 6 months following the observation anchor date (`index_dt`), given tabular clinical/claims features and optionally new TE (text-embedding) features. The dataset covers 2024-11-20 → 2025-09-30, with an in-time training window of 2024-11-20 → 2025-06-30 and an OOT evaluation window of 2025-07-01 → 2025-09-30.

The primary experimental question is: **does adding new TE embedding features (hybrid feature set) improve lift at 1% over the production tabular-only baseline?**

## 2. Why the task matters

Commercial IP prediction is a core use case for care management outreach. The current production model uses RAP embeddings. The new TE embeddings are generated from the same formal-training cohort and share the same anchor date, making them directly comparable. This campaign validates the lift contribution of the new embeddings before a production switch decision.

## 3. Success criteria (detail)

- Primary: `val_lift_1pct >= 4.5` on the fixed digit-8 validation split.
- Secondary: `val_auc_roc >= 0.78` on the same validation split.
- Both are placeholders. After round 1 (A_validate, tabular_only baseline), update via C3 with the real observed values and a target delta.

## 4. Constraints (detail)

- 90s per experiment (hard timeout 150s) to accommodate BQ parquet cache reads and model training.
- The prejoined BigQuery modeling table is read-only; prepare.py reads from a local parquet cache.
- `prepare.py` and `shared/` are human-owned; the Executor only edits `train.py`.
- `EXCLUDE_COLUMNS` in prepare.py matches the notebook's list verbatim. Any change requires C3.
- OOT data (index_dt > 2025-06-30) is available in prepare.py for Reviewer reporting only — never used in training or keep/discard decisions.

## 5. Non-goals (detail)

- No Medicare IP model in this campaign (separate problem contract).
- No production deployment or inference pipeline.
- No fairness or subgroup analysis.
- No comparison to production RAP embeddings (handled in the notebook; not the agent's scope).
