# Campaign Template

Copy this directory to create a new campaign:

```bash
cp -r runner/campaign_template campaigns/<your-campaign-name>
cd campaigns/<your-campaign-name>
# Edit contracts/ to define your problem, data, and evaluation protocol
# Edit train.py with your baseline model
```

## Directory structure

```
campaigns/<name>/
├── contracts/           # G1/G2/G3 gates — define problem, data, eval
│   ├── PROBLEM_CONTRACT.md   # What you're solving, success criteria
│   ├── DATA_CONTRACT.md      # Dataset schema, column whitelist
│   ├── EVAL_PROTOCOL.md      # Primary metric, mandatory tools, budgets
│   ├── PRIORS.md             # Known good/bad from prior campaigns
│   ├── STRATEGY_GUIDE.md     # ML planning heuristics
│   └── FINAL_REPORT.md       # End-of-campaign report template
├── state/               # Auto-managed by the driver — do NOT edit manually
│   └── .gitkeep
└── train.py             # The ONLY file the Executor edits
```

## Running

```bash
runner/run_round.sh init --campaign-dir campaigns/<your-campaign-name>
runner/run_round.sh plan-check --campaign-dir campaigns/<your-campaign-name>
# ... etc
```

## Autonomous Operation

Once contracts are signed (G1/G2/G3 — `approved_at` is non-null in each):

```bash
# Interactive — observe and intervene
# Open Claude Code in repo root, then say:
# "Read runner/roles/orchestrator.md and run the campaign at campaigns/<your-name>"

# Headless — fully autonomous
claude -p "Read runner/roles/orchestrator.md and run the campaign at campaigns/<your-name>. Run autonomously until a stop condition." --dangerously-skip-permissions

# Resume after interruption
# "Read runner/roles/orchestrator.md and resume campaigns/<your-name> with --resume"
```

The orchestrator reads all role prompts, executes each phase, calls the driver for
validation between phases, and manages halt/pause/budget conditions automatically.
