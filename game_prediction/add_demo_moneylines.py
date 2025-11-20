#!/usr/bin/env python3
"""
Add demonstration moneylines to predictions based on win probability.
This simulates what would come from ESPN API in a real scenario.
"""

import pandas as pd
import os


def probability_to_american_odds(prob):
    """
    Convert win probability to American moneyline odds.
    
    Args:
        prob: Win probability (0 to 1)
    
    Returns:
        American odds (e.g., -150, +120)
    """
    if prob >= 0.5:
        # Favorite (negative odds)
        if prob >= 0.99:
            prob = 0.99  # Cap to avoid division by zero
        odds = -(prob / (1 - prob)) * 100
    else:
        # Underdog (positive odds)
        if prob <= 0.01:
            prob = 0.01  # Cap to avoid extreme odds
        odds = ((1 - prob) / prob) * 100
    
    return int(odds)


def add_moneylines_to_predictions():
    """Add synthetic moneylines to predictions for demo purposes."""
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
    
    if not os.path.exists(predictions_path):
        print("✗ No predictions file found")
        return
    
    predictions = pd.read_csv(predictions_path)
    print(f"✓ Loaded {len(predictions)} predictions")
    
    # Add moneylines based on win probabilities
    predictions['home_moneyline'] = predictions['home_win_probability'].apply(probability_to_american_odds)
    predictions['away_moneyline'] = predictions['away_win_probability'].apply(probability_to_american_odds)
    
    # Save back
    predictions.to_csv(predictions_path, index=False)
    print(f"✓ Added moneylines to predictions")
    print(f"  Sample home moneylines: {predictions['home_moneyline'].head().tolist()}")
    print(f"  Sample away moneylines: {predictions['away_moneyline'].head().tolist()}")
    
    # Also add to upcoming games if it exists
    upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
    if os.path.exists(upcoming_path):
        upcoming = pd.read_csv(upcoming_path)
        
        # Merge with predictions to get probabilities
        merged = upcoming.merge(
            predictions[['game_id', 'home_win_probability', 'away_win_probability']],
            on='game_id',
            how='left'
        )
        
        # Add moneylines where we have probabilities
        merged['home_moneyline'] = merged['home_win_probability'].apply(
            lambda x: probability_to_american_odds(x) if pd.notna(x) else None
        )
        merged['away_moneyline'] = merged['away_win_probability'].apply(
            lambda x: probability_to_american_odds(x) if pd.notna(x) else None
        )
        
        # Keep original columns plus moneylines
        for col in ['home_moneyline', 'away_moneyline']:
            upcoming[col] = merged[col]
        
        upcoming.to_csv(upcoming_path, index=False)
        print(f"✓ Added moneylines to upcoming games")


if __name__ == "__main__":
    add_moneylines_to_predictions()
