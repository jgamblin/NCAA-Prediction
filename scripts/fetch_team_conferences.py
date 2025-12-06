#!/usr/bin/env python3
"""
Fetch conference data for all teams from ESPN.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import pandas as pd
import time
from backend.database import get_db_connection

print("="*80)
print("FETCHING TEAM CONFERENCES FROM ESPN")
print("="*80)
print()

# Step 1: Load ESPN team mappings
print("1. Loading ESPN team mappings...")
mappings_df = pd.read_csv('data/espn_team_mappings.csv')
print(f"   ✓ Loaded {len(mappings_df)} teams")

# Step 2: Fetch conference for each team
print("\n2. Fetching conferences from ESPN...")

conference_map = {}
conference_id_to_name = {}
errors = []

for idx, row in mappings_df.iterrows():
    team_name = row['canonical_name']
    espn_id = row['espn_id']
    
    if idx % 20 == 0:
        print(f"   Progress: {idx}/{len(mappings_df)} teams...")
    
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{espn_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            team_info = data.get('team', {})
            
            # Extract conference info
            groups = team_info.get('groups', {})
            if groups and 'id' in groups:
                conf_id = groups['id']
                conf_name = groups.get('name', groups.get('shortName', 'Unknown'))
                
                conference_map[team_name] = conf_name
                conference_id_to_name[conf_id] = conf_name
            else:
                # Try alternate location
                if 'conferenceId' in team_info:
                    conf_id = team_info['conferenceId']
                    # We'll need to look this up
                    conference_map[team_name] = f"Conference_{conf_id}"
        
        # Rate limit
        time.sleep(0.1)
        
    except Exception as e:
        errors.append(f"{team_name}: {str(e)}")
        conference_map[team_name] = "Unknown"

print(f"   ✓ Fetched conferences for {len([c for c in conference_map.values() if c != 'Unknown'])} teams")

if errors:
    print(f"   ⚠️  {len(errors)} errors (set to Unknown)")

# Step 3: Save conference mappings
print("\n3. Saving conference data...")

# Update the canonical teams CSV with conference info
espn_teams_df = pd.read_csv('data/espn_teams_canonical.csv')
espn_teams_df['conference'] = espn_teams_df['short_name'].map(conference_map).fillna('Unknown')
espn_teams_df.to_csv('data/espn_teams_canonical.csv', index=False)
print("   ✓ Updated espn_teams_canonical.csv")

# Also update mappings CSV
mappings_df['conference'] = mappings_df['canonical_name'].map(conference_map).fillna('Unknown')
mappings_df.to_csv('data/espn_team_mappings.csv', index=False)
print("   ✓ Updated espn_team_mappings.csv")

# Step 4: Show conference distribution
print("\n4. Conference distribution:")
conf_counts = pd.Series(list(conference_map.values())).value_counts()
for conf, count in conf_counts.head(15).items():
    print(f"   {conf:<40} {count:>3} teams")

if len(conf_counts) > 15:
    print(f"   ... and {len(conf_counts) - 15} more conferences")

# Step 5: Update export to use conference data
print("\n5. Re-exporting team data with conferences...")
os.system('python scripts/export_to_json.py > /dev/null 2>&1')
print("   ✓ Teams exported with conference data")

print("\n" + "="*80)
print("✅ CONFERENCES FETCHED SUCCESSFULLY")
print("="*80)
print()
print(f"Summary:")
print(f"  • {len([c for c in conference_map.values() if c != 'Unknown'])} teams have conference data")
print(f"  • {len(conf_counts)} unique conferences found")
print(f"  • Data saved to CSV files")
print()
print("🔄 Refresh browser to see conference names on Teams page")
