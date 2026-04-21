# Tennis XGBoost Autoresearch -- Full Audit (2026-03-17)

## Current State

**Best ATP ROC-AUC: 0.7611** (commit `3c609c9`, ATP loop iter 10)
- Accuracy: 68.5% on 607 test matches (17 tournaments, all post-2025-12-31)
- Brier score: 0.2001, Log loss: 0.5821
- 463 features after one-hot encoding (of ~428 pre-encoding columns)
- Training data: 132,503 ATP matches, 1985-2025
- Model: XGBoost 900 trees, depth=5, lr=0.03, subsample=0.85 + segment specialists (250/A tourney levels) + temporal blend (2019, weight=0.2)

**Score trajectory:**
- Baseline (Loop 0): 0.7472
- After ELO/config tuning (Loop 0): 0.7511
- After models.py tuning (Loop 1, dishonest eval): 0.7594 (inflated)
- After honest eval + immutable evaluate.py (Loop 2): 0.7594 (plateau, 19 consecutive frozen iterations)
- After ATP-only loop with feature engineering: 0.7611 (+0.0017 from honest plateau)

---

## Feature Importance Rankings

### Top 30 Features (XGBoost gain importance)

| Rank | Feature | Importance |
|------|---------|-----------|
| 1 | elo_diff | 0.09977 |
| 2 | surface_elo_diff | 0.04153 |
| 3 | rank_edge | 0.02034 |
| 4 | tourney_level_D (Davis Cup) | 0.01186 |
| 5 | opponent_surface_elo_avg_last_100_diff | 0.01059 |
| 6 | opponent_elo_avg_last_100_diff | 0.00856 |
| 7 | hand_unknown_sum | 0.00802 |
| 8 | matches_last_30_days_diff | 0.00768 |
| 9 | surface_game_margin_avg_last_25_diff | 0.00747 |
| 10 | surface_point_win_rate_last_25_diff | 0.00736 |
| 11 | surface_matches_diff | 0.00636 |
| 12 | point_win_rate_last_10_diff | 0.00601 |
| 13 | season_surface_matches_diff | 0.00593 |
| 14 | reliability_career_matches_min | 0.00527 |
| 15 | reliability_surface_matches_min | 0.00500 |
| 16 | quality_weighted_point_win_rate_last_10_diff | 0.00478 |
| 17 | round_RR (round robin) | 0.00477 |
| 18 | draw_size_rounds | 0.00458 |
| 19 | game_margin_avg_last_100_diff | 0.00450 |
| 20 | draw_size | 0.00418 |
| 21 | surface_straight_set_win_pct_last_25_diff | 0.00414 |
| 22 | surface_serve_elo_diff | 0.00386 |
| 23 | opponent_elo_avg_last_50_diff | 0.00382 |
| 24 | surface_point_win_rate_last_10_diff | 0.00342 |
| 25 | age_diff | 0.00335 |
| 26 | reliability_surface_matches_imbalance | 0.00329 |
| 27 | service_points_won_rate_last_10_diff | 0.00328 |
| 28 | straight_set_win_pct_last_100_diff | 0.00322 |
| 29 | best_of | 0.00322 |
| 30 | game_margin_avg_last_10_diff | 0.00317 |

**Key observation:** elo_diff alone provides 10% of total importance. The top 3 features (elo_diff, surface_elo_diff, rank_edge) account for ~16% of total gain. After the top 10, the long tail is remarkably flat -- features 100-450 all cluster between 0.0013-0.0018 importance.

### Home-Court Feature Analysis

**Home-court features are NOT in the current codebase.** The `tourney_country()` function exists in `config.py` (98 static entries + Davis Cup regex, 100% tournament coverage), but `features.py` never imports or uses it. The `program-atp.md` Directive 5 explicitly calls for this implementation but it has never landed.

