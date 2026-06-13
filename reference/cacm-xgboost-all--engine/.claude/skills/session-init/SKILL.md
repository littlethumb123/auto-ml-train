---
name: session-init
description: >
  XGBoost Session Init — show current context at session start: branch, project config,
  recent experiments, GPU status, data artifacts, and model artifacts. Automatically
  triggered by the session-start hook. Use when the user says "what's the current state",
  "session init", "/session-init", "where did I leave off", or wants to see project status.
---

# XGBoost Session Init

Show current context at session start.

## Step 1 — Branch and Config

```bash
git branch --show-current
```

If on `main` or `engine`: warn "You are on `<branch>`. Training and endpoint work must be on `endpoint/*` branches."

Read `project.yaml` if present. Print:
- `project.name`, `project.prefix`
- `data.feature_table` (last path segment only)

If `project.yaml` missing: print "No project.yaml — run `/onboard` to configure."

## Step 2 — Last Experiments

```bash
grep "^## " docs/EXPERIMENTATION.md | tail -3
```

Then print the metric lines for the most recent entry:
```bash
grep -A 8 "$(grep '^## ' docs/EXPERIMENTATION.md | tail -1)" docs/EXPERIMENTATION.md | head -10
```

## Step 3 — GPU Status

```bash
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader 2>/dev/null || echo "No GPU"
```

## Step 4 — Pipeline Artifacts

```bash
ls -td output/data/*/   2>/dev/null | head -3
ls -td output/models/*/ 2>/dev/null | head -3
ls -td output/features/*/ 2>/dev/null | head -3
```

For the latest tag in `output/models/`:
- Does `output/models/<tag>/xgb.json` exist?
- Does `output/features/<tag>/threshold_metrics_<tag>.csv` exist? If so, print AUC line.
- Does `output/features/<tag>/selected_features*.txt` exist?

## Step 5 — Summary Line

```
=== XGBoost Session Summary ===
Project:  [name or "NOT CONFIGURED"]
Endpoint: [feature_table last segment or "(not set)"]
Branch:   [current branch]
Last experiment: [tag + date from EXPERIMENTATION.md or "none"]
GPU: [name] ([used]/[free] MiB)
Models: [count in latest tag or "none"]

Recommended action: [one specific, actionable next step]
```

## Step 6 — Available Skills

Print:
```
Available: /onboard  /quickstart  /train  /validate  /diagnose  /log-exp  /commit-exp
```

## Recommended Action Logic

- No `project.yaml` → "Run `/onboard` to configure your endpoint"
- On `engine` or `main` → "Run `git checkout -b endpoint/<name>` then `/onboard`"
- No data in `output/data/` → "Run `pipenv run python3 scripts/1_pull_features.py --tag v1`"
- Data exists, no models → "Run `/train`"
- Models exist, no `threshold_metrics*.csv` → "Run `/validate --tag <latest_tag>`"
- Models + metrics exist, no EXPERIMENTATION.md entry → "Run `/log-exp <latest_tag>`"
- Everything present → "Run `/validate` to re-evaluate or start a new experiment with `/train`"
