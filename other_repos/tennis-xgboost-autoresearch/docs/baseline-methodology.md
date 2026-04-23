# XGBoost Baseline for Professional Tennis Match Prediction

## Methodology, Results, and Indian Wells 2026 Predictions

*tennis-xgboost-autoresearch project*

March 14, 2026 -- Version 1.1 (Updated for rebalanced WTA test set)

---

### Abstract

We present a gradient-boosted tree baseline for predicting professional tennis match outcomes on both the ATP and WTA tours. The model combines an ELO rating system (K=32, with Bayesian-shrunk surface-specific ratings) with 200+ engineered features spanning career statistics, rolling-window performance metrics, surface-specific form, head-to-head records, and rank momentum indicators. Feature vectors are constructed under strict temporal integrity constraints: all predictors use only pre-match information, and training/test splits enforce chronological separation. Trained on approximately 133K ATP and 113K WTA matches from 1985--2025 and validated on 607 ATP matches (after 2025-12-31) and 614 WTA matches (after 2025-09-30), the ATP model achieves **68.7% accuracy** (ROC-AUC 0.747, Brier 0.205) and the WTA model achieves **66.6% accuracy** (ROC-AUC 0.728, Brier 0.213). The combined ROC-AUC across both tours is **0.7421**. We document a data-ordering bug discovered during development that inflated WTA accuracy to 90.5%, describe how it was caught and fixed, and present forward-looking model forecasts for the Indian Wells 2026 semifinals and finals.

---

## 1. Introduction

Predicting the outcome of professional tennis matches is a well-studied problem at the intersection of sports analytics and machine learning. Tennis is particularly amenable to quantitative modeling: matches are one-on-one contests with rich historical data, well-defined surfaces that affect play style, and standardized rating systems that provide a natural baseline signal.

This project was inspired by a widely-cited result from GreenCoding (2025) claiming 85% prediction accuracy on a dataset of 95,000+ ATP matches using XGBoost with ELO features. While that figure warrants scrutiny -- our own initial WTA run appeared to hit 90.5% before a temporal ordering bug was discovered (see Section 7) -- the general finding that gradient-boosted trees on ELO-augmented features provide strong tennis prediction baselines is well-supported by the literature.

This paper documents the baseline methodology for the `tennis-xgboost-autoresearch` project, which aims to establish a rigorous, reproducible prediction pipeline that can serve as the foundation for automated hyperparameter and feature engineering exploration. Our contributions are:

1. A complete, tour-agnostic pipeline that works identically for ATP and WTA data with strict temporal integrity;
2. Surface-specific ELO ratings with Bayesian shrinkage to handle players with limited surface exposure;
3. A feature engineering framework spanning 210+ features across 8 categories;
4. Honest baseline results with full per-tournament breakdowns;
5. Documentation of a subtle but critical data ordering bug and its resolution.

## 2. Data

The primary data source is Jeff Sackmann's open tennis repositories (CC BY-NC-SA 4.0), which provide match-by-match records for the ATP tour (1968--present) and WTA tour (1968--present). We use main-tour matches from 1985 onward, excluding qualifiers, ITF events, futures, and challengers.

For 2025--2026 coverage beyond the Sackmann repositories, we supplement with:

- **TML-Database:** ATP match data for 2025--2026, converted to Sackmann-compatible format via a dedicated pipeline;
- **Web scraping:** WTA 2025--2026 data from tennisexplorer.com and tennisabstract.com;
- **Indian Wells 2026 validation set:** Manually curated results for the ongoing tournament (93 ATP matches, 96 WTA matches).

The complete dataset comprises **133,110 ATP matches** and **112,678 WTA matches**. A detailed schema and provenance description is provided in the companion [Dataset Documentation](dataset.md).

## 3. Methodology

### 3.1 ELO Rating System

We implement a standard ELO rating system with the following parameters:

- **K-factor:** 32 (fixed for all matches, following the classical chess convention for active players)
- **Initial rating:** 1500 for all players
- **Expected score:** E(A) = 1 / (1 + 10^((R_B - R_A) / 400))
- **Update rule:** R'_A = R_A + K * (S_A - E(A)), where S_A in {0, 1}