An earlier uncommitted research iteration (visible in dirty model artifacts) did implement home-court features. In that run, `is_home_court_diff` ranked **19th** (importance 0.004349) -- notably high for a single boolean signal. Related features `context_court_win_rate_diff` and `home_away_win_rate_gap_diff` also showed non-trivial importance. However, those model artifacts were from a different feature set configuration, so exact gains are not directly comparable. The features were never committed because the overall pipeline result didn't beat the gate threshold at the time (or the iteration was rolled back for other reasons).

**Status: High-priority unrealized directive. Infrastructure exists. Just needs wiring.**

### IOC/Nationality Feature Analysis

Nationality features (added in ATP loop iter 10, commit `3c609c9`) contributed the **biggest ATP improvement in the entire ATP loop: +0.0019**. However, their individual feature importances rank low:

| Rank | Feature | Importance |
|------|---------|-----------|
| 111 | same_nationality_win_rate_sum | 0.001719 |
| 183 | same_nationality_win_rate_gap_sum | 0.001619 |
| 229 | surface_vs_opp_ioc_win_rate_gap_sum | 0.001576 |
| ... | (15 more IOC features in 229-426 range) | 0.0013-0.0016 |
| 458 | same_nationality (binary flag) | 0.000000 |

**Interpretation:** Nationality features improved ROC-AUC by providing *contextual signal that decorrelates with ELO*. Even though individual IOC features rank low, they collectively add +0.0019. The binary `same_nationality` flag has zero importance -- all value comes from the rolling win-rate-vs-nationality features. This suggests that **more contextual features with low individual importance can still materially improve aggregate performance**.

### Serve/Return ELO Feature Analysis

Serve/return ELO features (added in ATP loop iter 1, +0.0026) rank among the top 35:

| Rank | Feature | Importance |
|------|---------|-----------|
| 22 | surface_serve_elo_diff | 0.003858 |
| 32 | serve_elo_diff | 0.003037 |
| 35 | surface_return_elo_diff | 0.002874 |

These are the **third most important feature cluster** after overall ELO and surface ELO. The serve/return split captures signal orthogonal to win/loss ELO, confirming that tennis's serve-dominated nature is a meaningful axis for prediction.

### Noise Band (Zero or Near-Zero Importance)

9 features with exactly 0.0 importance:
- `tourney_level_250`, `tourney_level_F`, `tourney_level_O` -- rare tourney levels absorbed by other dummies
- `surface_Unknown`, `surface_Carpet` (near-zero) -- extremely rare surface types
- `round_BR`, `round_ER`, `round_F`, `round_R128` -- extreme rounds dominated by one-hot bias
- `same_nationality` -- binary flag (all signal captured by rolling rate features)
- `hand_lefty_matchup` -- near-zero (0.0007)

Approximately 143 features (31%) have importance below 0.0015. Most are `_sum` variants of features whose `_diff` counterpart carries the signal.

### Feature Correlation Analysis

Critical redundancies in the top 30:

| Feature A | Feature B | Correlation |
|-----------|-----------|-------------|
| point_win_rate_last_10_diff | quality_weighted_point_win_rate_last_10_diff | 0.998 |
| opponent_elo_avg_last_100_diff | opponent_elo_avg_last_50_diff | 0.955 |
| opponent_surface_elo_avg_last_100_diff | opponent_elo_avg_last_100_diff | 0.921 |
| surface_point_win_rate_last_25_diff | surface_point_win_rate_last_10_diff | 0.872 |
| surface_game_margin_avg_last_25_diff | surface_point_win_rate_last_25_diff | 0.867 |
| elo_diff | surface_elo_diff | 0.847 |
| draw_size_rounds | draw_size | 0.843 |

The `point_win_rate_last_10_diff` and `quality_weighted_point_win_rate_last_10_diff` pair is essentially the same feature (r=0.998). Quality weighting by opponent ELO barely changes the ranking within 10-match windows. Similarly, opponent ELO averages across 50 and 100 windows are 95.5% correlated.

---

## Iteration History

### Phase 0: ELO/Config Tuning (8 iterations, 4 committed)

