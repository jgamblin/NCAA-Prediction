#!/usr/bin/env python3
"""
CatBoost Hyperparameter Tuning for NCAA Predictions

Steps:
  1. Load historical completed games
  2. Prepare data (same logic as simple predictor)
  3. Build rolling team features (win rates, point diff, rest days)
  4. Apply time-weighted sample weights
  5. Split into chronological training/validation (latest chunk as holdout)
  6. Iteratively train CatBoost with parameter grid + early stopping
  7. Track metrics: accuracy, logloss, ROC AUC, Brier score
  8. Select best params and optionally calibrate probabilities
  9. Save artifacts and update tuning log JSON

Run:
  python model_training/tune_catboost.py --holdout-fraction 0.1 --early-stop 50 --max-iters 1500
"""

import os
import sys
import json
import argparse
import hashlib
import pandas as pd
import numpy as np
from typing import Dict, Any
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score, brier_score_loss
from sklearn.model_selection import TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder

try:
    from catboost import CatBoostClassifier, Pool
except Exception as e:
    raise ImportError(f"CatBoost must be installed to run tuning: {e}")

# ----------------------------------------------------------------------------
# Utilities (copied/consistent with existing project functions)
# ----------------------------------------------------------------------------

def calculate_sample_weights(df, current_season='2025-26', decay_factor=0.5):
    weights = np.ones(len(df))
    seasons = sorted(df['season'].unique(), reverse=True)
    season_weights = {}
    for i, season in enumerate(seasons):
        if season == current_season:
            season_weights[season] = 10.0
        elif i == 1:
            season_weights[season] = 3.0
        elif i == 2:
            season_weights[season] = 1.5
        else:
            season_weights[season] = decay_factor ** (i - 2)
    for season, w in season_weights.items():
        weights[df['season'] == season] = w
    if current_season in df['season'].values:
        mask = df['season'] == current_season
        current_df = df[mask]
        if len(current_df) > 0:
            dates = pd.to_datetime(current_df['game_day'])
            days_since_start = (dates - dates.min()).dt.days
            max_days = days_since_start.max()
            if max_days > 0:
                recency_multiplier = 1.0 + (days_since_start / max_days)
                weights[mask] *= recency_multiplier
    return weights


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if 'home_score' in df.columns and 'away_score' in df.columns:
        df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
    df['is_neutral'] = df.get('is_neutral', 0)
    df['is_neutral'] = df['is_neutral'].fillna(0).astype(int)
    df['home_rank'] = df.get('home_rank', 99)
    df['home_rank'] = df['home_rank'].fillna(99).astype(int)
    df['away_rank'] = df.get('away_rank', 99)
    df['away_rank'] = df['away_rank'].fillna(99).astype(int)
    return df

# ----------------------------------------------------------------------------
# Feature Engineering: Rolling Team Stats
# ----------------------------------------------------------------------------

