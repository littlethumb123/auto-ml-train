---
schema_version: 1
campaign_id: "p0-fix-validation-h"
last_updated: "2026-06-20"
---

## Unexplored Technique Classes

<!-- Planner reads this every round (mandatory when consecutive_discards >= 2). -->
<!-- Format: -->
<!-- - **<class name>:** <description>. Status: Unexplored. Expected Δ: <range>. -->

- **Optuna HP search (LightGBM):** Systematic Bayesian HP search over n_estimators (300–2500), learning_rate (0.01–0.10), num_leaves (31–127), min_child_samples (3–20). PRIORS.md shows n_est=2500 → 0.830 (+0.015 from baseline). Status: Unexplored. Expected Δ: +0.010–0.015.
- **Amount log-transform + interactions:** log1p(Amount), Amount/median(Amount), Amount×V-feature interaction terms. Raw Amount has heavy right-tail that tree splits may not handle efficiently. Status: Unexplored. Expected Δ: +0.003–0.008.
- **LightGBM+XGBoost averaging ensemble:** Simple probability averaging of LightGBM and XGBoost predictions. Round 2 shows complementary metric profiles (XGBoost better lift_at_10, LightGBM better PR-AUC). Status: Unexplored. Expected Δ: +0.002–0.007.
- **Cross-validation scheme upgrade (5-fold stratified CV):** Replace single 20% holdout with 5-fold stratified cross-validation to reduce bootstrap SE from ~0.038 to ~0.017 (factor of √5). Enables reliable detection of HP improvements Δ > 0.034 currently masked by single-holdout noise. Required if continuing A_hp (lr, num_leaves, direct Optuna) experiments where expected Δ < 0.020. Status: Unexplored. Expected Δ: indirect — unlocks experiments currently undetectable on single holdout.
- **Direct LightGBM lr/num_leaves search (no proxy, fixed n_est):** Grid or Optuna search over learning_rate (0.01–0.05) and num_leaves (31–63) holding n_est=2000 constant. Avoids proxy-mismatch dead-end (P-2). n_est ceiling established at 2000 by R4. Expected Δ: +0.003–0.008 (speculative; detectable only with CV scheme). Status: Unexplored.
