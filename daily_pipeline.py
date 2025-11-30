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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))


def scrape_espn_games(scraper, start_date, end_date, max_retries=3):
    """
    Scrape ESPN games with retry logic.
    
    Args:
        scraper: ESPNScraper instance
        start_date: Start date for scraping
        end_date: End date for scraping
        max_retries: Maximum retry attempts
        
    Returns:
        List of games or empty list on failure
    """
    from retry_utils import retry_call
    import requests
    
    try:
        games = retry_call(
            scraper.get_season_games,
            start_date,
            end_date,
            max_retries=max_retries,
            initial_delay=5.0,
            backoff_factor=2.0,
            exceptions=(requests.exceptions.RequestException, ConnectionError, TimeoutError),
        )
        return games
    except Exception as e:
        print(f"❌ ESPN scraping failed after {max_retries + 1} attempts: {e}")
        return []


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
    
    # Use retry-enabled scraping for robustness against network issues
    games = scrape_espn_games(scraper, start_date, end_date, max_retries=3)
    
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
        from data_collection.team_name_utils import normalize_game_dataframe
        # Apply normalization to historical file for modeling
        hist_df = pd.read_csv(historical_path)
        hist_df = normalize_game_dataframe(hist_df, team_columns=['home_team', 'away_team'])
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
            from data_collection.team_name_utils import normalize_game_dataframe
            upcoming = normalize_game_dataframe(upcoming, team_columns=['home_team', 'away_team'])
            print("✓ Normalized upcoming games team names")
        except Exception as exc:
            print(f"⚠️ Failed to normalize upcoming games: {exc}")
        
        # Enrich upcoming games with feature store using fallback hierarchy (Phase 1 Task 1.1)
        try:
            from model_training.feature_store import load_feature_store, enrich_dataframe_with_fallback
            from model_training.team_id_utils import ensure_team_ids
            import json
            
            # Load feature flags
            try:
                with open('config/feature_flags.json') as f:
                    feature_flags = json.load(f)
            except Exception:
                feature_flags = {}
            
            use_fallback = feature_flags.get('use_feature_fallback', True)
            fallback_min_games = feature_flags.get('fallback_min_games', 5)
            
            upcoming = ensure_team_ids(upcoming)
            fs_df = load_feature_store()
            
            if not fs_df.empty and use_fallback:
                # Use new fallback-aware enrichment (no NaN values)
                print("  Using feature store with fallback hierarchy...")
                upcoming = enrich_dataframe_with_fallback(
                    upcoming, 
                    feature_store_df=fs_df,
                    min_games=fallback_min_games
                )
                print("✓ Added feature store columns to upcoming games (with fallback - no NaN)")
            elif not fs_df.empty:
                # Legacy merge approach (may have NaN values)
                fs_df_reduced = fs_df.sort_values(['season','team_id','games_played']).drop_duplicates(['season','team_id'], keep='last')
                fs_features = ['rolling_win_pct_5','rolling_win_pct_10','rolling_point_diff_avg_5','rolling_point_diff_avg_10','win_pct_last5_vs10','point_diff_last5_vs10','recent_strength_index_5']
                keep_cols = ['season','team_id'] + [c for c in fs_features if c in fs_df_reduced.columns]
                fs_df_reduced = fs_df_reduced[keep_cols]
                if 'season' not in upcoming.columns:
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
                print("✓ Added feature store columns to upcoming games (legacy merge)")
        except Exception as exc:
            import traceback
            print(f"⚠️ Skipped feature store enrichment for upcoming games: {exc}")
            traceback.print_exc()
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
    # STEP 3.5: Analyze betting line disagreements (value identification)
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 3.5: Analyzing betting line disagreements")
    print("-"*80)
    
    try:
        from game_prediction.analyze_betting_lines import analyze_betting_line_performance
        analyze_betting_line_performance()
    except Exception as exc:
        print(f"⚠️ Betting line analysis failed: {exc}")
    
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
        normalized_hist_path = os.path.join(data_dir, 'Completed_Games_Normalized.csv')
        if os.path.exists(normalized_hist_path):
            train_df = pd.read_csv(normalized_hist_path)
            print(f"✓ Using normalized training data ({len(train_df)} rows)")
        else:
            train_df = pd.read_csv(historical_path)
            print(f"✓ Using raw training data ({len(train_df)} rows) - normalized file not found")
        
        # Train model and generate predictions
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
            'n_estimators', 'max_depth', 'min_samples_split', 'min_games_threshold',
            'calibrate', 'calibration_method', 'home_court_logit_shift', 'confidence_temperature',
        ]:
            if key in adaptive_cfg:
                sp_kwargs[key] = adaptive_cfg[key]
                
        if sp_kwargs:
            print(f"✓ Loaded tuned adaptive predictor params: {sp_kwargs}")
        else:
            print("⚠️ No tuned params found (using defaults)")
            
        predictor = AdaptivePredictor(**sp_kwargs)
        
        # Enrich training data with point-in-time features
        try:
            from model_training.feature_store import calculate_point_in_time_features
            from model_training.team_id_utils import ensure_team_ids
            
            train_df = ensure_team_ids(train_df)
            print("  Calculating point-in-time features for training data...")
            train_df = calculate_point_in_time_features(train_df)
            print(f"✓ Added point-in-time features to training data (rows {len(train_df)})")
        except Exception as exc:
            import traceback
            print(f"⚠️ Failed to calculate point-in-time features for training data: {exc}")
            traceback.print_exc()

        # Fit model
        predictor.fit(train_df)
        
        # Predict and log
        try:
            preds = predictor.predict(upcoming)
            if len(preds) == len(upcoming):
                # 1. Add raw probabilities
                upcoming['home_win_prob'] = preds
                upcoming['away_win_prob'] = 1 - preds
                
                # 2. Calculate derived fields (Required for bets.md and predictions.md)
                upcoming['predicted_home_win'] = (upcoming['home_win_prob'] >= 0.5).astype(int)
                upcoming['confidence'] = upcoming.apply(
                    lambda x: x['home_win_prob'] if x['home_win_prob'] >= 0.5 else x['away_win_prob'], axis=1
                )
                upcoming['predicted_winner'] = upcoming.apply(
                    lambda x: x['home_team'] if x['predicted_home_win'] == 1 else x['away_team'], axis=1
                )

                # 3. Log to prediction_log.csv (History)
                log_df = upcoming.copy()
                log_predictions(
                    log_df,
                    source='live',
                    model_name='AdaptivePredictor',
                    model_version=model_version,
                    config_version=_config_version,
                    commit_hash=_commit_hash,
                    timestamp=datetime.now()
                )
                print("✓ Predictions logged to history")

                # 4. Save daily snapshot (Required for Today's Bets)
                snapshot_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
                upcoming.to_csv(snapshot_path, index=False)
                print(f"✓ Saved daily predictions snapshot to {snapshot_path}")
            else:
                print("⚠️ Prediction length mismatch")
        except Exception as e:
            import traceback
            print(f"⚠️ Prediction error: {e}")
            traceback.print_exc()
    else:
        print("✓ No upcoming games to predict")

    # =========================================================================
    # STEP 5: Generate markdown reports and update README
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5: Generating markdown reports")
    print("-"*80)

    # Generate predictions.md and update README.md
    try:
        from game_prediction.publish_artifacts import generate_predictions_markdown, refresh_readme_evaluation
        generate_predictions_markdown()
        refresh_readme_evaluation()
    except Exception as e:
        print(f"⚠️ Failed to generate predictions markdown: {e}")

    # Generate performance.md dashboard
    try:
        from scripts.generate_performance_report import main as generate_performance_report
        generate_performance_report()
    except Exception as e:
        print(f"⚠️ Failed to generate performance.md: {e}")

    # Generate betting tracker markdown files (bets.md, safest_bets.md, value_bets.md)
    try:
        from game_prediction.betting_tracker import generate_bets_markdown
        generate_bets_markdown()
    except Exception as e:
        print(f"⚠️ Failed to generate betting markdown: {e}")

    # =========================================================================
    # STEP 6: Generate health summary
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 6: Pipeline health summary")
    print("-"*80)
    
    # Collect health metrics
    health_summary = {
        'run_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'config_version': _config_version,
        'commit_hash': _commit_hash,
        'status': 'SUCCESS',
        'warnings': [],
    }
    
    # Check critical files exist
    critical_files = [
        ('data/Completed_Games.csv', 'Training data'),
        ('data/Upcoming_Games.csv', 'Upcoming games'),
        ('config/model_params.json', 'Model parameters'),
    ]
    
    for filepath, description in critical_files:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print(f"  ✓ {description}: {filepath} ({size:,} bytes)")
        else:
            print(f"  ⚠️ {description}: {filepath} MISSING")
            health_summary['warnings'].append(f"Missing {description}")
    
    # Summary output
    if health_summary['warnings']:
        health_summary['status'] = 'WARNING'
        print(f"\n⚠️ Pipeline completed with {len(health_summary['warnings'])} warnings")
    else:
        print("\n✓ All health checks passed")

    print("\n" + "="*80)
    print("Pipeline complete.")
    print("="*80)

if __name__ == "__main__":
    main()
