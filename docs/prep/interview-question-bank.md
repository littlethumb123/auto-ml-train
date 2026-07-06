# Interview Question Bank — Agentic-Engineering Deep Dive

**Companion to:** `harness-technical-report.md` in this directory.
**Assumed interviewer profile:** Senior agentic engineer, mix of generic industry knowledge (LangGraph, DSPy, AlphaEvolve, AutoGen, CrewAI) and applied-ML/AutoML platform framing.
**Question flavors:** (A) Architecture & design trade-offs — 17 questions. (B) Failure modes & production caveats — 17 questions. Total: **34**.

Each question is presented as:
- **Q** — how the interviewer would phrase it.
- **What they're probing** — the underlying concern (so you can tell if you're addressing it).
- **Model answer** — bullet-form talking points anchored in the actual harness. Use these as scaffolding, not scripts.
- **Follow-up traps** — common second-turn probes and how to handle them.

---

## Section A — Architecture & Design Trade-offs

### A1. Walk me through the top-level architecture. What are the pieces, and what does each one own?

**What they're probing:** Can you narrate a system cleanly? Do you know where responsibility boundaries actually are?

**Model answer:**
- Three layers: a **bash outer wrapper** (`run_campaign.sh`), a **stateless Python driver** (`runner_driver.py`) invoked per stage, and an **orchestrator prompt** running inside a Claude Code session that dispatches the four LLM roles.
- The LLM never invokes the driver; the orchestrator prompt does. The driver never invokes the LLM. This inversion is deliberate — it keeps every stage boundary a disk-persisted commit point that a Python program can re-enter after a crash.
- Four roles: **Planner** (writes `NEXT_EXPERIMENT.md`), **Executor** (edits `train.py`, commits, runs), **Reviewer** (verdict + REVIEW.md + CAMPAIGN_JOURNAL.md), **Historian** (periodic, rewrites `STRATEGY_MEMO.md`, appends to `PATTERN_BOOK.md`).
- Contracts under `campaigns/<name>/contracts/` are read-only during experiments — they define the problem, data schema, and evaluation protocol. Changing them requires a C3 escalation with human `approved_at`.

**Follow-up traps:**
- *"Why bash wrapper AND Python driver AND orchestrator prompt — that's three layers of dispatch."* → Each solves a distinct failure mode. Bash handles Claude-process crashes (relaunch loop). Python handles state validation and gates (unit-testable, no LLM). Orchestrator prompt handles the round-level state machine within a session. Collapsing any two loses either testability or recovery.

---

### A2. Why files on disk for inter-role communication instead of a shared context window?

**What they're probing:** Do you understand the epistemic argument for role blindness, or did you cargo-cult it from some paper?

**Model answer:**
- **Disk-as-truth prevents context rot.** In a long shared context, later turns anchor on earlier assertions — an Executor that saw a Planner rationalize an approach will implicitly defend it in run.log. Blind Reviewer Phase 1 (reads only outputs + contract + tool receipts, not the plan) breaks that.
- **Crash recovery.** After any stage, all state is on disk in versioned files. Relaunching the wrapper calls `resume-phase` which walks four disk-artifact heuristics to determine which stage to resume. Zero scheduler state to reconcile.
- **Auditability.** Every run leaves a `git log` + `REVIEW.md` + `driver_events.jsonl` that a human can post-mortem without replaying the LLM.
- **Cost.** Fresh contexts per role are shorter than one growing conversation — cheaper.

**Follow-up traps:**
- *"But you lose the LLM's ability to notice its own past mistakes."* → No — those are surfaced through explicit artifacts: `DEAD_ENDS.md`, `PATTERN_BOOK.md`, `ASSUMPTION_REGISTER.md`. The Planner is required to read them. The advantage: the surfacing is auditable and testable, not implicit.

---

### A3. Four roles. Why not one, or two, or ten?

**What they're probing:** Have you actually thought about the epistemic decomposition, or is this a magic number?

**Model answer:**
- Each role owns a **distinct epistemic task** that benefits from being blind to the others: hypothesis generation, controlled implementation, independent verification, cross-round pattern synthesis.
- Fewer collapses tasks that should stay separate. **1 mega-agent** collapses verification into implementation → sycophancy. **2 (Actor/Critic)** loses the Historian's cross-round pattern learning.
- More fragments context without adding independent perspective. We tried a "Critic" between Reviewer and Historian in an early draft — Reviewer Phase 1 blind + Historian's cross-round audit already covered its purpose. Dropped.
- **10 roles** starts to look like AutoGen "town halls" — coordination overhead dominates and errors compound.

**Follow-up traps:**
- *"Why not add an adversarial Reviewer 2 for independent verification?"* → Considered. Doubles per-round LLM cost. In our setup the Reviewer's Phase-1 blind pass plus the driver's mechanical noise-floor gate cover the main sycophancy risk. In a higher-stakes domain (medical, legal) we would add it.

---

### A4. How do you enforce that the Executor doesn't modify contracts or `prepare.py`?

**What they're probing:** Do you rely on the LLM to obey a prompt (bad), or on mechanical enforcement (good)?

**Model answer:**
- **Two layers.** Contractual: identity spec in `runner/roles/executor.md` says "never modify prepare.py / contracts/ / roles/ / tools/". Mechanical: `execute_finalize()` in the driver parses the commit diff and runs `_path_in_write_scope()` against a hardcoded `_READ_ONLY_PREFIXES` list.
- Any violation forces `synthetic_verdict: "malformed"` regardless of what the Executor claims. The Reviewer never even runs.
- The commit itself is preserved (rolled back by the discard rollback), so we have a forensic trail.

**Follow-up traps:**
- *"What if the Executor `git checkout -- prepare.py` between edits and commit?"* → The write-scope check runs on the diff of the commit, not the working tree. If the commit doesn't include prepare.py it's fine. If we cared about *runtime* modification of read-only files, we'd need cgroups or a filesystem-level guard — which is out of scope for our current threat model (a role in the same repo, not adversarial).

---

### A5. Walk me through the mandatory tool receipt system. Why can't you just trust the Reviewer's "I ran the tool"?

