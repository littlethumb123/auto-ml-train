---
name: log-exp
description: >
  XGBoost Log Experiment — write a structured entry to docs/EXPERIMENTATION.md for
  a completed training run. Reads metrics from threshold_metrics_<tag>.csv, asks for notes,
  updates any hook-written stub in-place, and stages the file. Does NOT auto-commit.
  Use when the user says "/log-exp", "log this run", "document the experiment",
  "update EXPERIMENTATION.md", or after /validate completes.
---

# XGBoost Log Experiment

Write a structured experiment entry to `docs/EXPERIMENTATION.md`.

## Step 1 — Get Tag

If `--tag <tag>` was provided: use it.

Otherwise detect the latest trained tag:
```bash
ls -td output/models/*/ 2>/dev/null | head -1 | xargs basename
```

Ask user to confirm: "Log experiment for tag `<tag>`?"

## Step 2 — Read Metrics

```python
import pandas as pd
df = pd.read_csv(f"output/features/{tag}/threshold_metrics_{tag}.csv")
print(df.to_string(index=False))
```

If `threshold_metrics_<tag>.csv` missing: WARN — "Run `/validate --tag <tag>` first to generate metrics."

## Step 3 — Ask for Notes

Print the metrics table, then ask:
"Add 1–2 sentences about what changed or what you were testing (press Enter to skip):"

## Step 4 — Format Entry

Build the structured entry:

```markdown
## <tag> — <YYYY-MM-DD>

**Purpose:** <user notes or "(no notes)">

**Config:** <project.name> | scale_pos_weight=<value> | 60/20/20 split

**Results:**

| AUC-ROC | PR-AUC | Brier | Lift@1% | Lift@10% |
|---------|--------|-------|---------|----------|
| <from threshold_metrics_<tag>.csv> | ... | ... | ... | ... |

**Artifacts:** `output/models/<tag>/`
```

## Step 5 — Write Entry (Dedup Check)

Check if a stub from the hook already exists:
```bash
grep -n "^## <tag>" docs/EXPERIMENTATION.md
```

- If found: replace the stub block in-place with the full entry (use the line number to locate it)
- If not found: append the entry at the end of `docs/EXPERIMENTATION.md`

After writing:
```bash
git add docs/EXPERIMENTATION.md
```

## Step 6 — Confirm

Print:
```
Logged: docs/EXPERIMENTATION.md — ## <tag>
Staged. Run 'git commit -m "log: <tag> experiment results"' when ready.
```

Do NOT auto-commit.
