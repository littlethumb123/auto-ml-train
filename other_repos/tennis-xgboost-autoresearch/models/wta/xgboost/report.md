# WTA XGBoost Report

- tour: `wta`
- train rows: `112064`
- test rows: `614`
- cutoff date: `2025-09-30`
- test mode: `date`
- test set: all matches after cutoff (16 tournaments)

## Metrics

| metric | value |
| --- | --- |
| accuracy | 0.6661 |
| roc_auc | 0.7258 |
| brier_score | 0.2133 |
| log_loss | 0.6155 |

## Per-Tournament Breakdown

| tourney_name | matches | correct | accuracy |
| --- | --- | --- | --- |
| Indian Wells | 89.0 | 68.0 | 0.7640449438202247 |
| Doha | 55.0 | 35.0 | 0.6363636363636364 |
| Dubai | 55.0 | 40.0 | 0.7272727272727273 |
| Wuhan | 55.0 | 36.0 | 0.6545454545454545 |
| Brisbane | 47.0 | 34.0 | 0.723404255319149 |
| Auckland | 31.0 | 23.0 | 0.7419354838709677 |
| Chennai | 31.0 | 15.0 | 0.4838709677419355 |
| Guangzhou | 31.0 | 18.0 | 0.5806451612903226 |
| Hobart | 31.0 | 17.0 | 0.5483870967741935 |
| Hong Kong | 31.0 | 26.0 | 0.8387096774193549 |
| Jiujiang | 31.0 | 16.0 | 0.5161290322580645 |
| Pan Pacific Open | 31.0 | 18.0 | 0.5806451612903226 |
| Abu Dhabi | 27.0 | 15.0 | 0.5555555555555556 |
| Ningbo | 27.0 | 16.0 | 0.5925925925925926 |
| Tokyo | 27.0 | 21.0 | 0.7777777777777778 |
| Riyadh Finals | 15.0 | 11.0 | 0.7333333333333333 |

## Top 20 Features

| feature | importance |
| --- | --- |
| elo_diff | 0.11188086867332458 |
| surface_elo_shrunk_diff | 0.046029336750507355 |
| tourney_level_D | 0.04156230762600899 |
| rank_edge | 0.024798735976219177 |
| opponent_elo_avg_last_100_diff | 0.022337252274155617 |
| surface_elo_diff | 0.018719565123319626 |
| win_rate_last_100_diff | 0.014009654521942139 |
| matches_last_30_days_diff | 0.01395495980978012 |
| round_order | 0.013207748532295227 |
| opponent_surface_elo_avg_last_100_diff | 0.009522035717964172 |
| draw_size | 0.009313437156379223 |
| win_rate_last_50_diff | 0.007957306690514088 |
| opponent_surface_elo_avg_last_50_diff | 0.007598718162626028 |
| surface_service_points_won_rate_last_25_diff | 0.007403102237731218 |
| point_win_rate_last_10_diff | 0.007327886298298836 |
| surface_win_rate_diff | 0.00712091289460659 |
| opponent_elo_avg_last_50_diff | 0.006708620581775904 |
| surface_service_points_won_rate_last_10_diff | 0.0065971058793365955 |
| entry_q_diff | 0.0063167414627969265 |
| entry_q_sum | 0.006266135722398758 |