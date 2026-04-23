#!/usr/bin/env python3
"""
Fill the WTA November-December 2025 data gap.

The only WTA tour-level event in Nov-Dec 2025 was:
- WTA Finals (Riyadh), Nov 1-8, 2025, tourney_id 2025-808

WTA 125 events (Angers, Limoges) are excluded as the Sackmann dataset
only tracks tour-level events (G/PM/P/I/F).

Sources:
- tennisabstract.com/current/2025WTAWtaFinals.html
- olympics.com WTA Finals 2025 results
- wtatennis.com WTA Finals Riyadh 2025

Match data verified across multiple sources. Alexandrova replaced
Keys (illness) for final RR match.
"""

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'tennis_wta')
CSV_PATH = os.path.join(DATA_DIR, 'wta_matches_2025.csv')

HEADER = [
    'tourney_id', 'tourney_name', 'surface', 'draw_size', 'tourney_level',
    'tourney_date', 'match_num', 'winner_id', 'winner_seed', 'winner_entry',
    'winner_name', 'winner_hand', 'winner_ht', 'winner_ioc', 'winner_age',
    'loser_id', 'loser_seed', 'loser_entry', 'loser_name', 'loser_hand',
    'loser_ht', 'loser_ioc', 'loser_age', 'score', 'best_of', 'round',
    'minutes', 'w_ace', 'w_df', 'w_svpt', 'w_1stIn', 'w_1stWon', 'w_2ndWon',
    'w_SvGms', 'w_bpSaved', 'w_bpFaced', 'l_ace', 'l_df', 'l_svpt',
    'l_1stIn', 'l_1stWon', 'l_2ndWon', 'l_SvGms', 'l_bpSaved', 'l_bpFaced',
    'winner_rank', 'winner_rank_points', 'loser_rank', 'loser_rank_points'
]

# Player data: id, name, hand, height, ioc
PLAYERS = {
    'Sabalenka':     ('214544', 'Aryna Sabalenka',      'R', '182', 'BLR'),
    'Swiatek':       ('216347', 'Iga Swiatek',          'R', '176', 'POL'),
    'Gauff':         ('221103', 'Coco Gauff',           'R', '175', 'USA'),
    'Anisimova':     ('216153', 'Amanda Anisimova',     'R', '180', 'USA'),
    'Pegula':        ('202468', 'Jessica Pegula',       'R', '170', 'USA'),
    'Rybakina':      ('214981', 'Elena Rybakina',       'R', '184', 'KAZ'),
    'Keys':          ('201619', 'Madison Keys',         'R', '178', 'USA'),
    'Paolini':       ('211148', 'Jasmine Paolini',      'R', '160', 'ITA'),
    'Alexandrova':   ('206420', 'Ekaterina Alexandrova', 'R', '175', 'RUS'),
}

# Seeds at 2025 WTA Finals
SEEDS = {
    'Sabalenka': '1',
    'Swiatek': '2',
    'Gauff': '3',
    'Anisimova': '4',
    'Pegula': '5',
    'Rybakina': '6',
    'Keys': '7',
    'Paolini': '8',
    'Alexandrova': '',  # alternate
}

# Entry type (ALT for alternate)
ENTRIES = {
    'Alexandrova': 'ALT',
}

# Tournament metadata
TOURNEY = {
    'tourney_id': '2025-808',
    'tourney_name': 'Riyadh Finals',
    'surface': 'Hard',
    'draw_size': '8',
    'tourney_level': 'F',
    'tourney_date': '20251101',
}

# All matches: (winner_key, loser_key, score, round)
# Matches numbered 300 down (following Sackmann convention from 2024)
#
# Stefanie Graf Group (Sabalenka, Gauff, Pegula, Paolini):
#   RR1: Sabalenka d. Paolini 6-3 6-1
#   RR2: Pegula d. Gauff 6-3 6-7(4) 6-2
#   RR3: Sabalenka d. Pegula 6-4 2-6 6-3
#   RR4: Gauff d. Paolini 6-3 6-2
#   RR5: Sabalenka d. Gauff 7-6(5) 6-2
#   RR6: Pegula d. Paolini 6-2 6-3
#
# Serena Williams Group (Rybakina, Swiatek, Anisimova, Keys/Alexandrova):
#   RR7: Swiatek d. Keys 6-1 6-2
#   RR8: Rybakina d. Anisimova 6-3 6-1
#   RR9: Rybakina d. Swiatek 3-6 6-1 6-0
#   RR10: Anisimova d. Keys 4-6 6-3 6-2
#   RR11: Anisimova d. Swiatek 6-7(3) 6-4 6-2
#   RR12: Rybakina d. Alexandrova 6-4 6-4  (Keys withdrew, Alexandrova replaced)
#
# Semifinals:
#   SF1: Sabalenka d. Anisimova 6-3 3-6 6-3
#   SF2: Rybakina d. Pegula 4-6 6-4 6-3
#
# Final:
#   F: Rybakina d. Sabalenka 6-3 7-6(0)

