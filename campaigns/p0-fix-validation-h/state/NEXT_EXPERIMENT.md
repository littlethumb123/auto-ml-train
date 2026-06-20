---
schema_version: 1
campaign_id: "p0-fix-validation-h"
round: 4
action_type: "A_hp"
hypothesis: "Increasing LightGBM n_estimators from 600 to 2000 (same baseline HP: lr=0.02, num_leaves=63, min_child_samples=5) will improve val_pr_auc to ~0.825-0.830 per PRIORS.md evidence (n_est=2500 → 0.830)"
expected_effect_size: 0.012
base_commit: "d20e21769bf720b89f011ba346644ea2d1d47063"
model_family: "lgbm_balanced"
n_features: 30
planner_invocation_at: "2026-06-20T00:00:00Z"
touches_helpers: false
helpers_declared: []
assumptions_tested: []
escalation: null
---

## 1. Context

Round 4 of 4 (final round). Budget 3/4 used. Best metric: val_pr_auc=0.8155 (lgbm_balanced, commit d20e217). consecutive_discards=2. Assumption-aware novelty check required (consecutive_discards ≥ 2). No ⚠ CRITICAL assumptions. Historian STRATEGY_MEMO §4: bottleneck=optimizer_quality. DEAD_ENDS.md: proxy Optuna approach dead-ended. PRIORS.md: n_est=2500 → 0.830 (+0.015 directly evidenced in prior campaign).

## 2. Evidence

**History (results.tsv top-3):**
- Round 1: lgbm_balanced n_est=600 lr=0.02 → val_pr_auc=0.8155 (keep)
- Round 2: xgb_balanced n_est=300 lr=0.05 → val_pr_auc=0.8144 (discard)
- Round 3: lgbm_balanced Optuna proxy n_est=1000 → val_pr_auc=0.8050 (discard)

**PRIORS.md key evidence:** LightGBM n_est=2500, lr=0.02 produced val_pr_auc=0.830 in smoke-test-creditcard campaign (same split, same seed=42). Δ = +0.015 from n_est=600 baseline. This is the strongest available evidence for a gainful experiment.

**DEAD_ENDS.md:** Round 3 proxy Optuna (n_est=200 proxy, n_est=1000 final) is dead-ended. The current plan avoids Optuna entirely — it's a single-variable change (n_estimators only) without proxy.

**UNEXPLORED_TECHNIQUES.md:** Amount interactions (Expected Δ +0.003-0.008), LightGBM+XGBoost ensemble (Expected Δ +0.002-0.007), direct Optuna HP search.

**Assumption-aware novelty check (consecutive_discards=2):**
- A-1-1 (scale_pos_weight, partially_verified): No experiment tests this — still holds
- A-1-2 (SE adequate, partially_verified): No new evidence. consecutive_discards=2 but assumptions are partially_verified (not ⚠ CRITICAL, which requires unverified status AND ≥2nd Historian audit)
- Decision: A_validate NOT required. Select highest expected Δ from unexplored techniques.

**UCB1 (EXPERIMENT_TREE phase: exploit — 100% of 4-round budget):** A_hp has 1 attempt (proxy Optuna, negative). UCB1 score is finite. A_ensemble has UCB1=inf (untried). However: direct n_est increase is structurally different from the proxy Optuna dead-end AND has the highest evidence-backed expected Δ from PRIORS.md.

**STRATEGY_MEMO §4:** bottleneck=optimizer_quality. Recommended: A_hp on LightGBM. Direct n_est increase is the cleanest possible A_hp (single variable, PRIORS-backed, no proxy risk).

**Pre-selection candidates:**

| Candidate | Action | UCB1 | Expected Δ | Dead-end? | Assumption risk | Selection rationale |
|-----------|--------|------|------------|-----------|-----------------|---------------------|
| 1 | A_hp (n_est=2000, direct) | finite (1 prior attempt) | +0.010–0.015 (PRIORS: n_est=2500→0.830) | No (dead-end only covers proxy approach) | None — same HP as baseline except n_est | PRIORS.md best-evidenced, single-variable change, no proxy risk |
| 2 | A_ensemble (LGBM+XGB avg) | inf | +0.002–0.007 | No | LGBM not tuned per STRATEGY_GUIDE §3.5 | Building blocks not individually tuned; weaker expected Δ |
| 3 | A_feature (Amount interactions) | inf | +0.003–0.008 | No | FE before champion tuned per STRATEGY_GUIDE | Champion still not tuned; lower expected Δ |
| **Selected** | **A_hp (n_est=2000)** | | **+0.010–0.015** | No | None | **Highest expected Δ, PRIORS.md evidence-backed, avoids proxy dead-end, single-variable. Final round — must maximize expected value.** |

### Historian context
- **Bottleneck diagnosis:** optimizer_quality
- **Critical assumptions:** none flagged ⚠ CRITICAL
- **Alignment:** Full alignment — direct n_est increase addresses optimizer_quality without proxy risk

**Template catalog check:** No templates applicable.

## 3. Plan

1. Change `n_estimators=600` to `n_estimators=2000` in the LightGBM model config.
2. Keep ALL other hyperparameters exactly as the baseline (lr=0.02, num_leaves=63, min_child_samples=5, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, scale_pos_weight=computed, n_jobs=4, verbose=-1).
3. Update `DESCRIPTION` to `"A_hp: LightGBM n_est=2000 (lr=0.02, num_leaves=63) — PRIORS.md n_est convergence"`.
4. Expected runtime: ~25s training (7.6 × 2000/600 ≈ 25s), total ~27s. Well within 60s SIGALRM.
5. Expected output: val_pr_auc ≈ 0.825-0.830 (PRIORS.md: n_est=2500 → 0.830 on same split).

## 4. Helpers

No helpers needed.

## 5. How this differs

Round 1 used n_est=600. Round 3 used n_est=1000 via Optuna proxy (structurally different — Optuna changed multiple HP simultaneously, proxy-selected different lr/num_leaves, failed). This experiment is a pure single-variable change: n_estimators 600→2000, all other HP unchanged from the known-good baseline. This directly tests the PRIORS.md claim that more estimators improve PR-AUC on this split.

## 6. Escalation

No escalation.
