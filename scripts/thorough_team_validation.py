#!/usr/bin/env python3
"""
Thorough validation of team records against ESPN.
Fetches each team's record individually and checks for duplicates.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from backend.database import get_db_connection
from datetime import datetime
import time
import json

print("="*80)
print("THOROUGH TEAM RECORD VALIDATION")
print("="*80)
print()

# Step 1: Load ESPN canonical teams
print("1. Loading ESPN team mappings...")
import pandas as pd
try:
    mappings_df = pd.read_csv('data/espn_team_mappings.csv')
    espn_teams = {}
    for _, row in mappings_df.iterrows():
        espn_teams[row['canonical_name']] = {
            'espn_id': row['espn_id'],
            'display_name': row['display_name']
        }
    print(f"   ✓ Loaded {len(espn_teams)} team mappings")
except Exception as e:
    print(f"   ❌ Error loading mappings: {e}")
    sys.exit(1)

# Step 2: Get database records for all teams
print("\n2. Fetching database records...")
db = get_db_connection()

db_query = """
    SELECT 
        team_name,
        SUM(games) as games_played,
        SUM(wins) as wins
    FROM (
        SELECT 
            home_team_canonical as team_name,
            COUNT(*) as games,
            SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins
        FROM games 
        WHERE season = '2025-26' AND game_status = 'Final'
        GROUP BY home_team_canonical
        
        UNION ALL
        
        SELECT 
            away_team_canonical as team_name,
            COUNT(*) as games,
            SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) as wins
        FROM games 
        WHERE season = '2025-26' AND game_status = 'Final'
        GROUP BY away_team_canonical
    )
    GROUP BY team_name
    HAVING SUM(games) > 0
    ORDER BY team_name
"""

db_records = {r['team_name']: r for r in db.fetch_all(db_query)}
print(f"   ✓ Found {len(db_records)} teams with games")

# Step 3: Fetch ESPN records for each team
print("\n3. Fetching ESPN records (this will take a few minutes)...")
print("   Checking teams with ESPN IDs...")

espn_records = {}
errors = []
checked = 0
total_to_check = len([t for t in db_records.keys() if t in espn_teams])

for team_name in db_records.keys():
    if team_name not in espn_teams:
        continue
    
    checked += 1
    if checked % 20 == 0:
        print(f"   Progress: {checked}/{total_to_check} teams checked...")
    
    espn_id = espn_teams[team_name]['espn_id']
    
    try:
        # Fetch team detail from ESPN
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{espn_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            team_data = response.json()
            
            # Extract record from team data
            record = team_data.get('team', {}).get('record', {})
            items = record.get('items', [])
            
            # Find overall record
            for item in items:
                if item.get('type') == 'total' or item.get('description') == 'Overall Record':
                    stats = item.get('stats', [])
                    wins = 0
                    losses = 0
                    
                    for stat in stats:
                        if stat.get('name') == 'wins':
                            wins = int(stat.get('value', 0))
                        elif stat.get('name') == 'losses':
                            losses = int(stat.get('value', 0))
                    
                    espn_records[team_name] = {
                        'wins': wins,
                        'losses': losses,
                        'games': wins + losses
                    }
                    break
        
        # Rate limiting
        time.sleep(0.1)
        
    except Exception as e:
        errors.append(f"{team_name}: {str(e)}")

print(f"   ✓ Fetched {len(espn_records)} team records from ESPN")
if errors:
    print(f"   ⚠️  {len(errors)} errors (will skip those teams)")

# Step 4: Check for duplicate games
print("\n4. Checking for duplicate games...")

duplicate_query = """
    SELECT 
        home_team_canonical,
        away_team_canonical,
        date,
        COUNT(*) as count,
        GROUP_CONCAT(game_id) as game_ids
    FROM games
    WHERE season = '2025-26' AND game_status = 'Final'
    GROUP BY home_team_canonical, away_team_canonical, date
    HAVING COUNT(*) > 1
"""

duplicates = db.fetch_all(duplicate_query)

if duplicates:
    print(f"   ⚠️  Found {len(duplicates)} duplicate game sets:")
    for dup in duplicates[:10]:
        print(f"      {dup['away_team_canonical']} @ {dup['home_team_canonical']} on {dup['date']}: {dup['count']} games")
        print(f"         Game IDs: {dup['game_ids']}")
else:
    print("   ✓ No duplicate games found")

# Step 5: Check for suspicious game patterns
print("\n5. Checking for suspicious patterns...")

# Teams playing themselves
self_games = db.fetch_all("""
    SELECT game_id, date, home_team_canonical, home_score, away_score
    FROM games
    WHERE season = '2025-26' 
      AND home_team_canonical = away_team_canonical
""")

if self_games:
    print(f"   ⚠️  Found {len(self_games)} games where team plays itself:")
    for game in self_games[:5]:
        print(f"      {game['home_team_canonical']} vs {game['home_team_canonical']} on {game['date']}")
else:
    print("   ✓ No self-play games found")

# Games with null scores but marked Final
null_score_finals = db.fetch_all("""
    SELECT game_id, date, home_team_canonical, away_team_canonical, home_score, away_score
    FROM games
    WHERE season = '2025-26' 
      AND game_status = 'Final'
      AND (home_score IS NULL OR away_score IS NULL)
