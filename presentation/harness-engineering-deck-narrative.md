# Harness Engineering Deck — Speaker Narrative

Companion narrative for `harness-engineering-deck-visual.html`. Each section is the punchy, discussive talk track for one slide.

---

## Slide 1 — Why an Auto-ML Harness Is Needed

> The bottleneck in modeling isn't model quality anymore. It's *search* and it's *memory*.

Every modeling problem opens up an unbounded space — features, families, encodings, imbalance strategies, hyperparameters — and they all interact. You can't brute-force it, and you can't intuit your way through it either. Teams end up settling for the first thing that looks good because the rest of the space is too expensive to explore manually.

The second problem is quieter but worse: **the experiments we *do* run rarely turn into durable knowledge.** Findings live in notebooks, decisions live in Slack, rationale lives in someone's head. Six months later, no one can tell you why a choice was made — or whether it would still hold today.

Our response is to treat model iteration as a *learning system*, not a sequence of one-off runs. Bound the search into governed rounds. Separate who proposes, who executes, who judges, and who synthesizes. Let a deterministic driver enforce the rules so the agent doesn't have to remember to behave. And persist everything — including the dead ends — as campaign memory.

The outcome we're after isn't just a better model. It's an auditable trail another data scientist can pick up cold.

---

## Slide 2 — Prior IP Commercial Benchmark

> This is the trajectory. Read it as a story about how *evidence from prior rounds shaped the next move* — not just a leaderboard.

We started at **22.21 val lift@1%** with a default CatBoost on hybrid features. Rounds 1–3 weren't about winning; they were about *establishing reference deltas* so later gains could be interpreted honestly.

Rounds 4–10 widened the search from one family to three, because the diagnostics said proxy-tuning CatBoost alone was slow and noisy. By round 14, a leakage-free three-family mean ensemble beat any single model — and rounds 16–22 quietly revealed that *weaker but different* models still contributed signal. The lesson: structural diversity beat more local tuning.

Then **round 25** — the breakthrough. We stopped tuning XGBoost for lift@1% and tuned it for AUC-ROC instead. That single decision added **+0.446** in one round, because XGB became more *complementary* in the ensemble tail.

What happened next is the part most decks omit: we spent **22 rounds stuck at 23.174.** Every small perturbation moved the weight solution away from that saddle. The evidence said this was a local optimum in weight space, not a feature problem. So round 48 swapped scipy/Nelder-Mead for differential evolution — a *global* optimizer — and immediately broke through to **23.26**.

The held-out test came in at **22.48**. The win was concentrated in the top 1% tail; AUC-ROC barely moved. That's the signature of a ranking improvement, not a calibration one — and the harness knew the difference because the metrics, the rationale, and the trajectory were all on disk.

---

## Slide 3 — Harness Design Patterns

> The harness isn't one clever trick. It's a set of constraints that shape how the agent is *allowed* to think.

Seven patterns, but they all answer the same question: *how do you keep a probabilistic agent honest across a long campaign?*

**Contract-first governance** — fix the problem, the data boundary, and the eval rules *before* the search starts. The system isn't allowed to redefine success mid-run.

**Producer is not verifier** — the planner, executor, reviewer, and historian are kept separate. The same model that proposed a change cannot be the one that signs off on it.

**Bounded autonomy** — write scope, repair attempts, and allowed action types are all explicit. Fast, but reversible.

**State on disk, not in chat** — campaign memory lives in artifacts. The next round reconstructs truth from files, not from whatever happens to be in context.

**Deterministic orchestration around probabilistic agents** — the driver owns the gates. Policy doesn't depend on the model remembering to behave.

**Escalate instead of improvise** — plateaus, anomalies, and contract conflicts route to explicit handling. When evidence is weak, the harness changes *mode* rather than guessing harder.

**Reason strategically, compute tactically** — agents frame the move; tools own the math. Language models are good at diagnosis. They are not the final numerical authority.

The throughline: constrain the behavior *before* any single experiment runs, and the campaign becomes repeatable by construction.

---

## Slide 4 — From Dataset and Metric to Autonomous Experiment Loop

> Claude Code is the agent doing the work. But the harness decides what *role* it's playing, what it can touch, what it must read, and how each output becomes persistent state.

It starts with the business owner — dataset, target, metric. Claude can help draft the contracts, but **initialization only begins after explicit human approval**. That gate is non-negotiable.

Once contracts are in force, the driver scaffolds state: `CAMPAIGN_STATE.json`, `results.tsv`, round directories. *Nothing* happens until that scaffolding exists.

Then the four Claude roles cycle:

- **Planner** reads contracts, memory, and the experiment tree, then writes the next experiment plan. It passes a plan-check before anything else moves.
- **Executor** applies one bounded change — only on approved files — and runs training.
- **Reviewer** forms an *independent* verdict from code, outputs, and mandatory tool runs. Same model family, different context, different job.
- **Historian** wakes up periodically — or on plateau — and synthesizes patterns, assumptions, and next-frontier strategy.

Every output lands in named artifacts: `NEXT_EXPERIMENT.md`, `run.log`, `REVIEW.md`, `DEAD_ENDS.md`, `PATTERN_BOOK.md`, `STRATEGY_MEMO.md`. **These artifacts are the loop's memory.** The next Planner doesn't start from whatever the model recalls — it starts from updated state on disk.

This is what makes it a governed workflow rather than a free-form agent session.

---

## Slide 5 — How the Harness Verifies Code, Strategy, and Results

> The harness does not prove a strategy is globally optimal. It proves that *every accepted step was scoped, checked, and justified.*

Verification happens at four moments, deliberately:

**Before execution** — the round itself has to be valid. Contracts approved. Plan schema clean. Action type allowed. Budget enforced. If any of that fails, the round never starts.

**During execution** — autonomy stays bounded. Write scope is restricted. Repair attempts are capped. The driver can inspect what's actually being committed. The loop stays reversible if a step turns out to be bad.

**After execution** — the verdict has to come from numbers, not narrative. Metrics are parsed from artifacts. Mandatory tools must run. Bootstrap confidence and anomaly checks fire. And the noise-floor logic blocks trivial movement from being called *progress* — which is what kept us honest during the 22-round plateau.

**Across rounds** — integrity is protected campaign-wide. Discards roll back cleanly. Anomalies pause the loop instead of being papered over. Contract conflicts escalate to humans.

The trust claim here is precise. It is *not* "the harness always finds the best model." It is "every accepted step survived scoped execution, numerical checks, and independent review." That's a much stronger and much more *defensible* claim.

---

## Slide 6 — How the Harness Reuses History and Logs

> The system does not just log the past. It *operationalizes* the past.

Four stages, each owned by a different role, each producing different artifacts:

**Raw execution output** — what the run literally produces. `train.py`, `run.log`, tool outputs. Faithful, but not yet useful as memory.

**Normalized round memory** — the Reviewer turns one round into something meaningful: `results.tsv`, `REVIEW.md`, `CAMPAIGN_JOURNAL.md`, `DEAD_ENDS.md`, `NOTEBOOK.md`, `ASSUMPTION_REGISTER.md`. This is where "what just happened" becomes "what one round now means."

**Cross-round synthesis** — the Historian zooms out: `PATTERN_BOOK.md`, `STRATEGY_MEMO.md`, `UNEXPLORED_TECHNIQUES.md`, `EXPERIMENT_TREE.json`. This is where many rounds reveal what no single round can — recurring failure modes, structural plateaus, branches we never tried.

**Next planning decision** — the Planner consumes all of it. What to avoid. What to test. What bottleneck to address. What branch to deepen. What assumption to validate.

That last step is the payoff. Without it, you have a journal. *With* it, you have a system that gets sharper every round — and a record any future data scientist can pick up cold.

---

## Slide 7 — How the Harness Balances Exploration and Exploitation

> The harness does not search exhaustively. It allocates scarce experiment budget *adaptively*, using evidence from prior rounds.

Three components:

**Representation.** Experiments live in an explicit *tree* — nodes carry commit, parent, strategy class, metric, verdict. The Planner doesn't browse history informally; it reads a structured search surface. Best branch point is always the strongest kept commit.

**Scoring.** Strategy classes are scored with UCB1: `mean_delta + c * sqrt(ln N / n)`. Observed improvement plus an exploration bonus. Untried classes get effectively infinite priority until they're sampled at least once. Classes producing only noise-floor movement get penalized. And the Historian can override naive UCB preference when the campaign is stuck for a *structural* reason rather than a sampling one.

**Phase policy.** Budget is split adaptively:

- **0–30% — diversify:** try untried strategy classes before committing.
- **30–70% — deepen:** follow the highest-UCB branches.
- **70–100% — exploit:** refine, ensemble, or final-tune the champion — while reserving a small moonshot budget so we don't go fully greedy.

The behavior is explicit and inspectable. Diversify early. Deepen in the middle. Exploit late. And down-weight branches that are only producing noise-level movement. That's how the same harness that took *22 rounds* to recognize a plateau also took *one round* to escape it — once the evidence said "this is a weight landscape problem, not a feature problem."