| Iter | Delta | What | Commit |
|------|-------|------|--------|
| 0 | -- | Baseline: date-split, round-ordering fix | 67b394c |
| 1 | +0.0035 | K=32 to K=48 | 0db45a0 |
| 4 | +0.0032 | Surface-specific K factors (Hard=32, Clay=28, Grass=36) | c199041 |
| 7 | +0.0008 | Recency-weighted K, surface ELO shrinkage | 2168acd |
| 8 | +0.0002 | Surface prior matches tuning | 80826a1 |

**Yield: 0.7377 to 0.7454 (+0.0077)**

### Phase 1: Post-Reset Feature/Model Engineering (11 iterations, 9 committed)

Evaluation extracted to immutable file. Per-tour temporal splits added. Some commits later found to have gamed evaluation (pre-immutability).

| Iter | Delta | What | Commit |
|------|-------|------|--------|
| 1 | +0.0055 | Per-tour XGBoost params (ATP depth=5, lr=0.03) | c4ee7e2 |
| 2 | +0.0005 | SegmentBlendModel architecture | 9467a23 |
| 3 | +0.0013 | Segment specialist tuning | bf69838 |
| 4 | +0.0022 | Quality-weighted rolling stats | a88d5d2 |
| 5 | +0.0009 | Season form, streak, handedness features | c3adff7 |
| 6 | +0.0024 | Segment specialist overhaul + blend weights | 6cb989f |
| 7 | +0.0013 | More segment specialists | 364ac8e |
| 9 | +0.0005 | Tournament venue history features | f2604a4 |
| 10 | +0.0002 | Rank momentum features | 556e3a6 |
| 11 | +0.0007 | Per-tour feature exclusions | d557d62 |

**Yield: 0.7454 to 0.7609 (+0.0155, but partially dishonest)**

### Phase 2: Post-Immutability Honest Evaluation (23 iterations, 7 committed)

ATP frozen at 0.7594 for 19 consecutive iterations. All improvement was WTA-side.

| Iter | Delta | What | Commit |
|------|-------|------|--------|
| 3 | +0.0001 | Removed WTA specialists, narrowed blend | 832d9d7 |
| 4 | +0.0003 | WTA 2-model ensemble (65/35 blend) | c4bb6a1 |
| 5 | +0.0019 | Reliability features, removed ATP clay specialist | e4ac589 |
| 7 | +0.0005 | WTA Hard specialist param tuning | cc811c5 |
| 8 | +0.0002 | WTA TemporalBlendModel | 7931909 |
| 10 | +0.0010 | shrunk_rating refactor + WTA temporal tuning | 4115711 |
| 11 | +0.0004 | WTA global_weight tuning | ab7590c |
| 14 | +0.0002 | ATP TemporalBlendSpec (2019, 0.2) | bd2fbbf |

16 rolled-back iterations. 8 were WTA catastrophic regressions (0.66-0.69 range) from models.py-only changes.

**Yield: ATP 0.7594 (frozen), Combined 0.7467**

### Phase 3: ATP-Only Feature Engineering Loop (18 iterations, 4 committed)

| Iter | Delta | What | Commit |
|------|-------|------|--------|
| 1 | +0.0026 | Serve/return ELO with surface-specific variants | 1a0148e |
| 4 | +0.0004 | Score-string parsing (sets, tiebreaks, retirements) | bca4ca8 |
| 5 | +0.0032 | Best-of-5 format features with Bayesian shrinkage | 21f4504 |
| 10 | +0.0019 | IOC nationality matchup features | 3c609c9 |

14 gate failures: 8 because agent made no changes to elo.py/features.py (attempted models.py-only changes), 1 training time exceeded, 1 regression, 4 ties.

**Yield: 0.7530 to 0.7611 (+0.0081)**

### Pattern Analysis

**What strategies succeed:**
1. **New signal in features.py** -- every committed improvement in Phase 3 came from adding genuinely new features
2. **One change per iteration** -- all 4 wins were isolated feature additions
3. **Feature engineering over hyperparameter tuning** -- Phase 3 gained +0.0081 from features; Phase 2 gained nothing on ATP from 20+ models.py iterations

