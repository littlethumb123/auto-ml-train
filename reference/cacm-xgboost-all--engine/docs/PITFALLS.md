# Pitfalls

## Data

1. **Never fillna(0) across all features.** Lab values and sparse indicators need forward-fill or should stay NaN (XGBoost handles missing values natively via its split-finding algorithm). Filling with 0 creates false signal.

2. **Check scale_pos_weight.** Must match actual class ratio: `neg_count / pos_count`. A wrong value silently degrades calibration.

3. **Verify exclude_patterns.** Any column that encodes the outcome (e.g., `outcome_flag`, staging columns) must be excluded from features. An outcome table JOIN may add suffixed columns (`_outcome`) that anchored patterns miss — inspect joined columns after pulling.

4. **Column name sanitization.** XGBoost requires alphanumeric column names. The pipeline auto-prefixes `col_` to digit-leading names. The `save_feature_list` function strips this prefix back.

## Training

5. **SHAP on the full model is slow.** Use `--shap` only at validation time, not during feature selection. The pipeline uses XGBoost native `pred_contribs` to avoid the `shap` library's memory issues.
