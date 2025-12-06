#!/usr/bin/env python3
"""
Sync teams from ESPN API to create canonical team list.
ESPN is the source of truth since we pull games from ESPN anyway.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import pandas as pd
from backend.database import get_db_connection
from collections import defaultdict

print("="*80)
print("SYNCING TEAMS FROM ESPN API (SOURCE OF TRUTH)")
print("="*80)
print()

# Step 1: Fetch all teams from ESPN
print("1. Fetching teams from ESPN API...")
url = "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=500"

try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    espn_teams = []
    for league in data.get('sports', [{}])[0].get('leagues', []):
        for team_data in league.get('teams', []):
            team = team_data.get('team', {})
            if team.get('isActive'):
                espn_teams.append({
                    'espn_id': team['id'],
                    'display_name': team.get('displayName', ''),
                    'short_name': team.get('shortDisplayName', ''),
                    'location': team.get('location', ''),
                    'name': team.get('name', ''),
                    'abbreviation': team.get('abbreviation', ''),
                    'color': team.get('color', ''),
                    'logo': team.get('logos', [{}])[0].get('href', '') if team.get('logos') else ''
                })
    
    print(f"   ✓ Found {len(espn_teams)} active teams from ESPN")
    
except Exception as e:
    print(f"   ❌ Error fetching from ESPN: {e}")
    sys.exit(1)

# Step 2: Analyze current database team names
print("\n2. Analyzing team names in database...")
db = get_db_connection()

query = """
    SELECT team_name, COUNT(*) as game_count
    FROM (
        SELECT home_team as team_name FROM games WHERE season = '2025-26'
        UNION ALL
        SELECT away_team as team_name FROM games WHERE season = '2025-26'
    )
    GROUP BY team_name
    ORDER BY game_count DESC
"""

db_teams = db.fetch_all(query)
print(f"   ✓ Found {len(db_teams)} unique team names in database (2025-26 season)")

# Step 3: Create automatic mappings
print("\n3. Creating team name mappings...")

mappings = []
unmatched_db_teams = []

for db_team in db_teams:
    db_name = db_team['team_name']
    db_count = db_team['game_count']
    
    # Try to find exact or partial match in ESPN teams
    matched = False
    best_match = None
    best_score = 0
    
    for espn_team in espn_teams:
        # Check for exact matches first
        if db_name == espn_team['short_name'] or \
           db_name == espn_team['display_name'] or \
           db_name == espn_team['location']:
            best_match = espn_team
            best_score = 100
            break
        
        # Check for partial matches
        score = 0
        if espn_team['short_name'].lower() in db_name.lower() or \
           db_name.lower() in espn_team['short_name'].lower():
            score = 80
        elif espn_team['location'].lower() in db_name.lower() or \
             db_name.lower() in espn_team['location'].lower():
            score = 60
        elif any(word.lower() in espn_team['short_name'].lower() 
                 for word in db_name.split() if len(word) > 3):
            score = 40
        
        if score > best_score:
            best_score = score
            best_match = espn_team
    
    if best_match and best_score >= 60:
        mappings.append({
            'database_name': db_name,
            'espn_id': best_match['espn_id'],
            'canonical_name': best_match['short_name'],
            'display_name': best_match['display_name'],
            'match_confidence': best_score,
            'game_count': db_count
        })
        matched = True
    
    if not matched and db_count > 3:
        unmatched_db_teams.append({
            'database_name': db_name,
            'game_count': db_count
        })

print(f"   ✓ Matched {len(mappings)} teams")
print(f"   ⚠️  {len(unmatched_db_teams)} unmatched teams with >3 games")

# Step 4: Show mapping results
print("\n4. Mapping Analysis:")
print(f"\n   High confidence (80-100): {sum(1 for m in mappings if m['match_confidence'] >= 80)}")
print(f"   Medium confidence (60-79): {sum(1 for m in mappings if 60 <= m['match_confidence'] < 80)}")

# Show some examples
print("\n   Sample Mappings (high confidence):")
for m in sorted(mappings, key=lambda x: x['game_count'], reverse=True)[:10]:
    if m['match_confidence'] >= 80:
        print(f"      '{m['database_name']}' → '{m['canonical_name']}' (ESPN ID: {m['espn_id']}, {m['game_count']} games)")

if unmatched_db_teams:
    print("\n   ⚠️  Unmatched teams (need manual review):")
    for u in sorted(unmatched_db_teams, key=lambda x: x['game_count'], reverse=True)[:10]:
        print(f"      '{u['database_name']}' ({u['game_count']} games)")

# Step 5: Save outputs
print("\n5. Saving results...")

# Save ESPN teams list
espn_df = pd.DataFrame(espn_teams)
espn_df.to_csv('data/espn_teams_canonical.csv', index=False)
print(f"   ✓ Saved {len(espn_teams)} ESPN teams to data/espn_teams_canonical.csv")

# Save mappings
mappings_df = pd.DataFrame(mappings)
mappings_df.to_csv('data/espn_team_mappings.csv', index=False)
print(f"   ✓ Saved {len(mappings)} mappings to data/espn_team_mappings.csv")

# Save unmatched for manual review
if unmatched_db_teams:
    unmatched_df = pd.DataFrame(unmatched_db_teams)
    unmatched_df.to_csv('data/espn_unmatched_teams.csv', index=False)
    print(f"   ⚠️  Saved {len(unmatched_db_teams)} unmatched teams to data/espn_unmatched_teams.csv")

# Step 6: Analyze potential duplicates
print("\n6. Analyzing potential duplicates...")

# Group by canonical name to find duplicates
duplicates = defaultdict(list)
for m in mappings:
    duplicates[m['canonical_name']].append(m['database_name'])

duplicate_teams = {k: v for k, v in duplicates.items() if len(v) > 1}

if duplicate_teams:
    print(f"   Found {len(duplicate_teams)} teams with multiple database names:")
    for canonical, db_names in sorted(duplicate_teams.items(), 
                                     key=lambda x: len(x[1]), 
                                     reverse=True)[:10]:
        print(f"      {canonical}: {', '.join(db_names)}")

# Step 7: Calculate cleanup impact
print("\n" + "="*80)
print("CLEANUP IMPACT")
print("="*80)

total_games = sum(m['game_count'] for m in mappings)
affected_teams = len(duplicate_teams)
merged_names = sum(len(v) - 1 for v in duplicate_teams.values())

print(f"Total games in season: {sum(t['game_count'] for t in db_teams)}")
print(f"Teams that will be merged: {merged_names}")
print(f"Unique teams after cleanup: {len(db_teams) - merged_names}")
print(f"Affected games: {total_games}")

print("\n📝 Next Steps:")
print("1. Review data/espn_team_mappings.csv")
print("2. Manually map teams in data/espn_unmatched_teams.csv")
print("3. Run apply_espn_mappings.py to update database")
print("4. Re-run pipeline to regenerate predictions with clean data")

db.close()
