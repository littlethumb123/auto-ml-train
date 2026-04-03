#!/usr/bin/env python3
"""
Executable ABES (Adaptive Bayesian Experiment Selection) Engine.

The navigator for autonomous ML experimentation. Reads experiment history,
computes numerical urgency/opportunity scores, enforces hard constraints,
tracks a multi-metric Pareto front, and recommends the next action.

Usage:
    python3 abes_engine.py init [--budget N] [--tag TAG]
    python3 abes_engine.py recommend
"""

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

RESULTS_FILE = "results.tsv"
STATE_FILE = "abes_state.json"

MODEL_FAMILIES = ["xgboost", "lightgbm", "catboost", "rf", "gbm", "et"]
ALL_MODEL_TAGS = MODEL_FAMILIES + ["ensemble", "other"]
ACTION_TYPES = [
    "A_model",
    "A_feature",
    "A_hp",
    "A_diagnose",
    "A_ensemble",
    "A_validate",
    "A_restart",
    "A_imbalance",
]
FEATURE_GROUPS = [
    "log_amount",
    "time_features",
    "v_interactions",
    "amount_interactions",
    "magnitude_features",
    "rank_features",
]

DEAD_ENDS_DEFAULT = [
    "SMOTE + scale_pos_weight",
    "QuantileTransformer on tree models",
    "BaggingClassifier wrapping XGBoost",
    "aucpr as early stopping metric",
    "LightGBM is_unbalance=True",
    "DART booster",
    "tree_method=approx",
    "sklearn GBM (GradientBoostingClassifier)",
]

ANOMALY_FLOOR = 0.75


def load_state():
    if not Path(STATE_FILE).exists():
        print(f"ERROR: {STATE_FILE} not found. Run: python3 abes_engine.py init", file=sys.stderr)
        sys.exit(1)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_results():
    if not Path(RESULTS_FILE).exists():
        return []
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) <= 1:
        return []
    header = lines[0].rstrip("\n").split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = line.rstrip("\n").split("\t")
        row = dict(zip(header, vals))
        rows.append(row)
    return rows


def cmd_init(args):
    budget = getattr(args, "budget", 100)
    tag = getattr(args, "tag", "apr03")
    state = {
        "run_tag": tag,
        "budget": budget,
        "experiment_count": 0,
        "consecutive_discards": 0,
        "best_pr_auc": 0.0,
        "best_lift": 0.0,
        "best_macro_f1": 0.0,
        "last_action_types": [],
        "action_type_counts": {a: 0 for a in ACTION_TYPES},
        "action_type_rewards": {a: [] for a in ACTION_TYPES},
        "model_family_trials": {f: 0 for f in MODEL_FAMILIES},
        "feature_groups_tested": [],
        "pareto_front": [],
        "dead_ends": DEAD_ENDS_DEFAULT,
        "anomalies_undiagnosed": [],
        "warm_start": {
            "known_good_features": ["log_amount", "amount_interactions"],
            "known_bad_features": ["v_interactions", "time_features"],
            "best_model_family": "xgboost",
            "competitive_families": ["lightgbm"],
            "known_optimal_ranges": {
                "xgboost_depth": [4, 6],
                "xgboost_lr": [0.02, 0.08],
                "xgboost_n_estimators": [1000, 2000],
            },
        },
    }
    save_state(state)

    header = (
        "commit\tval_pr_auc\tlift_at_10\tmacro_f1\tval_f1\tstatus\tn_features\t"
        "model_family\taction_type\thypothesis\tdescription\n"
    )
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(header)

    print(f"ABES initialized: run_tag={tag}, budget={budget}")
    print(f"State written to {STATE_FILE}")
    print(f"Results header written to {RESULTS_FILE}")
    print(f"Dead ends loaded: {len(DEAD_ENDS_DEFAULT)}")
    print(
        f"Warm-start: good_features={state['warm_start']['known_good_features']}, "
        f"bad_features={state['warm_start']['known_bad_features']}"
    )


def lambda_explore(t, budget):
    if budget <= 0:
        return 0.0
    fraction_remaining = max(0, (budget - t)) / budget
    return 2.0 / (1.0 + math.exp(-5 * (fraction_remaining - 0.5)))


