#!/usr/bin/env python3
"""
Apply manual corrections to canonical team names.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from backend.database import get_db_connection

print("="*80)
print("APPLYING MANUAL CORRECTIONS TO CANONICAL NAMES")
print("="*80)
print()

# Load corrections
print("1. Loading corrections...")
corrections_df = pd.read_csv('data/espn_team_corrections.csv')
print(f"   ✓ Loaded {len(corrections_df)} corrections")

# Connect to database
db = get_db_connection()

# Apply each correction
print("\n2. Applying corrections to games table...")
for _, row in corrections_df.iterrows():
    db_name = row['database_name']
    canonical = row['canonical_name']
    
    # Update home team
    result1 = db.execute("""
        UPDATE games 
        SET home_team_canonical = ?
        WHERE home_team = ?
    """, (canonical, db_name))
    
    # Update away team  
    result2 = db.execute("""
        UPDATE games
        SET away_team_canonical = ?
        WHERE away_team = ?
    """, (canonical, db_name))
    
    print(f"   ✓ '{db_name}' → '{canonical}'")

# Update predictions table
print("\n3. Updating predictions table...")
for _, row in corrections_df.iterrows():
    db_name = row['database_name']
    canonical = row['canonical_name']
    
    db.execute("""
        UPDATE predictions
        SET predicted_winner = ?
        WHERE predicted_winner = ?
    """, (canonical, db_name))

# Also update any predictions that still point to old canonical names
old_mappings = {
    'Maryland': 'MD Eastern',  # If any predictions had Maryland but meant MD Eastern
    'Houston': 'Sam Houston',   # If any predictions had Houston but meant Sam Houston
    'Virginia': 'VCU'           # If any predictions had Virginia but meant VCU
}

print("\n4. Checking for indirect prediction corrections...")
for db_name in corrections_df['database_name']:
    # Get games with this team
    games = db.fetch_all("""
        SELECT game_id, home_team, away_team, home_team_canonical, away_team_canonical
        FROM games
        WHERE home_team = ? OR away_team = ?
    """, (db_name, db_name))
    
    for game in games:
        # Check if predictions for this game need updating
        if game['home_team'] == db_name:
            correct_canonical = game['home_team_canonical']
        else:
            correct_canonical = game['away_team_canonical']
        
        # Update prediction if needed
        db.execute("""
            UPDATE predictions
            SET predicted_winner = ?
            WHERE game_id = ? AND predicted_winner IN (?, ?)
        """, (correct_canonical, game['game_id'], game['home_team'], game['away_team']))

print("   ✓ Predictions updated")

# Verify
print("\n5. Verifying corrections...")
for _, row in corrections_df.iterrows():
    db_name = row['database_name']
    canonical = row['canonical_name']
    
    count = db.fetch_one("""
        SELECT COUNT(*) as count
        FROM games
        WHERE (home_team = ? AND home_team_canonical = ?)
           OR (away_team = ? AND away_team_canonical = ?)
    """, (db_name, canonical, db_name, canonical))
    
    if count['count'] > 0:
        print(f"   ✓ '{db_name}' → '{canonical}': {count['count']} games")

# Update the mappings CSV for future use
print("\n6. Updating mappings file...")
mappings_df = pd.read_csv('data/espn_team_mappings.csv')

for _, row in corrections_df.iterrows():
    if pd.notna(row['espn_id']):
        # Update mapping
        mask = mappings_df['database_name'] == row['database_name']
        if mask.any():
            mappings_df.loc[mask, 'canonical_name'] = row['canonical_name']
            mappings_df.loc[mask, 'espn_id'] = int(row['espn_id'])
            mappings_df.loc[mask, 'match_confidence'] = 100

mappings_df.to_csv('data/espn_team_mappings.csv', index=False)
print("   ✓ Updated espn_team_mappings.csv")

print("\n" + "="*80)
print("✅ CORRECTIONS APPLIED SUCCESSFULLY")
print("="*80)
print()
print("📝 Corrections Applied:")
for _, row in corrections_df.iterrows():
    print(f"   '{row['database_name']}' → '{row['canonical_name']}'")

db.close()
