#!/usr/bin/env python3
"""
Apply canonical team names to database using ESPN mappings.
Adds new columns to preserve original data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from backend.database import get_db_connection
from datetime import datetime

print("="*80)
print("APPLYING CANONICAL TEAM NAMES TO DATABASE")
print("="*80)
print()

# Step 1: Load mappings
print("1. Loading ESPN team mappings...")
try:
    mappings_df = pd.read_csv('data/espn_team_mappings.csv')
    print(f"   ✓ Loaded {len(mappings_df)} team mappings")
    
    # Create lookup dictionary
    name_to_canonical = {}
    for _, row in mappings_df.iterrows():
        name_to_canonical[row['database_name']] = row['canonical_name']
    
    print(f"   ✓ Created mapping dictionary")
except FileNotFoundError:
    print("   ❌ Error: data/espn_team_mappings.csv not found")
    print("   Run sync_espn_teams.py first!")
    sys.exit(1)

# Step 2: Connect to database
print("\n2. Connecting to database...")
db = get_db_connection()

# Step 3: Add canonical columns if they don't exist
print("\n3. Adding canonical columns to games table...")
try:
    # Check if columns already exist
    existing_cols = db.fetch_one("SELECT * FROM games LIMIT 1")
    
    if 'home_team_canonical' not in existing_cols:
        db.execute("ALTER TABLE games ADD COLUMN home_team_canonical VARCHAR")
        print("   ✓ Added home_team_canonical column")
    else:
        print("   ℹ️  home_team_canonical column already exists")
    
    if 'away_team_canonical' not in existing_cols:
        db.execute("ALTER TABLE games ADD COLUMN away_team_canonical VARCHAR")
        print("   ✓ Added away_team_canonical column")
    else:
        print("   ℹ️  away_team_canonical column already exists")
        
except Exception as e:
    print(f"   ❌ Error adding columns: {e}")
    sys.exit(1)

# Step 4: Get all games that need canonical names
print("\n4. Fetching games to update...")
games = db.fetch_all("""
    SELECT game_id, home_team, away_team, 
           home_team_canonical, away_team_canonical
    FROM games
    ORDER BY date DESC
""")
print(f"   ✓ Found {len(games)} games")

# Step 5: Apply mappings
print("\n5. Applying canonical name mappings...")

updates = []
mapped_count = 0
unmapped_home = set()
unmapped_away = set()

for game in games:
    home_canonical = name_to_canonical.get(game['home_team'], game['home_team'])
    away_canonical = name_to_canonical.get(game['away_team'], game['away_team'])
    
    # Track if we found mappings
    if game['home_team'] in name_to_canonical:
        mapped_count += 1
    else:
        unmapped_home.add(game['home_team'])
    
    if game['away_team'] in name_to_canonical:
        mapped_count += 1
    else:
        unmapped_away.add(game['away_team'])
    
    # Only update if changed or currently NULL
    if home_canonical != game.get('home_team_canonical') or \
       away_canonical != game.get('away_team_canonical'):
        updates.append({
            'game_id': game['game_id'],
            'home_canonical': home_canonical,
            'away_canonical': away_canonical
        })

print(f"   ✓ Found {mapped_count} team references with mappings")
print(f"   ℹ️  {len(updates)} games need updates")

if unmapped_home or unmapped_away:
    all_unmapped = unmapped_home.union(unmapped_away)
    print(f"   ⚠️  {len(all_unmapped)} unique team names without mappings")
    if len(all_unmapped) <= 10:
        print("      Unmapped teams:", ', '.join(sorted(all_unmapped)[:10]))

# Step 6: Apply updates
print("\n6. Updating database...")
if updates:
    update_query = """
        UPDATE games 
        SET home_team_canonical = ?,
            away_team_canonical = ?
        WHERE game_id = ?
    """
    
    batch_size = 100
    updated = 0
    
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        with db.transaction() as conn:
            for update in batch:
                conn.execute(update_query, (
                    update['home_canonical'],
                    update['away_canonical'],
                    update['game_id']
                ))
        updated += len(batch)
        if updated % 1000 == 0:
            print(f"   Progress: {updated}/{len(updates)} games updated...")
    
    print(f"   ✓ Updated {updated} games")
else:
    print("   ℹ️  No updates needed - all games already have canonical names")

# Step 7: Verify results
print("\n7. Verifying updates...")
verification = db.fetch_one("""
    SELECT 
        COUNT(*) as total_games,
        COUNT(DISTINCT home_team) as unique_original_home,
        COUNT(DISTINCT away_team) as unique_original_away,
        COUNT(DISTINCT home_team_canonical) as unique_canonical_home,
        COUNT(DISTINCT away_team_canonical) as unique_canonical_away
    FROM games
""")

print(f"   Total games: {verification['total_games']}")
print(f"   Unique original names: {verification['unique_original_home'] + verification['unique_original_away']}")
print(f"   Unique canonical names: {verification['unique_canonical_home'] + verification['unique_canonical_away']}")
print(f"   Reduction: {(verification['unique_original_home'] + verification['unique_original_away']) - (verification['unique_canonical_home'] + verification['unique_canonical_away'])} duplicate names eliminated")

# Step 8: Show examples
print("\n8. Sample mappings applied:")
examples = db.fetch_all("""
    SELECT home_team, home_team_canonical, away_team, away_team_canonical
    FROM games
    WHERE home_team != home_team_canonical 
       OR away_team != away_team_canonical
    LIMIT 10
""")

for ex in examples:
    if ex['home_team'] != ex['home_team_canonical']:
        print(f"   '{ex['home_team']}' → '{ex['home_team_canonical']}'")
    if ex['away_team'] != ex['away_team_canonical']:
        print(f"   '{ex['away_team']}' → '{ex['away_team_canonical']}'")

# Step 9: Update predictions table to use canonical names
print("\n9. Updating predictions to use canonical names...")
try:
    pred_update = db.execute("""
        UPDATE predictions p
        SET predicted_winner = g.home_team_canonical
        FROM games g
        WHERE p.game_id = g.game_id 
          AND p.predicted_winner = g.home_team
          AND g.home_team != g.home_team_canonical
    """)
    
    pred_update2 = db.execute("""
        UPDATE predictions p
        SET predicted_winner = g.away_team_canonical
        FROM games g
        WHERE p.game_id = g.game_id 
          AND p.predicted_winner = g.away_team
          AND g.away_team != g.away_team_canonical
    """)
    
    print("   ✓ Updated predictions table")
except Exception as e:
    print(f"   ⚠️  Could not update predictions: {e}")

print("\n" + "="*80)
print("✅ CANONICAL NAMES APPLIED SUCCESSFULLY")
print("="*80)
print()
print("📝 Next Steps:")
print("1. Update export scripts to use canonical names")
print("2. Update prediction code to use canonical names")
print("3. Re-run daily_pipeline_db.py to regenerate predictions")
print("4. Export fresh data with canonical names")
print()
print("💾 Data Preserved:")
print("   - Original names: home_team, away_team")
print("   - Canonical names: home_team_canonical, away_team_canonical")
print("   - Both available for reference and rollback")

db.close()
