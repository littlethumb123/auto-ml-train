#!/usr/bin/env python3
"""Predict match outcome for a specific matchup using the trained model.

Usage:
    python scripts/predict_matchup.py --tour atp --player-a "Carlos Alcaraz" --player-b "Jannik Sinner" --surface Hard --round F --tourney-level M

This script:
1. Loads the processed feature parquet (with all historical ELO state baked in)
2. Finds the most recent feature row for a matchup between the two players
3. If no direct match exists in the data, constructs a synthetic feature vector
   from the latest available snapshots of each player
4. Runs the trained model to produce a win probability

For the ATP Final at Indian Wells 2026, the players' ELO states are fully
updated through their SF wins, so we build a synthetic matchup row.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def find_player_latest_snapshot(
    df: pd.DataFrame, player_name: str
) -> dict[str, float] | None:
    """Find the latest match where player appears and extract their snapshot.

    We look at both player_a and player_b positions to find the most recent
    appearance, then extract their feature values.
    """
    mask_a = df["player_a_name"] == player_name
    mask_b = df["player_b_name"] == player_name

    latest_a = df.loc[mask_a, "match_date"].max() if mask_a.any() else pd.NaT
    latest_b = df.loc[mask_b, "match_date"].max() if mask_b.any() else pd.NaT

    if pd.isna(latest_a) and pd.isna(latest_b):
        return None

    # Determine which role has the most recent appearance
    if pd.isna(latest_b) or (not pd.isna(latest_a) and latest_a >= latest_b):
        row = df.loc[mask_a & (df["match_date"] == latest_a)].iloc[-1]
        role = "a"
    else:
        row = df.loc[mask_b & (df["match_date"] == latest_b)].iloc[-1]
        role = "b"

    return {"row": row, "role": role}


def build_synthetic_matchup(
    df: pd.DataFrame,
    model: object,
    player_a_name: str,
    player_b_name: str,
    surface: str = "Hard",
    tourney_level: str = "M",
    round_val: str = "F",
) -> dict:
    """Build a synthetic feature vector for a matchup not in the data.

    Strategy: find the latest match for each player, extract their individual
    features from _diff and _sum columns, then reconstruct for the new pairing.

    For diff features: val = player_a_val - player_b_val
    For sum features: val = player_a_val + player_b_val
    """
    meta_cols = {
        "match_id", "match_date", "tourney_name", "score",
        "winner_name", "loser_name", "player_a_id", "player_a_name",
        "player_b_id", "player_b_name", "label",
    }
    feat_cols = [c for c in df.columns if c not in meta_cols]

    # Find latest appearances for both players
    snap_a = find_player_latest_snapshot(df, player_a_name)
    snap_b = find_player_latest_snapshot(df, player_b_name)

    if snap_a is None:
        raise ValueError(f"Player '{player_a_name}' not found in data")
    if snap_b is None:
        raise ValueError(f"Player '{player_b_name}' not found in data")

    row_a = snap_a["row"]
    role_a = snap_a["role"]
    row_b = snap_b["row"]
    role_b = snap_b["role"]

    # Reconstruct individual player values from diff/sum
    # If player was in position A: val_a = (diff + sum) / 2
    # If player was in position B: val_b = (sum - diff) / 2
    def extract_player_vals(row, role, suffix_type):
        """Extract per-player values from diff/sum encoded features."""
        vals = {}
        for col in feat_cols:
            if col.endswith("_diff"):
                base = col[:-5]
                sum_col = f"{base}_sum"
                if sum_col in feat_cols:
                    diff_val = row[col] if not pd.isna(row[col]) else 0.0
                    sum_val = row[sum_col] if not pd.isna(row[sum_col]) else 0.0
                    if role == "a":
                        vals[base] = (diff_val + sum_val) / 2.0
                    else:
                        vals[base] = (sum_val - diff_val) / 2.0
        return vals

    a_vals = extract_player_vals(row_a, role_a, "diff")
    b_vals = extract_player_vals(row_b, role_b, "diff")

    # Build the synthetic row
    synth = {}
    for col in feat_cols:
        if col.endswith("_diff"):
            base = col[:-5]
            if base in a_vals and base in b_vals:
                synth[col] = a_vals[base] - b_vals[base]
            else:
                synth[col] = np.nan
        elif col.endswith("_sum"):
            base = col[:-4]
            if base in a_vals and base in b_vals:
                synth[col] = a_vals[base] + b_vals[base]
            else:
                synth[col] = np.nan
        elif col == "surface":
            synth[col] = surface
        elif col == "tourney_level":
            synth[col] = tourney_level
        elif col == "round":
            synth[col] = round_val
        elif col in ("age_diff", "height_diff", "seed_diff", "rank_edge",
                      "rank_points_diff", "h2h_diff", "h2h_total"):
            # For standalone diff features, try to get from latest match context
            # Use player A's latest value minus player B's latest value
            if role_a == "a":
                val_a_standalone = row_a.get(col, np.nan)
            else:
                # If player was B, the diff was B perspective
                val_a_standalone = np.nan

            synth[col] = np.nan  # Will be imputed by model
        else:
            synth[col] = np.nan

    return synth


def predict_matchup(
    tour: str,
    player_a: str,
    player_b: str,
    surface: str = "Hard",
    tourney_level: str = "M",
    round_val: str = "F",
) -> dict:
    """Generate prediction for a specific matchup."""
    parquet_path = PROJECT_ROOT / "data" / "processed" / f"{tour}_features_strict.parquet"
    model_path = PROJECT_ROOT / "models" / tour / "xgboost" / "model.joblib"

    df = pd.read_parquet(parquet_path)
    model = joblib.load(model_path)

    meta_cols = {
        "match_id", "match_date", "tourney_name", "score",
        "winner_name", "loser_name", "player_a_id", "player_a_name",
        "player_b_id", "player_b_name", "label",
    }
    feat_cols = [c for c in df.columns if c not in meta_cols]

    # Check if match already exists in data
    existing = df[
        ((df["player_a_name"] == player_a) & (df["player_b_name"] == player_b)) |
        ((df["player_a_name"] == player_b) & (df["player_b_name"] == player_a))
    ]
    existing_2026 = existing[existing["match_date"] >= "2026-01-01"]

    if not existing_2026.empty:
        # Use the most recent existing match
        row = existing_2026.iloc[-1]
        x = pd.DataFrame([row[feat_cols]])
        prob = model.predict_proba(x)[0]

        # Determine orientation
        if row["player_a_name"] == player_a:
            prob_a = prob[1]  # prob of label=1 means player_a wins
        else:
            prob_a = 1.0 - prob[1]

        return {
            "player_a": player_a,
            "player_b": player_b,
            "prob_a_wins": float(prob_a),
            "prob_b_wins": float(1.0 - prob_a),
            "predicted_winner": player_a if prob_a >= 0.5 else player_b,
            "confidence": float(max(prob_a, 1.0 - prob_a)),
            "source": "existing_match",
            "key_features": {
                "elo_diff": float(row.get("elo_diff", np.nan)),
                "surface_elo_diff": float(row.get("surface_elo_diff", np.nan)),
                "rank_edge": float(row.get("rank_edge", np.nan)),
                "surface_elo_shrunk_diff": float(row.get("surface_elo_shrunk_diff", np.nan)),
            },
        }
    else:
        # Build synthetic matchup
        synth = build_synthetic_matchup(
            df, model, player_a, player_b, surface, tourney_level, round_val
        )
        x = pd.DataFrame([{col: synth.get(col, np.nan) for col in feat_cols}])
        prob = model.predict_proba(x)[0]
        prob_a = prob[1]

        return {
            "player_a": player_a,
            "player_b": player_b,
            "prob_a_wins": float(prob_a),
            "prob_b_wins": float(1.0 - prob_a),
            "predicted_winner": player_a if prob_a >= 0.5 else player_b,
            "confidence": float(max(prob_a, 1.0 - prob_a)),
            "source": "synthetic",
            "key_features": {
                "elo_diff": float(synth.get("elo_diff", np.nan)),
                "surface_elo_diff": float(synth.get("surface_elo_diff", np.nan)),
                "rank_edge": float(synth.get("rank_edge", np.nan)),
                "surface_elo_shrunk_diff": float(synth.get("surface_elo_shrunk_diff", np.nan)),
            },
        }


def main():
    parser = argparse.ArgumentParser(description="Predict tennis matchup")
    parser.add_argument("--tour", choices=["atp", "wta"], required=True)
    parser.add_argument("--player-a", required=True)
    parser.add_argument("--player-b", required=True)
    parser.add_argument("--surface", default="Hard")
    parser.add_argument("--tourney-level", default="M")
    parser.add_argument("--round", default="F", dest="round_val")
    args = parser.parse_args()

    result = predict_matchup(
        args.tour, args.player_a, args.player_b,
        args.surface, args.tourney_level, args.round_val,
    )

    print(f"\n{'='*60}")
    print(f"  {result['player_a']}  vs  {result['player_b']}")
    print(f"{'='*60}")
    print(f"  Predicted winner: {result['predicted_winner']}")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  P({result['player_a']} wins): {result['prob_a_wins']:.1%}")
    print(f"  P({result['player_b']} wins): {result['prob_b_wins']:.1%}")
    print(f"  Source: {result['source']}")
    print(f"\n  Key Features:")
    for k, v in result["key_features"].items():
        print(f"    {k}: {v:.1f}" if not np.isnan(v) else f"    {k}: N/A")
    print()


if __name__ == "__main__":
    main()
