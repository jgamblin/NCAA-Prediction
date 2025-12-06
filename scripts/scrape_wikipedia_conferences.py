#!/usr/bin/env python3
"""
Scrape conference data from Wikipedia's List of NCAA Division I men's basketball programs.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from bs4 import BeautifulSoup
import pandas as pd

print("="*80)
print("SCRAPING NCAA D1 CONFERENCES FROM WIKIPEDIA")
print("="*80)
print()

# Step 1: Fetch Wikipedia page
print("1. Fetching Wikipedia page...")
url = "https://en.wikipedia.org/wiki/List_of_NCAA_Division_I_men%27s_basketball_programs"

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    print("   ✓ Page fetched successfully")
except Exception as e:
    print(f"   ❌ Error fetching page: {e}")
    sys.exit(1)

# Step 2: Parse HTML
print("\n2. Parsing HTML...")
soup = BeautifulSoup(response.content, 'html.parser')

# Step 3: Extract teams and conferences
print("\n3. Extracting team and conference data...")

teams_data = []

# Find all tables with class "wikitable"
tables = soup.find_all('table', {'class': 'wikitable'})
print(f"   Found {len(tables)} tables")

for table in tables:
    # Look for conference headers (usually in <caption> or header rows)
    caption = table.find('caption')
    if caption:
        conference_name = caption.get_text(strip=True)
        # Clean up conference name
        if 'Conference' in conference_name or 'conference' in conference_name:
            # Extract just the conference name
            conference_name = conference_name.split('[')[0].strip()
            
            # Get all rows in this table
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell is usually the school name
                    school_cell = cells[0]
                    
                    # Try to get the link text (cleaner than cell text)
                    link = school_cell.find('a')
                    if link:
                        school_name = link.get_text(strip=True)
                    else:
                        school_name = school_cell.get_text(strip=True)
                    
                    # Clean up school name
                    school_name = school_name.split('[')[0].strip()
                    
                    if school_name and len(school_name) > 2:
                        teams_data.append({
                            'school': school_name,
                            'conference': conference_name
                        })

print(f"   ✓ Extracted {len(teams_data)} teams from tables")

# Step 4: Load existing canonical team names
print("\n4. Loading canonical team mappings...")
try:
    mappings_df = pd.read_csv('data/espn_team_mappings.csv')
    canonical_names = set(mappings_df['canonical_name'].unique())
    print(f"   ✓ Loaded {len(canonical_names)} canonical team names")
except Exception as e:
    print(f"   ⚠️  Could not load mappings: {e}")
    canonical_names = set()

# Step 5: Match Wikipedia names to canonical names
print("\n5. Matching Wikipedia names to canonical names...")

# Create mapping helpers
def normalize_for_matching(name):
    """Normalize name for fuzzy matching."""
    name = name.lower()
    # Remove common suffixes
    for suffix in [' university', ' college', ' state', ' tech', ' institute']:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    return name

# Build lookup
canonical_lookup = {normalize_for_matching(name): name for name in canonical_names}

matched_teams = []
unmatched_teams = []

for team in teams_data:
    wiki_name = team['school']
    normalized = normalize_for_matching(wiki_name)
    
    # Try exact match first
    if wiki_name in canonical_names:
        matched_teams.append({
            'canonical_name': wiki_name,
            'conference': team['conference']
        })
    # Try normalized match
    elif normalized in canonical_lookup:
        matched_teams.append({
            'canonical_name': canonical_lookup[normalized],
            'conference': team['conference']
        })
    # Try partial match
    else:
        found = False
        for canonical in canonical_names:
            if normalized in normalize_for_matching(canonical) or \
               normalize_for_matching(canonical) in normalized:
                matched_teams.append({
                    'canonical_name': canonical,
                    'conference': team['conference']
                })
                found = True
                break
        
        if not found:
            unmatched_teams.append(team)

print(f"   ✓ Matched {len(matched_teams)} teams")
print(f"   ⚠️  {len(unmatched_teams)} teams not matched")

# Step 6: Load existing conference data and merge
print("\n6. Merging with existing conference data...")

try:
    existing_df = pd.read_csv('data/team_conferences.csv')
    existing_dict = dict(zip(existing_df['canonical_name'], existing_df['conference']))
    print(f"   ✓ Loaded {len(existing_dict)} existing mappings")
except FileNotFoundError:
    existing_dict = {}
    print("   ℹ️  No existing file, will create new one")

# Merge new data with existing (new data takes precedence)
for team in matched_teams:
    existing_dict[team['canonical_name']] = team['conference']

# Step 7: Save updated conference data
print("\n7. Saving updated conference data...")

final_df = pd.DataFrame([
    {'canonical_name': name, 'conference': conf}
    for name, conf in sorted(existing_dict.items())
])

final_df.to_csv('data/team_conferences.csv', index=False)
print(f"   ✓ Saved {len(final_df)} teams to team_conferences.csv")

# Step 8: Show statistics
print("\n8. Conference statistics:")

conf_counts = final_df['conference'].value_counts()
for conf, count in conf_counts.head(20).items():
    print(f"   {conf:<40} {count:>3} teams")

if len(conf_counts) > 20:
    print(f"   ... and {len(conf_counts) - 20} more conferences")

# Step 9: Show unmatched teams
if unmatched_teams:
    print(f"\n9. Unmatched teams (for manual review):")
    print("   These Wikipedia names didn't match any canonical names:")
    for team in unmatched_teams[:20]:
        print(f"   '{team['school']}' ({team['conference']})")
    if len(unmatched_teams) > 20:
        print(f"   ... and {len(unmatched_teams) - 20} more")

print("\n" + "="*80)
print("✅ CONFERENCE DATA SCRAPED AND SAVED")
print("="*80)
print()
print(f"Summary:")
print(f"  • {len(matched_teams)} teams matched from Wikipedia")
print(f"  • {len(final_df)} total teams with conference data")
print(f"  • {len(conf_counts)} unique conferences")
print()
print("Next: Run 'python scripts/export_to_json.py' to update frontend data")
