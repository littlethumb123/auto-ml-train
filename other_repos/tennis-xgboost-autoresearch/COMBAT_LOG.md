# Combat Log -- Tennis XGBoost Autoresearch

What was tried, what worked, what failed. Read this before every iteration.

## Three Phases of History

**Loop 0** (iters 1-8): ELO/config tuning. K-factor adjustments, surface K-factors. Ended at COMBINED 0.7454.
**Reset**: Evaluation extracted to immutable evaluate.py. Per-tour temporal splits added. Honest peak recalibrated.
**Loop 1** (iters 1-11): Post-reset. Gaming-proof evaluation. Feature engineering + model architecture. Ended at COMBINED 0.7609 (dishonest -- pre-immutability commits were gaming).
**Loop 2** (iters 3-14): Post-immutability. Honest evaluation. models.py tuning only. ATP frozen at 0.7594 from iter 5 onward. Ended at COMBINED 0.7467.
**ATP-Only Loop** (iter 1+): feature-engineering against the 2026 ATP date split after the IOC nationality win. Current best ATP ROC-AUC: 0.7611147327.

---

## Committed (worked)

### ATP-Only Loop -- 2026 ATP Validation

| Iter | Change | ATP ROC-AUC | Delta vs 0.7611 | Status | Notes |
|------|--------|-------------|-----------------|--------|-------|
| 1 | elo.py + features.py: retirement durability proxies (`retirement_count_last_25`, `matches_since_last_retirement`) | 0.7611147327 | +0.0000147 | kept | Role-aware loser retirement flag only; +4 columns after diff/sum; ATP feature count 421 |

### ATP-Only Loop -- Rolled Back

| Iter | Change | ATP ROC-AUC | Delta vs 0.7611 | Status | Notes |
|------|--------|-------------|-----------------|--------|-------|
| 2 | features.py: ATP fatigue composites (`match_density_14`, `minute_density_14`) | 0.7600717080 | -0.0010430 | reverted | Rest-adjusted 14-day workload densities added as +4 diff/sum columns; gate runtime 404s, ATP feature count 421 |
| 3 | features.py: recent H2H enrichment (`recent_h2h_diff`, `recent_h2h_total`, `h2h_recency_ratio`) | 0.7590938722 | -0.0020209 | reverted | 3-year hard cutoff on matchup history; +3 row features (417 -> 420 ATP feature count); gate runtime 411s |
| 4 | features.py: surface-transition context (`surface_transition`, `current_surface_streak_matches`, `current_surface_streak_win_rate`) | 0.7571164711 | -0.0039983 | reverted | Previous-surface switch flag plus current-surface streak length/win rate; +6 diff/sum columns (417 -> 423 ATP feature count); gate runtime 405s |
| 5 | features.py: rank momentum enhancement (`rank_rising`, `rank_volatility_91_days`) | 0.7588222512 | -0.0022925 | reverted | Added 91-day binary direction plus rank-range volatility as +4 diff/sum columns (417 -> 421 ATP feature count); gate runtime 411s |
| 6 | elo.py + features.py: ATP upset propensity (`upset_rate_last_20_diff`, `loss_to_lower_rate_last_20_diff`) | 0.7564754455 | -0.0046393 | reverted | Ranking-indexed last-20 large-gap upset/favorite-loss rates stored in match history; +2 diff-only columns (417 -> 419 ATP feature count); gate runtime 410s |
| 7 | config.py + features.py: zero-importance pruning (`same_nationality` drop + categorical level masking) | 0.7558670143 | -0.0052477 | reverted | Dropped raw `same_nationality`; masked `surface_Unknown`, `tourney_level_F/O`, and `round_R128/F/ER/BR` before one-hot; `tourney_level_250` preserved because frozen ATP specialist still keys on raw `250`; gate runtime 414s |
| 8 | elo.py + features.py: event-aware ATP fatigue composites (`match_density`, `minute_density`) | 0.7566818774 | -0.0044329 | reverted | 14-day inverse-sqrt workload densities with same-tournament round-gap fallback; +4 diff/sum columns (417 -> 421 ATP feature count); gate runtime 408s |
| 9 | features.py: gated surface-transition adaptation (`surface_transition_adaptation_matches`, `surface_transition_adaptation_pve`) | 0.7606040852 | -0.0005106 | reverted | Historical first-two-matches-after-switch sample on the current surface, surfaced only when the upcoming match was also in that transition window; gate runtime 404s, ATP feature count 421 |
| 10 | features.py: soft-recency H2H enrichment (`recent_h2h_diff`, `recent_h2h_total`, `h2h_recency_ratio`) | 0.7592677097 | -0.0018470 | reverted | Exponential 1095-day half-life over lifetime H2H wins instead of a hard cutoff; +3 row features (417 -> 420 ATP feature count); gate runtime 405s |

