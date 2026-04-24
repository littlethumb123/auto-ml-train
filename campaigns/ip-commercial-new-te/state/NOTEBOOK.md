---
schema_version: 1
campaign_id: "ip-commercial-new-te"
count: 0
last_updated: "2026-04-24"
---

# Observations worth remembering (non-dead-end)

(None recorded yet. Reviewer appends surprising-but-not-dead-end observations here.)

- embedding_only baseline: lift@1%=18.162 — does NOT beat tabular_only (21.578). Embeddings only add value combined with tabular (+0.635 in hybrid). Round 3.
- embedding_only trains 6× faster than tabular_only (24s vs 143s) — useful for rapid ablations.

- Round 4: top-150 feature selection (73 emb, 77 tab) gives lift@1%=21.767 vs full hybrid 22.213. Training 1.8× faster. _index_dt_parsed appeared in top-10 — temporal leakage risk, exclude in future rounds.
