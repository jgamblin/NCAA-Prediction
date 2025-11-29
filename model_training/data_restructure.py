"""
data_restructure.py

Expands games to one row per team-game for rolling feature calculation.
"""
import pandas as pd

def expand_to_team_games(games_df):
    rows = []
    for _, r in games_df.iterrows():
        # Home team
        rows.append({
            'game_id': r['game_id'],
            'season': r['season'],
            'date': r['date'],
            'team_id': r['home_team_id'],
            'opponent_id': r['away_team_id'],
            'is_home': 1,
            'won': int(r['home_score'] > r['away_score']),
            'point_diff': int(r['home_score']) - int(r['away_score'])
        })
        # Away team
        rows.append({
            'game_id': r['game_id'],
            'season': r['season'],
            'date': r['date'],
            'team_id': r['away_team_id'],
            'opponent_id': r['home_team_id'],
            'is_home': 0,
            'won': int(r['away_score'] > r['home_score']),
            'point_diff': int(r['away_score']) - int(r['home_score'])
        })
    return pd.DataFrame(rows)
