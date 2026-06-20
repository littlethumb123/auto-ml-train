---
schema_version: 1
campaign_id: "p0-fix-validation-h"
count: 1
last_updated: "2026-06-20"
---

<!-- Reviewer appends entries on discard when pattern is structurally new. -->
<!-- Format: - **Round N (action_type: short label):** description -->
- **Round 3 (A_hp: proxy Optuna mismatch):** Optuna search with n_est=200 proxy → n_est=1000 final is structurally flawed for LightGBM on this dataset. Proxy ranking does not transfer to final model. Selected num_leaves=81, min_child_samples=10 performed worse than baseline (num_leaves=63, min_child_samples=5) at n_est=1000. If retrying A_hp, use direct search (no proxy, fixed n_est=600) and tune only lr and num_leaves.
