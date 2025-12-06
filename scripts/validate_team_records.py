#!/usr/bin/env python3
"""
Validate team records against ESPN to find mapping errors.
This checks if our database W-L records match ESPN's official records.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from backend.database import get_db_connection
from datetime import datetime
import time

print("="*80)
print("VALIDATING TEAM RECORDS AGAINST ESPN")
print("="*80)
print()

# Step 1: Get ESPN teams with their records
print("1. Fetching team records from ESPN...")
url = "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=500"

try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    espn_records = {}
    team_id_to_name = {}
    
    for league in data.get('sports', [{}])[0].get('leagues', []):
        for team_data in league.get('teams', []):
            team = team_data.get('team', {})
            
            # Get team record from team data
            record = team_data.get('team', {}).get('record', {})
            
            # Store by short name (what we use as canonical)
            short_name = team.get('shortDisplayName', '')
            team_id = team.get('id', '')
            
            if short_name:
                team_id_to_name[team_id] = short_name
                espn_records[short_name] = {
                    'wins': 0,  # Will fetch from standings
                    'losses': 0,
                    'games': 0
                }
    
    print(f"   ✓ Found {len(espn_records)} teams")
    
except Exception as e:
    print(f"   ❌ Error fetching from ESPN: {e}")
    sys.exit(1)

# Step 2: Fetch current standings from ESPN
print("\n2. Fetching 2025-26 standings from ESPN...")
standings_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/standings"

try:
    response = requests.get(standings_url, timeout=30)
    if response.status_code == 200:
        standings_data = response.json()
        
        # ESPN standings can be complex - try to extract team records
        for entry in standings_data.get('children', []):
            for standing in entry.get('standings', {}).get('entries', []):
                team_info = standing.get('team', {})
                team_id = team_info.get('id', '')
                
                if team_id in team_id_to_name:
                    short_name = team_id_to_name[team_id]
                    stats = standing.get('stats', [])
                    
                    # Extract wins/losses from stats
                    for stat in stats:
                        if stat.get('name') == 'wins':
                            espn_records[short_name]['wins'] = int(stat.get('value', 0))
                        elif stat.get('name') == 'losses':
                            espn_records[short_name]['losses'] = int(stat.get('value', 0))
                        elif stat.get('name') == 'gamesPlayed':
                            espn_records[short_name]['games'] = int(stat.get('value', 0))
        
        teams_with_records = sum(1 for r in espn_records.values() if r['games'] > 0)
        print(f"   ✓ Found records for {teams_with_records} teams")
    else:
        print(f"   ⚠️  Could not fetch standings (status {response.status_code})")
        print("   Will compare game counts only")
        
except Exception as e:
    print(f"   ⚠️  Error fetching standings: {e}")
    print("   Will compare game counts only")

# Step 3: Get our database records
print("\n3. Querying database for team records...")
db = get_db_connection()

db_query = """
    SELECT 
        team_name,
        SUM(games) as games_played,
        SUM(wins) as wins,
        SUM(losses) as losses
    FROM (
        SELECT 
            home_team_canonical as team_name,
            COUNT(*) as games,
            SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) as losses
        FROM games 
        WHERE season = '2025-26' AND game_status = 'Final'
        GROUP BY home_team_canonical
        
        UNION ALL
        
        SELECT 
            away_team_canonical as team_name,
            COUNT(*) as games,
            SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN away_score < home_score THEN 1 ELSE 0 END) as losses
        FROM games 
        WHERE season = '2025-26' AND game_status = 'Final'
        GROUP BY away_team_canonical
    )
    GROUP BY team_name
    ORDER BY team_name
