Completed. We now have **20/20 experiments** logged in `results.tsv`, so here is a rigorous post-run reflection.

## 1) Outcome Snapshot (This 20-Experiment Run)

- **Best `val_pr_auc`**: `0.845984` (`a060eb0`, `A_restart`, tuned XGBoost basin)
- **Start-of-run baseline**: `0.838794`
- **Net gain over run baseline**: `+0.007190`
- **Keeps / discards / crashes**: `2 / 18 / 0`
- **Keep rate**: `10%`
- **Max consecutive non-improvements**: `9`
- **Action mix**:
  - `A_model`: 7
  - `A_restart`: 4
  - `A_feature`: 3
  - `A_hp`: 2
  - `A_diagnose`: 2
  - `A_imbalance`: 2
- **Family bests**:
  - XGBoost: `0.845984`
  - LightGBM: `0.830511`
  - CatBoost: `0.824894`
  - RF: `0.816348`
  - ET: `0.818763`

## 2) Strategy Quality Assessment

### What worked
- **Restart strategy worked once, decisively**: the biggest gain came from `A_restart` (jumping to the stronger XGBoost basin), not incremental HP nudges.
- **ABES as executable policy helped discipline**:
  - Action types were explicit and logged every run.
  - Plateau forcing worked (it forced restart when discard streak was high).
  - We avoided pure intuitive drift.

### What failed
- **Most experiments were local noise around an already-strong basin**:
  - Feature additions (`magnitude`, `rank`) and imbalance variants mostly degraded PR-AUC.
  - Minor HP perturbations around best config were near-flat or negative.
- **Model-family retries did not change winner**:
  - LightGBM/CatBoost/RF/ET stayed clearly below tuned XGBoost.
- **Diagnosis detected anomaly but did not produce competitive alternative**:
  - LightGBM anomaly was real in effect (severe underperformance), but fixes only recovered to ~0.83 PR-AUC.

### Pipeline effectiveness
- **Strong operational reliability**:
  - 0 crashes in this 20-run campaign.
  - All runs completed within budget envelope.
- **Weak search efficiency**:
  - 18/20 discards means low information yield per compute minute in late run.
  - Plateau management worked procedurally, but not enough to create truly new high-performing regions beyond the known one.

## 3) Algorithm Usefulness (Empirical, This Run)

Ranked by practical value in this campaign:

1. **`A_restart`** — highest ROI  
   - Only path that produced the winning improvement.
2. **`A_hp`** — medium  
   - Useful for confirming local sensitivity; rarely improved.
3. **`A_feature`** — low-medium  
   - Useful as falsification/ablation; mostly degraded.
4. **`A_diagnose`** — medium (for debugging), low (for metric gain)  
   - Good for understanding anomalies, not for top score.
5. **`A_model`** — low (after fair coverage)  
   - Once major families are covered, additional family retries had diminishing value.
6. **`A_imbalance`** — low  
   - Alternative imbalance manipulations were mostly harmful versus tuned `scale_pos_weight`.

## 4) Root Cause Analysis of Result Patterns

### Why one restart improved but most others failed
- **Known high-quality basin existed** (depth-6, lr~0.0777, 1500 trees, tuned regularization).  
  Jumping there improved quickly.
- **Subsequent perturbations were mostly within local neighborhood** and often reflected noise-level differences rather than structural gains.

### Why non-XGBoost models stayed behind
- On this feature space (PCA-heavy + limited engineered features), **XGBoost’s bias/variance tradeoff** remained superior.
- LightGBM showed recurrent weak behavior in this setup; even anomaly-fix runs remained significantly below best.

### Why feature expansion underperformed
- Added groups (`magnitude`, `rank`) likely introduced redundancy/noise relative to already expressive tuned trees.
- Current strongest configuration already captures much of available signal from existing transformed inputs.

### Why imbalance alternatives underperformed
- Base tuned configuration already handled class imbalance well via `scale_pos_weight`.
- Additional imbalance interventions (ADASYN, overweighting) likely over-corrected or distorted class boundary.

## 5) Comparison With Mar31 and Apr01

### Versus Mar31 (`docs/brainstorming/2026-03-31-autotrain-mar30-postmortem.md`)
- Mar31 honest best was ~`0.833714` (with noted leakage concerns on one higher score).
- This run best: `0.845984`.
- **Improvement**: roughly `+0.0123` absolute over Mar31 honest best.
- **Why improved**:
  - Better prior initialization and warm-start knowledge.
  - Stronger XGBoost basin discovery/reuse.
  - More disciplined action logging and controlled experiment flow.
  - Fewer methodological mistakes (no crash churn, cleaner loop execution).

### Versus Apr01 (`docs/brainstorming/2026-04-03-apr01-100exp-reflection.md`)
- Apr01 best was effectively `~0.846`.
- This run best: `0.845984` (essentially the same).
- **What improved vs Apr01**:
  - ABES execution was more operationally explicit (engine-driven, constraint-enforced).
  - Faster recovery to high-quality basin despite lower budget.
- **What did not improve**:
  - **No new SOTA beyond Apr01**.
  - Same dominant basin, no better one found.
  - Similar failure mode in late stage: many non-improving trials around plateau.

## 6) What Improved / What Didn’t / Why

### Improved
- **Reliability**: 0 crashes.
- **Process traceability**: every run typed and logged with structured metadata.
- **Speed to strong result**: recovered high basin quickly within 20-run cap.
- **Scientific discipline**: mostly single-variable tests and explicit keep/discard logic.

### Not improved
- **Top metric ceiling**: no gain above `0.845984`.
- **Exploration productivity after best found**: many low-yield runs.
- **Alternative model competitiveness**: no challenger to tuned XGBoost.

### Why
- Likely hitting **dataset/model-class ceiling** for current pipeline family.
- Search remained mostly within **tree-ensemble paradigm** on same feature substrate.
- No fundamentally new representation learning or data signal expansion introduced.

## 7) Critical Final Judgment

- The run is a **successful optimization replication**, not a breakthrough run.
- It validated that:
  - The prior best basin is robust.
  - Most nearby alternatives are inferior.
- It did **not** establish a materially better frontier than Apr01.
- Given the plateau behavior and repeated negative marginal returns, this 20-run budget was used correctly to confirm boundaries, but not enough to open a new frontier.

## 8) If Continuing Beyond 20 (Optional, Not Required)

For genuine upside (not micro-tuning), next cycle should be structurally different:
- Add **new signal families** (not just more interactions/ranks of current columns).
- Add **strict anomaly protocol** for LightGBM calibration diagnostics beyond head samples.
- Shift objective from “single best point” to **Pareto-aware selection** when PR-AUC differences are tiny.
- Use restart policy that explores **truly orthogonal basins**, not slight variants of known tuned XGBoost.