In addition to overall ELO, we maintain **per-surface ELO ratings** (Hard, Clay, Grass, Carpet) with independent tracking. To handle the cold-start problem for surface ratings -- a player may have extensive match history on hard courts but very few grass-court appearances -- we apply **Bayesian shrinkage**:

> ELO_shrunk = ELO_overall + (ELO_surface - ELO_overall) * min(n_surface / 20, 1.0)

where n_surface is the player's match count on that surface and 20 is the `SURFACE_PRIOR_MATCHES` hyperparameter. When a player has fewer than 20 surface matches, their surface ELO is blended toward their overall rating; at 20+ matches, the raw surface ELO is used directly.

**Temporal integrity:** All ELO values used as features are strictly pre-match snapshots. The ELO update is applied *after* feature extraction for each match, ensuring zero information leakage from future results.

### 3.2 Feature Engineering

Features are organized into eight categories, all computed from the perspective of a canonically-oriented player pair (player A vs. player B, assigned deterministically by ID comparison to remove winner/loser label bias):

| Category | Features | Description |
|----------|----------|-------------|
| ELO Ratings | elo_diff, elo_sum, surface_elo_diff, surface_elo_sum, surface_elo_shrunk_diff/sum, surface_elo_gap_diff/sum | Overall and surface-specific ratings, Bayesian-shrunk variants, and surface-vs-overall gap |
| Career Statistics | career_matches_diff/sum, career_win_rate_diff/sum, surface_matches_diff/sum, surface_win_rate_diff/sum | Lifetime match counts and win rates, overall and per-surface |
| Rolling Windows | 17 metrics x 4 windows (10/25/50/100) x 2 (diff/sum) = 136 features | Win rate, ace rate, double-fault rate, first-serve stats, return stats, break points, match duration, ELO delta, opponent strength, performance vs. expectation |
| Surface-Specific Form | 6 metrics x 2 windows (10/25) x 2 (diff/sum) = 24 features | Same metrics restricted to the current match surface |
| Recent Activity | 3 metrics x 2 windows (14/30 days) x 2 (diff/sum) = 12 features | Match count, total minutes, win rate in recent calendar windows |
| Rank Momentum | 2 metrics x 2 windows (28/91 days) x 2 (diff/sum) = 8 features | Rank change and ranking points change over recent periods |
| Head-to-Head | h2h_diff, h2h_total | Pre-match head-to-head win count differential and total meetings |
| Static Diffs | age_diff, height_diff, seed_diff, rank_edge, rank_points_diff | Physical and ranking attributes |

*Table 1. Feature categories and their composition. Total: 210 numeric features + 3 categorical features.*

**Canonical orientation:** For each match, players are assigned to positions A and B deterministically by comparing (player_id, player_name) tuples. The label is 1 if player A won, 0 otherwise. All numeric features are computed as both `diff` (A - B) and `sum` (A + B), allowing the model to capture both relative strength and absolute quality. This eliminates winner/loser ordering bias that would otherwise leak the target.

### 3.3 Categorical Features

Three categorical features are included:

- **surface:** Hard, Clay, Grass, Carpet, Unknown
- **tourney_level:** G (Grand Slam), M (Masters 1000), 500, 250, D (Davis Cup/Billie Jean King Cup), etc.
- **round:** R128, R64, R32, R16, QF, SF, F, RR, BR

### 3.4 Model Architecture

The model is a scikit-learn `Pipeline` consisting of a preprocessing step and an XGBoost classifier:

**Preprocessing:**
- Numeric features: median imputation (`SimpleImputer(strategy="median")`)
- Categorical features: most-frequent imputation followed by one-hot encoding (`OneHotEncoder(handle_unknown="ignore")`)

**XGBoost hyperparameters (fixed baseline):**

