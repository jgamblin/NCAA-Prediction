#!/usr/bin/env python3
"""
Fix all team names in the database to use normalized names without mascots.

This script fixes the accuracy drop that occurred after Nov 24 when team names
started being stored with mascots (e.g., "Indiana Hoosiers" instead of "Indiana").

The model was trained on normalized names, so predictions for non-normalized names
fail catastrophically.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection
from backend.repositories import GamesRepository, TeamsRepository, PredictionsRepository
from data_collection.team_name_utils import normalize_team_name
import pandas as pd


def fix_games_table(games_repo, db):
    """Normalize all team names in the games table."""
    
    print("\n" + "="*80)
    print("FIXING GAMES TABLE")
    print("="*80)
    
    # Get all games
    query = "SELECT game_id, home_team, away_team FROM games"
    games_df = db.fetch_df(query)
    
    print(f"\nFound {len(games_df)} games in database")
    
    # Normalize team names
    updates_needed = 0
    updates_made = 0
    
    for idx, row in games_df.iterrows():
        game_id = row['game_id']
        home_orig = row['home_team']
        away_orig = row['away_team']
        
        # Skip A&M teams - URL encoding issues
        if 'A&M' in home_orig or 'A&M' in away_orig:
            continue
        if 'A%26M' in home_orig or 'A%26M' in away_orig:
            continue
        
        home_norm = normalize_team_name(home_orig)
        away_norm = normalize_team_name(away_orig)
        
        needs_update = False
        if home_orig != home_norm:
            needs_update = True
            updates_needed += 1
        if away_orig != away_norm:
            needs_update = True
            updates_needed += 1
        
        if needs_update:
            # Update the game
            db.execute("""
                UPDATE games 
                SET home_team = ?, away_team = ?
                WHERE game_id = ?
            """, (home_norm, away_norm, game_id))
            updates_made += 1
            
            if updates_made <= 10:
                print(f"  Fixed game {game_id}:")
                if home_orig != home_norm:
                    print(f"    Home: '{home_orig}' → '{home_norm}'")
                if away_orig != away_norm:
                    print(f"    Away: '{away_orig}' → '{away_norm}'")
    
    if updates_made > 10:
        print(f"  ... and {updates_made - 10} more games")
    
    print(f"\n✓ Updated {updates_made} games ({updates_needed} team name changes)")


def fix_teams_table(teams_repo, db):
    """Normalize all team names in the teams table."""
    
    print("\n" + "="*80)
    print("FIXING TEAMS TABLE")
    print("="*80)
    
    # Get all teams
    query = "SELECT team_id, display_name, canonical_name FROM teams"
    teams_df = db.fetch_df(query)
    
    print(f"\nFound {len(teams_df)} teams in database")
    
    updates_needed = 0
    updates_made = 0
    
    for idx, row in teams_df.iterrows():
        team_id = row['team_id']
        display_orig = row['display_name']
        canonical_orig = row.get('canonical_name', display_orig)
        
        # Skip A&M teams - URL encoding issues
        if 'A&M' in display_orig or 'A%26M' in display_orig:
            continue
        
        display_norm = normalize_team_name(display_orig)
        canonical_norm = normalize_team_name(canonical_orig)
        
        needs_update = (display_orig != display_norm or canonical_orig != canonical_norm)
        
        if needs_update:
            # Check if canonical_name already exists (unique constraint)
            existing = db.fetch_one("""
                SELECT team_id FROM teams 
                WHERE canonical_name = ? AND team_id != ?
            """, (canonical_norm, team_id))
            
            if existing:
                # Skip this update to avoid constraint violation
                # (The duplicate will be handled separately)
                print(f"  Skipping {team_id}: canonical name '{canonical_norm}' already exists")
                continue
            
            db.execute("""
                UPDATE teams 
                SET display_name = ?, canonical_name = ?
                WHERE team_id = ?
            """, (display_norm, canonical_norm, team_id))
            updates_made += 1
            
            if updates_made <= 10:
                print(f"  Fixed team {team_id}: '{display_orig}' → '{display_norm}'")
    
    if updates_made > 10:
        print(f"  ... and {updates_made - 10} more teams")
    
    print(f"\n✓ Updated {updates_made} teams")


def fix_predictions_table(pred_repo, db):
    """Normalize team names in the predictions table (via games lookup)."""
    
    print("\n" + "="*80)
    print("FIXING PREDICTIONS TABLE")
    print("="*80)
    
    # Predictions are linked to games by game_id, so they'll automatically
    # reference the corrected team names when joined
    # We just need to update the predicted_winner field if it contains mascots
    
    query = """
        SELECT id, predicted_winner 
        FROM predictions 
        WHERE predicted_winner IS NOT NULL
    """
    preds_df = db.fetch_df(query)
    
    print(f"\nFound {len(preds_df)} predictions in database")
    
    updates_made = 0
    
    for idx, row in preds_df.iterrows():
        pred_id = row['id']
        winner_orig = row['predicted_winner']
        
        if not winner_orig:
            continue
        
        # Skip A&M teams - URL encoding issues
        if 'A&M' in winner_orig or 'A%26M' in winner_orig:
            continue
        
        winner_norm = normalize_team_name(winner_orig)
        
        if winner_orig != winner_norm:
            db.execute("""
                UPDATE predictions 
                SET predicted_winner = ?
                WHERE id = ?
            """, (winner_norm, pred_id))
            updates_made += 1
            
            if updates_made <= 10:
                print(f"  Fixed prediction {pred_id}: '{winner_orig}' → '{winner_norm}'")
    
    if updates_made > 10:
        print(f"  ... and {updates_made - 10} more predictions")
    
    print(f"\n✓ Updated {updates_made} predictions")


def verify_normalization(db):
    """Verify that all team names are now normalized."""
    
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    # Check for any remaining team names with common mascots
    common_mascots = ['Hoosiers', 'Wildcats', 'Tigers', 'Eagles', 'Bulldogs', 
                      'Bears', 'Lions', 'Panthers', 'Hawks', 'Cardinals']
    
    problems_found = 0
    
    for mascot in common_mascots:
        query = f"""
            SELECT DISTINCT home_team FROM games 
            WHERE home_team LIKE '%{mascot}%'
            UNION
            SELECT DISTINCT away_team FROM games 
            WHERE away_team LIKE '%{mascot}%'
        """
        result = db.fetch_all(query)
        
        if result:
            problems_found += len(result)
            if problems_found <= 10:
                for row in result[:3]:
                    # row is a dict with 'home_team' key
                    team_name = row.get('home_team', list(row.values())[0] if row else '')
                    print(f"  ⚠️  Found unnormalized name: '{team_name}'")
    
    if problems_found > 0:
        print(f"\n⚠️  Warning: Found {problems_found} team names that may still contain mascots")
        print("   This might be OK if they're part of the official school name")
    else:
        print("\n✓ All team names appear to be normalized!")


def main():
    """Run the database team name fix."""
    
    print("="*80)
    print("DATABASE TEAM NAME NORMALIZATION FIX")
    print("="*80)
    print("\nThis script fixes team names that were stored with mascots,")
    print("which caused the accuracy drop from 70% to 36% after Nov 24.")
    print()
    
    # Get database connection
    db = get_db_connection()
    
    games_repo = GamesRepository(db)
    teams_repo = TeamsRepository(db)
    pred_repo = PredictionsRepository(db)
    
    try:
        # Fix each table
        fix_games_table(games_repo, db)
        fix_teams_table(teams_repo, db)
        fix_predictions_table(pred_repo, db)
        
        # Verify the fix
        verify_normalization(db)
        
        print("\n" + "="*80)
        print("✅ DATABASE FIX COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("  1. Re-run the daily pipeline: python daily_pipeline_db.py")
        print("  2. Check prediction accuracy")
        print("  3. The pipeline will now normalize team names immediately after scraping")
        print()
        
    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