**Iter 2 analysis:** The hypothesis was that ATP validation would benefit from a compact fatigue signal that combines recent workload with recovery time, using existing strict pre-match state only. The implementation touched `src/tennis_predict/features.py` and derived `match_density_14` plus `minute_density_14` from `matches_last_14_days`, `minutes_last_14_days`, and `days_since_last_match`, with the usual `+3` rest-day stabilizer used in prior WTA work.

The result regressed to **`ATP_ROC_AUC=0.760071707953064`**, missing the live `0.7611` gate by about `0.00104`. The likely reason is that this formulation was too derivative of signal the ATP model already had: raw 14-day match counts, raw 14-day minutes, and days-since-last-match were already available as separate features, so the new composites mostly re-parameterized existing workload information instead of adding a new axis. In ATP specifically, that compression may have been worse than neutral because the model already sees best-of-5 history, score-derived match length proxies, and nationality/context features; folding counts and rest into a single ratio probably threw away useful separability between "played a lot" and "played recently."

**Implication for future attempts:** simple rest-adjusted density ratios built directly from existing ATP activity features are not enough. If fatigue gets revisited, it should be through a genuinely new state variable rather than a transformation of already-exposed counts, for example tournament-round carryover, previous-match minutes on the same event path, or a surface-transition-specific recovery signal. Do not retry the bare `matches_last_14_days / (days_since_last_match + 3)` and `minutes_last_14_days / (days_since_last_match + 3)` formulation.

**Iter 3 analysis:** The hypothesis was that ATP validation would benefit from separating fresh matchup familiarity from stale lifetime H2H counts. The implementation changed only `src/tennis_predict/features.py`, added a 1095-day recent-H2H store alongside the existing lifetime `head_to_head` dict, and surfaced three new row-level features: `recent_h2h_diff`, `recent_h2h_total`, and `h2h_recency_ratio`. Feature count moved from **417** to **420**.

The result regressed to **`ATP_ROC_AUC=0.7590938722294654`**, about **`0.00202`** below the live **`0.7611147327`** gate. The most likely reason is that the new features were too sparse and too collinear at the same time. For the large share of matches with no prior meetings, the recent-H2H features add no information. For the smaller set of repeat matchups, the model already had `h2h_diff`, `h2h_total`, `surface_h2h_diff`, and strong global skill signals from ELO, surface ELO, serve/return ELO, and rank features. The hard 3-year cutoff probably made things worse by discarding older but still meaningful style-matchup information, while `h2h_recency_ratio` mostly re-expressed existing H2H volume in a noisier form.

**Implication for future attempts:** do not retry simple recent-H2H counts or `recent / lifetime` ratios with a fixed 1095-day window. This formulation appears to add feature noise without opening a new signal axis. If H2H is revisited at all, it should be treated as a lower-priority area and would need a materially different structure, not a hard-window clone of the existing lifetime H2H features.

**Iter 4 analysis:** The hypothesis was that ATP validation would benefit from explicitly modeling surface carryover: whether a player was switching surfaces before the match, how long they had been on the current surface, and whether that immediate surface run had been successful. The implementation changed only `src/tennis_predict/features.py`, added a `surface_transition_snapshot()` helper over pre-match history, and surfaced three player-level features: `surface_transition`, `current_surface_streak_matches`, and `current_surface_streak_win_rate`. Because the pipeline emits both `_diff` and `_sum`, ATP feature count rose from **417** to **423**.

The result regressed sharply to **`ATP_ROC_AUC=0.757116471099522`**, about **`0.00400`** below the live **`0.7611147327`** gate and even below the pre-nationality plateau. The likely reason is that this was not genuinely new signal for the ATP model; it was a noisy restatement of context the model already sees through `surface_elo`, shrunk surface ELO, surface rolling form windows, `surface_matches`, `season_surface_share`, and `days_since_last_surface_match`. The binary switch flag also likely behaved more like a season-calendar marker than a player-skill marker, while the current-surface streak features were sparse and unstable at exactly the moments where they mattered most: players entering a new swing after zero or one match on the surface. In effect, the added columns appear to have encouraged the model to overfit short-run scheduling patterns rather than improving discrimination about relative strength.