**What they're probing:** Have you experienced the trust problem with LLMs claiming things they didn't do?

**Model answer:**
- Documented history: in the June 2026 self-audit (docs/reflections/2026-06-19-harness-self-audit.md), P0-3 was the finding that Reviewers were declaring `keep` without having run `anomaly` or `bootstrap_ci`.
- Fix: **F3 receipt system.** `runner.tools.run.execute()` is a wrapper that runs any tool as a subprocess, captures `exit_code`, computes SHA-256[:16] `args_hash` of the canonical JSON args, and emits a `tool_run` event to `driver_events.jsonl` with `start_ts` / `end_ts`.
- At `review_finalize`, the driver reads the JSONL, filters `event == "tool_run"` with `start_ts >= round_started_at` (stamped at plan_check) and `exit_code == 0`. Any mandatory tool without a matching receipt → verdict override to `malformed` + `tools_ran_unverified` event.
- **The Reviewer cannot fake this without forging both a subprocess exit trace and a matching args_hash** — which requires actually running the tool.

**Follow-up traps:**
- *"Why not sign the receipts cryptographically?"* → Theatre — the driver is trusted. The `args_hash` is anti-tampering enough for the threat model.
- *"What if the tool runs but the receipt write fails (disk full, permission)?"* → The write is non-critical (`_emit_event` silently skips). The consequence is a false-negative F3 fail → `malformed`. Preferable to false-positive.

---

### A6. Why UCB1 over `action_type` classes? Why not just have the Planner reason about it in prose?

**What they're probing:** Do you know why we mix deterministic algorithms with LLM reasoning at all?

**Model answer:**
- **Right level of abstraction.** UCB1 wants scalar reward per arm. `action_type` (A_model | A_feature | A_hp | ...) gives us that: mean Δ primary_metric per class over history. Individual HPs would be too many arms (curse of dimensionality) and too correlated. Prose alone gives no exploration guarantee.
- **UCB1 formula:** `mean_delta + c * sqrt(ln(N) / n_i)`, with untried arms → `inf`. Plus diminishing-returns detection: last 2 deltas both < noise_floor → halve UCB1 score for that class.
- **LLM still does the *within-class* selection** — which specific HPs, which specific features. UCB1 tells it "you've overused A_hp lately, try A_feature"; the LLM chooses which feature to build.
- Rebuild-from-`results.tsv` (F5) means the tree is derivable from ground truth on init — no drift.

**Follow-up traps:**
- *"Why not Thompson sampling or GP-UCB?"* → n_arms is small (5–7), we have no natural prior variance model, and UCB1's parameter-free simplicity is a feature at this scale. If we had 30 arms and cared about smoothness, we'd revisit.

---

### A7. Why markdown + YAML frontmatter for state, instead of a real database?

**What they're probing:** Are you a "reach for Postgres by default" person, or can you match tools to scale?

**Model answer:**
- **Scale.** Campaigns are ~20 rounds. `results.tsv` at n=20 is faster to `sort` than to `SELECT`.
- **Diffability.** Every state change lands in git. A schema change on `REVIEW.md` shows up in `git diff` and can be rolled back. Postgres migrations are heavier and less legible.
- **Human-in-the-loop friction.** A human reading `PATTERN_BOOK.md` in a markdown viewer costs zero. A human reading a Postgres row via a custom UI costs everything.
- **Safety.** Schema validators (`tools/schema.py`) plus F2 mtime checks give us typed-storage safety without giving up readability.
- **Explicit tradeoff:** no concurrent writes, no cross-campaign queries, no live subscribers. All acceptable — the harness is single-writer per campaign.

**Follow-up traps:**
- *"What if you needed to run 100 campaigns in parallel?"* → Different problem. At 100 concurrent campaigns you'd want (a) a job scheduler on top of the wrapper, (b) probably a `campaign_index.jsonl` at the top level, and (c) a dashboard reading each campaign's `results.tsv`. But those additions leave the per-campaign harness unchanged — you're building around it, not rewriting it.

---

### A8. Two-phase Reviewer with binding Phase-1 verdict — is that not just theater? Phase 2 can still write persuasive prose.

**What they're probing:** Do you know the mechanical vs prompt-level enforcement distinction?

**Model answer:**
- The Phase-1-is-binding rule is a **prompt-level** norm — it can fail if the Reviewer decides to flip. That's why it's paired with a **driver-level mechanical override**: the noise-floor gate. If `verdict == "keep"` and `|Δ| < noise_floor` from `EVAL_PROTOCOL.md`, the driver overrides to `discard` with a `noise_floor_override` string in the result. No LLM involvement.
- Phase 1 blindness has a different value: it makes the *plan comparison* honest — the Reviewer's independent assessment exists on disk before it sees the hypothesis, so the plan-vs-result narrative can't be retconned.
- Empirically, in otto-r2 the noise-floor gate fired in `p0-fix-smoke` Round 3 (Δ=+0.001331, Reviewer said keep, driver said discard) — verified in that campaign's REVIEW.md.

**Follow-up traps:**
- *"But the Reviewer sees `noise_floor` in EVAL_PROTOCOL.md — it can just lie about Δ."* → It can't, because the driver recomputes Δ from `results.tsv` at `review_finalize` time using the metric column, not from Reviewer prose. And `reproduce_check` cross-validates from `y_val_*.npy` artifacts.

---

### A9. Why one commit per experiment, and why on a dedicated branch?

**What they're probing:** Do you understand the operational value of a clean git history for agentic systems?

**Model answer:**
- **One commit per experiment** gives an atomic unit of rollback: `git reset --hard HEAD~1` undoes exactly one experiment.
- **Dedicated `campaign/<name>` branch** isolates experimentation from `main` — a rollback doesn't touch shared infrastructure or other campaigns.
- **Human-legible history.** `git log` on the campaign branch reads as a chronological experiment log matching `results.tsv` row order.
- **Bisectability.** If we suspect a regression was introduced 5 rounds ago, `git bisect` on the campaign branch works.

