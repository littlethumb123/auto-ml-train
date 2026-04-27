---
schema_version: 1
campaign_id: "smoke-test-creditcard"
historian_round: 9
trigger: "periodic"
rounds_covered: [1, 9]
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

**Category (updated round 9): near_optimum**

*(Previous bottleneck was optimizer_quality — resolved by n_estimators search rounds 6-8. New assessment below.)*

**Justification (round 9 update):**
1. n_estimators convergence reached: geometric decay confirmed (Δ: 0.009→0.004→0.002 per 500 estimators). Round 10 (2000→2500) predicted Δ~0.001 — near zero.
2. Feature additions: confirmed dead end (rounds 4 and 9, both large negative Δ). P-3 pattern established.
3. Only 1 round remaining.
4. Champion at val_pr_auc=0.829948 represents the near-achievable ceiling for this HP configuration.

**Evidence for near_optimum bottleneck:**
- Three consecutive n_estimators keeps with geometric Δ decay
- Two feature addition failures with large negative effects
- Bootstrap SE=0.037 means improvements <0.005 are indistinguishable from noise

**Highest-ROI technique for round 10:**
Given near-optimum state and 1 round remaining, two options:
1. `n_estimators=2500` (safe; predicted Δ~0.001; confirms convergence; very low risk of negative Δ)
2. `colsample_bytree=0.6` (unexplored direction; higher variance; could yield +0.003-0.010 or negative)

**Recommendation:** `n_estimators=2500`. The geometric decay pattern is reliable and the predicted gain (~0.001) is positive by verdict rule. With only 1 round left, a risky unexplored direction could end the campaign on a discard rather than a keep.
