#!/usr/bin/env python3
"""
Scrape WTA match results from tennisabstract.com tournament pages
and produce Sackmann-compatible CSVs.

Data source: tennisabstract.com/current/{year}WTA{tournament}.html
Each page embeds a JavaScript variable `completedSingles` containing
all match results in a compact text format.

Output:
  - data/raw/tennis_wta/wta_matches_2025.csv
  - data/raw/tennis_wta/wta_matches_2026.csv

Usage:
  python scripts/scrape_wta_tennisabstract.py [--year 2025|2026] [--dry-run] [--verbose]
"""

import argparse
import csv
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─── Project paths ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_WTA = PROJECT_ROOT / "data" / "raw" / "tennis_wta"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# ─── Sackmann 49-column schema ──────────────────────────────────
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

# ─── Tournament databases ───────────────────────────────────────
# Key = tennisabstract URL slug (without .html)
# Values: name, surface, draw_size, level (Sackmann encoding), date, tid

TOURNAMENTS_2025 = {
    # January
    "2025WTABrisbane": {"name": "Brisbane", "surface": "Hard", "draw_size": 64, "level": "P", "date": "20250101", "tid": "2025-800"},
    "2025WTAAuckland": {"name": "Auckland", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250106", "tid": "2025-1049"},
    "2025WTAAdelaide": {"name": "Adelaide", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250106", "tid": "2025-2014"},
    "2025WTAHobart": {"name": "Hobart", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250113", "tid": "2025-1050"},
    "2025AustralianOpenWomen": {"name": "Australian Open", "surface": "Hard", "draw_size": 128, "level": "G", "date": "20250113", "tid": "2025-580"},
    "2025WTALinz": {"name": "Linz", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250127", "tid": "2025-528"},
    "2025WTASingapore": {"name": "Singapore", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250127", "tid": "2025-8996"},
    # February
    "2025WTAAbuDhabi": {"name": "Abu Dhabi", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250203", "tid": "2025-2088"},
    "2025WTAClujNapoca": {"name": "Cluj-Napoca", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250203", "tid": "2025-2050"},
    "2025WTADoha": {"name": "Doha", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20250210", "tid": "2025-1003"},
    "2025WTADubai": {"name": "Dubai", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20250217", "tid": "2025-718"},
    "2025WTAMerida": {"name": "Merida", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250217", "tid": "2025-2085"},
    "2025WTAAustin": {"name": "Austin", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250224", "tid": "2025-2082"},
    # March
    "2025WTAIndianWells": {"name": "Indian Wells", "surface": "Hard", "draw_size": 128, "level": "PM", "date": "20250305", "tid": "2025-609"},
    "2025WTAMiami": {"name": "Miami", "surface": "Hard", "draw_size": 128, "level": "PM", "date": "20250319", "tid": "2025-902"},
    "2025WTACharleston": {"name": "Charleston", "surface": "Clay", "draw_size": 64, "level": "P", "date": "20250331", "tid": "2025-804"},
    "2025WTABogota": {"name": "Bogota", "surface": "Clay", "draw_size": 32, "level": "I", "date": "20250331", "tid": "2025-894"},
    # April
    "2025WTAStuttgart": {"name": "Stuttgart", "surface": "Clay", "draw_size": 32, "level": "P", "date": "20250414", "tid": "2025-1051"},
    "2025WTARouen": {"name": "Rouen", "surface": "Clay", "draw_size": 32, "level": "I", "date": "20250414", "tid": "2025-2066"},
    "2025WTAMadrid": {"name": "Madrid", "surface": "Clay", "draw_size": 128, "level": "PM", "date": "20250421", "tid": "2025-1038"},
    # May
    "2025WTARome": {"name": "Rome", "surface": "Clay", "draw_size": 128, "level": "PM", "date": "20250505", "tid": "2025-709"},
    "2025WTAStrasbourg": {"name": "Strasbourg", "surface": "Clay", "draw_size": 32, "level": "P", "date": "20250519", "tid": "2025-406"},
    "2025WTARabat": {"name": "Rabat", "surface": "Clay", "draw_size": 32, "level": "I", "date": "20250519", "tid": "2025-1005"},
    "2025FrenchOpenWomen": {"name": "Roland Garros", "surface": "Clay", "draw_size": 128, "level": "G", "date": "20250526", "tid": "2025-520"},
    # June
    "2025WTASHertogenbosch": {"name": "s Hertogenbosch", "surface": "Grass", "draw_size": 32, "level": "I", "date": "20250609", "tid": "2025-822"},
    "2025WTANottingham": {"name": "Nottingham", "surface": "Grass", "draw_size": 32, "level": "I", "date": "20250609", "tid": "2025-1080"},
    "2025WTABirmingham": {"name": "Birmingham", "surface": "Grass", "draw_size": 32, "level": "P", "date": "20250616", "tid": "2025-1052"},
    "2025WTABerlin": {"name": "Berlin", "surface": "Grass", "draw_size": 32, "level": "P", "date": "20250616", "tid": "2025-2012"},
    "2025WTAEastbourne": {"name": "Eastbourne", "surface": "Grass", "draw_size": 32, "level": "P", "date": "20250623", "tid": "2025-710"},
    "2025WTABadHomburg": {"name": "Bad Homburg", "surface": "Grass", "draw_size": 32, "level": "P", "date": "20250623", "tid": "2025-2017"},
    "2025WimbledonWomen": {"name": "Wimbledon", "surface": "Grass", "draw_size": 128, "level": "G", "date": "20250630", "tid": "2025-540"},
    # July
    "2025WTAIasi": {"name": "Iasi", "surface": "Clay", "draw_size": 32, "level": "I", "date": "20250714", "tid": "2025-2063"},
    "2025WTAHamburg": {"name": "Hamburg", "surface": "Clay", "draw_size": 32, "level": "I", "date": "20250714", "tid": "2025-8997"},
    "2025WTAPrague": {"name": "Prague", "surface": "Clay", "draw_size": 32, "level": "I", "date": "20250721", "tid": "2025-1082"},
    "2025WTAWashingtonDc": {"name": "Washington", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250728", "tid": "2025-1045"},
    "2025WTAMontreal": {"name": "Toronto", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20250804", "tid": "2025-806"},
    # August
    "2025WTACincinnati": {"name": "Cincinnati", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20250811", "tid": "2025-1017"},
    "2025WTAMonterrey": {"name": "Monterrey", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250818", "tid": "2025-1039"},
    "2025WTACleveland": {"name": "Cleveland", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250818", "tid": "2025-2040"},
    "2025USOpenWomen": {"name": "Us Open", "surface": "Hard", "draw_size": 128, "level": "G", "date": "20250825", "tid": "2025-560"},
    # September
    "2025WTAGuadalajara500": {"name": "Guadalajara", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250908", "tid": "2025-2075"},
    "2025WTASaoPaulo": {"name": "Sao Paulo", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20250908", "tid": "2025-2072"},
    "2025WTASeoul": {"name": "Seoul", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20250915", "tid": "2025-1024"},
    "2025WTABeijing": {"name": "Beijing", "surface": "Hard", "draw_size": 128, "level": "PM", "date": "20250924", "tid": "2025-1020"},
    # October
    "2025WTAWuhan": {"name": "Wuhan", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20251006", "tid": "2025-1075"},
    "2025WTATokyo": {"name": "Tokyo", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20251013", "tid": "2025-405"},
    "2025WTANingbo": {"name": "Ningbo", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20251013", "tid": "2025-2092"},
    "2025WTAOsaka": {"name": "Pan Pacific Open", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20251020", "tid": "2025-1056"},
    "2025WTAGuangzhou": {"name": "Guangzhou", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20251020", "tid": "2025-1023"},
    "2025WTAHongKong": {"name": "Hong Kong", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20251020", "tid": "2025-1074"},
    "2025WTAJiujiang": {"name": "Jiujiang", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20251027", "tid": "2025-1077"},
    "2025WTAChennai": {"name": "Chennai", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20251027", "tid": "2025-8998"},
    # November
    "2025WTAFinals": {"name": "WTA Finals", "surface": "Hard", "draw_size": 8, "level": "F", "date": "20251103", "tid": "2025-808"},
}

# Grand Slams may use different URL slugs; try alternatives
GRAND_SLAM_ALTERNATIVES = {
    "2025AustralianOpenWomen": ["2025AustralianOpen", "2025WTAAustralianOpen"],
    "2025FrenchOpenWomen": ["2025FrenchOpen", "2025RolandGarros", "2025WTARolandGarros", "2025RolandGarrosWomen"],
    "2025WimbledonWomen": ["2025Wimbledon", "2025WTAWimbledon"],
    "2025USOpenWomen": ["2025USOpen", "2025WTAUSOpen"],
    "2026AustralianOpenWomen": ["2026AustralianOpen", "2026WTAAustralianOpen"],
}

TOURNAMENTS_2026 = {
    "2026WTABrisbane": {"name": "Brisbane", "surface": "Hard", "draw_size": 64, "level": "P", "date": "20260101", "tid": "2026-800"},
    "2026WTAAuckland": {"name": "Auckland", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20260105", "tid": "2026-1049"},
    "2026WTAHobart": {"name": "Hobart", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20260112", "tid": "2026-1050"},
    "2026AustralianOpenWomen": {"name": "Australian Open", "surface": "Hard", "draw_size": 128, "level": "G", "date": "20260119", "tid": "2026-580"},
    "2026WTALinz": {"name": "Linz", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20260126", "tid": "2026-528"},
    "2026WTASingapore": {"name": "Singapore", "surface": "Hard", "draw_size": 32, "level": "I", "date": "20260126", "tid": "2026-8996"},
    "2026WTAAbuDhabi": {"name": "Abu Dhabi", "surface": "Hard", "draw_size": 32, "level": "P", "date": "20260202", "tid": "2026-2088"},
    "2026WTADoha": {"name": "Doha", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20260209", "tid": "2026-1003"},
    "2026WTADubai": {"name": "Dubai", "surface": "Hard", "draw_size": 64, "level": "PM", "date": "20260216", "tid": "2026-718"},
    "2026WTAIndianWells": {"name": "Indian Wells", "surface": "Hard", "draw_size": 128, "level": "PM", "date": "20260304", "tid": "2026-609"},
}


# ─── Round mapping ──────────────────────────────────────────────
def get_round_map(draw_size):
    """Map tennisabstract round labels to Sackmann round labels."""
    if draw_size == 128:
        return {"R1": "R128", "R2": "R64", "R3": "R32", "R4": "R16",
                "QF": "QF", "SF": "SF", "F": "F", "RR": "RR", "BR": "BR"}
    elif draw_size == 64:
        return {"R1": "R64", "R2": "R32", "R3": "R16",
                "QF": "QF", "SF": "SF", "F": "F", "RR": "RR", "BR": "BR"}
    elif draw_size == 32:
        return {"R1": "R32", "R2": "R16",
                "QF": "QF", "SF": "SF", "F": "F", "RR": "RR", "BR": "BR"}
    elif draw_size == 16:
        return {"R1": "R16",
                "QF": "QF", "SF": "SF", "F": "F", "RR": "RR", "BR": "BR"}
    elif draw_size == 8:
        return {"RR": "RR", "SF": "SF", "F": "F", "BR": "BR"}
    else:
        # Fallback: same as 32
        return {"R1": "R32", "R2": "R16",
                "QF": "QF", "SF": "SF", "F": "F", "RR": "RR", "BR": "BR"}

# Sackmann round ordering (for match_num assignment: F=highest)
ROUND_ORDER = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "RR": 4,
               "QF": 5, "SF": 6, "BR": 6, "F": 7}


# ─── Score parsing ──────────────────────────────────────────────
def parse_compact_score(compact):
    """
    Convert tennisabstract compact score to Sackmann format.
    '64 36 76(4)' -> '6-4 3-6 7-6(4)'
    '64 63' -> '6-4 6-3'
    'W/O' -> 'W/O'
    '30 RET' -> '3-0 RET'
    """
    compact = compact.strip()
    if not compact:
        return ""
    if compact in ("W/O", "DEF", "walkover", "w/o"):
        return "W/O"

    parts = compact.split()
    result_parts = []
    for part in parts:
        if part in ("RET", "Ret.", "ret", "retired", "DEF", "ABD", "Default", "default"):
            result_parts.append("RET")
            continue
        if part in ("W/O", "w/o", "walkover", "Walkover"):
            return "W/O"
        # Already in Sackmann format: 6-4, 7-6(4), etc -- pass through
        if re.match(r'^\d+-\d+(\(\d+\))?$', part):
            result_parts.append(part)
            continue
        # Handle tiebreak: 76(4) -> 7-6(4)
        tb_match = re.match(r'^(\d)(\d)\((\d+)\)$', part)
        if tb_match:
            g1, g2, tb = tb_match.group(1), tb_match.group(2), tb_match.group(3)
            result_parts.append(f"{g1}-{g2}({tb})")
            continue
        # Handle regular set: 64 -> 6-4
        set_match = re.match(r'^(\d)(\d)$', part)
        if set_match:
            g1, g2 = set_match.group(1), set_match.group(2)
            result_parts.append(f"{g1}-{g2}")
            continue
        # Handle extended tiebreak or unusual scores: 1311 -> 13-11, etc
        if re.match(r'^\d{3,4}$', part):
            if len(part) == 3:
                result_parts.append(f"{part[0]}-{part[1:]}")
            elif len(part) == 4:
                result_parts.append(f"{part[:2]}-{part[2:]}")
            continue
        # Pass through anything else as-is
        result_parts.append(part)

    return " ".join(result_parts)


# ─── Match line parsing ─────────────────────────────────────────
# Pattern: "F: (1) Aryna Sabalenka (BLR) d. Jelena Ostapenko (LAT) 64 63"
# Or: "R2: Madison Keys (USA) d. (WC) Sloane Stephens (USA) 63 64"

MATCH_LINE_RE = re.compile(
    r'^(?P<round>[A-Z0-9]+):\s*'               # Round label
    r'(?P<winner_prefix>\([^)]+\)\s*)?'         # Optional seed/entry for winner
    r'(?P<winner_name>[A-Za-z\s\'\-\.]+?)\s*'   # Winner name
    r'\((?P<winner_ioc>[A-Z]{3})\)\s*'          # Winner IOC
    r'd\.\s*'                                    # "d." separator
    r'(?P<loser_prefix>\([^)]+\)\s*)?'          # Optional seed/entry for loser
    r'(?P<loser_name>[A-Za-z\s\'\-\.]+?)\s*'    # Loser name
    r'\((?P<loser_ioc>[A-Z]{3})\)\s*'           # Loser IOC
    r'(?P<score>.+)$'                            # Score
)


def parse_seed_entry(prefix):
    """Parse a prefix like '(1)' or '(WC)' or '(Q)' into (seed, entry)."""
    if not prefix:
        return "", ""
    prefix = prefix.strip()
    m = re.match(r'\((\d+)\)', prefix)
    if m:
        return m.group(1), ""
    m = re.match(r'\(([A-Za-z]+)\)', prefix)
    if m:
        entry = m.group(1).upper()
        return "", entry
    return "", ""


def parse_match_line(line, round_map, verbose=False):
    """Parse a single match line into a dict of fields."""
    line = line.strip()
    if not line:
        return None

    # Skip byes -- not real matches
    if ' bye' in line.lower():
        return None

    m = MATCH_LINE_RE.match(line)
    if not m:
        # Try more lenient parsing
        if verbose:
            print(f"  [WARN] Could not parse match line: {line[:100]}")
        return None

    ta_round = m.group("round")

    # Skip qualifying rounds (Q1, Q2, Q3) but NOT QF (quarterfinal)
    if ta_round.startswith("Q") and ta_round != "QF":
        return None

    # Map round
    sackmann_round = round_map.get(ta_round, ta_round)

    w_seed, w_entry = parse_seed_entry(m.group("winner_prefix"))
    l_seed, l_entry = parse_seed_entry(m.group("loser_prefix"))

    score = parse_compact_score(m.group("score"))

    return {
        "round": sackmann_round,
        "winner_seed": w_seed,
        "winner_entry": w_entry,
        "winner_name": m.group("winner_name").strip(),
        "winner_ioc": m.group("winner_ioc"),
        "loser_seed": l_seed,
        "loser_entry": l_entry,
        "loser_name": m.group("loser_name").strip(),
        "loser_ioc": m.group("loser_ioc"),
        "score": score,
    }


# ─── Page fetching and extraction ───────────────────────────────
def fetch_page(url, verbose=False):
    """Fetch a URL and return the HTML text, or None on error."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (tennis-xgboost research scraper)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"  [HTTP {e.code}] {url}")
        return None
    except Exception as e:
        if verbose:
            print(f"  [ERROR] {url}: {e}")
        return None


def strip_html_tags(text):
    """Remove HTML tags from text, preserving content."""
    return re.sub(r'<[^>]+>', '', text)


def extract_completed_singles(html):
    """Extract the completedSingles JavaScript variable from HTML.
    Returns a list of individual match lines (HTML stripped)."""
    raw = None
    # Try single-quoted string
    m = re.search(r"var\s+completedSingles\s*=\s*'(.*?)'\s*;", html, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # Try double-quoted string
        m = re.search(r'var\s+completedSingles\s*=\s*"(.*?)"\s*;', html, re.DOTALL)
        if m:
            raw = m.group(1)
    if not raw:
        return None
    # Split by <br/> BEFORE stripping HTML tags
    lines = re.split(r'<br\s*/?>', raw)
    # Strip HTML tags from each line, filter empty/nbsp
    result = []
    for line in lines:
        clean = strip_html_tags(line).strip()
        if clean and clean != '&nbsp;':
            # Also strip &nbsp; entities
            clean = clean.replace('&nbsp;', ' ').strip()
            if clean:
                result.append(clean)
    return result


def scrape_tournament(slug, meta, verbose=False):
    """Scrape a single tournament and return list of parsed matches."""
    base_url = "https://www.tennisabstract.com/current/"

    # Try primary URL
    urls_to_try = [f"{base_url}{slug}.html"]
    # Add alternatives for Grand Slams
    if slug in GRAND_SLAM_ALTERNATIVES:
        for alt in GRAND_SLAM_ALTERNATIVES[slug]:
            urls_to_try.append(f"{base_url}{alt}.html")

    html = None
    used_url = None
    for url in urls_to_try:
        html = fetch_page(url, verbose)
        if html:
            used_url = url
            break
        time.sleep(0.5)

    if not html:
        if verbose:
            print(f"  [SKIP] {slug}: no page found")
        return []

    lines = extract_completed_singles(html)
    if not lines:
        if verbose:
            print(f"  [SKIP] {slug}: no completedSingles variable found")
        return []

    round_map = get_round_map(meta["draw_size"])
    matches = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parsed = parse_match_line(line, round_map, verbose)
        if parsed:
            matches.append(parsed)

    if verbose:
        print(f"  [OK] {slug}: {len(matches)} main-draw matches from {used_url}")

    return matches


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


# Common name aliases: tennisabstract name -> Sackmann canonical name
NAME_ALIASES = {
    "Jimenez Kasintseva": "Vicky Jimenez Kasintseva",
    "Bouzas Maneiro": "Jessica Bouzas Maneiro",
    "Haddad Maia": "Beatriz Haddad Maia",
    "Zheng": "Qinwen Zheng",
    "Qinwen Zheng": "Qinwen Zheng",
    "Xiyu Wang": "Xiyu Wang",
    "Catherine McNally": "Caty Mcnally",
    "Caty McNally": "Caty Mcnally",
    "Victoria Mboko": "Victoria Mboko",
    "Camila Osorio Serrano": "Camila Osorio",
    "Marketa Vondrousova": "Marketa Vondrousova",
    "Karolina Pliskova": "Karolina Pliskova",
    "Barbora Krejcikova": "Barbora Krejcikova",
    "Kristyna Pliskova": "Kristyna Pliskova",
    "Wang Xinyu": "Xinyu Wang",
    "Wang Xiyu": "Xiyu Wang",
}


def lookup_player(name, db):
    """Look up a player by name in the player database."""
    if name in db:
        return db[name]
    if name in NAME_ALIASES:
        canonical = NAME_ALIASES[name]
        if canonical in db:
            return db[canonical]
    # Try last-name match as fallback (risky with common names)
    last_name = name.split()[-1] if name else ""
    candidates = [k for k in db if k.split()[-1] == last_name]
    if len(candidates) == 1:
        return db[candidates[0]]
    return None


# ─── CSV generation ─────────────────────────────────────────────
def generate_csv(all_tournament_matches, player_db, output_path):
    """
    Generate a Sackmann-compatible CSV from all tournament matches.
    all_tournament_matches: list of (meta_dict, matches_list) tuples
    """
    rows = []
    global_match_counter = 0

    # Sort tournaments by date
    all_tournament_matches.sort(key=lambda x: x[0]["date"])

    for meta, matches in all_tournament_matches:
        if not matches:
            continue

        # Sort matches within tournament: F first (highest match_num)
        # Assign round ordering
        def round_sort_key(m):
            return ROUND_ORDER.get(m["round"], 0)

        matches.sort(key=round_sort_key)

        # Assign match numbers (F gets highest)
        tourney_match_count = len(matches)
        for i, match in enumerate(matches):
            global_match_counter += 1
            match_num = tourney_match_count - i  # F=highest

            w_info = lookup_player(match["winner_name"], player_db)
            l_info = lookup_player(match["loser_name"], player_db)

            # Use IOC from scrape (tennisabstract provides it)
            w_ioc = match.get("winner_ioc", "")
            l_ioc = match.get("loser_ioc", "")
            # If we have player DB info, prefer its IOC (more reliable)
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
            rows.append(row)

    # Reverse within each tournament group so F is first row (Sackmann convention)
    # Actually, we need to re-sort: within each tournament, F first then down to R128
    final_rows = []
    current_tid = None
    current_group = []
    for row in rows:
        if row["tourney_id"] != current_tid:
            if current_group:
                current_group.reverse()  # F first
                final_rows.extend(current_group)
            current_group = [row]
            current_tid = row["tourney_id"]
        else:
            current_group.append(row)
    if current_group:
        current_group.reverse()
        final_rows.extend(current_group)

    # Write CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(final_rows)

    return final_rows


# ─── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Scrape WTA match results from tennisabstract.com"
    )
    parser.add_argument("--year", type=int, choices=[2025, 2026],
                        help="Scrape only this year (default: both)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List URLs without fetching")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay between requests in seconds (default: 1.0)")
    args = parser.parse_args()

    years_to_scrape = []
    if args.year:
        years_to_scrape = [args.year]
    else:
        years_to_scrape = [2025, 2026]

    # Build player database from historical data
    if not args.dry_run:
        print("Building player database from historical Sackmann WTA data...")
        player_db = build_player_db(RAW_WTA)
        print(f"Player database: {len(player_db)} players")
    else:
        player_db = {}

    for year in years_to_scrape:
        tournaments = TOURNAMENTS_2025 if year == 2025 else TOURNAMENTS_2026
        output_path = RAW_WTA / f"wta_matches_{year}.csv"

        print(f"\n{'='*60}")
        print(f"Scraping {year} WTA season ({len(tournaments)} tournaments)")
        print(f"Output: {output_path}")
        print(f"{'='*60}")

        if args.dry_run:
            base_url = "https://www.tennisabstract.com/current/"
            for slug, meta in tournaments.items():
                urls = [f"{base_url}{slug}.html"]
                if slug in GRAND_SLAM_ALTERNATIVES:
                    urls.extend([f"{base_url}{alt}.html"
                                 for alt in GRAND_SLAM_ALTERNATIVES[slug]])
                print(f"  {meta['name']:25s} | {meta['surface']:5s} | "
                      f"{meta['level']:2s} | draw={meta['draw_size']:3d} | "
                      f"{urls[0]}")
            continue

        all_matches = []
        success_count = 0
        skip_count = 0
        total_match_count = 0

        for slug, meta in tournaments.items():
            matches = scrape_tournament(slug, meta, args.verbose)
            if matches:
                all_matches.append((meta, matches))
                success_count += 1
                total_match_count += len(matches)
            else:
                skip_count += 1
            time.sleep(args.delay)

        if not all_matches:
            print(f"  No matches scraped for {year}. Skipping CSV generation.")
            continue

        # Generate CSV
        rows = generate_csv(all_matches, player_db, output_path)

        # Summary
        print(f"\n--- {year} Summary ---")
        print(f"  Tournaments scraped: {success_count}/{success_count + skip_count}")
        print(f"  Tournaments skipped: {skip_count}")
        print(f"  Total matches: {len(rows)}")

        # Round distribution
        round_counts = {}
        for row in rows:
            rnd = row["round"]
            round_counts[rnd] = round_counts.get(rnd, 0) + 1
        print("  Round distribution:")
        for rnd in ["F", "SF", "QF", "R16", "R32", "R64", "R128", "RR", "BR"]:
            if rnd in round_counts:
                print(f"    {rnd}: {round_counts[rnd]}")

        # Player match rate
        matched = sum(1 for row in rows if row["winner_id"])
        print(f"  Players matched to IDs: {matched}/{len(rows)} "
              f"({100*matched/len(rows):.1f}%)")

        # Unmatched players
        unmatched = set()
        for row in rows:
            for prefix in ["winner", "loser"]:
                name = row[f"{prefix}_name"]
                pid = row[f"{prefix}_id"]
                if not pid:
                    unmatched.add(name)
        if unmatched:
            print(f"  Unmatched players ({len(unmatched)}):")
            for name in sorted(unmatched)[:20]:
                print(f"    - {name}")
            if len(unmatched) > 20:
                print(f"    ... and {len(unmatched) - 20} more")

        print(f"\n  Output written to: {output_path}")
        print(f"  Column count: {len(COLUMNS)}")


if __name__ == "__main__":
    main()