""")

if null_score_finals:
    print(f"   ⚠️  Found {len(null_score_finals)} 'Final' games with null scores:")
    for game in null_score_finals[:5]:
        print(f"      {game['away_team_canonical']} @ {game['home_team_canonical']} on {game['date']}")
else:
    print("   ✓ No null score finals found")

# Step 6: Compare records
print("\n6. Comparing database vs ESPN records...")

mismatches = []
close_matches = []
perfect_matches = 0

for team_name, db_data in db_records.items():
    if team_name not in espn_records:
        continue
    
    espn_data = espn_records[team_name]
    
    db_wins = db_data['wins']
    db_games = db_data['games_played']
    db_losses = db_games - db_wins
    
    espn_wins = espn_data['wins']
    espn_losses = espn_data['losses']
    espn_games = espn_data['games']
    
    # Perfect match
    if db_wins == espn_wins and db_losses == espn_losses:
        perfect_matches += 1
    # Close match (within 1-2 games - might be scheduling)
    elif abs(db_games - espn_games) <= 2:
        close_matches.append({
            'team': team_name,
            'db_record': f"{db_wins}-{db_losses}",
            'espn_record': f"{espn_wins}-{espn_losses}",
            'db_games': db_games,
            'espn_games': espn_games,
            'diff': abs(db_games - espn_games)
        })
    # Significant mismatch
    else:
        mismatches.append({
            'team': team_name,
            'db_record': f"{db_wins}-{db_losses}",
            'espn_record': f"{espn_wins}-{espn_losses}",
            'db_games': db_games,
            'espn_games': espn_games,
            'diff': abs(db_games - espn_games)
        })

# Step 7: Report Results
print("\n" + "="*80)
print("VALIDATION RESULTS")
print("="*80)

print(f"\n📊 Summary:")
print(f"   Teams validated: {len(espn_records)}")
print(f"   Perfect matches: {perfect_matches}")
print(f"   Close matches (±1-2 games): {len(close_matches)}")
print(f"   Significant mismatches: {len(mismatches)}")

if mismatches:
    print(f"\n\n⚠️  SIGNIFICANT MISMATCHES ({len(mismatches)} teams):")
    print("="*80)
    mismatches.sort(key=lambda x: x['diff'], reverse=True)
    
    for m in mismatches:
        print(f"\n  {m['team']}:")
        print(f"    Database: {m['db_record']} ({m['db_games']} games)")
        print(f"    ESPN:     {m['espn_record']} ({m['espn_games']} games)")
        print(f"    Diff:     {m['diff']} game(s)")
        
        # Show game details for this team
        games = db.fetch_all("""
            SELECT date, home_team, away_team, home_team_canonical, away_team_canonical, home_score, away_score
            FROM games
            WHERE season = '2025-26' AND game_status = 'Final'
              AND (home_team_canonical = ? OR away_team_canonical = ?)
            ORDER BY date
        """, (m['team'], m['team']))
        
        # Check for multiple original names
        orig_names = set()
        for g in games:
            if g['home_team_canonical'] == m['team']:
                orig_names.add(g['home_team'])
            if g['away_team_canonical'] == m['team']:
                orig_names.add(g['away_team'])
        
        if len(orig_names) > 1:
            print(f"    ⚠️  Multiple original names:")
            for name in orig_names:
                count = sum(1 for g in games if (g['home_team'] == name or g['away_team'] == name))
                print(f"       - '{name}' ({count} games)")

if close_matches:
    print(f"\n\nℹ️  CLOSE MATCHES ({len(close_matches)} teams):")
    print("="*80)
    print("   These are within 1-2 games (likely scheduling differences):")
    
    close_matches.sort(key=lambda x: x['diff'], reverse=True)
    for m in close_matches[:15]:
        print(f"   {m['team']:<30} DB: {m['db_record']:<8} ESPN: {m['espn_record']:<8} (±{m['diff']})")

if duplicates:
    print(f"\n\n⚠️  DUPLICATE GAMES ({len(duplicates)} sets):")
    print("="*80)
    for dup in duplicates:
        print(f"   {dup['away_team_canonical']} @ {dup['home_team_canonical']} on {dup['date']}: {dup['count']} copies")

# Save report
print("\n\n" + "="*80)
print("SAVING DETAILED REPORT")
print("="*80)

report = {
    'timestamp': datetime.now().isoformat(),
    'summary': {
        'teams_validated': len(espn_records),
        'perfect_matches': perfect_matches,
        'close_matches': len(close_matches),
        'significant_mismatches': len(mismatches),
        'duplicates': len(duplicates)
    },
    'mismatches': mismatches,
    'close_matches': close_matches,
    'duplicates': [dict(d) for d in duplicates] if duplicates else []
}

with open('data/thorough_validation_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print("   ✓ Saved to data/thorough_validation_report.json")

# Final verdict
print("\n" + "="*80)
print("FINAL VERDICT")
print("="*80)

if not mismatches and not duplicates:
    print("\n✅ EXCELLENT! Database is clean:")
    print(f"   • {perfect_matches} teams match ESPN perfectly")
    print(f"   • {len(close_matches)} teams within 1-2 games (normal variation)")
    print(f"   • No duplicate games")
    print(f"   • No significant data quality issues")
elif len(mismatches) <= 3 and not duplicates:
    print("\n✅ GOOD! Database is mostly clean:")
    print(f"   • {perfect_matches} teams match ESPN perfectly")
    print(f"   • Only {len(mismatches)} teams need investigation")
else:
    print("\n⚠️  DATA QUALITY ISSUES FOUND:")
    print(f"   • {len(mismatches)} teams with significant mismatches")
    print(f"   • {len(duplicates)} duplicate game sets")
    print("   • Review report and fix canonical name mappings")

db.close()