| Parameter | Value |
|-----------|-------|
| n_estimators | 500 |
| max_depth | 4 |
| learning_rate | 0.05 |
| subsample | 0.85 |
| colsample_bytree | 0.80 |
| reg_lambda | 1.0 |
| min_child_weight | 5 |
| objective | binary:logistic |
| eval_metric | logloss |
| tree_method | hist |
| random_state | 42 |

*Table 2. XGBoost baseline hyperparameters.*

Separate models are trained for ATP and WTA tours. The rationale is that the two tours have structurally different characteristics: ATP matches are best-of-5 at Grand Slams (vs. best-of-3 for WTA), tournament structures differ (Masters 1000 vs. Premier Mandatory/Premier 5), and the statistical distributions of serve dominance, break rates, and match duration differ meaningfully between tours. A unified model would need to learn these distinctions implicitly, adding unnecessary complexity to the baseline.

## 4. Experimental Setup

### 4.1 Training Data

The training set comprises all matches up to each tour's cutoff date:

| Tour | Training Matches | Year Range | Cutoff Date |
|------|-----------------|------------|-------------|
| ATP | 132,503 | 1985--2025 | 2025-12-31 |
| WTA | ~112,900 | 1985--2025 | 2025-09-30 |

*Table 3. Training set composition. Per-tour cutoff dates balance the test set sizes.*

### 4.2 Validation Data

The validation set consists of all matches played after each tour's cutoff date, providing a genuine out-of-time test. Per-tour cutoff dates are used to balance the test set sizes so that the combined ROC-AUC metric weights both tours equally by sample count.

| Tour | Test Matches | Tournaments | Cutoff Date | Period |
|------|-------------|-------------|-------------|--------|
| ATP | 607 | 17 | 2025-12-31 | Jan 1 -- Mar 14, 2026 |
| WTA | 614 | 16 | 2025-09-30 | Oct 1, 2025 -- Mar 14, 2026 |

*Table 4. Validation set composition.*

This temporal split is stricter than k-fold cross-validation and more realistic: the model must predict unseen future matches using only historical data, exactly as it would be used in practice. The per-tour cutoff approach ensures that neither tour dominates the combined metric.

## 5. Results

### 5.1 Overall Metrics

| Metric | ATP | WTA |
|--------|-----|-----|
| Accuracy | **68.70%** | **66.57%** |
| ROC-AUC | 0.7472 | 0.7282 |
| Brier Score | 0.2052 | 0.2126 |
| Log Loss | 0.5948 | 0.6118 |
| **Combined ROC-AUC** | | **0.7421** |

*Table 5. Overall model performance on validation data. Combined ROC-AUC is computed over the union of ATP (607) and WTA (614) test matches.*

The ATP model outperforms WTA by approximately 2 percentage points in accuracy, consistent with the general observation that ATP results are more predictable due to best-of-5 format at Slams reducing upset variance, higher serve dominance amplifying skill differentials, and a more stable top-player hierarchy.

> **Note on WTA metrics:** The WTA accuracy and ROC-AUC figures above reflect the original baseline parameters evaluated on the rebalanced 614-match test set. Individual tournament-level metrics for the expanded WTA test set (including 2025 Q4 tournaments) are TBD -- to be recomputed after rebalancing is fully validated. The overall figures are taken from the initial pipeline evaluation under the new cutoff.

### 5.2 Per-Tournament Breakdown: ATP

| Tournament | Matches | Correct | Accuracy |
|------------|---------|---------|----------|
| Delray Beach | 15 | 13 | **86.7%** |
| Doha | 31 | 25 | **80.6%** |
| Australian Open | 127 | 99 | **78.0%** |
| Rotterdam | 31 | 24 | 77.4% |
| Dallas | 31 | 24 | 77.4% |
| Buenos Aires | 15 | 11 | 73.3% |
| Adelaide | 27 | 19 | 70.4% |
| Santiago | 19 | 13 | 68.4% |
| Acapulco | 31 | 21 | 67.7% |
| Dubai | 31 | 21 | 67.7% |
| Hong Kong | 27 | 18 | 66.7% |
| Rio de Janeiro | 31 | 20 | 64.5% |
| Indian Wells Masters | 89 | 57 | 64.0% |
| Auckland | 27 | 17 | 63.0% |
| Brisbane | 31 | 16 | *51.6%* |
| United Cup | 25 | 12 | *48.0%* |
| Montpellier | 19 | 7 | *36.8%* |

