---
schema_version: 1
campaign_id: "ip-commercial-new-te"
count: 1
last_updated: "2026-05-25"
---

<!-- Reviewer appends entries on every keep verdict. -->
<!-- Format: ### A-<round>-<seq> — <short name> -->

### A-1-1 — Tabular baseline is reproducible floor

- **Claim:** CatBoost with default params on tabular_only features (533 features) achieves val_lift_1pct ~21.5 ± 0.5, establishing the floor for this campaign.
- **Evidence for:** val_lift_1pct = 21.544, consistent with prior campaign round 1 (21.578). Bootstrap CI [20.60, 22.49].
- **Evidence against:** none
- **Confidence:** high
- **Load-bearing:** yes
- **Verification status:** unverified
- **Last audited:** round 1 by Reviewer
