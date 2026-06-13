---
name: commit-exp
description: >
  XGBoost Commit Experiment — selectively stage and commit experiment artifacts to git.
  Stages model, feature lists, metrics, figures, logs, and project.yaml for a given tag.
  Includes a "mark as best" flow that tracks the current best tag and offers to
  git rm --cached old artifacts when a new best is promoted. Use when the user says
  "/commit-exp", "commit experiment", "save experiment to git", "push results",
  "mark as best", or after /validate completes.
---

# XGBoost Commit Experiment

Stage and commit experiment artifacts for a given tag, with optional "best" promotion.

## Step 1 — Get Tag

Ask for `--tag` if not provided. Suggest the most recently validated tag:
```bash
ls -td output/models/*/ 2>/dev/null | head -1 | xargs basename
```

## Step 2 — Verify Artifacts Exist

Check key artifacts are present before staging:
```bash
ls output/models/<tag>/xgb.json 2>/dev/null || echo "MISSING: model"
ls output/features/<tag>/selected_features*.txt 2>/dev/null || echo "MISSING: feature list"
ls output/features/<tag>/threshold_metrics_<tag>.csv 2>/dev/null || echo "MISSING: metrics"
ls output/figures/<tag>/ 2>/dev/null || echo "MISSING: figures"
```

If model is missing: BLOCK — "No model found for `<tag>`. Run `/train` then `/validate`."
If metrics are missing: warn — "Metrics not found — run `/validate --tag <tag>` first, or continue without them."

## Step 3 — Stage Artifacts

Stage the following files for the given tag:
```bash
# Core config (always)
git add project.yaml

# Feature selection outputs
git add output/features/<tag>/selected_features*.txt
git add output/features/<tag>/member_split.json
git add output/features/<tag>/threshold_metrics*.csv
git add output/features/<tag>/best_params.json 2>/dev/null || true
git add output/features/<tag>/hpo_trials.csv 2>/dev/null || true
git add output/features/<tag>/feature_importance_ranking.csv 2>/dev/null || true

# Figures and model
git add output/figures/<tag>/
git add output/models/<tag>/xgb.json

# Logs for this tag
git add output/logs/*_<tag>_*.log 2>/dev/null || true

# Experiment doc if updated
git add docs/EXPERIMENTATION.md
```

Show staging summary:
```bash
git diff --staged --stat
```

## Step 4 — Mark as Best (optional)

Read current best:
```bash
cat output/best_experiment.txt 2>/dev/null || echo "(none)"
```

Ask: "Is `<tag>` the new best experiment? (y/n)"

If **yes**:
1. Note the current best tag (call it `<old_tag>`).
2. If an old best exists, list its committed artifacts:
   ```bash
   git ls-files output/models/<old_tag>/ output/figures/<old_tag>/ output/features/<old_tag>/
   ```
3. Ask: "Remove `<old_tag>` artifacts from git to keep history clean? (y/n)"
   - If yes: `git rm --cached <files...>` (removes from git index, keeps local disk)
   - If no: skip
4. Write new tag to best_experiment file and stage it:
   ```bash
   echo "<tag>" > output/best_experiment.txt
   git add output/best_experiment.txt
   ```

If **no**: skip steps above.

## Step 5 — Commit

Show final staged diff:
```bash
git diff --staged --stat
```

Ask: "Commit message? (default: 'Add <tag> experiment results')"

Commit:
```bash
git commit -m "<message>"
```

## Step 6 — Push (optional)

Ask: "Push to remote? (y/n)"
- If yes: `git push`
- If no: print "Run `git push` when ready."

## Notes

- **Never stages:** `output/data/` (raw parquet), any `*.parquet`, HTML reports
- `git rm --cached` only removes from git tracking — local files are untouched
- If pushing after promoting a new best, old artifact files will be removed from the remote on the next push
