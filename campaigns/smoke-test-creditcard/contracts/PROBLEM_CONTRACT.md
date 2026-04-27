---
schema_version: 1
campaign_id: "smoke-test-creditcard"
problem_title: "Creditcard Fraud Detection — Harness Smoke Test"
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
  - "Hard timeout: 90s per experiment"
non_goals:
  - "Production deployment"
  - "Full hyperparameter search"
approved_at: "2026-04-27"
approved_by: "human"
---

## 1. Task

Binary classification: predict whether a credit card transaction is fraudulent (Class=1).

## 2. Why the task matters

Smoke test for the harness meta-cognitive tier (Historian role, Assumption Register, Pattern Book,
evidence-first Reviewer, token tracking). The goal is to validate the harness end-to-end, not to
achieve production-grade fraud detection performance.

## 3. Success criteria (detail)

`val_pr_auc >= 0.75` on the fixed val split. PR-AUC is the correct primary metric for extreme
class imbalance (~0.17% fraud rate). A random classifier scores ~0.0017; a basic LGBM baseline
scores ~0.75–0.85.

## 4. Constraints (detail)

Stratified splits are fixed by seed=42 in train.py. The Executor must not change split logic.
The 90s hard timeout is enforced via SIGALRM in train.py.

## 5. Non-goals (detail)

This campaign has 10-round budget. Deep hyperparameter optimization and ensemble stacking are
out of scope. The goal is harness validation, not SOTA fraud detection.
