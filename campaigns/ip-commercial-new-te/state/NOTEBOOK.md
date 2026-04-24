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