**Implication for future attempts:** treat simple surface-switch/streak summaries as a dead end. Do not retry `surface_transition` plus immediate current-surface streak length/win-rate features in this form. If surface-transition signal is revisited at all, it should be through a materially different construction, likely tied to opponent-adjusted adaptation or a stronger event-level context, not bare previous-surface continuity counts.

**Iter 5 analysis:** The hypothesis was that ATP validation would benefit from a compact measure of ranking trajectory uncertainty beyond the existing raw rank deltas. The implementation changed only `src/tennis_predict/features.py`, extended `RankingsIndex.snapshot()` with two new player-level features, `rank_rising` and `rank_volatility_91_days`, and let the normal player-A/player-B diff/sum expansion surface them as **+4 columns** overall. `rank_rising` was a binary flag derived from the existing 91-day rank change, while `rank_volatility_91_days` measured the max-minus-min ranking range over the prior 91 days. ATP feature count rose from **417** to **421**.

The result regressed to **`ATP_ROC_AUC=0.7588222511951326`**, about **`0.00229`** below the live **`0.7611147327`** gate, with gate runtime at **411s**. The likely reason is that this change mostly repackaged information the ATP model already had instead of opening a new signal axis. `rank_rising` is just a thresholded version of the existing `rank_change_91_days` feature family, and XGBoost can already learn sign-based splits directly from those numeric deltas. `rank_volatility_91_days` was more novel, but in practice it appears to have been too noisy and too indirect: the distribution was very wide, with heavy tails from players making extreme ranking jumps, and it also introduced additional missingness for players with sparse ranking history. That kind of volatility is not purely “uncertainty”; it mixes breakouts, comebacks, protected-ranking cases, sparse data, and tour-level churn into one coarse number. The model did use the new features a little (`rank_rising_diff` importance ~`0.00168`, `rank_volatility_91_days_sum` ~`0.00152`), but that looks like mid-tail split consumption rather than genuinely helpful discrimination.

**Implication for future attempts:** do not retry simple rank-direction binaries or raw 91-day rank-range volatility. The ATP stack already captures most usable rank momentum through the existing 28/91-day rank and points deltas, plus ELO/activity/context features. If rankings are revisited, it should be through a materially different construction, such as opponent-conditioned ranking over/under-performance or a cleaner uncertainty signal that does not collapse breakouts and sparse-history cases into one broad volatility bucket.

**Iter 6 analysis:** The hypothesis was that ATP validation would benefit from a player-specific upset profile that was orthogonal to raw strength: some players consistently overperform when stepping up in class, while others protect ranking edges poorly against weaker opponents. The implementation changed `src/tennis_predict/elo.py` and `src/tennis_predict/features.py`. It added a `rank_gap` field to per-match history, populated that gap from the ranking index rather than the sparse raw validation ranks, and exposed two **diff-only** pre-match features: `upset_rate_last_20_diff` and `loss_to_lower_rate_last_20_diff`. Each player rate looked only at the last 20 prior matches with a rank gap of at least 20 places, shrunk toward `0.5` with a 5-match prior to avoid single-match extremes. ATP feature count rose from **417** to **419**.

The result regressed sharply to **`ATP_ROC_AUC=0.7564754454584964`**, about **`0.00464`** below the live **`0.7611147327`** gate, even though accuracy ticked up to **`0.68699`**. The feature-importance dump shows the model did consume the new signal (`upset_rate_last_20_diff` importance **`0.00168`**, `loss_to_lower_rate_last_20_diff` **`0.00143`**), so this was not a pure no-op. The more plausible failure mode is that the features were semantically noisy despite being dense. Large-gap rank outcomes are not a clean “clutch” trait; they mix genuine style/mentality effects with ranking lag, protected-ranking cases, injury returns, post-break declines, and cross-level schedule effects. In other words, the feature family was measuring a blend of player quality drift and tour-context noise that the model already captures more cleanly through ELO, rank edge, opponent-ELO rolling averages, and performance-vs-expectation features. The shrink-to-`0.5` design also likely flattened the tails enough that the residual variation looked like weak, noisy disagreement with stronger existing skill signals. That is consistent with the AUC drop: the model found splits on the new columns, but those splits worsened ordering even while a few 0.5-threshold classifications improved.

**Implication for future attempts:** treat simple last-20 upset/favorite-loss rates based on raw rank-gap buckets as a dead end. Do not retry `upset_rate_last_20_diff` and `loss_to_lower_rate_last_20_diff` in this form, including ranking-indexed history with a fixed 20-place threshold. If “over/under-performance versus rank” is revisited, it should be through a materially cleaner construction, likely opponent-conditioned residuals or event-level context, not bucketed upset propensity counts.

