#!/usr/bin/env python3
"""
Parse Wikipedia conference data from the table structure.
The table has columns: School | Nickname | Home arena | Conference | ...
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import re
import pandas as pd

print("="*80)
print("PARSING NCAA D1 CONFERENCES FROM WIKIPEDIA TABLE")
print("="*80)
print()

# Step 1: Read the Wikipedia content (provided by user)
# For this, I'll create a mapping manually from the clear table structure

# Dictionary of school name variations to conference
wikipedia_data = {}

# Parse from the table - School name is in first column, Conference in 4th column
# Format: "Full School Name (Short Name)" -> Conference

# America East
america_east_teams = [
    "Albany", "Binghamton", "Bryant", "UMaine", "UMBC", "UMass Lowell",
    "New Hampshire", "NJIT", "Vermont"
]

# American
american_teams = [
    "Charlotte", "East Carolina", "FAU", "Memphis", "North Texas", "Rice",
    "South Florida", "Temple", "UAB", "UTSA", "Tulane", "Tulsa", "Wichita St"
]

# ACC  
acc_teams = [
    "Boston College", "California", "Clemson", "Duke", "Florida St", "Georgia Tech",
    "Louisville", "Miami", "North Carolina", "NC State", "Notre Dame", "Pittsburgh",
    "SMU", "Stanford", "Syracuse", "Virginia", "Virginia Tech", "Wake Forest"
]

# ASUN
asun_teams = [
    "Austin Peay", "Bellarmine", "Central Arkansas", "Eastern Kentucky",
    "Florida Gulf Coast", "Jacksonville", "Lipscomb", "North Alabama",
    "North Florida", "Queens University", "Stetson", "West Georgia"
]

# Atlantic 10
atlantic_10_teams = [
    "Davidson", "Dayton", "Duquesne", "Fordham", "George Mason", "George Washington",
    "La Salle", "Loyola Chicago", "Rhode Island", "Richmond", "St Bonaventure",
    "St Joseph's", "Saint Louis", "VCU", "UMass"  # Added UMass here as it's in A-10 now
]

# Big East
big_east_teams = [
    "Butler", "Creighton", "DePaul", "Georgetown", "Marquette", "Providence",
    "St John's", "Seton Hall", "UConn", "Villanova", "Xavier"
]

# Big Sky
big_sky_teams = [
    "Eastern Washington", "Idaho", "Idaho St", "Montana", "Montana St",
    "Northern Arizona", "Northern Colorado", "Portland St", "Sacramento St",
    "Weber St"
]

# Big South
big_south_teams = [
    "Charleston Southern", "Gardner-Webb", "High Point", "Longwood", "Presbyterian",
    "Radford", "UNC Asheville", "USC Upstate", "Winthrop"
]

# Big Ten
big_ten_teams = [
    "UCLA", "Illinois", "Indiana", "Iowa", "Maryland", "Michigan", "Michigan St",
    "Minnesota", "Nebraska", "Northwestern", "Ohio St", "Oregon", "Penn State",
    "Purdue", "Rutgers", "USC", "Washington", "Wisconsin"
]

# Big 12
big_12_teams = [
    "Arizona", "Arizona St", "Baylor", "BYU", "UCF", "Cincinnati", "Colorado",
    "Houston", "Iowa St", "Kansas", "Kansas St", "Oklahoma St", "TCU",
    "Texas Tech", "Utah", "West Virginia"
]

# Big West
big_west_teams = [
    "Cal Poly", "CSU Bakersfield", "Cal State Fullerton", "Cal State Northridge",
    "Hawai'i", "Long Beach St", "UC Davis", "UC Irvine", "UC Riverside",
    "UC San Diego", "UC Santa Barbara"
]

# CAA
caa_teams = [
    "Campbell", "Charleston", "Drexel", "Elon", "Hampton", "Hofstra", "Monmouth",
    "North Carolina A&T", "Northeastern", "Stony Brook", "Towson", "UNC Wilmington",
    "William & Mary"
]

# Conference USA
cusa_teams = [
    "Delaware", "FIU", "Jacksonville St", "Kennesaw St", "Liberty", "Louisiana Tech",
    "Middle Tennessee", "Missouri St", "New Mexico St", "Sam Houston", "UTEP",
    "Western Kentucky"
]

# Horizon League
horizon_teams = [
    "Cleveland St", "Detroit Mercy", "IU Indy", "Milwaukee", "Northern Kentucky",
    "Oakland", "Purdue FW", "Robert Morris", "Green Bay", "Wright St", "Youngstown St"
]

# Ivy League
ivy_teams = [
    "Brown", "Columbia", "Cornell", "Dartmouth", "Harvard", "Penn", "Princeton", "Yale"
]

# MAAC
maac_teams = [
    "Canisius", "Fairfield", "Iona", "Manhattan", "Marist", "Merrimack",
    "Mount St Mary's", "Niagara", "Quinnipiac", "Rider", "Sacred Heart",
    "Saint Peter's", "Siena"
]

# MAC
mac_teams = [
    "Akron", "Ball St", "Bowling Green", "Buffalo", "Central Michigan",
    "Eastern Michigan", "Kent St", "Miami (OH)", "Northern Illinois",
    "Ohio", "Toledo", "Western Michigan"
]

# MEAC
meac_teams = [
    "Coppin St", "Delaware St", "Howard", "MD Eastern", "Morgan St",
    "Norfolk St", "North Carolina Central", "SC State"
]

# Missouri Valley
mvc_teams = [
    "Belmont", "Bradley", "Drake", "Evansville", "Illinois St", "Indiana St",
    "Murray St", "UNI", "Southern Illinois", "UIC", "Valparaiso"
]

# Mountain West
mw_teams = [
    "Air Force", "Boise St", "Colorado St", "Fresno St", "Grand Canyon",
    "Nevada", "New Mexico", "San Diego St", "San Jose St", "UNLV", "Utah St", "Wyoming"
]

# NEC
nec_teams = [
    "Central Connecticut", "Chicago St", "Fairleigh Dickinson", "Le Moyne",
    "LIU", "Mercyhurst", "New Haven", "Saint Francis", "Stonehill", "Wagner"
]

# Ohio Valley
ovc_teams = [
    "Eastern Illinois", "Lindenwood", "Little Rock", "Morehead St",
    "Southeast Missouri", "SIU Edwardsville", "Southern Indiana", "UT Martin",
    "Tennessee St", "Tennessee Tech", "Western Illinois"
]

# Patriot League
patriot_teams = [
    "American", "Army", "Boston University", "Bucknell", "Colgate", "Holy Cross",
    "Lafayette", "Lehigh", "Loyola MD", "Navy"
]

# SEC
sec_teams = [
    "Alabama", "Arkansas", "Auburn", "Florida", "Georgia", "Kentucky", "LSU",
    "Ole Miss", "Mississippi St", "Missouri", "Oklahoma", "South Carolina",
    "Tennessee", "Texas", "Texas A&M", "Vanderbilt"
]

# Southern
southern_teams = [
    "Chattanooga", "The Citadel", "ETSU", "Furman", "Mercer", "Samford",
    "UNC Greensboro", "VMI", "Western Carolina", "Wofford"
]

# Southland
southland_teams = [
    "East Texas A&M", "Hou Christian", "Incarnate Word", "Lamar", "McNeese",
    "New Orleans", "Nicholls", "Northwestern St", "SE Louisiana",
    "Stephen F Austin", "Texas A&M-CC", "UTRGV"
]

# SWAC
swac_teams = [
    "Alabama A&M", "Alabama St", "Alcorn St", "Arkansas-Pine Bluff",
    "Bethune-Cookman", "Florida A&M", "Grambling", "Jackson St",
    "Mississippi Valley St", "Prairie View", "Southern", "Texas Southern"
]

# The Summit
summit_teams = [
    "Denver", "Kansas City", "North Dakota", "North Dakota St", "Omaha",
    "Oral Roberts", "St Thomas (MN)", "South Dakota", "S Dakota St"
]

# Sun Belt
sun_belt_teams = [
    "Appalachian St", "Arkansas St", "Coastal", "Georgia Southern", "Georgia St",
    "James Madison", "Louisiana", "ULM", "Marshall", "Old Dominion",
    "South Alabama", "Southern Miss", "Texas St", "Troy"
]

# WCC
wcc_teams = [
    "Gonzaga", "Loyola Marymount", "Oregon St", "Pacific", "Pepperdine",
    "Portland", "Saint Mary's", "San Diego", "San Francisco", "Santa Clara",
    "Seattle U", "Washington St"
]

# WAC
wac_teams = [
    "Abilene Christian", "Cal Baptist", "Southern Utah", "Tarleton St",
    "Utah Tech", "Utah Valley", "UT Arlington"
]

# Combine all into one dictionary
conference_mapping = {}

for team in america_east_teams:
    conference_mapping[team] = "America East"
for team in american_teams:
    conference_mapping[team] = "American"
for team in acc_teams:
    conference_mapping[team] = "ACC"
for team in asun_teams:
    conference_mapping[team] = "ASUN"
for team in atlantic_10_teams:
    conference_mapping[team] = "Atlantic 10"
for team in big_east_teams:
    conference_mapping[team] = "Big East"
for team in big_sky_teams:
    conference_mapping[team] = "Big Sky"
for team in big_south_teams:
    conference_mapping[team] = "Big South"
for team in big_ten_teams:
    conference_mapping[team] = "Big Ten"
for team in big_12_teams:
    conference_mapping[team] = "Big 12"
for team in big_west_teams:
    conference_mapping[team] = "Big West"
for team in caa_teams:
    conference_mapping[team] = "CAA"
for team in cusa_teams:
    conference_mapping[team] = "Conference USA"
for team in horizon_teams:
    conference_mapping[team] = "Horizon"
for team in ivy_teams:
    conference_mapping[team] = "Ivy League"
for team in maac_teams:
    conference_mapping[team] = "MAAC"
for team in mac_teams:
    conference_mapping[team] = "MAC"
for team in meac_teams:
    conference_mapping[team] = "MEAC"
for team in mvc_teams:
    conference_mapping[team] = "Missouri Valley"
for team in mw_teams:
    conference_mapping[team] = "Mountain West"
for team in nec_teams:
    conference_mapping[team] = "NEC"
for team in ovc_teams:
    conference_mapping[team] = "Ohio Valley"
for team in patriot_teams:
    conference_mapping[team] = "Patriot"
for team in sec_teams:
    conference_mapping[team] = "SEC"
for team in southern_teams:
    conference_mapping[team] = "Southern"
for team in southland_teams:
    conference_mapping[team] = "Southland"
for team in swac_teams:
    conference_mapping[team] = "SWAC"
for team in summit_teams:
    conference_mapping[team] = "Summit"
for team in sun_belt_teams:
    conference_mapping[team] = "Sun Belt"
for team in wcc_teams:
    conference_mapping[team] = "WCC"
for team in wac_teams:
    conference_mapping[team] = "WAC"

print(f"1. Created mapping for {len(conference_mapping)} teams")

# Step 2: Save to CSV
print("\n2. Saving to team_conferences.csv...")

df = pd.DataFrame([
    {'canonical_name': name, 'conference': conf}
    for name, conf in sorted(conference_mapping.items())
])

df.to_csv('data/team_conferences.csv', index=False)
print(f"   ✓ Saved {len(df)} teams")

# Step 3: Show statistics
print("\n3. Conference distribution:")
conf_counts = df['conference'].value_counts()
for conf, count in conf_counts.items():
    print(f"   {conf:<25} {count:>3} teams")

print("\n" + "="*80)
print("✅ CONFERENCE DATA SAVED")
print("="*80)
print()
print(f"Total: {len(df)} D1 teams with conferences")
print()
print("Next: Run 'python scripts/export_to_json.py' to update frontend")
