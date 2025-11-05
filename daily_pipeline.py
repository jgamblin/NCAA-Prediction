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
import subprocess
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
    
    # Inline normalization after merge (ensures modeling continuity)
    try:
        from data_collection.normalize_teams import team_name_mapping
        # Apply mapping to historical file for modeling (in-place copy with normalized columns)
        hist_df = pd.read_csv(historical_path)
        for col in ['home_team', 'away_team']:
            if col in hist_df.columns:
                hist_df[col] = hist_df[col].replace(team_name_mapping)
        normalized_hist_path = os.path.join(data_dir, 'Completed_Games_Normalized.csv')
        hist_df.to_csv(normalized_hist_path, index=False)
        print(f"✓ Normalized historical games written: {normalized_hist_path}")
    except Exception as e:
        print(f"⚠️ Normalization step failed (continuing): {e}")

    # Save upcoming games (also normalize team display names for consistency)
    if len(upcoming) > 0:
        upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
        try:
            from data_collection.normalize_teams import team_name_mapping
            for col in ['home_team', 'away_team']:
                if col in upcoming.columns:
                    upcoming[col] = upcoming[col].replace(team_name_mapping)
        except Exception as e:
            print(f"⚠️ Failed to normalize upcoming games: {e}")
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
        
        # Use simplified prediction model
        from simple_predictor import SimplePredictor
        
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
        predictor = SimplePredictor()
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
        except Exception as e:
            print(f"⚠️ Failed to merge team IDs into predictions: {e}")

        # Save predictions (persist with normalized flag)
        predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
        predictions_df['normalized_input'] = os.path.exists(normalized_hist_path)
        predictions_df.to_csv(predictions_path, index=False)

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
    print(f"  - {os.path.join(data_dir, 'Completed_Games_Normalized.csv')} (if normalization succeeded)")
    print(f"  - {os.path.join(data_dir, 'NCAA_Game_Predictions.csv')}")
    print(f"  - {os.path.join(data_dir, 'Accuracy_Report.csv')}")
    print(f"  - predictions.md")
    print(f"  - README.md (Model Evaluation section)")
    print(f"\nRun this script daily to keep predictions updated!")
    print("="*80)

if __name__ == "__main__":
    main()
