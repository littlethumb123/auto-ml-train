---
schema_version: 1
campaign_id: "smoke-test-creditcard"
historian_round: 4
trigger: "c2"
rounds_covered: [1, 4]
---

## 1. Trajectory Narrative

**Phase:** Early exploitation — the campaign established a strong LightGBM baseline in round 1 (val_pr_auc=0.815530), then spent rounds 2–4 unsuccessfully exploring alternative approaches. This is a C2 plateau: 3 consecutive discards with no improvement.

**Δ-per-round trend:** Round 1 (keep, +baseline), Round 2 (discard, Δ=-0.022), Round 3 (discard, Δ=-0.002), Round 4 (discard, Δ=-0.035). All post-champion rounds went negative. Net Δ across rounds 2-4 = -0.059. The champion (round 1) remains at val_pr_auc=0.815530.

**Phase transition:** The campaign is in a plateau. The exploration attempts (XGBoost, num_leaves tuning, feature engineering) all failed to improve on the round-1 baseline. The plateau signal is clear: the simple LightGBM with 30 features and default HP is a local optimum that none of these interventions could escape.

**Last keep:** Round 1. Rounds since last keep = 3 (the plateau trigger threshold).

## 2. Pattern Extraction

**Pattern P-1: Perturbations of the champion configuration consistently degrade PR-AUC.**
- Round 2: Model family change (XGBoost) → Δ=-0.022
- Round 3: num_leaves increase (63→127) → Δ=-0.002
- Round 4: Feature addition (log1p Amount) → Δ=-0.035
- All three perturbation types (model family, HP, feature) produced negative Δ.
- Confidence: low (3 rounds, very early campaign)
- Supporting evidence: rounds 2, 3, 4
- Implication: The champion configuration is unusually robust/stable. Simple perturbations don't help. May need more radical interventions OR the champion is near a global optimum for this approach.

**Pattern P-2: Amount-based feature engineering strongly hurts performance.**
- Round 4: log1p(Amount) caused Δ=-0.035 (largest drop in campaign)
- This is surprising given the UNEXPLORED_TECHNIQUES expected Δ=0.01-0.03
- The large negative suggests Amount information is already captured by V1-V28 PCA features (which were computed from raw transaction data including Amount), OR the additional feature column disrupts tree split allocation
- Confidence: low (1 data point)
- Implication: Amount-based feature engineering is likely a dead end. Avoid log1p(Amount), Amount×V interactions. The PCA features may already encode Amount information.

**Patterns requiring ≥3 rounds for extraction:** Both patterns above have support from only 2-3 rounds. They are low-confidence but actionable.

## 3. Assumption Audit

**A-1-1 — scale_pos_weight has minimal effect on PR-AUC:**
- Status: unverified
- Round evidence: No direct test in rounds 2-4.
- Assessment: Remains low-confidence. Not re-tested.
- Last audited: round 1 by Reviewer
- **Action:** DOES NOT NEED immediate testing — dead-end already recorded.

**A-1-2 — LightGBM is a viable model family:**
- Status: verified
- Round 2 evidence: XGBoost default underperformed LGBM by 0.022. LGBM remains the superior family at these configurations.
- Assessment: CONFIRMED. High confidence.
- Last audited: round 2 by Reviewer

**A-1-3 — val split adequate for PR-AUC estimation but wide CI:**
- Status: verified
- Assessment: Bootstrap SE ≈ 0.038 across rounds. Wide CI confirmed. Small improvements (|Δ|<0.010) are statistically ambiguous.
- Last audited: round 1 by Reviewer

⚠ CRITICAL — **Unverified assumption: LightGBM champion HP (num_leaves=63, lr=0.02, n_est=600) is near-optimal for this dataset.**
- This is implicit in the results but has NOT been formally tested.
- Round 3 (num_leaves=127) failed but this only tests upward direction. num_leaves=31 has not been tested.
- learning_rate has not been systematically tested. Current lr=0.02 may be too slow.
- n_estimators=600 has not been varied (may be under- or over-trained)
- This is ⚠ CRITICAL because all "alternative approaches" failed while the champion HP has never been validated against alternatives within the LGBM family.
- **Recommendation:** Run A_validate with A-hp to test min_child_samples=1 (fewer samples per leaf → more fraud-pattern-sensitive splits) or learning_rate=0.05 with n_estimators=300 (faster convergence).

## 4. Bottleneck Diagnosis

**Category: optimizer_quality**

**Justification:**
1. The campaign champion (round 1) was established with a single default-HP LightGBM run. No systematic HP search has been done.
2. Rounds 2-4 all tried single-point perturbations rather than systematic search. num_leaves=127 failed but num_leaves=31 was not tried. Learning rate was never varied.
3. The Strategy Guide §1 condition "Champion family selected; no systematic HP search yet → A_hp is next highest-ROI layer" still applies — we have NOT done systematic HP search. Round 3 was a single num_leaves test, not a search.
4. The wide bootstrap CI (SE=0.038) means we cannot detect small improvements reliably, but the champion may still have room at different HP settings that haven't been explored.

**Evidence for optimizer_quality bottleneck:**
- Evidence 1: No learning_rate or n_estimators variation tested — these are the most impactful LGBM HPs
- Evidence 2: Round 3 (num_leaves=127) failed but this is a single-point test, not a search; the HP space is underexplored

**Highest-ROI technique class from UNEXPLORED_TECHNIQUES.md given this diagnosis:**
- "Regularization tuning: min_child_samples, lambda, alpha for LGBM" — Expected Δ: 0.005-0.01
- Specifically: **min_child_samples=1** (from 5) would allow splits on very small fraud groups, potentially capturing patterns that 5-sample minimum obscures. The fraud class has only ~295 training samples — min_child_samples=5 may be too high for effective modeling.
- This is the highest-ROI unexplored direction given the optimizer_quality bottleneck.
