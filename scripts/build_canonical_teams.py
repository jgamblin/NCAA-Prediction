#!/usr/bin/env python3
"""
Build canonical D1 basketball teams list from Wikipedia.
This becomes the single source of truth for team names and creates mappings
for all the various name variations used in data sources.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from bs4 import BeautifulSoup
import pandas as pd
from backend.database import get_db_connection
import re

print("="*80)
print("BUILDING CANONICAL D1 TEAMS LIST")
print("="*80)
print()

# Step 1: Scrape Wikipedia for official D1 teams list
print("1. Fetching official D1 teams from Wikipedia...")
url = "https://en.wikipedia.org/wiki/List_of_NCAA_Division_I_men%27s_basketball_programs"

try:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the main table with team data
    tables = soup.find_all('table', class_='wikitable')
    
    d1_teams = []
    for table in tables:
        rows = table.find_all('tr')[1:]  # Skip header
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                # Typically: School, Team Name, City, State, Founded, etc.
                school = cells[0].get_text(strip=True)
                team = cells[1].get_text(strip=True) if len(cells) > 1 else school
                
                # Clean up the name
                school = re.sub(r'\[.*?\]', '', school)  # Remove references
                team = re.sub(r'\[.*?\]', '', team)
                
                if school and school not in ['School', 'Team']:
                    d1_teams.append({
                        'school': school,
                        'team_name': team,
                        'canonical_name': school  # Use school name as canonical
                    })
    
    print(f"   ✓ Found {len(d1_teams)} D1 teams from Wikipedia")
    
except Exception as e:
    print(f"   ❌ Error fetching from Wikipedia: {e}")
    print("   Creating manual list of major D1 teams instead...")
    
    # Fallback: Manual list of major D1 teams
    major_teams = [
        "Duke", "North Carolina", "Kansas", "Kentucky", "UCLA", "Indiana",
        "Michigan State", "Louisville", "Syracuse", "Arizona", "Connecticut",
        "Villanova", "Florida", "Ohio State", "Michigan", "Illinois", "Wisconsin",
        "Gonzaga", "Houston", "Purdue", "Tennessee", "Alabama", "Auburn",
        "Arkansas", "Baylor", "Texas", "Oklahoma", "Virginia", "Miami",
        "Clemson", "Wake Forest", "NC State", "Virginia Tech", "Georgia Tech",
        "Pittsburgh", "Boston College", "Notre Dame", "Marquette", "Creighton",
        "Xavier", "Butler", "Providence", "Seton Hall", "Georgetown", "St. John's",
        "Memphis", "Cincinnati", "Wichita State", "Temple", "South Florida",
        "East Carolina", "Tulane", "SMU", "San Diego State", "New Mexico",
        "Nevada", "UNLV", "Boise State", "Colorado State", "Air Force",
        "BYU", "Utah", "Stanford", "California", "Oregon", "Oregon State",
        "Washington", "Washington State", "USC", "Arizona State", "Colorado",
        "Iowa", "Iowa State", "Minnesota", "Nebraska", "Northwestern",
        "Penn State", "Rutgers", "Maryland", "West Virginia", "TCU",
        "Texas Tech", "Kansas State", "Oklahoma State", "Missouri", "LSU",
        "Mississippi State", "Ole Miss", "Texas A&M", "South Carolina", "Georgia",
        "Florida State", "Vanderbilt", "Saint Mary's", "Santa Clara", "Loyola Marymount"
    ]
    
    d1_teams = [{'school': team, 'team_name': team, 'canonical_name': team} for team in major_teams]
    print(f"   ✓ Created list of {len(d1_teams)} major D1 teams")

# Step 2: Get all unique team names from our database
print("\n2. Analyzing team names in database...")
db = get_db_connection()

# Get all unique team names from games
query = """
    SELECT DISTINCT team_name, COUNT(*) as game_count
    FROM (
        SELECT home_team as team_name FROM games
        UNION ALL
        SELECT away_team as team_name FROM games
    )
    GROUP BY team_name
    ORDER BY game_count DESC
