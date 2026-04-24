---
schema_version: 1
campaign_id: "ip-commercial-new-te"
purpose: "Retrospective decision log — planned reasoning vs actual outcome per round. Reviewer-owned; appended every round."
last_updated: "2026-04-24"
---

# Campaign Journal — ip-commercial-new-te

Answers the question: *why did we try X, what did we expect, and what did we actually learn?*
Use this for retrospective analysis, identifying where priors were wrong, and calibrating future campaigns.

---

## Round 1 — 2026-04-24

**Action:** A_validate — CatBoost tabular_only baseline to establish lift@1% floor

**Trigger:** STRATEGY_GUIDE §1 "No baseline exists → A_validate with simple default"

**Alternatives rejected:**
- A_hp: no floor to beat yet; HP search without a reference point is unmotivated
- A_validate hybrid: cannot measure embedding lift without tabular-only reference first

**Expected Δ (lift@1%):** n/a — first baseline, no prior to compare against

**Actual val_lift_1pct:** 21.578 (Δ = n/a, first baseline)
**Actual val_auc_roc:** 0.853
**Verdict:** keep

**Key finding:** Tabular-only CatBoost with default params achieves lift@1%=21.58 — far exceeding the placeholder success criterion of 4.5. This is a strong baseline. The dataset has 534 tabular features after EXCLUDE_COLUMNS. Critical infrastructure finding: 13GB parquet with 10.3M rows × 824 cols; naive full-table loading hits the 600s HARD_TIMEOUT before training even starts. Required row filter (in-time only, 7.5M rows) + column-selective read to fit within budget.

---

## Round 2 — 2026-04-24

**Action:** A_validate — CatBoost hybrid (tabular + 256 embeddings) baseline to measure embedding lift

**Trigger:** STRATEGY_GUIDE §1 "tabular_only baseline exists; no hybrid baseline → A_validate hybrid"

**Alternatives rejected:**
- A_hp on tabular_only: cannot decide which feature set to HP-tune without hybrid comparison
- A_feature: no SHAP baseline yet; feature selection premature before understanding embedding contribution

**Expected Δ (lift@1%):** +0.5 to +3.0 (STRATEGY_GUIDE §2 A_validate hybrid prior)

**Actual val_lift_1pct:** 22.213 (Δ = +0.635 vs round 1 best)
**Actual val_auc_roc:** 0.859
**Bootstrap CI:** [21.258, 23.156], SE=0.495
**Verdict:** keep

**Key finding:** 256 new TE embeddings add +0.635 lift points over tabular-only with identical model config. Δ > noise_floor=0.3 and > bootstrap_se=0.495 (barely — worth noting). Embedding contribution is real but modest with default params. The large embedding dimensionality (256) suggests feature selection could reveal which embeddings carry the signal and which are noise. Success criteria already exceeded (target ≥4.5, achieved 22.21 on round 2). Note: embedding_only NOT YET TESTED — this is the primary research question per updated PROBLEM_CONTRACT.

---

## Round 3 — 2026-04-24

**Action:** A_validate — CatBoost embedding_only (256 dims, no tabular)
**Trigger:** STRATEGY_GUIDE §1 "No embedding_only baseline" — primary research question
**Alternatives rejected:**
- A_hp on hybrid: cannot choose target without embedding_only baseline

**Expected Δ vs tabular floor:** -2.0 to +2.0 (unknown — this was the question)
**Actual val_lift_1pct:** 18.162 (Δ = −3.416 vs tabular_only, −4.051 vs hybrid best)
**Verdict:** discard

