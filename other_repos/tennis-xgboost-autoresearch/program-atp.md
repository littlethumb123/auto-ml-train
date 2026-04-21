# program-atp.md -- ATP-Only Tennis Match Prediction Auto-Research

## MANDATORY CONSTRAINTS

1. **`models.py` is FROZEN.** Hyperparameters, ensemble weights, blend tuning, and segment specialists are exhausted after 20+ iterations. Any iteration that only touches `models.py` will be rolled back. You MUST change `elo.py` or `features.py`.
2. **Read `COMBAT_LOG.md` first.** It records what already worked, what failed, and what is exhausted. Repeating a dead end wastes an iteration.
3. **The live ATP gate is `0.7611` ROC-AUC.** `0.7594` was the honest pre-nationality plateau. It is not the win threshold anymore. The ATP-only loop baseline was `0.7530`.
4. **One change per iteration.** Isolate variables. If you test home-court isolation and retirement proxies together and the score moves, you learn nothing.
5. **Directives 1-4 are completed wins to preserve.** The next loop starts with Directive 5.

## Objective

Maximize `ATP_ROC_AUC` on the 2026 date-split ATP validation set. Higher is better. One scalar. That is the target function.

**Current best:** `0.7611` ATP ROC-AUC  
**ATP-only loop baseline:** `0.7530`  
**Honest plateau before nationality:** `0.7594`  
**Near-term target:** `0.7700+`  
**Stretch target:** `0.7900+`  
**Practical ceiling:** roughly `0.80-0.82` because tennis has irreducible match variance

The ATP-only loop produced exactly 4 verified wins:
- Iter 1: serve/return ELO, `+0.0026`
- Iter 4: score parsing, `+0.0004`
- Iter 5: best-of-5 features, `+0.0032`
- Iter 10: IOC nationality, `+0.0019`

The next loop should extend that path. Do not reopen solved areas unless a directive explicitly says to preserve, prune, or isolate them.

## Evaluation

```bash
bash gate-atp.sh
# Outputs: ATP_ROC_AUC=0.XXXX
# Runs the ATP pipeline only, extracts ROC-AUC, and enforces guard rails
# Deterministic: XGBoost random_state=42, tree_method="hist"
```

Research-loop scoring rules:
- The only real win is `ATP_ROC_AUC > 0.7611`
- `0.7594` is historical context only
- A run that clears stale `0.7594` plumbing but does not beat `0.7611` is not a success
- Keep timing practical: target under 5 minutes, and never exceed the existing hard gate elsewhere

## What You Can Change

| File | Arena | Hard Constraints |
|------|-------|-----------------|
| `src/tennis_predict/config.py` | K-factors, windows, priors, constants, tournament-country logic | Keep `META_COLUMNS`, `TARGET_COLUMN`, `TOURS`, `RepoPaths` |
| `src/tennis_predict/elo.py` | Rating-system logic, K behavior, state tracking, alternate rating approaches such as Glicko | Keep function signatures: `elo_expected()`, `updated_elo()`, `apply_match_result()`. `PlayerState` stays a dataclass |
| `src/tennis_predict/features.py` | Feature engineering, feature removal, transformations, composite features | Keep `build_feature_frame()` signature. Keep player A/B orientation. Keep strict temporal ordering: pre-match snapshot only |
| `pyproject.toml` | Dependencies only | Do not change package name, Python version, or build system |

## What You Cannot Change

`data.py`, `cli.py`, `evaluate.py`, `gate-atp.sh`, `run-research-atp.sh`, `data/raw/**`, `data/validation/**`, `tests/**`.

These are structural. Touching them invalidates comparisons.

**Why `evaluate.py` is immutable:** it owns scoring, feature-importance extraction, and sanity checks. Earlier loops abused mutable evaluation-path code to game validation scores. That attack surface is closed.

## The System You Are Improving

ATP match prediction via XGBoost over pre-match feature snapshots. Roughly `132K` ATP training matches from 1985-2025 feed the training set.

**Validation split:** ATP matches after `2025-12-31` on the date-based holdout.

**Current architecture:**
- ELO engine: base ELO, surface ELO, serve/return ELO, surface serve/return ELO, Bayesian surface shrinkage, tournament-level K, recency-sensitive K logic
- Features: roughly `324` columns after one-hot in the iter-10 importance dump, including ELO diffs, rank/form/activity windows, serve/return strength, score-derived stats, best-of-5 history, IOC nationality rolling features, H2H, age/height/seed diffs, categoricals, and reliability-style aggregates
- Model: the frozen `models.py` XGBoost stack already validated by prior loops

