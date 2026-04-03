#!/usr/bin/env python3
"""
Executable ABES (Adaptive Bayesian Experiment Selection) Engine.

The navigator for autonomous ML experimentation. Reads experiment history,
computes numerical urgency/opportunity scores, enforces hard constraints,
tracks a multi-metric Pareto front, and recommends the next action.

Usage:
    python3 abes_engine.py init [--budget N] [--tag TAG]
    python3 abes_engine.py recommend
    python3 abes_engine.py log <commit> <pr_auc> <lift> <macro_f1> <val_f1> <status> <n_features> <model_family> <action_type> "<hypothesis>" "<description>"
    python3 abes_engine.py check
    python3 abes_engine.py status
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


def cmd_log(args):
    state = load_state()

    if args.action_type not in ACTION_TYPES:
        print(f"ERROR: invalid action_type '{args.action_type}'. Must be one of: {ACTION_TYPES}", file=sys.stderr)
        sys.exit(2)
    if args.model_family not in ALL_MODEL_TAGS:
        print(f"ERROR: invalid model_family '{args.model_family}'. Must be one of: {ALL_MODEL_TAGS}", file=sys.stderr)
        sys.exit(2)

    row = (
        f"{args.commit}\t{args.pr_auc}\t{args.lift}\t{args.macro_f1}\t"
        f"{args.val_f1}\t{args.status}\t{args.n_features}\t{args.model_family}\t"
        f"{args.action_type}\t{args.hypothesis}\t{args.description}\n"
    )
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(row)

    pr_auc = float(args.pr_auc)
    lift = float(args.lift)
    macro_f1 = float(args.macro_f1)
    status = args.status

    state["experiment_count"] = state.get("experiment_count", 0) + 1
    state.setdefault("last_action_types", []).append(args.action_type)
    if len(state["last_action_types"]) > 20:
        state["last_action_types"] = state["last_action_types"][-20:]

    state.setdefault("action_type_counts", {})
    state["action_type_counts"][args.action_type] = state["action_type_counts"].get(args.action_type, 0) + 1

    if args.model_family in MODEL_FAMILIES and status != "crash":
        state.setdefault("model_family_trials", {})
        state["model_family_trials"][args.model_family] = state["model_family_trials"].get(args.model_family, 0) + 1

    if args.action_type == "A_feature":
        desc_lower = (args.description.lower() + " " + args.hypothesis.lower()).strip()
        tested = state.get("feature_groups_tested", [])
        for feature_group in FEATURE_GROUPS:
            fg_space = feature_group.replace("_", " ")
            if fg_space in desc_lower or feature_group in desc_lower:
                if feature_group not in tested:
                    tested.append(feature_group)
        state["feature_groups_tested"] = tested

    if status == "keep":
        state["consecutive_discards"] = 0
        reward = max(0.0, pr_auc - float(state.get("best_pr_auc", 0.0)))
        if pr_auc > float(state.get("best_pr_auc", 0.0)):
            state["best_pr_auc"] = pr_auc
        if lift > float(state.get("best_lift", 0.0)):
            state["best_lift"] = lift
        if macro_f1 > float(state.get("best_macro_f1", 0.0)):
            state["best_macro_f1"] = macro_f1
    elif status == "discard":
        state["consecutive_discards"] = state.get("consecutive_discards", 0) + 1
        reward = 0.0
    else:
        state["consecutive_discards"] = state.get("consecutive_discards", 0) + 1
        reward = -0.1

    rewards_list = state.get("action_type_rewards", {}).get(args.action_type, [])
    rewards_list.append(reward)
    if len(rewards_list) > 20:
        rewards_list = rewards_list[-20:]
    state.setdefault("action_type_rewards", {})
    state["action_type_rewards"][args.action_type] = rewards_list

    save_state(state)
    print(
        f"Logged experiment {state['experiment_count']}/{state['budget']}: "
        f"status={status}, pr_auc={pr_auc:.6f}"
    )


def _print_action_distribution(state):
    counts = state.get("action_type_counts", {})
    total = sum(counts.values())
    if total == 0:
        return
    print("Action type distribution:")
    for action in ACTION_TYPES:
        count = counts.get(action, 0)
        pct = count / total * 100 if total > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"  {action:15s} {count:3d} ({pct:5.1f}%) {bar}")


def cmd_check(_args):
    state = load_state()
    results = load_results()
    if not results:
        print("No results to check.")
        return

    last = results[-1]
    pr_auc = float(last.get("val_pr_auc", 0))
    lift = float(last.get("lift_at_10", 0))
    macro_f1 = float(last.get("macro_f1", 0))
    status = last.get("status", "")
    best = float(state.get("best_pr_auc", 0))

    print("=" * 60)
    print("ABES POST-EXPERIMENT CHECK")
    print("=" * 60)

    threshold = max(0.5 * best, ANOMALY_FLOOR) if best > 0 else ANOMALY_FLOOR
    if status != "crash" and 0 < pr_auc < threshold:
        print(f"ANOMALY DETECTED: pr_auc={pr_auc:.6f} < threshold={threshold:.6f}")
        print("  -> Add predict_proba diagnostic to next experiment")
        print("  -> Do NOT dismiss this model family from one anomalous result")
        anomalies = state.get("anomalies_undiagnosed", [])
        anomalies.append(
            {
                "experiment": state.get("experiment_count", 0),
                "pr_auc": pr_auc,
                "model_family": last.get("model_family", "unknown"),
                "description": last.get("description", ""),
            }
        )
        state["anomalies_undiagnosed"] = anomalies
    else:
        print(f"No anomaly (pr_auc={pr_auc:.6f}, threshold={threshold:.6f})")

    new_point = {
        "pr_auc": pr_auc,
        "lift": lift,
        "macro_f1": macro_f1,
        "experiment": state.get("experiment_count", 0),
        "description": last.get("description", ""),
    }
    pareto = state.get("pareto_front", [])
    dominated = False
    to_remove = []

    for idx, point in enumerate(pareto):
        if (
            point["pr_auc"] >= pr_auc
            and point["lift"] >= lift
            and point["macro_f1"] >= macro_f1
            and (
                point["pr_auc"] > pr_auc
                or point["lift"] > lift
                or point["macro_f1"] > macro_f1
            )
        ):
            dominated = True
            break
        if (
            pr_auc >= point["pr_auc"]
            and lift >= point["lift"]
            and macro_f1 >= point["macro_f1"]
            and (
                pr_auc > point["pr_auc"]
                or lift > point["lift"]
                or macro_f1 > point["macro_f1"]
            )
        ):
            to_remove.append(idx)

    if not dominated and status != "crash":
        for idx in sorted(to_remove, reverse=True):
            pareto.pop(idx)
        pareto.append(new_point)
        state["pareto_front"] = pareto
        print(f"PARETO UPDATE: New point added to Pareto front ({len(pareto)} points total)")
    else:
        print(f"Pareto front unchanged ({len(pareto)} points)")

    consec = state.get("consecutive_discards", 0)
    if consec >= 5:
        print(f"WARNING: {consec} consecutive discards - approaching plateau trigger (8)")
    if consec >= 8:
        print("PLATEAU TRIGGERED: Next recommendation will be A_restart")

    print()
    print(f"Budget: {state['experiment_count']}/{state['budget']}")
    _print_action_distribution(state)

    save_state(state)
    print("=" * 60)


def cmd_status(_args):
    state = load_state()
    _ = load_results()
    print("=" * 60)
    print(f"ABES STATUS - Run: {state.get('run_tag', '?')}")
    print("=" * 60)
    print(f"Experiments: {state['experiment_count']}/{state['budget']}")
    print(f"Best val_pr_auc: {state.get('best_pr_auc', 0):.6f}")
    print(f"Best lift@10:    {state.get('best_lift', 0):.2f}")
    print(f"Best macro_f1:   {state.get('best_macro_f1', 0):.6f}")
    print(f"Consecutive discards: {state.get('consecutive_discards', 0)}")
    print()
    _print_action_distribution(state)
    print()
    print("Model family trials:")
    for fam in MODEL_FAMILIES:
        print(f"  {fam:12s} {state.get('model_family_trials', {}).get(fam, 0)} trials")
    print()
    print(f"Feature groups tested: {state.get('feature_groups_tested', [])}")
    print(f"Undiagnosed anomalies: {len(state.get('anomalies_undiagnosed', []))}")
    print(f"Pareto front size: {len(state.get('pareto_front', []))}")
    if state.get("pareto_front"):
        print("Pareto front:")
        for point in state["pareto_front"]:
            print(
                f"  pr_auc={point['pr_auc']:.6f}  lift={point['lift']:.2f}  "
                f"macro_f1={point['macro_f1']:.6f}  (exp {point.get('experiment', '?')})"
            )
    print()
    dead = state.get("dead_ends", [])
    print(f"Dead ends ({len(dead)}): {dead}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="ABES Decision Engine")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize ABES state")
    p_init.add_argument("--budget", type=int, default=100)
    p_init.add_argument("--tag", type=str, default="apr03")

    sub.add_parser("recommend", help="Get next experiment recommendation")

    p_log = sub.add_parser("log", help="Log an experiment result")
    p_log.add_argument("commit")
    p_log.add_argument("pr_auc")
    p_log.add_argument("lift")
    p_log.add_argument("macro_f1")
    p_log.add_argument("val_f1")
    p_log.add_argument("status")
    p_log.add_argument("n_features")
    p_log.add_argument("model_family")
    p_log.add_argument("action_type")
    p_log.add_argument("hypothesis")
    p_log.add_argument("description")

    sub.add_parser("check", help="Run anomaly detection and Pareto update")
    sub.add_parser("status", help="Print full state dump for recovery")

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "recommend":
        cmd_recommend(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
