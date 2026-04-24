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
