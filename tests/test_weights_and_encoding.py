import os
import sys
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

# Ensure repository root is on the path for local package imports
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from model_training.model_bakeoff import calculate_sample_weights, prepare_data  # noqa: E402

def make_dummy_df():
    data = {
        'game_day': pd.date_range('2025-11-01', periods=6, freq='D'),
        'season': ['2025-26']*6,
        'home_team': ['A','B','C','A','B','C'],
        'away_team': ['B','C','A','C','A','B'],
        'home_score':[80,75,70,85,66,90],
        'away_score':[70,80,75,80,70,85],
        'is_neutral':[0,0,1,0,1,0],
        'home_rank':[10,20,30,10,20,30],
        'away_rank':[15,25,35,15,25,35]
    }
    df = pd.DataFrame(data)
    return prepare_data(df)

def test_weight_monotonic_recency():
    df = make_dummy_df()
    weights = calculate_sample_weights(df, current_season='2025-26')
    # Later dates should have >= earlier dates within same season due to recency multiplier
    by_date = pd.DataFrame({'date':df['game_day'], 'w':weights}).sort_values('date')
    assert all(np.diff(by_date['w']) >= -1e-9), 'Weights should be non-decreasing over time in current season'

def test_unknown_team_encoding():
    df = make_dummy_df()
    enc = LabelEncoder().fit(['A','B','C'])
    mapping = {team: idx for idx, team in enumerate(enc.classes_)}
    # known
    assert mapping['A'] >= 0
    # simulate unknown
    unknown_team = 'Z'
    encoded = mapping.get(unknown_team, -1)
    assert encoded == -1

def test_prepare_data_adds_home_win():
    df = make_dummy_df()
    assert 'home_win' in df.columns
    assert set(df['home_win'].unique()).issubset({0,1})
