---
schema_version: 1
campaign_id: "<campaign_id>"
final_commit: "<sha>"
final_primary_metric: null
final_ci: [null, null]
baseline_primary_metric: null
n_experiments: null
n_keeps: null
n_discards: null
reviewed_at: null
reviewed_by: null
---

## 1. Headline

<1 paragraph: what was the best approach, by how much it beat baseline, CI overlap with baseline.>

## 2. What worked

<Enumerated list of keep commits with short rationale for each.>

## 3. What did not work (and why)

<Reference to DEAD_ENDS.md — no need to repeat; cite each dead-end and explain the root cause if known.>

## 4. Statistical caveats

<CI overlap with baseline? Paired test significance? Any anomalies encountered? Reflect on whether the single-holdout split was adequate or whether Phase 2 CV upgrade is warranted.>

## 5. Recommended priors update

<Diff for PRIORS.md — what to add/remove/modify. Format as: "Add to Known good: ...", "Add to Known bad: ...", "Update ceiling: ...">

## 6. Open questions

<What should a follow-up campaign try? List unresolved hypotheses worth carrying forward.>
