#!/usr/bin/env python3
"""
Test Feature Removal Impact

Compares model performance WITH and WITHOUT useless features removed.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.calibration_metrics import expected_calibration_error
import pandas as pd

def test_feature_removal():
    print("="*80)
    print("TESTING FEATURE REMOVAL IMPACT")
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
    
    # ================================================================
    # Model WITH Useless Features (30 features)
    # ================================================================
    print("\n" + "="*80)
    print("MODEL WITH ALL FEATURES (30 features)")
    print("="*80)
    print()
    
    model_with = AdaptivePredictor(
        model_type='xgboost',
        xgb_reg_alpha=0.5,
        xgb_reg_lambda=2.0,
        remove_useless_features=False,  # Keep all features
    )
    
    model_with.fit(train_data, use_validation=True, val_days=14)
    
    # Count features used
    if hasattr(model_with._raw_model, 'feature_names_in_'):
        features_with = list(model_with._raw_model.feature_names_in_)
        print(f"Features used: {len(features_with)}")
        print()
    
    # Predict and evaluate
    preds_with = model_with.predict(test_data)
    results_with = test_data.merge(preds_with[['game_id', 'predicted_winner', 'confidence']], on='game_id')
    results_with['actual_winner'] = results_with.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    results_with['correct'] = (results_with['predicted_winner'] == results_with['actual_winner']).astype(int)
    
    acc_with = results_with['correct'].mean()
    ece_with = expected_calibration_error(results_with['correct'].values, results_with['confidence'].values)
    
    print(f"Accuracy: {acc_with:.1%}")
    print(f"ECE: {ece_with:.4f}")
    
    # High confidence
    high_with = results_with[results_with['confidence'] >= 0.80]
    if len(high_with) > 0:
        high_acc_with = high_with['correct'].mean()
        print(f"80%+ confidence: {len(high_with)} games, {high_acc_with:.1%} accurate")
    
    # ================================================================
    # Model WITHOUT Useless Features (18 features)
    # ================================================================
    print("\n" + "="*80)
    print("MODEL WITHOUT USELESS FEATURES (18 features)")
    print("="*80)
    print()
    
    model_without = AdaptivePredictor(
        model_type='xgboost',
        xgb_reg_alpha=0.5,
        xgb_reg_lambda=2.0,
        remove_useless_features=True,  # Remove useless features
    )
    
    model_without.fit(train_data, use_validation=True, val_days=14)
    
    # Count features used
    if hasattr(model_without._raw_model, 'feature_names_in_'):
        features_without = list(model_without._raw_model.feature_names_in_)
        print(f"Features used: {len(features_without)}")
        print(f"Removed: {len(features_with) - len(features_without)} features")
        print()
        
        removed = set(features_with) - set(features_without)
        if removed:
            print(f"Removed features: {', '.join(sorted(removed))}")
            print()
    
    # Predict and evaluate
    preds_without = model_without.predict(test_data)
    results_without = test_data.merge(preds_without[['game_id', 'predicted_winner', 'confidence']], on='game_id')
    results_without['actual_winner'] = results_without.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    results_without['correct'] = (results_without['predicted_winner'] == results_without['actual_winner']).astype(int)
    
    acc_without = results_without['correct'].mean()
    ece_without = expected_calibration_error(results_without['correct'].values, results_without['confidence'].values)
    
    print(f"Accuracy: {acc_without:.1%}")
    print(f"ECE: {ece_without:.4f}")
    
    # High confidence
    high_without = results_without[results_without['confidence'] >= 0.80]
    if len(high_without) > 0:
        high_acc_without = high_without['correct'].mean()
        print(f"80%+ confidence: {len(high_without)} games, {high_acc_without:.1%} accurate")
    
    # ================================================================
    # COMPARISON
    # ================================================================
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)
    print()
    
    print(f"{'Metric':<25} {'With (30)':<15} {'Without (18)':<15} {'Change':<12}")
    print("-" * 70)
    print(f"{'Accuracy':<25} {acc_with:>14.1%} {acc_without:>14.1%} {(acc_without-acc_with):>11.1%}")
    print(f"{'ECE':<25} {ece_with:>14.4f} {ece_without:>14.4f} {(ece_without-ece_with):>11.4f}")
    
    if len(high_with) > 0 and len(high_without) > 0:
        print(f"{'High Conf Accuracy':<25} {high_acc_with:>14.1%} {high_acc_without:>14.1%} {(high_acc_without-high_acc_with):>11.1%}")
    
    print()
    
    # Verdict
    if acc_without > acc_with and ece_without < ece_with:
        print("✅ IMPROVEMENT: Feature removal helps both accuracy and calibration!")
    elif acc_without > acc_with:
        print("✅ IMPROVEMENT: Feature removal improves accuracy")
    elif ece_without < ece_with:
        print("✅ IMPROVEMENT: Feature removal improves calibration")
    else:
        print("⚠️  NEUTRAL: No significant improvement from feature removal")
    
    print()
    print("="*80)
    
    db.close()

if __name__ == '__main__':
    test_feature_removal()