*Table 6. ATP per-tournament accuracy, sorted by accuracy descending.*

Performance varies substantially across tournaments. The model excels at Grand Slams (Australian Open: 78.0%) and larger events where top players dominate, but struggles at smaller 250-level events (Montpellier: 36.8%) and team events (United Cup: 48.0%) where match dynamics differ from standard tour play.

### 5.3 Per-Tournament Breakdown: WTA

The WTA test set now spans 16 tournaments across two periods: 2025 Q4 (after the 2025-09-30 cutoff) and 2026 through mid-March.

**2025 Q4 tournaments (Oct--Nov 2025):**

| Tournament | Matches | Correct | Accuracy |
|------------|---------|---------|----------|
| Wuhan | 55 | TBD | TBD |
| Pan Pacific Open | 31 | TBD | TBD |
| Jiujiang | 31 | TBD | TBD |
| Hong Kong | 31 | TBD | TBD |
| Guangzhou | 31 | TBD | TBD |
| Chennai | 31 | TBD | TBD |
| Tokyo | 27 | TBD | TBD |
| Ningbo | 27 | TBD | TBD |
| Riyadh Finals | 15 | TBD | TBD |

**2026 tournaments (Jan--Mar 2026):**

| Tournament | Matches | Correct | Accuracy |
|------------|---------|---------|----------|
| Indian Wells | 96 | TBD | TBD |
| Dubai | 55 | TBD | TBD |
| Doha | 55 | TBD | TBD |
| Brisbane | 47 | TBD | TBD |
| Auckland | 31 | TBD | TBD |
| Hobart | 31 | TBD | TBD |
| Abu Dhabi | 27 | TBD | TBD |

*Table 7. WTA per-tournament accuracy. TBD -- per-tournament breakdowns to be recomputed after rebalancing is fully validated. Match counts are approximate and subject to deduplication.*

### 5.4 Feature Importance: Top 10

| Rank | ATP Feature | Importance | WTA Feature | Importance |
|------|-------------|------------|-------------|------------|
| 1 | elo_diff | 0.1457 | elo_diff | 0.1214 |
| 2 | surface_elo_diff | 0.0675 | surface_elo_shrunk_diff | 0.0464 |
| 3 | rank_edge | 0.0405 | tourney_level_D | 0.0331 |
| 4 | surface_point_win_rate_last_25_diff | 0.0178 | surface_elo_diff | 0.0287 |
| 5 | opponent_elo_avg_last_100_diff | 0.0178 | opponent_elo_avg_last_100_diff | 0.0231 |
| 6 | matches_last_30_days_diff | 0.0156 | opponent_surface_elo_avg_last_100_diff | 0.0206 |
| 7 | point_win_rate_last_10_diff | 0.0134 | rank_edge | 0.0203 |
| 8 | tourney_level_D | 0.0124 | round_RR | 0.0158 |
| 9 | surface_matches_diff | 0.0106 | matches_last_30_days_diff | 0.0146 |
| 10 | surface_point_win_rate_last_10_diff | 0.0103 | surface_service_points_won_rate_last_10_diff | 0.0109 |

*Table 8. Top 10 features by XGBoost importance (gain) for each tour.*

The ELO differential dominates both models, accounting for 14.6% (ATP) and 12.1% (WTA) of total feature importance. Surface ELO variants collectively contribute another 7--8%, confirming that rating-based features are the backbone of prediction quality. Notably, the WTA model places higher importance on Bayesian-shrunk surface ELO, suggesting that surface-specific rating uncertainty matters more in the women's game where player surface specialization patterns differ.

Beyond ELO, the models value recent form (point win rates, recent activity), strength of schedule (opponent ELO averages), and tournament context (tournament level, round). The long tail of 200+ features with individually small importance contributions collectively adds significant predictive power.