"""

db_teams = db.fetch_all(query)
print(f"   ✓ Found {len(db_teams)} unique team names in database")
print(f"   Top 10 by games played:")
for i, team in enumerate(db_teams[:10], 1):
    print(f"      {i}. {team['team_name']} ({team['game_count']} games)")

# Step 3: Create name mapping recommendations
print("\n3. Creating name normalization mappings...")

# Simple fuzzy matching for now
def normalize_name(name):
    """Normalize a team name for matching"""
    # Remove common suffixes
    name = re.sub(r'\s+(Crimson Tide|Tar Heels|Blue Devils|Wildcats|Bruins|'
                  r'Hoosiers|Spartans|Cardinals|Orange|Wildcats|Huskies|'
                  r'Volunteers|Bulldogs|Tigers|Razorbacks|Bears|Longhorns|'
                  r'Sooners|Cavaliers|Hurricanes|Demon Deacons|Wolfpack|'
                  r'Hokies|Yellow Jackets|Panthers|Eagles|Fighting Irish|'
                  r'Golden Eagles|Bluejays|Musketeers|Friars|Pirates|Hoyas|'
                  r'Red Storm|Rebels|Bearcats|Shockers|Owls|Bulls|Pirates|'
                  r'Mustangs|Aztecs|Lobos|Wolf Pack|Rebels|Broncos|Rams|'
                  r'Falcons|Cougars|Utes|Cardinal|Bears|Ducks|Beavers|'
                  r'Huskies|Trojans|Sun Devils|Buffaloes|Hawkeyes|Cyclones|'
                  r'Golden Gophers|Cornhuskers|Wildcats|Nittany Lions|'
                  r'Scarlet Knights|Terrapins|Mountaineers|Horned Frogs|'
                  r'Red Raiders|Aggies|Gamecocks|Bulldogs|Seminoles|'
                  r'Commodores|Gaels|Broncos|Lions)$', '', name, flags=re.IGNORECASE)
    
    # Remove "University of", "State", etc.
    name = re.sub(r'^(University of|The|College of)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+(University|State|College)$', '', name, flags=re.IGNORECASE)
    
    # Standardize common abbreviations
    replacements = {
        'UConn': 'Connecticut',
        'UNC': 'North Carolina',
        'UCLA': 'UCLA',  # Keep as is
        'UNLV': 'UNLV',  # Keep as is
        'USC': 'USC',    # Keep as is
        'SMU': 'SMU',    # Keep as is
        'BYU': 'BYU',    # Keep as is
        'TCU': 'TCU',    # Keep as is
        'LSU': 'LSU',    # Keep as is
    }
    
    for abbr, full in replacements.items():
        if name.upper() == abbr.upper():
            return full
    
    return name.strip()

# Create mappings
mappings = []
for db_team in db_teams:
    db_name = db_team['team_name']
    normalized = normalize_name(db_name)
    
    # Try to find match in D1 list
    matched = False
    for d1_team in d1_teams:
        if normalized.lower() == d1_team['canonical_name'].lower() or \
           normalized.lower() in d1_team['canonical_name'].lower() or \
           d1_team['canonical_name'].lower() in normalized.lower():
            mappings.append({
                'raw_name': db_name,
                'canonical_name': d1_team['canonical_name'],
                'confidence': 'high',
                'game_count': db_team['game_count']
            })
            matched = True
            break
    
    if not matched and db_team['game_count'] > 5:  # Only care about teams with >5 games
        mappings.append({
            'raw_name': db_name,
            'canonical_name': normalized,
            'confidence': 'low',
            'game_count': db_team['game_count']
        })

print(f"   ✓ Created {len(mappings)} name mappings")
print(f"   High confidence: {sum(1 for m in mappings if m['confidence'] == 'high')}")
print(f"   Low confidence: {sum(1 for m in mappings if m['confidence'] == 'low')}")

# Step 4: Save mappings
print("\n4. Saving team mappings...")

mappings_df = pd.DataFrame(mappings)
mappings_df.to_csv('data/team_name_mappings.csv', index=False)
print(f"   ✓ Saved to data/team_name_mappings.csv")

# Step 5: Save canonical D1 teams list
d1_teams_df = pd.DataFrame(d1_teams)
d1_teams_df.to_csv('data/d1_teams_canonical.csv', index=False)
print(f"   ✓ Saved canonical D1 list to data/d1_teams_canonical.csv")

# Step 6: Show stats
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Canonical D1 Teams: {len(d1_teams)}")
print(f"Raw team names in DB: {len(db_teams)}")
print(f"Name mappings created: {len(mappings)}")
print()
print("📝 Next Steps:")
print("1. Review data/team_name_mappings.csv for accuracy")
print("2. Manually fix any low-confidence mappings")
print("3. Run normalize_team_names.py to apply mappings to database")
print("4. Re-export data with normalized names")

db.close()