**Follow-up traps:**
- *"Why not branch per experiment?"* → Considered. Rejected because it fragments the experiment log — the linear branch is more legible for post-mortems, and rollback is cleaner than merge-abort.
- *"What if the harness is running on a machine where the git repo is shared with other users?"* → The write-scope check + campaign branch discipline mean concurrent development on `main` doesn't collide. Concurrent writes from other harnesses to the same campaign branch would collide — that's a single-writer invariant we don't currently enforce beyond convention.

---

### A10. How does the Historian know what to do? What triggers it, what does it produce, and how do you keep it from drifting into unfocused prose?

**What they're probing:** Do you know how to make an agent's job structured enough to be auditable?

**Model answer:**
- **Trigger:** `review_finalize` sets `historian_trigger_pending: true` when `rounds_since_last_historian >= historian_interval` (default 10) OR `consecutive_discards >= plateau_trigger` (default 3).
- **Output structure:** `STRATEGY_MEMO.md` must contain four required sections — Trajectory Narrative, Pattern Extraction, Assumption Audit, Bottleneck Diagnosis — each ≥80 characters of non-placeholder content.
- **Enforced by F1** (`_verify_strategy_memo`): if any section is missing / too short / matches a placeholder regex → `historian_skipped` event, `historian_trigger_pending` stays true for retry.
- **Bottleneck category is mandated exclusive-choice:** one of `model_quality | optimizer_quality | data_quality | eval_quality | feature_representation`. Forces the Historian to commit to a diagnosis instead of hedging.
- **Assumption audit** requires updating `last_audited` on every entry assessed, even if no other field changes — the timestamp is falsifiable.

**Follow-up traps:**
- *"How do you prevent PATTERN_BOOK.md from growing to 1000 patterns?"* → Historian is prompted to update confidence and status (`active | inapplicable | dead end`) rather than always append. Patterns that go inapplicable are marked, not deleted — preserves history.
- *"What if the Historian and Planner disagree about the bottleneck?"* → Planner reads STRATEGY_MEMO.md but is not bound by it; its rationalization table must independently justify the chosen action. Legitimate disagreement is expected and healthy.

---

### A11. Why not use LangGraph? It has state machines built in.

**What they're probing:** Have you thought through framework choices, or defaulted?

**Model answer:**
- **LangGraph's checkpointing is designed for one long-running agent state.** Our four roles share nothing but files — no shared context to checkpoint.
- LangGraph would model our stages as graph nodes with typed edges. We'd end up wrapping LangGraph state around what is already a disk-persisted state, adding a compilation step for a state machine we can express as a shell dispatch.
- Stages we care about are unit-testable Python functions returning JSON. LangGraph's abstraction wants them to be graph nodes, which is a lossy conversion for our use case.
- **We considered LangGraph and passed.** Not because it's bad — because it's optimized for a different shape of agent (single conversation, tool-heavy, streaming).

**Follow-up traps:**
- *"But you'd get a nice DAG visualization and standard tracing."* → We get diffable state files and greppable event JSONL. Different tradeoff. For the audit-heavy domain we're in, the file-based approach is easier to review post-hoc.

---

### A12. DSPy vs your approach — why isn't the Planner a DSPy `Module`?

**What they're probing:** Do you know when prompt optimization is a fit vs an active harm?

**Model answer:**
- **DSPy optimizes prompts against a metric.** Our metric is the eval protocol's primary metric, which is defined in `EVAL_PROTOCOL.md` and is *contractually immutable*. DSPy's optimizer wants to co-adapt the prompt with the metric — exactly what our sticky-contract invariant forbids.
- More concretely: DSPy compiling the Planner would treat "get better val_log_loss" as the objective and adjust prompts to that end. That's directly the "spec-gaming" failure mode we designed C3 approval to prevent.
- The Planner's job isn't to optimize prompt structure — it's to reason about *what experiment to run next given a policy hierarchy encoded in prompts humans have vetted*.
- **Where DSPy would be a fit:** if we wanted to compile the Reviewer's rationalization-table generation to a Signature-based module for reliability, that would be reasonable — but it's a small local win vs a substantial refactor.

**Follow-up traps:**
- *"What if you locked the eval metric and let DSPy optimize the Planner's prompt only?"* → Reasonable in principle. The remaining concern: DSPy would optimize toward *observed* Δ improvements, which would push the Planner toward safe, incremental actions — anti-exploration. Our UCB1 explicitly rewards under-explored action classes. We'd lose that.

---

### A13. Why treat contracts as sticky and require human approval? Why not let the Planner refine them if it sees a better objective?

**What they're probing:** Do you understand the alignment argument for pinning down the fitness function?

**Model answer:**
- **The contract IS the ground truth.** If the Planner can rewrite the eval protocol, "improvement" becomes whatever the Planner wants it to be — the classic Goodhart's law / spec-gaming failure.
- **AutoML systems that let the agent redefine success collapse.** We've seen it: allow the Planner to tighten a floor, and after 3 rounds the "champion" is a model optimized against a subtly weaker constraint.
- **The C3 escalation is a formal channel** for legitimate changes: Planner writes `escalation: C3`, driver halts (`pause_c3`), human runs `contract_diff` (which risk-classifies the change), reviews, sets `approved_at`. Restart resumes from plan phase.
- **Contract diff tool** is deterministic — YAML frontmatter flattened to dotted paths, comparison field-by-field, `_HIGH_RISK_FIELDS` set-based risk classification.

**Follow-up traps:**
- *"But sometimes the metric IS wrong and the agent should say so."* → That's exactly what C3 escalation is for. The Planner CAN propose a change — it just can't unilaterally enact it. This is the classic "let the system flag concerns without letting the system change the rules" pattern.

---

### A14. The Planner reads a lot of state files. Doesn't context grow linearly with rounds?

**What they're probing:** Do you know how to keep prompt cost bounded as the campaign progresses?

