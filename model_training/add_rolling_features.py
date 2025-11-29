"""
add_rolling_features.py

Provides point-in-time correct rolling feature engineering for NCAA games.
"""
import pandas as pd
import numpy as np

def add_rolling_features(team_games_df: pd.DataFrame, windows=[5, 10]):
    """
    Adds rolling features (win %, point diff avg, etc.) for each team-game, using only past data.
    Expects one row per team-game (not matchup).
    """
    team_games_df = team_games_df.sort_values(['season', 'team_id', 'date', 'game_id']).copy()
    for w in windows:
        # Rolling win %
        team_games_df[f'rolling_win_pct_{w}'] = (
            team_games_df.groupby(['season', 'team_id'])['won']
            .transform(lambda x: x.shift(1).rolling(window=w, min_periods=1).mean())
        )
        # Rolling point diff avg
        team_games_df[f'rolling_point_diff_avg_{w}'] = (
            team_games_df.groupby(['season', 'team_id'])['point_diff']
            .transform(lambda x: x.shift(1).rolling(window=w, min_periods=1).mean())
        )
    # Deltas
    team_games_df['win_pct_last5_vs10'] = (
        team_games_df['rolling_win_pct_5'] - team_games_df['rolling_win_pct_10']
    )
    team_games_df['point_diff_last5_vs10'] = (
        team_games_df['rolling_point_diff_avg_5'] - team_games_df['rolling_point_diff_avg_10']
    )
    team_games_df['recent_strength_index_5'] = (
        team_games_df['rolling_win_pct_5'] * team_games_df['rolling_point_diff_avg_5']
    )
    return team_games_df
