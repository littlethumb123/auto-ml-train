---
schema_version: 1
campaign_id: "ip-commercial-new-te"
last_round: 46
last_verdict: discard
hypothesis: "Establish tabular_only CatBoost baseline lift@1%"
---

## Round 1 — 2026-05-25

### Independent Assessment
val_lift_1pct = 21.544, val_auc_roc = 0.853, test_lift_1pct = 21.910. Bootstrap CI: [20.60, 22.49], SE = 0.487. Anomaly tool: not fired. This is the first experiment — no prior to compare against. The tabular_only CatBoost baseline with default params achieves lift@1% = 21.544 on val, consistent with the prior campaign's round 1 result of 21.578. Test lift is slightly higher (21.91), suggesting no val overfitting.

### Plan Comparison
Expected: n/a (baseline). Actual: 21.544. Baseline established.

### Verdict: keep
First experiment, establishes the tabular_only floor. No mandatory tools flagged.
