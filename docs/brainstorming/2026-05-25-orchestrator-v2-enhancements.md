# V2 Orchestrator Enhancement Opportunities

**Date:** 2026-05-25
**Context:** After shipping v1 (prompt-level harness), these are the planned upgrades for v2 (SDK-based orchestrator) and v3 (knowledge pipeline).

---

## V2: SDK-Based Runtime Orchestrator

**Trigger:** When the team has broad Anthropic API key access, or when context rot becomes a measurable problem in long campaigns (>30 rounds).

### 2.1 Real-Time Write-Scope Enforcement

**Current (v1):** Post-hoc check in `execute_finalize()` → rollback if violated.
**V2:** Intercept every `write_file` tool call before execution. Block and return `[BLOCKED]` to the model. Prevents the violation from ever reaching disk.

**Why upgrade:** Post-hoc enforcement wastes a round (the write happens, commit happens, then rollback). Real-time enforcement saves the round. Matters more in long campaigns.

### 2.2 Exact Token Tracking

**Current (v1):** `_auto_estimate_round_tokens()` estimates from artifact sizes (±50%).
**V2:** `response.usage.input_tokens + output_tokens` from API response. Exact per-role, per-round.

**Why upgrade:** Accurate cost attribution per role enables budget optimization. Planner may be over-consuming; Executor may be under-budgeted. Exact data reveals this.

### 2.3 Model Tiering Per Role

**Current (v1):** All roles use the session's model.
**V2:** Opus for Planner/Reviewer/Historian (reasoning-heavy), Sonnet for Executor (code generation).

**Why upgrade:** 3-4x cost reduction on Executor calls (code editing doesn't need Opus reasoning). Better reasoning quality on Planner/Reviewer (where strategic decisions matter most).

**Model tier map:**
```python
MODEL_PLANNER  = "claude-opus-4-6"
MODEL_EXECUTOR = "claude-sonnet-4-6"
MODEL_REVIEWER = "claude-opus-4-6"
MODEL_HISTORIAN = "claude-opus-4-6"
```

### 2.4 Programmatic Tool-Use Loop

**Current (v1):** Agent follows prompt instructions, calls bash commands.
**V2:** Python `while stop_reason != "end_turn"` loop with tool dispatch, safety cap (60 calls), structured sentinel parsing via regex.

**Why upgrade:** Deterministic loop → no prompt-following failures. Regex sentinel parsing → 100% reliability vs ~95% agent interpretation. Safety cap → prevents runaway tool use.

### 2.5 Fresh Context Per Role (Sub-Agent Dispatch)

**Current (v1):** Single session, role-switching, context-rot mitigated by checkpoints.
**V2:** Each role gets a fresh API call with 200K context. Zero context rot. True role isolation.

**Why upgrade:** Eliminates the fundamental context rot risk. Each role sees only its §2 Inputs, not leaked context from other roles. Critical for campaigns >30 rounds.

### 2.6 Structured Output Parsing

**Current (v1):** Agent emits sentinel text, driver parses via regex when called.
**V2:** Structured output schemas enforced by the SDK. Reviewer returns `{verdict, commit, metrics, tools_ran}` as a typed object.

**Why upgrade:** Eliminates sentinel parsing failures. Guarantees all required fields are present.

---

## V3: Knowledge Pipeline (Layer 3)

**Trigger:** After the harness is adopted by 3+ data scientists and 5+ campaigns have completed.

### 3.1 Per-Round Knowledge Extraction

After every round, extract atomic learnings:
```python
class RoundLearning:
    campaign_id: str
    round: int
    hypothesis: str
    action_type: str
    outcome: Literal["keep", "discard", "crash"]
    delta: float
    is_dead_end: bool
    pattern_detected: str | None
    model_family: str
    n_features: int
```

Store in `campaign_kb/learnings.jsonl` (per-campaign).

### 3.2 Post-Campaign Compilation

When a campaign concludes, compile generalizable knowledge:
- What model families worked for this problem type?
- What hyperparameter ranges were effective?
- What feature engineering approaches helped?
- What dead ends should be avoided?
- What patterns were reliable?

Output: `team_kb/findings/{campaign_id}.md`

### 3.3 Cross-Campaign Priors Injection

At campaign init, query the Team KB for relevant priors:
- Same problem type (binary classification, regression, etc.)
- Same model family
- Similar data characteristics (row count, feature count, class imbalance ratio)

Auto-populate `contracts/PRIORS.md` with relevant findings.

### 3.4 Team Knowledge Base Storage

Options (in order of complexity):
1. **Markdown files in `team_kb/`** — git-versioned, transparent, simple
2. **SQLite + FTS5** — structured queries across 100+ campaigns
3. **Vector DB (Chroma/Qdrant)** — semantic search for relevant priors

Start with option 1, upgrade as campaign count grows.

### 3.5 The Closed Loop

```
Campaign execution → Round learnings → Campaign KB
                                          ↓
                                   Post-campaign compilation
                                          ↓
                                      Team KB
                                          ↓
                              New campaign PRIORS.md injection
                                          ↓
                              Better experiments from round 1
```

Every campaign makes future campaigns better. Every dead end is documented once, respected forever.

---

## V2 Implementation Upgrade Path

The upgrade from v1 to v2 is designed to be non-breaking:

| Component | V1 (stays unchanged) | V2 (swaps out) |
|---|---|---|
| Role prompts (`runner/roles/*.md`) | ✓ Same | ✓ Same — read as system prompts |
| Contracts (`contracts/*.md`) | ✓ Same | ✓ Same |
| State artifacts (`state/*`) | ✓ Same | ✓ Same |
| Driver functions (`runner_driver.py`) | Called via bash | Called via Python import |
| Sentinel parsing | Agent interprets | Python regex |
| Tool execution | Claude Code native | Custom tool handlers |
| Context management | Agent prompt rules | Fresh API calls per role |
| Orchestrator | Prompt (`orchestrator.md`) | Python (`orchestrator.py`) |

The role prompts don't change. The driver doesn't change. The state artifacts don't change. Only the dispatch mechanism changes — from prompt-driven to code-driven.
