# Copilot Instructions for auto_train

This repository is an autonomous ML experiment system. When working here:

1. Always read `program.md` first for the full experiment protocol.
2. Only modify `train.py`. Never modify `prepare.py` or data files.
3. The goal is to maximize `val_pr_auc` on the credit card fraud dataset.
4. Run experiments in a loop: edit → commit → run → evaluate → keep/discard → repeat.
5. **Experiment limit: 20** (or `$MAX_EXPERIMENTS`). Stop when limit reached or plateau detected.
6. Log all experiments to `results.tsv` in tab-separated format.
7. When stopping: summarize results, report best val_pr_auc, list top 3 approaches.
