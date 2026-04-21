---
schema_version: 1
campaign_id: "tiny-binary-test"
problem_title: "Tiny test binary classification"
task_type: "binary_classification"
unit_of_observation: "row"
target:
  name: "Class"
  positive_class: 1
  definition: "Synthetic positive class."
success_criteria:
  - "val_pr_auc >= 0.50"
constraints:
  - "Single-file train.py."
non_goals:
  - "No deployment."
approved_at: "2026-04-21"
approved_by: "test"
---

## 1. Task

Synthetic tiny binary classification.

## 2. Why the task matters

Test fixture.

## 3. Success criteria (detail)

Must beat 0.50.

## 4. Constraints (detail)

One file.

## 5. Non-goals (detail)

No deployment.