**Model answer:**
- **Most state files are bounded.** `PATTERN_BOOK.md` grows only when the Historian adds a pattern (~1 per 3-5 rounds); `DEAD_ENDS.md` similarly. `results.tsv` grows one row per round, ~200 bytes.
- **The big ones are `REVIEW.md` and `CAMPAIGN_JOURNAL.md`** — one block per round. At round 20 they're ~40–80KB total, still cheap.
- **`STRATEGY_MEMO.md` is rewritten (not appended) each Historian run.** So its size is bounded by whatever the Historian chooses to summarize — an intentional summarization gate.
- **`TOKEN_SUMMARY.txt`** is a per-round token digest — the Planner can see approximate context sizes and reason about them.
- **Anthropic prompt cache TTL** is ~5 minutes; the `--resume <session_id>` wrapper design tries to keep sessions warm between rounds so we're not re-reading the state cold every time.
- **Explicit tradeoff:** we don't compress or summarize state on the fly. If campaigns grew to 200 rounds, we'd add a per-N-rounds summarization step. At 20 rounds it doesn't earn its complexity.

**Follow-up traps:**
- *"What's your worst-case Planner input size?"* → Empirically, ~40k tokens by round 20 in otto-r2. Well within Claude's context window; the more relevant constraint is prompt cache warmth.

---

### A15. Why hardcode `max_repair_attempts == 2` in the schema validator?

**What they're probing:** Do you make principled parameter choices with data behind them?

**Model answer:**
- **Empirical:** attempts 3+ are almost always thrashing on the same bug. The Executor either fixes it in 1–2 tries or has the wrong mental model and needs the round declared crash so the Reviewer can diagnose.
- **Hard schema check** (not just a default) prevents per-campaign drift — someone editing an EVAL_PROTOCOL.md to `max_repair_attempts: 5` gets a validation error at `init_campaign()`.
- **Design principle:** parameters that we've decided globally shouldn't be tunable per-campaign belong in the schema validator, not in the config file with a default. Otherwise every campaign eventually gets a bespoke config.

**Follow-up traps:**
- *"So there's no way to escape it for a genuine edge case?"* → Correct — you'd have to edit `tools/schema.py`. That's the point: the escape hatch requires touching harness code, which shows up in git and warrants review.

---

### A16. Walk me through crash recovery. What state matters, what doesn't?

**What they're probing:** Do you actually understand your own recovery story or is it "well, it should work"?

**Model answer:**
- **Level 1: wrapper.** `run_campaign.sh` is a while-loop. If Claude exits non-zero, the wrapper reads `CAMPAIGN_STATE.json` and launches a new Claude session, passing `--resume <session_id>` (heuristically parsed from `wrapper.log`).
- **Level 2: orchestrator prompt.** New session starts by re-reading `CAMPAIGN_STATE.json` and calling `run_round.sh resume-phase`.
- **Level 3: `determine_resume_phase()`.** Walks four disk-artifact heuristics in priority order:
  1. `CAMPAIGN_JOURNAL.md` has `## Round <current>` entry → Reviewer done → resume from `historian` or `next_round`.
  2. `run.log` has `RUN_COMPLETE|RUN_FAILED` sentinel → Executor done → resume from `reviewer`.
  3. `NEXT_EXPERIMENT.md` exists → Planner done → resume from `executor`.
  4. Else → resume from `planner`.
- **What state matters:** `CAMPAIGN_STATE.json` (counters), the three or four artifact files above, git HEAD.
- **What doesn't matter:** the LLM's in-memory chat state. It's all reconstructed from disk. This is the payoff of disk-as-truth.
- **Double-plateau hard stop.** `consecutive_discards >= 6` (2× the `plateau_trigger`) → wrapper exits, logs "double-plateau detected." Prevents infinite thrash.

**Follow-up traps:**
- *"What if `NEXT_EXPERIMENT.md` was half-written when the crash happened?"* → The `plan_check` YAML schema validator will fail on incomplete frontmatter → returns `malformed` → orchestrator loops back to Planner. Cost: one wasted Planner invocation. Value: no silent corruption.

---

### A17. If you had to add real-time monitoring (dashboards, alerts), where would you plug in?

**What they're probing:** Can you extend the architecture without breaking its shape?

**Model answer:**
- **Read side: `driver_events.jsonl` is already the source of truth.** A sidecar process tailing that file gives you every state transition in real time. Filter by `event` type.
- **Push side:** add a hook in `_emit_event()` in `runner_driver.py` — if a `WEBHOOK_URL` env var is set, POST the event.
- **Metrics:** the raw event stream contains everything for dashboards — round durations, verdict rates, tool exit codes, `consecutive_discards`, budget usage. A small Prometheus exporter reading the JSONL would surface all of it.
- **Alerts:** the events that matter are `halt_loop: true`, `reviewer_artifacts_all_missing`, `historian_skipped`. These are already emitted; you'd just route them.
- **Design win:** all of this is additive. The event bus was designed to be read by future subscribers even though today it's only read by `review_finalize`'s F3 check.

**Follow-up traps:**
- *"You said 'zero infra' was a design choice — this proposal adds infra."* → Yes, and that's fine because it's *optional* infra reading a bus that already exists. The zero-infra property is that the harness itself needs nothing to run.

---

## Section B — Failure Modes & Production Caveats

### B1. How do you detect if the Executor lied about the metrics in its run.log?

**What they're probing:** Do you have defense-in-depth for one of the highest-risk LLM behaviors?

**Model answer:**
- **`reproduce_check` tool.** After the run, it loads `y_val_true.npy` and `y_val_prob.npy` from the artifacts dir, recomputes the metric using `shared/metrics.py`, and cross-checks against the value parsed from `run.log`. Tolerance 0.001.
- **Output:** `{artifacts_valid, mismatches: [{metric, reported, recomputed, delta}], passed}`. A delta > 0.01 on a critical metric is grounds for `malformed`.
- **Why this catches lying:** the Executor would have to fabricate `run.log` AND fabricate consistent `.npy` files. The `.npy` files are numeric arrays — much harder to fabricate than log strings.
- **Known gap:** `reproduce_check` is hardcoded for binary classification shape (`y_prob: (N,)`). Multiclass campaigns get `artifacts_valid: false` on every round (known false negative). Manual verification is done inline in REVIEW.md.

