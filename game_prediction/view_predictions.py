#!/usr/bin/env python3
"""
View Today's NCAA Basketball Game Predictions
Quick script to display today's predictions in a readable format.
"""

import pandas as pd
from datetime import datetime

def main():
    """Display today's predictions."""
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    print("="*80)
    print(f"NCAA BASKETBALL PREDICTIONS - {today}")
    print("="*80)
    
    # Load predictions
    try:
        predictions = pd.read_csv('data/NCAA_Game_Predictions.csv')
    except FileNotFoundError:
        print("\n✗ No predictions found. Run `python3 daily_pipeline.py` first.")
        return
    
    # Filter for today
    today_games = predictions[predictions['date'] == today].copy()
    
    if len(today_games) == 0:
        print(f"\n✗ No predictions for {today}")
        print("   Run `python3 daily_pipeline.py` to generate predictions")
        return
    
    print(f"\nTotal games: {len(today_games)}")
    
    # Sort by confidence
    today_games = today_games.sort_values('confidence', ascending=False)
    
    # Group by confidence level
    high = today_games[today_games['confidence'] >= 0.7]
    medium = today_games[(today_games['confidence'] >= 0.6) & (today_games['confidence'] < 0.7)]
    low = today_games[today_games['confidence'] < 0.6]
    
    if len(high) > 0:
        print(f"\n{'='*80}")
        print(f"HIGH CONFIDENCE PICKS (≥70%) - {len(high)} games")
        print(f"{'='*80}")
        for i, (_, game) in enumerate(high.iterrows(), 1):
            winner = game['predicted_winner']
            loser = game['home_team'] if winner == game['away_team'] else game['away_team']
            conf = game['confidence']
            print(f"{i:2}. {winner:40} over {loser:30} ({conf:.1%})")
    
    if len(medium) > 0:
        print(f"\n{'='*80}")
        print(f"MEDIUM CONFIDENCE PICKS (60-70%) - {len(medium)} games")
        print(f"{'='*80}")
        for i, (_, game) in enumerate(medium.iterrows(), 1):
            winner = game['predicted_winner']
            loser = game['home_team'] if winner == game['away_team'] else game['away_team']
            conf = game['confidence']
            print(f"{i:2}. {winner:40} over {loser:30} ({conf:.1%})")
    
    if len(low) > 0:
        print(f"\n{'='*80}")
        print(f"LOWER CONFIDENCE PICKS (<60%) - {len(low)} games")
        print(f"{'='*80}")
        for i, (_, game) in enumerate(low.iterrows(), 1):
            winner = game['predicted_winner']
            loser = game['home_team'] if winner == game['away_team'] else game['away_team']
            conf = game['confidence']
            print(f"{i:2}. {winner:40} over {loser:30} ({conf:.1%})")
    
    # Summary stats
    home_favored = len(today_games[today_games['predicted_home_win'] == 1])
    away_favored = len(today_games[today_games['predicted_home_win'] == 0])
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Home teams favored: {home_favored}")
    print(f"Away teams favored: {away_favored}")
    print(f"Average confidence: {today_games['confidence'].mean():.1%}")
    print(f"\nFull predictions saved in: data/NCAA_Game_Predictions.csv")
    print("="*80)

if __name__ == "__main__":
    main()
