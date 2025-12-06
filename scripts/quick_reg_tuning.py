#!/usr/bin/env python3
"""
Quick Regularization Tuning

Tests different L1/L2 combinations to find better balance.
Current: L1=0.5, L2=2.0 (might be too aggressive)
Try: Softer values to improve overall accuracy while keeping high-conf performance.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.calibration_metrics import expected_calibration_error
import pandas as pd

def test_regularization_combo(train_data, test_data, l1, l2, name):
    """Test a specific regularization combination."""
    print(f"\nTesting {name}: L1={l1}, L2={l2}")
    
    model = AdaptivePredictor(
        model_type='xgboost',
        xgb_reg_alpha=l1,
        xgb_reg_lambda=l2,
        remove_useless_features=True,
    )
    
    model.fit(train_data, use_validation=True, val_days=14)
    
    # Predict
    predictions = model.predict(test_data)
    results = test_data.merge(predictions[['game_id', 'predicted_winner', 'confidence']], on='game_id')
    results['actual_winner'] = results.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    results['correct'] = (results['predicted_winner'] == results['actual_winner']).astype(int)
    
    # Metrics
    acc = results['correct'].mean()
    ece = expected_calibration_error(results['correct'].values, results['confidence'].values)
    
    # High confidence
    high = results[results['confidence'] >= 0.80]
    high_acc = high['correct'].mean() if len(high) > 0 else 0
    high_count = len(high)
    
    print(f"  Overall: {acc:.1%} accuracy, ECE: {ece:.4f}")
    print(f"  80%+: {high_count} games, {high_acc:.1%} accurate")
    
    return {
        'name': name,
        'l1': l1,
        'l2': l2,
        'accuracy': acc,
        'ece': ece,
        'high_conf_count': high_count,
        'high_conf_acc': high_acc,
        'score': acc + (high_acc * 0.5) - (ece * 0.3)  # Balanced score
    }


def main():
    print("="*80)
    print("QUICK REGULARIZATION TUNING")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    completed_games = games_repo.get_completed_games_df()
    current_season = completed_games[completed_games['season'] == '2025-26'].copy()
    
    # Split
    split_idx = int(len(current_season) * 0.85)
    train_data = current_season.iloc[:split_idx].copy()
    test_data = current_season.iloc[split_idx:].copy()
    
    print(f"Training: {len(train_data)} games")
    print(f"Testing: {len(test_data)} games")
    print()
    
    # Test different regularization combinations
    configs = [
        # Current (too aggressive?)
        (0.5, 2.0, "Current (Aggressive)"),
        
        # Softer options
        (0.3, 1.5, "Soft"),
        (0.1, 1.0, "Minimal"),
        (0.2, 1.0, "Light"),
        (0.3, 1.0, "Medium-Light"),
    ]
    
    results = []
    for l1, l2, name in configs:
        result = test_regularization_combo(train_data, test_data, l1, l2, name)
        results.append(result)
    
    # Summary
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    print()
    
    results_df = pd.DataFrame(results).sort_values('score', ascending=False)
    
    print(f"{'Name':<20} {'L1':<6} {'L2':<6} {'Acc':<8} {'ECE':<10} {'80%+ Acc':<10} {'Score':<8}")
    print("-" * 80)
    for _, row in results_df.iterrows():
        print(f"{row['name']:<20} {row['l1']:<6.1f} {row['l2']:<6.1f} "
              f"{row['accuracy']:<7.1%} {row['ece']:<10.4f} "
              f"{row['high_conf_acc']:<9.1%} {row['score']:<8.3f}")
    
    print()
    best = results_df.iloc[0]
    print(f"✅ BEST: {best['name']} (L1={best['l1']}, L2={best['l2']})")
    print(f"   Accuracy: {best['accuracy']:.1%}")
    print(f"   80%+ Accuracy: {best['high_conf_acc']:.1%}")
    print(f"   ECE: {best['ece']:.4f}")
    print()
    
    db.close()

if __name__ == '__main__':
    main()
