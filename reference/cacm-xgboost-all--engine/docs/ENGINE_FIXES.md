# Engine Fix Backlog

Bugs and gaps found during endpoint work that should be cherry-picked back to `engine`.
Each entry notes: what broke, which script/file, the fix, and whether it's already applied
to this endpoint branch.

---

## Pending cherry-picks to `engine`

### FIX-001 — `db-dtypes` missing from Pipfile
- **Found:** endpoint/ckd4-progression, 2026-06-03, step 1 pull
- **Symptom:** `ValueError: Please install the 'db-dtypes' package` when calling
  `client.query(...).to_dataframe()` in `scripts/1_pull_features.py`
- **Fix:** `pipenv install db-dtypes` + add `db-dtypes = "*"` to `Pipfile`
- **Files:** `Pipfile`, `Pipfile.lock`

### FEAT-001 — Multi-table feature join in step 1
- **Found:** endpoint/ckd4-progression, 2026-06-03 (needed for _base + _ts1 split tables)
- **What:** `feature_tables` (list) in `project.yaml` + `config.py`; step 1 LEFT JOINs all
  tables on `id_column` at pull time. Falls back to `feature_table` (single string) for
  backward compat. Generic — any endpoint with features spread across multiple BQ tables benefits.
- **Files:** `xgboost_model/config.py`, `scripts/1_pull_features.py`, `project.example.yaml`

### FEAT-002 — Optuna HPO step (3b)
- **Found:** endpoint/ckd4-progression, 2026-06-03 (user request)
- **What:** `scripts/3b_tune_hyperparams.py` — new script. Runs Optuna TPE search on
  selected features, saves `best_params.json`, picked up automatically by step 4.
  `tuning:` section added to `project.example.yaml` and `config.py`. Generic.
- **Files:** `scripts/3b_tune_hyperparams.py` (new), `xgboost_model/config.py`,
  `project.example.yaml`, `.claude/skills/train/SKILL.md`

### FEAT-003 — RFECV feature selection step (3c) + parallel experiment flags
- **Found:** endpoint/ckd4-progression, 2026-06-03 (user request for dual experiments)
- **What:** `scripts/3c_rfe.py` — RFECV with fast mode (starts from importance top-N).
  Added `--feature-list` to steps 3b, 4, 5 so any feature list file can be used.
  Added `--source-tag` to step 3b so experiments can share a data pull.
  Generic — useful for any endpoint wanting to compare feature selection strategies.
- **Files:** `scripts/3c_rfe.py` (new), `scripts/3b_tune_hyperparams.py`,
  `scripts/4_train_model.py`, `scripts/5_validate_run.py`

### FIX-002 — BQ DATE columns unreadable after parquet round-trip
- **Found:** endpoint/ckd4-progression, 2026-06-03, step 2 (reading step 1 parquet)
- **Symptom:** `TypeError: data type 'dbdate' not understood` — BQ DATE columns stored as
  `db_dtypes.DateDtype` in parquet; pandas can't map the type name back on read
- **Fix:** `load_parquet` in `data.py` now uses pyarrow directly, casting `date`/`time`
  columns to `pa.string()` before converting to pandas. No BQ re-query needed — re-serialize
  existing parquet in-place with the same cast.
- **Note:** `index_dt` and `index_dt_1` (duplicate from JOIN) both cast to string and
  auto-dropped by `prep_features` as non-numeric. Harmless but `index_dt_1` should be
  added to `non_feature_columns` in `project.example.yaml` as a reminder.
- **Files:** `xgboost_model/data.py`

### FIX-003 — `prep_features` default `target_column` wrong for non-default outcome columns
- **Found:** endpoint/ckd4-progression, 2026-06-03 (caught before step 3 ran)
- **Symptom:** `prep_features` default is `"impute_outcome_flag"` but any endpoint with a
  different outcome column name would get a silent wrong target or a KeyError at `y = df[target_column]`
