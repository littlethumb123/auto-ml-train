# Tennis Match Dataset Documentation

*tennis-xgboost-autoresearch project*

March 14, 2026 -- Version 1.1 (Updated for rebalanced WTA test set)

---

## 1. Overview

This document describes the match-level dataset used by the `tennis-xgboost-autoresearch` prediction pipeline. The dataset covers professional tennis matches on both the ATP (men's) and WTA (women's) tours from 1985 through early March 2026.

| Dimension | ATP | WTA |
|-----------|-----|-----|
| Total matches | 133,110 | 112,678 |
| Year range | 1985--2026 | 1985--2026 |
| Unique tournaments | 3,180 | 4,596 |
| Columns per match | 49 | 49 |
| File format (raw) | CSV (Sackmann schema) | CSV (Sackmann schema) |
| File format (processed) | Parquet (210+ engineered features) | Parquet (210+ engineered features) |

*Table 1. Dataset summary statistics.*

## 2. Sources & Provenance

### 2.1 Primary Source: JeffSackmann Tennis Repositories

The backbone of the dataset is Jeff Sackmann's open-source tennis data, maintained at:

- `github.com/JeffSackmann/tennis_atp` -- ATP match data, 1968--2024
- `github.com/JeffSackmann/tennis_wta` -- WTA match data, 1968--2024

**License:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0). Commercial use requires separate permission from the repository maintainer.

The Sackmann repositories are the de facto standard for academic and hobbyist tennis analytics, providing match-by-match records with winner/loser identity, tournament metadata, detailed serve and return statistics, rankings at the time of the match, and player biographical data (height, handedness, nationality).

We use main-tour match files from 1985 onward, excluding:

- Qualifying draws (`*_qual_*`)
- ITF-level events (`*_itf_*`)
- Futures (`*_futures_*`)
- Challengers (`*_chall_*`)

### 2.2 TML-Database (ATP 2025--2026)

For ATP matches in 2025 and early 2026 not yet incorporated into the Sackmann repository, we use data from the TML (Tennis Match Log) Database, converted to Sackmann-compatible CSV format via the pipeline script `scripts/convert_tml_to_sackmann.py`.

The conversion maps TML column names and value encodings to the Sackmann 49-column schema. Player IDs are cross-referenced against the Sackmann player database to maintain consistent identity. Matches with no Sackmann ID mapping are retained with empty ID fields.

### 2.3 Web Scraping (WTA 2025--2026)

WTA match data for late 2025 and 2026 is obtained from:

- **tennisexplorer.com** -- match results, scores, and bracket information
- **tennisabstract.com** -- supplementary player statistics and cross-referencing

Scraping scripts are located in `scripts/scrape_wta_tennisabstract.py` and `scripts/fill_wta_nov_dec_2025.py`. The scraped data follows the same 49-column schema but lacks serve/return statistics (which are not available from results-only pages).

### 2.4 Indian Wells 2026 Validation Set

A manually curated validation set covering the 2026 BNP Paribas Open (Indian Wells):

| Field | ATP | WTA |
|-------|-----|-----|
| File | `indian_wells_2026_atp.csv` | `indian_wells_2026_wta.csv` |
| Matches | 93 | 96 |
| Coverage | R128 through SF | R128 through F |
| tourney_id | 2026-0404 | 2026-609 |
| tourney_level | M (Masters) | PM (Premier Mandatory) |
| Surface | Hard | Hard |
| Source | tennisexplorer.com, scraped 2026-03-14 | tennisexplorer.com, scraped 2026-03-14 |

*Table 2. Indian Wells 2026 validation set details.*

> **Deduplication:** When validation CSVs are merged with the main Sackmann data, deduplication is performed on the `(tourney_id, match_num)` pair to prevent double-counting of matches that appear in both sources.

## 3. Schema

