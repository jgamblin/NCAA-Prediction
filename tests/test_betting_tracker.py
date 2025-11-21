"""
Tests for betting_tracker.py
"""
import pytest
from game_prediction.betting_tracker import (
    american_odds_to_payout,
    calculate_bet_result,
    is_bettable_moneyline,
    calculate_value_score,
    get_todays_bets
)
import pandas as pd


def test_american_odds_positive():
    """Test conversion of positive (underdog) American odds."""
    # +150 odds: $1 bet should return $2.50 ($1 stake + $1.50 profit)
    result = american_odds_to_payout(150, 1.0)
    assert result == pytest.approx(2.50, abs=0.01)
    
    # +200 odds: $1 bet should return $3.00 ($1 stake + $2.00 profit)
    result = american_odds_to_payout(200, 1.0)
    assert result == pytest.approx(3.00, abs=0.01)


def test_american_odds_negative():
    """Test conversion of negative (favorite) American odds."""
    # -150 odds: $1 bet should return $1.67 ($1 stake + $0.67 profit)
    result = american_odds_to_payout(-150, 1.0)
    assert result == pytest.approx(1.67, abs=0.01)
    
    # -110 odds: $1 bet should return $1.91 ($1 stake + $0.91 profit)
    result = american_odds_to_payout(-110, 1.0)
    assert result == pytest.approx(1.91, abs=0.01)


def test_american_odds_invalid():
    """Test handling of invalid odds."""
    assert american_odds_to_payout(None, 1.0) is None
    assert american_odds_to_payout('invalid', 1.0) is None


def test_calculate_bet_result_winning_bet():
    """Test calculation of a winning bet."""
    row = pd.Series({
        'game_id': '12345',
        'date': '2025-11-15',
        'away_team': 'Team A',
        'home_team': 'Team B',
        'predicted_winner': 'Team B',
        'predicted_home_win': 1,
        'confidence': 0.85,
        'home_score': 75,
        'away_score': 70,
        'home_moneyline': -150,
        'away_moneyline': 150
    })
    
    result = calculate_bet_result(row, 1.0)
    
    assert result['has_moneyline'] is True
    assert result['bet_won'] is True
    assert result['actual_winner'] == 'Team B'
    assert result['payout'] == pytest.approx(1.67, abs=0.01)
    assert result['profit'] == pytest.approx(0.67, abs=0.01)


def test_calculate_bet_result_losing_bet():
    """Test calculation of a losing bet."""
    row = pd.Series({
        'game_id': '12345',
        'date': '2025-11-15',
        'away_team': 'Team A',
        'home_team': 'Team B',
        'predicted_winner': 'Team B',
        'predicted_home_win': 1,
        'confidence': 0.85,
        'home_score': 70,  # Lost
        'away_score': 75,
        'home_moneyline': -150,
        'away_moneyline': 150
    })
    
    result = calculate_bet_result(row, 1.0)
    
    assert result['has_moneyline'] is True
    assert result['bet_won'] is False
    assert result['actual_winner'] == 'Team A'
    assert result['payout'] == 0.0
    assert result['profit'] == -1.0


def test_calculate_bet_result_no_moneyline():
    """Test handling of games without moneylines."""
    row = pd.Series({
        'game_id': '12345',
        'date': '2025-11-15',
        'away_team': 'Team A',
        'home_team': 'Team B',
        'predicted_winner': 'Team B',
        'predicted_home_win': 1,
        'confidence': 0.85,
        'home_score': 75,
        'away_score': 70,
        'home_moneyline': None,
        'away_moneyline': None
    })
    
    result = calculate_bet_result(row, 1.0)
    
    assert result['has_moneyline'] is False
    assert result['bet_won'] is None
    assert result['payout'] == 0.0
    assert result['profit'] == -1.0


def test_calculate_bet_result_incomplete_game():
    """Test handling of games that haven't been completed yet."""
    row = pd.Series({
        'game_id': '12345',
        'date': '2025-11-15',
        'away_team': 'Team A',
        'home_team': 'Team B',
        'predicted_winner': 'Team B',
        'predicted_home_win': 1,
        'confidence': 0.85,
        'home_score': None,
        'away_score': None,
        'home_moneyline': -150,
        'away_moneyline': 150
    })
    
    result = calculate_bet_result(row, 1.0)
    
    assert result['has_moneyline'] is True
    assert result['actual_winner'] is None
    assert result['bet_won'] is None