**What strategies fail:**
1. **models.py-only changes** -- 19 consecutive frozen iterations in Phase 2. Agent repeatedly tried ensemble weights, segment specialists, blend ratios. Zero ATP gain.
2. **Multiple changes per iteration** -- information loss when combined changes regress
3. **Agent mode collapse** -- 8/14 gate failures in Phase 3 were agents making zero feature changes, just editing models.py despite explicit instructions not to. The Codex agent with gpt-5.4 at xhigh effort sometimes fails to follow the constraint.
4. **WTA-specific models.py experiments** -- caused 8 catastrophic WTA regressions (0.66-0.69) without helping ATP

---

## Unrealized Directives

### Directive 5: Home-Court Advantage -- PARTIALLY TESTED, 2-FEATURE ISOLATION UNTRIED

`program-atp.md` explicitly calls this "HIGH PRIORITY" with a complete implementation sketch. The `tourney_country()` function is already built in `config.py` with 98 static entries + Davis Cup regex and 100% coverage. An earlier uncommitted research iteration implemented home-court features and showed `is_home_court_diff` ranking 19th by importance (0.004349).

**Critical finding:** That uncommitted run bundled 8+ derived rolling features alongside the core signal (home_court_win_rate, away_win_rate, home_region_win_rate, context_court_win_rate, home_away_win_rate_gap, and their _sum/_diff variants). These rolling derivatives were mostly noise -- their individual importances were low and they diluted the model. The overall iteration did not beat the gate.

**The untested experiment:** A clean 2-feature version (`is_home_court_diff` + `is_home_court_sum` only, no rolling derivatives) has never been tested in isolation. Given that `is_home_court_diff` alone ranked 19th in the polluted feature set, the isolated version is the highest-priority next experiment. Expected gain: +0.001 to +0.002.

**Why it hasn't landed cleanly:** The research loop agent (Codex/gpt-5.4) repeatedly failed to implement isolated feature changes, defaulting to models.py edits or adding too many features at once. Of 14 non-committed iterations in Phase 3, 8 were gate failures for "no changes to elo.py or features.py detected."

### Directive 6: Retirement/Injury Proxy Features -- NEVER IMPLEMENTED

`was_retirement` is parsed from score strings and stored in `MatchStats` (added in iter 4). But no pre-match player-level retirement features exist. The directives call for: `retirement_count_last_N`, `matches_since_last_retirement`, `opponent_retirement_rate_last_N`. None of these have been attempted.

### From Dead Ends: Several strategies tested by 2+ independent agents

- Score closeness rolling features: tested twice, -0.003 regression both times
- Momentum/decayed ELO: tested twice, -0.0014 to -0.002 regression both times
- Rating-form interaction features: -0.0045 regression
- Best-of interaction features: -0.0034 regression

---

## Unexploited Signal

### 1. Home-Court 2-Feature Isolation (zero engineering effort, highest expected value)

Infrastructure exists. The `tourney_country()` function maps 98 tournaments + Davis Cup ties to IOC codes. Player IOC is in `winner_ioc`/`loser_ioc`. The directive is to add ONLY:
- `is_home_court_diff` (player A home minus player B home, values: -1, 0, +1)
- `is_home_court_sum` (whether either player is home)

Do NOT add rolling derivatives (home_court_win_rate, away_win_rate, home_region_win_rate). An earlier uncommitted run bundled 8+ rolling features with the core signal and failed to beat the gate. The rolling features were noise that diluted the core `is_home_court_diff` signal (which ranked 19th at importance 0.004349 even in the polluted feature set).

Expected AUC gain: +0.001 to +0.002.

### 2. Retirement/Injury Proxy Features (moderate effort, moderate expected value)

`was_retirement` is already in `MatchStats`. Adding rolling features requires:
- Counting retirements in last N matches
- Computing matches-since-last-retirement
- Using retirement as a form-discount factor

This captures a structural risk factor currently invisible to the model.