def compute_urgency(state, results):
    t = state.get("experiment_count", 0)
    budget = state.get("budget", 100)
    _ = (t, budget)  # explicit placeholder for future schedule-aware urgency terms

    scores = {}

    under_explored = sum(1 for fam in MODEL_FAMILIES if state.get("model_family_trials", {}).get(fam, 0) < 2)
    scores["A_model"] = under_explored / len(MODEL_FAMILIES)

    tested = len(state.get("feature_groups_tested", []))
    scores["A_feature"] = 1.0 - (tested / len(FEATURE_GROUPS)) if FEATURE_GROUPS else 0.0

    last_5 = state.get("last_action_types", [])[-5:]
    hp_count = sum(1 for a in last_5 if a == "A_hp")
    scores["A_hp"] = 1.0 / (1.0 + hp_count)

    anomaly_count = len(state.get("anomalies_undiagnosed", []))
    scores["A_diagnose"] = min(1.0, 0.5 * anomaly_count)

    best = float(state.get("best_pr_auc", 0.0))
    if best > 0:
        threshold_5pct = best * 0.95
        family_bests = {}
        for row in results:
            if row.get("status") == "crash":
                continue
            fam = row.get("model_family", "")
            try:
                score = float(row.get("val_pr_auc", 0))
            except (TypeError, ValueError):
                continue
            if fam and score > family_bests.get(fam, 0):
                family_bests[fam] = score
        competitive = sum(1 for score in family_bests.values() if score >= threshold_5pct)
        scores["A_ensemble"] = 0.3 if competitive >= 2 else 0.0
    else:
        scores["A_ensemble"] = 0.0

    if budget > 0:
        scores["A_validate"] = max(0.0, (state.get("experiment_count", 0) / budget - 0.8) * 5.0)
    else:
        scores["A_validate"] = 0.0

    consec = state.get("consecutive_discards", 0)
    scores["A_restart"] = 1.0 if consec >= 8 else 0.0

    last_10 = state.get("last_action_types", [])[-10:]
    imb_count = sum(1 for a in last_10 if a == "A_imbalance")
    scores["A_imbalance"] = 1.0 / (1.0 + imb_count)

    return scores


def compute_opportunity(state):
    scores = {}
    for action in ACTION_TYPES:
        rewards = state.get("action_type_rewards", {}).get(action, [])
        if len(rewards) < 2:
            if action == "A_model":
                scores[action] = 0.5
            elif action == "A_restart":
                scores[action] = 0.7
            else:
                scores[action] = 0.3
        else:
            scores[action] = min(1.0, 0.8 * statistics.stdev(rewards))
    return scores


def enforce_constraints(urgency, state):
    """Apply hard constraints that override urgency scores."""
    blocked = set()
    warnings = []

    last_5 = state.get("last_action_types", [])[-5:]
    if len(last_5) == 5 and len(set(last_5)) == 1:
        blocked_type = last_5[0]
        blocked.add(blocked_type)
        warnings.append(f"BLOCKED {blocked_type}: 5 consecutive experiments of same type")

    if state.get("consecutive_discards", 0) >= 8:
        warnings.append("PLATEAU: 8+ consecutive discards - forcing A_restart")
        return {"A_restart": 1.0}, set(ACTION_TYPES) - {"A_restart"}, warnings

    if state.get("experiment_count", 0) >= state.get("budget", 100):
        warnings.append("BUDGET EXHAUSTED")
        return {}, set(ACTION_TYPES), warnings

    dead_ends = state.get("dead_ends", [])
    if dead_ends:
        warnings.append(f"Dead ends active ({len(dead_ends)}): do not retry these")

    filtered = {a: s for a, s in urgency.items() if a not in blocked}
    return filtered, blocked, warnings


