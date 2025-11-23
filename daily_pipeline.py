#!/usr/bin/env python3
"""
Daily NCAA Basketball Prediction Pipeline
Run this script daily to:
1. Scrape completed and upcoming games from ESPN
2. Merge completed games into training data
3. Generate predictions for upcoming games
4. Track accuracy of previous predictions
"""

import sys
import os
import pandas as pd
import subprocess  # type: ignore  # dynamic import resolution in runtime env
from datetime import datetime, timedelta
from pathlib import Path
try:
    from config.load_config import get_config, get_config_version
    _cfg = get_config()
    _config_version = get_config_version()
    # Commit hash lineage
    from config.versioning import get_commit_hash
    _commit_hash = get_commit_hash()
except Exception:
    _cfg = {}
    _config_version = 'unknown'
    _commit_hash = 'unknown'

# Add directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data_collection'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'game_prediction'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'model_training'))

def main():
    """Run the daily prediction pipeline."""
    
    print("="*80)
    print("NCAA BASKETBALL DAILY PREDICTION PIPELINE")
    print(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    row_guard_pct = float(_cfg.get('row_inflation_guard_pct', 0.10))
    drift_window = int(_cfg.get('team_drift_window', 25))
    refresh_ids_flag = ('--refresh-ids' in sys.argv) or bool(os.environ.get('REFRESH_ID_LOOKUP')) or bool(_cfg.get('id_refresh_enabled_default', False))
    if refresh_ids_flag:
        print("\nCONFIG: ID refresh enabled for this run.")
    # Local alias to satisfy static analysis on subprocess usage
    sp_run = subprocess.run  # type: ignore[attr-defined]
    
    # Optional ID lookup refresh (behind flag)
    if refresh_ids_flag:
        print("\n" + "="*80)
        print("OPTIONAL: Refreshing cross-source ID lookup")
        print("-"*80)
        try:
            result = sp_run(['python3', 'data_collection/build_id_lookup.py'], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print("✓ ID lookup refresh complete")
            else:
                print(f"⚠️ ID lookup refresh failed: {result.stderr}")
        except Exception as exc:
            print(f"⚠️ ID lookup step skipped: {exc}")

    # =========================================================================
    # STEP 1: Scrape ESPN for recent games
    # =========================================================================
    print("STEP 1: Scraping ESPN for recent games")
    print("-"*80)
    
    from espn_scraper import ESPNScraper  # type: ignore
    
    scraper = ESPNScraper()
    
    # Get last 3 days to catch any games we missed, plus next 7 days for upcoming games
    start_date = datetime.now() - timedelta(days=3)
    end_date = datetime.now() + timedelta(days=7)
    
    print(f"Fetching games from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    games = scraper.get_season_games(start_date, end_date)
    
    if len(games) == 0:
        print("✗ No games found on ESPN")
        return
    
    df = pd.DataFrame(games)
    df = df.drop_duplicates(subset=['game_id'])
    
    print(f"✓ Collected {len(df)} unique games")
    print(f"  - Completed: {len(df[df['game_status'] == 'Final'])}")
    print(f"  - Scheduled: {len(df[df['game_status'] == 'Scheduled'])}")
    
    # =========================================================================
    # STEP 2: Merge completed games into training data
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 2: Merging completed games into training data")
    print("-"*80)
    
    completed = df[df['game_status'] == 'Final'].copy()
    upcoming = df[df['game_status'] == 'Scheduled'].copy()
    
    historical_path = os.path.join(data_dir, 'Completed_Games.csv')
    # Predeclare normalized path to avoid potential unbound warnings later
    normalized_hist_path = os.path.join(data_dir, 'Completed_Games_Normalized.csv')
    
    if os.path.exists(historical_path):
        historical_df = pd.read_csv(historical_path)
        print(f"✓ Loaded {len(historical_df)} historical games")
        
        if len(completed) > 0:
            # Merge and deduplicate
            merged_df = pd.concat([historical_df, completed], ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['game_id'], keep='last')
            
            new_games = len(merged_df) - len(historical_df)
            merged_df.to_csv(historical_path, index=False)
            
            print(f"✓ Merged: {len(merged_df)} total games")
            if new_games > 0:
                print(f"  Added {new_games} new completed games")
            else:
                print(f"  No new completed games to add")
        else:
            print("✓ No new completed games to merge")
    else:
        print("✗ Historical data file not found!")
        return
    
    # Inline normalization after merge (ensures modeling continuity)
    try:
        from data_collection.normalize_teams import team_name_mapping
        # Apply mapping to historical file for modeling (in-place copy with normalized columns)
        hist_df = pd.read_csv(historical_path)
        for col in ['home_team', 'away_team']:
            if col in hist_df.columns:
                hist_df[col] = hist_df[col].replace(team_name_mapping)
        hist_df.to_csv(normalized_hist_path, index=False)
        print(f"✓ Normalized historical games written: {normalized_hist_path}")
    except Exception as exc:
        print(f"⚠️ Normalization step failed (continuing): {exc}")

    # =========================================================================
    # STEP 2.5: Build / Update Per-Team Feature Store
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 2.5: Building per-team feature store (rolling performance)")
    print("-"*80)
    try:
        from model_training.feature_store import build_feature_store, save_feature_store, load_feature_store
        from model_training.team_id_utils import ensure_team_ids

        # Use normalized historical games if available, else raw
        hist_source_path = normalized_hist_path if os.path.exists(normalized_hist_path) else historical_path
        hist_for_features = pd.read_csv(hist_source_path)

        # Ensure required columns exist / fallback safe
        needed_cols = {'home_team','away_team','home_score','away_score','game_id'}
        if not needed_cols.issubset(set(hist_for_features.columns)):
            raise ValueError(f"Historical games missing columns for feature store: {needed_cols - set(hist_for_features.columns)}")

        # Filter to completed / final games if status column exists
        if 'game_status' in hist_for_features.columns:
            hist_for_features = hist_for_features[hist_for_features['game_status'] == 'Final']

        # Ensure season column (fallback to existing if already present)
        if 'season' not in hist_for_features.columns and 'Season' in hist_for_features.columns:
            hist_for_features['season'] = hist_for_features['Season']

        hist_for_features = ensure_team_ids(hist_for_features)
        feature_store_df = build_feature_store(hist_for_features)
        save_feature_store(feature_store_df)
        print(f"✓ Feature store rows: {len(feature_store_df)} (stored at data/feature_store/feature_store.csv)")

    except Exception as e:
        print(f"⚠️ Feature store build skipped: {e}")

    # Save upcoming games (also normalize team display names for consistency)
    if len(upcoming) > 0:
        upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
        try:
            from data_collection.normalize_teams import team_name_mapping
            for col in ['home_team', 'away_team']:
                if col in upcoming.columns:
                    upcoming[col] = upcoming[col].replace(team_name_mapping)
        except Exception as exc:
            print(f"⚠️ Failed to normalize upcoming games: {exc}")
        # Enrich upcoming games with feature store aggregates (season-aware, no cartesian)
        try:
            from model_training.feature_store import load_feature_store
            from model_training.team_id_utils import ensure_team_ids
            upcoming = ensure_team_ids(upcoming)
            fs_df = load_feature_store()
            if not fs_df.empty:
                # Reduce to one row per (season, team_id) keeping latest (highest games_played)
                fs_df_reduced = fs_df.sort_values(['season','team_id','games_played']).drop_duplicates(['season','team_id'], keep='last')
                fs_features = ['rolling_win_pct_5','rolling_win_pct_10','rolling_point_diff_avg_5','rolling_point_diff_avg_10','win_pct_last5_vs10','point_diff_last5_vs10','recent_strength_index_5']
                keep_cols = ['season','team_id'] + [c for c in fs_features if c in fs_df_reduced.columns]
                fs_df_reduced = fs_df_reduced[keep_cols]
                if 'season' not in upcoming.columns:
                    # If upcoming lacks season, attempt to infer most recent season from feature store; fallback: merge on team only
                    inferred_season = fs_df_reduced['season'].max()
                    upcoming['season'] = inferred_season
                # Home merge
                home_fs = fs_df_reduced.rename(columns={'team_id':'home_team_id'})
                home_fs = home_fs.add_prefix('home_fs_').rename(columns={'home_fs_home_team_id':'home_team_id','home_fs_season':'season'})
                upcoming = upcoming.merge(home_fs, on=['home_team_id','season'], how='left')
                # Away merge
                away_fs = fs_df_reduced.rename(columns={'team_id':'away_team_id'})
                away_fs = away_fs.add_prefix('away_fs_').rename(columns={'away_fs_away_team_id':'away_team_id','away_fs_season':'season'})
                upcoming = upcoming.merge(away_fs, on=['away_team_id','season'], how='left')
                print("✓ Added feature store columns to upcoming games (season-aware)")
        except Exception as exc:
            print(f"⚠️ Skipped feature store enrichment for upcoming games: {exc}")
        upcoming.to_csv(upcoming_path, index=False)
        print(f"✓ Saved {len(upcoming)} upcoming games for prediction")
        
        # Show today's games
        today = datetime.now().strftime('%Y-%m-%d')
        today_games = upcoming[upcoming['date'] == today]
        if len(today_games) > 0:
            print(f"\n  Today's games ({len(today_games)}):")
            for _, game in today_games.head(5).iterrows():
                print(f"    - {game['away_team']} @ {game['home_team']}")
            if len(today_games) > 5:
                print(f"    ... and {len(today_games) - 5} more")
    else:
        print("✓ No upcoming games found")
    
    # =========================================================================
    # STEP 3: Track accuracy of previous predictions
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 3: Tracking accuracy of previous predictions")
    print("-"*80)
    
    from track_accuracy import track_accuracy  # type: ignore
    track_accuracy()
    
    # =========================================================================
    # STEP 4: Generate predictions for upcoming games
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 4: Generating predictions for upcoming games")
    print("-"*80)
    
    if len(upcoming) > 0:
        print(f"Generating predictions for {len(upcoming)} upcoming games...")

        # Use adaptive prediction model
        from adaptive_predictor import AdaptivePredictor  # type: ignore
        from prediction_logger import append_predictions as log_predictions  # type: ignore
        import json
        
        # Load training data
        # Prefer normalized historical file if available
        normalized_hist_path = os.path.join(data_dir, 'Completed_Games_Normalized.csv')
        if os.path.exists(normalized_hist_path):
            train_df = pd.read_csv(normalized_hist_path)
            print(f"✓ Using normalized training data ({len(train_df)} rows)")
        else:
            train_df = pd.read_csv(historical_path)
            print(f"✓ Using raw training data ({len(train_df)} rows) - normalized file not found")
        
        # Train model and generate predictions
        # Load tuned hyperparameters if available
        from config.model_params_loader import load_model_params  # type: ignore
        model_cfg = load_model_params()
        sp_kwargs = {}
        adaptive_cfg = {}
        if model_cfg:
            adaptive_cfg = model_cfg.get('adaptive_predictor') or model_cfg.get('simple_predictor', {})
        model_version = ""
        if model_cfg:
            metadata = model_cfg.get('metadata', {})
            model_version = metadata.get('tuner_commit') or metadata.get('model_version', '') or ""
        for key in [
            'n_estimators',
            'max_depth',
            'min_samples_split',
            'min_games_threshold',
            'calibrate',
            'calibration_method',
            'home_court_logit_shift',
            'confidence_temperature',
        ]:
            if key in adaptive_cfg:
                sp_kwargs[key] = adaptive_cfg[key]
        if sp_kwargs:
            print(f"✓ Loaded tuned adaptive predictor params: {sp_kwargs}")
        else:
            print("⚠️ No tuned params found (using defaults)")
        predictor = AdaptivePredictor(**sp_kwargs)
        # Enrich training data with feature store stats similar to upcoming enrichment
        try:
            from model_training.feature_store import load_feature_store
            from model_training.team_id_utils import ensure_team_ids
            train_df = ensure_team_ids(train_df)
            raw_training_rows = len(train_df)
            fs_df = load_feature_store()
            if not fs_df.empty:
                # Reduce to one row per (season, team_id)
                fs_df_reduced = (
                    fs_df.sort_values(['season','team_id','games_played'])
                         .drop_duplicates(['season','team_id'], keep='last')
                )
                fs_features = [
                    'rolling_win_pct_5','rolling_win_pct_10',
                    'rolling_point_diff_avg_5','rolling_point_diff_avg_10',
                    'win_pct_last5_vs10','point_diff_last5_vs10','recent_strength_index_5'
                ]
                keep_cols = ['season','team_id'] + [c for c in fs_features if c in fs_df_reduced.columns]
                fs_df_reduced = fs_df_reduced[keep_cols]
                if 'season' not in train_df.columns and 'Season' in train_df.columns:
                    train_df['season'] = train_df['Season']
                if 'season' not in train_df.columns:
                    inferred_season = fs_df_reduced['season'].max()
                    train_df['season'] = inferred_season
                # Merge home side
                home_fs = fs_df_reduced.rename(columns={'team_id':'home_team_id'}).copy()
                for col in list(home_fs.columns):
                    if col not in ('home_team_id','season'):
                        home_fs.rename(columns={col: f'home_fs_{col}'}, inplace=True)
                train_df = train_df.merge(home_fs, on=['home_team_id','season'], how='left')
                # Merge away side
                away_fs = fs_df_reduced.rename(columns={'team_id':'away_team_id'})
                for col in list(away_fs.columns):
                    if col not in ('away_team_id','season'):
                        away_fs.rename(columns={col: f'away_fs_{col}'}, inplace=True)
                train_df = train_df.merge(away_fs, on=['away_team_id','season'], how='left')
                # Guard against unexpected inflation
                if len(train_df) > raw_training_rows * (1 + row_guard_pct):
                    print(f"⚠️ Row inflation detected after FS merge: {len(train_df)} vs {raw_training_rows}. De-duplicating by game_id.")
                    if 'game_id' in train_df.columns:
                        before = len(train_df)
                        train_df = train_df.drop_duplicates(subset=['game_id'])
                        print(f"  De-dup reduced rows to {len(train_df)} (was {before}).")
                    else:
                        print("  Cannot de-dup (no game_id). Proceeding anyway.")
                else:
                    print(f"✓ Added feature store columns to training data (rows {len(train_df)})")
        except Exception as exc:
            print(f"⚠️ Skipped feature store enrichment for training data: {exc}")
        # Optional sample weighting if enabled in config
        cfg_section = {}
        if model_cfg:
            cfg_section = model_cfg.get('adaptive_predictor') or model_cfg.get('simple_predictor', {})
        use_weights = bool(cfg_section.get('use_sample_weights', False)) if cfg_section else False
        if use_weights and 'season' in train_df.columns:
            print("✓ Sample weighting enabled: emphasizing current season performance")
            # Lightweight weight scheme: boost current season 10x, previous 3x, older decay
            seasons = sorted(train_df['season'].unique(), reverse=True)
            season_weight_map = {}
            for i, season in enumerate(seasons):
                if i == 0:
                    season_weight_map[season] = 10.0
                elif i == 1:
                    season_weight_map[season] = 3.0
                elif i == 2:
                    season_weight_map[season] = 1.5
                else:
                    season_weight_map[season] = 0.5 ** (i - 2)
            sample_weights = train_df['season'].map(season_weight_map).values
            predictor.fit(train_df)  # initial fit populates encoders
            try:
                # Re-fit raw model with weights (calibration wrapper handled inside predictor)
                available = [c for c in predictor.feature_cols if c in train_df.columns]
                Xw = train_df[available]
                yw = train_df['home_win'] if 'home_win' in train_df.columns else None
                if yw is not None:
                    predictor._raw_model.fit(Xw, yw, sample_weight=sample_weights)
                    if predictor.calibrate:
                        from sklearn.calibration import CalibratedClassifierCV
                        predictor.model = CalibratedClassifierCV(predictor._raw_model, method=predictor.calibration_method, cv=5)
                        predictor.model.fit(Xw, yw)
                    print("✓ Applied sample weighting (current season heavy) in predictor training")
            except Exception as exc:
                print(f"⚠️ Sample weighting re-fit failed: {exc}; using unweighted model.")
        else:
            print("✓ Sample weights disabled (standard training)")
            predictor.fit(train_df)
        predictions_df = predictor.predict(upcoming)
        
        # Sort by confidence (highest first) for better readability
        predictions_df = predictions_df.sort_values('confidence', ascending=False)
        
        # Enrich predictions with team IDs if present in upcoming games
        try:
            id_cols = [c for c in ['home_team_id', 'away_team_id'] if c in upcoming.columns]
            if id_cols:
                id_df = upcoming[['game_id'] + id_cols].drop_duplicates(subset=['game_id'])
                predictions_df = predictions_df.merge(id_df, on='game_id', how='left')
        except Exception as exc:
            print(f"⚠️ Failed to merge team IDs into predictions: {exc}")

        # Save predictions (persist with normalized flag)
        predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
        predictions_df['normalized_input'] = os.path.exists(normalized_hist_path)
        predictions_df['config_version'] = _config_version
        predictions_df['commit_hash'] = _commit_hash
        predictions_df.to_csv(predictions_path, index=False)
        # Validation guard: ensure lineage columns present post-write
        try:
            _verify = pd.read_csv(predictions_path, nrows=5)
            missing_cols = [c for c in ['config_version','commit_hash'] if c not in _verify.columns]
            if missing_cols:
                print(f"✗ Lineage columns missing after write: {missing_cols}")
            else:
                print("✓ Lineage columns verified in predictions CSV")
        except Exception as _val_exc:
            print(f"⚠️ Could not validate lineage columns: {_val_exc}")

        # Append live predictions to drift log
        try:
            log_path = Path(data_dir) / 'prediction_log.csv'
            log_predictions(
                predictions_df,
                source='live',
                model_name='AdaptivePredictor',
                model_version=model_version,
                config_version=_config_version,
                commit_hash=_commit_hash,
                log_path=log_path,
                timestamp=datetime.now(datetime.UTC),
            )
            print(f"✓ Logged live predictions to {log_path}")
        except Exception as log_exc:
            print(f"⚠️ Failed to log live predictions: {log_exc}")

        print(f"✓ Generated {len(predictions_df)} predictions")
        print(f"  - Home team favored: {predictions_df['predicted_home_win'].sum()}")
        print(f"  - Away team favored: {len(predictions_df) - predictions_df['predicted_home_win'].sum()}")
        print(f"  - Average confidence: {predictions_df['confidence'].mean():.1%}")

        # Show high confidence predictions
        high_conf = predictions_df[predictions_df['confidence'] >= 0.7].sort_values('confidence', ascending=False)
        if len(high_conf) > 0:
            print(f"\n  High confidence predictions (≥70%):")
            for _, game in high_conf.head(10).iterrows():
                winner = game['predicted_winner']
                loser = game['home_team'] if winner == game['away_team'] else game['away_team']
                conf = game['confidence']
                print(f"    {winner:35} over {loser:30} ({conf:.1%})")
            if len(high_conf) > 10:
                print(f"    ... and {len(high_conf) - 10} more")
    else:
        print("✓ No upcoming games to predict")
    
    # =========================================================================
    # STEP 5: Publish artifacts (predictions.md + README evaluation/banner)
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5: Publishing artifacts (predictions.md & README)")
    print("-"*80)
    try:
        result = sp_run(['python3', 'game_prediction/publish_artifacts.py'], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"✗ Artifact publishing failed: {result.stderr}")
    except Exception as exc:
        print(f"✗ Artifact publishing error: {exc}")

    # Generate performance dashboard (charts + markdown)
    try:
        perf_result = sp_run(['python3', 'scripts/generate_performance_report.py'], capture_output=True, text=True, timeout=60)
        if perf_result.returncode == 0:
            if perf_result.stdout.strip():
                print(perf_result.stdout.strip())
            else:
                print("✓ performance.md generated")
        else:
            print(f"⚠️ Performance report failed: {perf_result.stderr}")
    except Exception as exc:
        print(f"⚠️ Performance report step skipped: {exc}")
    
    # =========================================================================
    # STEP 5.5: Generate Betting Tracker Report
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5.5: Generating betting tracker report")
    print("-"*80)
    try:
        result = sp_run(['python3', 'game_prediction/betting_tracker.py'], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"⚠️ Betting tracker failed: {result.stderr}")
    except Exception as exc:
        print(f"⚠️ Betting tracker step skipped: {exc}")
    
    # =========================================================================
    # STEP 6: Per-Team Drift & Anomaly Summaries
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 6: Updating per-team drift & anomaly summaries")
    print("-"*80)
    try:
        # Run drift monitor module
        result = sp_run(
            ['python3', '-m', 'model_training.team_drift_monitor', '--window', str(drift_window)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            print("✓ Drift monitor executed")
        else:
            print(f"⚠️ Drift monitor non-zero exit: {result.stderr}")
        # Generate TEAM_ANOMALIES.md if anomalies exist
        anomalies_csv = Path(data_dir) / 'Team_Anomalies.csv'
        anomalies_md = Path(data_dir) / 'TEAM_ANOMALIES.md'
        try:
            from model_training.team_drift_monitor import write_anomalies_markdown
            if write_anomalies_markdown(anomalies_csv, anomalies_md, drift_window):
                print(f"✓ Anomalies markdown written: {anomalies_md}")
            else:
                print("✓ No anomalies markdown generated (missing or empty anomalies CSV)")
        except Exception as sub_exc:
            print(f"⚠️ Failed anomaly markdown generation: {sub_exc}")
    except Exception as exc:
        print(f"⚠️ Drift/anomaly summary skipped: {exc}")

    # =========================================================================
    # STEP 7: Pipeline Complete
    # =========================================================================
    print("\n" + "="*80)
    print("PIPELINE COMPLETE!")
    print("="*80)
    print(f"\nFiles updated:")
    print(f"  - {os.path.join(data_dir, 'Completed_Games.csv')}")
    print(f"  - {os.path.join(data_dir, 'Upcoming_Games.csv')}")
    print(f"  - {os.path.join(data_dir, 'Completed_Games_Normalized.csv')} (if normalization succeeded)")
    print(f"  - {os.path.join(data_dir, 'NCAA_Game_Predictions.csv')} (config_version={_config_version})")
    print(f"    commit_hash={_commit_hash}")
    print(f"  - {os.path.join(data_dir, 'Accuracy_Report.csv')}")
    print(f"  - predictions.md")
    print(f"  - bets.md (comparison)")
    print(f"  - safest_bets.md")
    print(f"  - value_bets.md")
    print(f"  - README.md (Model Evaluation section)")
    print(f"\nRun this script daily to keep predictions updated!")
    print("="*80)

if __name__ == "__main__":
    main()