**Iter 7 analysis:** The hypothesis was that ATP validation would benefit from removing known dead weight after the iter-10 SHAP audit, specifically the zero-importance `same_nationality` flag and the categorical levels that had contributed no gain in the global model. The implementation changed `src/tennis_predict/config.py` and `src/tennis_predict/features.py`. It dropped the raw `same_nationality` feature outright and masked the zero-importance categorical levels (`surface_Unknown`, `tourney_level_F`, `tourney_level_O`, `round_R128`, `round_F`, `round_ER`, `round_BR`) before the frozen preprocessing stack one-hot encoded them. `tourney_level_250` was intentionally **not** masked even though it was zero-importance in the audit, because the frozen ATP stack still routes raw `tourney_level == "250"` rows into a validated segment specialist; removing that raw level would have turned the experiment into a model-routing change rather than a pure pruning pass.

The result regressed to **`ATP_ROC_AUC=0.7558670143415908`**, about **`0.00525`** below the live **`0.7611147327`** gate, with gate runtime at **414s** and reported ATP feature count **416**. The post-run importance dump makes the failure mode fairly clear: this did **not** behave like a clean one-hot-column deletion. Because `models.py` is frozen, the only available implementation path for categorical pruning inside `features.py` was to mask the pruned levels to missing values and let the downstream categorical imputer fill them. In practice that means finals, R128 matches, odd rounds, and low-value tourney-level buckets were not becoming “all-zero / dropped-column” representations; they were being reassigned to the column mode before one-hot encoding. That is a materially different transformation. It collapses semantically distinct rows into the dominant category while leaving the numeric round/tournament context features to disagree with the imputed categorical label. The magnitude of the regression suggests that this mismatch was much more harmful than the small regularization win from deleting a few dead columns. The fact that the new run simply produced fresh zero-importance tails (`hand_same_known`, `round_R64`) reinforces that the bottleneck is not raw feature-count cleanup by itself; under the current stack, the model can just reshuffle importance mass across interchangeable low-value columns.

**Implication for future attempts:** do not retry zero-importance categorical pruning via pre-feature masking or missing-value coercion. Under the frozen preprocessing stack, that approach is not equivalent to dropping one-hot columns and is actively harmful. If Directive 15 is revisited at all, it needs a materially different implementation angle: true post-encoding column removal or an explicit encoder-category specification that preserves raw routing columns while removing selected global-model dummies. Without that capability, D15 should be treated as effectively blocked by the current `models.py` constraints, and future ATP iterations should move on to untried directives instead of repeating feature-frame masking variants.

**Iter 8 analysis:** The hypothesis was that D6 could still work if ATP fatigue composites stopped collapsing existing 14-day totals and instead injected the missing same-event carryover path. The implementation changed `src/tennis_predict/elo.py` and `src/tennis_predict/features.py`. It extended `MatchStats` with `tourney_id` and `round_order`, then added player-level `match_density` and `minute_density` features built from a **14-day inverse-sqrt workload kernel**. For ordinary prior matches the lag used true calendar-day distance. For prior matches inside the **same tournament**, where the Sackmann `match_date` field is the tournament start date and therefore misses intra-event spacing, the lag fell back to `current_round_order - prior_round_order` so current-event carryover would finally enter the ATP fatigue path.

The result regressed to **`ATP_ROC_AUC=0.7566818774445893`**, about **`0.00443`** below the live **`0.7611147327`** gate, with gate runtime **408s** and ATP feature count **421**. This was not a no-op. The feature-importance dump shows the model did consume the new columns: `minute_density_sum` at **`0.001536`**, `match_density_diff` at **`0.001528`**, `minute_density_diff` at **`0.001425`**, and `match_density_sum` at **`0.001378`**. That points to a semantic failure rather than an implementation bug.

The likely reason is that the round-gap fallback was too confounded to behave like true fatigue. Inside a tournament, cumulative workload and advancing deeper in the draw are tightly coupled. Stronger players are exactly the ones who accumulate same-event density because they keep winning. The frozen ATP stack already sees that context through `round_order`, `round_stage_progress`, `tourney_matches`, best-of-5 history, score-derived shape, and the regular recent-activity windows. By converting round progression into pseudo-rest days, the new composites mixed three effects into one number: actual physical burden, match advancement, and latent player strength. The model then spent gain on mid-tail splits over a variable that sometimes penalized stronger players for making deep runs and sometimes double-counted round context. Because the source data still lacks real per-match intra-event dates, this construction could not distinguish “played two long matches on consecutive days” from “played a routine path on the tournament’s normal cadence.”