MATCHES = [
    # match_num, winner, loser, score, round
    (300, 'Sabalenka',   'Paolini',      '6-3 6-1',         'RR'),
    (299, 'Pegula',      'Gauff',        '6-3 6-7(4) 6-2',  'RR'),
    (298, 'Swiatek',     'Keys',         '6-1 6-2',         'RR'),
    (297, 'Rybakina',    'Anisimova',    '6-3 6-1',         'RR'),
    (296, 'Sabalenka',   'Pegula',       '6-4 2-6 6-3',     'RR'),
    (295, 'Gauff',       'Paolini',      '6-3 6-2',         'RR'),
    (294, 'Rybakina',    'Swiatek',      '3-6 6-1 6-0',     'RR'),
    (293, 'Anisimova',   'Keys',         '4-6 6-3 6-2',     'RR'),
    (292, 'Sabalenka',   'Gauff',        '7-6(5) 6-2',      'RR'),
    (291, 'Pegula',      'Paolini',      '6-2 6-3',         'RR'),
    (290, 'Anisimova',   'Swiatek',      '6-7(3) 6-4 6-2',  'RR'),
    (289, 'Rybakina',    'Alexandrova',  '6-4 6-4',         'RR'),
    (288, 'Sabalenka',   'Anisimova',    '6-3 3-6 6-3',     'SF'),
    (287, 'Rybakina',    'Pegula',       '4-6 6-4 6-3',     'SF'),
    (286, 'Rybakina',    'Sabalenka',    '6-3 7-6(0)',       'F'),
]


def make_row(match_num, winner_key, loser_key, score, round_name):
    """Build a CSV row following exact Sackmann schema."""
    w = PLAYERS[winner_key]
    l = PLAYERS[loser_key]

    row = {
        **TOURNEY,
        'match_num': str(match_num),
        'winner_id': w[0],
        'winner_seed': SEEDS.get(winner_key, ''),
        'winner_entry': ENTRIES.get(winner_key, ''),
        'winner_name': w[1],
        'winner_hand': w[2],
        'winner_ht': w[3],
        'winner_ioc': w[4],
        'winner_age': '',
        'loser_id': l[0],
        'loser_seed': SEEDS.get(loser_key, ''),
        'loser_entry': ENTRIES.get(loser_key, ''),
        'loser_name': l[1],
        'loser_hand': l[2],
        'loser_ht': l[3],
        'loser_ioc': l[4],
        'loser_age': '',
        'score': score,
        'best_of': '3',
        'round': round_name,
        'minutes': '',
        'w_ace': '', 'w_df': '', 'w_svpt': '', 'w_1stIn': '',
        'w_1stWon': '', 'w_2ndWon': '', 'w_SvGms': '',
        'w_bpSaved': '', 'w_bpFaced': '',
        'l_ace': '', 'l_df': '', 'l_svpt': '', 'l_1stIn': '',
        'l_1stWon': '', 'l_2ndWon': '', 'l_SvGms': '',
        'l_bpSaved': '', 'l_bpFaced': '',
        'winner_rank': '', 'winner_rank_points': '',
        'loser_rank': '', 'loser_rank_points': '',
    }

    return [row[h] for h in HEADER]


def main():
    # Verify existing file
    with open(CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        existing_header = next(reader)
        assert existing_header == HEADER, f"Header mismatch!\nExpected: {HEADER}\nGot: {existing_header}"
        existing_rows = list(reader)

    print(f"Existing rows: {len(existing_rows)}")

    # Check if WTA Finals already in file
    finals_rows = [r for r in existing_rows if r[0] == '2025-808']
    if finals_rows:
        print(f"WARNING: WTA Finals 2025 already has {len(finals_rows)} rows in file. Skipping.")
        return

    # Check last tourney_date
    dates = sorted(set(r[5] for r in existing_rows))
    print(f"Date range: {dates[0]} to {dates[-1]}")

    # Generate new rows
    new_rows = []
    for match_num, winner, loser, score, round_name in MATCHES:
        new_rows.append(make_row(match_num, winner, loser, score, round_name))

    print(f"New matches to add: {len(new_rows)}")

    # Append to CSV
    with open(CSV_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        for row in new_rows:
            writer.writerow(row)

    # Verify
    with open(CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        all_rows = list(reader)

    print(f"\nAfter append:")
    print(f"  Total rows: {len(all_rows)}")

    finals = [r for r in all_rows if r[0] == '2025-808']
    print(f"  WTA Finals matches: {len(finals)}")

    dates = sorted(set(r[5] for r in all_rows))
    print(f"  Date range: {dates[0]} to {dates[-1]}")
    print(f"  Last date: {dates[-1]}")

    # Verify column count
    bad = [i for i, r in enumerate(all_rows) if len(r) != len(HEADER)]
    if bad:
        print(f"  ERROR: {len(bad)} rows have wrong column count!")
    else:
        print(f"  All rows have correct column count ({len(HEADER)})")

    print("\nTournaments added:")
    print("  - 2025 WTA Finals (Riyadh), Nov 1-8, 15 matches")
    print("    Winner: Elena Rybakina d. Aryna Sabalenka 6-3 7-6(0)")
    print("\nNote: No other WTA tour-level events in Nov-Dec 2025.")
    print("WTA 125 events (Angers, Limoges) excluded per Sackmann schema.")


if __name__ == '__main__':
    main()
