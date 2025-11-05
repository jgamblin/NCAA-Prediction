#!/usr/bin/env python3
"""Filter Completed_Games.csv down to Division I vs Division I matchups only.

Uses canonical D1 list (data/d1_teams_canonical_2024_25.csv) and normalization.
Outputs data/Completed_Games_D1_Only.csv
Also prints:
- Total games retained
- Games removed (non-D1 opponent or non-D1 vs D1)
- Distinct D1 teams present
"""
import os
import sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
INPUT = os.path.join(DATA, 'Completed_Games.csv')
D1_PATH = os.path.join(DATA, 'd1_teams_canonical_2024_25.csv')
OUT = os.path.join(DATA, 'Completed_Games_D1_Only.csv')

sys.path.insert(0, ROOT)
from data_collection.team_name_utils import normalize_team_name

def load_d1():
    df = pd.read_csv(D1_PATH)
    names = [normalize_team_name(x) for x in df['team_name'].dropna().tolist()]
    return set(names)

def main():
    if not os.path.exists(INPUT):
        print(f"Input not found: {INPUT}")
        sys.exit(1)
    d1 = load_d1()
    df = pd.read_csv(INPUT)
    df['home_team'] = df['home_team'].apply(normalize_team_name)
    df['away_team'] = df['away_team'].apply(normalize_team_name)

    mask = df['home_team'].isin(d1) & df['away_team'].isin(d1)
    d1_df = df[mask].copy()
    d1_df.to_csv(OUT, index=False)

    removed = len(df) - len(d1_df)
    print(f"D1-only games written: {len(d1_df)}")
    print(f"Removed (non-D1 involvement): {removed}")
    print(f"Distinct D1 teams in retained games: {len(set(d1_df['home_team']) | set(d1_df['away_team']))}")
    print(f"Output: {OUT}")

if __name__ == '__main__':
    main()
