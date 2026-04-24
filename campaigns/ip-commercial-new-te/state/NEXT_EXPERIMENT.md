---
schema_version: 1
campaign_id: "ip-commercial-new-te"
round: 20
planner_invocation_at: "2026-04-24T11:20:00Z"
action_type: "A_feature"
hypothesis: "Adding 5 more targeted domain features (IP days severity, recency ratio, ER utilization, ER×chronic interaction, and stay severity) to the existing 5 will improve lift@1% by encoding more clinical risk signal that the base features don't directly capture."
expected_effect_size: "Δval_lift_1pct: +0.05 to +0.3 (incremental domain features)"
base_commit: "daaa604"
touches_helpers: false
helpers_declared: []
escalation: null
---

## 1. Context

Round 20. Best: 5-model ensemble + 5 eng features = 22.677 (round 19). Gains of +0.018 suggest signal is present but marginal. Adding 5 more domain features targeting IP severity (days per admission), recency (1yr vs 2yr utilization ratio), ER pathway (ER visits predict IP), and combined risk (ER × chronic disease burden).

## 2. Evidence from memory

- Round 19: 5 features (IP score, chronic score, lab score, age×IP, mm/IP ratio) added +0.018.
- ER visits are a known IP precursor — `er_clm_cnt_1yr` exists in columns.
- IP MDC days columns (`ipmdc*_2yr_days`) capture stay severity, not just count.
- 1yr/2yr IP recency ratio captures acceleration of utilization.

## 3. Plan

Extend `_engineer()` in train.py to add 5 more features:
1. `eng_ip_days_score` = sum(ipmdc*_2yr_days) — total IP days in 2yr
2. `eng_ip_recency` = sum(ipmdc*_1yr_cnt) / (sum(ipmdc*_2yr_cnt) + 0.1) — recent vs total ratio
3. `eng_er_total` = er_clm_cnt_1yr
4. `eng_er_x_chronic` = er_clm_cnt_1yr × chronic_score
5. `eng_severity` = eng_ip_days / (eng_ip_score + 0.1) — average IP stay length

No new cache rebuild needed (features added post-cache-load).

## 4. Helpers

None.

## 5. How this differs from current train.py

Extend `_engineer()` function body: add 5 more computed columns (10 total). The rest of the pipeline (5-model ensemble, scipy optimization) is unchanged.

## 6. Escalation

### No escalation