**Follow-up traps:**
- *"So on multiclass campaigns you have no automated defense?"* → We have `run.log` parsing + Reviewer's independent recomputation from artifacts (documented in REVIEW.md). Fixing the tool is a two-line change we've deferred because campaigns are single-Reviewer and audit-heavy anyway.

---

### B2. What happens if the Historian generates a plausible-sounding but wrong pattern into `PATTERN_BOOK.md`?

**What they're probing:** Have you thought about pollution of long-term memory?

**Model answer:**
- **Structural constraints reduce the risk.** Pattern entries require `Supporting evidence:` with specific round numbers + metric values; `Confidence:` (high/medium/low); `Status:` (active/inapplicable/dead end); `Implication for Planner:`. A pattern without evidence fails the structural check.
- **Assumption audit** — the Historian must re-audit patterns and assumptions on every invocation. A pattern proven wrong gets `Status: inapplicable` with an updated `Evidence against:` block.
- **Blast radius is bounded.** A bad pattern misleads at worst until the next Historian run (default 10 rounds). If it's actively harmful (e.g., "always avoid A_hp"), the stuck-check + UCB1 diversity pressure will still force exploration.
- **Real case:** P-1 in otto-r2 was initially scoped "CatBoost depth≥10 blocks FE augmentations." After R10 (XGBoost champion improved with same FE approach), Historian scope-updated P-1 to CatBoost-specific. Pattern-book self-corrects.

**Follow-up traps:**
- *"What if the Historian is systematically over-confident?"* → We haven't observed this empirically, but the mitigation would be adding an adversarial Reviewer-2 pass over new patterns. Deferred as cost vs benefit.

---

### B3. Machine load was 95/32 cores in R13. How does the harness handle environmental problems it can't control?

**What they're probing:** Do you have a story for adapting to external state, or does the harness assume clean-room?

**Model answer:**
- **Detection is post-hoc.** No pre-flight resource gate in the driver today. R13 hit hard timeout because per-trial wall-clock hit ~900s under load.
- **Reviewer diagnoses environmental vs code failure.** In R13, the Reviewer ran a smoke test of the early-stopping code to confirm it worked in isolation, then attributed the crash to load. Distinct from R12 where the code was broken.
- **Learning encoded as Pattern P-4.** "Machine load > 8/32 cores blocks multi-trial Optuna within 1800s. Before Optuna experiment: check `uptime`; if load > 8: reduce N_TRIALS ≤ 5 and proxy_timeout ≤ 300s, OR use N_TRIALS=1 fixed HP."
- **Planner consults it.** R14's NEXT_EXPERIMENT.md explicitly reads: *"Machine load: 76/32 cores (P-4 pattern active). Multi-trial Optuna infeasible (A_hp blocked by stuck-check AND load constraint). A_ensemble OOF stacking would also exceed timeout under this load."* Planner picks a load-resilient action instead.
- **Gap.** Pre-flight `uptime` check in `plan_check` would surface infeasible plans before burning 1800s. Natural extension.

**Follow-up traps:**
- *"So the first time you learn about a new environmental problem, you have to fail once?"* → Yes. That's a legitimate limitation. The alternative — pre-guess every environmental constraint — either under-covers or over-restricts. Pattern-based learning trades one failed round for a durable adaptation.

---

### B4. R11 selected `reg_lambda ≈ 0.001` from log-uniform in (0.0001, 10), overfit catastrophically. Why doesn't the harness prevent this?

**What they're probing:** Do you know when the harness should intervene vs when it's rightly the Planner's responsibility?

**Model answer:**
- **Search-space quality is Planner-level, not driver-level.** The driver doesn't know that `reg_lambda ≈ 0` is dangerous — that's ML-domain knowledge.
- **The failure surfaced through the standard cascade:** train.py ran, produced metrics, Reviewer computed Δ=+0.021634 (regression), flagged `discard`.
- **Learning:** DEAD_ENDS entry 4 + Pattern P-5: *"Always constrain XGBoost reg_lambda ≥ 0.5 in any HPO search."*
- **Next Planner run reads DEAD_ENDS.** Any future plan proposing log-uniform reg_lambda near zero would trigger dead-end collision at `plan_check` (fuzzy word overlap check).
- **Deeper answer:** the harness enforces *process* (contracts sticky, gates fire, artifacts written), not ML *content*. Encoding ML knowledge into the driver would make the driver ML-domain-specific, undoing generality.

**Follow-up traps:**
- *"So the harness accepts one catastrophic experiment per novel search-space mistake?"* → Yes. The tradeoff is preserving generality across problem domains. If we cared about specific domain knowledge in a single problem area (e.g., "XGBoost HPO"), we'd add a domain-specific pre-flight validator — but as a separate module, not in the core driver.

---

### B5. R12 was a silent XGBoost 3.x API change. How could the harness detect that class of failure faster?

**What they're probing:** Do you have a story for dependency drift?

**Model answer:**
- **Current detection is post-hoc.** run.log empty + hard timeout → Reviewer performs manual API audit. Two repair attempts exhausted before crash declared.
- **Learning captured in DEAD_ENDS #5** with the correct API + a smoke test (`XGBClassifier with callbacks=[EarlyStopping(rounds=5)] stops at best_iteration=29`).
- **Possible mitigations:**
  1. **Pre-flight smoke tests** in the campaign template for critical operations. Cheap; each new library integration adds a smoke test.
  2. **`substantive-diff` check** already catches no-op commits; a related check could flag "the code claims to use early stopping but the trained model has n_estimators trees, suggesting it didn't stop."
  3. **Pin library versions in the campaign's `requirements.txt` / `environment.yml`** — we don't do this today; XGBoost 3.x was the environment's version. Pinning would have prevented R12.
- **Real production answer:** pin versions per campaign + smoke test per critical library call.

**Follow-up traps:**
- *"You have `**kwargs` absorbing bad arguments silently everywhere in scikit-learn-style APIs. This will happen again."* → Yes. The general fix is `strict=True` mode where available, or wrapping constructors with argument validators. Neither is done today; both are natural next steps.

---

### B6. What is the sycophancy failure mode you're most afraid of, and why doesn't it happen?