Each match record follows the 49-column Sackmann schema. The table below describes every column, its data type, and its role in the pipeline.

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `tourney_id` | str | Unique tournament identifier, typically `YYYY-NNNN` format |
| 2 | `tourney_name` | str | Tournament name (e.g., "Australian Open", "Indian Wells Masters") |
| 3 | `surface` | str | Playing surface: Hard, Clay, Grass, Carpet, or Unknown |
| 4 | `draw_size` | int | Main draw size (32, 48, 64, 96, 128) |
| 5 | `tourney_level` | str | Tournament tier. ATP: G, M, 500, 250, D, F, O. WTA: G, PM, P, T1--T5, CC, I, D, W, E, F, O |
| 6 | `tourney_date` | int | Tournament start date as `YYYYMMDD` integer |
| 7 | `match_num` | int | Match number within tournament. **Convention changed in 2025** -- see Section 6 |
| 8 | `winner_id` | int | Sackmann player ID of the winner |
| 9 | `winner_seed` | int/NaN | Winner's tournament seed (NaN if unseeded) |
| 10 | `winner_entry` | str/NaN | Winner's entry type: WC (wild card), Q (qualifier), LL (lucky loser), or NaN |
| 11 | `winner_name` | str | Winner's full name in "First Last" format |
| 12 | `winner_hand` | str | Winner's dominant hand: R (right), L (left), U (unknown) |
| 13 | `winner_ht` | int/NaN | Winner's height in centimeters |
| 14 | `winner_ioc` | str | Winner's country (IOC 3-letter code) |
| 15 | `winner_age` | float/NaN | Winner's age at match time (decimal years) |
| 16 | `loser_id` | int | Sackmann player ID of the loser |
| 17 | `loser_seed` | int/NaN | Loser's tournament seed |
| 18 | `loser_entry` | str/NaN | Loser's entry type |
| 19 | `loser_name` | str | Loser's full name |
| 20 | `loser_hand` | str | Loser's dominant hand |
| 21 | `loser_ht` | int/NaN | Loser's height in centimeters |
| 22 | `loser_ioc` | str | Loser's country (IOC code) |
| 23 | `loser_age` | float/NaN | Loser's age at match time |
| 24 | `score` | str | Match score (e.g., "6-4 7-6(3) 6-2") |
| 25 | `best_of` | int | Best-of format: 3 or 5 |
| 26 | `round` | str | Round: R128, R64, R32, R16, R4, QF, SF, F, RR, BR, ER |
| 27 | `minutes` | float/NaN | Match duration in minutes |
| 28 | `w_ace` | float/NaN | Winner's ace count |
| 29 | `w_df` | float/NaN | Winner's double fault count |
| 30 | `w_svpt` | float/NaN | Winner's total service points played |
| 31 | `w_1stIn` | float/NaN | Winner's first serves in |
| 32 | `w_1stWon` | float/NaN | Winner's first-serve points won |
| 33 | `w_2ndWon` | float/NaN | Winner's second-serve points won |
| 34 | `w_SvGms` | float/NaN | Winner's service games played |
| 35 | `w_bpSaved` | float/NaN | Winner's break points saved |
| 36 | `w_bpFaced` | float/NaN | Winner's break points faced |
| 37 | `l_ace` | float/NaN | Loser's ace count |
| 38 | `l_df` | float/NaN | Loser's double fault count |
| 39 | `l_svpt` | float/NaN | Loser's total service points played |
| 40 | `l_1stIn` | float/NaN | Loser's first serves in |
| 41 | `l_1stWon` | float/NaN | Loser's first-serve points won |
| 42 | `l_2ndWon` | float/NaN | Loser's second-serve points won |
| 43 | `l_SvGms` | float/NaN | Loser's service games played |
| 44 | `l_bpSaved` | float/NaN | Loser's break points saved |
| 45 | `l_bpFaced` | float/NaN | Loser's break points faced |
| 46 | `winner_rank` | float/NaN | Winner's ATP/WTA ranking at match time |
| 47 | `winner_rank_points` | float/NaN | Winner's ranking points at match time |
| 48 | `loser_rank` | float/NaN | Loser's ATP/WTA ranking at match time |
| 49 | `loser_rank_points` | float/NaN | Loser's ranking points at match time |

*Table 3. Complete schema of raw match data (49 columns).*

## 4. Coverage

### 4.1 Year-by-Year Match Counts

The dataset spans 42 years of professional tennis. Match volume reflects the evolution of both tours, including expansion in the 1990s, the impact of the 2020 COVID-19 pandemic, and the gradual recovery thereafter.

| Period | ATP Matches | WTA Matches |
|--------|-------------|-------------|
| 1985--1989 | 17,503 | 13,683 |
| 1990--1994 | 19,028 | 13,624 |
| 1995--1999 | 18,122 | 14,001 |
| 2000--2004 | 16,404 | 14,869 |
| 2005--2009 | 15,931 | 13,918 |
| 2010--2014 | 14,899 | 13,933 |
| 2015--2019 | 14,498 | 13,935 |
| 2020--2024 | 13,257 | 11,966 |
| 2025--2026* | 3,468 | 2,749 |
| **Total** | **133,110** | **112,678** |

*Table 4. Match counts by five-year period. \*2025--2026 data is partial (through March 14, 2026).*

### 4.2 Tournament Level Distribution

