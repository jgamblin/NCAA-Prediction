#!/usr/bin/env python3
"""Backfill remaining missing D1 teams by targeted season fetch.

Uses all_games.fetch_all_games with --teams restriction across configured seasons.
Merges new games into existing Completed_Games.csv without dropping current data.

Targets (default): UCF,VMI,"St. Thomas (MN)"
Note: St. Thomas (MN) may legitimately have zero games if not present in source repo for early seasons.

Usage:
    python data_collection/backfill_missing_d1.py
    python data_collection/backfill_missing_d1.py --teams="UCF,VMI,St. Thomas (MN)" --seasons="2024-25"
"""
import os
import sys
import pandas as pd
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
COMPLETED = os.path.join(DATA, 'Completed_Games.csv')

sys.path.insert(0, ROOT)
from data_collection.all_games import fetch_all_games, SEASONS as DEFAULT_SEASONS
from data_collection.team_name_utils import normalize_team_name

def parse_arg(name: str, default: List[str]) -> List[str]:
    for arg in sys.argv[1:]:
        if arg.startswith(f"--{name}="):
            raw = arg.split('=',1)[1]
            return [x.strip() for x in raw.split(',') if x.strip()]
    return default

def main():
    target_teams = parse_arg('teams', ['UCF','VMI','St. Thomas (MN)'])
    seasons = parse_arg('seasons', DEFAULT_SEASONS)

    if not os.path.exists(COMPLETED):
        print(f"Missing base file: {COMPLETED}")
        sys.exit(1)

    base_df = pd.read_csv(COMPLETED)
    existing_ids = set(str(x) for x in base_df['game_id'].astype(str))

    print(f"Starting backfill for {len(target_teams)} teams across {len(seasons)} seasons.")
    print(f"Teams: {', '.join(target_teams)}")

    new_games = []
    for season in seasons:
        print(f"--- Season {season} ---")
        df_season = fetch_all_games(season, limit_teams=target_teams)
        if df_season.empty:
            print(f"No games fetched for season {season} (teams may be absent in source).")
            continue
        # Filter to completed only for consistency
        df_season = df_season[df_season['game_status'] == 'Final']
        # Deduplicate against existing
        df_season['game_id'] = df_season['game_id'].astype(str)
        fresh = df_season[~df_season['game_id'].isin(existing_ids)].copy()
        print(f"Fetched {len(df_season)} games; {len(fresh)} are new.")
        new_games.append(fresh)

    if not new_games:
        print("No new games discovered. Backfill complete.")
        return

    add_df = pd.concat(new_games, ignore_index=True)
    merged = pd.concat([base_df, add_df], ignore_index=True)
    merged = merged.drop_duplicates(subset=['game_id'], keep='last')

    # Normalize new rows teams for consistency
    merged['home_team'] = merged['home_team'].apply(normalize_team_name)
    merged['away_team'] = merged['away_team'].apply(normalize_team_name)

    merged.to_csv(COMPLETED, index=False)
    print(f"Added {len(add_df)} new games. Completed_Games.csv now has {len(merged)} rows.")

if __name__ == '__main__':
    main()