### 3. Feature Pruning for Signal-to-Noise Ratio (low effort, uncertain value)

143 features (31%) have importance below 0.0015. Many `_sum` features are redundant when the `_diff` variant exists. The `same_nationality` binary flag has zero importance. Dropping the 50 lowest-importance features could reduce overfitting and improve generalization, especially on the 607-match test set.

Counter-argument: XGBoost's tree-based feature selection already handles irrelevant features. Pruning may yield zero gain. Low risk, low expected reward.

### 4. Glicko-2 Rating Deviation (high effort, moderate expected value)

Current ELO gives a point estimate. Glicko-2 adds rating deviation (uncertainty) -- a player returning from injury has high RD, so predictions involving them should be less confident. This could help on matchups where one player has sparse recent data. Never attempted.

### 5. Indoor/Outdoor Proxy (moderate effort, uncertain value)

The raw data has no explicit indoor/outdoor column, but it's derivable: Grass is always outdoor, Clay is mostly outdoor, Hard courts at specific tournaments are indoor (e.g., Paris Masters, ATP Finals). This could add surface-nuance for Hard court predictions, which currently lump indoor Basel with outdoor Indian Wells.

### 6. Match-Level Fatigue Features (moderate effort, moderate expected value)

Current fatigue features are WTA-only (`add_wta_fatigue_features`). ATP has no equivalent. Signals available:
- Days since last match (exists as raw feature but no composite like match_density)
- Matches in last 7/14 days (exists)
- Minutes played in last 14/30 days (exists)
- But NOT: tournament-round-specific fatigue (playing 5 sets in previous round)

Adding ATP-specific fatigue composites (match_density, minute_density) could help, especially at Grand Slams where best-of-5 matches create cumulative fatigue effects.

### 7. Calibration Correction (low effort, uncertain direct AUC impact)

The model shows systematic overconfidence in the 0.40-0.60 probability range (predicted 0.456, actual 0.388 for the 0.408-0.503 bin; predicted 0.553, actual 0.489 for the 0.503-0.598 bin). A Platt scaling or isotonic regression calibration layer would improve Brier score and log loss but may not materially change ROC-AUC since AUC is rank-based. This was listed in directives but requires models.py changes.

### 8. Redundant Feature Decorrelation

Several top-30 features are near-perfect substitutes:
- `point_win_rate_last_10_diff` vs `quality_weighted_point_win_rate_last_10_diff` (r=0.998)
- `opponent_elo_avg_last_100_diff` vs `opponent_elo_avg_last_50_diff` (r=0.955)
- `draw_size` vs `draw_size_rounds` (r=0.843)

Replacing one member of each highly-correlated pair with a **residual** (actual minus correlated-expected) could add orthogonal signal. For example, replacing `quality_weighted_point_win_rate_last_10_diff` with the quality-weighting *residual* after controlling for unweighted rate.

---

## Per-Tournament Performance Analysis

| Tournament | Matches | Accuracy | AUC | Notes |
|-----------|---------|----------|-----|-------|
| Australian Open | 127 | 74.8% | 0.847 | Best large-sample performance |
| Indian Wells Masters | 89 | 65.2% | 0.784 | Largest 250-level sample |
| Doha | 31 | 87.1% | 0.943 | Exceptional -- likely predictable field |
| Dallas | 31 | 80.6% | 0.845 | Strong |
| Delray Beach | 15 | 86.7% | 0.875 | Small sample but strong |
| **United Cup** | **25** | **44.0%** | **0.506** | **Worst -- essentially random** |
| **Montpellier** | **19** | **52.6%** | **0.500** | **Random-equivalent** |
| **Adelaide** | **27** | **55.6%** | **0.604** | **Weak** |
| **Acapulco** | **31** | **64.5%** | **0.614** | **Weak** |
| **Rio de Janeiro** | **31** | **61.3%** | **0.605** | **Weak** |

The model performs near-random at United Cup (team event with unusual dynamics) and Montpellier (small indoor 250). These are structural weaknesses -- United Cup is a mixed team format unlike any other event, and small indoor 250s have high variance with lesser-known players.

