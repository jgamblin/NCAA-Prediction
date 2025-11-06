import pandas as pd
from model_training.simple_predictor import SimplePredictor  # type: ignore


def test_simple_predictor_end_to_end():
    train_df = pd.DataFrame([
        {
            'game_id': 'G1', 'home_team': 'TeamA', 'away_team': 'TeamB',
            'home_score': 70, 'away_score': 65, 'home_team_id': 1, 'away_team_id': 2,
            'home_win': 1
        },
        {
            'game_id': 'G2', 'home_team': 'TeamC', 'away_team': 'TeamA',
            'home_score': 60, 'away_score': 75, 'home_team_id': 3, 'away_team_id': 1,
            'home_win': 0
        }
    ])
    upcoming_df = pd.DataFrame([
        {
            'game_id': 'G3', 'home_team': 'TeamA', 'away_team': 'TeamC',
            'home_team_id': 1, 'away_team_id': 3, 'date': '2025-11-06', 'game_url': 'http://example.com/G3'
        },
        {
            'game_id': 'G4', 'home_team': 'TeamB', 'away_team': 'TeamC',
            'home_team_id': 2, 'away_team_id': 3, 'date': '2025-11-06', 'game_url': 'http://example.com/G4'
        }
    ])
    predictor = SimplePredictor(min_games_threshold=0, calibrate=False)
    predictor.fit(train_df)
    preds = predictor.predict(upcoming_df)
    assert len(preds) == len(upcoming_df)
    assert 'predicted_winner' in preds.columns
    assert 'confidence' in preds.columns
