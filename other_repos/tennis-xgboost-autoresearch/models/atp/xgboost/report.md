# ATP XGBoost Report

- tour: `atp`
- train rows: `132503`
- test rows: `607`
- cutoff date: `2025-12-31`
- test mode: `date`
- test set: all matches after cutoff (17 tournaments)

## Metrics

| metric | value |
| --- | --- |
| accuracy | 0.6853 |
| roc_auc | 0.7611 |
| brier_score | 0.2001 |
| log_loss | 0.5821 |

## Per-Tournament Breakdown

| tourney_name | matches | correct | accuracy |
| --- | --- | --- | --- |
| Australian Open | 127.0 | 95.0 | 0.7480314960629921 |
| Indian Wells Masters | 89.0 | 58.0 | 0.651685393258427 |
| Acapulco | 31.0 | 20.0 | 0.6451612903225806 |
| Dubai | 31.0 | 21.0 | 0.6774193548387096 |
| Rotterdam | 31.0 | 23.0 | 0.7419354838709677 |
| Rio de Janeiro | 31.0 | 19.0 | 0.6129032258064516 |
| Doha | 31.0 | 27.0 | 0.8709677419354839 |
| Dallas | 31.0 | 25.0 | 0.8064516129032258 |
| Brisbane | 31.0 | 19.0 | 0.6129032258064516 |
| Adelaide | 27.0 | 15.0 | 0.5555555555555556 |
| Hong Kong | 27.0 | 17.0 | 0.6296296296296297 |
| Auckland | 27.0 | 17.0 | 0.6296296296296297 |
| United Cup | 25.0 | 11.0 | 0.44 |
| Montpellier | 19.0 | 10.0 | 0.5263157894736842 |
| Santiago | 19.0 | 13.0 | 0.6842105263157895 |
| Delray Beach | 15.0 | 13.0 | 0.8666666666666667 |
| Buenos Aires | 15.0 | 13.0 | 0.8666666666666667 |

## Top 20 Features

| feature | importance |
| --- | --- |
| elo_diff | 0.09976469725370407 |
| surface_elo_diff | 0.041525572538375854 |
| rank_edge | 0.020341333001852036 |
| tourney_level_D | 0.011862518265843391 |
| opponent_surface_elo_avg_last_100_diff | 0.01058920007199049 |
| opponent_elo_avg_last_100_diff | 0.008559194393455982 |
| hand_unknown_sum | 0.008023062720894814 |
| matches_last_30_days_diff | 0.007675746455788612 |
| surface_game_margin_avg_last_25_diff | 0.007466768380254507 |
| surface_point_win_rate_last_25_diff | 0.007354978006333113 |
| surface_matches_diff | 0.006358908023685217 |
| point_win_rate_last_10_diff | 0.0060069868341088295 |
| season_surface_matches_diff | 0.005931721534579992 |
| reliability_career_matches_min | 0.005265256855636835 |
| reliability_surface_matches_min | 0.004997905809432268 |
| quality_weighted_point_win_rate_last_10_diff | 0.004780640825629234 |
| round_RR | 0.004770047962665558 |
| draw_size_rounds | 0.00458306772634387 |
| game_margin_avg_last_100_diff | 0.0044958810321986675 |
| draw_size | 0.004184272605925798 |