Read the source before changing it. `features.py` remains the primary lever. `elo.py` is the secondary lever.

## Plateau Diagnosis

The stale story was wrong. The ATP loop did **not** top out at `0.7592`.

The correct ATP progression was:
- `0.7530` baseline
- `0.7556` after serve/return ELO
- `0.7560` after score parsing
- `0.7592` after best-of-5
- `0.7594` honest plateau before nationality
- `0.7611` after IOC nationality

The correct lesson is:
- isolated, structurally plausible signal can still move ATP ROC-AUC
- small wins compound when they attack different failure modes
- bundled feature dumps hide signal and add noise
- feature-count bloat and low-importance clutter are now real constraints

Feature-importance evidence from iter 10 (`324` features) should guide the next loop:
- Top 10: `elo_diff (0.1135)`, `surface_elo_diff (0.0511)`, `rank_edge (0.0266)`, `tourney_level_D (0.0126)`, `opponent_surface_elo_avg_last_100_diff (0.0109)`, `matches_last_30_days_diff (0.0101)`, `hand_unknown_sum (0.0101)`, `opponent_elo_avg_last_100_diff (0.0096)`, `surface_point_win_rate_last_25_diff (0.0095)`, `surface_elo_shrunk_diff (0.0091)`
- Serve/return ELO still matters: `surface_serve_elo_diff` rank `22` (`0.00386`), `serve_elo_diff` rank `32` (`0.00304`), `surface_return_elo_diff` rank `35` (`0.00287`)
- Zero-importance features: `tourney_level_250`, `tourney_level_F`, `tourney_level_O`, `surface_Unknown`, `round_R128`, `round_F`, `round_ER`, `round_BR`, `same_nationality`
- Bottom `143` features, about `31%` of the set, sit below `0.0015` importance and are mostly `_sum` variants
- Near-perfect correlation pairs already exist: `point_win_rate_last_10_diff` vs quality-weighted version (`r=0.998`), `opponent_elo_avg_last_100_diff` vs `opponent_elo_avg_last_50_diff` (`r=0.955`)

Home-court isolation is no longer a live ATP lead:
- the 2-feature isolation was tested 5 times across 2 loop runs
- it consistently regressed by roughly `-0.004` to around `0.7570`
- the signal appears to already be absorbed by the rolling nationality features

Do not prune proven winners just because they are not in the top 10. Do prune proven dead weight. Keep each change scoped enough that you can attribute the result honestly.

## Research Directives

These are not suggestions. This is the evidence-backed ATP queue for the next loop.

**Raw columns still matter.** `winner_ioc`, `loser_ioc`, `score`, `minutes`, and the serve stats in the source CSVs are still valid places to mine signal. But each iteration must stay tightly isolated.

### Directive 1: Serve/Return ELO -- COMPLETED (iter 1, `+0.0026`)

Implemented and validated. Keep the service-point-based serve/return ELO family and the surface-specific variants.

Preserve:
- `serve_elo`
- `return_elo`
- `surface_serve_elo`
- `surface_return_elo`

Do not reopen this area by switching to:
- hold-rate-based serve ELO
- serve/return probability transforms
- momentum or decay variants tied to serve/return form

### Directive 2: Score Parsing -- COMPLETED (iter 4, `+0.0004`)

Implemented and validated. Score parsing already exposes sets played, tiebreaks, game margin, retirement detection, and related match-shape features.

Do not revisit this area with:
- score-closeness rolling features
- broad score-shape interaction bundles

### Directive 3: Best-of-5 Performance -- COMPLETED (iter 5, `+0.0032`)

Implemented and validated. Format-specific history is in and should remain.

Do not reopen this area with:
- best-of interaction features
- large format-specific cross terms

### Directive 4: IOC Nationality Features -- COMPLETED (iter 10, `+0.0019`)

Implemented and validated. Nationality carries real ATP signal. Keep the rolling nationality rates and IOC-bucket structure that survived validation.

Important nuance:
- the nationality win does **not** protect the raw `same_nationality` flag
- `same_nationality` showed zero importance
- the rolling nationality features carried the actual signal

### Directive 5: Retirement/Injury Proxy Features

This is the lowest-effort fresh signal source.

Use the existing retirement parsing already present in match stats and surface it as pre-match player state:
- `retirement_count_last_N`
- `matches_since_last_retirement`

Keep the first pass minimal. Do not bundle:
- extra injury heuristics
- interaction terms
- speculative medical features

Expected gain: roughly `+0.0005` to `+0.0020`

### Directive 6: ATP Fatigue Composites

