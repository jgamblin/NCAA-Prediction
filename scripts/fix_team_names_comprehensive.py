#!/usr/bin/env python3
"""
Comprehensive team name normalization for the entire database.

This script:
1. Finds all team name variations in the database
2. Identifies likely duplicates (same base name with/without mascot)
3. Builds a mapping of ESPN aliases to canonical names
4. Re-normalizes ALL games in the database
5. Consolidates team records
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data_collection'))

import duckdb
from pathlib import Path
from team_name_utils import normalize_team_name
from collections import defaultdict

def analyze_team_duplicates(conn):
    """Find potential duplicate teams (base name with/without mascot)."""
    
    # Get all teams and their game counts
    result = conn.execute('''
        SELECT 
            t.display_name,
            COUNT(DISTINCT CASE WHEN g.game_status = 'Final' THEN g.game_id END) as completed_games,
            COUNT(DISTINCT g.game_id) as total_games
        FROM teams t
        LEFT JOIN games g ON (t.team_id = g.home_team_id OR t.team_id = g.away_team_id)
        GROUP BY t.display_name
        HAVING total_games > 0
        ORDER BY t.display_name
    ''').fetchall()
    
    teams_by_normalized = defaultdict(list)
    
    # Group teams by their normalized names
    for display_name, completed, total in result:
        normalized = normalize_team_name(display_name)
        teams_by_normalized[normalized].append({
            'display_name': display_name,
            'completed_games': completed,
            'total_games': total,
            'normalized': normalized
        })
    
    # Find duplicates (multiple display names normalizing to same base)
    duplicates = {}
    aliases_found = {}
    
    for normalized, team_list in teams_by_normalized.items():
        if len(team_list) > 1:
            # Sort by game count to find the canonical name (most games)
            team_list.sort(key=lambda x: x['completed_games'], reverse=True)
            canonical = team_list[0]
            
            duplicates[normalized] = team_list
            
            # Map aliases to canonical
            for team in team_list[1:]:
                aliases_found[team['display_name']] = canonical['display_name']
    
    return duplicates, aliases_found, teams_by_normalized


def print_duplicate_analysis(duplicates):
    """Print analysis of duplicate teams."""
    print("\n" + "="*80)
    print("DUPLICATE TEAM ANALYSIS")
    print("="*80)
    print(f"\nFound {len(duplicates)} teams with multiple name variations\n")
    
    # Sort by total games across all variations
    sorted_dupes = sorted(
        duplicates.items(),
        key=lambda x: sum(t['total_games'] for t in x[1]),
        reverse=True
    )
    
    for normalized, team_list in sorted_dupes[:30]:  # Show top 30
        total_games = sum(t['completed_games'] for t in team_list)
        print(f"\n{normalized} ({total_games} total games):")
        for team in team_list:
            marker = "✓ CANONICAL" if team == team_list[0] else "  → alias"
            print(f"  {marker:15} {team['display_name']:50} {team['completed_games']:3} games")


def create_alias_map_file(aliases_found, output_path='data/espn_alias_map.json'):
    """Create/update the ESPN alias map JSON file."""
    import json
    
    # Load existing map if it exists
    existing_map = {}
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data = json.load(f)
            existing_map = data.get('alias_to_canonical', {})
    
    # Merge with new findings
    existing_map.update(aliases_found)
    
    # Save updated map
    output_data = {
        'alias_to_canonical': existing_map,
        'description': 'ESPN team name aliases mapped to canonical database names',
        'auto_generated': True,
        'total_aliases': len(existing_map)
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, sort_keys=True)
    
    print(f"\n✓ Saved {len(existing_map)} aliases to {output_path}")


def renormalize_all_games(conn):
    """Re-normalize all team names in the games table."""
    
    print("\n" + "="*80)
    print("RE-NORMALIZING ALL GAMES")
    print("="*80)
    
    # Get all unique team names from games
    result = conn.execute('''
        SELECT DISTINCT home_team FROM games
        UNION
        SELECT DISTINCT away_team FROM games
    ''').fetchall()
    
    team_names = [r[0] for r in result]
    print(f"\nFound {len(team_names)} unique team names in games table")
    
    # Create normalization mapping
    normalization_map = {}
    changed_count = 0
    
    for team_name in team_names:
        normalized = normalize_team_name(team_name)
        if normalized != team_name:
            normalization_map[team_name] = normalized
            changed_count += 1
    
    print(f"Will normalize {changed_count} team names\n")
    
    if changed_count == 0:
        print("✓ All team names already normalized!")
        return
    
    # Show examples
    print("Examples of normalizations:")
    for i, (old, new) in enumerate(list(normalization_map.items())[:10]):
        print(f"  {old:50} → {new}")
    if len(normalization_map) > 10:
        print(f"  ... and {len(normalization_map) - 10} more")
    
    # Update games table
    print("\nUpdating games table...")
    update_count = 0
    for old_name, new_name in normalization_map.items():
        conn.execute('''
            UPDATE games 
            SET home_team = ? 
            WHERE home_team = ?
        ''', [new_name, old_name])
        
        conn.execute('''
            UPDATE games 
            SET away_team = ? 
            WHERE away_team = ?
        ''', [new_name, old_name])
        
        update_count += 1
        if update_count % 50 == 0:
            print(f"  Updated {update_count}/{len(normalization_map)} teams...")
    
    print(f"✓ Updated all {update_count} team names in games table")


def consolidate_team_records(conn):
    """Consolidate duplicate team records in teams table."""
    
    print("\n" + "="*80)
    print("CONSOLIDATING TEAM RECORDS")
    print("="*80)
    
    # Get all teams
    result = conn.execute('''
        SELECT team_id, display_name
        FROM teams
        ORDER BY display_name
    ''').fetchall()
    
    teams_by_normalized = defaultdict(list)
    for team_id, display_name in result:
        normalized = normalize_team_name(display_name)
        teams_by_normalized[normalized].append({
            'team_id': team_id,
            'display_name': display_name,
            'normalized': normalized
        })
    
    # Find duplicates in teams table
    duplicates_found = 0
    for normalized, team_list in teams_by_normalized.items():
        if len(team_list) > 1:
            duplicates_found += 1
            # Keep the first one, update display_name to normalized
            canonical_id = team_list[0]['team_id']
            
            conn.execute('''
                UPDATE teams
                SET display_name = ?
                WHERE team_id = ?
            ''', [normalized, canonical_id])
            
            # Delete duplicates
            for team in team_list[1:]:
                conn.execute('''
                    DELETE FROM teams
                    WHERE team_id = ?
                ''', [team['team_id']])
    
    if duplicates_found > 0:
        print(f"✓ Consolidated {duplicates_found} duplicate team records")
    else:
        print("✓ No duplicate team records found")


def main():
    """Run comprehensive team name fix."""
    
    db_path = Path(__file__).parent.parent / 'data' / 'ncaa_predictions.duckdb'
    
    print("="*80)
    print("COMPREHENSIVE TEAM NAME NORMALIZATION")
    print("="*80)
    print(f"\nDatabase: {db_path}\n")
    
    conn = duckdb.connect(str(db_path))
    
    # Step 1: Analyze duplicates
    print("Step 1: Analyzing duplicate team names...")
    duplicates, aliases_found, teams_by_norm = analyze_team_duplicates(conn)
    
    print_duplicate_analysis(duplicates)
    
    print(f"\n\nSummary:")
    print(f"  Total unique teams: {len(teams_by_norm)}")
    print(f"  Teams with aliases: {len(duplicates)}")
    print(f"  Total aliases found: {len(aliases_found)}")
    
    # Step 2: Create alias map
    print("\n\nStep 2: Creating ESPN alias map...")
    create_alias_map_file(aliases_found)
    
    # Step 3: Re-normalize all games
    print("\n\nStep 3: Re-normalizing all games in database...")
    renormalize_all_games(conn)
    
    # Step 4: Consolidate team records
    print("\n\nStep 4: Consolidating team records...")
    consolidate_team_records(conn)
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ COMPREHENSIVE NORMALIZATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("  1. Re-run the daily pipeline to regenerate predictions")
    print("  2. Export to JSON for frontend")
    print("  3. Verify prediction coverage improved\n")


if __name__ == '__main__':
    main()
