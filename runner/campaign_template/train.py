"""
Auto-train experiment script for campaign: <CAMPAIGN_NAME>
Single-file ML pipeline — the ONLY file the Executor edits.

TODO: Fill in data loading, feature engineering, model training, and metric reporting.

Output between --- markers is parsed by the Reviewer:
  val_<primary_metric>, training_seconds, total_seconds, n_features, description
"""
import time

t_start = time.time()

DESCRIPTION = "Baseline: TODO"

# ─── Data loading ───────────────────────────────────────────────────────────
# TODO: Load your dataset and create train/val/test splits

# ─── Feature engineering ────────────────────────────────────────────────────
# TODO: Feature engineering here

# ─── Model training ─────────────────────────────────────────────────────────
# TODO: Train your model

# ─── Evaluation ─────────────────────────────────────────────────────────────
# TODO: Compute metrics

t_total = time.time() - t_start

# ─── Structured output (parsed by Reviewer) ─────────────────────────────────
print("---METRICS_START---")
# TODO: print your metrics
print(f"training_seconds: {0:.1f}")
print(f"total_seconds:    {t_total:.1f}")
print(f"n_features:       {0}")
print(f"description:      {DESCRIPTION}")
print("---METRICS_END---")