**Implication for future attempts:** treat event-aware fatigue densities that infer same-tournament rest from round distance as exhausted. Do not retry `match_density` / `minute_density` variants that backfill intra-event lag from `round_order` under the current data. If fatigue is revisited, it needs a materially different source of timing information or a narrower burden signal that does not proxy draw progression, such as real per-match dates, validated previous-match carryover from a richer schedule feed, or a non-round-based recovery proxy.

**Directive 11 scheduling-density revisit analysis (2026-03-17):** The hypothesis was that ATP validation still lacked a genuinely short-horizon schedule-load view beyond the existing 14/30-day activity windows, and that adding a 7-day density slice plus recent match-duration burden could capture congested tournament weeks without repeating the earlier rest-adjusted or round-gap fatigue constructions. The implementation changed only `src/tennis_predict/features.py`. It added `scheduling_density_snapshot()` and surfaced three player-level features: `match_density_7d`, `minute_density_7d`, and `minutes_per_match_last_10`. Because the feature frame emits `_diff` and `_sum`, that produced **+6 columns** overall, and the evaluated ATP feature frame finished at **423 features**. `pytest` passed and gate runtime was **427s**.

The result regressed to **`ATP_ROC_AUC=0.7564754454584963`**, about **`0.00464`** below the live **`0.7611147327`** gate, so the change was reverted. The most likely reason is that this D11 pass was still too redundant with the current feature set even though it avoided the exact earlier fatigue formulas. `minutes_per_match_last_10` was effectively a rename of the already-existing `minutes_avg_last_10` rolling feature, so it added no new axis at all. `minute_density_7d` was new in window length, but semantically it sat very close to the combination of `minutes_last_14_days`, `matches_last_14_days`, `days_since_last_match`, and the existing rolling minutes averages. That leaves `match_density_7d` as the only materially new slice, and on ATP data that likely confounds workload with match advancement: players accumulate dense 7-day schedules precisely when they are winning and going deep in draws. The added columns therefore mixed fatigue, current form, and latent strength in a way the frozen stack already models more cleanly through ELO, round context, recent activity, and rolling match-shape features.

**Implication for future attempts:** treat simple scheduling-density additions built from the current `history` minutes/counts as exhausted. Do not retry 7-day match/minute density features or renamed duration averages under this feature frame. If Directive 11 is revisited at all, it should use schedule information that is not already present in the existing windows, such as real intra-event day gaps from richer match-date granularity or a narrowly defined turnaround-burden signal that does not duplicate `minutes_avg_last_10` and recent-activity totals.

**Directive 10 surface-transition performance revisit analysis (2026-03-17):** The hypothesis was that the original D10 failure came from exposing generic schedule context (`surface_transition`, current streak length, current streak win rate) instead of the actual player trait that should matter: how well a player historically adapts in the first couple of matches after moving onto a new surface. The implementation changed only `src/tennis_predict/features.py`. It added a transition-aware snapshot that scanned pre-match history for prior matches on the current surface that occurred within the **first two matches of a new surface run after a genuine switch**, then surfaced two player-level features: `surface_transition_adaptation_matches` and `surface_transition_adaptation_pve`. To avoid repeating the dead-end global switch flag, those features were only activated when the upcoming match itself was also in that first-two-match transition window; otherwise they were set to neutral zero values. `pytest` passed, gate runtime was **404s**, and the evaluated ATP feature frame finished at **421 features**.

The result regressed to **`ATP_ROC_AUC=0.7606040851803564`**, about **`0.00051`** below the live **`0.7611147327`** gate, so the change was reverted. This was not a no-op. The feature-importance dump shows the model did spend gain on the new columns: `surface_transition_adaptation_pve_sum` at **`0.001676`**, `surface_transition_adaptation_pve_diff` at **`0.001491`**, `surface_transition_adaptation_matches_diff` at **`0.001430`**, and `surface_transition_adaptation_matches_sum` at **`0.001386`**. That points to semantic weakness rather than wiring failure.

