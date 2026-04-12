#!/usr/bin/env python3
"""Convert TML-Database CSV files to Sackmann schema for the tennis prediction pipeline.

TML-Database: https://github.com/Tennismylife/TML-Database
Sackmann:     https://github.com/JeffSackmann/tennis_atp

Key differences handled:
  - TML has an extra 'indoor' column (dropped)
  - TML places winner_rank/winner_rank_points/loser_rank/loser_rank_points
    after the respective player fields; Sackmann puts them at the end
  - TML uses ATP alphanumeric player IDs; Sackmann uses numeric IDs.
    We map via player names from historical Sackmann data; unmapped players
    get synthetic IDs starting at 900_000.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd

# ── Sackmann column order (49 columns) ──────────────────────────────────────
SACKMANN_COLUMNS = [
    "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level",
    "tourney_date", "match_num",
    "winner_id", "winner_seed", "winner_entry", "winner_name", "winner_hand",
    "winner_ht", "winner_ioc", "winner_age",
    "loser_id", "loser_seed", "loser_entry", "loser_name", "loser_hand",
    "loser_ht", "loser_ioc", "loser_age",
    "score", "best_of", "round", "minutes",
    "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
    "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon",
    "l_SvGms", "l_bpSaved", "l_bpFaced",
    "winner_rank", "winner_rank_points", "loser_rank", "loser_rank_points",
]

# ── Known name aliases: TML name → Sackmann name ────────────────────────────
NAME_ALIASES: dict[str, str] = {
    "Alex de Minaur": "Alex De Minaur",
    "Albert Ramos-Vinolas": "Albert Ramos",
    "Botic van de Zandschulp": "Botic Van De Zandschulp",
    "Christopher O'Connell": "Christopher OConnell",
    "Chun-Hsin Tseng": "Chun Hsin Tseng",
    "Nicolas Jarry Bueno": "Nicolas Jarry",
    "Gael Monfils": "Gael Monfils",
    "Jan-Lennard Struff": "Jan Lennard Struff",
    "Pierre-Hugues Herbert": "Pierre Hugues Herbert",
    "Marc-Andrea Huesler": "Marc Andrea Huesler",
    "Juan-Pablo Varillas": "Juan Pablo Varillas",
    "Jaume Munar Clar": "Jaume Munar",
}

SYNTHETIC_ID_START = 900_000


def _normalize(name: str) -> str:
    """Normalize a player name for fuzzy matching."""
    # Remove accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase, strip punctuation, collapse whitespace
    cleaned = re.sub(r"['\-.]", " ", ascii_only).lower()
    return re.sub(r"\s+", " ", cleaned).strip()


def build_name_to_id(raw_dir: Path, start_year: int = 1985) -> dict[str, int]:
    """Build player name → Sackmann numeric ID from historical match files."""
    name_to_id: dict[str, int] = {}
    for csv_path in sorted(raw_dir.glob("atp_matches_*.csv")):
        stem = csv_path.stem
        if any(x in stem for x in ("qual", "itf", "futures", "chall", "doubles")):
            continue
        year_token = stem.split("_")[-1]
        if not year_token.isdigit() or int(year_token) < start_year:
            continue
        df = pd.read_csv(csv_path, low_memory=False, usecols=[
            "winner_name", "winner_id", "loser_name", "loser_id",
        ])
        for _, row in df.iterrows():
            wn, wid = row.get("winner_name"), row.get("winner_id")
            ln, lid = row.get("loser_name"), row.get("loser_id")
            if pd.notna(wn) and pd.notna(wid):
                name_to_id[str(wn)] = int(wid)
            if pd.notna(ln) and pd.notna(lid):
                name_to_id[str(ln)] = int(lid)
    return name_to_id


def resolve_player_id(
    name: str,
    name_to_id: dict[str, int],
    norm_to_id: dict[str, int],
    synthetic_ids: dict[str, int],
) -> int:
    """Resolve a TML player name to a numeric Sackmann-compatible ID."""
    # 1. Direct match
    if name in name_to_id:
        return name_to_id[name]

    # 2. Known alias
    alias = NAME_ALIASES.get(name)
    if alias and alias in name_to_id:
        return name_to_id[alias]

    # 3. Normalized fuzzy match
    norm = _normalize(name)
    if norm in norm_to_id:
        return norm_to_id[norm]

    # 4. Last-name match (only if unique)
    last = name.split()[-1] if name.strip() else name
    candidates = {n: nid for n, nid in name_to_id.items() if n.endswith(last)}
    if len(candidates) == 1:
        return next(iter(candidates.values()))

    # 5. Synthetic ID
    if name not in synthetic_ids:
        synthetic_ids[name] = SYNTHETIC_ID_START + len(synthetic_ids)
    return synthetic_ids[name]


def convert_tml_to_sackmann(
    tml_path: Path,
    name_to_id: dict[str, int],
    norm_to_id: dict[str, int],
) -> pd.DataFrame:
    """Read a TML CSV and return a DataFrame in Sackmann schema."""
    df = pd.read_csv(tml_path, low_memory=False)

    # Drop the 'indoor' column that Sackmann doesn't have
    if "indoor" in df.columns:
        df = df.drop(columns=["indoor"])

    # Map player IDs from TML alphanumeric to numeric
    synthetic_ids: dict[str, int] = {}
    unmapped_names: list[str] = []

    def _map_id(name: str) -> int:
        nid = resolve_player_id(name, name_to_id, norm_to_id, synthetic_ids)
        if nid >= SYNTHETIC_ID_START:
            unmapped_names.append(name)
        return nid

    df["winner_id"] = df["winner_name"].apply(_map_id)
    df["loser_id"] = df["loser_name"].apply(_map_id)

    # Fill missing match_num with sequential values per tournament
    # (TML leaves match_num blank for some tournaments)
    if df["match_num"].isna().any():
        missing_count = df["match_num"].isna().sum()
        for tourney_id, grp in df[df["match_num"].isna()].groupby("tourney_id"):
            # Start numbering from 1 (or after max existing match_num for that tourney)
            existing = df.loc[
                (df["tourney_id"] == tourney_id) & df["match_num"].notna(), "match_num"
            ]
            start = int(existing.max()) + 1 if len(existing) > 0 else 1
            df.loc[grp.index, "match_num"] = range(start, start + len(grp))
        print(f"  ℹ Filled {missing_count} missing match_num values")

    # Reorder columns to match Sackmann schema exactly
    # TML has all required columns after dropping 'indoor';
    # just reorder them
    for col in SACKMANN_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[SACKMANN_COLUMNS]

    if synthetic_ids:
        unique_unmapped = sorted(set(unmapped_names))
        print(f"  ⚠ {len(unique_unmapped)} players assigned synthetic IDs "
              f"(no Sackmann match): {unique_unmapped[:10]}{'...' if len(unique_unmapped) > 10 else ''}")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert TML-Database CSVs to Sackmann schema")
    parser.add_argument(
        "--tml-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "raw" / "tml_raw",
        help="Directory containing TML CSV files (2025.csv, 2026.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "raw" / "tennis_atp",
        help="Output directory (Sackmann tennis_atp data dir)",
    )
    parser.add_argument(
        "--sackmann-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "raw" / "tennis_atp",
        help="Sackmann data dir for building name→ID map",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2025, 2026],
        help="Years to convert",
    )
    args = parser.parse_args()

    print("Building player name → Sackmann ID mapping from historical data...")
    name_to_id = build_name_to_id(args.sackmann_dir)
    print(f"  {len(name_to_id)} player name→ID entries loaded")

    # Build normalized lookup
    norm_to_id: dict[str, int] = {}
    for name, nid in name_to_id.items():
        norm = _normalize(name)
        norm_to_id[norm] = nid

    for year in args.years:
        tml_path = args.tml_dir / f"{year}.csv"
        if not tml_path.exists():
            print(f"⚠ {tml_path} not found, skipping year {year}")
            continue

        print(f"\nConverting {tml_path.name}...")
        result = convert_tml_to_sackmann(tml_path, name_to_id, norm_to_id)

        out_path = args.output_dir / f"atp_matches_{year}.csv"
        result.to_csv(out_path, index=False)
        print(f"  ✓ Wrote {out_path} — {len(result)} matches, {len(result.columns)} columns")

        # Quick sanity checks
        assert len(result.columns) == 49, f"Column count mismatch: {len(result.columns)}"
        assert list(result.columns) == SACKMANN_COLUMNS, "Column order mismatch"
        assert result["winner_name"].notna().all(), "Missing winner names"
        assert result["loser_name"].notna().all(), "Missing loser names"
        assert result["tourney_date"].notna().all(), "Missing tourney dates"

        # Show sample
        print(f"  Sample: {result[['tourney_name', 'surface', 'winner_name', 'loser_name', 'score']].head(3).to_string(index=False)}")


if __name__ == "__main__":
    main()
