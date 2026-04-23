---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
problem_title: "Credit-card fraud detection"
task_type: "binary_classification"
unit_of_observation: "transaction"
target:
  name: "Class"
  positive_class: 1
  definition: "1 if labeled fraud by issuer, 0 otherwise."
success_criteria:
  - "val_pr_auc >= 0.85 on held-out validation"
  - "lift_at_10 >= 8.0"
constraints:
  - "No third-party data integration."
  - "Total campaign compute <= 60s per experiment."
  - "Do not modify prepare.py or data/."
non_goals:
  - "No deployment / inference service."
  - "No fairness / subgroup analysis in this campaign."
approved_at: "2026-04-22"
approved_by: "copilot"
---

## 1. Task

Predict whether a credit-card transaction is fraudulent given a PCA-transformed feature set. The dataset is extremely imbalanced (~0.17% positive rate).

## 2. Why the task matters

This dataset is the canonical benchmark used in `auto_train` campaigns; establishing a reproducible runner MVP on it validates the greenfield architecture against historical results (mar30, apr01, apr03).

## 3. Success criteria (detail)

- Primary: val_pr_auc >= 0.85 on the fixed validation split defined by prepare.py.
- Secondary: lift_at_10 >= 8.0 at the 10% flagging threshold.

## 4. Constraints (detail)

- 60s per experiment (hard timeout 90s).
- Libraries fixed to requirements.txt; no new installs.
- prepare.py and data/ are read-only (workspace rule).

## 5. Non-goals (detail)

- Production service, deployment, or calibration for a specific business threshold.
- Fairness / subgroup analyses (future campaign).
- Novel model architecture research.
