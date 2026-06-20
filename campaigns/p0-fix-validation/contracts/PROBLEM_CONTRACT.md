---
schema_version: 1
campaign_id: "p0-fix-validation"
problem_title: "P0 Fixes Autonomous-Orchestrator Validation — Creditcard Fraud"
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

Binary classification: predict fraud (Class=1) on credit card transactions.

## 2. Why the task matters

Validation campaign for the autonomous orchestrator-md flow under the
post-F1–F5 harness. Goals: confirm a headless Claude session reads role docs,
uses the tool-run wrapper, writes Reviewer artifacts, and that the F1
Historian gate fires naturally at round 4 (historian_interval=4).

## 3. Success criteria (detail)

`val_pr_auc >= 0.75`. With LightGBM defaults this is trivially achievable;
the validation campaign aims to exercise full role flow, not benchmark.

## 4. Constraints (detail)

Stratified splits fixed by seed=42; 60s timeout via SIGALRM.

## 5. Non-goals (detail)

5-round budget. No HP search beyond what the Planner naturally explores;
harness validation only.
