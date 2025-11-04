#!/usr/bin/env python3
"""
NCAA Predictions Accuracy Tracker
Compares predictions against actual game results and calculates accuracy metrics.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

def track_accuracy():
    """Compare predictions to actual results and calculate accuracy."""
    
    print("="*80)
    print("NCAA PREDICTIONS ACCURACY TRACKER")
    print("="*80)
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Load predictions
    predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
    if not os.path.exists(predictions_path):
        print("\n✗ No predictions file found")
        return
    
    predictions = pd.read_csv(predictions_path)
    print(f"\n✓ Loaded {len(predictions)} predictions")
    
    # Load completed games
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    if not os.path.exists(completed_path):
        print("\n✗ No completed games file found")
        return
    
    completed = pd.read_csv(completed_path)
    print(f"✓ Loaded {len(completed)} completed games")
    
    # Find predictions that now have results
    predictions['game_id'] = predictions['game_id'].astype(str)
    completed['game_id'] = completed['game_id'].astype(str)
    
    # Merge predictions with actual results
    merged = predictions.merge(
        completed[['game_id', 'home_score', 'away_score', 'game_status']],
        on='game_id',
        how='inner'
    )
    
    if len(merged) == 0:
        print("\n✗ No completed games found matching predictions yet")
        print("   Games are likely scheduled for later today/tomorrow")
        return
    
    print(f"\n✓ Found {len(merged)} predictions with results")
    
    # Determine actual winner
    merged['actual_home_win'] = (merged['home_score'] > merged['away_score']).astype(int)
    merged['actual_winner'] = merged.apply(
        lambda row: row['home_team'] if row['actual_home_win'] == 1 else row['away_team'],
        axis=1
    )
    
    # Check if prediction was correct
    merged['correct'] = (merged['predicted_winner'] == merged['actual_winner']).astype(int)
    
    # Calculate accuracy
    accuracy = merged['correct'].mean()
    
    # Calculate by confidence level
    merged['confidence'] = merged[['home_win_probability', 'away_win_probability']].max(axis=1)
    
    # Results summary
    print("\n" + "="*80)
    print("ACCURACY RESULTS")
    print("="*80)
    print(f"\nOverall Accuracy: {accuracy:.1%} ({merged['correct'].sum()}/{len(merged)} correct)")
    
    # Accuracy by confidence level
    print("\nAccuracy by Confidence Level:")
    for threshold in [0.5, 0.6, 0.7, 0.8]:
        high_conf = merged[merged['confidence'] >= threshold]
        if len(high_conf) > 0:
            acc = high_conf['correct'].mean()
            print(f"  {threshold:.0%}+ confidence: {acc:.1%} ({high_conf['correct'].sum()}/{len(high_conf)} games)")
    
    # Show incorrect predictions
    incorrect = merged[merged['correct'] == 0]
    if len(incorrect) > 0:
        print(f"\n" + "="*80)
        print(f"INCORRECT PREDICTIONS ({len(incorrect)}):")
        print("="*80)
        for _, game in incorrect.iterrows():
            predicted = game['predicted_winner']
            actual = game['actual_winner']
            conf = game['confidence']
            score = f"{int(game['away_score'])}-{int(game['home_score'])}"
            print(f"  Predicted: {predicted:35} | Actual: {actual:35} | Confidence: {conf:.1%} | Score: {score}")
    
    # Show correct predictions
    correct = merged[merged['correct'] == 1]
    if len(correct) > 0:
        print(f"\n" + "="*80)
        print(f"CORRECT PREDICTIONS ({len(correct)}):")
        print("="*80)
        for _, game in correct.head(10).iterrows():
            winner = game['predicted_winner']
            conf = game['confidence']
            score = f"{int(game['away_score'])}-{int(game['home_score'])}"
            print(f"  {winner:35} | Confidence: {conf:.1%} | Score: {score}")
        if len(correct) > 10:
            print(f"  ... and {len(correct) - 10} more")
    
    # Save accuracy report
    report_path = os.path.join(data_dir, 'Accuracy_Report.csv')
    report_df = pd.DataFrame({
        'date': [datetime.now().strftime('%Y-%m-%d')],
        'total_predictions': [len(predictions)],
        'games_completed': [len(merged)],
        'correct_predictions': [merged['correct'].sum()],
        'accuracy': [accuracy],
        'avg_confidence': [merged['confidence'].mean()]
    })
    
    # Append to existing report if it exists
    if os.path.exists(report_path):
        existing = pd.read_csv(report_path)
        report_df = pd.concat([existing, report_df], ignore_index=True)
    
    report_df.to_csv(report_path, index=False)
    print(f"\n✓ Saved accuracy report to {report_path}")
    
    print("\n" + "="*80)
    print("TRACKING COMPLETE")
    print("="*80)

if __name__ == "__main__":
    track_accuracy()