## 6. Indian Wells 2026 Predictions

We apply the trained models to generate forward-looking predictions for the Indian Wells 2026 semifinals and finals. These predictions were generated on March 14, 2026, before the matches were played.

> **Retrospective note (March 16, 2026):** The matches described below have since been played (March 15--16, 2026). The predictions are retained here as a retrospective record of the model's forecasting ability. See the project's validation logs for actual vs. predicted outcomes.

### 6.1 ATP Semifinal Forecasts

| Match | Matchup | Predicted Winner | Model Confidence | Key Factors |
|-------|---------|-----------------|-----------------|-------------|
| SF1 | Carlos Alcaraz vs. Daniil Medvedev | **Carlos Alcaraz** | 76.1% | ELO diff +298.2, surface ELO diff +215.1 (Hard) |
| SF2 | Jannik Sinner vs. Alexander Zverev | **Jannik Sinner** | 67.6% | ELO diff +294.8, surface ELO diff +299.4 (Hard) |

*Table 9. ATP Indian Wells 2026 semifinal forecasts.*

**SF1 -- Alcaraz vs. Medvedev:** The model gives Alcaraz a strong 76.1% win probability, driven by an ELO differential of +298.2 and a hard-court surface ELO edge of +215.1. Alcaraz is the clear favorite despite Medvedev's strong run through the draw.

**SF2 -- Sinner vs. Zverev:** The model favors Sinner at 67.6%, based on an ELO differential of +294.8 and surface ELO differential of +299.4 on hard court. This is a synthetic prediction constructed from each player's latest feature states.

### 6.2 ATP Final Forecast

**FORECAST: ATP Indian Wells 2026 Final**

**Carlos Alcaraz vs. Jannik Sinner** (conditional on both winning their SFs)

Predicted winner: **Jannik Sinner (66.0%)**

| Factor | Value | Favors |
|--------|-------|--------|
| ELO Differential | -8.2 | Essentially even (slight Sinner edge) |
| Surface ELO Differential | -94.6 | Sinner (+94.6 hard court advantage) |
| Surface ELO Shrunk Diff | -94.6 | Sinner (both have 20+ hard court matches) |

Note: This is a synthetic prediction constructed from each player's latest feature states. The overall ELO is nearly identical, but Sinner's hard-court surface ELO is approximately 95 points higher, driving the model's prediction. The confidence level of 66.0% reflects the genuine closeness of this matchup.

### 6.3 WTA Final Forecast

**FORECAST: WTA Indian Wells 2026 Final**

**Aryna Sabalenka vs. Elena Rybakina**

Predicted winner: **Aryna Sabalenka (53.5%)**

| Factor | Value | Favors |
|--------|-------|--------|
| ELO Differential | +118.0 | Sabalenka |
| Surface ELO Differential | +118.3 | Sabalenka |
| Surface ELO Shrunk Diff | +118.3 | Sabalenka |

Note: Despite the ELO edge, the model assigns only 53.5% probability, reflecting the high variance of WTA matchups at the highest level. This is essentially a coin-flip call with a slight lean toward Sabalenka.

### 6.4 Forecast Summary

| Match | Predicted Winner | Model Confidence | Key Factor |
|-------|-----------------|-----------------|------------|
| ATP SF1: Alcaraz vs. Medvedev | Carlos Alcaraz | 76.1% | ELO diff +298.2 |
| ATP SF2: Sinner vs. Zverev | Jannik Sinner | 67.6% | ELO diff +294.8 |
| ATP Final: Alcaraz vs. Sinner | Jannik Sinner | 66.0% | Surface ELO diff +94.6 |
| WTA Final: Sabalenka vs. Rybakina | Aryna Sabalenka | 53.5% | ELO diff +118.0 |

*Table 10. Indian Wells 2026 prediction summary. Predictions generated March 14, 2026; all matches have since been played (March 15--16, 2026).*

## 7. Bug Discovery & Fix: The `match_num` Ordering Problem