**What they're probing:** Have you identified the failure you *most* need to prevent, or are you scattered?

**Model answer:**
- **The one I'm most afraid of:** Reviewer sees a `keep`-eligible Δ (marginally above noise_floor), then in Phase 2 sees a compelling narrative in the plan, and writes a `keep` with prose like "this represents a meaningful directional signal." Champion drift accumulates over rounds.
- **Three defenses layered:**
  1. **Phase 1 blindness** — verdict is set before reading the plan.
  2. **Mechanical noise-floor gate** — driver overrides `keep` to `discard` if `|Δ| < noise_floor`, in Python, no LLM.
  3. **Forbidden phrases** in the Reviewer prompt — "shows promise," "encouraging direction," "marginal gain" followed by keep are explicitly disallowed.
  4. **Adversarial verification via dead-end register** — a pattern like "champion drift after 3 consecutive marginal keeps" would (hypothetically) get flagged by the Historian, but this is not implemented today.
- **What still slips:** a Reviewer with a technically-correct Δ above noise_floor but a subtly bad experiment design. Depends on the Reviewer's independent code audit — human-comparable ML judgment.

**Follow-up traps:**
- *"How do you know your defenses actually work?"* → `p0-fix-smoke` is the answer. It's designed to force the noise-floor override to fire (inflated `min_improvement`); verified in its REVIEW.md Round 3.

---

### B7. Two consecutive `malformed` verdicts halt the loop. Why halt instead of retry?

**What they're probing:** Do you know when to fail loudly vs recover silently?

**Model answer:**
- **Two consecutive malformed = a structural pathology,** not a transient error. Either the Reviewer prompt is broken, an artifact schema was corrupted, or a role is deadlocked.
- **Retrying would burn budget on a symptom.** The right response is human diagnosis.
- **The `halt_loop: true` fires plus a `mandatory_gate_reason` string** telling the human what went wrong — usually "reviewer_artifacts_all_missing" listing exactly which files were absent.
- **In otto-r2** this fired twice — around R10/R11 and around R14/R15. In both cases a human completed the missing Reviewer artifacts and the loop resumed cleanly. Zero data loss.

**Follow-up traps:**
- *"But you paused a running campaign — what if the timeout has real costs?"* → Yes, but pausing on ambiguity is safer than automatic recovery that might commit corrupted state. In production, `halt_loop` would page an on-call human via the webhook hook described in A17.

---

### B8. Give me an example where the campaign's institutional memory actively misled the Planner.

**What they're probing:** Have you seen state artifacts fail?

**Model answer:**
- **P-1 initial scope was too broad.** After R7 (target encoding failure on CatBoost), Historian wrote "CatBoost depth≥10 blocks FE augmentations." Planner read this as "any FE augmentation on CatBoost is dead."
- When XGBoost became champion in R10 with the same 9 centroid features, the Historian had to scope-update P-1 to CatBoost-only. If the Planner had been more literal in reading the pattern (and less inclined to reason from first principles), it would have avoided the entire XGBoost-with-FE line.
- **How this surfaced:** the Planner's rationalization table shows candidate pruning; a reviewer of that table (human or auditor) would notice "XGBoost + centroid features" being pruned as dead-end because of a CatBoost-scoped pattern. That's the audit surface.
- **Fix now baked in:** pattern statements are explicitly scope-annotated — e.g., "*for CatBoost with depth ≥ 10*". P-5's implication is model-family-specific.

**Follow-up traps:**
- *"So the Historian's phrasing is a critical failure surface."* → Yes. Historian prompt now includes explicit guidance to scope patterns by model family / feature-size range / other observable context.

---

### B9. How do you prevent the Executor's repair attempts from committing garbage?

**What they're probing:** Do you have safeguards against Executor thrash?

**Model answer:**
- **`substantive-diff` check** rejects no-op commits (whitespace-only, comment-only). Prevents "I fixed it" commits that changed nothing.
- **Write-scope check** rejects commits touching read-only paths, even under repair.
- **2-attempt cap** hard-limits thrash; attempt 3 declares crash and rolls back.
- **`RUN_FAILED: <sha> <reason>` sentinel** on the attempt means run.log has a specific failure reason for the Reviewer / next attempt to consume — not free-form failure.

**Follow-up traps:**
- *"What if the two repairs both pass `substantive-diff` but both are broken in different ways?"* → Both would fail with `RUN_FAILED`, cap reached, round declared crash. The Reviewer diagnoses in a post-mortem; the code stays broken until Planner writes a new experiment. This is correct behavior — the harness prefers a clean crash over a limp-along.

---

### B10. The noise_floor is 0.005 for otto-r2 but you also observed fold_std of 0.007–0.012. Isn't the noise_floor set too aggressive?

**What they're probing:** Do you understand statistical noise vs configuration?

**Model answer:**
- **Yes — this is a known and codified pattern.** P-2 (high confidence, evidence across 10 rounds): the nominal `noise_floor=0.005` in `EVAL_PROTOCOL.md` understates the real reliable detection threshold, which is approximately 2× fold_std ≈ 0.011–0.024.
- **What the harness does with this:** the Planner reads P-2 and treats improvements between `0.005` and `~0.011` as "keep-eligible but weakly detectable." Ambiguous keeps get `Confidence: low` in ASSUMPTION_REGISTER.
- **What we don't do:** raise the mechanical noise_floor in EVAL_PROTOCOL.md. That would require a C3 escalation with human approval — because it changes the definition of "improvement" and is contractually stable.
- **The right long-term answer:** the noise_floor should be a function of empirical fold_std, computed dynamically. That's a valid C3 proposal we haven't yet made.

**Follow-up traps:**
- *"So you knowingly accept some fake-improvement keeps?"* → Yes, and we know their expected rate (~30% of borderline keeps regress on rerun, per P-2 evidence). The mitigation is Historian pattern audit — persistent borderline-keep champions get flagged as suspect.

---

### B11. What if the LLM decides to just... stop calling the mandatory tools and lie about it?

**What they're probing:** How defense-in-depth is the tool receipt system?