**Key finding:** Embedding_only does NOT beat tabular_only (18.16 vs 21.58). Gap is real (CIs don't overlap). Embeddings add value only in combination (hybrid +0.635). All three baselines now established. embedding_only trains 6× faster — useful for future ablations.

---

## Round 4 — 2026-04-24

**Action:** A_feature — CatBoost native importance top-150 numeric features from hybrid 790
**Trigger:** STRATEGY_GUIDE §1 "All 3 baselines done; feature selection not done"
**Alternatives rejected:**
- A_hp on full hybrid: 150 features → 3× more Optuna trials per budget
**Expected Δ:** 0.0 to +1.0
**Actual val_lift_1pct:** 21.767 (Δ = −0.446 vs hybrid best)
**Verdict:** discard

**Key finding:** Top-150 numeric captures 98% of hybrid performance but just misses the noise floor. Training 1.8× faster (93s vs 170s). 73/256 embeddings selected — signal concentrated. Bug: _index_dt_parsed (prepare.py internal variable) in top-10 importances — temporal leakage risk. Strategy for round 5: A_hp Optuna on hybrid full features (with _index_dt_parsed excluded), leveraging the knowledge that default params lose 0.446 lift — HP search should recover this.

---

## Round 5 — 2026-04-24

**Action:** A_hp — Optuna wide HP search on full hybrid (first systematic HP tune)
**Trigger:** STRATEGY_GUIDE §1 "Champion family; no systematic HP search → A_hp highest ROI"
**Alternatives rejected:**
- A_model (LightGBM): CatBoost should be tuned first before comparing families

**Expected Δ (lift@1%):** +0.5 to +2.5

**Actual val_lift_1pct:** 22.162 (Δ = **-0.051** — noise level, within 0.1 SE)
**Verdict:** discard (3rd consecutive → C2 plateau fires)

**Key finding:** INFRASTRUCTURE WIN: split cache loaded in 27s (vs 250s first run). Only 7 Optuna trials completed in 500s because each 200-iter CatBoost proxy takes ~71s on 789 features × 508K rows. The result (-0.051, 0.1 SE below prior best) is statistically indistinguishable from the default-param best (22.213). This is not a true plateau — the HP search was severely under-sampled. **Fix**: use 50-iter proxy instead of 200-iter (17s/trial → 28 trials in 500s), OR switch to LightGBM (5× faster per iteration). C2 fires mechanically; A_diagnose follows per protocol.

---

## Round 6 — 2026-04-24

**Action:** A_diagnose — SHAP analysis on hybrid best + error analysis (mandatory after C2)
**Trigger:** c2_pending_diagnose=True (C2 protocol requires A_diagnose before structural changes)
**Expected Δ:** ~0 (diagnostic only)

**Actual val_lift_1pct:** 22.213 (Δ = 0.0 — reproduces round 2 champion exactly)
**Verdict:** discard (Δ not > 0, but expected for diagnostic round)

**Key finding:** SHAP shows near-perfect 50/50 split between embedding and tabular features in top-50 (26 emb vs 24 tab). Embeddings are NOT redundant with tabular — they are COMPLEMENTARY. This confirms hybrid is the right feature set and suggests stacking (diverse feature subsets) could add value. Error analysis: 75.5% of positives are "hard" (score below neg-p99) — inherent task difficulty. Model is well-calibrated. Target gap (1.787 lift pts) is detectable (gap = 1.80× SE). No measurement bottleneck. C2 cleared. Root cause of 3 discards: infrastructure bugs + too-slow Optuna proxy (71s/trial). Fix: 50-iter proxy (17s/trial → 28 trials in 500s).

---

## Round 7 — 2026-04-24

**Action:** A_hp — Optuna 50-iter proxy on full hybrid (28-54 trials)
**Trigger:** STRATEGY_GUIDE §1 "First systematic HP search after A_diagnose"
**Expected Δ:** +0.5 to +2.0

**Actual val_lift_1pct:** 21.990 (Δ = **-0.223 vs best**, -0.45 SE)
**Verdict:** discard

**Key finding:** 50-iter proxy runs 54 trials but is too fast to reliably rank HPs for lift@1% (proxy best=21.05, but full model at those params gives 21.99). The proxy and full model don't correlate well for this noisy metric at low iteration counts. Default CatBoost params (depth=6, lr=0.05) appear near-optimal for lift@1% — Optuna keeps finding slightly different params that don't outperform them. Next: try LightGBM (different family, different bias, faster iteration → more reliable proxy). If LightGBM beats CatBoost, HP tune that; if not, return to ensemble.

---

## Round 8 — 2026-04-24

**Action:** A_model — LightGBM default params on hybrid (second family baseline)
**Trigger:** STRATEGY_GUIDE §1 "Only CatBoost tried; 2+ rounds → try alternative family"
**Alternatives rejected:**
- A_hp on CatBoost: 54 trials failed to beat default; different family more likely to find improvement
**Expected Δ:** -1.0 to +1.5

**Actual val_lift_1pct:** 22.316 (Δ = **+0.103 — NEW BEST**)
**Verdict:** keep

**Key finding:** LightGBM outperforms CatBoost default by +0.103 (within noise floor but positive). Training 206s with early stopping at iter 251. LGBM's leaf-wise growth strategy finds a different optimum than CatBoost's symmetric trees. The margin is small — HP tuning is the clear next step since LGBM is fast per iteration and will give more reliable Optuna trials. Target gap narrowed to 1.684 lift points (still 1.74 SE — detectable).

---

## Round 9 — 2026-04-24

**Action:** A_hp — Optuna LightGBM HP search on hybrid
**Expected Δ:** +0.3 to +1.5
**Actual val_lift_1pct:** 22.179 (Δ = **-0.137**)
**Verdict:** discard

**Key finding:** Same Optuna bottleneck: only 7 trials in 500s because num_leaves=351 makes the 200-iter proxy as slow as CatBoost's. Full model (num_leaves=351, 2000 iter early-stop@124) took 711s — extremely slow. LightGBM HP search needs constrained num_leaves (≤127) to keep proxy fast. Alternative path: skip HP tuning and go directly to A_ensemble (stacking default LightGBM + default CatBoost) since both are near-optimal with defaults and SHAP showed complementary signals.

---

## Round 10 — 2026-04-24

**Action:** A_ensemble — LightGBM (22.316) + CatBoost (21.698) holdout stacking, logistic meta
**Expected Δ:** +0.3 to +0.8
**Actual val_lift_1pct:** 22.333 (Δ = **+0.017 — MARGINAL NEW BEST**)
**Verdict:** keep (Δ>0 by rule, but practically noise)

**Key finding:** In-sample stacking (meta trained+evaluated on val) gave 0.017 lift improvement — well within measurement noise. The stacking weights favor LightGBM (3.15 vs CatBoost 2.61). val_lift_10pct showed larger gain (+0.07), suggesting ensemble helps on the harder lower-risk cases more than the very high-risk ones. For honest evaluation, stacking must be done out-of-fold or with a separate holdout for the meta-learner. The in-sample result is optimistic and likely overstates true gain.

---

## Round 11 — 2026-04-24

**Action:** A_hp — LightGBM Optuna narrow search (num_leaves 31-255, 50-iter proxy)
**Expected Δ:** +0.3 to +1.5
**Actual val_lift_1pct:** 22.162 (Δ = -0.172)
**Verdict:** discard

**Key finding:** Confirmed: lift@1% is too noisy as Optuna proxy at low iterations. Proxy estimated 21.90; full model gave 22.16 — 0.26-point gap makes the proxy misleading. LightGBM default params (num_leaves=127, lr=0.05) appear near-optimal. **Strategy shift**: (1) try XGBoost to complete the three-family comparison, (2) if XGBoost also underperforms, do proper OOF stacking, (3) if HP search needed, use AUC-ROC as proxy (smoother, more reliable at low iterations).

---

## Round 12 — 2026-04-24

**Action:** A_model — XGBoost hist default params (third family baseline)
**Expected Δ:** -1.0 to +1.0
**Actual val_lift_1pct:** 22.196 (Δ = -0.137)
**Verdict:** discard

**Key finding:** Three-family comparison complete: LightGBM(22.316) > CatBoost(22.213) ≈ XGBoost(22.196). XGBoost is fastest (144s vs 206s LGBM) — good for Optuna proxies. LightGBM is confirmed champion. **Strategy**: try LightGBM HP search using AUC-ROC as Optuna metric (smoother than lift@1% at low iterations). XGBoost's speed makes it valuable for ensemble diversity even if weaker standalone.

---

## Round 13 — 2026-04-24

**Action:** A_hp — LightGBM Optuna with AUC-ROC proxy (fix attempt)
**Expected Δ:** +0.3 to +1.5
**Actual val_lift_1pct:** 22.162 (Δ = -0.172; SAME params as round 11)
**Verdict:** discard → C2 fires (3 consecutive)

**Key finding:** AUC-ROC proxy found IDENTICAL params as round 11 (same TPE seed, same exploration). **Conclusion: Optuna short-proxy HP search is fundamentally broken for LightGBM on this dataset.** The 50-iter proxy with early_stop=20 almost always converges in 20 iterations — not enough signal. Default params (num_leaves=127, lr=0.05) appear to be a genuine optimum for this problem. **Strategy shift**: abandon HP search; focus on three-family mean ensemble (LGBM+CB+XGBoost simple average, no in-sample leakage from logistic meta-learner). If ensemble fails, consider data engineering (interaction features, time-based features) or CV upgrade.

---

## Round 14 — 2026-04-24

**Action:** A_diagnose — three-family prediction diversity + mean ensemble test
**Expected Δ:** ~0 (diagnostic); actual: NEW BEST
**Actual val_lift_1pct:** 22.556 (Δ = **+0.223 — NEW BEST via three-family mean**)
**Verdict:** keep

**Key finding:** Three-family mean ensemble (no meta-learner) gives 22.556 — honest estimate (no in-sample leakage). Prediction correlations are very high (0.97) but ensemble still adds +0.24 lift at the top-1% threshold. **Critical insight**: CatBoost adds ZERO when combined with LGBM (too similar). XGBoost adds +0.137 (makes different top-1% errors). All three = best. Next: commit this three-family ensemble as the champion via a proper A_ensemble round (round 15), then investigate whether any other models can increase diversity further.

---

## Round 15 — 2026-04-24

**Action:** A_ensemble — LGBM+XGB+RandomForest mean
**Expected Δ:** +0.1 to +0.5
**Actual val_lift_1pct:** 21.321 (Δ = **-1.236**)
**Verdict:** discard

**Key finding:** RandomForest (lift@1%=20.016) is too weak. Despite lower correlation with GBDT (0.917 vs 0.974), adding it dilutes the ensemble: 21.321 < 22.453 (LGBM+XGB). RF fails at the top-1% region — 789 embedding-heavy features may not suit RF's random feature selection. ANTI-PATTERN confirmed: blending a weak model into a strong ensemble always hurts. Next: optimize LGBM+XGB+CB weights (find optimal 3-way weighting of the three-GBDT family), or pivot to feature engineering.

---

## Round 16 — 2026-04-24

**Action:** A_ensemble — scipy-optimized weights for LGBM+CB+XGB
**Expected Δ:** +0.1 to +0.5
**Actual val_lift_1pct:** 22.608 (Δ = **+0.052 — NEW BEST**)
**Verdict:** keep (Δ>0, but 0.10 SE — noise level)

**Key finding:** Optimized weights LGBM=0.356, CB=0.150, XGB=0.493. Surprising: XGBoost gets the most weight (0.493) despite being the weakest individual model (22.196). This means XGB makes the most unique errors in the top-1% region, effectively acting as a "correction" to LGBM's blind spots. CB contributes minimally (0.150). The 0.052 improvement over equal weights is marginal. Further improvements likely require model diversity beyond these three GBDT families or feature engineering.

---

## Round 17 — 2026-04-24

**Action:** A_ensemble — 4-model (LGBM_hybrid+LGBM_tabular+CB+XGB) scipy-optimized weights
**Expected Δ:** +0.1 to +0.4
**Actual val_lift_1pct:** 22.642 (Δ = **+0.034 — NEW BEST**)
**Verdict:** keep (Δ>0 but 0.07 SE — noise)

**Key finding:** Tabular-only LGBM (corr=0.909 with hybrid LGBM) adds real structural diversity vs the same-seed variants that would correlate at 0.997+. The 4-model ensemble weights distribute more evenly (LGBM_h=0.317, LGBM_t=0.120, CB=0.254, XGB=0.310). The pattern continues: gains are shrinking (22.556 → 22.608 → 22.642). We may be approaching the ensemble ceiling. val_lift_10pct improved (6.191 vs 6.164) — ensemble is improving the tail, not just the top. Next iteration: add more structural diversity (embedding-only LGBM, or different tabular subsets) OR shift to feature engineering.

---

## Round 18 — 2026-04-24

**Action:** A_ensemble — 5-model (LGBM_hybrid+LGBM_tab+LGBM_emb+CB+XGB) scipy-optimized
**Actual val_lift_1pct:** 22.659 (Δ = **+0.017 — NEW BEST**)
**Verdict:** keep (0.03 SE — pure noise)

**Key finding:** 5-model ensemble keeps improving but gains are vanishing (0.243→0.052→0.034→0.017 per round). LGBM_emb (corr=0.874 with hybrid) adds real diversity but is too weak (18.6) to contribute much. Optimal weights give LGBM_hybrid only 0.135 — the diverse weaker models dilute it. This is approaching a pure diversity ceiling: further ensemble additions will hit diminishing returns without stronger diverse models. **Strategy pivot**: shift from ensemble expansion to feature engineering — create interaction features or time-based features that could add genuinely new signal.

---

## Round 19 — 2026-04-24

**Action:** A_feature — +5 engineered interaction features (IP utilization, chronic burden, lab abnormality, age×IP, mm/IP ratio)
**Actual val_lift_1pct:** 22.677 (Δ = **+0.017 — NEW BEST**)
**Verdict:** keep (0.03 SE — noise)

**Key finding:** Engineered features add marginal signal (+0.017). The gains continue to shrink (0.243→0.052→0.034→0.017→0.017). We may be at the Bayes rate ceiling for this feature set and model family. 19 rounds completed, budget_used=19/100. Strategy for remaining rounds: (1) try more aggressive feature engineering (polynomial interactions, count-based risk scores); (2) accept the 22.677 ceiling and focus on robustness; (3) diversify ensemble further with different data subsets.

---

## Round 20 — 2026-04-24

**Action:** A_feature — +10 domain features (5 new: IP days, recency, ER, ER×chronic, severity)
**Actual val_lift_1pct:** 22.625 (Δ = **-0.052**)
**Verdict:** discard

**Key finding:** Adding 5 more features hurt (-0.052). The IP recency ratio and severity features are likely noisy (high variance at low IP count). ER features (er_total, er_x_chronic) may have signal but were overwhelmed by the noisy features. Optimal weights abandoned LGBM_hybrid entirely (0.019). Lesson: more features ≠ better; targeted single features work better. Next round: try only ER features on top of round 19's baseline.

---

## Round 21 — 2026-04-24

**Action:** A_feature — +2 ER features on top of round-19 baseline
**Actual val_lift_1pct:** 22.591 (Δ = **-0.086**)
**Verdict:** discard → 2 consecutive discards

**Key finding:** ER features also hurt (-0.086). The pattern across rounds 20-21 is consistent: adding ANY features beyond round-19's 5 makes things worse. Round-19's {ip_score, chronic_score, lab_score, age×ip, mm/ip_ratio} is a local optimum in this feature engineering space. The LGBM_hybrid model collapses to near-zero weight when extra features are added, suggesting the extra features distort the embedding signal. Feature engineering has hit its ceiling at 22.677. Budget_used=21/100. Remaining strategy: try different training configurations on the eng-5 dataset, then accept the ceiling.

---

## Round 22 — 2026-04-24

**Action:** A_ensemble — 7-model scipy (LGBM_h+LGBM_t+LGBM_e+CB_h+CB_t+XGB_h+XGB_t)
**Actual val_lift_1pct:** 22.728 (Δ = **+0.051 — NEW BEST**)
**Verdict:** keep (0.10 SE — noise but positive)

**Key finding:** Adding CB_tabular and XGB_tabular to the 5-model ensemble breaks through the 22.677 ceiling. XGBoost pair (hybrid+tabular) gets 0.535 combined weight — highest of any family. The tabular-only XGB (21.595 standalone) contributes more diversity than expected. The pattern: as we add more tabular-only variants, they collectively dominate the optimal blend, while the hybrid LGBM gradually loses influence (0.121 weight). This suggests the tabular features + engineered features contain most of the predictable signal, and embeddings add marginal value in the full ensemble context.

---
