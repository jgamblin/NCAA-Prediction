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
import numpy as np
from datetime import datetime, timedelta

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
    
    # =========================================================================
    # STEP 1: Scrape ESPN for recent games
    # =========================================================================
    print("STEP 1: Scraping ESPN for recent games")
    print("-"*80)
    
    from espn_scraper import ESPNScraper
    
    scraper = ESPNScraper()
    
    # Get last 3 days to catch any games we missed
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
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
    
    # Save upcoming games
    predictions_df = None  # will hold resulting predictions if generated
    if len(upcoming) > 0:
        upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
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
    
    from track_accuracy import track_accuracy
    track_accuracy()
    
    # =========================================================================
    # STEP 4: Generate predictions for upcoming games
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 4: Generating predictions for upcoming games")
    print("-"*80)
    
    if len(upcoming) > 0:
        print(f"Generating predictions for {len(upcoming)} upcoming games...")
        
        # Attempt to use calibrated CatBoost model if present, else fallback
        data_dir_abs = data_dir
        calibrated_path = os.path.join(data_dir_abs, 'catboost_calibrated.pkl')
        best_model_path = os.path.join(data_dir_abs, 'catboost_best_model.cbm')
        predictor = None
        model_type = 'SimplePredictor'
        try:
            if os.path.exists(calibrated_path):
                import joblib
                from catboost import CatBoostClassifier
                from sklearn.calibration import CalibratedClassifierCV
                calib = joblib.load(calibrated_path)
                model_type = 'CalibratedCatBoost'
                predictor = calib
            elif os.path.exists(best_model_path):
                from catboost import CatBoostClassifier
                cat_model = CatBoostClassifier()
                cat_model.load_model(best_model_path)
                predictor = cat_model
                model_type = 'CatBoost'
        except Exception as e:
            print(f"[WARN] CatBoost load failed, falling back to SimplePredictor: {e}")
            predictor = None

        from simple_predictor import SimplePredictor
        train_df = pd.read_csv(historical_path)

        if predictor is None:
            sp = SimplePredictor()
            sp.fit(train_df)
            predictions_df = sp.predict(upcoming)
        else:
            # Need to prepare upcoming in same style as simple predictor
            sp_temp = SimplePredictor()
            train_df_prep = sp_temp.prepare_data(train_df)
            # Fit encoder on historical teams for consistent numeric mapping
            all_teams_series = pd.concat([train_df_prep['home_team'], train_df_prep['away_team']])
            all_teams = all_teams_series.unique()
            sp_temp.team_encoder.fit(all_teams)
            up_df = sp_temp.prepare_data(upcoming.copy())
            up_df['home_team_encoded'] = up_df['home_team'].apply(lambda t: sp_temp.team_encoder.transform([t])[0] if t in sp_temp.team_encoder.classes_ else -1)
            up_df['away_team_encoded'] = up_df['away_team'].apply(lambda t: sp_temp.team_encoder.transform([t])[0] if t in sp_temp.team_encoder.classes_ else -1)
            X_up = up_df[sp_temp.feature_cols]
            # CatBoost or calibrated model predictions
            try:
                proba = predictor.predict_proba(X_up)  # type: ignore
            except Exception:
                proba = predictor.predict(X_up)  # type: ignore
                # If only raw predictions, synthesize probability columns
                if proba.ndim == 1:
                    proba = np.vstack([1 - proba, proba]).T
            if proba.shape[1] == 2:
                home_win_prob = proba[:,1]
                away_win_prob = proba[:,0]
            else:
                # Fallback assume binary probability in single column
                home_win_prob = proba.ravel()
                away_win_prob = 1 - home_win_prob
            preds = (home_win_prob >= 0.5).astype(int)
            results_df = pd.DataFrame({
                'game_id': up_df['game_id'],
                'date': up_df['date'],
                'away_team': up_df['away_team'],
                'home_team': up_df['home_team'],
                'predicted_home_win': preds,
                'home_win_probability': home_win_prob,
                'away_win_probability': away_win_prob,
                'game_url': up_df.get('game_url','')
            })
            results_df['predicted_winner'] = results_df.apply(lambda r: r['home_team'] if r['predicted_home_win']==1 else r['away_team'], axis=1)
            results_df['confidence'] = results_df[['home_win_probability','away_win_probability']].max(axis=1)
            predictions_df = results_df
        print(f"Using model type: {model_type}")
        
        # Sort by confidence (highest first) for better readability
        predictions_df = predictions_df.sort_values('confidence', ascending=False)
        
        # Save predictions
        predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
        predictions_df.to_csv(predictions_path, index=False)
        print(f"✓ Generated {len(predictions_df)} predictions")
        print(f"  - Home team favored: {predictions_df['predicted_home_win'].sum()}")
        print(f"  - Away team favored: {len(predictions_df) - predictions_df['predicted_home_win'].sum()}")
        print(f"  - Average confidence: {predictions_df['confidence'].mean():.1%}")

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
    # STEP 5: Generate predictions.md
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5: Generating predictions.md")
    print("-"*80)
    
    try:
        import subprocess
        result = subprocess.run(['python3', 'game_prediction/generate_predictions_md.py'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"✗ Error generating predictions.md: {result.stderr}")
    except Exception as e:
        print(f"✗ Error generating predictions.md: {e}")
    
    # =========================================================================
    # STEP 6: Update README with current model stats
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 6: Updating README model statistics")
    print("-"*80)
    
    try:
        result = subprocess.run(['python3', 'game_prediction/update_readme_stats.py'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"✗ Error updating README: {result.stderr}")
    except Exception as e:
        print(f"✗ Error updating README: {e}")
    
    # =========================================================================
    # Pipeline Complete
    # =========================================================================
    print("\n" + "="*80)
    print("PIPELINE COMPLETE!")
    print("="*80)
    print(f"\nFiles updated:")
    print(f"  - {os.path.join(data_dir, 'Completed_Games.csv')}")
    print(f"  - {os.path.join(data_dir, 'Upcoming_Games.csv')}")
    print(f"  - {os.path.join(data_dir, 'NCAA_Game_Predictions.csv')}")
    print(f"  - {os.path.join(data_dir, 'Accuracy_Report.csv')}")
    print(f"  - predictions.md")
    print(f"  - README.md (Model Evaluation section)")
    print(f"\nRun this script daily to keep predictions updated!")
    print("="*80)

if __name__ == "__main__":
    main()