The ATP tournament hierarchy comprises Grand Slams (G), Masters 1000 (M), ATP 500, ATP 250, Davis Cup (D), Tour Finals (F), and Olympics (O). The WTA uses a broader set of tier designations that has evolved over time: Grand Slams (G), Premier Mandatory (PM), Premier 5 (P), Tiers 1--5 (T1--T5), Championships (CC), International (I), and several minor categories.

### 4.3 Surface Distribution

| Surface | ATP Matches | WTA Matches |
|---------|-------------|-------------|
| Hard | ~53% | ~55% |
| Clay | ~30% | ~28% |
| Grass | ~9% | ~8% |
| Carpet | ~7% | ~8% |
| Unknown | <1% | <1% |

*Table 5. Approximate surface distribution (full dataset).*

Note: Carpet courts were phased out of the ATP tour after 2009 and appear only in pre-2009 data. They remain in the dataset as they provide historical context for ELO computation and career statistics.

## 5. Data Quality

### 5.1 Missing Value Rates

Missing data is a significant concern, particularly for serve/return statistics in older matches and supplementary data sources.

| Column Group | ATP Missing Rate | WTA Missing Rate | Notes |
|-------------|-----------------|-----------------|-------|
| Core identity (IDs, names) | <0.1% | <0.1% | Required; rows with missing IDs are dropped |
| Serve stats (w_ace through l_bpFaced) | ~12% | ~18% | Higher in pre-1991 and 2025+ data |
| Minutes | ~15% | ~20% | Frequently missing for older events and minor tours |
| Rankings (rank, rank_points) | ~8% | ~12% | Missing for unranked players and very early data |
| Height | ~5% | ~15% | WTA height data is significantly sparser |
| Age | ~3% | ~5% | Missing when birth date is unavailable |
| Seed | ~75% | ~75% | Expected: most players in a draw are unseeded |

*Table 6. Approximate missing value rates by column group.*

> **2025--2026 data gap:** The supplementary data sources (TML-Database, web scraping) provide match results and basic metadata but not detailed serve/return statistics. This means all rolling-window features based on serve statistics (ace rate, first-serve percentage, break point rates, etc.) are computed from NaN-valued inputs for recent matches, effectively relying on the model's imputation to handle them. The features are not removed because historical data still provides training signal, but their predictive contribution is degraded for the 2026 validation set.

### 5.2 ATP vs. WTA Data Quality Comparison

The ATP dataset is generally more complete than WTA:

