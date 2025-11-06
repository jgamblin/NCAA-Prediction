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
from sklearn.model_selection import TimeSeriesSplit
from datetime import datetime
import os
import json
import sys

# Optional lineage imports (defensive)
try:  # pragma: no cover
    from config.load_config import get_config_version
    from config.versioning import get_commit_hash
    _config_version = get_config_version()
    _commit_hash = get_commit_hash()
except Exception:  # noqa: BLE001
    _config_version = 'unknown'
    _commit_hash = 'unknown'

# Feature store utilities
try:  # pragma: no cover
    from model_training.feature_store import load_feature_store
    from model_training.team_id_utils import ensure_team_ids
    _fs_available = True
except Exception:  # Provide safe fallbacks so static analysis sees symbols
    _fs_available = False
    def load_feature_store():  # type: ignore
        return pd.DataFrame()
    def ensure_team_ids(df: pd.DataFrame, home_col: str = 'home_team', away_col: str = 'away_team'):  # type: ignore
        return df

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

def tune_hyperparameters(X, y, sample_weights, quick: bool = False):
    """
    Tune model hyperparameters using time-series cross-validation.
    
    Returns:
        Best hyperparameters dictionary
    """
    print("Tuning hyperparameters with weighted cross-validation...")
    
    # Define hyperparameter grid (focused search)
    if quick:
        param_combinations: list[dict[str,int]] = [
            {'n_estimators': 120, 'max_depth': 18, 'min_samples_split': 10},
            {'n_estimators': 200, 'max_depth': 25, 'min_samples_split': 5}
        ]
        print("Quick mode enabled: reduced hyperparameter grid.")
    else:
        param_combinations: list[dict[str,int]] = [
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
            n_estimators=params['n_estimators'],
            max_depth=params['max_depth'],
            min_samples_split=params['min_samples_split']
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

def _integrate_feature_store(train_df: pd.DataFrame) -> pd.DataFrame:
    """Merge latest feature store aggregates and derive diff features if available."""
    if not _fs_available:
        print("Feature store utilities unavailable; skipping FS integration.")
        return train_df
    try:
        fs_df = load_feature_store()
        if fs_df.empty:
            print("Feature store empty; skip integration.")
            return train_df
        # Ensure IDs on training data
        train_df = ensure_team_ids(train_df)
        # Reduce FS to latest row per (season, team_id)
        fs_reduced = fs_df.sort_values(['season','team_id','games_played']).drop_duplicates(['season','team_id'], keep='last')
        home_fs = fs_reduced.add_prefix('home_fs_').rename(columns={'home_fs_team_id':'home_team_id'})
        away_fs = fs_reduced.add_prefix('away_fs_').rename(columns={'away_fs_team_id':'away_team_id'})
        if 'season' not in train_df.columns:
            # Attempt inference from FS
            inferred_season = fs_reduced['season'].max()
            train_df['season'] = inferred_season
        train_df = train_df.merge(home_fs, on=['home_team_id','season'], how='left')
        train_df = train_df.merge(away_fs, on=['away_team_id','season'], how='left')
        # Diff features
        diff_specs = [
            ('rolling_win_pct_5','fs_win_pct5_diff'),
            ('rolling_win_pct_10','fs_win_pct10_diff'),
            ('rolling_point_diff_avg_5','fs_point_diff5_diff'),
            ('rolling_point_diff_avg_10','fs_point_diff10_diff'),
            ('win_pct_last5_vs10','fs_win_pct_last5_vs10_diff'),
            ('point_diff_last5_vs10','fs_point_diff_last5_vs10_diff'),
            ('recent_strength_index_5','fs_recent_strength_index5_diff'),
        ]
        for base, diff in diff_specs:
            h = f'home_fs_{base}'
            a = f'away_fs_{base}'
            if h in train_df.columns and a in train_df.columns:
                train_df[diff] = train_df[h] - train_df[a]
        print("✓ Integrated feature store aggregates & diff features into tuning dataset")
    except Exception as exc:
        print(f"Feature store integration failed (tuner continues): {exc}")
    return train_df

def train_weighted_model(quick: bool = False):
    """Train model with time-weighted samples and tuned hyperparameters."""
    
    print("="*80)
    print("WEEKLY MODEL TUNING - TIME-WEIGHTED TRAINING")
    print("="*80)
    print()
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    historical_path = os.path.join(data_dir, 'Completed_Games.csv')
    normalized_path = os.path.join(data_dir, 'Completed_Games_Normalized.csv')
    
    # Load data
    print("Loading training data...")
    source_path = normalized_path if os.path.exists(normalized_path) else historical_path
    df = pd.read_csv(source_path)
    if source_path == normalized_path:
        print(f"✓ Using normalized training data: {normalized_path}")
    else:
        print("Using raw training data (normalized file not found).")
    df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
    # Integrate feature store aggregates early (before encoding)
    df = _integrate_feature_store(df)
    
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
    # Append FS diff features if present
    fs_diff_cols = [c for c in df.columns if c.startswith('fs_') and c.endswith('_diff')]
    if fs_diff_cols:
        feature_cols.extend(fs_diff_cols)
        print(f"Added FS diff features: {fs_diff_cols}")
    X = df[feature_cols]
    y = df['home_win']
    
    print(f"✓ Features: {feature_cols}")
    
    # Tune hyperparameters
    print()
    best_params = tune_hyperparameters(X, y, sample_weights, quick=quick)
    if best_params is None:
        best_params = {'n_estimators': 150, 'max_depth': 22, 'min_samples_split': 12}
    # Capture CV score for metadata (from tune_hyperparameters return path we stored best_score locally only; recompute quickly)
    # Simple re-evaluation using a lightweight hold-out to approximate CV score
    approx_cv_model = RandomForestClassifier(
        random_state=42,
        n_jobs=-1,
        n_estimators=best_params['n_estimators'],
        max_depth=best_params['max_depth'],
        min_samples_split=best_params['min_samples_split']
    )
    # Use a simple 80/20 split for approximation when computing metadata
    from sklearn.model_selection import train_test_split
    X_tmp_train, X_tmp_test, y_tmp_train, y_tmp_test, w_tmp_train, w_tmp_test = train_test_split(
        X, y, sample_weights, test_size=0.2, random_state=7
    )
    approx_cv_model.fit(X_tmp_train, y_tmp_train, sample_weight=w_tmp_train)
    approx_cv_score = approx_cv_model.score(X_tmp_test, y_tmp_test)
    
    # Train final model with best parameters and sample weights
    print("\nTraining final weighted model...")
    if best_params is None:
        print("No best_params selected (all scores -inf?). Falling back to defaults.")
        best_params = {'n_estimators': 150, 'max_depth': 20, 'min_samples_split': 10}
    final_model = RandomForestClassifier(
        random_state=42,
        n_jobs=-1,
        n_estimators=best_params['n_estimators'],
        max_depth=best_params['max_depth'],
        min_samples_split=best_params['min_samples_split']
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
        },
        'config_version': _config_version,
        'commit_hash': _commit_hash,
        'fs_diff_feature_count': len(fs_diff_cols)
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

    # ------------------------------------------------------------------
    # Auto-update model_params.json with best params + metadata
    # ------------------------------------------------------------------
    params_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'model_params.json')
    try:
        # Load existing params if present
        if os.path.exists(params_path):
            with open(params_path, 'r') as f:
                existing = json.load(f)
        else:
            existing = {}
        simple_cfg = existing.get('simple_predictor', {})
        # Update hyperparameters (force sample weighting flag on for current-season emphasis)
        simple_cfg.update({
            'n_estimators': best_params['n_estimators'],
            'max_depth': best_params['max_depth'],
            'min_samples_split': best_params['min_samples_split'],
            'use_sample_weights': True
        })
        # Preserve other keys (e.g., calibrate, min_games_threshold, use_sample_weights)
        existing['simple_predictor'] = simple_cfg
        meta = existing.get('metadata', {})
        meta.update({
            'last_tuned': tuning_results['date'],
            'tuned_by': 'tune_model.py',
            'tuner_commit': _commit_hash,
            'source': 'auto-tuner',
            'cv_score': approx_cv_score,
            'weighted_accuracy': overall_accuracy,
            'weighting_scheme': 'current=10x prev=3x prev2=1.5x older geometric 0.5^(i-2)'
        })
        existing['metadata'] = meta
        with open(params_path, 'w') as f:
            json.dump(existing, f, indent=2)
        print(f"✓ Updated model hyperparameters in {params_path}")
    except Exception as exc:
        print(f"⚠️ Failed to update model_params.json: {exc}")
    
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
    quick_flag = '--quick' in sys.argv
    train_weighted_model(quick=quick_flag)
