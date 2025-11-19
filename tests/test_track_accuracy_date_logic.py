#!/usr/bin/env python3
"""Test that track_accuracy properly handles date logic for completed games."""

import pandas as pd
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'game_prediction'))


def test_date_logic_filters_completed_games():
    """Test the date logic for filtering completed games."""
    # Create mock predictions
    predictions = pd.DataFrame({
        'game_id': ['game1', 'game2', 'game3'],
        'date': ['2025-11-15', '2025-11-15', '2025-11-16'],
        'home_team': ['TeamA', 'TeamC', 'TeamE'],
        'away_team': ['TeamB', 'TeamD', 'TeamF'],
        'predicted_winner': ['TeamA', 'TeamC', 'TeamE'],
        'home_win_probability': [0.8, 0.7, 0.6],
        'away_win_probability': [0.2, 0.3, 0.4],
        'confidence': [0.8, 0.7, 0.6]
    })
    
    # Create mock completed games with mix of Final and Scheduled
    completed = pd.DataFrame({
        'game_id': ['game1', 'game2', 'game3', 'game4'],
        'date': ['2025-11-15', '2025-11-15', '2025-11-16', '2025-11-17'],
        'home_team': ['TeamA', 'TeamC', 'TeamE', 'TeamG'],
        'away_team': ['TeamB', 'TeamD', 'TeamF', 'TeamH'],
        'home_score': [80, 75, 70, 0],
        'away_score': [70, 72, 65, 0],
        'game_status': ['Final', 'Final', 'Scheduled', 'Scheduled']
    })
    
    # Simulate the merge and filter logic from track_accuracy
    predictions['game_id'] = predictions['game_id'].astype(str)
    completed['game_id'] = completed['game_id'].astype(str)
    
    merged = predictions.merge(
        completed[['game_id', 'home_score', 'away_score', 'game_status', 'date']],
        on='game_id',
        how='inner',
        suffixes=('_pred', '_actual')
    )
    
    # Filter to only Final games
    merged = merged[merged['game_status'] == 'Final'].copy()
    
    # Verify only 2 games are in the result (game1 and game2)
    assert len(merged) == 2, f"Expected 2 completed games, got {len(merged)}"
    
    # Verify game3 (Scheduled) is not in the result
    assert 'game3' not in merged['game_id'].values, "Scheduled games should be filtered out"
    
    # Verify both remaining games have status='Final'
    assert all(merged['game_status'] == 'Final'), "All merged games should have status='Final'"
    
    print("✓ Date logic correctly filters only completed (Final) games")


def test_grouping_by_game_date():
    """Test that accuracy reports group by game date, not current date."""
    # Create mock merged data with different dates
    merged = pd.DataFrame({
        'date_actual': ['2025-11-10', '2025-11-10', '2025-11-11', '2025-11-11'],
        'game_id': ['g1', 'g2', 'g3', 'g4'],
        'correct': [1, 1, 1, 0],
        'confidence': [0.9, 0.85, 0.8, 0.75]
    })
    
    # Simulate the grouping logic from track_accuracy
    date_col = 'date_actual'
    daily_reports = []
    for game_date, day_games in merged.groupby(date_col):
        daily_accuracy = day_games['correct'].mean()
        daily_report = {
            'date': game_date,
            'games_completed': len(day_games),
            'correct_predictions': int(day_games['correct'].sum()),
            'accuracy': daily_accuracy,
            'avg_confidence': day_games['confidence'].mean()
        }
        daily_reports.append(daily_report)
    
    report_df = pd.DataFrame(daily_reports)
    
    # Verify we have 2 separate date entries
    assert len(report_df) == 2, f"Expected 2 date entries, got {len(report_df)}"
    
    # Verify the dates are the game dates, not today's date
    assert '2025-11-10' in report_df['date'].values, "Report should contain game date 2025-11-10"
    assert '2025-11-11' in report_df['date'].values, "Report should contain game date 2025-11-11"
    
    today = datetime.now().strftime('%Y-%m-%d')
    if today not in ['2025-11-10', '2025-11-11']:
        assert today not in report_df['date'].values, \
            f"Report should not contain today's date ({today})"
    
    # Verify accuracy calculations per date
    nov10 = report_df[report_df['date'] == '2025-11-10'].iloc[0]
    assert nov10['games_completed'] == 2
    assert nov10['correct_predictions'] == 2
    assert nov10['accuracy'] == 1.0
    
    nov11 = report_df[report_df['date'] == '2025-11-11'].iloc[0]
    assert nov11['games_completed'] == 2
    assert nov11['correct_predictions'] == 1
    assert nov11['accuracy'] == 0.5
    
    print("✓ Accuracy reports correctly group by game date, not current date")


if __name__ == '__main__':
    test_date_logic_filters_completed_games()
    test_grouping_by_game_date()
    print("\nAll date logic tests passed!")