def test_is_bettable_moneyline():
    """Test the is_bettable_moneyline function."""
    # Normal bettable moneylines
    assert is_bettable_moneyline(-110) is True
    assert is_bettable_moneyline(-500) is True
    assert is_bettable_moneyline(-1000) is True
    assert is_bettable_moneyline(150) is True
    assert is_bettable_moneyline(200) is True
    
    # Unbettable extreme moneylines
    assert is_bettable_moneyline(-1001) is False
    assert is_bettable_moneyline(-3000) is False
    assert is_bettable_moneyline(-100000) is False
    
    # Invalid inputs
    assert is_bettable_moneyline(None) is False
    assert is_bettable_moneyline('invalid') is False


def test_calculate_value_score():
    """Test the calculate_value_score function."""
    # High confidence with decent odds should have positive value
    value = calculate_value_score(0.80, -110)
    assert value > 0  # Should be profitable in expectation
    
    # Low confidence with underdog odds should have negative value
    value = calculate_value_score(0.30, 200)
    assert value < 0  # Should lose money in expectation
    
    # Edge case: 50% confidence at even odds
    value = calculate_value_score(0.50, 100)
    assert value == pytest.approx(0.0, abs=0.01)
    
    # Unbettable moneyline should return None
    assert calculate_value_score(0.85, -3000) is None
    
    # Invalid inputs should return None
    assert calculate_value_score(None, -110) is None
    assert calculate_value_score(0.85, None) is None


def test_calculate_bet_result_extreme_moneyline():
    """Test that extreme moneylines are treated as unbettable."""
    row = pd.Series({
        'game_id': '12345',
        'date': '2025-11-15',
        'away_team': 'Team A',
        'home_team': 'Team B',
        'predicted_winner': 'Team B',
        'predicted_home_win': 1,
        'confidence': 0.85,
        'home_score': 75,
        'away_score': 70,
        'home_moneyline': -100000,  # Extreme moneyline
        'away_moneyline': 150
    })
    
    result = calculate_bet_result(row, 1.0)
    
    # Should be treated as having no moneyline
    assert result['has_moneyline'] is False
    assert result['bet_won'] is None


def test_get_todays_bets():
    """Test the get_todays_bets function."""
    # Create sample predictions data
    today_preds = pd.DataFrame({
        'home_team': ['Team A', 'Team B', 'Team C'],
        'away_team': ['Team D', 'Team E', 'Team F'],
        'predicted_home_win': [1, 0, 1],
        'confidence': [0.90, 0.75, 0.80],
        'home_moneyline': [-500, -110, -200],
        'away_moneyline': [400, -110, 180],
        'has_real_odds': [True, True, True]
    })
    
    result = get_todays_bets(today_preds)
    
    # Safest bet should be Team A (90% confidence)
    assert result['safest_bet'] is not None
    assert result['safest_bet']['home_team'] == 'Team A'
    assert result['safest_bet']['confidence'] == 0.90
    
    # Value bet should exist
    assert result['value_bet'] is not None


def test_get_todays_bets_with_extreme_moneyline():
    """Test get_todays_bets with extreme moneylines."""
    today_preds = pd.DataFrame({
        'home_team': ['Team A', 'Team B'],
        'away_team': ['Team C', 'Team D'],
        'predicted_home_win': [1, 1],
        'confidence': [0.90, 0.80],
        'home_moneyline': [-100000, -200],  # First is extreme
        'away_moneyline': [50000, 180],
        'has_real_odds': [True, True]
    })
    
    result = get_todays_bets(today_preds)
    
    # Safest bet should skip the extreme moneyline and use Team B
    assert result['safest_bet'] is not None
    assert result['safest_bet']['home_team'] == 'Team B'
    assert result['safest_bet']['confidence'] == 0.80


def test_get_todays_bets_no_real_odds():
    """Test get_todays_bets when no real odds are available."""
    today_preds = pd.DataFrame({
        'home_team': ['Team A'],
        'away_team': ['Team B'],
        'predicted_home_win': [1],
        'confidence': [0.90],
        'home_moneyline': [-500],
        'away_moneyline': [400],
        'has_real_odds': [False]
    })
    
    result = get_todays_bets(today_preds)
    
    # Should return None for both bets
    assert result['safest_bet'] is None
    assert result['value_bet'] is None
