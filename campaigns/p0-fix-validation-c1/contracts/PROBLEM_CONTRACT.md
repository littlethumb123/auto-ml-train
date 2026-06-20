---
schema_version: 1
campaign_id: "p0-fix-validation-c1"
problem_title: "P0 Fixes C1 Anomaly Path Validation — Creditcard Fraud"
task_type: "binary_classification"
unit_of_observation: "transaction"
target:
  name: "Class"
  positive_class: 1
  definition: "1 = fraudulent transaction, 0 = legitimate"
success_criteria:
  - "val_pr_auc >= 0.75"
constraints:
  - "No leakage: do not use Class or any derived fraud label as a feature"
  - "Fixed splits: stratified 60/20/20, seed=42 — do not re-split"
  - "Hard timeout: 60s per experiment"
non_goals:
  - "Production deployment"
  - "Full hyperparameter search"
approved_at: "2026-06-20"
approved_by: "human"
---

## 1. Task

Binary classification: predict fraud (Class=1).

## 2. Why the task matters

Single-round validation of the C1 anomaly path: planted train.py
deliberately leaks the label so val_pr_auc≈1.0. Reviewer should run
runner.tools.anomaly, see fired=true, issue verdict=anomaly, and
review_finalize should return pause_loop=true. Orchestrator must STOP.

## 3. Success criteria (detail)

`val_pr_auc >= 0.75`.

## 4. Constraints (detail)

Stratified splits fixed by seed=42; 60s timeout via SIGALRM. The planted
train.py simulates leakage as a TEST FIXTURE — that is the test, not a
contract violation.

## 5. Non-goals (detail)

1-round campaign for the anomaly path test only.