- **Fix:** Steps 3, 3b, 3c now all pass `config.OUTCOME_COLUMN` explicitly to `prep_features`
- **Files:** `scripts/3_select_features.py`, `scripts/3b_tune_hyperparams.py`,
  `scripts/3c_rfe.py`

### FIX-004 — 3c_rfe OOM: full parquet loaded before column filter applied
- **Found:** endpoint/ckd4-progression, 2026-06-03, step 3c first run
- **Symptom:** Process silently OOM-killed after loading 302k × 8,538 cols into memory.
  Fast mode was loading the full parquet then filtering to top-N columns — too late.
- **Fix:** Read importance feature list BEFORE opening parquet; pass `columns=` to
  `pq.read_table()` so only ~500 cols + outcome are loaded (~60x memory reduction).
- **Files:** `scripts/3c_rfe.py`

### FIX-005 — session_context.sh misses HPO and RFECV active processes
- **Found:** endpoint/ckd4-progression, 2026-06-03
- **Symptom:** Hook reported "No training processes running" while 3b and 3c were both active
- **Fix:** Added `3b_tune_hyperparams\.py|3c_rfe\.py` to the process grep pattern
- **Files:** `.claude/hooks/session_context.sh`

### FIX-006 — 3b_tune_hyperparams loads full parquet before filtering to selected features
- **Found:** endpoint/ckd4-progression, 2026-06-03 (same root cause as FIX-004)
- **Symptom:** Full 8,538-col parquet loaded into memory then filtered to 500 cols in prep_features.
  Didn't OOM on this machine but is a liability on smaller instances.
- **Fix:** Load feature list first, then use `pq.read_table(..., columns=[...])` to read
  only selected columns + outcome + id. Same pattern as 3c fix.
- **Files:** `scripts/3b_tune_hyperparams.py`

### FEAT-004 — `scale_pos_weight` in config + `xgb_params()`
- **Found:** endpoint/ckd4-progression, 2026-06-03
- **What:** `scale_pos_weight` now readable from `project.yaml` `training:` section and
  injected into `xgb_params()`. Was previously hardcoded/absent. Generic.
- **Files:** `xgboost_model/config.py`

### FIX-008 — Step 4 and step 5 OOM: full wide parquet loaded before column filter
- **Found:** endpoint/ckd4-progression, 2026-06-03, step 4 first run (after FIX-007 resolved)
- **Symptom:** Process silently OOM-killed after loading 302k × 8,538 cols into memory.
  Both step 4 and step 5 used `load_parquet()` (full table) then filtered columns after.
  Same root cause as FIX-004/FIX-006 (3c/3b OOM).
- **Fix:** Load feature list BEFORE opening parquet; read parquet schema to check available
  columns; use `pq.read_table(..., columns=[...])` with: selected_features + NON_FEATURE_COLUMNS
  + OUTCOME_COLUMN + ID_COLUMN + censoring columns (time_to_event, event_indicator,
  follow_up_months, censor_dt, excluded_pre_index). Filter to available columns via schema check.
- **Files:** `scripts/4_train_model.py`, `scripts/5_validate_run.py`

### FIX-007 — `apply_method` ignores `OUTCOME_COLUMN`, defaults to `"impute_outcome_flag"`
- **Found:** endpoint/ckd4-progression, 2026-06-03, step 4 first run
- **Symptom:** `KeyError: 'impute_outcome_flag'` — all censoring functions default
  `target_col="impute_outcome_flag"` and `apply_method` never receives the real column name.
  Any endpoint with a non-default outcome column fails immediately.
- **Fix:** Pass `target_col=config.OUTCOME_COLUMN` as the first kwarg to every `apply_method()`
  call. Also pass `id_col=config.ID_COLUMN` for the `discrete_time` method specifically.
- **Files:** `scripts/4_train_model.py`

