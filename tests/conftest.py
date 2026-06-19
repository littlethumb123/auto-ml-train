"""Shared pytest fixtures for the runner test suite."""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path

import pytest


def write_valid_strategy_memo(
    campaign: Path,
    round_num: int,
    trigger: str = "periodic",
    rounds_covered: tuple[int, int] | None = None,
) -> Path:
    """Write a STRATEGY_MEMO.md that passes F1 verification.

    All four mandatory sections have >80 chars of non-placeholder content.
    Frontmatter has historian_round matching ``round_num`` and trigger matching.
    """
    if rounds_covered is None:
        rounds_covered = (1, round_num)
    body = (
        f"---\n"
        f"schema_version: 1\n"
        f'campaign_id: "tiny"\n'
        f"historian_round: {round_num}\n"
        f'trigger: "{trigger}"\n'
        f"rounds_covered: [{rounds_covered[0]}, {rounds_covered[1]}]\n"
        f"---\n\n"
        "## 1. Trajectory Narrative\n"
        "Campaign currently in the exploitation phase. Mean Δ-per-round is +0.004 over "
        "the covered window. Last family switch occurred at round 3.\n\n"
        "## 2. Pattern Extraction\n"
        "Pattern P-1 — adding raw features hurts PR-AUC. Supporting rounds: 4, 9. "
        "Confidence: medium. Implication: prefer hp/ensemble over feature additions.\n\n"
        "## 3. Assumption Audit\n"
        "A-1-1 (load-bearing) remains unverified after this audit. No new evidence "
        "for or against. Recommend a validation experiment next round.\n\n"
        "## 4. Bottleneck Diagnosis\n"
        "Category: model_quality. Justification: model family is near its ceiling "
        "given current feature representation. Highest-ROI: A_ensemble.\n"
    )
    memo_path = campaign / "state" / "STRATEGY_MEMO.md"
    memo_path.write_text(body)
    return memo_path


def simulate_reviewer_writes(
    campaign: Path,
    new_round: int,
    verdict: str = "keep",
) -> None:
    """Append the artifacts F2 expects: CAMPAIGN_JOURNAL Round N entry,
    REVIEW.md Round N body, and (on keep) an A-N-1 assumption entry.

    Used by tests that exercise a successful keep/discard verdict under
    review_finalize after an anchor has been stamped.
    """
    state_dir = campaign / "state"

    journal = state_dir / "CAMPAIGN_JOURNAL.md"
    journal_text = journal.read_text() if journal.exists() else "---\nschema_version: 1\n---\n"
    journal.write_text(
        journal_text
        + f"\n## Round {new_round} — 2026-06-19\n\n**Verdict:** {verdict}\n"
    )

    review = state_dir / "REVIEW.md"
    review_text = review.read_text() if review.exists() else (
        "---\nschema_version: 1\nlast_verdict: null\nlast_round: 0\n---\n"
    )
    review.write_text(
        review_text + f"\n## Round {new_round} — review block\n"
        "Independent assessment, plan comparison, verdict rationale.\n"
    )

    if verdict == "keep":
        register = state_dir / "ASSUMPTION_REGISTER.md"
        register_text = register.read_text() if register.exists() else (
            "---\nschema_version: 1\ncount: 0\n---\n"
        )
        register.write_text(
            register_text + f"\n### A-{new_round}-1 — generated assumption\n"
            "- **Claim:** the simulated assumption holds.\n"
            "- **Confidence:** medium\n"
        )


def anchor_round_with_receipts(
    campaign: Path,
    tools: list[str],
    include_reviewer_writes: bool = True,
    verdict_for_writes: str = "keep",
) -> str:
    """Stamp round_started_at and emit tool_run receipts (F3 test helper).

    Tests that exercise review_finalize with verdict=keep need to satisfy
    both F3 (receipts since round_started_at) and F2 (reviewer artifacts
    appended since round_started_at). By default, this helper sets up both:
      1. Stamps state.round_started_at to "now".
      2. Appends one tool_run event per named tool to driver_events.jsonl
         with exit_code=0 and start_ts/end_ts at "now".
      3. Simulates the Reviewer's CAMPAIGN_JOURNAL/REVIEW.md/ASSUMPTION_REGISTER
         writes for the next round (override with include_reviewer_writes=False
         when the test wants F2 rejection).

    Returns the anchor timestamp.
    """
    from runner import runner_driver  # local import to avoid pytest collection cycles

    state_path = campaign / "state" / "CAMPAIGN_STATE.json"
    state = json.loads(state_path.read_text())
    anchor = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["round_started_at"] = anchor
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    events = campaign / "state" / "driver_events.jsonl"
    with open(events, "a") as f:
        for t in tools:
            rec = {
                "ts": anchor,
                "event": "tool_run",
                "name": runner_driver._normalize_mandatory_tool_name(t),
                "start_ts": anchor,
                "end_ts": anchor,
                "exit_code": 0,
                "args_hash": "deadbeefdeadbeef",
                "round": int(state.get("round", 0)),
                "campaign_dir": str(campaign),
            }
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    if include_reviewer_writes:
        new_round = int(state.get("round", 0)) + 1
        simulate_reviewer_writes(campaign, new_round=new_round, verdict=verdict_for_writes)
    return anchor


@pytest.fixture
def tmp_campaign_dir(tmp_path: Path) -> Path:
    """A temporary `runner/` workspace with the directory tree created and
    empty placeholder artifacts. Does NOT create valid contracts; individual
    tests populate what they need."""
    root = tmp_path / "runner"
    for sub in ("contracts", "state", "tools", "roles", "experiment_helpers"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    header = (
        "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
        "model_family\taction_type\thypothesis\tdescription\n"
    )
    (root / "state" / "results.tsv").write_text(header)
    return root


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """A temporary initialized git repo with an initial commit. Used by
    driver tests that exercise `git reset --hard HEAD~1`."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path
