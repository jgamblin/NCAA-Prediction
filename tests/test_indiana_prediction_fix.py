#!/usr/bin/env python3
"""
Test that team name normalization plus ID integration yields a sensible Indiana vs Alabama A&M prediction.
Relocated from root (test_indiana_fix.py).
"""

import pandas as pd
from model_training.simple_predictor import SimplePredictor
from data_collection.team_name_utils import normalize_team_name

TARGET_GAME_ID = 401827172  # Alabama A&M @ Indiana


def test_indiana_prediction_reasonable():
    completed = pd.read_csv('data/Completed_Games.csv')
    upcoming = pd.read_csv('data/Upcoming_Games.csv')
    game = upcoming[upcoming['game_id'] == TARGET_GAME_ID].copy()
    assert not game.empty, "Indiana upcoming game not found"

    predictor = SimplePredictor()
    predictor.fit(completed)
    preds = predictor.predict(game)
    assert not preds.empty, "No prediction generated for Indiana game"

    row = preds.iloc[0]
    home_norm = normalize_team_name(game['home_team'].values[0])
    assert row['predicted_winner'] == home_norm, (
        f"Expected home team {home_norm} to be predicted winner, got {row['predicted_winner']}"
    )
    assert row['confidence'] >= 0.6, "Indiana prediction confidence unexpectedly low (<60%)"