ATP still lacks the validated WTA-style fatigue derivation path in the ATP feature loop.

Priority candidates:
- `match_density`
- `minute_density`

Bring over the ATP equivalents if they are absent from the ATP path. Keep them as compact composites, not a wide family of fatigue interactions or rolling derivatives.

Expected gain: roughly `+0.0005` to `+0.0015`

### Directive 7: Reserved

The original pruning directive has been moved to Directive 15 so zero-importance removal stays isolated from the feature-expansion queue. Do not implement work against stale references to Directive 7.

### Directive 8: Glicko-2 Rating Deviation

Higher effort. Exploratory, but defensible.

Goal:
- add rating deviation as an uncertainty signal
- capture when a player's current rating should be trusted less

This is different from dead-end `ELO_START` tuning and different from failed momentum/decay experiments. Keep the implementation isolated from K retuning and form interactions.

### Directive 9: Indoor/Outdoor Proxy for Hard Courts

Moderate effort. Uncertain, but still viable.

Hard courts mix materially different conditions. If a robust indoor/outdoor proxy can be derived without fragile heuristics, it may create useful structure. Do not let this expand into a large metadata project or a broad geography feature bundle.

### Directive 10: Surface-Transition Performance

Players perform differently when switching surfaces. A clay specialist moving to hard court in the same month has measurably different form.

Already available in `features.py`: surface tracking per match, `days_since_last_surface_match`.

Implementation:
- In `_snapshot_player()`, track the player's previous match surface in `PlayerHistory`
- Add `surface_transition` binary: `1` if current surface != previous match surface, `0` otherwise
- Add `surface_streak`: count of consecutive matches on current surface
- Add `surface_win_rate_current_streak`: win rate during the current surface streak only
- Expose as `_diff` and `_sum` in the match feature row

Expected gain: `+0.0005` to `+0.0015`
Do NOT add rolling surface-transition composites or surface-pair interaction matrices.

### Directive 11: Scheduling Density Features

Already exists: `matches_last_7_days`, `matches_last_14_days`, `matches_last_30_days`, `days_since_last_match`.
Missing: minute-level density and fatigue composites validated on WTA.

Implementation:
- In `_snapshot_player()`, compute `match_density_7d`: `matches_last_7_days / 7.0`
- Compute `minute_density_14d`: total minutes played in last 14 days (from stored match minutes in history records)
- Compute `minutes_per_match_last_10`: average match duration from last 10 matches
- Expose as `_diff` and `_sum`

Expected gain: `+0.0005` to `+0.0015`
Keep to 3 new features maximum. Do not expand into a fatigue interaction family.

### Directive 12: Head-to-Head Enrichment

Already exists: `h2h_diff`, `h2h_total`, `surface_h2h_diff`, `surface_h2h_total`.
Missing: recent H2H form (last 3 meetings weight more than meetings 5 years ago).

Implementation:
- In `build_feature_frame()`, alongside the existing `head_to_head` dict, maintain a `recent_h2h` dict keyed by `(player_a_id, player_b_id)` that stores only meetings from last 3 years (`1095` days)
- Add `recent_h2h_diff` and `recent_h2h_total` (last 3 years only)
- Add `h2h_recency_ratio`: `recent_h2h_total / h2h_total` (how much of H2H history is recent)
- Expose as features in the match row

Expected gain: `+0.0005` to `+0.0010`
Do NOT add H2H surface interaction terms or H2H-conditioned win rates.

### Directive 13: Rank Momentum Enhancement

Already exists: `rank_change_30_days`, `rank_change_90_days`, `rank_change_365_days` (in `features.py` lines `493-523`).
Missing: momentum direction signal and rank volatility.

Implementation:
- In `_snapshot_player()`, add `rank_rising`: `1` if `rank_change_90_days > 0` (rank improved), `0` otherwise
- Add `rank_volatility_90d`: `abs(max_rank - min_rank)` over last 90 days from rank history
- Expose as `_diff` and `_sum`

Expected gain: `+0.0003` to `+0.0010`
Keep to 2 new features. Do not add rank trajectory polynomials or rank interaction terms.

### Directive 14: Upset Propensity

Not currently tracked. Some players consistently beat higher-ranked opponents while others consistently lose to lower-ranked ones.

Implementation:
- In `PlayerHistory`, when recording a match, also record whether the opponent's rank was higher or lower
- Track `upset_wins`: count of wins against opponents ranked higher (by at least 20 positions)
- Track `upset_losses`: count of losses to opponents ranked lower (by at least 20 positions)
- Compute `upset_rate_last_20`: `upset_wins / total_matches_vs_higher_ranked` (last 20 relevant matches)
- Compute `loss_to_lower_rate_last_20`: `upset_losses / total_matches_vs_lower_ranked` (last 20 relevant matches)
- Expose as `_diff`