def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values('game_day').copy()
    # Ensure datetime type
    df['game_day'] = pd.to_datetime(df['game_day'])

    # Build per-team historical performance before each game (no leakage)
    # We'll construct a long format and pivot back.
    records = []
    # Use index iteration for clarity; optimize later if needed
    for idx, row in df.iterrows():
        game_date = row['game_day']
        home = row['home_team']
        away = row['away_team']
        # Subsets before this game
        hist_home = df[(df['home_team'] == home) | (df['away_team'] == home)]
        hist_home = hist_home[hist_home['game_day'] < game_date]
        hist_away = df[(df['home_team'] == away) | (df['away_team'] == away)]
        hist_away = hist_away[hist_away['game_day'] < game_date]

        def team_stats(hist: pd.DataFrame, team: str) -> Dict[str, Any]:
            if len(hist) == 0:
                return {
                    'games_played': 0,
                    'win_rate_last5': 0.5,
                    'win_rate_last10': 0.5,
                    'season_win_rate': 0.5,
                    'avg_point_diff_last5': 0.0,
                    'avg_point_diff_last10': 0.0,
                    'rest_days': 7,  # neutral default
                    'neutral_ratio_last10': 0.0
                }
            # Determine wins from perspective of team
            home_mask = hist['home_team'] == team
            away_mask = hist['away_team'] == team
            wins = ((hist['home_score'] > hist['away_score']) & home_mask) | ((hist['away_score'] > hist['home_score']) & away_mask)
            diffs = np.where(home_mask, hist['home_score'] - hist['away_score'], hist['away_score'] - hist['home_score'])
            hist_sorted = hist.sort_values('game_day')
            last5 = hist_sorted.tail(5)
            last10 = hist_sorted.tail(10)
            wins_last5 = (((last5['home_score'] > last5['away_score']) & (last5['home_team'] == team)) | ((last5['away_score'] > last5['home_score']) & (last5['away_team'] == team))).mean() if len(last5) > 0 else 0.5
            wins_last10 = (((last10['home_score'] > last10['away_score']) & (last10['home_team'] == team)) | ((last10['away_score'] > last10['home_score']) & (last10['away_team'] == team))).mean() if len(last10) > 0 else 0.5
            point_diff_last5 = np.where((last5['home_team'] == team), last5['home_score'] - last5['away_score'], last5['away_score'] - last5['home_score']).mean() if len(last5) > 0 else 0.0
            point_diff_last10 = np.where((last10['home_team'] == team), last10['home_score'] - last10['away_score'], last10['away_score'] - last10['home_score']).mean() if len(last10) > 0 else 0.0
            season_mask = hist['season'] == row['season']
            season_hist = hist[season_mask]
            season_win_rate = wins[season_mask].mean() if len(season_hist) > 0 else 0.5
            last_game_date = hist_sorted['game_day'].max()
            rest_days = (row['game_day'] - last_game_date).days if pd.notnull(last_game_date) else 7
            neutral_ratio_last10 = (last10['is_neutral'].mean()) if len(last10) > 0 else 0.0
            return {
                'games_played': int(len(hist)),
                'win_rate_last5': float(wins_last5),
                'win_rate_last10': float(wins_last10),
                'season_win_rate': float(season_win_rate if not np.isnan(season_win_rate) else 0.5),
                'avg_point_diff_last5': float(point_diff_last5),
                'avg_point_diff_last10': float(point_diff_last10),
                'rest_days': int(rest_days),
                'neutral_ratio_last10': float(neutral_ratio_last10)
            }

        home_stats = team_stats(hist_home, home)
        away_stats = team_stats(hist_away, away)
        rec = {
            'index': idx,
            **{f'home_{k}': v for k, v in home_stats.items()},
            **{f'away_{k}': v for k, v in away_stats.items()}
        }
        records.append(rec)

    feat_df = pd.DataFrame(records).set_index('index')
    df = df.join(feat_df, how='left')
    # Rank diff feature (already numeric ranks filled)
    df['rank_diff'] = df['home_rank'] - df['away_rank']
    return df

# ----------------------------------------------------------------------------
# Parameter Grid
# ----------------------------------------------------------------------------

PARAM_GRID = [
    {'depth': 6, 'learning_rate': 0.08, 'l2_leaf_reg': 5, 'iterations': 1000},
    {'depth': 8, 'learning_rate': 0.05, 'l2_leaf_reg': 8, 'iterations': 1200},
    {'depth': 8, 'learning_rate': 0.03, 'l2_leaf_reg': 10, 'iterations': 1500},
    {'depth': 10, 'learning_rate': 0.04, 'l2_leaf_reg': 12, 'iterations': 1500},
    {'depth': 7, 'learning_rate': 0.06, 'l2_leaf_reg': 6, 'iterations': 1300},
]

# ----------------------------------------------------------------------------
# Tuning Routine
# ----------------------------------------------------------------------------

