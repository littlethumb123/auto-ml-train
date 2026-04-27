---
schema_version: 1
campaign_id: "smoke-test-creditcard"
count: 2
last_updated: "2026-04-27"
---

<!-- Historian appends entries during periodic/C2 runs. -->
<!-- Format: ### P-<seq> — <pattern name> -->

### P-1 — Simple perturbations of the champion consistently degrade PR-AUC

- **Pattern:** Single-parameter perturbations of the champion LightGBM configuration (model family swap, num_leaves increase, feature addition) all produce negative Δ on PR-AUC. The champion appears to be a local optimum that simple perturbations cannot escape.
- **Supporting evidence:** round 2 (XGBoost default: Δ=-0.022), round 3 (num_leaves=127: Δ=-0.002), round 4 (log1p Amount: Δ=-0.035) — all negative
- **Confidence:** low (3 rounds, C2 plateau trigger)
- **Status:** active
- **Implication for Planner:** Single-variable perturbations have failed across all tried categories (model family, HP, feature). Consider either more radical interventions (ensemble, CV upgrade) or systematic HP search within LGBM rather than single-point tests.

### P-2 — Amount-based feature engineering hurts PR-AUC

- **Pattern:** Adding log1p(Amount) as a feature alongside the original 30 features caused a large PR-AUC drop (Δ=-0.035). Amount-related feature engineering is likely counterproductive because V1-V28 PCA features already encode amount information from the original transaction data.
- **Supporting evidence:** round 4 (log1p_Amount as feature 31: val_pr_auc=0.780562 vs champion 0.815530, Δ=-0.035)
- **Confidence:** low (1 data point)
- **Status:** active
- **Implication for Planner:** Avoid Amount-based feature engineering (log1p, Amount×V interactions, Amount^2). The PCA transformation likely already captures Amount's contribution to fraud patterns. Feature engineering budget is better spent on Time-based features if any.