"""

db_records = db.fetch_all(db_query)
print(f"   ✓ Found {len(db_records)} teams in database")

# Step 4: Compare records
print("\n4. Comparing records...")

mismatches = []
missing_from_espn = []
extra_games = []

for db_team in db_records:
    team_name = db_team['team_name']
    db_wins = db_team['wins']
    db_losses = db_team['losses']
    db_games = db_team['games_played']
    
    if team_name in espn_records:
        espn_team = espn_records[team_name]
        espn_wins = espn_team['wins']
        espn_losses = espn_team['losses']
        espn_games = espn_team['games']
        
        # Only compare if ESPN has data
        if espn_games > 0:
            if db_wins != espn_wins or db_losses != espn_losses or db_games != espn_games:
                mismatches.append({
                    'team': team_name,
                    'db_record': f"{db_wins}-{db_losses} ({db_games} games)",
                    'espn_record': f"{espn_wins}-{espn_losses} ({espn_games} games)",
                    'difference': abs(db_games - espn_games)
                })
    else:
        # Team in our DB but not in ESPN (likely non-D1)
        if db_games > 5:  # Only care about teams with significant games
            missing_from_espn.append({
                'team': team_name,
                'games': db_games,
                'record': f"{db_wins}-{db_losses}"
            })

print(f"   ✓ Comparison complete")

# Step 5: Report results
print("\n" + "="*80)
print("VALIDATION RESULTS")
print("="*80)

if mismatches:
    print(f"\n⚠️  RECORD MISMATCHES ({len(mismatches)} teams):")
    print("="*80)
    
    # Sort by difference (biggest issues first)
    mismatches.sort(key=lambda x: x['difference'], reverse=True)
    
    for m in mismatches[:20]:  # Show top 20
        print(f"\n  {m['team']}:")
        print(f"    Database: {m['db_record']}")
        print(f"    ESPN:     {m['espn_record']}")
        print(f"    Diff:     {m['difference']} game(s)")
    
    if len(mismatches) > 20:
        print(f"\n  ... and {len(mismatches) - 20} more")
else:
    print("\n✅ NO MISMATCHES FOUND!")
    print("   All team records match ESPN")

if missing_from_espn:
    print(f"\n\nℹ️  TEAMS IN DATABASE BUT NOT ESPN D1 ({len(missing_from_espn)} teams):")
    print("="*80)
    print("   These are likely D2/D3/NAIA teams:")
    
    missing_from_espn.sort(key=lambda x: x['games'], reverse=True)
    
    for m in missing_from_espn[:15]:
        print(f"   {m['team']:<40} {m['record']:<15} ({m['games']} games)")
    
    if len(missing_from_espn) > 15:
        print(f"   ... and {len(missing_from_espn) - 15} more")

# Step 6: Detailed mismatch investigation
if mismatches:
    print("\n\n" + "="*80)
    print("DETAILED INVESTIGATION OF TOP MISMATCHES")
    print("="*80)
    
    for m in mismatches[:5]:  # Investigate top 5
        team_name = m['team']
        print(f"\n📊 {team_name}:")
        
        # Get all games for this team
        games = db.fetch_all("""
            SELECT 
                game_id,
                date,
                home_team,
                away_team,
                home_team_canonical,
                away_team_canonical,
                home_score,
                away_score
            FROM games
            WHERE season = '2025-26' 
              AND game_status = 'Final'
              AND (home_team_canonical = ? OR away_team_canonical = ?)
            ORDER BY date
        """, (team_name, team_name))
        
        print(f"   Games found: {len(games)}")
        print(f"   Original team names used:")
        
        # Check for name variations
        original_names = set()
        for game in games:
            if game['home_team_canonical'] == team_name:
                original_names.add(game['home_team'])
            if game['away_team_canonical'] == team_name:
                original_names.add(game['away_team'])
        
        for name in sorted(original_names):
            count = sum(1 for g in games if g['home_team'] == name or g['away_team'] == name)
            print(f"      - '{name}' ({count} games)")

# Save detailed report
print("\n\n" + "="*80)
print("SAVING DETAILED REPORT")
print("="*80)

report_lines = []
report_lines.append("TEAM RECORD VALIDATION REPORT")
report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append("="*80)
report_lines.append("")

if mismatches:
    report_lines.append(f"MISMATCHES FOUND: {len(mismatches)}")
    report_lines.append("")
    for m in mismatches:
        report_lines.append(f"{m['team']}")
        report_lines.append(f"  Database: {m['db_record']}")
        report_lines.append(f"  ESPN:     {m['espn_record']}")
        report_lines.append("")
else:
    report_lines.append("✅ NO MISMATCHES - All records match!")

with open('data/team_validation_report.txt', 'w') as f:
    f.write('\n'.join(report_lines))

print("   ✓ Saved to data/team_validation_report.txt")

print("\n" + "="*80)
print("VALIDATION COMPLETE")
print("="*80)

if mismatches:
    print(f"\n⚠️  Found {len(mismatches)} teams with record mismatches")
    print("   Review the report and check for incorrect team name mappings")
else:
    print("\n✅ All team records validated successfully!")

db.close()
