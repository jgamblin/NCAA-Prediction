#!/usr/bin/env python3
"""Check normalized game data for teams not in the canonical D1 list.

Usage:
    python check_unmatched_teams.py 
        (assumes data/Completed_Games_Normalized.csv & canonical_d1_list.txt)

Options:
    --normalized data/Completed_Games_Normalized.csv
    --canonical canonical_d1_list.txt
    --generate-if-missing  (auto-create canonical_d1_list.txt from data/d1_teams_canonical_2024_25.csv if absent)

This tool helps the iterative cleaning loop:
  1. Run data_collection/normalize_teams.py (add new mappings each time).
  2. Run this checker to see what remains unmatched.
  3. Add mappings OR add missing legitimate D1 names to canonical list.
  4. Repeat until only true non-D1 teams remain.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd

DEFAULT_CANONICAL_SOURCE = Path('data/d1_teams_canonical_2024_25.csv')


def load_canonical_list(path: Path) -> set[str]:
    with path.open('r', encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}


def generate_canonical_if_missing(target: Path, source_csv: Path) -> bool:
    if target.exists():
        return False
    if not source_csv.exists():
        print(f"Cannot generate canonical list; source CSV missing: {source_csv}")
        return False
    try:
        df = pd.read_csv(source_csv)
        if 'team_name' not in df.columns:
            print(f"Source CSV lacks 'team_name' column: {source_csv}")
            return False
        names = sorted(set(df['team_name'].dropna().astype(str)))
        with target.open('w', encoding='utf-8') as f:
            for n in names:
                f.write(n + '\n')
        print(f"Generated canonical list with {len(names)} names at {target}")
        return True
    except Exception as e:
        print(f"Failed generating canonical list: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description='Report unmatched teams after normalization.')
    parser.add_argument('--normalized', default='data/Completed_Games_Normalized.csv', help='Normalized games CSV path.')
    parser.add_argument('--canonical', default='canonical_d1_list.txt', help='Text file of canonical D1 team names.')
    parser.add_argument('--generate-if-missing', action='store_true', help='Auto-create canonical file from data/d1_teams_canonical_2024_25.csv if missing.')
    args = parser.parse_args()

    normalized_path = Path(args.normalized)
    canonical_path = Path(args.canonical)

    if not normalized_path.exists():
        print(f"Error: normalized file not found: {normalized_path}\nRun data_collection/normalize_teams.py first.")
        return 1

    if args.generate_if_missing and not canonical_path.exists():
        generate_canonical_if_missing(canonical_path, DEFAULT_CANONICAL_SOURCE)

    if not canonical_path.exists():
        print(f"Error: canonical list file not found: {canonical_path}\nCreate it manually or use --generate-if-missing.")
        return 1

    canonical_names = load_canonical_list(canonical_path)
    print(f"Loaded {len(canonical_names)} canonical names.")

    try:
        df = pd.read_csv(normalized_path)
    except Exception as e:
        print(f"Failed to read normalized CSV: {e}")
        return 1

    needed_cols = {'home_team_normalized', 'away_team_normalized'}
    if not needed_cols.issubset(df.columns):
        print("Normalized columns missing. Did you run data_collection/normalize_teams.py?")
        return 1

    unique_home = set(df['home_team_normalized'])
    unique_away = set(df['away_team_normalized'])
    all_teams = unique_home | unique_away
    unmatched = sorted(all_teams - canonical_names)

    print('-' * 40)
    print(f"Total unique normalized teams: {len(all_teams)}")
    print(f"Unmatched (not in canonical list): {len(unmatched)}")
    print('-' * 40)

    for name in unmatched:
        print(name)

    # Simple heuristic suggestions: look for patterns like 'St ' or directional abbreviations.
    suggestions = []
    for name in unmatched:
        low = name.lower()
        if low.startswith('st ') or low.startswith('st.'):
            suggestions.append(name)
        elif 'state' in low and low.split()[-1] == 'state':
            suggestions.append(name)
        elif low.startswith(('w ', 'n ', 'e ', 's ')):
            suggestions.append(name)
    if suggestions:
        print('\nPotential alias candidates (heuristic subset):')
        for s in suggestions[:30]:
            print(f"  * {s}")

    print("\nNext steps:")
    print("  1. Add confirmed D1 schools missing from canonical_d1_list.txt.")
    print("  2. Add alias mappings in data_collection/normalize_teams.py (or external JSON).")
    print("  3. Re-run normalization and this checker until unmatched only contains true non-D1 teams.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