Expected gain: `+0.0005` to `+0.0015`
Keep strictly to 2 features. Do not add rank-gap-weighted variants.

### Directive 15: Feature Pruning -- Zero-Importance Removal

This is the original Directive 7 (now renumbered). Prune the 9 zero-importance features from iter-10 SHAP audit:
- `tourney_level_250`, `tourney_level_F`, `tourney_level_O`
- `surface_Unknown`
- `round_R128`, `round_F`, `round_ER`, `round_BR`
- `same_nationality`

These are one-hot encoded categorical values. Pruning means either:
(a) dropping them in `features.py` before returning the feature frame, or
(b) adding them to a `DROP_FEATURES` list in `config.py` that `build_feature_frame()` filters out

Option (b) is cleaner -- add a `ZERO_IMPORTANCE_FEATURES` list to `config.py`, then filter in `build_feature_frame()` right before return.

Expected gain: `0.0000` to `+0.0010`

## Dead Ends

| Approach | Why |
|----------|-----|
| Post-match ELO as feature | Temporal leakage. Inflates validation materially |
| `match_num` for ordering | Convention changed in 2025. Fixed in `data.py` |
| Height features on ATP | Already included. Marginal signal only |
| `ELO_START` tuning (`1400-1600`) | Cancels out in diffs. No meaningful impact |
| MLP / RandomForest / DecisionTree | XGBoost dominates. Already tested |
| Removing one-hot categoricals wholesale | Surface, round, and tournament level still matter |
| `models.py` hyperparameter sweeps | Exhausted over 20+ iterations |
| Segment specialist tuning | Current setup is the local optimum. More specialists regress |
| Ensemble blend weight changes | Not the ATP bottleneck |
| Temporal blend weight changes | Already tuned. Further changes are noise |
| Score closeness rolling features | Tested by 2 independent agents. Roughly `-0.003` |
| Hold-rate-based serve ELO | Strictly worse than service-point-based serve ELO. Roughly `-0.002` |
| Momentum / decayed ELO | Tested by 2 agents. Roughly `-0.0014` to `-0.0020` |
| Rating-form interaction features | Roughly `-0.0045` |
| Best-of interaction features | Roughly `-0.0034` |
| Serve/return probability transforms | ELO win-prob transforms regressed roughly `-0.001` |
| Home-court 2-feature isolation (`is_home_court_diff`, `is_home_court_sum`) | Tested 5 times across 2 loop runs. Consistent `-0.004` regression to `~0.7570`. The signal is already captured by nationality rolling features |
| Bundled home-court rolling derivatives | The 8-feature home/away bundle added noise and obscured the core signal. Do not retry the bundle. Test the 2-feature core only |

## Guard Rails

- Aim for under 5 minutes end-to-end. Treat anything slower as a regression. Existing shell guards elsewhere must still pass.
- Model size must stay under 100MB
- Feature count must stay under 500 after one-hot
- `pytest` must pass
- No leakage: no validation rows in training, no training rows in validation
- Memory use must stay under 8GB
- Preserve strict pre-match temporal ordering for every feature
- Avoid wide feature bundles unless the entire point of the iteration is isolated pruning

## Combat Log

Read `COMBAT_LOG.md` before every iteration. It contains the cross-loop history of what worked, what failed, and what is exhausted.

Known ATP wins to preserve:
- Iter 1: serve/return ELO `+0.0026`
- Iter 4: score parsing `+0.0004`
- Iter 5: best-of-5 `+0.0032`
- Iter 10: IOC nationality `+0.0019`

Directive order for the next ATP loop:
1. Retirement/injury proxy features (D5)
2. Surgical pruning of zero-importance features (D15)
3. ATP fatigue composites / scheduling density (D6/D11)
4. Surface-transition performance (D10)
5. H2H enrichment (D12)
6. Rank momentum enhancement (D13)
7. Upset propensity (D14)
8. Glicko-2 rating deviation (D8)
9. Indoor/outdoor hard-court proxy (D9)

Every ATP iteration log entry should record:
- the single hypothesis tested
- exact files changed
- feature count delta if applicable
- `ATP_ROC_AUC`
- whether it beat `0.7611`
- whether the change was kept, reverted, or moved to dead ends

Treat `0.7611` as the live gate. If a change does not beat `0.7611`, it is not good enough. Make each iteration isolate one evidence-backed idea and either validate it cleanly or kill it cleanly.
