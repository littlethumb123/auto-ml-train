---
schema_version: 1
campaign_id: "smoke-test-creditcard"
---

<!-- Reviewer appends one entry per round. -->
<!-- Format: ## Round N — YYYY-MM-DD -->

## Round 1 — 2026-04-26

**Action:** A_imbalance — set scale_pos_weight to computed class ratio (~578) to correct baseline structural flaw
**Trigger:** Round 1 — no prior experiments; baseline had scale_pos_weight=1 despite 578:1 imbalance
**Alternatives rejected:**
- A_model (XGBoost): lower expected ROI than fixing known misconfiguration first
- A_feature (log1p(Amount), interactions): feature engineering premature before correcting model calibration

**Independent assessment:** The run completed cleanly (9.9s, well within timeout), val_pr_auc=0.815530 is a strong result for 0.17% fraud rate, and all mandatory tools passed — this is a valid first experiment establishing the champion baseline.

**Expected Δ (val_pr_auc):** +0.020 (plan expected 0.822 → 0.842; no prior in results.tsv to verify)
**Actual val_pr_auc:** 0.815530 (Δ = N/A vs prior best — round 1 establishes champion)
**Verdict:** keep
**Key finding:** The scale_pos_weight correction produced a valid, strong result (PR-AUC=0.815530) but did not achieve the plan's expected +0.020 gain over the cited 0.822 baseline. If the 0.822 baseline is accurate, the correction may have slightly reduced PR-AUC — consistent with the Strategy Guide's note that PR-AUC is naturally imbalance-aware and A_imbalance typically gives 0.000–0.010 when PR-AUC is the metric. Bootstrap SE=0.0378 makes the difference statistically ambiguous. The 0.815530 result is now the official round-1 champion.

## Round 2 — 2026-04-27

**Action:** A_model — XGBoost (n_est=200, lr=0.05, max_depth=6, spw=578) vs LightGBM champion
**Trigger:** Strategy Guide §1: "Fewer than 2 distinct model families in results.tsv → try ≥1 alternative family"
**Alternatives rejected:**
- A_feature (log1p(Amount)): Strategy Guide says compare families before feature engineering; family rankings may reverse after tuning
- A_hp (LightGBM tuning): Premature before confirming which family to invest in

**Independent assessment:** XGBoost ran cleanly in 4.8s. val_pr_auc=0.793611 — clearly below champion's 0.815530, Δ=-0.022. Anomaly did not fire. XGBoost PR-AUC ranking is weaker than LightGBM at these settings.

**Expected Δ (val_pr_auc):** +0.010 (plan expected XGBoost to match or exceed LGBM)
**Actual val_pr_auc:** 0.793611 (Δ = -0.021919 vs prior best 0.815530)
**Verdict:** discard
**Key finding:** Default-param XGBoost underperforms LightGBM by 0.022 on PR-AUC. However, XGBoost was tested at 200 estimators vs LGBM's 600, so this is not a fully controlled comparison. Strategy Guide trigger ("best leads by >2× noise_floor") now fires, indicating LightGBM is the preferred family — commit to it and move to HP tuning or feature engineering.

## Round 3 — 2026-04-27

**Action:** A_hp — LightGBM num_leaves 63→127 to increase model capacity
**Trigger:** Strategy Guide §1: "Champion family selected; no systematic HP search yet → A_hp is next highest-ROI layer"
**Alternatives rejected:**
- A_feature (log1p(Amount)): Strategy Guide says A_hp before A_feature when no systematic HP search done
- A_hp (lr change): changing lr and n_estimators together violates one-variable rule

**Independent assessment:** Run completed in 13.6s. val_pr_auc=0.813307 — slightly below champion 0.815530 (Δ=-0.002). Anomaly did not fire. Slight decrease suggests num_leaves=127 may introduce mild overfitting on this small fraud class.

**Expected Δ (val_pr_auc):** +0.008 (num_leaves increase expected to improve model expressiveness)
**Actual val_pr_auc:** 0.813307 (Δ = -0.002223 vs prior best 0.815530)
**Verdict:** discard
**Key finding:** Doubling num_leaves from 63 to 127 did not improve PR-AUC — slightly decreased it (Δ=-0.002, within bootstrap SE=0.038 so statistically ambiguous). The default num_leaves=63 appears well-suited or this direction is saturated. Feature engineering (A_feature) may be more productive than further HP tuning of num_leaves.
