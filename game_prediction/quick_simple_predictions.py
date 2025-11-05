#!/usr/bin/env python3
"""Quick predictions using SimplePredictor with 75-game threshold."""
import pandas as pd
import os
import sys

# Add model_training directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'model_training'))
from simple_predictor import SimplePredictor

data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
completed_path = os.path.join(data_dir, 'Completed_Games.csv')
upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')

completed = pd.read_csv(completed_path)
upcoming = pd.read_csv(upcoming_path)

print(f"Completed games: {len(completed):,}")
print(f"Upcoming games:  {len(upcoming)}")

pred = SimplePredictor(min_games_threshold=75)
pred.fit(completed)
results = pred.predict(upcoming, skip_low_data=True, low_data_log_path=os.path.join(data_dir, 'Low_Data_Games_75.csv'))

print("\nSummary:")
print(f"  Predictions generated: {len(results)}")
if len(results):
    print(f"  Avg confidence: {results['confidence'].mean():.1%}")
    print(f"  Home favored: {results['predicted_home_win'].sum()} | Away favored: {len(results) - results['predicted_home_win'].sum()}")

skipped = pd.read_csv(os.path.join(data_dir, 'Low_Data_Games_75.csv'))
print(f"  Skipped (low data <75): {len(skipped)}")
print(f"  Unique low-data teams: {len(set(list(skipped.away_team) + list(skipped.home_team)))}")

print("\nTop 5 predictions:")
print(results[['away_team','home_team','predicted_winner','confidence']].head())