- **Serve statistics:** ATP has ~6% fewer missing values, reflecting earlier adoption of detailed match statistics tracking in men's tennis.
- **Height:** WTA has approximately 3x the missing rate for player height, a known gap in the Sackmann data.
- **Tournament levels:** WTA uses a more fragmented tier system (T1--T5, PM, P, CC, I, W, E vs. ATP's simpler G/M/500/250/D/F), which increases categorical diversity and can make tournament-level features noisier.
- **Player ID coverage:** A small number of WTA players (particularly new or minor-tour players) lack Sackmann IDs, resulting in empty ID fields. These matches are retained but produce NaN for all player-state features.

## 6. Known Issues & Caveats

### 6.1 The `match_num` Convention Change (2025)

**CRITICAL.** Prior to the 2025 data files, Sackmann's `match_num` field used ascending order from early rounds to finals (R128 matches had low match_num, the final had the highest). Starting with 2025 data files, this convention was reversed: the final has `match_num=1` and early-round matches have the highest values.

**Impact:** Any code that sorts matches by ascending `match_num` within a tournament will produce reverse-chronological order for 2025+ data, potentially causing temporal leakage in ELO computations and feature engineering.

**Mitigation:** The pipeline sorts by explicit round ordinals (R128=1, R64=2, ..., F=8) rather than `match_num`. The `match_num` field is retained only as a tiebreaker within the same round.

### 6.2 WTA Height Missingness

The WTA dataset has approximately 15% missing height values, compared to 5% for ATP. This primarily affects the `height_diff` feature. The model handles this through median imputation, but the effective signal from height in WTA predictions is weaker than for ATP.

### 6.3 Carpet Surface Phase-Out

Carpet courts were removed from the ATP and WTA tours after the 2009 season. The ~8,000 historical carpet-court matches remain in the dataset and contribute to overall ELO computation, but the "Carpet" surface ELO is effectively frozen for all active players, as no new carpet-court matches are being played. The feature is retained for completeness but has zero predictive value for modern predictions.

### 6.4 Player ID Matching in Supplementary Data

When converting supplementary data (TML, scraped) to Sackmann format, player names are mapped to Sackmann canonical IDs via a name-matching pipeline with aliases. A small number of players (4 ATP, 3 WTA at Indian Wells 2026) have no Sackmann ID due to being new or minor-tour players not present in the historical database. These matches retain empty ID fields, and the affected players have no ELO or feature history.

### 6.5 Walkover and Retirement Matches

Walkovers (W/O) and retirements (RET) are included in the dataset with the score field indicating the outcome type (e.g., "6-3 3-1 RET"). These matches update ELO and career statistics normally. For serve/return statistics, retirement matches typically have complete stats only for completed sets; the model's rolling-window features handle partial data through NaN propagation.

### 6.6 Round Robin Scoring

Round-robin events (tour finals, some team events) are included with `round=RR`. In these tournaments, a player may lose a match but still advance, which differs from standard elimination brackets. The model treats RR matches identically to elimination matches for ELO and feature purposes.

## 7. Validation Set

### 7.1 Construction

The validation set is defined by per-tour temporal cutoffs: all matches after the tour's cutoff date constitute the test set. This provides a genuine out-of-time evaluation where the model predicts future matches using only historical data.

Per-tour cutoff dates are used to balance the test set sizes so that the combined ROC-AUC metric weights both tours equally by sample count. The WTA cutoff is set earlier (2025-09-30 vs. ATP's 2025-12-31) because WTA has sparser early-2026 data; pulling the cutoff back to include 2025 Q4 tournaments yields a comparable test set size.

| Property | ATP | WTA |
|----------|-----|-----|
| Cutoff date | 2025-12-31 | 2025-09-30 |
| Test matches | 607 | 614 |
| Test tournaments | 17 | 16 |
| Period | Jan 1 -- Mar 14, 2026 | Oct 1, 2025 -- Mar 14, 2026 |

*Table 7. Validation set parameters.*

### 7.2 Deduplication

When validation CSV files (e.g., Indian Wells 2026 scraped data) are merged with the main Sackmann dataset, deduplication is performed on the `(tourney_id, match_num)` composite key. If a match appears in both sources, the Sackmann version is retained (as it typically has more complete data). The merge is logged with counts of new matches added and duplicates removed.

### 7.3 ATP Validation Tournaments (2026)

| Tournament | Matches | Level | Surface |
|------------|---------|-------|---------|
| Australian Open | 127 | G | Hard |
| Indian Wells Masters | 89 | M | Hard |
| Acapulco | 31 | 500 | Hard |
| Dubai | 31 | 500 | Hard |
| Rotterdam | 31 | 500 | Hard |
| Rio de Janeiro | 31 | 500 | Clay |
| Doha | 31 | 250 | Hard |
| Dallas | 31 | 250 | Hard |
| Brisbane | 31 | 250 | Hard |
| Adelaide | 27 | 250 | Hard |
| Hong Kong | 27 | 250 | Hard |
| Auckland | 27 | 250 | Hard |
| United Cup | 25 | D | Hard |
| Montpellier | 19 | 250 | Hard |
| Santiago | 19 | 250 | Clay |
| Delray Beach | 15 | 250 | Hard |
| Buenos Aires | 15 | 250 | Clay |

*Table 8. ATP 2026 tournaments in the validation set.*

### 7.4 WTA Validation Tournaments

The WTA test set spans two periods due to the earlier cutoff date (2025-09-30).

**2025 Q4 tournaments (Oct--Nov 2025):**

| Tournament | Matches | Level | Surface |
|------------|---------|-------|---------|
| Wuhan | 55 | PM | Hard |
| Pan Pacific Open | 31 | P | Hard |
| Jiujiang | 31 | I | Hard |
| Hong Kong | 31 | I | Hard |
| Guangzhou | 31 | I | Hard |
| Chennai | 31 | I | Hard |
| Tokyo | 27 | P | Hard |
| Ningbo | 27 | I | Hard |
| Riyadh Finals | 15 | CC | Hard |

**2026 tournaments (Jan--Mar 2026):**

| Tournament | Matches | Level | Surface |
|------------|---------|-------|---------|
| Indian Wells | 96 | PM | Hard |
| Dubai | 55 | P | Hard |
| Doha | 55 | P | Hard |
| Brisbane | 47 | I | Hard |
| Auckland | 31 | I | Hard |
| Hobart | 31 | I | Hard |
| Abu Dhabi | 27 | I | Hard |

*Table 9. WTA tournaments in the validation set (16 total). Match counts are approximate and subject to deduplication (effective total: ~614 matches).*

> **Note:** The validation set is entirely composed of hard-court events (with the exception of three ATP clay-court 250s). Clay, grass, and carpet surfaces are not represented in the current validation period, which runs through early March. Clay-court season and the grass-court swing will provide broader surface coverage as the 2026 season progresses.

---

*Generated by tennis-xgboost-autoresearch -- March 14, 2026 -- Version 1.1*
