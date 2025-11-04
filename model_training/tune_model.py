#!/usr/bin/env python3
"""
Weekly Model Tuning with Time-Weighted Training
This script tunes the model weekly to prioritize recent season data over historical data.
Run this weekly to keep the model sharp on current season trends.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from datetime import datetime, timedelta
import os
import json

def calculate_sample_weights(df, current_season='2025-26', decay_factor=0.5):
    """
    Calculate sample weights that heavily favor current season data.
    
    Args:
        df: DataFrame with game data
        current_season: Current season (e.g., '2025-26')
        decay_factor: How much to reduce weight for each season back (0.5 = half weight per season)
    
    Returns:
        Array of sample weights
    """
    weights = np.ones(len(df))
    
    # Define season order (most recent = highest weight)
    seasons = sorted(df['season'].unique(), reverse=True)
    season_weights = {}
    
    for i, season in enumerate(seasons):
        if season == current_season:
            # Current season gets full weight (10x multiplier)
            season_weights[season] = 10.0
        elif i == 1:
            # Last season (2024-25) gets 3x weight - still very relevant
            season_weights[season] = 3.0
        elif i == 2:
            # 2 seasons ago (2023-24) gets 1.5x weight
            season_weights[season] = 1.5
        else:
            # Older seasons decay exponentially
            season_weights[season] = decay_factor ** (i - 2)
    
    # Apply weights
    for season, weight in season_weights.items():
        weights[df['season'] == season] = weight
    
    # Additional recency boost within current season
    if current_season in df['season'].values:
        current_season_mask = df['season'] == current_season
        current_season_df = df[current_season_mask]
        
        if len(current_season_df) > 0:
            # Parse dates and calculate days since start of season
            dates = pd.to_datetime(current_season_df['game_day'])
            days_since_start = (dates - dates.min()).dt.days
            max_days = days_since_start.max()
            
            if max_days > 0:
                # Linear recency boost: more recent games get up to 2x additional weight
                recency_multiplier = 1.0 + (days_since_start / max_days)
                weights[current_season_mask] *= recency_multiplier
    
    return weights

def tune_hyperparameters(X, y, sample_weights):
    """
    Tune model hyperparameters using time-series cross-validation.
    
    Returns:
        Best hyperparameters dictionary
    """
    print("Tuning hyperparameters with weighted cross-validation...")
    
    # Define hyperparameter grid (focused search)
    param_combinations = [
        {'n_estimators': 100, 'max_depth': 15, 'min_samples_split': 20},
        {'n_estimators': 100, 'max_depth': 20, 'min_samples_split': 10},
        {'n_estimators': 150, 'max_depth': 20, 'min_samples_split': 10},
        {'n_estimators': 200, 'max_depth': 25, 'min_samples_split': 5},
        {'n_estimators': 150, 'max_depth': 30, 'min_samples_split': 10},
    ]
    
    best_score = -np.inf
    best_params = None
    
    # Use TimeSeriesSplit to respect temporal ordering
    tscv = TimeSeriesSplit(n_splits=5)
    
    for params in param_combinations:
        model = RandomForestClassifier(
            random_state=42,
            n_jobs=-1,
            **params
        )
        
        # Manually run cross-validation with sample weights
        scores = []
        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            weights_train = sample_weights[train_idx]
            
            model.fit(X_train, y_train, sample_weight=weights_train)
            score = model.score(X_test, y_test)
            scores.append(score)
        
        scores = np.array(scores)
        
        mean_score = scores.mean()
        print(f"  Params: {params} → Score: {mean_score:.4f} (±{scores.std():.4f})")
        
        if mean_score > best_score:
            best_score = mean_score
            best_params = params
    
    print(f"\n✓ Best parameters: {best_params}")
    print(f"✓ Best CV score: {best_score:.4f}")
    
    return best_params

def train_weighted_model():
    """Train model with time-weighted samples and tuned hyperparameters."""
    
    print("="*80)
    print("WEEKLY MODEL TUNING - TIME-WEIGHTED TRAINING")
    print("="*80)
    print()
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    historical_path = os.path.join(data_dir, 'Completed_Games.csv')
    
    # Load data
    print("Loading training data...")
    df = pd.read_csv(historical_path)
    df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
    
    print(f"✓ Loaded {len(df)} games")
    print(f"  Seasons: {sorted(df['season'].unique())}")
    
    # Show season distribution
    season_counts = df.groupby('season').size().sort_index()
    print(f"\nGames per season:")
    for season, count in season_counts.items():
        print(f"  {season}: {count:,} games")
    
    # Calculate sample weights
    print("\nCalculating time-weighted sample weights...")
    current_season = '2025-26'
    sample_weights = calculate_sample_weights(df, current_season=current_season)
    
    print(f"\nSample weight distribution:")
    for season in sorted(df['season'].unique(), reverse=True):
        season_mask = df['season'] == season
        avg_weight = sample_weights[season_mask].mean()
        print(f"  {season}: {avg_weight:.2f}x weight (avg)")
    
    # Encode teams
    print("\nEncoding teams...")
    all_teams = pd.concat([df['home_team'], df['away_team']]).unique()
    team_encoder = LabelEncoder()
    team_encoder.fit(all_teams)
    
    df['home_team_encoded'] = team_encoder.transform(df['home_team'])
    df['away_team_encoded'] = team_encoder.transform(df['away_team'])
    
    # Handle missing columns properly
    if 'is_neutral' in df.columns:
        df['is_neutral'] = df['is_neutral'].fillna(0).astype(int)
    else:
        df['is_neutral'] = 0
    
    df['home_rank'] = df['home_rank'].fillna(99).astype(int)
    df['away_rank'] = df['away_rank'].fillna(99).astype(int)
    
    # Prepare features
    feature_cols = ['home_team_encoded', 'away_team_encoded', 'is_neutral', 'home_rank', 'away_rank']
    X = df[feature_cols]
    y = df['home_win']
    
    print(f"✓ Features: {feature_cols}")
    
    # Tune hyperparameters
    print()
    best_params = tune_hyperparameters(X, y, sample_weights)
    
    # Train final model with best parameters and sample weights
    print("\nTraining final weighted model...")
    final_model = RandomForestClassifier(
        random_state=42,
        n_jobs=-1,
        **best_params
    )
    final_model.fit(X, y, sample_weight=sample_weights)
    
    # Evaluate on current season data
    current_season_mask = df['season'] == current_season
    current_accuracy = None  # Initialize to avoid unbound variable
    
    if current_season_mask.sum() > 0:
        X_current = X[current_season_mask]
        y_current = y[current_season_mask]
        
        current_accuracy = final_model.score(X_current, y_current)
        print(f"\n✓ Current season ({current_season}) accuracy: {current_accuracy:.1%}")
    
    # Overall accuracy (weighted)
    overall_accuracy = final_model.score(X, y, sample_weight=sample_weights)
    print(f"✓ Weighted overall accuracy: {overall_accuracy:.1%}")
    
    # Save tuning results
    tuning_results = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'current_season': current_season,
        'total_games': len(df),
        'best_params': best_params,
        'weighted_accuracy': float(overall_accuracy),
        'current_season_games': int(current_season_mask.sum()),
        'current_season_accuracy': float(current_accuracy) if current_accuracy is not None else None,
        'season_weights': {
            season: float(sample_weights[df['season'] == season].mean())
            for season in sorted(df['season'].unique(), reverse=True)
        }
    }
    
    tuning_log_path = os.path.join(data_dir, 'Model_Tuning_Log.json')
    
    # Append to existing log
    if os.path.exists(tuning_log_path):
        with open(tuning_log_path, 'r') as f:
            log = json.load(f)
        if not isinstance(log, list):
            log = [log]
        log.append(tuning_results)
    else:
        log = [tuning_results]
    
    with open(tuning_log_path, 'w') as f:
        json.dump(log, f, indent=2)
    
    print(f"\n✓ Saved tuning results to {tuning_log_path}")
    
    print("\n" + "="*80)
    print("TUNING COMPLETE!")
    print("="*80)
    
    if best_params:
        print("\nRecommendation: Update daily_pipeline.py with these parameters:")
        print(f"  n_estimators={best_params['n_estimators']}")
        print(f"  max_depth={best_params['max_depth']}")
        print(f"  min_samples_split={best_params['min_samples_split']}")
        print("\nAnd add sample_weight=calculate_sample_weights(train_df) to model.fit()")
    
    print("="*80)

if __name__ == "__main__":
    train_weighted_model()