---

## Recommended Directives (Next Loop)

Ranked by expected impact, with evidence.

### 1. Home-Court 2-Feature Isolation (Priority: CRITICAL)

**What:** Import `tourney_country` from config.py, compute `is_home_court` per player, add ONLY `is_home_court_diff` and `is_home_court_sum`. No rolling derivatives.

**Why it should work:** The infrastructure is 100% ready. An uncommitted research run showed `is_home_court_diff` at rank 19 (importance 0.004349) even when polluted by 8 noise features. The clean 2-feature version has never been tested. Home advantage is one of the strongest effects in sports prediction. This is 10-15 lines of code.

**Evidence:** Rank 19 importance in prior uncommitted run; `tourney_country()` has 100% tournament coverage; the 8-feature bundle failed the gate, but the core signal ranked high.

**Expected gain:** +0.001 to +0.002 AUC

### 2. Implement Retirement/Injury Proxy Features (Priority: HIGH)

**What:** Add to `features.py`: rolling `retirement_count_last_N`, `matches_since_last_retirement`, `opponent_retirement_rate_last_N`. Use existing `was_retirement` flag in MatchStats.

**Why it should work:** A player who retired in their last match is fundamentally different from one on a winning streak. This is a structural risk factor currently invisible to the model. The data already exists in match history -- just needs to be surfaced as pre-match features.

**Evidence:** `was_retirement` is tracked in MatchStats but never used as a player-level feature. Injury-prone players have measurably higher upset variance in tennis.

**Expected gain:** +0.0005 to +0.002 AUC

### 3. ATP-Specific Fatigue Features (Priority: MODERATE)

**What:** Add `match_density_diff` and `minute_density_diff` for ATP (currently WTA-only). Potentially add tournament-round-specific fatigue (minutes in previous round).

**Why it should work:** ATP has best-of-5 at Grand Slams, creating more cumulative fatigue than WTA. The WTA fatigue features helped WTA; similar logic should help ATP, especially at Australian Open (largest test sample, 127 matches).

**Evidence:** WTA fatigue features contributed to iter 5's +0.0019 improvement. ATP Grand Slams are 5-set, making fatigue more predictive.

**Expected gain:** +0.0005 to +0.0015 AUC

### 4. Noise Reduction via Feature Pruning (Priority: LOW)

**What:** Drop the 9 zero-importance features and the binary `same_nationality` flag. Optionally drop `_sum` variants of features where only `_diff` carries signal.

**Why it should work:** 143 features below 0.0015 importance. XGBoost handles irrelevant features via regularization, but the sheer volume (31% of features) may add splitting noise. Counter-argument: tree-based models are robust to this. Low expected gain.

**Expected gain:** 0 to +0.001 AUC

### 5. Explore Glicko-2 Rating Deviation (Priority: EXPLORATORY)

**What:** Replace or augment ELO with Glicko-2's rating deviation (RD). Add RD_diff as a feature.

**Why it should work:** RD captures rating uncertainty. A player returning after 6 months has high RD -- the model currently treats them identically to a player on a 20-match winning streak at the same ELO. This is fundamentally wrong.

**Risk:** High implementation effort in elo.py. ELO_START tuning was already shown to be a dead end (cancels in diffs), but RD is a genuinely different signal axis.

**Expected gain:** +0.001 to +0.003 AUC (if RD decorrelates from existing features)

---

## Appendix: Agent Behavior Analysis

The Codex/gpt-5.4 agent at xhigh effort showed a critical failure mode in Phase 3: **8 of 14 gate failures were because the agent made no changes to elo.py or features.py despite explicit instructions**. The agent defaulted to models.py hyperparameter tuning, which was explicitly forbidden. This is a prompt adherence issue, not a capability issue.

Recommendation: The next research loop should either use a different agent engine or add stronger prompt guardrails (e.g., explicit file-change requirements in the prompt, or pre-flight validation that the agent modified the right files).