During initial development, the WTA model achieved an apparent accuracy of **90.5%** -- a suspiciously high result that warranted investigation. The root cause was a subtle interaction between our temporal ordering logic and a convention change in Sackmann's data.

**The convention change:** Prior to the 2025 data files, Sackmann's `match_num` field assigned the highest values to later rounds (the final might have match_num ~300, R128 matches ~1--64). From 2025 onward, this convention reversed: the final has match_num=1 and early rounds have high match_num values.

**The bug:** Our initial implementation sorted matches by `(match_date, tourney_name, match_num ASC)`. This worked correctly for pre-2025 data (ascending match_num = R128 first, Final last = chronological order). But for 2025+ data, ascending match_num put the Final *first* and R128 matches *last*, reversing chronological order within each tournament. This meant ELO updates from the final contaminated features for first-round matches, creating massive temporal leakage.

**The fix:** Replace match_num-based ordering with explicit round-ordinal sorting. We defined a `ROUND_ORDER` mapping (R128=1, R64=2, ..., F=8) and sort by `(match_date, tourney_name, round_ordinal, match_num)`. The match_num is retained only as a tiebreaker within the same round. This approach is convention-agnostic and handles any future match_num encoding changes.

**Impact:** After the fix, WTA accuracy dropped from 90.5% to 66.6% -- a 24-point correction that brought results into alignment with ATP accuracy and with expectations from the literature. We document this bug explicitly as a cautionary example: a model that appears to perform far above established baselines should be investigated for data leakage before being celebrated.

## 8. Limitations & Future Work

This baseline has several known limitations that the auto-research exploration loop will address:

1. **Fixed hyperparameters:** The XGBoost parameters were set by reasonable convention, not tuned. Systematic Bayesian optimization over the hyperparameter space may yield 1--3% accuracy improvement.
2. **Fixed K-factor:** A constant K=32 treats all matches equally. Adaptive K-factors (higher for Grand Slams, lower for 250s; higher for new players, lower for established) could improve ELO signal quality.
3. **Missing serve/return data:** The 2025--2026 validation data lacks serve statistics (aces, double faults, first-serve percentage, etc.), meaning rolling window features based on these are NaN for recent matches. This disproportionately affects recent-form features.
4. **No recency weighting:** All historical matches contribute equally to career statistics. Time-decayed career metrics might better capture player trajectory.
5. **No contextual features:** The model does not incorporate betting odds, player injury status, weather conditions, or scheduling factors (e.g., days between matches, time zone changes).
6. **Single model type:** The baseline uses only XGBoost. Comparison with logistic regression (for calibration assessment), neural networks (for non-linear feature interactions), and ensemble methods would strengthen the analysis.
7. **WTA data quality:** WTA data has higher rates of missing height values and more tournament-level category diversity (T1--T5, PM, P, CC, etc.), introducing heterogeneity that may reduce model performance.

The auto-research pipeline will systematically explore these dimensions, treating each as a hypothesis to be tested with proper experimental controls.

## References

[1] Sackmann, J. (2024). Tennis Abstract / GitHub: tennis_atp, tennis_wta. Available at: `github.com/JeffSackmann/tennis_atp`, `github.com/JeffSackmann/tennis_wta`. License: CC BY-NC-SA 4.0.

[2] GreenCoding (2025). "Tennis Match Prediction with Machine Learning: 85% Accuracy on 95K+ Matches." Blog post. (Inspiration seed for this project.)

[3] Elo, A. (1978). *The Rating of Chessplayers, Past and Present.* Arco Publishing.

[4] Chen, T. & Guestrin, C. (2016). "XGBoost: A Scalable Tree Boosting System." *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.*

[5] Klaassen, F. J. & Magnus, J. R. (2003). "Forecasting the winner of a tennis match." *European Journal of Operational Research*, 148(2), 257--267.

[6] Sipko, M. & Knottenbelt, W. (2015). "Machine Learning for the Prediction of Professional Tennis Matches." MEng Computing Final Year Project, Imperial College London.

---

*Generated by tennis-xgboost-autoresearch -- March 14, 2026 -- Baseline v1.1*
