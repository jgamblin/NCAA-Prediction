#!/usr/bin/env python3
"""
NCAA Basketball Data Collection Pipeline
Run this script to collect game data for multiple seasons.
This script combines:
1. Historical data from ncaahoopR_data (2020-21 through 2024-25)
2. Current season data from ESPN scraper (2025-26)
"""

import sys
import os
import pandas as pd

# Add data_collection to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data_collection'))

def main():
    """Main data collection pipeline."""
    print("="*80)
    print("NCAA BASKETBALL DATA COLLECTION PIPELINE")
    print("="*80)
    print()
    
    # Step 1: Collect historical data (2020-21 through 2024-25)
    print("STEP 1: Collecting historical data from ncaahoopR_data...")
    print("-"*80)
    from all_games import main as collect_historical
    collect_historical()
    
    print("\n")
    
    # Step 2: Collect current season data from ESPN
    print("STEP 2: Collecting current season (2025-26) data from ESPN...")
    print("-"*80)
    from espn_scraper import ESPNScraper
    from datetime import datetime
    
    scraper = ESPNScraper()
    season_start = datetime(2025, 11, 1)
    today = datetime.now()
    
    print(f"Scraping ESPN from {season_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    current_season_games = scraper.get_season_games(season_start, today)
    
    if len(current_season_games) > 0:
        # Convert to DataFrame
        current_season_df = pd.DataFrame(current_season_games)
        current_season_df = current_season_df.drop_duplicates(subset=['game_id'])
        # Save ESPN data separately
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        # Ensure directory exists (handles cleaned repo scenarios)
        os.makedirs(data_dir, exist_ok=True)
        espn_path = os.path.join(data_dir, 'ESPN_Current_Season.csv')
        current_season_df.to_csv(espn_path, index=False)
        print(f"\nSaved {len(current_season_df)} current season games to: ESPN_Current_Season.csv")
        
        # Step 3: Merge historical and current season data
        print("\n")
        print("STEP 3: Merging historical and current season data...")
        print("-"*80)
        
        historical_path = os.path.join(data_dir, 'Completed_Games.csv')
        if os.path.exists(historical_path):
            historical_df = pd.read_csv(historical_path)
            print(f"Historical data: {len(historical_df)} games from {historical_df['season'].unique()}")
            
            # Separate completed and upcoming games from ESPN
            completed_current = current_season_df[current_season_df['game_status'] == 'Final'].copy()
            upcoming_current = current_season_df[current_season_df['game_status'] == 'Scheduled'].copy()
            
            if not completed_current.empty:
                # Merge completed games
                merged_df = pd.concat([historical_df, completed_current], ignore_index=True)
                merged_df = merged_df.drop_duplicates(subset=['game_id'], keep='last')
                merged_df.to_csv(historical_path, index=False)
                print(f"Merged data: {len(merged_df)} total games")
                print(f"  Added {len(completed_current)} new completed games from 2025-26 season")
            
            # Save upcoming games separately
            if not upcoming_current.empty:
                upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
                upcoming_current.to_csv(upcoming_path, index=False)
                print(f"  Saved {len(upcoming_current)} upcoming games to: Upcoming_Games.csv")
        else:
            print("Warning: Historical data file not found. Only ESPN data available.")
    else:
        print("\nNo current season games found on ESPN yet.")
        print("The 2025-26 season may not have started or no games have been played.")
    
    print("\n" + "="*80)
    print("DATA COLLECTION COMPLETE!")
    print("="*80)

if __name__ == "__main__":
    main()
