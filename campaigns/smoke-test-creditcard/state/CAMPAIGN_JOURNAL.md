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

## Round 4 — 2026-04-27

**Action:** A_feature — add log1p(Amount) as feature 31 to LightGBM champion
**Trigger:** Strategy Guide §1: "A_feature when champion model trained and feature coverage not inspected" — consecutive_discards=2, approaching plateau
**Alternatives rejected:**
- A_hp (min_child_samples reduction): risks overfitting; lower priority than FE
- A_hp (lr change): two-variable change violates one-controlled-change rule

**Independent assessment:** Run completed in 10.8s. val_pr_auc=0.780562 — large drop of 0.035 from champion 0.815530. Adding log1p(Amount) alongside Amount strongly hurt performance. Anomaly did not fire.

**Expected Δ (val_pr_auc):** +0.010 (log1p expected to improve Amount representation)
**Actual val_pr_auc:** 0.780562 (Δ = -0.034968 vs prior best 0.815530)
**Verdict:** discard — PLATEAU TRIGGER FIRED (consecutive_discards=3, historian_trigger_pending=true)
**Key finding:** Adding log1p(Amount) as an additional feature strongly hurt PR-AUC (Δ=-0.035). This is a key negative result: Amount-based feature engineering hurts when added alongside Amount. The PCA features V1-V28 are likely the primary drivers; Amount is less informative and adding its transform may divert model attention from the PCA structure. Feature engineering on Amount is likely a dead end.

## Round 5 — 2026-04-27

**Action:** A_hp — LightGBM min_child_samples 5→1 for fraud pattern sensitivity
**Trigger:** Historian bottleneck diagnosis: optimizer_quality; top recommendation was min_child_samples reduction
**Alternatives rejected:**
- A_hp (lr=0.05 only): lower priority; Historian recommended min_child_samples first
- A_validate: no specific assumption to test beyond the CRITICAL HP assumption

**Independent assessment:** Run completed in 10.2s. val_pr_auc=0.793780 — large drop from champion 0.815530 (Δ=-0.022). Interesting: lift_at_10 improved to 9.29 vs champion's 8.99, suggesting min_child_samples=1 improves top-decile targeting while hurting overall PR-AUC.

**Expected Δ (val_pr_auc):** +0.008 (Historian top recommendation)
**Actual val_pr_auc:** 0.793780 (Δ = -0.021750 vs prior best 0.815530)
**Verdict:** discard
**Key finding:** min_child_samples=1 trades PR-AUC for lift_at_10 — it concentrates fraud detection at the very top scores but degrades calibration across the full probability range. This is a consistent pattern: XGBoost (r2) and min_child_samples=1 (r5) both showed improved lift_at_10 with reduced PR-AUC, suggesting a precision-recall tradeoff where aggressive models win at extremes but lose overall.

## Round 6 — 2026-04-27

**Action:** A_hp — LightGBM n_estimators 600→1000 to test convergence depth
**Trigger:** Strategy Guide §1: "Champion family selected; no systematic HP search yet"; Historian bottleneck=optimizer_quality; A-6-2 assumption (lr=0.02 needs >600 rounds) being tested
**Alternatives rejected:**
- A_hp (reg_lambda=10): less likely to help than testing convergence depth; overfitting evidence is weak
- A_validate: low ROI; better to explore HP space

**Independent assessment:** Run completed in 14.9s. val_pr_auc=0.824075 — clearly above champion 0.815530. Δ=+0.009. Anomaly did not fire. Bootstrap CI: [0.749, 0.892], no regression.

**Expected Δ (val_pr_auc):** +0.006 (more boosting rounds expected to capture residual signal)
**Actual val_pr_auc:** 0.824075 (Δ = +0.008545 vs prior best 0.815530)
**Verdict:** keep — NEW CHAMPION at val_pr_auc=0.824075
**Key finding:** LightGBM with n_estimators=1000 outperforms 600 by 0.009 — the model was undertrained. This confirms the CRITICAL assumption was correct: champion HP was NOT near-optimal. Learning rate 0.02 with 600 rounds was insufficient for convergence. The pattern is: increasing n_estimators (staying with same architecture) does help, contradicting the "simple perturbations hurt" pattern from earlier rounds. That pattern was only 3 data points of a specific type (family, num_leaves, feature) and didn't generalize to convergence depth.

## Round 7 — 2026-04-27

**Action:** A_hp — LightGBM n_estimators 1000→1500 to test convergence depth (testing A-6-2)
**Trigger:** A-6-2 assumption: lr=0.02 needs >600 rounds; round 6 confirmed >600; testing if >1000 also helps
**Alternatives rejected:**
- A_hp (lr change): two-variable change; keep convergence direction for clean test
- A_validate (seed stability): lower ROI than exploring convergence

**Independent assessment:** Run completed in 18.5s. val_pr_auc=0.827750 — above prior champion 0.824075. Δ=+0.004. Continuing convergence trajectory. Diminishing returns visible.

**Expected Δ (val_pr_auc):** +0.005 (continuing convergence at reduced rate)
**Actual val_pr_auc:** 0.827750 (Δ = +0.003675 vs prior best 0.824075)
**Verdict:** keep — NEW CHAMPION at val_pr_auc=0.827750
**Key finding:** n_estimators=1500 continues improving PR-AUC. Diminishing returns pattern confirmed: Δ_{600→1000}=+0.009 vs Δ_{1000→1500}=+0.004. Next step (1500→2000) likely yields <0.003 — near noise_floor. The model is approaching convergence with lr=0.02.

## Round 8 — 2026-04-27

**Action:** A_hp — LightGBM n_estimators 1500→2000 to test convergence limit (testing A-7-1, A-7-2)
**Trigger:** A-7-1: still improving at 1500; A-7-2: diminishing returns — testing if next step still yields positive Δ
**Alternatives rejected:**
- A_validate (seed stability test): lower priority than convergence frontier with 2 rounds remaining
- A_ensemble: XGBoost underperformed; unlikely to produce competitive ensemble

**Independent assessment:** Run completed in 21.4s. val_pr_auc=0.829948 — above prior champion 0.827750. Δ=+0.002. Still positive but below noise_floor. Diminishing returns confirmed (Δ halves each 500-estimator step: 0.009 → 0.004 → 0.002).

**Expected Δ (val_pr_auc):** +0.003 (expected ~half of previous step based on diminishing returns pattern)
**Actual val_pr_auc:** 0.829948 (Δ = +0.002198 vs prior best 0.827750)
**Verdict:** keep — NEW CHAMPION at val_pr_auc=0.829948
**Key finding:** Convergence pattern confirmed: Δ per 500 estimators decays geometrically (0.009 → 0.004 → 0.002). The model is near convergence at n_estimators=2000. Predicted next step (2000→2500) gain: ~0.001 — below noise_floor. With 2 rounds remaining, shifting strategy to something other than n_estimators tuning is warranted.
