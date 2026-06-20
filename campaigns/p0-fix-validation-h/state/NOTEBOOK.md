---
schema_version: 1
campaign_id: "p0-fix-validation-h"
count: 1
last_updated: "2026-06-20"
---

<!-- Reviewer appends surprising-but-not-dead-end observations. -->
<!-- Format: - **Round N (YYYY-MM-DD):** description -->
- **Round 2 (2026-06-20):** XGBoost lift_at_10=9.293 > LightGBM 8.990 despite lower PR-AUC (0.8144 vs 0.8155). XGBoost ranks top-decile fraud cases higher even with slightly worse overall calibration. This complementarity (different strengths across metrics) may make an ensemble of LightGBM+XGBoost worth evaluating in round 4.
