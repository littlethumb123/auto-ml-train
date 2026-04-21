---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
count: 3
last_updated: "2026-04-21"
---

# Observations worth remembering (non-dead-end)

- XGBoost depth=4 and depth=6 both found independent optima in apr01 — basin is not a single point.
- Removing `time_features` improved by ~0.003 AND simplified the pipeline in apr01.
- `lift_at_10` is ~3× more stable across seeds than `val_pr_auc` on this split (reflection §7).
