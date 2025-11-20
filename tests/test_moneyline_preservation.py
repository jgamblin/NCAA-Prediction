"""
Tests for moneyline preservation in predictions.
Ensures that betting-related columns from upcoming games are preserved in predictions.
"""
import pandas as pd
from model_training.adaptive_predictor import AdaptivePredictor  # type: ignore


def test_moneyline_columns_preserved():
    """Test that moneyline columns are preserved when generating predictions."""
    # Create minimal training data
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
        },
        {
            'game_id': 'G3', 'home_team': 'TeamB', 'away_team': 'TeamC',
            'home_score': 80, 'away_score': 70, 'home_team_id': 2, 'away_team_id': 3,
            'home_win': 1
        }
    ])
    
    # Create upcoming games with moneyline data
    upcoming_df = pd.DataFrame([
        {
            'game_id': 'U1', 'home_team': 'TeamA', 'away_team': 'TeamC',
            'home_team_id': 1, 'away_team_id': 3, 
            'date': '2025-11-20', 'game_url': 'http://example.com/U1',
            'home_moneyline': -150, 'away_moneyline': 130, 'has_real_odds': True
        },
        {
            'game_id': 'U2', 'home_team': 'TeamB', 'away_team': 'TeamC',
            'home_team_id': 2, 'away_team_id': 3,
            'date': '2025-11-20', 'game_url': 'http://example.com/U2',
            'home_moneyline': -200, 'away_moneyline': 175, 'has_real_odds': True
        },
        {
            'game_id': 'U3', 'home_team': 'TeamA', 'away_team': 'TeamB',
            'home_team_id': 1, 'away_team_id': 2,
            'date': '2025-11-20', 'game_url': 'http://example.com/U3',
            'home_moneyline': None, 'away_moneyline': None, 'has_real_odds': False
        }
    ])
    
    # Generate predictions
    predictor = AdaptivePredictor(min_games_threshold=0, calibrate=False)  # type: ignore[arg-type]
    predictor.fit(train_df)
    predictions = predictor.predict(upcoming_df)
    
    # Verify moneyline columns are preserved
    assert 'home_moneyline' in predictions.columns, "home_moneyline column missing in predictions"
    assert 'away_moneyline' in predictions.columns, "away_moneyline column missing in predictions"
    assert 'has_real_odds' in predictions.columns, "has_real_odds column missing in predictions"
    
    # Verify values are correct
    assert len(predictions) == 3, "Expected 3 predictions"
    
    # Check first game (with real odds)
    game1 = predictions[predictions['game_id'] == 'U1'].iloc[0]
    assert game1['home_moneyline'] == -150, "home_moneyline value mismatch for U1"
    assert game1['away_moneyline'] == 130, "away_moneyline value mismatch for U1"
    assert game1['has_real_odds'] == True, "has_real_odds value mismatch for U1"
    
    # Check second game (with real odds)
    game2 = predictions[predictions['game_id'] == 'U2'].iloc[0]
    assert game2['home_moneyline'] == -200, "home_moneyline value mismatch for U2"
    assert game2['away_moneyline'] == 175, "away_moneyline value mismatch for U2"
    assert game2['has_real_odds'] == True, "has_real_odds value mismatch for U2"
    
    # Check third game (without real odds)
    game3 = predictions[predictions['game_id'] == 'U3'].iloc[0]
    assert pd.isna(game3['home_moneyline']), "home_moneyline should be NaN for U3"
    assert pd.isna(game3['away_moneyline']), "away_moneyline should be NaN for U3"
    assert game3['has_real_odds'] == False, "has_real_odds value mismatch for U3"


def test_predictions_without_moneylines():
    """Test that predictions work even when moneyline columns are missing."""
    # Create minimal training data with both wins and losses
    train_df = pd.DataFrame([
        {
            'game_id': 'G1', 'home_team': 'TeamA', 'away_team': 'TeamB',
            'home_score': 70, 'away_score': 65, 'home_team_id': 1, 'away_team_id': 2,
            'home_win': 1
        },
        {
            'game_id': 'G2', 'home_team': 'TeamA', 'away_team': 'TeamB',
            'home_score': 60, 'away_score': 75, 'home_team_id': 1, 'away_team_id': 2,
            'home_win': 0
        }
    ])
    
    # Create upcoming games WITHOUT moneyline data
    upcoming_df = pd.DataFrame([
        {
            'game_id': 'U1', 'home_team': 'TeamA', 'away_team': 'TeamB',
            'home_team_id': 1, 'away_team_id': 2,
            'date': '2025-11-20', 'game_url': 'http://example.com/U1'
        }
    ])
    
    # Generate predictions
    predictor = AdaptivePredictor(min_games_threshold=0, calibrate=False)  # type: ignore[arg-type]
    predictor.fit(train_df)
    predictions = predictor.predict(upcoming_df)
    
    # Verify predictions are generated even without moneyline columns
    assert len(predictions) == 1, "Expected 1 prediction"
    assert 'predicted_winner' in predictions.columns, "predicted_winner column missing"
    assert 'confidence' in predictions.columns, "confidence column missing"
    
    # Moneyline columns should NOT be present if they weren't in input
    assert 'home_moneyline' not in predictions.columns, "home_moneyline should not be present"
    assert 'away_moneyline' not in predictions.columns, "away_moneyline should not be present"
    assert 'has_real_odds' not in predictions.columns, "has_real_odds should not be present"