**Model answer:**
- **Cannot lie about receipts.** The `tool_run` event in `driver_events.jsonl` is written by the `runner.tools.run.execute` subprocess wrapper — not by the LLM. The LLM never touches the JSONL file directly.
- **The LLM's only lever** is: (a) not call the tool → no receipt → F3 fail → `malformed`; (b) call the tool via `python -m runner.tools.X` directly, bypassing the wrapper → no receipt → F3 fail → `malformed`; (c) forge a JSONL entry — but the LLM's write scope doesn't include the state dir's JSONL (well, it does write to state files, but `driver_events.jsonl` has append-only conventions and any forged entry would need the exact schema).
- **Realistic threat:** an LLM could try to hallucinate a tool receipt by writing to the JSONL directly. Would fail on the `args_hash` mismatch when F3 recomputes it — the hash is over the exact argv, which the driver knows.
- **Fully closed?** Not quite — a very determined LLM could invoke `runner.tools.run.execute` with dummy args, producing a valid receipt for a no-op invocation. That's what `args_hash` audit is for in post-mortem: the hash is deterministic per invocation, so identical hashes across rounds signal repeated dummy calls.

**Follow-up traps:**
- *"So you're trusting that the LLM's write-scope discipline holds."* → Correct. The write-scope check is on the *commit*, not on the *working tree*. An LLM that writes to `driver_events.jsonl` outside a commit couldn't be detected by `execute-finalize`. In practice, we haven't seen this behavior. If we did, the fix would be moving the JSONL out of the campaign dir into a driver-owned location.

---

### B12. What are the failure modes of your git-based rollback?

**What they're probing:** Do you know where `git reset --hard` breaks?

**Model answer:**
- **Uncommitted state artifacts survive rollback.** By design — REVIEW.md, PATTERN_BOOK.md, DEAD_ENDS.md are all state changes we want to *keep* across a rollback. But it means an incomplete artifact write from a `malformed` round persists into the next round's state.
- **`git reset --hard` is destructive of working-tree changes.** If a human is mid-edit on `train.py` when the harness rolls back, they lose work. In practice the harness owns `train.py` on the campaign branch, and humans don't touch it — but this isn't enforced by anything.
- **Rollback assumes one commit == one experiment.** If the Executor somehow commits twice in a round (which write-scope + sentinel checks make hard but not impossible), `HEAD~1` rolls back the wrong thing. Never observed empirically.
- **Rollback cannot recover from `git reflog` issues.** If a rollback races with another git operation, HEAD could point somewhere weird. Single-writer discipline is our defense; no locking.

**Follow-up traps:**
- *"Would you consider using git worktrees to isolate the harness's git operations?"* → Yes, natural extension. Would prevent human-vs-harness working-tree races. Cost is more complex setup and a slight learning curve for auditors reading `git log`.

---

### B13. You mentioned the anomaly tool is hardcoded to maximize metrics. What campaigns does this break?

**What they're probing:** Do you know your own harness's blind spots?

**Model answer:**
- **Otto (minimize `val_log_loss`) breaks it entirely.** The anomaly tool's second condition — "metric < max(floor, relative × best_prior)" — is inverted for a minimize direction. If a run scores *worse* (higher log_loss), the check reads it as fine because the value is *above* the floor.
- **EVAL_PROTOCOL.md comment in otto-r2** documents this: *"Both gates disabled: anomaly.py is not direction-aware and assumes higher=better."* Both `floor` and `relative` are set to 0.0.
- **Consequence:** anomaly gate silently disabled for otto. Regression detection falls back to the Reviewer's Δ-based verdict plus the noise-floor override.
- **Fix scope:** two-line change to read `direction` from `EVAL_PROTOCOL.md` and invert the comparison. Deferred because other campaigns don't need it urgently.

**Follow-up traps:**
- *"So you have a documented critical tool disabled and it's been that way for how long?"* → Since otto-r1. Not blocking because Reviewer + noise-floor + reproduce_check cover the failure modes. But yes — it should be fixed. It's a good example of "known-tolerated debt" that would surface in a production readiness review.

---

### B14. What happens when two campaigns run concurrently on the same machine?

**What they're probing:** Do you think about concurrency and shared state?

**Model answer:**
- **Different campaign dirs, different branches — safe.** `campaigns/otto-r2/` and `campaigns/ieee-cis-fraud-r1/` have disjoint state, disjoint train.py, and run on `campaign/otto-r2` and `campaign/ieee-cis-fraud-r1` branches respectively. No collisions on writes.
- **Shared: the machine's CPU / memory.** This is exactly the P-4 pattern surface — a heavy ieee-cis training job at 20+ hours can starve an otto-r2 Optuna experiment. Documented in R12/R13 post-mortems.
- **Shared: the shell environment.** `~/.bashrc`, git config, python site-packages. These are read-only for the harness, so it's fine.
- **Not shared: the LLM session.** Each campaign has its own Claude wrapper loop and session-id file.
- **What's not enforced:** a mutex on `git checkout` or `git reset`. If two harnesses tried to check out the same file at the same instant, one would fail. In practice the campaigns operate on different branches so it doesn't matter — but there's no explicit lock.

**Follow-up traps:**
- *"What if the ieee-cis harness rebases main under otto-r2?"* → Would break otto-r2's branch tracking. In practice, harness runs never touch main. We have a convention, not an enforcement, that harness = campaign-branch-only writes.

---

### B15. What's your cost story? How many tokens does a full campaign burn?

**What they're probing:** Applied-ML startup framing — do you know operational cost?