def _print_suggestion(action, state, results):
    warm = state.get("warm_start", {})
    if action == "A_model":
        under = [f for f in MODEL_FAMILIES if state.get("model_family_trials", {}).get(f, 0) < 2]
        if under:
            print(f"Suggestion: Try {under[0]} with canonical config.")
            print(f"  Under-explored families: {under}")
        else:
            print("Suggestion: Re-try runner-up family with refined config.")
    elif action == "A_feature":
        untested = [g for g in FEATURE_GROUPS if g not in state.get("feature_groups_tested", [])]
        bad = warm.get("known_bad_features", [])
        candidates = [g for g in untested if g not in bad]
        if candidates:
            print(f"Suggestion: Test feature group '{candidates[0]}'.")
            print(f"  Untested groups: {untested}")
            print(f"  Skip (known bad): {bad}")
        else:
            print("Suggestion: Re-ablate a feature group with the current best config.")
    elif action == "A_hp":
        print("Suggestion: Change ONE hyperparameter from current best.")
        ranges = warm.get("known_optimal_ranges", {})
        if ranges:
            print(f"  Known optimal ranges: {ranges}")
    elif action == "A_restart":
        print("PLATEAU DETECTED - Basin restart triggered.")
        print("Suggestion: Run screen_configs() in train.py to test 16 random configs at low fidelity.")
        print("  Use n_estimators=200, 25% training data subsample.")
        print("  Pick the top-1 config and evaluate at full fidelity.")
    elif action == "A_ensemble":
        print("Suggestion: Soft-vote the top-2 competitive model families.")
    elif action == "A_diagnose":
        anomalies = state.get("anomalies_undiagnosed", [])
        if anomalies:
            print(f"Suggestion: Diagnose anomaly: {anomalies[0]}")
            print("  Print model.predict_proba(X_val[:5]) to check for inversion.")
    elif action == "A_validate":
        print("Suggestion: Proper hold-out early stopping (reserve 20% of train as stop set).")
    elif action == "A_imbalance":
        print("Suggestion: Try a different class imbalance strategy.")
        print("  Options: class_weight='balanced', ADASYN, different scale_pos_weight ratio.")
    else:
        _ = results
        print("Suggestion: No specific suggestion available.")


def cmd_recommend(_args):
    state = load_state()
    results = load_results()
    t = state.get("experiment_count", 0)
    budget = state.get("budget", 100)

    if t >= budget:
        print("=" * 60)
        print(f"STOP: Budget exhausted ({t}/{budget})")
        print("Run: python3 abes_engine.py status  for final summary")
        print("=" * 60)
        return

    lam = lambda_explore(t, budget)
    urgency = compute_urgency(state, results)
    opportunity = compute_opportunity(state)
    filtered, blocked, warnings = enforce_constraints(urgency, state)

    if not filtered:
        print("STOP: All action types blocked or budget exhausted.")
        for warning in warnings:
            print(f"  {warning}")
        return

    composite = {}
    for action in filtered:
        u = filtered[action]
        o = opportunity.get(action, 0.3)
        composite[action] = u * lam + o * (1.0 - lam / 2.0)

    ranked = sorted(composite.items(), key=lambda x: x[1], reverse=True)
    recommended = ranked[0][0]

    print("=" * 60)
    print(f"ABES RECOMMENDATION - Experiment {t + 1}/{budget}")
    print("=" * 60)
    mode = "EXPLORE" if lam > 1.0 else ("BALANCED" if lam > 0.3 else "EXPLOIT")
    print(f"lambda_explore: {lam:.3f}  ({mode})")
    print(f"consecutive_discards: {state.get('consecutive_discards', 0)}")
    print(f"best_pr_auc: {state.get('best_pr_auc', 0):.6f}")
    if warnings:
        print()
        print("Constraint Warnings:")
        for warning in warnings:
            print(f"  WARNING: {warning}")
    print()
    print("Urgency Scores:")
    for action in ACTION_TYPES:
        flag = ""
        if action in blocked:
            flag = " [BLOCKED]"
        elif action == recommended:
            flag = " <<<< RECOMMENDED"
        print(
            f"  {action:15s}  urgency={urgency.get(action, 0):.3f}  "
            f"opportunity={opportunity.get(action, 0):.3f}  "
            f"composite={composite.get(action, 0):.3f}{flag}"
        )
    print()
    print(f"RECOMMENDED ACTION: {recommended}")
    print()
    dead_ends = state.get("dead_ends", [])
    if dead_ends:
        print("DEAD ENDS (do NOT retry):")
        for dead_end in dead_ends:
            print(f"  X {dead_end}")
        print()
    _print_suggestion(recommended, state, results)
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="ABES Decision Engine")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize ABES state")
    p_init.add_argument("--budget", type=int, default=100)
    p_init.add_argument("--tag", type=str, default="apr03")

    sub.add_parser("recommend", help="Get next experiment recommendation")

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "recommend":
        cmd_recommend(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
