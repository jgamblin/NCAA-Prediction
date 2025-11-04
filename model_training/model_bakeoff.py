#!/usr/bin/env python3
"""
Model Bakeoff: Compare multiple classifiers (CPU-only) on historical NCAA game data.

This script:
  * Loads historical completed games
  * Prepares features mirroring logic from simple_predictor.py
  * Applies time-weighted sample weighting (exact function from tune_model.py)
  * Evaluates models with TimeSeriesSplit to respect temporal order
  * Tests CatBoost both with encoded numeric features and native categorical handling
  * Reports mean metrics (accuracy, logloss, roc_auc) across folds

Usage:
  python model_training/model_bakeoff.py

Requirements:
  pandas, numpy, scikit-learn, tabulate, lightgbm, xgboost, catboost
"""

import os
import warnings
import argparse
import pandas as pd
import numpy as np
from tabulate import tabulate
from typing import Dict, Any

# Sklearn imports
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score, brier_score_loss, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression

# External gradient boosting libraries
"""Imports for gradient boosting models with graceful fallbacks so the script
can run even if a library (e.g. LightGBM) isn't properly compiled on the host.
"""
LIGHTGBM_AVAILABLE = True
XGBOOST_AVAILABLE = True
CATBOOST_AVAILABLE = True

# Predeclare names to avoid "possibly unbound" warnings for type checkers
LGBMClassifier = None  # type: ignore
XGBClassifier = None  # type: ignore
CatBoostClassifier = None  # type: ignore

try:  # LightGBM often fails on macOS if libomp is missing
    from lightgbm import LGBMClassifier  # type: ignore
except Exception as _e:  # broad to catch OSError from missing libomp
    print(f"[WARN] LightGBM unavailable: {_e}\n       -> brew install libomp && pip install --force-reinstall lightgbm")
    LIGHTGBM_AVAILABLE = False

try:
    from xgboost import XGBClassifier  # type: ignore
except Exception as _e:
    print(f"[WARN] XGBoost unavailable: {_e}\n       -> pip install xgboost (or conda install -c conda-forge xgboost)")
    XGBOOST_AVAILABLE = False

try:
    from catboost import CatBoostClassifier  # type: ignore
except Exception as _e:
    print(f"[WARN] CatBoost unavailable: {_e}\n       -> pip install catboost (or conda install -c conda-forge catboost)")
    CATBOOST_AVAILABLE = False

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

################################################################################
# Time-weighted sample weighting (EXACT COPY from tune_model.py)
################################################################################

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

