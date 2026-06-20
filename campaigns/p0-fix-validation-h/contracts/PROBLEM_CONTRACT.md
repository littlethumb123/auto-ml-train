---
schema_version: 1
campaign_id: "p0-fix-validation-h"
problem_title: "P0 Fixes F1 Natural-Trigger Validation — Creditcard Fraud"
task_type: "binary_classification"
unit_of_observation: "transaction"
target:
  name: "Class"
  positive_class: 1
  definition: "1 = fraudulent transaction, 0 = legitimate"
success_criteria:
  - "val_pr_auc >= 0.75"
constraints:
  - "No leakage: do not use Class as a feature"
  - "Fixed splits: stratified 60/20/20, seed=42"
  - "Hard timeout: 60s per experiment"
non_goals:
  - "Production deployment"
approved_at: "2026-06-20"
approved_by: "human"
---

## 1. Task

Binary classification: predict fraud (Class=1).

## 2. Why the task matters

4-round validation campaign focused on the F1 Historian natural-trigger
chain. historian_interval=2 means Historian fires after round 2 and again
after round 4. The autonomous orchestrator must read historian.md, write
STRATEGY_MEMO.md with all four mandatory sections, and pass the F1 gate.

## 3. Success criteria (detail)

`val_pr_auc >= 0.75`. PRIORS.md provides the proven config — LightGBM
n_est=600, lr=0.02, scale_pos_weight=computed → val_pr_auc≈0.815.
The Planner is strongly suggested to start there.

## 4. Constraints (detail)

Stratified splits fixed by seed=42; 60s timeout via SIGALRM.

## 5. Non-goals (detail)

4-round budget; harness validation only.
