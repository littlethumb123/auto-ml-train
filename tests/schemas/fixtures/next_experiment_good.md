---
schema_version: 1
campaign_id: "tiny-binary-test"
round: 1
planner_invocation_at: "2026-04-21T18:00:00Z"
action_type: "A_hp"
hypothesis: "Tighter depth range converges faster."
expected_effect_size: 0.005
base_commit: "abcdef012345"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context summary

Baseline at 0.65; Optuna explored wide range.

## 2. Evidence from memory

- results_query: top-5 shown below.
- dead_ends_query: no matches.
- NOTEBOOK observations: none relevant.

## 3. Plan

1. In `train.py`, narrow max_depth range.

## 4. Helpers

None.

## 5. How this differs from prior experiments

Prior experiments used the full range.

## 6. Escalation (only if `escalation` frontmatter is non-null)

N/A.
