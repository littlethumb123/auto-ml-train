---
schema_version: 1
campaign_id: "p0-fix-smoke"
problem_title: "P0 Harness Fixes Smoke Test — Creditcard Fraud"
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
approved_at: "2026-06-19"
approved_by: "human"
---

## 1. Task

Binary classification: predict fraud (Class=1) on credit card transactions.

## 2. Why the task matters

End-to-end smoke test for the post-F1–F5 audit harness. The goal is to verify
that all audit-fixed gates fire correctly across a 3-round campaign:
F4 (skeletons), F5 (tree rebuild), F3 (tool receipts), F1 (Historian assertion),
F2 (Reviewer artifact assertion).

## 3. Success criteria (detail)

`val_pr_auc >= 0.75`. With LightGBM defaults this is trivially achievable;
the smoke campaign is forced to produce at least one discard via the
inflated `min_improvement` in EVAL_PROTOCOL so the F2 discard path runs.

## 4. Constraints (detail)

Stratified splits fixed by seed=42; 60s timeout via SIGALRM.

## 5. Non-goals (detail)

3-round budget; harness validation only.