The likely reason it still lost is that even this gated version remained too confounded by calendar structure and sparse history. The historical “first two matches after a switch” subset does isolate adaptation better than the old streak features, but it is still heavily shaped by where surface changes happen on the ATP calendar: opening rounds of swing changes, tune-up events, and tour-tier mix. Good players often enter new surface stretches with easier early opponents, while lower-tier or returning players can generate the same pattern for very different reasons. That makes `surface_transition_adaptation_pve` a blend of true adaptation skill, draw strength, event selection, and the player’s career phase rather than a clean transition trait. The neutral-zero gating also means the feature family effectively behaves like a sparse context switch, so the model can still overfit “someone is in a surface-change window” even though the explicit binary flag was removed. The smaller regression versus the original D10 attempt suggests this angle was less harmful, but still not additive enough versus existing `surface_elo`, `surface_elo_shrunk`, surface rolling form, `season_surface_share`, and `days_since_last_surface_match`.

**Implication for future attempts:** treat match-sequence-derived surface-transition summaries as close to exhausted under the current data. Do not retry bare switch/streak features, and do not retry gated historical first-two-match adaptation aggregates (`surface_transition_adaptation_matches`, `surface_transition_adaptation_pve`) in this form. If Directive 10 is revisited again, it needs materially richer transition context than the current history sequence alone can provide, likely real surface-swing metadata or a cleaner opponent-adjusted adaptation label. Without that richer source, D10 should be considered low-priority relative to untried directives.

**Directive 12 head-to-head enrichment revisit analysis (2026-03-17):** The hypothesis was that the original D12 failure came from the blunt 1095-day cutoff rather than from matchup recency itself. The implementation therefore stayed inside the same D12 feature family but changed the structure materially: instead of keeping only meetings from the last 3 years, `src/tennis_predict/features.py` maintained a **soft recency-weighted H2H state** where each prior matchup win decayed with a **1095-day half-life**. That preserved older rivalry information while still making fresh meetings count more. The row-level outputs stayed compact and isolated to the directive: `recent_h2h_diff`, `recent_h2h_total`, and `h2h_recency_ratio`. `pytest` passed, gate runtime was **405s**, and ATP feature count rose from **417** to **420**.

The result still regressed to **`ATP_ROC_AUC=0.7592677096914385`**, about **`0.00185`** below the live **`0.7611147327`** gate, so the change was reverted. This was not a no-op. The trained ATP model did spend gain on the new columns: `recent_h2h_diff` importance **`0.002124`**, `h2h_recency_ratio` **`0.001571`**, and `recent_h2h_total` **`0.001544`**. That means the failure was semantic, not wiring. Soft decay fixed the specific problem from the first D12 attempt, namely the hard discard of older meetings, but it did not fix the deeper issue that H2H recency is still a thin, matchup-sparse slice of information that often disagrees with cleaner current-strength signals. In ATP, repeat matchups are limited enough that the model can overfit “rivalry freshness” on a small subset of rows, while the broader population still gets more reliable ordering from `elo_diff`, surface ELO, serve/return ELO, ranking edge, and existing lifetime/surface H2H counts. `h2h_recency_ratio` also remained partly a disguised measure of matchup age and volume, so the new family still invited splits on pair-history freshness rather than a fundamentally different skill axis.

**Implication for future attempts:** treat Directive 12 as close to exhausted under the current data, not just the hard-window version. Do not retry time-decayed or soft-weighted variants of `recent_h2h_diff`, `recent_h2h_total`, and `h2h_recency_ratio` built from pair win counts alone. If H2H is ever revisited again, it should require materially richer matchup information than raw win counts by pair and date, for example style-level interaction residuals or point-level matchup traits. That is outside the scope of D12 as currently specified, so future ATP iterations should move on to untried directives instead of spending more cycles on H2H recency variants.

### Loop 0 -- ELO/Config Tuning (pre-reset, old evaluation)

| Iter | Change | ATP ROC-AUC | WTA ROC-AUC | Combined | Delta | Commit |
|------|--------|-------------|-------------|----------|-------|--------|
| 0 | Baseline: date-split eval, round-ordering fix | 0.7472 | 0.7282 | 0.7377 | -- | 67b394c |
| 1 | config.py: K-factor tuning (K=32 -> K=48) | 0.7497 | 0.7327 | 0.7412 | +0.0035 | 0db45a0 |
| 4 | config.py: surface K-factor refinement | 0.7496 | 0.7392 | 0.7444 | +0.0032 | c199041 |
| 7 | elo.py + features.py: recency-weighted K, surface ELO shrinkage | 0.7511 | 0.7394 | 0.7452 | +0.0008 | 2168acd |
| 8 | config.py + elo.py + features.py: surface prior matches tuning | 0.7473 | 0.7435 | 0.7454 | +0.0002 | 80826a1 |

