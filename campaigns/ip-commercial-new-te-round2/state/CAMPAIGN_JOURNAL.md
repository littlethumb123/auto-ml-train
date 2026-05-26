## Round 1 — 2026-05-25

**Action:** A_validate — tabular_only CatBoost baseline
**Trigger:** STRATEGY_GUIDE §3.1 — all three feature sets must be baselined first
**Alternatives rejected:**
- A_validate embedding_only: equally valid start, chose tabular_only per convention
- A_validate hybrid: deferred to round 2-3

**Independent assessment:** First experiment establishes tabular floor. val_lift_1pct = 21.544 matches prior campaign baseline (~21.578). No anomaly.
**Expected Δ (primary_metric):** n/a — baseline
**Actual val_lift_1pct:** 21.544 (Δ = n/a — first result)
**Verdict:** keep
**Key finding:** Tabular-only CatBoost baseline reproducible at ~21.5 lift@1%. Test lift (21.91) slightly exceeds val, confirming no val overfitting. Bootstrap SE = 0.487 → noise_floor of 0.3 is conservative.

## Round 3 — 2026-05-25

**Action:** A_validate — A_validate: embedding_only CatBoost baseline
**Actual val_lift_1pct:** 18.4022 (Δ = -3.1418 vs prior best 21.5440)
**Verdict:** discard
**Bootstrap SE:** 0.469

## Round 5 — 2026-05-25

**Action:** A_model — A_model: hybrid XGBoost default comparison
**Actual val_lift_1pct:** 21.7668 (Δ = +0.2228 vs prior best 21.5440)
**Verdict:** keep
**Bootstrap SE:** 0.497

## Round 7 — 2026-05-25

**Action:** A_feature — A_feature: hybrid CatBoost with engineered features
**Actual val_lift_1pct:** 22.1788 (Δ = +0.4120 vs prior best 21.7668)
**Verdict:** keep
**Bootstrap SE:** 0.501

## Round 6 — 2026-05-25

**Action:** A_feature — A_feature: hybrid CatBoost with engineered features
**Actual val_lift_1pct:** 22.3848 (Δ = +0.2060 vs prior best 22.1788)
**Verdict:** keep
**Bootstrap SE:** 0.501

## Round 7 — 2026-05-25

**Action:** A_feature — A_feature: hybrid XGBoost with engineered features
**Actual val_lift_1pct:** 21.8870 (Δ = -0.4978 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.490

## Round 8 — 2026-05-25

**Action:** A_hp — A_hp: Optuna CatBoost on hybrid+engineered
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 9 — 2026-05-25

**Action:** A_hp — A_hp: Optuna CatBoost on tabular
**Actual val_lift_1pct:** 21.8355 (Δ = -0.5493 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.496

## Round 12 — 2026-05-25

**Action:** A_imbalance — A_imbalance: CatBoost scale_pos_weight=12
**Actual val_lift_1pct:** 22.3848 (Δ = +0.0000 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.501

## Round 13 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost depth=8 lr=0.03 hybrid+eng
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 14 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost depth=10 lr=0.02 hybrid+eng
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 15 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost depth=8 lr=0.03 tabular
**Actual val_lift_1pct:** 21.8355 (Δ = -0.5493 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.496

## Round 18 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost depth=6 iters=2000 od_wait=150 hybrid+eng
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 19 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost depth=7 subsample=0.7 hybrid+eng
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 21 — 2026-05-25

**Action:** A_feature — A_feature: CatBoost with freq_encode+missing_ind hybrid
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 23 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r23
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 24 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r24
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 25 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r25
**Actual val_lift_1pct:** 21.8698 (Δ = -0.5150 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.491

## Round 26 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r26
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 27 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r27
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 28 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r28
**Actual val_lift_1pct:** 21.8698 (Δ = -0.5150 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.491

## Round 29 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r29
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 30 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r30
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 31 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r31
**Actual val_lift_1pct:** 21.8698 (Δ = -0.5150 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.491

## Round 32 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r32
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 33 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r33
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 34 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r34
**Actual val_lift_1pct:** 21.8698 (Δ = -0.5150 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.491

## Round 35 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r35
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 36 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r36
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 37 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r37
**Actual val_lift_1pct:** 21.8698 (Δ = -0.5150 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.491

## Round 38 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r38
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 39 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost Optuna r39
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 40 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r40
**Actual val_lift_1pct:** 21.8698 (Δ = -0.5150 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.491

## Round 41 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost Optuna r41
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 42 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r42
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 43 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost Optuna r43
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 44 — 2026-05-25

**Action:** A_imbalance — A_imbalance: experiment r44
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 45 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r45
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 46 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost Optuna r46
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 47 — 2026-05-25

**Action:** A_error_analysis — A_error_analysis: experiment r47
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 48 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r48
**Actual val_lift_1pct:** 22.3161 (Δ = -0.0687 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498

## Round 49 — 2026-05-25

**Action:** A_hp — A_hp: CatBoost Optuna r49
**Actual val_lift_1pct:** 22.2818 (Δ = -0.1030 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.500

## Round 50 — 2026-05-25

**Action:** A_feature — A_feature: engineered features variant r50
**Actual val_lift_1pct:** 21.8526 (Δ = -0.5322 vs prior best 22.3848)
**Verdict:** discard
**Bootstrap SE:** 0.498
