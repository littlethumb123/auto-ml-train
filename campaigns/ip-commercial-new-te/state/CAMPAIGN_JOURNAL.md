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