### Loop 1 -- Post-Reset (pre-immutability, some commits gamed evaluation)

| Iter | Change | ATP ROC-AUC | WTA ROC-AUC | Combined | Delta | Commit |
|------|--------|-------------|-------------|----------|-------|--------|
| 1 | models.py: per-tour XGBoost params (ATP depth=5, lr=0.03) | N/A | N/A | 0.7509 | +0.0055 | c4ee7e2 |
| 2 | models.py: SegmentBlendModel architecture | N/A | N/A | 0.7514 | +0.0005 | 9467a23 |
| 3 | models.py: segment specialist tuning | N/A | N/A | 0.7527 | +0.0013 | bf69838 |
| 4 | features.py + models.py: quality-weighted rolling stats | N/A | N/A | 0.7549 | +0.0022 | a88d5d2 |
| 5 | features.py: season form, streak, handedness features | N/A | N/A | 0.7558 | +0.0009 | c3adff7 |
| 6 | models.py: segment specialist overhaul + blend weights | N/A | N/A | 0.7582 | +0.0024 | 6cb989f |
| 7 | models.py: more segment specialists | N/A | N/A | 0.7595 | +0.0013 | 364ac8e |
| 9 | features.py + models.py: tournament venue history features | N/A | N/A | 0.7600 | +0.0005 | f2604a4 |
| 10 | elo.py + features.py + models.py: rank momentum features | N/A | N/A | 0.7602 | +0.0002 | 556e3a6 |
| 11 | models.py: per-tour feature exclusions | N/A | N/A | 0.7609 | +0.0007 | d557d62 |

### Loop 2 -- Post-Immutability (honest evaluation, current codebase)

| Iter | Change | ATP ROC-AUC | WTA ROC-AUC | Combined | Delta | Commit |
|------|--------|-------------|-------------|----------|-------|--------|
| 3 | models.py: removed WTA R32/P specialists, narrowed blend | 0.7585 | 0.7260 | 0.7422 | +0.0001 | 832d9d7 |
| 4 | models.py: WTA 2-model ensemble (65/35 blend) | 0.7585 | 0.7264 | 0.7425 | +0.0003 | c4bb6a1 |
| 5 | models.py: reliability features, removed ATP clay specialist, WTA fatigue features | 0.7590 | 0.7298 | 0.7444 | +0.0019 | e4ac589 |
| 7 | models.py: WTA Hard specialist param tuning (depth 3->4) | 0.7590 | 0.7307 | 0.7449 | +0.0005 | cc811c5 |
| 8 | models.py: TemporalBlendModel for WTA (2016, weight=0.2) | 0.7590 | 0.7312 | 0.7451 | +0.0002 | 7931909 |
| 10 | elo.py: shrunk_rating() refactor + models.py: WTA temporal 2017/0.25 | 0.7590 | 0.7333 | 0.7461 | +0.0010 | 4115711 |
| 11 | models.py: WTA segment global_weight tuning + temporal weight 0.35 | 0.7590 | 0.7339 | 0.7465 | +0.0004 | ab7590c |
| 14 | models.py: ATP TemporalBlendSpec (2019, weight=0.2) | 0.7594 | 0.7339 | 0.7467 | +0.0002 | bd2fbbf |

---

## Rolled Back (failed) -- Loop 2 only

| Iter | ATP ROC-AUC | WTA ROC-AUC | Combined | Delta | Likely Cause |
|------|-------------|-------------|----------|-------|--------------|
| 1 (gate fail) | 0.7585 | -- | -- | -- | ATP training exceeded 5-min guard rail (314s) |
| 2 | 0.7568 | 0.7259 | 0.7413 | -0.0008 | ATP regression, WTA still weak |
| 6 | 0.7590 | 0.7298 | 0.7444 | 0.0000 | No improvement, tie not counted |
| 9 | 0.7590 | 0.7312 | 0.7451 | 0.0000 | No improvement, tie not counted |
| 12 | 0.7590 | 0.7339 | 0.7465 | 0.0000 | No improvement, tie not counted |
| 13 | 0.7590 | 0.7339 | 0.7465 | 0.0000 | No improvement, tie not counted |
| 15 | 0.7594 | 0.7339 | 0.7467 | 0.0000 | No improvement, tie not counted |
| 16 | 0.7594 | 0.6657 | 0.7126 | -0.0341 | WTA catastrophic regression (models.py WTA-specific change) |
| 17 | 0.7594 | 0.6692 | 0.7143 | -0.0324 | WTA catastrophic regression |
| 18 | 0.7594 | 0.6848 | 0.7221 | -0.0246 | WTA catastrophic regression |
| 19 | 0.7594 | 0.6717 | 0.7155 | -0.0312 | WTA catastrophic regression |
| 20 | 0.7594 | 0.6894 | 0.7244 | -0.0223 | WTA catastrophic regression |
| 21 | 0.7594 | 0.7339 | 0.7467 | 0.0000 | No improvement, tie not counted |
| 22 | 0.7594 | 0.6657 | 0.7126 | -0.0341 | WTA catastrophic regression |
| 23 | 0.7594 | 0.6657 | 0.7126 | -0.0341 | WTA catastrophic regression |

