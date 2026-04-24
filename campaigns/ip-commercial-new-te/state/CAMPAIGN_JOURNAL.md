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
