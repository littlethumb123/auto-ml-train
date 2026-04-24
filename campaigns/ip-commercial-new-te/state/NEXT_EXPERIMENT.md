---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 19
planner_invocation_at: "2026-04-24T11:15:00Z"
action_type: "A_feature"
hypothesis: "Engineered features combining tabular signals (IP utilization counts × chronic condition flags; age bins × IP history) will add predictive signal not captured by the existing 789 features, improving the 5-model ensemble beyond the current ceiling (22.659)."
expected_effect_size: "Δval_lift_1pct: +0.3 to +1.0 (STRATEGY_GUIDE §2: A_feature 0.2-1.0 when champion not saturated)"
base_commit: "75b3ee2"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 19. Best: 5-model ensemble 22.659. Ensemble gains vanishing (+0.017 in round 18). Feature engineering is the next STRATEGY_GUIDE §1 priority — 789 features are all available, but interaction terms may capture signal that individual features miss.

## 2. Evidence from memory

- PRIORS known_good: `np.log1p(Amount)` and `Amount * V1/V2` added signal in creditcard campaign.
- Round 6 SHAP: 50/50 embedding/tabular split. Tabular features carry strong signal.
- Known tabular features include: IP MDC counts (ipmdc01-25), member months (mm_*mo), lab values.
- Domain knowledge: IP6 risk driven by: (1) prior IP utilization, (2) comorbidity burden, (3) lab abnormalities.

## 3. Plan

Engineer features in train.py before loading from cache:
1. `ip_utilization_score` = sum of ipmdc*_2yr_cnt columns (total IP episodes by MDC)
2. `chronic_burden_score` = sum of binary chronic condition flags
3. `lab_abnormality_score` = sum of lab_elev_* and lab_low_* columns
4. `age_ip_interaction` = age × ip_utilization_score
5. `mm_ip_ratio` = ip_utilization_score / (mm_2yr_cnt + 1)

Use these 5 new features alongside the 789 existing in the 5-model ensemble. Rebuild the split cache with augmented features.

## 4. Helpers

None.

## 5. How this differs from current train.py

Add feature engineering block after loading from cache. New cache will be built for the augmented feature set.

## 6. Escalation

### No escalation
