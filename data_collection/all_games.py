"""
NCAA Basketball Game Data Scraper
This script fetches all NCAA basketball games for the current season from the ncaahoopR_data repository.
The data is scraped from ESPN by the ncaahoopR package and made available on GitHub.
It exports completed and upcoming games to CSV files.

Season Format: NCAA seasons are named by the year they start (e.g., "2024-25" for Nov 2024 - Apr 2025)
"""

import pandas as pd
import requests
from datetime import datetime
import time
import json
import sys
import os

# Configure the seasons to fetch data for
# Format: "YYYY-YY" (e.g., "2024-25" for the 2024-2025 season)
# The season typically runs from November YYYY to April YY+1
# For multi-season training, we fetch the last 5 seasons
SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
CURRENT_SEASON = "2024-25"  # The season we're making predictions for


def get_available_seasons():
    """Get list of available seasons from ncaahoopR_data repository."""
    api_url = "https://api.github.com/repos/lbenz730/ncaahoopR_data/contents/"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        files = response.json()
        # Get directories that look like seasons (YYYY-YY format)
        seasons = [f['name'] for f in files if f['type'] == 'dir' and '-' in f['name'] and f['name'][0].isdigit()]
        return sorted(seasons)
    except Exception as e:
        print(f"Error fetching available seasons: {e}")
        return []


def get_team_schedule_urls(season):
    """Get list of all team schedule CSV files from ncaahoopR_data repository for a given season."""
    api_url = f"https://api.github.com/repos/lbenz730/ncaahoopR_data/contents/{season}/schedules"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        files = response.json()
        return [f['download_url'] for f in files if f['name'].endswith('_schedule.csv')]
    except Exception as e:
        print(f"Error fetching schedule list for season {season}: {e}")
        return []


def fetch_all_games(season):
    """Fetch all NCAA basketball games for a given season from ncaahoopR_data repository."""
    print(f"Fetching NCAA basketball games for {season} season...")
    
    # Check if season exists
    available_seasons = get_available_seasons()
    if available_seasons:
        if season not in available_seasons:
            print(f"\nWarning: Season '{season}' not found in repository.")
            print(f"Using most recent season: {available_seasons[-1]}")
            season = available_seasons[-1]
    
    # Get list of all team schedule files
    schedule_urls = get_team_schedule_urls(season)
    
    if not schedule_urls:
        print(f"Error: Could not retrieve schedule files for {season} season.")
        return pd.DataFrame()
    
    print(f"Found {len(schedule_urls)} team schedules to process...")
    
    all_games = []
    games_by_id = {}  # Track games by ID to avoid duplicates
    team_names = {}  # Track team names from file URLs
    
    for idx, url in enumerate(schedule_urls, 1):
        try:
            # Show progress every 50 teams
            if idx % 50 == 0:
                print(f"Processing team {idx}/{len(schedule_urls)}...")
            
            # Extract team name from URL
            team_name = url.split('/')[-1].replace('_schedule.csv', '').replace('_', ' ')
            
            # Fetch team schedule
            df = pd.read_csv(url)
            
            # Process each game in the schedule
            for _, row in df.iterrows():
                game_id = str(row.get('game_id', ''))
                
                # Skip if we've already processed this game
                if game_id in games_by_id:
                    continue
                
                location = row.get('location', 'H')
                opponent = row.get('opponent', '')
                team_score = row.get('team_score')
                opp_score = row.get('opp_score')
                
                # Determine home/away teams based on location
                if location == 'H':  # Home game
                    home_team = team_name
                    away_team = opponent
                    home_score = int(team_score) if pd.notna(team_score) else 0
                    away_score = int(opp_score) if pd.notna(opp_score) else 0
                elif location == 'A':  # Away game
                    home_team = opponent
                    away_team = team_name
                    home_score = int(opp_score) if pd.notna(opp_score) else 0
                    away_score = int(team_score) if pd.notna(team_score) else 0
                else:  # Neutral site
                    # For neutral sites, use alphabetical order for consistency
                    teams = sorted([team_name, opponent])
                    home_team = teams[0]
                    away_team = teams[1]
                    if team_name == home_team:
                        home_score = int(team_score) if pd.notna(team_score) else 0
                        away_score = int(opp_score) if pd.notna(opp_score) else 0
                    else:
                        home_score = int(opp_score) if pd.notna(opp_score) else 0
                        away_score = int(team_score) if pd.notna(team_score) else 0
                
                # Determine game status
                if pd.notna(team_score) and pd.notna(opp_score):
                    game_status = 'Final'
                else:
                    game_status = 'Scheduled'
                
                # Create game record
                game_record = {
                    'game_id': game_id,
                    'game_day': row.get('date', ''),
                    'game_status': game_status,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score,
                    'home_record': '',  # Will be calculated from scores
                    'away_record': '',  # Will be calculated from scores
                    'home_rank': None,  # Not available in schedule files
                    'away_rank': None,  # Not available in schedule files
                    'home_point_spread': '',  # Not available in schedule files
                    'is_neutral': 1 if location == 'N' else 0,
                    'season': season  # Add season tracking
                }
                
                games_by_id[game_id] = game_record
            
            # Small delay to be respectful
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Error processing schedule {url}: {e}")
            continue
    
    # Convert to DataFrame
    all_games = list(games_by_id.values())
    df_season_games = pd.DataFrame(all_games)
    
    if not df_season_games.empty:
        # Sort by date
        df_season_games['game_day'] = pd.to_datetime(df_season_games['game_day'])
        df_season_games = df_season_games.sort_values('game_day')
        df_season_games['game_day'] = df_season_games['game_day'].dt.strftime('%Y-%m-%d')
        df_season_games = df_season_games.reset_index(drop=True)
    
    print(f"\nSuccessfully fetched {len(df_season_games)} unique games for the {season} season!")
    
    return df_season_games