**Model answer:**
- **Roughly bounded per role:** Planner ~5–15k input, ~5k output; Executor ~5–10k in, 5k out (code); Reviewer ~10–20k in (reads more), ~5k out; Historian ~30–50k in (reads everything), ~10k out.
- **Per round:** ~50–100k tokens across all roles.
- **Per 20-round campaign:** ~1M–2M tokens.
- **`TOKEN_SUMMARY.txt` tracks per-role subtotals** so we can see drift.
- **Prompt caching helps:** the wrapper does `claude --resume <session_id>` to keep sessions warm; state files that don't change across rounds cache-hit.
- **Cost mitigations already in place:** stateless roles mean no context accumulation across rounds beyond disk state (which is small); Historian's periodic-trigger keeps its heavy read cost bounded; PATTERN_BOOK.md and DEAD_ENDS.md let the Planner condense prior learning into ~1KB of state instead of re-reading 20 rounds of REVIEW.md.
- **What would blow this up:** disabling the periodic-trigger for Historian; letting REVIEW.md concatenate raw run.log outputs (which we don't); a Reviewer that reads all 20 rounds of raw REVIEW.md blocks (which we don't — it's summarized in `results.tsv` for its context).

**Follow-up traps:**
- *"$5 per campaign, $50, $500?"* → At ~1.5M tokens and current Sonnet pricing, roughly $10–20 per 20-round campaign. Order of magnitude; not a hot cost.

---

### B16. How do you deal with the Executor generating code that passes all checks but is subtly wrong (e.g., data leakage)?

**What they're probing:** Do you know the deepest failure mode of code-generation agents?

**Model answer:**
- **First-line defense: Reviewer code audit.** The Reviewer explicitly checks for common leakage patterns — fitting a scaler on all data, computing target statistics on val, using future timestamps. REVIEW.md rounds in otto-r2 include this kind of audit ("StandardScaler fit on train fold only (clean)").
- **Second-line: `reproduce_check` cross-validates the reported metric against a recomputation from `y_val_*.npy`.** Catches metric fabrication but not silent leakage that produces *legitimate-looking* val metrics.
- **Third-line: `PATTERN_BOOK` / `DEAD_ENDS` accumulate leakage lessons.** Once a leakage pattern has been observed and diagnosed, it becomes a `DEAD_ENDS` entry and the Planner is required to check against it.
- **Fourth-line: contracts.** The `DATA_CONTRACT.md` has `leakage_audit.performed_at` — a human sign-off on the data pipeline itself. Anything the Executor does downstream is filtered by that pre-audit.
- **Genuinely hard:** subtle leakage from feature engineering that isn't documented as a pattern yet. This is why we don't rely on the harness alone — real campaigns have a human review pass on the champion before it's used for anything downstream.

**Follow-up traps:**
- *"So you have no automated leakage detector?"* → Correct. Semantic leakage detection is an open problem. Our approach: encode observed leakage patterns as DEAD_ENDS + rely on the Reviewer's code audit for novel forms. It's not a solved problem in industry.

---

### B17. What would your #1 priority fix be if you had to make this production-ready tomorrow?

**What they're probing:** Do you have prioritization instincts?

**Model answer (pick one, defend it):**
- **My #1:** version-pin per-campaign environments (pin XGBoost, LightGBM, CatBoost, etc. in a per-campaign `environment.yml`). This alone would have prevented R12 (silent XGBoost 3.x API break) and generally makes the harness reproducible across time.
- **My #2:** direction-aware anomaly tool. Two-line fix; unblocks minimize-direction campaigns from having a critical gate disabled.
- **My #3:** pre-flight `uptime` check in `plan_check` — surface infeasible Optuna plans before they burn budget on hard-timeout.
- **My #4:** adversarial Reviewer-2 pass for high-stakes verdicts. Doubles cost but eliminates a class of Reviewer-single-point-of-failure risks.

Choose one and defend the choice against alternatives.

**Follow-up traps:**
- *"Why not just fix all of them?"* → Sequencing matters. Version pinning is the most operationally durable fix — it prevents entire failure classes across all future campaigns. The others are point fixes for known specific issues.

---

## Section C — Bonus / integration questions

### C1. Compare this harness to AlphaEvolve / MLEvolve. What's the same, what's different?

**Model answer:**
- **Same:** LLM-in-the-loop code evolution with a fitness function; per-experiment commit history; iterative improvement.
- **Different (three axes):**
  1. **Planner as first-class strategist.** Not just a mutation operator — has UCB1, dead-end memory, contract awareness, escalation authority.
  2. **Blind Reviewer.** Phase 1 is structurally blind to the plan. Pure evolutionary approaches lack this independent-verification structure.
  3. **Sticky contract.** The fitness function is contractually pinned; the Planner cannot spec-game it without human C3 approval. Some evolve-your-own-metric research has documented spec-gaming failures we've deliberately designed around.

---

### C2. How would you adapt this harness for a non-ML domain — say, code refactoring?

**Model answer:**
- **What transfers:** the four-role structure, blind Reviewer, disk-as-truth, sticky contract, F1–F5 gates, receipt system.
- **What changes:** the primary metric (from a scalar val_score to a domain-specific measure like "tests pass and no regression benchmarks"), the action_type whitelist (from `A_model/A_feature/A_hp/...` to domain-specific actions), the tools (from `anomaly` / `bootstrap_ci` to domain-specific checks — e.g., `runner.tools.test_run`, `runner.tools.static_analysis`).
- **What's harder:** noise_floor and reproduce_check assume a numeric metric with variance you can bootstrap. For a discrete pass/fail metric, you'd need multi-seed test runs and a different reproducibility check.

---

### C3. If you were interviewing me on this harness, what's the question you'd most want to hear a good answer to?

**Model answer (frame it back):**
- The question I'd care most about: *"Why is the driver stateless and the state on disk, instead of a long-running orchestrator process holding state in memory?"* Because that decision (a) determines every other architectural property (crash recovery, blind roles, auditability) and (b) is the design choice most likely to be questioned by someone with a "just build one big graph" instinct.
- A candidate who can defend that decision convincingly demonstrates they understand the whole system's shape, not just its pieces.

---

## Rehearsal Tips

- **Anchor answers in specific rounds / files / commits.** "R11 R12 R13 shows this exact pattern..." reads far more credible than abstract claims.
- **Own the gaps openly.** The anomaly-tool-direction bug, the multiclass reproduce_check false-negative, the missing pre-flight load gate — pointing these out unprompted signals maturity.
- **Frame tradeoffs, not choices.** "We picked X because Y, giving up Z" beats "X is better than Y."
- **When in doubt, retreat to invariants.** The five hard invariants (§1 of the report) are the constitutional layer; every design decision serves at least one of them.
