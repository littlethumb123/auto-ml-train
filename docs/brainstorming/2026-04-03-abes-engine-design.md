# Executable ABES Engine + Next-Run Campaign Design

**Date**: 2026-04-03
**Status**: Approved
**Context**: Post-apr01 run (100 experiments, best val_pr_auc=0.845984). Reflection identified that ABES was only ~40% implemented because it was advisory (prose) rather than executable (code). The 31-experiment plateau and 55% A_hp over-allocation were direct consequences.

---

## I. Problem Statement

The auto-train agent needs a **computable decision engine** that:
1. Replaces intuitive ABES approximation with numerical urgency/opportunity scores
2. Enforces hard constraints (action-type switching, plateau detection) and advisory dead-end awareness
3. Supports multi-fidelity screening for basin-restart
4. Tracks Pareto front across val_pr_auc, lift@10%, and macro_F1
5. Persists state across context compactions

The agent remains the executor (edits `train.py`, runs experiments, interprets results), but the engine is the **navigator** — it tells the agent what action type to take next and flags when the agent deviates.

## II. Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Multi-metric rule** | Lexicographic with Pareto awareness | val_pr_auc remains keep/discard criterion (backward compatible); Pareto front tracked for analysis and experiment guidance |
| **Engine architecture** | Hybrid: `abes_engine.py` + updated `program.md` | Executable Python computes scores; program.md tells agent to call it |
| **Multi-fidelity** | Built-in `A_restart` action type | Low-fidelity screening (200 trees, 25% data) screens 16 configs per slot |
| **Warm-start** | Selective | Structural learnings loaded (model families, features, dead ends); HP-level priors reset to avoid local-optimum anchoring |
| **Starting point** | Fair neutral XGBoost | Canonical defaults, no Optuna-tuned params, prevents anchoring |
| **Scope** | Full refactor | New files: `abes_engine.py`, `abes_state.json`; updated: `program.md`, `CLAUDE.md`, `AGENTS.md`, `train.py` |
| **Budget** | 100 experiments | Direct comparison to apr01 |

## III. Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      AI AGENT (LLM)                          │
│   Reads engine output → Edits train.py → Runs experiment     │
└──────────┬──────────────────────┬───────────────────────────┘
           │ 1. Run engine        │ 4. Log result
           ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐
│   abes_engine.py    │  │    results.tsv      │
│                     │  │  (experiment log)    │
│ • read results.tsv  │  └─────────────────────┘
│ • read abes_state   │
│ • compute urgency   │  ┌─────────────────────┐
│ • enforce constraints│  │   abes_state.json   │
│ • recommend action  │  │ (persistent state)   │
│ • update state      │  └─────────────────────┘
│ • detect anomalies  │
│ • track Pareto front│  ┌─────────────────────┐
│ • print decision    │  │     train.py        │
└─────────────────────┘  │ (agent edits this)   │
                         └─────────────────────┘
```

### Experiment Loop (Revised)

```
LOOP:
  1. python3 abes_engine.py recommend     → prints recommended action + urgency scores
  2. Agent reads recommendation, edits train.py
  3. git commit -am "experiment: [action_type] — <hypothesis>"
  4. python3 train.py > run.log 2>&1
  5. grep metrics from run.log
  6. python3 abes_engine.py log <commit> <pr_auc> <lift> <macro_f1> <val_f1> <status> <n_features> <model_family> <action_type> "<hypothesis>" "<description>"
  7. python3 abes_engine.py check         → prints anomaly check + Pareto update
  8. If keep: advance. If discard: git reset --hard HEAD~1
  9. GOTO 1
```

### Key Difference from Apr01

The agent no longer *chooses* the action type by intuition. It runs `abes_engine.py recommend`, gets a numerical recommendation with scores, and follows it. The engine enforces:

- **Hard constraint**: Max 5 consecutive experiments of the same action type
- **Plateau trigger**: 8+ consecutive discards → forces `A_restart`
- **Dead-end awareness**: Known dead ends from warm-start printed before every experiment (advisory — agent must not retry)
- **Budget-proportional exploration**: λ_explore(t, T) computed numerically

## IV. ABES Engine Design (`abes_engine.py`)

### Commands

| Command | Input | Output |
|---------|-------|--------|
| `recommend` | reads results.tsv + abes_state.json | Prints urgency scores, recommended action type, suggested experiment |
| `log` | CLI args (11 columns) | Appends to results.tsv, updates abes_state.json |
| `check` | reads results.tsv + abes_state.json | Anomaly detection, Pareto front update, plateau check |
| `status` | reads results.tsv + abes_state.json | Full state dump for recovery |
| `init` | warm-start config | Creates initial abes_state.json with priors |

### Urgency Computation (Revised from Apr01)

Same 7 action types, but now with `A_restart` added:

| Action Type | Urgency Formula | Change from Apr01 |
|-------------|----------------|-------------------|
| `A_model` | (families with < 2 completed non-crash trials) ÷ 6 | Same |
| `A_feature` | 1 − (feature groups tested ÷ total groups); `feature_groups_tested` updated by `log` command via keyword matching on hypothesis/description | Expanded feature groups from 4 to 6 |
| `A_hp` | 1 ÷ (1 + count of A_hp in last 5 rows) | Same |
| `A_diagnose` | min(1.0, 0.5 × undiagnosed anomaly count) | Same |
| `A_ensemble` | 0.3 if ≥2 model families have per-family best scores within 5% of global best val_pr_auc (from results.tsv); else 0.0 | Clarified: uses per-family max from results history |
| `A_validate` | max(0, (t/T − 0.8) × 5) | Same |
| `A_restart` | **NEW**: 1.0 if consecutive_discards ≥ 8; else 0.0 | New action type |
| `A_imbalance` | **NEW urgency**: 1 ÷ (1 + count of A_imbalance in last 10 rows) | Now tracked |

### Exploration-Exploitation Decay

```python
def lambda_explore(t, T):
    fraction_remaining = (T - t) / T
    return 2.0 / (1.0 + math.exp(-5 * (fraction_remaining - 0.5)))
