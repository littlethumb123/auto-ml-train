---
schema_version: 1
campaign_id: "ip-commercial-new-te"
last_round: 1
last_verdict: "keep"
---

# Review log

## Round 1

commit: 8c39baa
verdict: keep
action_type: A_validate
hypothesis: Default-parameter CatBoost on tabular_only features establishes the lift@1% floor.
model_family: catboost
feature_set: tabular_only
val_lift_1pct: 21.577960
val_auc_roc: 0.853128
val_lift_5pct: 9.313658
val_lift_10pct: 6.007624
val_auc_pr: 0.102798
n_features: 534
training_seconds: 143.8
total_seconds: 300.7
anomaly_fired: false
anomaly_reason: val_lift_1pct=21.577960 within expected range (threshold=1.500000)
bootstrap_se: n/a (round 1 — log truncation issue; .npy save fix applied to train.py)
review_note: First baseline. val_lift_1pct=21.58 is the campaign floor. Any future experiment must beat this. training_seconds=143.8 confirms dataset size requires od_wait tuning in A_hp rounds.

### Tool outputs

- anomaly: not fired — val_lift_1pct=21.58 >> floor=1.5
- bootstrap_ci: not computed (round 1 — val scores truncated from run.log due to 752K-row JSON; train.py updated to write current_val_*.npy for all future rounds)

### Infrastructure notes

- Dataset: 10.3M rows × 824 cols (256 embedding_* + 568 tabular); 534 tabular features after EXCLUDE_COLUMNS.
- Parquet read (tabular_only, 566 cols): 12.0s
- Data processing + downsampling (508K train rows after 10:1): 136.4s
- CatBoost 500 iter, depth=6, od_wait=50: 143.8s training
- Total: 300.7s — within 600s hard timeout
- val prevalence: 0.77% (5,826 positives in 752,579 val rows)

### Escalation

None. Round 1 baseline established successfully.
