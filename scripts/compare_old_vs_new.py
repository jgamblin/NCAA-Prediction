#!/usr/bin/env python3
"""
End-to-End Comparison: Old (Deployed) vs New (Improved) Model

Compares predictions between:
- OLD: No validation calibration, old hyperparameters, 30 features
- NEW: Validation calibration, tuned hyperparameters, regularization

Shows side-by-side comparison of:
- Accuracy
- Confidence calibration
- Overfitting gap
- High confidence predictions
- Confidence distribution
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
import json


def evaluate_predictions(predictions_df, actual_df, model_name):
    """Evaluate prediction quality."""
    
    # Merge predictions with actuals
    results = actual_df.merge(
        predictions_df[['game_id', 'predicted_winner', 'confidence', 'home_win_probability']],
        on='game_id'
    )
    
    # Determine actual winner
    results['actual_winner'] = results.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    
    results['correct'] = (results['predicted_winner'] == results['actual_winner']).astype(int)
    
    # Overall metrics
    overall_acc = results['correct'].mean()
    avg_conf = results['confidence'].mean()
    cal_gap = abs(avg_conf - overall_acc)
    
    # ECE and Brier
    ece = expected_calibration_error(results['correct'].values, results['confidence'].values)
    brier = brier_score(results['correct'].values, results['confidence'].values)
    logloss = log_loss(results['correct'].values, results['confidence'].values)
    
    # By confidence bucket
    buckets = calibration_by_bucket(results['correct'].values, results['confidence'].values)
    
    return {
        'model_name': model_name,
        'total_games': len(results),
        'overall_accuracy': overall_acc,
        'avg_confidence': avg_conf,
        'calibration_gap': cal_gap,
        'ece': ece,
        'brier': brier,
        'log_loss': logloss,
        'buckets': buckets,
        'results_df': results
    }


def compare_models():
    """Compare old vs new model end-to-end."""
    
    print("="*80)
    print("END-TO-END MODEL COMPARISON")
    print("OLD (Deployed) vs NEW (Improved)")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    
    print("Loading completed games...")
    completed_games = games_repo.get_completed_games_df()
    
    # Use current season
    current_season = completed_games[completed_games['season'] == '2025-26'].copy()
    
    print(f"  Total games (2025-26): {len(current_season):,}")
    print()
    
    # Split: train on first 85%, test on last 15%
    split_idx = int(len(current_season) * 0.85)
    train_data = current_season.iloc[:split_idx].copy()
    test_data = current_season.iloc[split_idx:].copy()
    
    print(f"Training on: {len(train_data):,} games")
    print(f"Testing on:  {len(test_data):,} games")
    print()
    
    # ================================================================
    # OLD MODEL (Deployed)
    # ================================================================
    print("\n" + "="*80)
    print("TRAINING OLD MODEL (Currently Deployed)")
    print("="*80)
    print()
    print("Settings:")
    print("  - No validation calibration (trains on all data)")
    print("  - No isotonic regression")
    print("  - Temperature: auto (not tuned on validation)")
    print("  - XGBoost defaults: max_depth=6, no regularization")
    print("  - All 30 features (including useless ones)")
    print()
    
    old_model = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True,
        model_type='xgboost',
        # OLD settings (before Week 2)
        xgb_max_depth=6,
        xgb_learning_rate=0.1,
        xgb_n_estimators=200,
        xgb_subsample=0.8,
        xgb_colsample_bytree=0.8,
        xgb_reg_alpha=0.0,  # NO L1 regularization
        xgb_reg_lambda=1.0,  # Minimal L2
    )
    
    print("Training...")
    old_model.fit(train_data, use_validation=False)  # No validation split
    
    # Get training accuracy
    train_prepared = old_model.prepare_data(train_data.copy())
    y_train = train_prepared['home_win']
    trained_features = old_model._raw_model.feature_names_in_
    X_train = train_prepared.reindex(columns=list(trained_features), fill_value=0)
    train_probs = old_model._raw_model.predict_proba(X_train)[:, 1]
    train_preds = (train_probs >= 0.5).astype(int)
    old_train_acc = (train_preds == y_train).mean()
    
    print(f"✓ Training accuracy: {old_train_acc:.1%}")
    print()
    
    # Predict on test set
    print("Predicting on test set...")
    old_predictions = old_model.predict(test_data)
    print(f"✓ Generated {len(old_predictions)} predictions")
    print()
    
    # Evaluate
    old_results = evaluate_predictions(old_predictions, test_data, "OLD (Deployed)")
    
    # ================================================================
    # NEW MODEL (Improved)
    # ================================================================
    print("\n" + "="*80)
    print("TRAINING NEW MODEL (Week 1 + Week 2 Improvements)")
    print("="*80)
    print()
    print("Settings:")
    print("  - Validation split for calibration (last 14 days)")
    print("  - Isotonic regression calibration")
    print("  - Temperature tuned on validation")
    print("  - XGBoost tuned: max_depth=6, L1+L2 regularization")
    print("  - Temperature override: 0.60 (emergency fix)")
    print("  - Confidence cap: 85%")
    print()
    
    new_model = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True,
        model_type='xgboost',
        # NEW settings (Week 2)
        xgb_max_depth=6,
        xgb_learning_rate=0.1,
        xgb_n_estimators=150,
        xgb_subsample=0.8,
        xgb_colsample_bytree=0.8,
        xgb_reg_alpha=0.5,   # L1 regularization (Week 2)
        xgb_reg_lambda=2.0,  # L2 regularization (Week 2)
    )
    
    print("Training...")
    new_model.fit(train_data, use_validation=True, val_days=14)  # WITH validation
    
    # Get training accuracy
    train_prepared_new = new_model.prepare_data(train_data.copy())
    y_train_new = train_prepared_new['home_win']
    trained_features_new = new_model._raw_model.feature_names_in_
    X_train_new = train_prepared_new.reindex(columns=list(trained_features_new), fill_value=0)
    train_probs_new = new_model._raw_model.predict_proba(X_train_new)[:, 1]
    train_preds_new = (train_probs_new >= 0.5).astype(int)
    new_train_acc = (train_preds_new == y_train_new).mean()
    
    print(f"✓ Training accuracy: {new_train_acc:.1%}")
    print()
    
    # Predict on test set
    print("Predicting on test set...")
    new_predictions = new_model.predict(test_data)
    print(f"✓ Generated {len(new_predictions)} predictions")
    print()
    
    # Evaluate
    new_results = evaluate_predictions(new_predictions, test_data, "NEW (Improved)")
    
    # ================================================================
    # SIDE-BY-SIDE COMPARISON
    # ================================================================
    print("\n" + "="*80)
    print("SIDE-BY-SIDE COMPARISON")
    print("="*80)
    print()
    
    # Overall metrics table
    print("Overall Metrics:")
    print(f"{'Metric':<25} {'OLD (Deployed)':>15} {'NEW (Improved)':>15} {'Change':>12}")
    print("-" * 70)
    
    metrics = [
        ('Total Games', old_results['total_games'], new_results['total_games'], 'count'),
        ('Accuracy', old_results['overall_accuracy'], new_results['overall_accuracy'], 'percent'),
        ('Avg Confidence', old_results['avg_confidence'], new_results['avg_confidence'], 'percent'),
        ('Calibration Gap', old_results['calibration_gap'], new_results['calibration_gap'], 'percent'),
        ('ECE', old_results['ece'], new_results['ece'], 'decimal'),
        ('Brier Score', old_results['brier'], new_results['brier'], 'decimal'),
        ('Log Loss', old_results['log_loss'], new_results['log_loss'], 'decimal'),
        ('Training Accuracy', old_train_acc, new_train_acc, 'percent'),
    ]
    
    for name, old_val, new_val, fmt in metrics:
        if fmt == 'count':
            print(f"{name:<25} {old_val:>15,} {new_val:>15,} {'-':>12}")
        elif fmt == 'percent':
            change = new_val - old_val
            symbol = '✅' if change > 0 and 'Acc' in name else '✅' if change < 0 and 'Gap' in name else '⚠️'
            print(f"{name:<25} {old_val:>14.1%} {new_val:>14.1%} {change:>11.1%} {symbol}")
        elif fmt == 'decimal':
            change = new_val - old_val
            symbol = '✅' if change < 0 else '⚠️'
            print(f"{name:<25} {old_val:>15.4f} {new_val:>15.4f} {change:>11.4f} {symbol}")
    
    print()
    
    # Overfitting analysis
    old_overfit = old_train_acc - old_results['overall_accuracy']
    new_overfit = new_train_acc - new_results['overall_accuracy']
    overfit_improvement = old_overfit - new_overfit
    
    print("Overfitting Analysis:")
    print(f"  OLD: Train {old_train_acc:.1%} - Test {old_results['overall_accuracy']:.1%} = {old_overfit:.1%} gap")
    print(f"  NEW: Train {new_train_acc:.1%} - Test {new_results['overall_accuracy']:.1%} = {new_overfit:.1%} gap")
    print(f"  Improvement: {overfit_improvement:.1%} {'✅' if overfit_improvement > 0 else '⚠️'}")
    print()
    
    # ================================================================
    # CONFIDENCE BUCKET COMPARISON
    # ================================================================
    print("\n" + "="*80)
    print("CONFIDENCE BUCKET COMPARISON")
    print("="*80)
    print()
    
    print("OLD (Deployed) - Calibration by Bucket:")
    print(f"{'Bucket':<12} {'Games':>7} {'Avg Conf':>10} {'Accuracy':>10} {'Gap':>8} {'Status':>8}")
    print("-" * 60)
    for _, row in old_results['buckets'].iterrows():
        gap = row['gap']
        status = '✅' if abs(gap) < 0.05 else '⚠️' if abs(gap) < 0.10 else '❌'
        print(f"{row['bucket']:<12} {row['games']:>7} {row['avg_confidence']:>10.1%} "
              f"{row['accuracy']:>10.1%} {gap:>8.1%} {status:>8}")
    
    print()
    print("NEW (Improved) - Calibration by Bucket:")
    print(f"{'Bucket':<12} {'Games':>7} {'Avg Conf':>10} {'Accuracy':>10} {'Gap':>8} {'Status':>8}")
    print("-" * 60)
    for _, row in new_results['buckets'].iterrows():
        gap = row['gap']
        status = '✅' if abs(gap) < 0.05 else '⚠️' if abs(gap) < 0.10 else '❌'
        print(f"{row['bucket']:<12} {row['games']:>7} {row['avg_confidence']:>10.1%} "
              f"{row['accuracy']:>10.1%} {gap:>8.1%} {status:>8}")
    
    print()
    
    # ================================================================
    # HIGH CONFIDENCE COMPARISON
    # ================================================================
    print("\n" + "="*80)
    print("HIGH CONFIDENCE PREDICTIONS (80%+)")
    print("="*80)
    print()
    
    old_high_conf = old_results['results_df'][old_results['results_df']['confidence'] >= 0.80]
    new_high_conf = new_results['results_df'][new_results['results_df']['confidence'] >= 0.80]
    
    print(f"{'Model':<20} {'Count':>8} {'Avg Conf':>10} {'Accuracy':>10} {'Gap':>8}")
    print("-" * 60)
    
    if len(old_high_conf) > 0:
        old_hc_acc = old_high_conf['correct'].mean()
        old_hc_conf = old_high_conf['confidence'].mean()
        old_hc_gap = old_hc_conf - old_hc_acc
        print(f"{'OLD (Deployed)':<20} {len(old_high_conf):>8} {old_hc_conf:>10.1%} "
              f"{old_hc_acc:>10.1%} {old_hc_gap:>8.1%}")
    else:
        print(f"{'OLD (Deployed)':<20} {'0':>8} {'-':>10} {'-':>10} {'-':>8}")
    
    if len(new_high_conf) > 0:
        new_hc_acc = new_high_conf['correct'].mean()
        new_hc_conf = new_high_conf['confidence'].mean()
        new_hc_gap = new_hc_conf - new_hc_acc
        print(f"{'NEW (Improved)':<20} {len(new_high_conf):>8} {new_hc_conf:>10.1%} "
              f"{new_hc_acc:>10.1%} {new_hc_gap:>8.1%}")
    else:
        print(f"{'NEW (Improved)':<20} {'0':>8} {'-':>10} {'-':>10} {'-':>8}")
    
    print()
    
    if len(old_high_conf) > 0 and len(new_high_conf) > 0:
        hc_improvement = new_hc_acc - old_hc_acc
        print(f"High Confidence Accuracy Improvement: {hc_improvement:+.1%} {'✅' if hc_improvement > 0 else '⚠️'}")
        
        hc_gap_improvement = old_hc_gap - new_hc_gap
        print(f"High Confidence Gap Reduction: {hc_gap_improvement:.1%} {'✅' if hc_gap_improvement > 0 else '⚠️'}")
        print()
    
    # ================================================================
    # CONFIDENCE DISTRIBUTION
    # ================================================================
    print("\n" + "="*80)
    print("CONFIDENCE DISTRIBUTION")
    print("="*80)
    print()
    
    old_dist = pd.cut(old_results['results_df']['confidence'], 
                      bins=[0, 0.5, 0.6, 0.7, 0.8, 1.0],
                      labels=['<50%', '50-60%', '60-70%', '70-80%', '80%+'])
    new_dist = pd.cut(new_results['results_df']['confidence'],
                      bins=[0, 0.5, 0.6, 0.7, 0.8, 1.0],
                      labels=['<50%', '50-60%', '60-70%', '70-80%', '80%+'])
    
    print(f"{'Confidence Range':<15} {'OLD Count':>12} {'OLD %':>10} {'NEW Count':>12} {'NEW %':>10}")
    print("-" * 65)
    
    for bucket in ['<50%', '50-60%', '60-70%', '70-80%', '80%+']:
        old_count = (old_dist == bucket).sum()
        old_pct = old_count / len(old_dist) * 100
        new_count = (new_dist == bucket).sum()
        new_pct = new_count / len(new_dist) * 100
        
        print(f"{bucket:<15} {old_count:>12} {old_pct:>9.1f}% {new_count:>12} {new_pct:>9.1f}%")
    
    print()
    
    # ================================================================
    # VERDICT
    # ================================================================
    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)
    print()
    
    improvements = []
    regressions = []
    
    # Check improvements
    if new_results['overall_accuracy'] > old_results['overall_accuracy']:
        improvements.append(f"Accuracy improved: {old_results['overall_accuracy']:.1%} → {new_results['overall_accuracy']:.1%}")
    
    if new_results['calibration_gap'] < old_results['calibration_gap']:
        improvements.append(f"Calibration improved: {old_results['calibration_gap']:.1%} → {new_results['calibration_gap']:.1%}")
    
    if new_results['ece'] < old_results['ece']:
        improvements.append(f"ECE improved: {old_results['ece']:.4f} → {new_results['ece']:.4f}")
    
    if new_overfit < old_overfit:
        improvements.append(f"Overfitting reduced: {old_overfit:.1%} → {new_overfit:.1%}")
    
    if len(new_high_conf) > 0 and len(old_high_conf) > 0:
        if new_hc_acc > old_hc_acc:
            improvements.append(f"High confidence accuracy: {old_hc_acc:.1%} → {new_hc_acc:.1%}")
    
    # Check regressions
    if new_results['overall_accuracy'] < old_results['overall_accuracy']:
        regressions.append(f"⚠️  Accuracy decreased: {old_results['overall_accuracy']:.1%} → {new_results['overall_accuracy']:.1%}")
    
    if new_results['ece'] > old_results['ece']:
        regressions.append(f"⚠️  ECE increased: {old_results['ece']:.4f} → {new_results['ece']:.4f}")
    
    # Print verdict
    if improvements:
        print("✅ IMPROVEMENTS:")
        for imp in improvements:
            print(f"   {imp}")
        print()
    
    if regressions:
        print("⚠️  REGRESSIONS:")
        for reg in regressions:
            print(f"   {reg}")
        print()
    
    # Overall score
    improvement_score = len(improvements) - len(regressions)
    
    if improvement_score >= 3:
        print("🎉 OVERALL: SIGNIFICANT IMPROVEMENT - Deploy the new model!")
    elif improvement_score > 0:
        print("✅ OVERALL: MODEST IMPROVEMENT - New model is better")
    elif improvement_score == 0:
        print("⚠️  OVERALL: NEUTRAL - Models perform similarly")
    else:
        print("❌ OVERALL: REGRESSION - Keep old model, investigate issues")
    
    print()
    
    # Save comparison
    comparison_results = {
        'old_model': {
            'accuracy': float(old_results['overall_accuracy']),
            'avg_confidence': float(old_results['avg_confidence']),
            'calibration_gap': float(old_results['calibration_gap']),
            'ece': float(old_results['ece']),
            'brier': float(old_results['brier']),
            'train_accuracy': float(old_train_acc),
            'overfit_gap': float(old_overfit),
        },
        'new_model': {
            'accuracy': float(new_results['overall_accuracy']),
            'avg_confidence': float(new_results['avg_confidence']),
            'calibration_gap': float(new_results['calibration_gap']),
            'ece': float(new_results['ece']),
            'brier': float(new_results['brier']),
            'train_accuracy': float(new_train_acc),
            'overfit_gap': float(new_overfit),
        },
        'improvements': improvements,
        'regressions': regressions,
        'improvement_score': improvement_score,
        'test_date': pd.Timestamp.now().isoformat()
    }
    
    output_path = 'data/model_comparison_results.json'
    with open(output_path, 'w') as f:
        json.dump(comparison_results, f, indent=2)
    
    print(f"Comparison results saved to: {output_path}")
    print()
    print("="*80)
    
    db.close()


if __name__ == '__main__':
    compare_models()