```

- t=1: λ=1.92 (strong exploration)
- t=50: λ=1.00 (balanced)
- t=90: λ=0.08 (strong exploitation)

### Composite Score

```
score(a) = urgency(a) × λ_explore + opportunity(a) × (1 - λ_explore/2)
```

Where `opportunity(a)` is the historical standard deviation of metric deltas for that action type (higher variance = more potential upside).

### Hard Constraints (Enforced in Code)

1. **Action-type cap**: If last 5 experiments are all the same action type → block that type, force next-highest
2. **Plateau restart**: 8+ consecutive discards → urgency(A_restart) = 1.0 (overrides all others)
3. **Dead-end awareness**: Known dead ends stored in `abes_state.json["dead_ends"]` → printed by `recommend` command so the agent sees them before every experiment. The engine cannot syntactically verify whether a proposed `train.py` edit matches a dead end (that requires semantic understanding), so enforcement is advisory: the engine prints the full dead-end list, and the agent is responsible for not retrying them.
4. **Budget gate**: If t ≥ T → print "STOP: budget exhausted" and summary

Note: `t` is the number of **completed** experiments (0-based at start). `T` is the budget.

### Multi-Fidelity Screening (`A_restart`)

When `A_restart` is triggered, the agent modifies `train.py` to run a screening function:

```python
def screen_configs(X_train, y_train, X_val, y_val, n_configs=16):
    """Low-fidelity screen: 200 trees on 25% data, test n_configs random configs."""
    # Subsample training data
    sample_idx = np.random.RandomState(42).choice(len(X_train), size=len(X_train)//4, replace=False)
    X_sub, y_sub = X_train.iloc[sample_idx], y_train.iloc[sample_idx]

    configs = generate_random_configs(n_configs)  # random HP configs
    results = []
    for cfg in configs:
        model = XGBClassifier(n_estimators=200, **cfg)
        model.fit(X_sub, y_sub)
        pr_auc = average_precision_score(y_val, model.predict_proba(X_val)[:, 1])
        results.append((cfg, pr_auc))
    
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:3]  # top 3 configs for full-fidelity evaluation
```

Each screen takes ~60s (16 × ~3.5s each). The top-3 results are printed, and the agent then evaluates the best one at full fidelity.

### Pareto Front Tracking

The engine maintains a Pareto front across (val_pr_auc, lift@10, macro_f1):

```python
def is_pareto_dominant(new, existing):
    """True if new dominates existing on ALL 3 metrics."""
    return (new["pr_auc"] >= existing["pr_auc"] and 
            new["lift"] >= existing["lift"] and 
            new["macro_f1"] >= existing["macro_f1"] and
            (new["pr_auc"] > existing["pr_auc"] or 
             new["lift"] > existing["lift"] or 
             new["macro_f1"] > existing["macro_f1"]))
