"""
Tests for betting_tracker.py
"""
import pytest
from game_prediction.betting_tracker import american_odds_to_payout, calculate_bet_result
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