**Key observation:** ATP ROC-AUC has been FROZEN at 0.7594 for iterations 5-23 (19 consecutive iterations). Every change only affected WTA. The agent repeatedly tried to fix WTA via models.py and caused catastrophic regressions (0.66-0.69 range).

---

## Exhausted Strategies (DO NOT RETRY)

- **models.py hyperparameter tuning** -- 20+ iterations of XGBoost param sweeps, fully saturated. ATP stuck at 0.7594, WTA fragile.
- **Ensemble weight adjustments** -- WTA 65/35 blend found in iter 4, further tuning yields nothing.
- **Segment specialist count/weight changes** -- Tested 0-4 specialists per tour. ATP: 250+A specialists optimal. WTA: Hard+I specialists optimal. Adding more regresses.
- **TemporalBlendModel weight tuning** -- ATP 2019/0.2, WTA 2017/0.35. Tested multiple combinations. Diminishing returns.
- **WTA-specific feature exclusions** -- Season, streak, handedness features excluded from WTA. Height excluded. Further exclusion does not help.
- **Reliability feature bases** -- All 10 bases added (career/surface/season/tourney matches, activity windows, rest days). No more to add.
- **WTA fatigue features** -- match_density, minute_density, surface_switch_gap all added. Covered.
- **Per-tour feature prefix exclusions** -- ATP excludes entry_, WTA excludes season_/streak/hand_. Tested.

---

## Untried Strategies (HIGH PRIORITY)

### 1. Serve/Return ELO (elo.py) -- HIGHEST VALUE
ATP is 60-65% serve-dominated. Current ELO treats every match as pure win/loss. Adding serve_elo and return_elo tracks would capture the single most predictive dimension in men's tennis.

**Implementation target:** `elo.py` -- add `serve_elo`/`return_elo` fields to `PlayerState`, surface-specific variants. Compute from `w_bpFaced`, `w_bpSaved`, `w_SvGms` (loaded in features.py stats_from_row, never used for ELO). Features: `serve_elo_diff`, `return_elo_diff`, `serve_return_gap`.

### 2. Score-String Parsing (features.py) -- HIGH VALUE
The `score` column exists in every match row (stored in META_COLUMNS, carried through as feature). Never parsed. Contains set counts, tiebreak markers, retirement flags, game margins.

**Implementation target:** `features.py` -- add `parse_score()` function. Extract: sets_played, tiebreaks_count, was_retirement, straight_set_win, game_margin. Add rolling: `avg_sets_played_last_N`, `tiebreak_win_rate_last_N`, `straight_set_pct_last_N`. Filter retirements from rolling stats.

### 3. Best-of-5 Flag (features.py) -- MODERATE VALUE
`best_of` column exists and `best_of_5` feature is already computed in build_feature_frame(). But there are no interaction features: `best_of_5 * elo_diff`, `best_of_5 * win_rate_last_N`, historical best-of-5 performance tracking.

**Implementation target:** `features.py` -- track per-player best-of-5 win rate, match count. Grand Slam format fundamentally changes prediction dynamics (better player wins more often in 5 sets).

### 4. Country/Home-Court Features (features.py) -- MODERATE VALUE
`winner_ioc` and `loser_ioc` columns in raw data. Completely ignored. Tournament-to-country mapping derivable from tourney_id prefix.

### 5. Calibrated Probability Stacking (models.py) -- LOW-MODERATE VALUE
XGBoost poorly calibrated. Platt scaling or isotonic regression on top. Listed since iteration 0, never tried. Would require models.py changes but is architecturally distinct from param tuning.

### 6. Momentum ELO (elo.py) -- MODERATE VALUE
Separate ELO track with exponential decay half-life. Recent form matters more than 6-month-old form. Current rolling windows partially capture this, but a dedicated ELO track would be structurally cleaner.
