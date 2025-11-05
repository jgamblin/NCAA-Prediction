#!/usr/bin/env python3
"""Check Division I coverage against normalized dataset.

Reads:
- data/Completed_Games.csv (already normalized after regeneration)
- data/d1_teams_canonical_2024_25.csv (authoritative canonical team list for 2024-25)

Outputs:
- Summary of total distinct teams in dataset
- Missing D1 teams (never appear in any game)
- Extra/non-D1 teams present in dataset (likely exhibitions or lower divisions)
- Low-game D1 teams (appear < threshold, default 75) for visibility

Usage:
    python data_collection/check_d1_coverage.py
"""
import os
import sys
import pandas as pd
from collections import Counter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, 'data')
D1_LIST = os.path.join(DATA_DIR, 'd1_teams_canonical_2024_25.csv')
COMPLETED_PATH = os.path.join(DATA_DIR, 'Completed_Games.csv')
THRESHOLD = 75

sys.path.insert(0, ROOT_DIR)
from data_collection.team_name_utils import normalize_team_name

def load_d1_list(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"D1 list file not found: {path}")
    df = pd.read_csv(path)
    teams = [normalize_team_name(t) for t in df['team_name'].dropna().tolist()]
    return sorted(set(teams))

def load_completed(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Completed games file not found: {path}")
    df = pd.read_csv(path)
    # Normalize just in case
    df['home_team'] = df['home_team'].apply(normalize_team_name)
    df['away_team'] = df['away_team'].apply(normalize_team_name)
    return df

def build_team_game_counts(df):
    counts = Counter()
    for _, row in df.iterrows():
        counts[row['home_team']] += 1
        counts[row['away_team']] += 1
    return counts

def main():
    d1_teams = load_d1_list(D1_LIST)
    games_df = load_completed(COMPLETED_PATH)
    counts = build_team_game_counts(games_df)

    dataset_teams = sorted(counts.keys())

    missing_d1 = [t for t in d1_teams if t not in counts]
    # Heuristic: extras are dataset teams not in authoritative list
    extras = [t for t in dataset_teams if t not in d1_teams]

    low_game_d1 = [(t, counts[t]) for t in d1_teams if t in counts and counts[t] < THRESHOLD]
    low_game_d1.sort(key=lambda x: x[1])

    print("="*80)
    print("Division I Coverage Report (2024-25 canonical list)")
    print("="*80)
    print(f"Total games in dataset: {len(games_df):,}")
    print(f"Distinct normalized teams in dataset: {len(dataset_teams):,}")
    print(f"Canonical D1 teams listed: {len(d1_teams):,}")
    print()
    print(f"Missing D1 teams (0 games): {len(missing_d1)}")
    if missing_d1:
        for t in missing_d1:
            print(f"  - {t}")
    else:
        print("  None (all covered)")
    print()
    print(f"Extra teams in dataset (non-D1 or exhibitions): {len(extras)}")
    if extras:
        for t in extras[:50]:  # limit display
            print(f"  - {t}")
        if len(extras) > 50:
            print(f"  ... (+{len(extras)-50} more)")
    else:
        print("  None")
    print()
    print(f"D1 teams below {THRESHOLD} games: {len(low_game_d1)}")
    if low_game_d1:
        for t, c in low_game_d1[:40]:  # limit
            print(f"  {t:30} {c:4}")
        if len(low_game_d1) > 40:
            print(f"  ... (+{len(low_game_d1)-40} more)")
    else:
        print("  None (all meet threshold)")

    # Sanity: show a few high-count teams
    top_counts = sorted([(t, c) for t, c in counts.items() if t in d1_teams], key=lambda x: -x[1])[:10]
    print("\nTop 10 D1 teams by game count:")
    for t, c in top_counts:
        print(f"  {t:25} {c:5}")

    print("\nReport complete.")
    print("="*80)

if __name__ == '__main__':
    main()
