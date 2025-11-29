#!/usr/bin/env python3
"""
NCAA Predictions Accuracy Tracker
Compares predictions against actual game results and calculates accuracy metrics.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

# Lineage imports (defensive)
try:  # pragma: no cover
    from config.load_config import get_config_version
    from config.versioning import get_commit_hash
    _config_version = get_config_version()
    _commit_hash = get_commit_hash()
except Exception:  # noqa: BLE001
    _config_version = 'unknown'
    _commit_hash = 'unknown'

def track_accuracy():
    """Compare predictions to actual results and calculate accuracy."""
    
    print("="*80)
    print("NCAA PREDICTIONS ACCURACY TRACKER")
    print("="*80)
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Load predictions from prediction_log.csv (contains all historical predictions)
    # Fall back to NCAA_Game_Predictions.csv if prediction_log.csv doesn't exist
    prediction_log_path = os.path.join(data_dir, 'prediction_log.csv')
    predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
    
    if os.path.exists(prediction_log_path):
        predictions = pd.read_csv(prediction_log_path)
        print(f"\n✓ Loaded {len(predictions)} predictions from prediction_log.csv")
    elif os.path.exists(predictions_path):
        predictions = pd.read_csv(predictions_path)
        print(f"\n✓ Loaded {len(predictions)} predictions from NCAA_Game_Predictions.csv")
    else:
        print("\n✗ No predictions file found")
        return
    
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
        completed[['game_id', 'home_score', 'away_score', 'game_status', 'date']],
        on='game_id',
        how='inner',
        suffixes=('_pred', '_actual')
    )
    
    # Filter to only games that are actually completed (game_status == 'Final')
    merged = merged[merged['game_status'] == 'Final'].copy()
    
    # Filter out games with invalid scores (0-0 or missing scores)
    # These are games that ESPN marks as "Final" prematurely
    merged = merged[
        (merged['home_score'].notna()) & 
        (merged['away_score'].notna()) &
        ((merged['home_score'] > 0) | (merged['away_score'] > 0))
    ].copy()
    
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
    
    # Save accuracy report (daily summary)
    # Group by game date to create separate entries for each day
    report_path = os.path.join(data_dir, 'Accuracy_Report.csv')
    
    # Use the actual game date from completed games, not today's date
    date_col = 'date_actual' if 'date_actual' in merged.columns else 'date'
    
    # Group by date and calculate metrics for each day
    daily_reports = []
    for game_date, day_games in merged.groupby(date_col):
        daily_accuracy = day_games['correct'].mean()
        daily_report = {
            'date': game_date,
            'total_predictions': len(day_games),
            'games_completed': len(day_games),
            'correct_predictions': int(day_games['correct'].sum()),
            'accuracy': daily_accuracy,
            'avg_confidence': day_games['confidence'].mean(),
            'config_version': _config_version,
            'commit_hash': _commit_hash
        }
        daily_reports.append(daily_report)
    
    report_df = pd.DataFrame(daily_reports)
    
    # Append to existing report if it exists, avoiding duplicates
    if os.path.exists(report_path):
        existing = pd.read_csv(report_path)
        # Remove any existing entries for the same dates to avoid duplicates
        existing = existing[~existing['date'].isin(report_df['date'])]
        report_df = pd.concat([existing, report_df], ignore_index=True)
        # Sort by date
        report_df = report_df.sort_values('date').reset_index(drop=True)
    
    report_df.to_csv(report_path, index=False)
    print(f"\n✓ Saved accuracy report to {report_path} ({len(daily_reports)} date(s) updated)")
    
    # Save detailed results for streak tracking
    detailed_path = os.path.join(data_dir, 'Prediction_Details.csv')
    
    # Use the actual game date
    date_col = 'date_actual' if 'date_actual' in merged.columns else 'date'
    
    # Select columns, using the correct date column
    cols_to_save = [
        date_col, 'game_id', 'home_team', 'away_team', 
        'predicted_winner', 'actual_winner', 'confidence', 
        'correct', 'home_score', 'away_score'
    ]
    detailed_df = merged[cols_to_save].copy()
    
    # Rename date column to 'date' if it was suffixed
    if date_col != 'date':
        detailed_df.rename(columns={date_col: 'date'}, inplace=True)
    
    detailed_df['config_version'] = _config_version
    detailed_df['commit_hash'] = _commit_hash
    
    # Deduplicate merged data before saving (keep first occurrence by game_id and date)
    detailed_df = detailed_df.drop_duplicates(subset=['date', 'game_id'], keep='first')
    
    # Append to existing details if exists, otherwise create new
    if os.path.exists(detailed_path):
        existing_details = pd.read_csv(detailed_path)
        # Remove duplicates (in case we run this multiple times)
        existing_details = existing_details[~existing_details['game_id'].isin(detailed_df['game_id'])]
        detailed_df = pd.concat([existing_details, detailed_df], ignore_index=True)
    
    # Final deduplication to ensure data integrity
    detailed_df = detailed_df.drop_duplicates(subset=['date', 'game_id'], keep='first')
    
    detailed_df.to_csv(detailed_path, index=False)
    print(f"✓ Saved detailed predictions to {detailed_path}")
    
    print("\n" + "="*80)
    print("TRACKING COMPLETE")
    print("="*80)

if __name__ == "__main__":
    track_accuracy()
