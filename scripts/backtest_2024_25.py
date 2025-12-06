#!/usr/bin/env python3
"""
Backtest on 2024-25 Season

Tests the optimized model on full 2024-25 season for robust performance estimates.
Much larger dataset (~1500+ games) vs current 2025-26 test (261 games).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.calibration_metrics import expected_calibration_error, brier_score, log_loss
import pandas as pd
import numpy as np

def analyze_by_confidence_bucket(results):
    """Analyze results by confidence bucket."""
    buckets = [
        (0.5, 0.6, "50-60%"),
        (0.6, 0.7, "60-70%"),
        (0.7, 0.8, "70-80%"),
        (0.8, 0.9, "80-90%"),
        (0.9, 1.0, "90-100%"),
    ]
    
    print("\nCalibration by Confidence Bucket:")
    print(f"{'Bucket':<12} {'Count':<8} {'Accuracy':<12} {'Avg Conf':<12} {'Gap':<12}")
    print("-" * 60)
    
    for low, high, label in buckets:
        bucket = results[(results['confidence'] >= low) & (results['confidence'] < high)]
        if len(bucket) > 0:
            acc = bucket['correct'].mean()
            conf = bucket['confidence'].mean()
            gap = conf - acc
            print(f"{label:<12} {len(bucket):<8} {acc:<11.1%} {conf:<11.1%} {gap:>+11.1%}")


def main():
    print("="*80)
    print("BACKTEST ON 2024-25 SEASON")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    completed_games = games_repo.get_completed_games_df()
    
    # Get 2024-25 season
    season_2024 = completed_games[completed_games['season'] == '2024-25'].copy()
    
    if len(season_2024) == 0:
        print("❌ No 2024-25 season data found!")
        print("\nAvailable seasons:")
        print(completed_games['season'].value_counts())
        db.close()
        return
    
    print(f"2024-25 Season: {len(season_2024)} games")
    print()
    
    # Split: Train on first 70%, test on last 30%
    split_idx = int(len(season_2024) * 0.70)
    train_data = season_2024.iloc[:split_idx].copy()
    test_data = season_2024.iloc[split_idx:].copy()
    
    print(f"Training: {len(train_data)} games")
    print(f"Testing: {len(test_data)} games")
    print()
    
    # ================================================================
    # Train Optimized Model
    # ================================================================
    print("="*80)
    print("TRAINING OPTIMIZED MODEL")
    print("="*80)
    print()
    
    model = AdaptivePredictor(
        model_type='xgboost',
        xgb_learning_rate=0.05,
        xgb_max_depth=6,
        xgb_reg_alpha=0.1,
        xgb_reg_lambda=1.0,
        remove_useless_features=True,
    )
    
    model.fit(train_data, use_validation=True, val_days=14)
    
    # ================================================================
    # Predict and Evaluate
    # ================================================================
    print("\n" + "="*80)
    print("EVALUATION ON TEST SET")
    print("="*80)
    print()
    
    predictions = model.predict(test_data)
    results = test_data.merge(predictions[['game_id', 'predicted_winner', 'confidence']], on='game_id')
    results['actual_winner'] = results.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    results['correct'] = (results['predicted_winner'] == results['actual_winner']).astype(int)
    
    # Overall metrics
    accuracy = results['correct'].mean()
    avg_confidence = results['confidence'].mean()
    ece = expected_calibration_error(results['correct'].values, results['confidence'].values)
    brier = brier_score(results['correct'].values, results['confidence'].values)
    logloss = log_loss(results['correct'].values, results['confidence'].values)
    
    print(f"Test Set: {len(results)} games")
    print(f"Overall Accuracy: {accuracy:.1%}")
    print(f"Average Confidence: {avg_confidence:.1%}")
    print(f"Overconfidence Gap: {avg_confidence - accuracy:+.1%}")
    print()
    print(f"Expected Calibration Error: {ece:.4f}")
    print(f"Brier Score: {brier:.4f}")
    print(f"Log Loss: {logloss:.4f}")
    
    # By confidence bucket
    analyze_by_confidence_bucket(results)
    
    # High confidence analysis
    print("\n" + "="*80)
    print("HIGH CONFIDENCE ANALYSIS")
    print("="*80)
    print()
    
    thresholds = [0.70, 0.75, 0.80, 0.85, 0.90]
    print(f"{'Threshold':<12} {'Count':<10} {'Accuracy':<12} {'Avg Conf':<12} {'Gap':<12} {'ROI':<12}")
    print("-" * 80)
    
    for threshold in thresholds:
        high = results[results['confidence'] >= threshold]
        if len(high) > 0:
            acc = high['correct'].mean()
            conf = high['confidence'].mean()
            gap = conf - acc
            
            # ROI calculation (assuming -110 odds, need >52.4% to profit)
            wins = high['correct'].sum()
            losses = len(high) - wins
            profit = (wins * 0.909) - losses  # Win $90.90 per $100 bet, lose $100
            roi = (profit / len(high)) if len(high) > 0 else 0
            
            print(f"{threshold:<11.0%} {len(high):<10} {acc:<11.1%} {conf:<11.1%} {gap:>+11.1%} {roi:>+11.1%}")
    
    # ================================================================
    # Betting Simulation
    # ================================================================
    print("\n" + "="*80)
    print("BETTING SIMULATION ($100 per pick)")
    print("="*80)
    print()
    
    for threshold in [0.70, 0.75, 0.80]:
        high = results[results['confidence'] >= threshold]
        if len(high) > 0:
            wins = high['correct'].sum()
            losses = len(high) - wins
            profit = (wins * 90.91) - (losses * 100)  # -110 odds
            roi = (profit / (len(high) * 100)) * 100
            
            print(f"{threshold:.0%}+ Confidence:")
            print(f"  Picks: {len(high)}")
            print(f"  Record: {wins}-{losses} ({high['correct'].mean():.1%})")
            print(f"  Profit: ${profit:,.2f}")
            print(f"  ROI: {roi:+.1f}%")
            print()
    
    # ================================================================
    # Save Results
    # ================================================================
    results_summary = {
        'season': '2024-25',
        'test_games': len(results),
        'accuracy': float(accuracy),
        'average_confidence': float(avg_confidence),
        'ece': float(ece),
        'brier_score': float(brier),
        'log_loss': float(logloss),
        'high_confidence_80plus': {
            'count': int((results['confidence'] >= 0.80).sum()),
            'accuracy': float(results[results['confidence'] >= 0.80]['correct'].mean())
        }
    }
    
    import json
    output_path = 'data/backtest_2024_25_results.json'
    with open(output_path, 'w') as f:
        json.dump(results_summary, f, indent=2)
    
    print(f"✓ Results saved to {output_path}")
    print()
    
    db.close()

if __name__ == '__main__':
    main()