### FEAT-005 — 60/20/20 train/val/test split across all pipeline steps
- **Found:** endpoint/ckd4-progression, 2026-06-03 (user request — previous split was 2-way, leaking test into HPO)
- **What:** Three-way stratified split (train 60% / val 20% / test 20%).
  - Step 3 generates the split and saves member IDs to `output/features/<tag>/member_split.json`
  - Steps 3b, 3c, 4, 5 all load member_split.json — guarantees identical holdout across all experiments
  - Test set never loaded until step 5
  - `val_size` + `test_size` configurable in `project.yaml` `training:` section
  - `split_data_three_way()`, `save_split_ids()`, `load_split_ids()` added to `training.py`
  - Steps 3/3b/3c eval on val; step 4 trains on train+val (80%); step 5 evals on test only
  - `--source-tag` added to steps 4 and 5 for cross-experiment data sharing (same pattern as 3b/3c)
- **Files:** `xgboost_model/config.py`, `xgboost_model/training.py`, `project.example.yaml`,
  `scripts/3_select_features.py`, `scripts/3b_tune_hyperparams.py`, `scripts/3c_rfe.py`,
  `scripts/4_train_model.py`, `scripts/5_validate_run.py`

### FIX-010 — Remove censoring module: binary classification pipeline only
- **Found:** endpoint/ckd4-progression, 2026-06-03 (post-training review)
- **What:** `xgboost_model/censoring.py` was carried over from time-to-event survival work and
  is inappropriate for binary classification. `naive_binary` is a no-op; `negative_restriction`,
  `discrete_time`, and `ipcw` all require columns (`follow_up_months`, `time_to_event`,
  `event_indicator`, `censor_dt`) that are never present in the feature pull for this endpoint type.
- **Fix:** Delete `censoring.py`. Remove the method loop from step 4 — single training pass,
  saves `xgb.json` (no method suffix). Remove `--method` from step 5 — loads `xgb.json` directly.
  Remove `_censoring` block and `HPO_METHOD` from `config.py`. Remove censoring columns from
  `non_feature_columns` / `exclude_patterns` in `project.example.yaml`. Delete `CENSORING_METHODS.md`.
- **Files:** `xgboost_model/censoring.py` (deleted), `docs/CENSORING_METHODS.md` (deleted),
  `xgboost_model/config.py`, `scripts/4_train_model.py`, `scripts/5_validate_run.py`,
  `project.example.yaml`, `CLAUDE.md`, `docs/PITFALLS.md`

### FIX-009 — `run_shap_analysis` crashes: surrogate model code + feature mismatch in pred_contribs
- **Found:** endpoint/ckd4-progression, 2026-06-03, step 5 SHAP run
- **Symptom 1:** `sub_model.fit(X_top, model.predict(X))` — dead surrogate-model code that copies params
  including `feature_types` from the trained model; calling `model.predict(X)` with the sub-model's
  `feature_types` set to 20 causes "expected 20, got 499"
- **Symptom 2:** After removing surrogate code, `model.get_booster().predict(DMatrix(X_top), pred_contribs=True)`
  fails with feature_names mismatch — model was trained on N features but `X_top` has only 20
- **Fix:** Remove surrogate model entirely. Run `pred_contribs` on full `X` (matches training columns),
  then select top-N contributions by mean |SHAP| for the bar chart.
- **Files:** `xgboost_model/evaluation.py`

---

## Already on engine (fixed during engine build)

- Hook step-number rot: `7_train_model` / `8_validate_run` → `4_train_model` / `5_validate_run`
  in `log_experiment.sh`, `post_training_metrics.sh`, `pre_training_check.sh`
- LOB / `cohort.lob` references removed from `log_experiment.sh`
- CKD-specific PostToolUse/Edit hooks (sql.jinja cross-sync, hardcoded-date detection) removed
  from `settings.json`
- `session_context.sh` now warns on `engine` branch (not just `main`/`master`)
