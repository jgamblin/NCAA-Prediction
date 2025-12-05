#!/usr/bin/env python3
"""
Hyperparameter Tuning with Validation Set

Tunes model hyperparameters to reduce overfitting:
- RandomForest: max_depth, min_samples_split, min_samples_leaf, max_features
- XGBoost: max_depth, learning_rate, subsample, colsample_bytree, reg_alpha, reg_lambda

Uses validation set for evaluation (NOT training set).
Goal: Reduce train/val accuracy gap from 13-18% to <8%.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.train_val_split import create_validation_split
from model_training.calibration_metrics import expected_calibration_error, brier_score
from sklearn.model_selection import ParameterGrid
import pandas as pd
import numpy as np
import json


def evaluate_model(model, val_data):
    """Evaluate model on validation set."""
    val_prepared = model.prepare_data(val_data.copy())
    y_val = val_prepared['home_win']
    
    # Get features
    trained_features = model._raw_model.feature_names_in_
    X_val = val_prepared.reindex(columns=list(trained_features), fill_value=0)
    
    # Predictions
    val_probs = model._raw_model.predict_proba(X_val)[:, 1]
    val_preds = (val_probs >= 0.5).astype(int)
    
    # Metrics
    accuracy = (val_preds == y_val).mean()
    ece = expected_calibration_error(y_val.values, val_probs)
    brier = brier_score(y_val.values, val_probs)
    
    return {
        'accuracy': accuracy,
        'ece': ece,
        'brier': brier
    }


def tune_hyperparameters():
    """Grid search hyperparameter tuning."""
    
    print("="*80)
    print("HYPERPARAMETER TUNING")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    
    print("Loading completed games...")
    completed_games = games_repo.get_completed_games_df()
    
    # Use current season
    current_season = completed_games[completed_games['season'] == '2025-26'].copy()
    
    print(f"  Current season (2025-26): {len(current_season):,} games")
    print()
    
    # Split data
    train_data, val_data = create_validation_split(current_season, val_days=21)
    
    # ================================================================
    # XGBoost Hyperparameter Grid
    # ================================================================
    print("\n" + "="*80)
    print("TUNING XGBOOST HYPERPARAMETERS")
    print("="*80)
    print()
    
    xgb_param_grid = {
        'max_depth': [4, 6, 8],
        'learning_rate': [0.05, 0.1, 0.15],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'reg_alpha': [0.0, 0.1, 0.5],  # L1 regularization
        'reg_lambda': [1.0, 2.0, 3.0],  # L2 regularization
    }
    
    # Start with a smaller grid for speed
    focused_grid = {
        'max_depth': [6, 8],
        'learning_rate': [0.05, 0.1],
        'subsample': [0.8],
        'colsample_bytree': [0.8],
        'reg_alpha': [0.1, 0.5],
        'reg_lambda': [1.0, 2.0],
    }
    
    print(f"Testing {len(list(ParameterGrid(focused_grid)))} parameter combinations...")
    print()
    
    results = []
    best_score = -np.inf
    best_params = None
    
    for i, params in enumerate(ParameterGrid(focused_grid), 1):
        print(f"[{i}/{len(list(ParameterGrid(focused_grid)))}] Testing: {params}")
        
        try:
            # Train model with these hyperparameters
            model = AdaptivePredictor(
                use_smart_encoding=True,
                use_early_season_adjustment=True,
                calibrate=True,
                model_type='xgboost',
                # XGBoost specific params
                xgb_max_depth=params['max_depth'],
                xgb_learning_rate=params['learning_rate'],
                xgb_n_estimators=150,  # Fixed
                xgb_subsample=params['subsample'],
                xgb_colsample_bytree=params['colsample_bytree'],
                xgb_reg_alpha=params['reg_alpha'],
                xgb_reg_lambda=params['reg_lambda']
            )
            
            # Train (without validation split since we already split)
            model.fit(train_data, use_validation=False)
            
            # Evaluate on validation
            metrics = evaluate_model(model, val_data)
            
            # Calculate training accuracy
            train_prepared = model.prepare_data(train_data.copy())
            y_train = train_prepared['home_win']
            trained_features = model._raw_model.feature_names_in_
            X_train = train_prepared.reindex(columns=list(trained_features), fill_value=0)
            train_preds = (model._raw_model.predict_proba(X_train)[:, 1] >= 0.5).astype(int)
            train_acc = (train_preds == y_train).mean()
            
            # Overfitting gap
            overfit_gap = train_acc - metrics['accuracy']
            
            # Score: balance accuracy and calibration, penalize overfitting
            score = metrics['accuracy'] - (metrics['ece'] * 0.5) - (overfit_gap * 0.3)
            
            result = {
                **params,
                'val_accuracy': metrics['accuracy'],
                'val_ece': metrics['ece'],
                'val_brier': metrics['brier'],
                'train_accuracy': train_acc,
                'overfit_gap': overfit_gap,
                'score': score
            }
            results.append(result)
            
            print(f"  Val Acc: {metrics['accuracy']:.3f} | Train Acc: {train_acc:.3f} | "
                  f"Overfit: {overfit_gap:.3f} | ECE: {metrics['ece']:.4f} | Score: {score:.4f}")
            
            if score > best_score:
                best_score = score
                best_params = params
                print(f"  ✓ New best score!")
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        
        print()
    
    # Results DataFrame
    results_df = pd.DataFrame(results).sort_values('score', ascending=False)
    
    print("="*80)
    print("TUNING RESULTS")
    print("="*80)
    print()
    
    print("Top 5 Parameter Combinations:")
    print()
    cols_to_show = ['max_depth', 'learning_rate', 'reg_alpha', 'reg_lambda', 
                    'val_accuracy', 'overfit_gap', 'val_ece', 'score']
    print(results_df[cols_to_show].head().to_string(index=False))
    print()
    
    print("Best Parameters:")
    for key, value in best_params.items():
        print(f"  {key}: {value}")
    print()
    
    print(f"Best Score: {best_score:.4f}")
    print()
    
    # Compare with baseline
    baseline = results_df[
        (results_df['max_depth'] == 6) & 
        (results_df['learning_rate'] == 0.1)
    ]
    
    if len(baseline) > 0:
        baseline_score = baseline['score'].iloc[0]
        improvement = ((best_score - baseline_score) / abs(baseline_score)) * 100
        print(f"Improvement over baseline: {improvement:.1f}%")
        print()
    
    # ================================================================
    # Save Results
    # ================================================================
    output_path = 'data/hyperparameter_tuning_results.json'
    os.makedirs('data', exist_ok=True)
    
    tuning_results = {
        'best_params': best_params,
        'best_score': float(best_score),
        'all_results': results_df.to_dict('records'),
        'analysis_date': pd.Timestamp.now().isoformat()
    }
    
    with open(output_path, 'w') as f:
        json.dump(tuning_results, f, indent=2)
    
    print(f"Results saved to: {output_path}")
    print()
    
    # ================================================================
    # Test Best Model
    # ================================================================
    print("="*80)
    print("TESTING BEST MODEL")
    print("="*80)
    print()
    
    # Train final model with best params
    best_model = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True,
        model_type='xgboost',
        xgb_max_depth=best_params['max_depth'],
        xgb_learning_rate=best_params['learning_rate'],
        xgb_n_estimators=150,
        xgb_subsample=best_params['subsample'],
        xgb_colsample_bytree=best_params['colsample_bytree'],
        xgb_reg_alpha=best_params['reg_alpha'],
        xgb_reg_lambda=best_params['reg_lambda']
    )
    
    print("Training best model with full validation...")
    best_model.fit(train_data, use_validation=False)
    
    # Detailed evaluation
    val_metrics = evaluate_model(best_model, val_data)
    
    train_prepared = best_model.prepare_data(train_data.copy())
    y_train = train_prepared['home_win']
    trained_features = best_model._raw_model.feature_names_in_
    X_train = train_prepared.reindex(columns=list(trained_features), fill_value=0)
    train_preds = (best_model._raw_model.predict_proba(X_train)[:, 1] >= 0.5).astype(int)
    train_acc = (train_preds == y_train).mean()
    
    print(f"\nFinal Model Performance:")
    print(f"  Training Accuracy:   {train_acc:.1%}")
    print(f"  Validation Accuracy: {val_metrics['accuracy']:.1%}")
    print(f"  Overfit Gap:         {train_acc - val_metrics['accuracy']:.1%}")
    print(f"  Validation ECE:      {val_metrics['ece']:.4f}")
    print(f"  Validation Brier:    {val_metrics['brier']:.4f}")
    print()
    
    if (train_acc - val_metrics['accuracy']) < 0.08:
        print("✅ OVERFITTING REDUCED: Gap < 8%")
    else:
        print("⚠️  Still overfitting, may need more regularization")
    
    if val_metrics['ece'] < 0.05:
        print("✅ WELL CALIBRATED: ECE < 0.05")
    else:
        print("⚠️  Needs better calibration")
    
    print()
    print("="*80)
    
    db.close()


if __name__ == '__main__':
    tune_hyperparameters()
