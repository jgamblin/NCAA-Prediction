#!/usr/bin/env python3
"""
Test Calibration Improvements

Tests the new validation-based calibration system:
1. Train/val split
2. Isotonic regression calibration
3. Temperature tuning on validation
4. ECE improvement measurement

Compares before/after calibration to validate improvements.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.calibration_metrics import (
    expected_calibration_error,
    brier_score,
    log_loss,
    calibration_by_bucket,
    print_calibration_report
)
import pandas as pd
import numpy as np


def test_calibration():
    """Test the new calibration system."""
    
    print("="*80)
    print("CALIBRATION IMPROVEMENT TEST")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    
    print("Loading completed games...")
    completed_games = games_repo.get_completed_games_df()
    
    # Filter to current season
    current_season = completed_games[completed_games['season'] == '2025-26'].copy()
    
    print(f"  Total games: {len(completed_games):,}")
    print(f"  Current season (2025-26): {len(current_season):,}")
    print()
    
    if len(current_season) < 300:
        print("⚠️  Warning: Not enough games for robust testing")
        print("   Proceeding anyway for demonstration...")
        print()
    
    # Split into train/test (use last 50 games as test)
    train_data = current_season.iloc[:-50].copy()
    test_data = current_season.iloc[-50:].copy()
    
    print(f"Training on {len(train_data)} games")
    print(f"Testing on {len(test_data)} games")
    print()
    
    # ================================================================
    # Test 1: Model WITH validation calibration
    # ================================================================
    print("="*80)
    print("TEST 1: Model WITH Validation Calibration")
    print("="*80)
    print()
    
    model_with_val = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True
    )
    
    print("Training model with validation split...")
    model_with_val.fit(train_data, use_validation=True, val_days=14)
    
    # Predict on test set
    print("\nPredicting on test set...")
    predictions_with_val = model_with_val.predict(test_data)
    
    # Calculate actual outcomes
    test_results = test_data.merge(
        predictions_with_val[['game_id', 'confidence', 'predicted_winner', 'home_win_probability']],
        on='game_id'
    )
    
    test_results['actual_winner'] = test_results.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    
    test_results['correct'] = (test_results['predicted_winner'] == test_results['actual_winner']).astype(int)
    
    # Calculate metrics
    y_true = test_results['correct'].values
    y_pred = test_results['home_win_probability'].values
    
    print_calibration_report(y_true, y_pred, "Model WITH Validation Calibration")
    
    # ================================================================
    # Test 2: Model WITHOUT validation calibration (baseline)
    # ================================================================
    print("\n" + "="*80)
    print("TEST 2: Model WITHOUT Validation Calibration (Baseline)")
    print("="*80)
    print()
    
    model_without_val = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True
    )
    
    print("Training model without validation split...")
    model_without_val.fit(train_data, use_validation=False)
    
    # Predict on test set
    print("\nPredicting on test set...")
    predictions_without_val = model_without_val.predict(test_data)
    
    # Calculate actual outcomes
    test_results_baseline = test_data.merge(
        predictions_without_val[['game_id', 'confidence', 'predicted_winner', 'home_win_probability']],
        on='game_id'
    )
    
    test_results_baseline['actual_winner'] = test_results_baseline.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    
    test_results_baseline['correct'] = (test_results_baseline['predicted_winner'] == test_results_baseline['actual_winner']).astype(int)
    
    # Calculate metrics
    y_true_baseline = test_results_baseline['correct'].values
    y_pred_baseline = test_results_baseline['home_win_probability'].values
    
    print_calibration_report(y_true_baseline, y_pred_baseline, "Model WITHOUT Validation Calibration")
    
    # ================================================================
    # Comparison
    # ================================================================
    print("\n" + "="*80)
    print("IMPROVEMENT COMPARISON")
    print("="*80)
    print()
    
    # Calculate improvements
    ece_with = expected_calibration_error(y_true, y_pred)
    ece_without = expected_calibration_error(y_true_baseline, y_pred_baseline)
    ece_improvement = ((ece_without - ece_with) / ece_without * 100) if ece_without > 0 else 0
    
    brier_with = brier_score(y_true, y_pred)
    brier_without = brier_score(y_true_baseline, y_pred_baseline)
    brier_improvement = ((brier_without - brier_with) / brier_without * 100) if brier_without > 0 else 0
    
    logloss_with = log_loss(y_true, y_pred)
    logloss_without = log_loss(y_true_baseline, y_pred_baseline)
    logloss_improvement = ((logloss_without - logloss_with) / logloss_without * 100) if logloss_without > 0 else 0
    
    print(f"{'Metric':<20} {'Without Val':>15} {'With Val':>15} {'Improvement':>15}")
    print("-" * 70)
    print(f"{'ECE':<20} {ece_without:>15.4f} {ece_with:>15.4f} {ece_improvement:>14.1f}%")
    print(f"{'Brier Score':<20} {brier_without:>15.4f} {brier_with:>15.4f} {brier_improvement:>14.1f}%")
    print(f"{'Log Loss':<20} {logloss_without:>15.4f} {logloss_with:>15.4f} {logloss_improvement:>14.1f}%")
    print()
    
    # High confidence check
    high_conf_with = test_results[test_results['confidence'] >= 0.80]
    high_conf_without = test_results_baseline[test_results_baseline['confidence'] >= 0.80]
    
    if len(high_conf_with) > 0:
        high_conf_acc_with = high_conf_with['correct'].mean()
        high_conf_avg_with = high_conf_with['confidence'].mean()
        print(f"80%+ Confidence WITH validation:")
        print(f"  Games: {len(high_conf_with)}")
        print(f"  Avg confidence: {high_conf_avg_with:.1%}")
        print(f"  Accuracy: {high_conf_acc_with:.1%}")
        print(f"  Gap: {abs(high_conf_avg_with - high_conf_acc_with):.1%} {'✅' if abs(high_conf_avg_with - high_conf_acc_with) < 0.05 else '⚠️'}")
        print()
    
    if len(high_conf_without) > 0:
        high_conf_acc_without = high_conf_without['correct'].mean()
        high_conf_avg_without = high_conf_without['confidence'].mean()
        print(f"80%+ Confidence WITHOUT validation:")
        print(f"  Games: {len(high_conf_without)}")
        print(f"  Avg confidence: {high_conf_avg_without:.1%}")
        print(f"  Accuracy: {high_conf_acc_without:.1%}")
        print(f"  Gap: {abs(high_conf_avg_without - high_conf_acc_without):.1%} {'✅' if abs(high_conf_avg_without - high_conf_acc_without) < 0.05 else '⚠️'}")
        print()
    
    # Overall verdict
    print("="*80)
    print("VERDICT")
    print("="*80)
    print()
    
    if ece_with < ece_without:
        print(f"✅ IMPROVEMENT: ECE reduced by {ece_improvement:.1f}%")
    else:
        print(f"⚠️  NO IMPROVEMENT: ECE increased")
    
    if ece_with < 0.05:
        print(f"✅ WELL-CALIBRATED: ECE = {ece_with:.4f} < 0.05")
    elif ece_with < 0.10:
        print(f"⚠️  ACCEPTABLE: ECE = {ece_with:.4f} < 0.10")
    else:
        print(f"❌ POORLY CALIBRATED: ECE = {ece_with:.4f} > 0.10")
    
    print()
    print("="*80)
    
    db.close()


if __name__ == '__main__':
    test_calibration()