```

The Pareto front is stored in `abes_state.json` and printed by the `check` command. When an experiment improves a secondary metric (lift or macro_f1) but not val_pr_auc, it's still logged as "pareto_notable" in the status output to inform future experiment selection.

### Anomaly Detection (Improved)

Threshold revised from apr01: `score < max(0.5 × best, 0.75)` (was 0.68). The 0.75 floor catches moderate anomalies like HistGBM's 0.71 that apr01 missed.

## V. Persistent State (`abes_state.json`)

```json
{
  "run_tag": "apr03",
  "budget": 100,
  "experiment_count": 0,
  "consecutive_discards": 0,
  "best_pr_auc": 0.0,
  "best_lift": 0.0,
  "best_macro_f1": 0.0,
  "last_action_types": [],
  "action_type_counts": {
    "A_model": 0, "A_feature": 0, "A_hp": 0,
    "A_diagnose": 0, "A_ensemble": 0, "A_validate": 0,
    "A_restart": 0, "A_imbalance": 0
  },
  "action_type_rewards": {
    "A_model": [], "A_feature": [], "A_hp": [],
    "A_diagnose": [], "A_ensemble": [], "A_validate": [],
    "A_restart": [], "A_imbalance": []
  },
  "model_family_trials": {
    "xgboost": 0, "lightgbm": 0, "catboost": 0,
    "rf": 0, "gbm": 0, "et": 0
  },
  "feature_groups_tested": [],
  "pareto_front": [],
  "dead_ends": [
    "SMOTE + scale_pos_weight",
    "QuantileTransformer on tree models",
    "BaggingClassifier wrapping XGBoost",
    "aucpr as early stopping metric",
    "LightGBM is_unbalance=True",
    "DART booster",
    "tree_method=approx",
    "sklearn GBM (GradientBoostingClassifier)"
  ],
  "anomalies_undiagnosed": [],
  "warm_start": {
    "known_good_features": ["log_amount", "amount_interactions"],
    "known_bad_features": ["v_interactions", "time_features"],
    "best_model_family": "xgboost",
    "competitive_families": ["lightgbm"],
    "known_optimal_ranges": {
      "xgboost_depth": [4, 6],
      "xgboost_lr": [0.02, 0.08],
      "xgboost_n_estimators": [1000, 2000]
    }
  }
}
```

## VI. Updated Results TSV Schema

Add `model_family` column (11 columns total):

```
commit  val_pr_auc  lift_at_10  macro_f1  val_f1  status  n_features  model_family  action_type  hypothesis  description
```

The `model_family` column is one of: `xgboost`, `lightgbm`, `catboost`, `rf`, `gbm`, `et`, `ensemble`, `other`. Only the first 6 are tracked for urgency computation; `ensemble` and `other` are valid log values but don't affect per-family trial counts.

## VII. Train.py Reset (Fair Neutral Starting Point)

Reset to canonical XGBoost with no Optuna-tuned parameters:

```python
DESCRIPTION = "baseline: XGBoost canonical + log_amount + amount_interactions"

def engineer_features(X):
    X = X.copy()
    X["log_amount"] = np.log1p(X["Amount"])
    X["Amt_V1"] = X["Amount"] * X["V1"]
    X["Amt_V2"] = X["Amount"] * X["V2"]
    return X

def build_pipeline(y_train):
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    ratio = n_neg / n_pos
    return XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=ratio,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=1.0,
        min_child_weight=5,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
```

This preserves known-good features (log_amount, amount_interactions) from warm-start but resets all HPs to canonical values. The ABES engine should rediscover the optimal basin independently.

## VIII. Updated Program.md Structure

Key changes to `program.md`:
1. **ABES section replaced** with "Run `python3 abes_engine.py recommend` and follow its recommendation"
2. **Experiment loop updated** to include engine calls at steps 1 and 7
3. **Strategy catalog retained** but marked as "reference only — the engine selects the action type"
4. **Warm-start section updated** with apr01 learnings
5. **Feature groups expanded** from 4 to 6 (add `magnitude_features` and `rank_features`)
6. **Recovery protocol updated** to include `python3 abes_engine.py status`
7. **A_restart documented** as a first-class action type

## IX. Feature Groups (Expanded)

| Group | Features | Status from Apr01 |
|-------|----------|-------------------|
| `log_amount` | `log1p(Amount)` | Known good (+signal) |
| `time_features` | `Time_hour`, `Time_sin`, `Time_cos` | Known bad (noise) |
| `v_interactions` | `V1*V2`, `V1*V3`, `V3*V4` | Known bad (noise) |
| `amount_interactions` | `Amount*V1`, `Amount*V2` | Known good (+signal) |
| `magnitude_features` | `abs(V14)`, `abs(V17)`, `V14**2` | **NEW** — untested |
| `rank_features` | `Amount.rank(pct=True)`, `V14.rank(pct=True)` | **NEW** — untested |

## X. Success Criteria

| Metric | Apr01 Result | Target (this run) | Stretch |
|--------|-------------|-------------------|---------|
| val_pr_auc | 0.845984 | > 0.855 | > 0.865 |
| lift@10 | 9.19 | > 9.30 | > 9.50 |
| macro_f1 | 0.922954 | > 0.930 | > 0.940 |
| Experiments to reach apr01 best | 71 | < 40 | < 25 |
| A_hp allocation | 55% | < 35% | < 25% |
| Plateau (max consecutive discards) | 31 | < 10 | < 6 |
| Known dead ends retried | 4 | 0 | 0 |

## XI. Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Engine bug gives wrong urgency → agent wastes experiments | Unit tests for all urgency formulas before the run |
| Multi-fidelity rank correlation is poor (low-fi ≠ full-fi) | Validate on 3 known configs before using in the run |
| Fair neutral start takes many experiments to recover to 0.84 | Warm-start includes known-good features; canonical XGBoost should reach ~0.83 on first run |
| Context compaction loses engine instructions | `abes_state.json` persists; recovery protocol includes `abes_engine.py status` |
| Pareto tracking adds complexity without value | Track silently; only use for final report, not keep/discard |
