"""Minimal stub implementation for sample weighting and data preparation used in tests.
Provides:
- prepare_data(df): adds home_win column.
- calculate_sample_weights(df, current_season): returns numpy array of weights with recency emphasis for current season.
This is a lightweight placeholder until full bakeoff logic is implemented.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns needed for modeling.
    Currently only computes home_win as a binary outcome.
    """
    out = df.copy()
    if 'home_score' in out.columns and 'away_score' in out.columns:
        out['home_win'] = (out['home_score'] > out['away_score']).astype(int)
    else:
        out['home_win'] = 0
    return out

def calculate_sample_weights(df: pd.DataFrame, current_season: str) -> np.ndarray:
    """Assign sample weights with simple recency emphasis for rows in current_season.
    Weights are >=1.0 baseline; within current season they increase monotonically by date.
    """
    if 'game_day' not in df.columns:
        return np.ones(len(df))
    # Ensure datetime
    game_days = pd.to_datetime(df['game_day'])
    min_day = game_days.min()
    max_day = game_days.max()
    span_days = (max_day - min_day).days + 1
    weights = []
    for idx, row in df.iterrows():
        base = 1.0
        if row.get('season') == current_season:
            # Recency factor scaled 1..2 (earliest -> ~1, latest -> ~2)
            day_pos = (pd.to_datetime(row['game_day']) - min_day).days + 1
            recency_factor = day_pos / span_days  # in (0,1]
            base += recency_factor  # in (1,2]
        weights.append(base)
    return np.array(weights)
