#!/usr/bin/env python3
"""
Check conference coverage to ensure we have all teams from major conferences.
Verifies that team name normalization isn't missing any schools.
"""

import pandas as pd
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_collection.team_name_utils import normalize_team_name


# Major D1 conferences and their members (2024-25 season)
MAJOR_CONFERENCES = {
    'ACC': [
        'Boston College', 'California', 'Clemson', 'Duke', 'Florida State',
        'Georgia Tech', 'Louisville', 'Miami (FL)', 'NC State', 'North Carolina',
        'Notre Dame', 'Pittsburgh', 'SMU', 'Stanford', 'Syracuse',
        'Virginia', 'Virginia Tech', 'Wake Forest'
    ],
    'Big 12': [
        'Arizona', 'Arizona State', 'Baylor', 'BYU', 'UCF', 'Cincinnati',
        'Colorado', 'Houston', 'Iowa State', 'Kansas', 'Kansas State',
        'Oklahoma State', 'TCU', 'Texas Tech', 'Utah', 'West Virginia'
    ],
    'Big Ten': [
        'Illinois', 'Indiana', 'Iowa', 'Maryland', 'Michigan', 'Michigan State',
        'Minnesota', 'Nebraska', 'Northwestern', 'Ohio State', 'Oregon',
        'Penn State', 'Purdue', 'Rutgers', 'UCLA', 'USC', 'Washington', 'Wisconsin'
    ],
    'SEC': [
        'Alabama', 'Arkansas', 'Auburn', 'Florida', 'Georgia', 'Kentucky',
        'LSU', 'Mississippi State', 'Missouri', 'Ole Miss', 'Oklahoma',
        'South Carolina', 'Tennessee', 'Texas', 'Texas A&M', 'Vanderbilt'
    ],
    'Big East': [
        'Butler', 'Creighton', 'Connecticut', 'DePaul', 'Georgetown',
        'Marquette', 'Providence', 'Seton Hall', 'St. John\'s', 'Villanova', 'Xavier'
    ],
    'American': [
        'Charlotte', 'East Carolina', 'Florida Atlantic', 'Memphis', 'Navy',
        'North Texas', 'Rice', 'South Florida', 'Temple', 'Tulane',
        'Tulsa', 'UAB', 'UTSA', 'Wichita State'
    ],
    'Mountain West': [
        'Air Force', 'Boise State', 'Colorado State', 'Fresno State',
        'Nevada', 'New Mexico', 'San Diego State', 'San Jose State',
        'UNLV', 'Utah State', 'Wyoming'
    ],
    'Atlantic 10': [
        'Davidson', 'Dayton', 'Duquesne', 'Fordham', 'George Mason',
        'George Washington', 'La Salle', 'Loyola Chicago', 'Massachusetts',
        'Rhode Island', 'Richmond', 'Saint Joseph\'s', 'Saint Louis',
        'St. Bonaventure', 'VCU'
    ],
    'West Coast': [
        'Gonzaga', 'LMU', 'Pacific', 'Pepperdine', 'Portland',
        'Saint Mary\'s', 'San Diego', 'San Francisco', 'Santa Clara', 'Washington State'
    ],
    'Conference USA': [
        'Florida International', 'Jacksonville State', 'Kennesaw State',
        'Liberty', 'Louisiana Tech', 'Middle Tennessee', 'New Mexico State',
        'Sam Houston State', 'UTEP', 'Western Kentucky'
    ],
}