################################################################################
# Data preparation (mirrors SimplePredictor.prepare_data logic)
################################################################################

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Replicate prepare_data from simple_predictor.py (adds home_win + fills NaNs)."""
    df = df.copy()

    # Add home_win if scores exist
    if 'home_score' in df.columns and 'away_score' in df.columns:
        df['home_win'] = (df['home_score'] > df['away_score']).astype(int)

    # Fill missing values (establish columns if absent)
    if 'is_neutral' in df.columns:
        df['is_neutral'] = df['is_neutral'].fillna(0).astype(int)
    else:
        df['is_neutral'] = 0

    if 'home_rank' in df.columns:
        df['home_rank'] = df['home_rank'].fillna(99).astype(int)
    else:
        df['home_rank'] = 99

    if 'away_rank' in df.columns:
        df['away_rank'] = df['away_rank'].fillna(99).astype(int)
    else:
        df['away_rank'] = 99

    return df

################################################################################
# Model definitions
################################################################################

def build_models(n_jobs: int):
    """Build dictionary of models honoring requested parallelism."""
    models_to_test: Dict[str, Any] = {
        'RandomForest': RandomForestClassifier(
            n_estimators=100, max_depth=20, min_samples_split=10,
            random_state=42, n_jobs=n_jobs
        )
    }

    # Conditionally add boosting models
    if LIGHTGBM_AVAILABLE and LGBMClassifier is not None:  # type: ignore
        models_to_test['LightGBM'] = LGBMClassifier(random_state=42, n_jobs=n_jobs)  # type: ignore
    if XGBOOST_AVAILABLE and XGBClassifier is not None:  # type: ignore
        models_to_test['XGBoost'] = XGBClassifier(
            random_state=42, n_jobs=n_jobs, eval_metric='logloss', use_label_encoder=False
        )  # type: ignore
    if CATBOOST_AVAILABLE and CatBoostClassifier is not None:  # type: ignore
        # CatBoost uses its own thread pool; setting thread_count if n_jobs provided
        models_to_test['CatBoost'] = CatBoostClassifier(
            random_state=42, verbose=0, thread_count=n_jobs
        )  # type: ignore

    # Build stacking only with available base estimators (excluding CatBoost per original design)
    base_estimators = []
    if 'RandomForest' in models_to_test:
        base_estimators.append(('rf', models_to_test['RandomForest']))
    if 'LightGBM' in models_to_test:
        base_estimators.append(('lgbm', models_to_test['LightGBM']))
    if 'XGBoost' in models_to_test:
        base_estimators.append(('xgb', models_to_test['XGBoost']))

    if len(base_estimators) >= 2:  # Need at least 2 for meaningful stacking
        models_to_test['Stacking'] = StackingClassifier(
            estimators=base_estimators,
            final_estimator=LogisticRegression(),
            cv=5,
            n_jobs=n_jobs
        )
    else:
        print("[INFO] Skipping StackingClassifier (need >=2 base models).")

    return models_to_test

################################################################################
# Evaluation logic
################################################################################

def evaluate_models(df: pd.DataFrame, n_jobs: int):
    # Prepare data
    df = prepare_data(df)
    feature_cols = ['home_team_encoded', 'away_team_encoded', 'is_neutral', 'home_rank', 'away_rank']
    tscv = TimeSeriesSplit(n_splits=5)
    models_to_test = build_models(n_jobs=n_jobs)
    results = []
    error_rows = []  # collect misclassifications for best model later (populate for all then filter)

    # Precompute global sample weights for error analysis referencing
    global_weights = calculate_sample_weights(df)

    for name, model in models_to_test.items():
        fold_num = 0
        # We must build indices on original df since we encode per fold
        for train_index, test_index in tscv.split(df):
            fold_num += 1
            train_df = df.iloc[train_index].copy()
            test_df = df.iloc[test_index].copy()

            # Per-fold team encoder to avoid leakage
            # Per-fold encoding without leakage using mapping
            teams_in_fold = pd.concat([train_df['home_team'], train_df['away_team']]).unique()
            team_mapping = {team: idx for idx, team in enumerate(teams_in_fold)}
            train_df['home_team_encoded'] = train_df['home_team'].map(team_mapping).astype(int)
            train_df['away_team_encoded'] = train_df['away_team'].map(team_mapping).astype(int)
            test_df['home_team_encoded'] = test_df['home_team'].map(team_mapping).fillna(-1).astype(int)
            test_df['away_team_encoded'] = test_df['away_team'].map(team_mapping).fillna(-1).astype(int)

            X_train = train_df[feature_cols]
            y_train = train_df['home_win']
            X_test = test_df[feature_cols]
            y_test = test_df['home_win']

            weights_train = calculate_sample_weights(train_df)

            if name == 'Stacking':
                model.fit(X_train, y_train)
            else:
                try:
                    model.fit(X_train, y_train, sample_weight=weights_train)
                except TypeError:
                    model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]

            accuracy = accuracy_score(y_test, y_pred)
            logloss = log_loss(y_test, y_pred_proba)
            roc_auc = roc_auc_score(y_test, y_pred_proba)
            brier = brier_score_loss(y_test, y_pred_proba)
            tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

            results.append({
                'model': name,
                'fold': fold_num,
                'accuracy': accuracy,
                'logloss': logloss,
                'roc_auc': roc_auc,
                'brier': brier,
                'tp': tp,
                'tn': tn,
                'fp': fp,
                'fn': fn
            })

            # Collect error rows (store for all models, filter later to chosen best)
            mis_mask = y_pred != y_test
            if mis_mask.any():
                mis_df = test_df[mis_mask].copy()
                mis_df['pred_proba'] = y_pred_proba[mis_mask]
                mis_df['pred_label'] = y_pred[mis_mask]
                mis_df['true_label'] = y_test[mis_mask]
                mis_df['sample_weight'] = global_weights[test_index][mis_mask]
                mis_df['model'] = name
                mis_df['fold'] = fold_num
                error_rows.append(mis_df)

    if CATBOOST_AVAILABLE:
        results, native_errors = evaluate_catboost_native(df, tscv, results)
        error_rows.extend(native_errors)
    else:
        print("[INFO] Skipping CatBoost (Native) evaluation; CatBoost not available.")

    # Concatenate error rows for external artifact generation
    if len(error_rows) > 0:
        errors_df = pd.concat(error_rows, ignore_index=True)
    else:
        errors_df = pd.DataFrame()

    return results, errors_df

################################################################################
# CatBoost native categorical evaluation
################################################################################

def evaluate_catboost_native(df: pd.DataFrame, tscv: TimeSeriesSplit, results):
    if not CATBOOST_AVAILABLE:
        return results  # Guard for static analyzers
    # Raw feature set with string categorical columns
    cat_features = ['home_team', 'away_team']
    raw_feature_cols = ['home_team', 'away_team', 'is_neutral', 'home_rank', 'away_rank']
    X_raw = df[raw_feature_cols]
    y = df['home_win']

    # Instantiate per instructions (note: cat_features usually passed to fit, kept here for spec compliance)
    native_model = CatBoostClassifier(random_state=42, verbose=0, cat_features=cat_features)  # type: ignore

    fold_num = 0
    error_rows = []
    global_weights = calculate_sample_weights(df)
    for train_index, test_index in tscv.split(X_raw):
        fold_num += 1
        X_train, X_test = X_raw.iloc[train_index], X_raw.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        train_df = df.iloc[train_index]
        weights_train = calculate_sample_weights(train_df)

        try:
            native_model.fit(X_train, y_train, sample_weight=weights_train)
        except TypeError:
            # If sample_weight not accepted in this context
            native_model.fit(X_train, y_train)

        y_pred = native_model.predict(X_test)
        y_pred_proba = native_model.predict_proba(X_test)[:, 1]

        accuracy = accuracy_score(y_test, y_pred)
        logloss = log_loss(y_test, y_pred_proba)
        roc_auc = roc_auc_score(y_test, y_pred_proba)
        brier = brier_score_loss(y_test, y_pred_proba)
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

        results.append({
            'model': 'CatBoost (Native)',
            'fold': fold_num,
            'accuracy': accuracy,
            'logloss': logloss,
            'roc_auc': roc_auc,
            'brier': brier,
            'tp': tp,
            'tn': tn,
            'fp': fp,
            'fn': fn
        })

        mis_mask = y_pred != y_test
        if mis_mask.any():
            orig_subset = df.iloc[test_index][mis_mask].copy()
            mis_df = orig_subset[['home_team','away_team','game_day','season']].copy()
            mis_df['pred_proba'] = y_pred_proba[mis_mask]
            mis_df['pred_label'] = y_pred[mis_mask]
            mis_df['true_label'] = y_test[mis_mask]
            mis_df['sample_weight'] = global_weights[test_index][mis_mask]
            mis_df['model'] = 'CatBoost (Native)'
            mis_df['fold'] = fold_num
            error_rows.append(mis_df)

    return results, error_rows

################################################################################
# Aggregation and reporting
################################################################################

def summarize_and_print(results, export_dir=None):
    df_results = pd.DataFrame(results)
    agg = {
        'accuracy': 'mean',
        'logloss': 'mean',
        'roc_auc': 'mean',
        'brier': 'mean'
    }
    # Sum confusion components to get totals across folds
    for c in ['tp','tn','fp','fn']:
        if c in df_results.columns:
            agg[c] = 'sum'
    summary = df_results.groupby('model').agg(agg).sort_values('roc_auc', ascending=False)

    print("\nModel Performance (mean across folds):")
    summary_reset = summary.reset_index()
    print(tabulate(summary_reset.values, headers=list(summary_reset.columns), tablefmt='pipe', floatfmt='.4f'))

    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        per_fold_path = os.path.join(export_dir, 'Model_Bakeoff_Results.csv')
        df_results.to_csv(per_fold_path, index=False)
        md_path = os.path.join(export_dir, 'MODEL_BAKEOFF_RESULTS.md')
        with open(md_path, 'w') as f:
            f.write('# Model Bakeoff Results\n\n')
            f.write('## Aggregated Metrics (mean across folds)\n\n')
            f.write(tabulate(summary_reset.values, headers=list(summary_reset.columns), tablefmt='pipe', floatfmt='.4f'))
            f.write('\n\n## Fold-Level Metrics\n\n')
            f.write(tabulate(df_results.sort_values(['model','fold']).values, headers=list(df_results.columns), tablefmt='pipe', floatfmt='.4f'))
        print(f"[INFO] Exported results to {per_fold_path} and {md_path}")

        # Append registry log
        registry_path = os.path.join(export_dir, 'Model_Bakeoff_Log.json')
        import sys
        entry = {
            'timestamp': pd.Timestamp.utcnow().isoformat(),
            'summary': summary_reset.to_dict(orient='records'),
            'folds': int(df_results['fold'].nunique()),
            'python_version': sys.version,
            'total_rows': int(len(df_results))
        }
        try:
            import json
            if os.path.exists(registry_path):
                with open(registry_path,'r') as rf:
                    existing = json.load(rf)
                if not isinstance(existing, list):
                    existing = [existing]
                existing.append(entry)
            else:
                existing = [entry]
            with open(registry_path,'w') as wf:
                json.dump(existing, wf, indent=2)
            print(f"[INFO] Updated registry log at {registry_path}")
        except Exception as e:
            print(f"[WARN] Failed to update registry log: {e}")

    return summary

################################################################################
# Main entry point
################################################################################

def parse_args():
    parser = argparse.ArgumentParser(description="Model bakeoff for NCAA predictions")
    parser.add_argument("--n-jobs", type=int, default=1,
                        help="Parallel jobs for supported models (set >1 to use multiprocessing; default 1 reduces resource_tracker errors on macOS Python 3.13)")
    return parser.parse_args()

def main():
    args = parse_args()
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    data_path = os.path.join(data_dir, 'Completed_Games.csv')

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Expected data file not found: {data_path}")

    print("Loading historical game data...")
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} completed games spanning seasons: {sorted(df['season'].unique())}")

    # Ensure required columns exist
    required_cols = ['home_team', 'away_team', 'home_score', 'away_score', 'season', 'game_day']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for weighting/evaluation: {missing}")

    print("Evaluating models with time-series cross-validation...")
    results, errors_df = evaluate_models(df, n_jobs=args.n_jobs)
    summary = summarize_and_print(results, export_dir=data_dir)

    # Build error analysis artifact for top model (highest roc_auc in summary)
    if not errors_df.empty and len(summary.index) > 0:
        best_model_name: str = str(summary.index[0])
        best_errors = errors_df[errors_df['model'] == best_model_name].copy()
        if not best_errors.empty:
            err_path = os.path.join(data_dir, 'Error_Analysis.csv')
            best_errors.to_csv(err_path, index=False)
            md_path = os.path.join(data_dir, 'ERROR_ANALYSIS.md')
            with open(md_path, 'w') as f:
                f.write('# Error Analysis\n\n')
                f.write(f'Best Model: **{best_model_name}**\n\n')
                f.write(f'Total Misclassifications: {len(best_errors)}\n\n')
                f.write('## Sample (first 25)\n\n')
                sample = best_errors.head(25)
                f.write(tabulate(sample.values, headers=list(sample.columns), tablefmt='pipe', floatfmt='.4f'))
            print(f"[INFO] Saved error analysis for {best_model_name} to {err_path} and {md_path}")

if __name__ == '__main__':
    main()
