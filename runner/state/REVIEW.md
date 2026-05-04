---
schema_version: 1
campaign_id: "apr21-creditcard-fraud"
last_round: 10
last_verdict: "discard"
---

# Review log

## Round 1

commit: beb95a9
verdict: keep
action_type: A_validate
hypothesis: Emit validation score telemetry so the reviewer can run bootstrap CI on every round.
model_family: lightgbm
val_pr_auc: 0.828827
lift_at_10: 8.89
macro_f1: 0.918346
val_f1: 0.836957
bootstrap_ci_lo: 0.757777
bootstrap_ci_hi: 0.897528
bootstrap_se: 0.036281
anomaly_fired: false
anomaly_reason: val_pr_auc=0.828827 within expected range (threshold=0.750000)
review_note: seed baseline

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.828811 ci=[0.757777, 0.897528] se=0.036281 n_boot=1000

### Escalation

None.

## Round 10

commit: 42d7410
verdict: discard
action_type: A_ensemble
hypothesis: A weighted XGBoost + LightGBM ensemble can beat the current single-model XGBoost incumbent.
model_family: ensemble
val_pr_auc: 0.831174
lift_at_10: 9.19
macro_f1: 0.922954
val_f1: 0.846154
bootstrap_ci_lo: 0.757307
bootstrap_ci_hi: 0.895168
bootstrap_se: 0.035804
anomaly_fired: false
anomaly_reason: val_pr_auc=0.831174 within expected range (threshold=0.750000)
review_note: delta=-0.013023 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.831174 ci=[0.757307, 0.895168] se=0.035804 n_boot=1000

### Escalation

Executed as the first post-C2 structural move after an operator reset of `consecutive_discards`.

## Round 9

commit: 425a998
verdict: discard
action_type: A_model
hypothesis: CatBoost on the same engineered feature set can challenge the current XGBoost incumbent without exceeding the time budget.
model_family: catboost
val_pr_auc: 0.820385
lift_at_10: 9.19
macro_f1: 0.916080
val_f1: 0.832432
bootstrap_ci_lo: 0.741170
bootstrap_ci_hi: 0.891035
bootstrap_se: 0.037404
anomaly_fired: false
anomaly_reason: val_pr_auc=0.820385 within expected range (threshold=0.750000)
review_note: delta=-0.023812 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.820385 ci=[0.741170, 0.891035] se=0.037404 n_boot=1000

### Escalation

None.

## Round 8

commit: 6877226
verdict: discard
action_type: A_hp
hypothesis: A larger final XGBoost booster can improve the incumbent because the current run is well under budget.
model_family: xgboost
val_pr_auc: 0.844136
lift_at_10: 9.29
macro_f1: 0.916080
val_f1: 0.832432
bootstrap_ci_lo: 0.775240
bootstrap_ci_hi: 0.905510
bootstrap_se: 0.034351
anomaly_fired: false
anomaly_reason: val_pr_auc=0.844136 within expected range (threshold=0.750000)
review_note: delta=-0.000061 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.844136 ci=[0.775240, 0.905510] se=0.034351 n_boot=1000

### Escalation

None.

## Round 7

commit: bd4fc8f
verdict: discard
action_type: A_hp
hypothesis: Anchoring XGBoost scale_pos_weight to the observed class ratio will improve ranking stability over the broad default range.
model_family: xgboost
val_pr_auc: 0.841134
lift_at_10: 9.19
macro_f1: 0.916080
val_f1: 0.832432
bootstrap_ci_lo: 0.766654
bootstrap_ci_hi: 0.901505
bootstrap_se: 0.034630
anomaly_fired: false
anomaly_reason: val_pr_auc=0.841134 within expected range (threshold=0.750000)
review_note: delta=-0.003063 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.841134 ci=[0.766654, 0.901505] se=0.034630 n_boot=1000

### Escalation

None.

## Round 6

commit: 8894daf
verdict: keep
action_type: A_model
hypothesis: A canonical XGBoost hist search in the known-good depth band can outperform the current LightGBM incumbent.
model_family: xgboost
val_pr_auc: 0.844197
lift_at_10: 9.29
macro_f1: 0.913838
val_f1: 0.827957
bootstrap_ci_lo: 0.774725
bootstrap_ci_hi: 0.904986
bootstrap_se: 0.034407
anomaly_fired: false
anomaly_reason: val_pr_auc=0.844197 within expected range (threshold=0.750000)
review_note: improved best

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.844196 ci=[0.774725, 0.904986] se=0.034407 n_boot=1000

### Escalation

None.

## Round 5

commit: c541c22
verdict: discard
action_type: A_feature
hypothesis: Log-scaled amount interactions will complement the raw amount interactions and improve ranking precision.
model_family: lightgbm
val_pr_auc: 0.830782
lift_at_10: 8.89
macro_f1: 0.918346
val_f1: 0.836957
bootstrap_ci_lo: 0.760639
bootstrap_ci_hi: 0.899481
bootstrap_se: 0.036210
anomaly_fired: false
anomaly_reason: val_pr_auc=0.830782 within expected range (threshold=0.750000)
review_note: delta=-0.004499 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.830764 ci=[0.760639, 0.899481] se=0.036210 n_boot=1000

### Escalation

None.

## Round 4

commit: c0c241e
verdict: keep
action_type: A_hp
hypothesis: A higher-fidelity Optuna proxy will pick stronger LightGBM parameters than the current 200-tree proxy.
model_family: lightgbm
val_pr_auc: 0.835281
lift_at_10: 9.50
macro_f1: 0.923610
val_f1: 0.847458
bootstrap_ci_lo: 0.761324
bootstrap_ci_hi: 0.896567
bootstrap_se: 0.035528
anomaly_fired: false
anomaly_reason: val_pr_auc=0.835281 within expected range (threshold=0.750000)
review_note: improved best

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.835253 ci=[0.761324, 0.896567] se=0.035528 n_boot=1000

### Escalation

None.

## Round 3

commit: 4205cec
verdict: discard
action_type: A_hp
hypothesis: Anchoring scale_pos_weight to the observed class ratio will stabilize the LightGBM search against overweighted positives.
model_family: lightgbm
val_pr_auc: 0.805350
lift_at_10: 9.09
macro_f1: 0.916080
val_f1: 0.832432
bootstrap_ci_lo: 0.723554
bootstrap_ci_hi: 0.873751
bootstrap_se: 0.038722
anomaly_fired: false
anomaly_reason: val_pr_auc=0.805350 within expected range (threshold=0.750000)
review_note: delta=-0.023477 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.805326 ci=[0.723554, 0.873751] se=0.038722 n_boot=1000

### Escalation

None.

## Round 2

commit: aa56fb6
verdict: discard
action_type: A_hp
hypothesis: Explicit depth control will reduce LightGBM overfitting versus the baseline leaf-only search.
model_family: lightgbm
val_pr_auc: 0.804273
lift_at_10: 9.09
macro_f1: 0.902081
val_f1: 0.804469
bootstrap_ci_lo: 0.722385
bootstrap_ci_hi: 0.871245
bootstrap_se: 0.038169
anomaly_fired: false
anomaly_reason: val_pr_auc=0.804273 within expected range (threshold=0.750000)
review_note: delta=-0.024554 <= 0

### Tool outputs

- anomaly: not fired
- bootstrap_ci: metric=0.804268 ci=[0.722385, 0.871245] se=0.038169 n_boot=1000

### Escalation

None.