def fetch_multiple_seasons(seasons=SEASONS):
    """Fetch games from multiple seasons and combine them."""
    print("="*80)
    print("MULTI-SEASON DATA COLLECTION")
    print("="*80)
    print(f"Fetching data for {len(seasons)} seasons: {', '.join(seasons)}")
    print("Source: ncaahoopR_data repository (https://github.com/lbenz730/ncaahoopR_data)")
    print()
    
    all_seasons_data = []
    
    for season in seasons:
        print(f"\n{'='*60}")
        print(f"SEASON: {season}")
        print(f"{'='*60}")
        df_season = fetch_all_games(season)
        
        if not df_season.empty:
            all_seasons_data.append(df_season)
            print(f"✓ Added {len(df_season)} games from {season}")
        else:
            print(f"✗ No games found for {season}")
        
        # Brief pause between seasons
        time.sleep(1)
    
    if not all_seasons_data:
        print("\nError: No data collected from any season!")
        return pd.DataFrame()
    
    # Combine all seasons
    print(f"\n{'='*80}")
    print("COMBINING DATA FROM ALL SEASONS")
    print(f"{'='*80}")
    combined_df = pd.concat(all_seasons_data, ignore_index=True)
    
    # Print summary statistics
    print(f"\nTotal games collected: {len(combined_df)}")
    print(f"Date range: {combined_df['game_day'].min()} to {combined_df['game_day'].max()}")
    print(f"\nGames per season:")
    for season in seasons:
        season_count = len(combined_df[combined_df['season'] == season])
        completed = len(combined_df[(combined_df['season'] == season) & (combined_df['game_status'] == 'Final')])
        print(f"  {season}: {season_count:,} total ({completed:,} completed)")
    
    return combined_df


def export_games(df_games):
    """Filter games by status and export to CSV files."""
    # Determine output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Get completed games (status = 'Final')
    completed_games = df_games[df_games['game_status'] == 'Final']
    
    # Get upcoming games (status = 'Scheduled') - only from current season
    if 'season' in df_games.columns:
        upcoming_games = df_games[(df_games['game_status'] == 'Scheduled') & 
                                  (df_games['season'] == CURRENT_SEASON)]
    else:
        upcoming_games = df_games[df_games['game_status'] == 'Scheduled']
    
    # Export to CSV files in data/ directory
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
    
    completed_games.to_csv(completed_path, index=False)
    upcoming_games.to_csv(upcoming_path, index=False)
    
    # Print summary
    print(f"\nExported {len(completed_games):,} completed games to {completed_path}")
    print(f"Exported {len(upcoming_games):,} upcoming games to {upcoming_path}")
    
    if 'season' in completed_games.columns:
        print(f"\nCompleted games by season:")
        season_counts = completed_games['season'].value_counts().sort_index()
        for season, count in season_counts.items():
            print(f"  {season}: {count:,} games")
    
    # Display sample of data
    print("\nSample of completed games (most recent):")
    print(completed_games.tail(5))
    if not upcoming_games.empty:
        print("\nSample of upcoming games:")
        print(upcoming_games.head(5))


def main():
    """Main function to orchestrate game data fetching and export."""
    print("Starting NCAA Basketball game data scraper...")
    print(f"Configured seasons: {', '.join(SEASONS)}")
    print(f"Current prediction season: {CURRENT_SEASON}")
    
    # Allow command-line override to fetch single season
    if len(sys.argv) > 1:
        season_to_use = sys.argv[1]
        print(f"\nCommand-line override: fetching single season {season_to_use}")
        df_games = fetch_all_games(season_to_use)
    else:
        # Default: fetch multiple seasons
        df_games = fetch_multiple_seasons(SEASONS)
    
    if df_games.empty:
        print("\nNo games fetched. Exiting.")
        sys.exit(1)
    
    export_games(df_games)
    print("\n" + "="*80)
    print("DATA COLLECTION COMPLETED SUCCESSFULLY!")
    print("="*80)


if __name__ == "__main__":
    main()