def check_conference_coverage():
    """Check which teams from major conferences are in our dataset."""
    
    # Load historical data
    completed = pd.read_csv('data/Completed_Games.csv')
    
    # Normalize all team names
    completed['home_normalized'] = completed['home_team'].apply(normalize_team_name)
    completed['away_normalized'] = completed['away_team'].apply(normalize_team_name)
    
    # Get historical data only (exclude current season)
    historical = completed[completed['season'] != '2025-26']
    
    # Get all unique teams in our dataset
    all_teams = set(list(historical['home_normalized'].unique()) + 
                   list(historical['away_normalized'].unique()))
    
    print('=' * 100)
    print('MAJOR CONFERENCE COVERAGE CHECK')
    print('=' * 100)
    print()
    
    total_expected = 0
    total_found = 0
    total_missing = 0
    total_low_data = 0
    
    all_missing = []
    all_low_data = []
    
    for conference, members in MAJOR_CONFERENCES.items():
        print(f'\n{conference} ({len(members)} teams)')
        print('-' * 100)
        
        found = []
        missing = []
        low_data = []
        
        for team in members:
            normalized = normalize_team_name(team)
            
            if normalized in all_teams:
                # Count games
                team_games = historical[
                    (historical['home_normalized'] == normalized) | 
                    (historical['away_normalized'] == normalized)
                ]
                game_count = len(team_games)
                
                if game_count >= 75:
                    found.append((team, normalized, game_count))
                else:
                    low_data.append((team, normalized, game_count))
                    all_low_data.append((conference, team, normalized, game_count))
            else:
                missing.append((team, normalized))
                all_missing.append((conference, team, normalized))
        
        # Print results for this conference
        if found:
            print(f'✓ Found {len(found)}/{len(members)} teams with ≥75 games:')
            for original, normalized, games in sorted(found, key=lambda x: x[2], reverse=True):
                if original != normalized:
                    print(f'  {original:30} → {normalized:30} {games:4} games')
                else:
                    print(f'  {original:30}   {" "*30} {games:4} games')
        
        if low_data:
            print(f'\n⚠️  Found {len(low_data)} teams with <75 games:')
            for original, normalized, games in sorted(low_data, key=lambda x: x[2], reverse=True):
                if original != normalized:
                    print(f'  {original:30} → {normalized:30} {games:4} games')
                else:
                    print(f'  {original:30}   {" "*30} {games:4} games')
        
        if missing:
            print(f'\n✗ MISSING {len(missing)} teams:')
            for original, normalized in missing:
                print(f'  {original:30} → {normalized:30} (0 games - check normalization!)')
        
        total_expected += len(members)
        total_found += len(found)
        total_missing += len(missing)
        total_low_data += len(low_data)
    
    # Summary
    print('\n' + '=' * 100)
    print('SUMMARY')
    print('=' * 100)
    print(f'Total teams in major conferences: {total_expected}')
    print(f'Found with ≥75 games:             {total_found} ({total_found/total_expected*100:.1f}%)')
    print(f'Found with <75 games:             {total_low_data} ({total_low_data/total_expected*100:.1f}%)')
    print(f'Missing (0 games):                {total_missing} ({total_missing/total_expected*100:.1f}%)')
    print()
    
    if all_missing:
        print('=' * 100)
        print('⚠️  MISSING TEAMS - NEED NORMALIZATION FIXES')
        print('=' * 100)
        for conference, team, normalized in all_missing:
            print(f'{conference:20} {team:30} → {normalized}')
        print()
    
    if all_low_data:
        print('=' * 100)
        print('LOW DATA TEAMS (<75 games)')
        print('=' * 100)
        for conference, team, normalized, games in sorted(all_low_data, key=lambda x: x[3]):
            print(f'{conference:20} {team:30} → {normalized:30} {games:4} games')
        print()
    
    return {
        'total_expected': total_expected,
        'total_found': total_found,
        'total_missing': total_missing,
        'total_low_data': total_low_data,
        'missing_teams': all_missing,
        'low_data_teams': all_low_data
    }


if __name__ == '__main__':
    results = check_conference_coverage()
    
    # Exit with error code if any teams are missing
    if results['total_missing'] > 0:
        print(f'\n❌ FAIL: {results["total_missing"]} teams are missing from dataset!')
        sys.exit(1)
    elif results['total_low_data'] > 0:
        print(f'\n⚠️  WARNING: {results["total_low_data"]} teams have <75 games')
        sys.exit(0)
    else:
        print('\n✅ SUCCESS: All major conference teams have ≥75 games!')
        sys.exit(0)
