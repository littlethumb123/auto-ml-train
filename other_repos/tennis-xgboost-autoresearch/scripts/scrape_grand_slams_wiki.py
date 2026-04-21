#!/usr/bin/env python3
"""
Parse Wikipedia draw templates to extract Grand Slam match data and
append to existing Sackmann-compatible WTA CSV files.

Wikipedia uses {{16TeamBracket-Compact-Tennis3}} templates for each draw section.
Each 128-player Grand Slam draw has 8 sections of 16 players, plus a Finals bracket.

Usage:
  python scripts/scrape_grand_slams_wiki.py [--year 2025] [--dry-run] [--verbose]
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_WTA = PROJECT_ROOT / "data" / "raw" / "tennis_wta"

COLUMNS = [
    "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level",
    "tourney_date", "match_num", "winner_id", "winner_seed", "winner_entry",
    "winner_name", "winner_hand", "winner_ht", "winner_ioc", "winner_age",
    "loser_id", "loser_seed", "loser_entry", "loser_name", "loser_hand",
    "loser_ht", "loser_ioc", "loser_age", "score", "best_of", "round",
    "minutes", "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
    "w_SvGms", "w_bpSaved", "w_bpFaced", "l_ace", "l_df", "l_svpt",
    "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
    "winner_rank", "winner_rank_points", "loser_rank", "loser_rank_points"
]

# Grand Slam tournament metadata
GRAND_SLAMS_2025 = {
    "2025 Australian Open – Women's singles": {
        "tid": "2025-580", "name": "Australian Open", "surface": "Hard",
        "draw_size": 128, "level": "G", "date": "20250113"
    },
    "2025 French Open – Women's singles": {
        "tid": "2025-520", "name": "Roland Garros", "surface": "Clay",
        "draw_size": 128, "level": "G", "date": "20250526"
    },
    "2025 Wimbledon Championships – Women's singles": {
        "tid": "2025-540", "name": "Wimbledon", "surface": "Grass",
        "draw_size": 128, "level": "G", "date": "20250630"
    },
    "2025 US Open – Women's singles": {
        "tid": "2025-560", "name": "Us Open", "surface": "Hard",
        "draw_size": 128, "level": "G", "date": "20250825"
    },
}

# Round mapping: Section RD numbers -> Sackmann round labels
# Each 16-player section has RD1 (8 matches) -> RD2 (4) -> RD3 (2) -> RD4 (1)
# These map to the overall bracket:
# Section RD1 = R128, RD2 = R64, RD3 = R32, RD4 = R16
SECTION_ROUND_MAP = {"RD1": "R128", "RD2": "R64", "RD3": "R32", "RD4": "R16"}
FINALS_ROUND_MAP = {"RD1": "QF", "RD2": "SF", "RD3": "F"}


def fetch_wikitext(page_title, verbose=False):
    """Fetch wikitext from Wikipedia API."""
    encoded = urllib.parse.quote(page_title)
    url = (f"https://en.wikipedia.org/w/api.php"
           f"?action=parse&page={encoded}&prop=wikitext&format=json&redirects=true")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "tennis-research-bot/1.0 (match-result-extraction)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if "parse" in data and "wikitext" in data["parse"]:
                return data["parse"]["wikitext"]["*"]
    except Exception as e:
        if verbose:
            print(f"  [ERROR] fetching {page_title}: {e}")
    return None


def extract_player_name(team_text):
    """Extract player name and IOC from wiki team text.
    Input: '''{{flagicon|USA}} [[Madison Keys|M Keys]]'''
    Output: (name, ioc, is_winner)
    """
    # Bold can wrap the entire text or just the wikilink
    is_winner = "'''" in team_text

    # Extract IOC from flagicon
    ioc_match = re.search(r"\{\{flagicon\|([A-Z]{3})\}\}", team_text)
    ioc = ioc_match.group(1) if ioc_match else ""

    # Extract player name from wikilink
    # Format: [[Full Name|Display Name]] or [[Full Name]]
    name_match = re.search(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", team_text)
    if name_match:
        name = name_match.group(1).strip()
        # Remove Wikipedia disambiguation suffixes like "(tennis)"
        name = re.sub(r"\s*\(tennis\)\s*$", "", name)
        name = re.sub(r"\s*\(tennis player\)\s*$", "", name)
        # Handle special characters (diacritics -> ASCII)
        name = name.replace("é", "e").replace("è", "e").replace("ë", "e")
        name = name.replace("á", "a").replace("à", "a").replace("ä", "a")
        name = name.replace("ó", "o").replace("ö", "o").replace("ú", "u")
        name = name.replace("ü", "u").replace("í", "i").replace("ñ", "n")
        name = name.replace("ž", "z").replace("š", "s").replace("č", "c")
        name = name.replace("ř", "r").replace("ě", "e").replace("ý", "y")
        name = name.replace("ů", "u").replace("ő", "o").replace("ı", "i")
        name = name.replace("ş", "s").replace("ç", "c").replace("ă", "a")
        name = name.replace("ś", "s").replace("ć", "c").replace("ę", "e")
        name = name.replace("ł", "l")
        # Additional diacritics
        name = name.replace("Ś", "S").replace("ą", "a").replace("ń", "n")
        name = name.replace("Š", "S").replace("î", "i").replace("ļ", "l")
        name = name.replace("ņ", "n").replace("ș", "s").replace("ț", "t")
        name = name.replace("Ž", "Z").replace("Č", "C").replace("Ř", "R")
        name = name.replace("Ó", "O").replace("Á", "A").replace("É", "E")
        name = name.replace("Ú", "U").replace("Í", "I").replace("Ñ", "N")
        name = name.replace("ğ", "g").replace("ã", "a").replace("ô", "o")
        name = name.replace("Ą", "A").replace("Ę", "E").replace("Ł", "L")
        name = name.replace("ð", "d").replace("þ", "th")
        name = name.replace("Ć", "C").replace("Đ", "D").replace("đ", "d")
        # Handle display name vs full name
        # Use full name from first part of wikilink
        return name, ioc, is_winner
    return "", ioc, is_winner


def parse_seed(seed_text):
    """Parse seed text into (seed_number, entry_type).
    '1' -> ('1', '')
    'Q' -> ('', 'Q')
    'WC' -> ('', 'WC')
    'LL' -> ('', 'LL')
    'PR' -> ('', 'PR')
    '' -> ('', '')
    """
    seed_text = seed_text.strip()
    if not seed_text:
        return "", ""
    if seed_text.isdigit():
        return seed_text, ""
    if seed_text in ("Q", "WC", "LL", "PR", "SE", "ALT"):
        return "", seed_text
    return "", ""


def parse_score(scores_p1, scores_p2, p1_is_winner):
    """Parse set scores into Sackmann format.
    scores_p1: list of score strings for player 1 (e.g., ["'''6'''", "3", "'''7<sup>7</sup>'''"])
    scores_p2: list of score strings for player 2
    Returns: "6-4 3-6 7-6(4)" from winner's perspective
    """
    sets = []
    for s1, s2 in zip(scores_p1, scores_p2):
        s1 = s1.strip()
        s2 = s2.strip()
        if not s1 and not s2:
            continue

        # Handle retirements (including <sup>r</sup> format)
        if "ret" in s1.lower() or "ret" in s2.lower():
            sets.append("RET")
            continue
        if "<sup>r</sup>" in s1.lower() or "<sup>r</sup>" in s2.lower():
            # Retirement mid-set: extract game count, add the partial set + RET
            s1_clean_r = re.sub(r"<sup>r</sup>", "", s1.replace("'''", "")).strip()
            s2_clean_r = re.sub(r"<sup>r</sup>", "", s2.replace("'''", "")).strip()
            g1_r = re.match(r"(\d+)", s1_clean_r)
            g2_r = re.match(r"(\d+)", s2_clean_r)
            if g1_r and g2_r:
                if p1_is_winner:
                    sets.append(f"{g1_r.group(1)}-{g2_r.group(1)}")
                else:
                    sets.append(f"{g2_r.group(1)}-{g1_r.group(1)}")
            sets.append("RET")
            break  # No more sets after retirement
        if "w/o" in s1.lower() or "w/o" in s2.lower():
            return "W/O"

        # Strip bold markers
        s1_clean = s1.replace("'''", "")
        s2_clean = s2.replace("'''", "")

        # Extract tiebreak scores from <sup> tags
        tb1 = re.search(r"<sup>(\d+)</sup>", s1_clean)
        tb2 = re.search(r"<sup>(\d+)</sup>", s2_clean)

        # Get base game count
        g1 = re.match(r"(\d+)", s1_clean.split("<")[0])
        g2 = re.match(r"(\d+)", s2_clean.split("<")[0])

        if not g1 or not g2:
            continue

        g1_val = g1.group(1)
        g2_val = g2.group(1)

        # Determine tiebreak score for Sackmann format
        # Sackmann convention: show loser-of-the-set's tiebreak score
        # In Wikipedia, <sup>N</sup> is on the player who scored N in the TB
        # The player with game score 6 lost the tiebreak, use their TB score
        tb_score = ""
        g1_int = int(g1_val)
        g2_int = int(g2_val)
        if g1_int == 7 and g2_int == 6 and tb2:
            # p1 won this set's tiebreak, use p2's (loser's) TB score
            tb_score = f"({tb2.group(1)})"
        elif g2_int == 7 and g1_int == 6 and tb1:
            # p2 won this set's tiebreak, use p1's (loser's) TB score
            tb_score = f"({tb1.group(1)})"
        elif tb1:
            tb_score = f"({tb1.group(1)})"
        elif tb2:
            tb_score = f"({tb2.group(1)})"

        # Build set score from winner's perspective
        if p1_is_winner:
            sets.append(f"{g1_val}-{g2_val}{tb_score}")
        else:
            sets.append(f"{g2_val}-{g1_val}{tb_score}")

    if not sets:
        return ""

    # Check if last element is RET
    score_str = " ".join(sets)
    return score_str


def _search_field(section_text, rd_key, field, slot_str):
    """Search for a wikitext field, trying both zero-padded and non-padded slot numbers."""
    # Try the given format first (e.g., "team01" or "team1")
    m = re.search(rf"\|\s*{rd_key}-{field}{slot_str}=(.*)", section_text)
    if m:
        return m
    # Try alternate format: if zero-padded, try non-padded and vice versa
    if slot_str.startswith("0"):
        alt = slot_str.lstrip("0") or "0"
        m = re.search(rf"\|\s*{rd_key}-{field}{alt}=(.*)", section_text)
    else:
        alt = f"{int(slot_str):02d}"
        m = re.search(rf"\|\s*{rd_key}-{field}{alt}=(.*)", section_text)
    return m


def parse_section(section_text, section_num, round_map, verbose=False):
    """Parse a single draw section and return list of matches."""
    matches = []

    # Find all rounds in this section
    for rd_num in range(1, 5):  # RD1 through RD4
        rd_key = f"RD{rd_num}"
        sackmann_round = round_map.get(rd_key)
        if not sackmann_round:
            continue

        # Determine number of matches in this round
        # RD1: 8 matches (slots 01-16), RD2: 4 (01-08), RD3: 2 (01-04), RD4: 1 (01-02)
        num_matches = 8 // (2 ** (rd_num - 1))

        for match_idx in range(num_matches):
            slot_a = match_idx * 2 + 1  # 1, 3, 5, ...
            slot_b = match_idx * 2 + 2  # 2, 4, 6, ...

            slot_a_str = f"{slot_a:02d}"
            slot_b_str = f"{slot_b:02d}"

            # Extract team names (match to end of line; team text contains pipes)
            team_a_match = _search_field(section_text, rd_key, "team", slot_a_str)
            team_b_match = _search_field(section_text, rd_key, "team", slot_b_str)

            if not team_a_match or not team_b_match:
                continue

            team_a_text = team_a_match.group(1).strip()
            team_b_text = team_b_match.group(1).strip()

            if not team_a_text or not team_b_text:
                continue

            name_a, ioc_a, a_won = extract_player_name(team_a_text)
            name_b, ioc_b, b_won = extract_player_name(team_b_text)

            if not name_a or not name_b:
                continue

            # Extract seeds
            seed_a_match = _search_field(section_text, rd_key, "seed", slot_a_str)
            seed_b_match = _search_field(section_text, rd_key, "seed", slot_b_str)

            seed_a_text = seed_a_match.group(1).strip() if seed_a_match else ""
            seed_b_text = seed_b_match.group(1).strip() if seed_b_match else ""

            seed_a, entry_a = parse_seed(seed_a_text)
            seed_b, entry_b = parse_seed(seed_b_text)

            # Extract scores (up to 5 sets)
            # Score fields: score01-1, score01-2, ... or score1-1, score1-2, ...
            scores_a = []
            scores_b = []
            slot_a_alt = slot_a_str.lstrip("0") or "0"
            slot_b_alt = slot_b_str.lstrip("0") or "0"
            for set_num in range(1, 6):
                sa_match = re.search(
                    rf"\|\s*{rd_key}-score{slot_a_str}-{set_num}=(.*)", section_text)
                if not sa_match:
                    sa_match = re.search(
                        rf"\|\s*{rd_key}-score{slot_a_alt}-{set_num}=(.*)", section_text)
                sb_match = re.search(
                    rf"\|\s*{rd_key}-score{slot_b_str}-{set_num}=(.*)", section_text)
                if not sb_match:
                    sb_match = re.search(
                        rf"\|\s*{rd_key}-score{slot_b_alt}-{set_num}=(.*)", section_text)
                sa = sa_match.group(1).strip() if sa_match else ""
                sb = sb_match.group(1).strip() if sb_match else ""
                scores_a.append(sa)
                scores_b.append(sb)

            # Determine winner based on bold text
            if a_won and not b_won:
                winner_name, winner_ioc, winner_seed, winner_entry = name_a, ioc_a, seed_a, entry_a
                loser_name, loser_ioc, loser_seed, loser_entry = name_b, ioc_b, seed_b, entry_b
                score = parse_score(scores_a, scores_b, True)
            elif b_won and not a_won:
                winner_name, winner_ioc, winner_seed, winner_entry = name_b, ioc_b, seed_b, entry_b
                loser_name, loser_ioc, loser_seed, loser_entry = name_a, ioc_a, seed_a, entry_a
                score = parse_score(scores_b, scores_a, True)
            else:
                if verbose:
                    print(f"  [WARN] Can't determine winner: {name_a} vs {name_b}")
                continue

            if not score:
                if verbose:
                    print(f"  [WARN] No score for: {winner_name} vs {loser_name}")
                continue

            matches.append({
                "round": sackmann_round,
                "winner_seed": winner_seed,
                "winner_entry": winner_entry,
                "winner_name": winner_name,
                "winner_ioc": winner_ioc,
                "loser_seed": loser_seed,
                "loser_entry": loser_entry,
                "loser_name": loser_name,
                "loser_ioc": loser_ioc,
                "score": score,
            })

    return matches


def parse_finals(finals_text, verbose=False):
    """Parse the finals bracket (QF, SF, F)."""
    return parse_section(finals_text, 0, FINALS_ROUND_MAP, verbose)


def parse_grand_slam(wikitext, verbose=False):
    """Parse an entire Grand Slam draw from wikitext."""
    all_matches = []

    # Parse each of the 8 sections
    for sec_num in range(1, 9):
        # Find section content
        sec_pattern = rf"====\s*Section {sec_num}\s*====(.*?)(?:====\s*Section {sec_num + 1}|====\s*Finals|$)"
        if sec_num == 8:
            sec_pattern = rf"====\s*Section 8\s*====(.*?)(?:===\s*(?:Bottom half|Finals|Withdrawn|Qualifying)|$)"

        m = re.search(sec_pattern, wikitext, re.DOTALL)
        if not m:
            # Try alternate section ending
            m = re.search(rf"====\s*Section {sec_num}\s*====(.*?)(?=====)", wikitext, re.DOTALL)
        if not m:
            if verbose:
                print(f"  [WARN] Section {sec_num} not found")
            continue

        section_text = m.group(1)
        matches = parse_section(section_text, sec_num, SECTION_ROUND_MAP, verbose)
        all_matches.extend(matches)
        if verbose:
            print(f"  Section {sec_num}: {len(matches)} matches")

    # Parse Finals (QF, SF, F)
    finals_match = re.search(r"===\s*Finals\s*===(.*?)(?:===\s*[A-Z]|$)", wikitext, re.DOTALL)
    if finals_match:
        finals_text = finals_match.group(1)
        finals_matches = parse_section(finals_text, 0, FINALS_ROUND_MAP, verbose)
        all_matches.extend(finals_matches)
        if verbose:
            print(f"  Finals: {len(finals_matches)} matches (QF+SF+F)")
    else:
        if verbose:
            print("  [WARN] Finals section not found")

    return all_matches


# ─── Player database ────────────────────────────────────────────
def build_player_db(csv_dir, pattern="wta_matches_*.csv"):
    """Build name -> {id, hand, ht, ioc} from all Sackmann WTA match files."""
    db = {}
    for f in sorted(csv_dir.glob(pattern)):
        with open(f, "r") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                wname = row.get("winner_name", "").strip()
                if wname and wname not in db:
                    db[wname] = {
                        "id": row.get("winner_id", ""),
                        "hand": row.get("winner_hand", ""),
                        "ht": row.get("winner_ht", ""),
                        "ioc": row.get("winner_ioc", ""),
                    }
                lname = row.get("loser_name", "").strip()
                if lname and lname not in db:
                    db[lname] = {
                        "id": row.get("loser_id", ""),
                        "hand": row.get("loser_hand", ""),
                        "ht": row.get("loser_ht", ""),
                        "ioc": row.get("loser_ioc", ""),
                    }
    return db


# Name aliases: Wikipedia name -> Sackmann canonical name
NAME_ALIASES = {
    "Jessica Bouzas Maneiro": "Jessica Bouzas Maneiro",
    "Magdalena Frech": "Magdalena Frech",
    "Linda Noskova": "Linda Noskova",
    "Mirra Andreeva": "Mirra Andreeva",
    "Donna Vekic": "Donna Vekic",
    "Anastasia Pavlyuchenkova": "Anastasia Pavlyuchenkova",
    "Qinwen Zheng": "Qinwen Zheng",
    "Beatriz Haddad Maia": "Beatriz Haddad Maia",
    "Caty Mcnally": "Caty Mcnally",
    "Caty McNally": "Caty Mcnally",
    "Catherine McNally": "Caty Mcnally",
    "Karolina Muchova": "Karolina Muchova",
    "Mccartney Kessler": "Mccartney Kessler",
    "McCartney Kessler": "Mccartney Kessler",
    # Chinese name order (Wikipedia) -> Western order (Sackmann)
    "Wang Xiyu": "Xiyu Wang",
    "Wang Yafan": "Yafan Wang",
    "Wang Xinyu": "Xinyu Wang",
    "Zheng Qinwen": "Qinwen Zheng",
    "Yuan Yue": "Yue Yuan",
    "Wei Sijia": "Sijia Wei",
    "Zhang Shuai": "Shuai Zhang",
    "Zheng Saisai": "Saisai Zheng",
    "Zhu Lin": "Lin Zhu",
    # Wikipedia disambiguation removed, but still need aliases
    "Ann Li": "Ann Li",
    "Francesca Jones": "Francesca Jones",
    # Sackmann uses full name
    "Anca Todoni": "Anca Alexia Todoni",
    # Sackmann spelling differences
    "Iga Swiatek": "Iga Swiatek",
    "Jelena Ostapenko": "Jelena Ostapenko",
    "Maja Chwalinska": "Maja Chwalinska",
    "Rebecca Sramkova": "Rebecca Sramkova",
    "Sorana Cirstea": "Sorana Cirstea",
    "Darja Semenistaja": "Darja Semenistaja",
    "Cristina Bucsa": "Cristina Bucsa",
    "Anastasiia Sobolieva": "Anastasiia Sobolieva",
    "Mimi Xu": "Mimi Xu",
}


def lookup_player(name, db):
    """Look up a player by name."""
    if name in db:
        return db[name]
    if name in NAME_ALIASES:
        canonical = NAME_ALIASES[name]
        if canonical in db:
            return db[canonical]
    # Try last-name match
    last_name = name.split()[-1] if name else ""
    candidates = [k for k in db if k.split()[-1] == last_name]
    if len(candidates) == 1:
        return db[candidates[0]]
    return None


ROUND_ORDER = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7}


def main():
    parser = argparse.ArgumentParser(
        description="Parse Wikipedia Grand Slam draws for WTA match data"
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--append", action="store_true", default=True,
                        help="Append to existing CSV (default: True)")
    args = parser.parse_args()

    if args.year != 2025:
        print(f"Only 2025 Grand Slams supported currently")
        return

    grand_slams = GRAND_SLAMS_2025

    # Build player DB
    if not args.dry_run:
        print("Building player database...")
        player_db = build_player_db(RAW_WTA)
        print(f"Player database: {len(player_db)} players")
    else:
        player_db = {}

    all_gs_matches = []

    for page_title, meta in grand_slams.items():
        print(f"\n--- {meta['name']} ---")

        if args.dry_run:
            encoded = urllib.parse.quote(page_title)
            url = f"https://en.wikipedia.org/w/api.php?action=parse&page={encoded}&prop=wikitext&format=json"
            print(f"  Would fetch: {url}")
            continue

        wikitext = fetch_wikitext(page_title, args.verbose)
        if not wikitext:
            print(f"  [SKIP] Could not fetch wikitext")
            continue
        time.sleep(1)

        matches = parse_grand_slam(wikitext, args.verbose)
        if matches:
            all_gs_matches.append((meta, matches))
            print(f"  Total: {len(matches)} matches")

            # Round distribution
            round_counts = {}
            for m in matches:
                rnd = m["round"]
                round_counts[rnd] = round_counts.get(rnd, 0) + 1
            for rnd in ["F", "SF", "QF", "R16", "R32", "R64", "R128"]:
                if rnd in round_counts:
                    print(f"    {rnd}: {round_counts[rnd]}")
        else:
            print(f"  [WARN] No matches parsed")

    if args.dry_run or not all_gs_matches:
        return

    # Generate rows
    all_rows = []
    for meta, matches in all_gs_matches:
        matches.sort(key=lambda m: ROUND_ORDER.get(m["round"], 0))
        match_count = len(matches)

        for i, match in enumerate(matches):
            match_num = match_count - i

            w_info = lookup_player(match["winner_name"], player_db)
            l_info = lookup_player(match["loser_name"], player_db)

            w_ioc = match.get("winner_ioc", "")
            l_ioc = match.get("loser_ioc", "")
            if w_info and w_info.get("ioc"):
                w_ioc = w_info["ioc"]
            if l_info and l_info.get("ioc"):
                l_ioc = l_info["ioc"]

            row = {
                "tourney_id": meta["tid"],
                "tourney_name": meta["name"],
                "surface": meta["surface"],
                "draw_size": meta["draw_size"],
                "tourney_level": meta["level"],
                "tourney_date": meta["date"],
                "match_num": match_num,
                "winner_id": w_info["id"] if w_info else "",
                "winner_seed": match.get("winner_seed", ""),
                "winner_entry": match.get("winner_entry", ""),
                "winner_name": match["winner_name"],
                "winner_hand": w_info["hand"] if w_info else "",
                "winner_ht": w_info["ht"] if w_info else "",
                "winner_ioc": w_ioc,
                "winner_age": "",
                "loser_id": l_info["id"] if l_info else "",
                "loser_seed": match.get("loser_seed", ""),
                "loser_entry": match.get("loser_entry", ""),
                "loser_name": match["loser_name"],
                "loser_hand": l_info["hand"] if l_info else "",
                "loser_ht": l_info["ht"] if l_info else "",
                "loser_ioc": l_ioc,
                "loser_age": "",
                "score": match["score"],
                "best_of": 3,
                "round": match["round"],
                "minutes": "",
                "w_ace": "", "w_df": "", "w_svpt": "", "w_1stIn": "",
                "w_1stWon": "", "w_2ndWon": "", "w_SvGms": "",
                "w_bpSaved": "", "w_bpFaced": "",
                "l_ace": "", "l_df": "", "l_svpt": "", "l_1stIn": "",
                "l_1stWon": "", "l_2ndWon": "", "l_SvGms": "",
                "l_bpSaved": "", "l_bpFaced": "",
                "winner_rank": "", "winner_rank_points": "",
                "loser_rank": "", "loser_rank_points": "",
            }
            all_rows.append(row)

    # Reverse within each tournament (F first)
    final_rows = []
    current_tid = None
    current_group = []
    for row in all_rows:
        if row["tourney_id"] != current_tid:
            if current_group:
                current_group.reverse()
                final_rows.extend(current_group)
            current_group = [row]
            current_tid = row["tourney_id"]
        else:
            current_group.append(row)
    if current_group:
        current_group.reverse()
        final_rows.extend(current_group)

    # Append to existing CSV
    csv_path = RAW_WTA / f"wta_matches_{args.year}.csv"
    existing_rows = []
    if csv_path.exists():
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    # Check for existing Grand Slam data (don't duplicate)
    existing_tids = {r["tourney_id"] for r in existing_rows}
    new_rows = [r for r in final_rows if r["tourney_id"] not in existing_tids]

    if not new_rows:
        print("\nAll Grand Slam data already in CSV. Nothing to add.")
        return

    combined = existing_rows + new_rows

    # Write combined CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(combined)

    # Summary
    print(f"\n=== Summary ===")
    print(f"Existing matches: {len(existing_rows)}")
    print(f"New Grand Slam matches: {len(new_rows)}")
    print(f"Total matches: {len(combined)}")
    print(f"Output: {csv_path}")

    # Player match rate
    matched = sum(1 for r in new_rows if r["winner_id"])
    print(f"Grand Slam winner IDs matched: {matched}/{len(new_rows)}")

    unmatched = set()
    for r in new_rows:
        for prefix in ["winner", "loser"]:
            name = r[f"{prefix}_name"]
            pid = r[f"{prefix}_id"]
            if not pid:
                unmatched.add(name)
    if unmatched:
        print(f"Unmatched players ({len(unmatched)}):")
        for name in sorted(unmatched)[:15]:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
