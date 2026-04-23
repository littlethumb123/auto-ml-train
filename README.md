# auto-ml-train

Autonomous ML experimentation on the credit-card fraud pipeline (`prepare.py` + root `train.py`).

## Quick links

| Topic | Where |
|--------|--------|
| **How to run the new harness (contracts, driver, roles)** | [`runner/README.md`](runner/README.md) |
| **Short agent entry (what to read first)** | [`runner/RUNNER.md`](runner/RUNNER.md) |
| **Repo rules for tools / invariants** | [`AGENTS.md`](AGENTS.md) |

## Legacy pointer

Root `program.md` redirects to `runner/RUNNER.md`. Experiment logging is done via `log.py` and `runner/run_round.sh review-finalize` (not `abes_engine.py`).

## Data and training

```bash
pip install -r requirements.txt
python3 prepare.py          # if data/splits need refreshing
python3 train.py            # single experiment (stdout + metrics)
```

See **`runner/README.md`** for the full **Planner → Executor → Reviewer** loop and `./runner/run_round.sh` usage.
