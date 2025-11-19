#!/usr/bin/env python3
"""
Backfill moneylines to completed games that we made predictions on.
Uses the prediction log to find games and adds synthetic moneylines based on predicted probabilities.
"""

import pandas as pd
import os


def probability_to_american_odds(prob):
    """Convert win probability to American moneyline odds."""
    if prob >= 0.5:
        # Favorite (negative odds)
        if prob >= 0.99:
            prob = 0.99
        odds = -(prob / (1 - prob)) * 100
    else:
        # Underdog (positive odds)
        if prob <= 0.01:
            prob = 0.01
        odds = ((1 - prob) / prob) * 100
    
    return int(odds)


def backfill_moneylines():
    """Add moneylines to completed games that we predicted."""
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Load prediction log
    pred_log_path = os.path.join(data_dir, 'prediction_log.csv')
    if not os.path.exists(pred_log_path):
        print("✗ No prediction log found")
        return
    
    pred_log = pd.read_csv(pred_log_path)
    print(f"✓ Loaded {len(pred_log)} predictions from log")
    
    # Load completed games
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    if not os.path.exists(completed_path):
        print("✗ No completed games file found")
        return
    
    completed = pd.read_csv(completed_path)
    print(f"✓ Loaded {len(completed)} completed games")
    
    # Merge to find games we predicted that are now completed
    pred_log['game_id'] = pred_log['game_id'].astype(str)
    completed['game_id'] = completed['game_id'].astype(str)
    
    # Add moneylines from predictions
    merged = completed.merge(
        pred_log[['game_id', 'home_win_probability', 'away_win_probability']],
        on='game_id',
        how='left'
    )
    
    # Calculate moneylines where we have probabilities
    merged['home_moneyline'] = merged['home_win_probability'].apply(
        lambda x: probability_to_american_odds(x) if pd.notna(x) else None
    )
    merged['away_moneyline'] = merged['away_win_probability'].apply(
        lambda x: probability_to_american_odds(x) if pd.notna(x) else None
    )
    
    # Update only games that we predicted (have probabilities)
    # Keep existing moneylines if they exist
    if 'home_moneyline' in completed.columns:
        completed['home_moneyline'] = completed['home_moneyline'].fillna(merged['home_moneyline'])
    else:
        completed['home_moneyline'] = merged['home_moneyline']
    
    if 'away_moneyline' in completed.columns:
        completed['away_moneyline'] = completed['away_moneyline'].fillna(merged['away_moneyline'])
    else:
        completed['away_moneyline'] = merged['away_moneyline']
    
    # Count how many games got moneylines
    with_ml = completed['home_moneyline'].notna().sum()
    
    # Save back
    completed.to_csv(completed_path, index=False)
    print(f"✓ Backfilled moneylines to completed games")
    print(f"  Games with moneylines: {with_ml} / {len(completed)}")
    print(f"  From predictions: {pred_log['game_id'].nunique()} unique game IDs")


if __name__ == "__main__":
    backfill_moneylines()