def tune_catboost(df: pd.DataFrame, holdout_fraction: float, early_stop: int, max_iters: int, calibrate: bool):
    df = prepare_data(df)
    df = add_rolling_features(df)

    # Separate holdout (latest chronological fraction)
    df = df.sort_values('game_day')
    holdout_size = int(len(df) * holdout_fraction)
    holdout_df = df.tail(holdout_size)
    train_df = df.head(len(df) - holdout_size)

    # Encode teams for baseline numeric features *and* keep raw for CatBoost native
    team_encoder = LabelEncoder()
    all_teams = pd.concat([train_df['home_team'], train_df['away_team']]).unique()
    team_encoder.fit(all_teams)
    home_map = {team: i for i, team in enumerate(team_encoder.classes_)}
    for d in [train_df, holdout_df]:
        d['home_team_encoded'] = d['home_team'].map(home_map).fillna(-1).astype(int)
        d['away_team_encoded'] = d['away_team'].map(home_map).fillna(-1).astype(int)

    feature_cols = [
        'home_team_encoded','away_team_encoded','is_neutral','home_rank','away_rank','rank_diff',
        'home_win_rate_last5','home_win_rate_last10','home_season_win_rate','home_avg_point_diff_last5',
        'home_avg_point_diff_last10','home_rest_days','home_neutral_ratio_last10',
        'away_win_rate_last5','away_win_rate_last10','away_season_win_rate','away_avg_point_diff_last5',
        'away_avg_point_diff_last10','away_rest_days','away_neutral_ratio_last10'
    ]
    # Some columns may have slightly different names due to prefixing; fix mapping
    rename_map = {
        'home_season_win_rate':'home_season_win_rate',
        'away_season_win_rate':'away_season_win_rate'
    }
    # Ensure columns exist (fill missing engineered ones if absent)
    for col in feature_cols:
        if col not in train_df.columns:
            train_df[col] = 0
        if col not in holdout_df.columns:
            holdout_df[col] = 0

    X_train = train_df[feature_cols]
    y_train = train_df['home_win']
    X_holdout = holdout_df[feature_cols]
    y_holdout = holdout_df['home_win']

    weights_train = calculate_sample_weights(train_df)

    results = []
    best_score = -np.inf
    best_model = None
    best_params = None

    for params in PARAM_GRID:
        local_params = params.copy()
        local_params['random_state'] = 42
        local_params['verbose'] = 0
        local_params['loss_function'] = 'Logloss'
        # Cap iterations by user max
        if local_params['iterations'] > max_iters:
            local_params['iterations'] = max_iters

        model = CatBoostClassifier(**local_params)
        # Create Pool for proper handling of weights
        train_pool = Pool(X_train, y_train, weight=weights_train)
        model.fit(train_pool, use_best_model=True, early_stopping_rounds=early_stop)

        # Evaluate on holdout
        holdout_proba = model.predict_proba(X_holdout)[:,1]
        holdout_pred = (holdout_proba >= 0.5).astype(int)
        acc = accuracy_score(y_holdout, holdout_pred)
        ll = log_loss(y_holdout, holdout_proba)
        auc = roc_auc_score(y_holdout, holdout_proba)
        brier = brier_score_loss(y_holdout, holdout_proba)
        score = auc  # selection criterion

        results.append({
            'params': params,
            'accuracy': acc,
            'logloss': ll,
            'roc_auc': auc,
            'brier': brier,
            'iterations_used': model.get_best_iteration() or params['iterations']
        })

        if score > best_score:
            best_score = score
            best_model = model
            best_params = params

        print(f"Tried {params} -> AUC={auc:.4f} ACC={acc:.4f} LOGLOSS={ll:.4f} BRIER={brier:.4f}")

    results_df = pd.DataFrame(results)
    print("\nTuning Summary (sorted by roc_auc):")
    print(results_df.sort_values('roc_auc', ascending=False).to_string(index=False))

    calibrated_model = None
    calibration_metrics = None

    if calibrate and best_model is not None:
        print("\nCalibrating best model (isotonic & sigmoid)...")
        # Use TimeSeriesSplit on training set for calibration
        tscv = TimeSeriesSplit(n_splits=5)
        proba_oof = np.zeros(len(X_train))
        for fold, (tr_idx, val_idx) in enumerate(tscv.split(X_train)):
            if not isinstance(best_params, dict):
                raise ValueError("best_params unexpectedly None during calibration phase")
            fold_params = {k: v for k, v in best_params.items()}  # type: ignore
            fold_params['random_state'] = 42
            fold_params['verbose'] = 0
            fold_model = CatBoostClassifier(**fold_params)  # type: ignore
            fold_pool = Pool(X_train.iloc[tr_idx], y_train.iloc[tr_idx], weight=weights_train[tr_idx])
            fold_model.fit(fold_pool, use_best_model=True, early_stopping_rounds=early_stop)
            proba_oof[val_idx] = fold_model.predict_proba(X_train.iloc[val_idx])[:,1]
        # Calibration frameworks
        iso = CalibratedClassifierCV(best_model, cv='prefit', method='isotonic')
        sig = CalibratedClassifierCV(best_model, cv='prefit', method='sigmoid')
        iso.fit(X_train, y_train)
        sig.fit(X_train, y_train)
        iso_proba = iso.predict_proba(X_holdout)[:,1]
        sig_proba = sig.predict_proba(X_holdout)[:,1]
        calibration_metrics = {
            'isotonic_logloss': log_loss(y_holdout, iso_proba),
            'sigmoid_logloss': log_loss(y_holdout, sig_proba),
            'isotonic_brier': brier_score_loss(y_holdout, iso_proba),
            'sigmoid_brier': brier_score_loss(y_holdout, sig_proba)
        }
        # Pick better (logloss priority then brier)
        if calibration_metrics['isotonic_logloss'] <= calibration_metrics['sigmoid_logloss']:
            calibrated_model = iso
            chosen = 'isotonic'
        else:
            calibrated_model = sig
            chosen = 'sigmoid'
        print(f"Chosen calibration: {chosen} -> logloss={calibration_metrics[chosen+'_logloss']:.4f}")

    # Persist artifacts
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(out_dir, exist_ok=True)

    artifacts = {
        'best_params': best_params,
        'best_auc': float(best_score),
        'tuning_results': results,
        'calibration_metrics': calibration_metrics,
        'feature_cols': feature_cols,
        'hash': hashlib.sha256(str(best_params).encode()).hexdigest() if best_params else None,
        'python_version': sys.version,
    }

    with open(os.path.join(out_dir, 'CatBoost_Tuning_Log.json'), 'a') as f:
        f.write(json.dumps(artifacts) + '\n')

    # Save model (CatBoost supports native save)
    if best_model:
        best_model.save_model(os.path.join(out_dir, 'catboost_best_model.cbm'))
    if calibrated_model:
        import joblib
        joblib.dump(calibrated_model, os.path.join(out_dir, 'catboost_calibrated.pkl'))

    print("\nBest Params:", best_params)
    print("Artifacts saved in data/ directory.")

    return artifacts

# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description='Tune CatBoost for NCAA predictions')
    p.add_argument('--holdout-fraction', type=float, default=0.1, help='Fraction of data reserved for final holdout evaluation.')
    p.add_argument('--early-stop', type=int, default=75, help='Early stopping rounds.')
    p.add_argument('--max-iters', type=int, default=1500, help='Upper cap on iterations.')
    p.add_argument('--calibrate', action='store_true', help='Whether to perform probability calibration.')
    return p.parse_args()

def main():
    args = parse_args()
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    path = os.path.join(data_dir, 'Completed_Games.csv')
    if not os.path.exists(path):
        raise FileNotFoundError(f'Missing data file: {path}')
    df = pd.read_csv(path)
    artifacts = tune_catboost(df, holdout_fraction=args.holdout_fraction, early_stop=args.early_stop, max_iters=args.max_iters, calibrate=args.calibrate)

if __name__ == '__main__':
    main()
