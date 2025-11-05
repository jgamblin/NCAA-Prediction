#!/usr/bin/env python3
"""Normalize team names in the games dataset using a manual mapping.

Usage (basic):
    python normalize_teams.py

Optional args:
    --input /path/to/Completed_Games_D1_Only.csv
    --output /path/to/Completed_Games_Normalized.csv
    --mapping-json team_name_mapping.json   # External JSON mapping (overrides / extends inline dict)
    --canonical canonical_d1_list.txt       # (Optional) file of canonical names to report unmapped D1-looking aliases

This script:
  1. Loads the games CSV.
  2. Applies textual replacements to home_team / away_team via team_name_mapping.
  3. Writes new columns home_team_normalized / away_team_normalized.
  4. Emits a small report of how many names changed and any still-suspicious aliases.

Add new aliases directly to the team_name_mapping dict or supply a JSON file with a dict of {"Bad Name": "Canonical Name"}.
The JSON file values will override duplicates in the inline dict.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Set
import pandas as pd

# --- 1. BASE TEAM NAME MAPPING (extend this over time) ---
# IMPORTANT: Only include mappings where you are certain of the Division I canonical target.
# For newly-transitioning D1 schools missing in canonical list, you can still map to their preferred form
# (e.g., 'Lindenwood' -> 'Lindenwood' once you add it to canonical_d1_list.txt later).
team_name_mapping: Dict[str, str] = {
    # Provided examples / obvious truncations:
    'St. Francis PA': 'St. Francis (PA)',
    'Mcneese': 'McNeese',
    'Miami OH': 'Miami (OH)',
    'N Arizona': 'Northern Arizona',
    'Northwestern St': 'Northwestern State',
    'N Colorado': 'Northern Colorado',
    "Mt St Mary's": "Mount St. Mary's",
    'South Dakota St': 'South Dakota State',
    "Saint Joe's": "Saint Joseph's",
    'N Illinois': 'Northern Illinois',
    "St John's": "St. John's",
    'Tennessee St': 'Tennessee State',
    'St Bonaventure': 'St. Bonaventure',
    'W Illinois': 'Western Illinois',
    'W Kentucky': 'Western Kentucky',
    'Youngstown St': 'Youngstown State',
    'Morgan St': 'Morgan State',
    'W Michigan': 'Western Michigan',
    'Washington St': 'Washington State',
    'Mount St. Mary': "Mount St. Mary's",
    'Pennsylvania': 'Penn',
    'Pitt': 'Pittsburgh',
    'UNC': 'North Carolina',
    'UVA': 'Virginia',
    'URI': 'Rhode Island',
    'UNCG': 'UNC Greensboro',
    'UNH': 'New Hampshire',
    'UCSB': 'UC Santa Barbara',
    'PV A&M': 'Prairie View A&M',
    'Kansas City': 'UMKC',
    'UM Kansas City': 'UMKC',
    'Cent Conn St': 'Central Connecticut',
    'Boston U': 'Boston University',
    'SF Austin': 'Stephen F. Austin',
    # --- Newly added high-frequency canonical expansions ---
    'Appalachian State': 'Appalachian St',
    'App State Mountaineers': 'Appalachian St',
    'LA Tech': 'Louisiana Tech',
    'Louisiana Tech Bulldogs': 'Louisiana Tech',
    'FIU': 'Florida International',
    'Florida International Panthers': 'Florida International',
    'FAU': 'Florida Atlantic',
    'Florida Atlantic Owls': 'Florida Atlantic',
    'FGCU': 'Florida Gulf Coast',
    'UCF Knights': 'UCF',
    'VCU Rams': 'VCU',
    'UConn': 'Connecticut',
    'UConn Huskies': 'Connecticut',
    'Jacksonville St': 'Jacksonville State',
    'Jacksonville State Gamecocks': 'Jacksonville State',
    'Sam Houston Bearkats': 'Sam Houston State',
    'Sam Houston State Bearkats': 'Sam Houston State',
    'New Mexico St': 'New Mexico State',
    'New Mexico State Aggies': 'New Mexico State',
    'North Dakota St': 'North Dakota State',
    'North Dakota State Bison': 'North Dakota State',
    'San José State': 'San Jose State',
    'San José State Spartans': 'San Jose State',
    'San JosÃ© State': 'San Jose State',
    'San JosÃ© State Spartans': 'San Jose State',
    'Miss St': 'Mississippi State',
    'South Dakota St': 'South Dakota State',
    'South Dakota State Jackrabbits': 'South Dakota State',
    # Some schools where the alias is already OK (identity map for consistency) - optional:
    'Ole Miss': 'Ole Miss',  # preferred short form
    'NC State': 'NC State',
    'UT Rio Grande': 'UT Rio Grande Valley',  # shorten -> full
    # Mascot / extended forms in dataset -> short canonical forms:
    'American University': 'American',
    'Delaware Blue Hens': 'Delaware',
    'Florida A&M Rattlers': 'Florida A&M',
    'Georgetown Hoyas': 'Georgetown',
    "Hawai'i Rainbow": "Hawai'i",
    'Northern Kentucky Norse': 'Northern Kentucky',
    'Stanford Cardinal': 'Stanford',
    'UAB Blazers': 'UAB',
    'UC San Diego Tritons': 'UC San Diego',
    # Add further mappings below as needed...
}


def load_external_mapping(path: Path) -> Dict[str, str]:
    if not path.exists():
        print(f"[mapping-json] File not found: {path}")
        return {}
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            print('[mapping-json] JSON must be an object/dict of {"Bad": "Good"}. Ignoring.')
            return {}
        # Normalize keys (strip whitespace)
        cleaned = {k.strip(): v.strip() for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
        print(f"[mapping-json] Loaded {len(cleaned)} mappings from {path}")
        return cleaned
    except Exception as e:
        print(f"[mapping-json] Failed to load mapping JSON: {e}")
        return {}


def apply_mapping(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Return a copy with normalized team columns added."""
    df = df.copy()
    for col in ['home_team', 'away_team']:
        if col not in df.columns:
            raise KeyError(f"Expected column '{col}' in input data.")
    df['home_team_normalized'] = df['home_team'].replace(mapping)
    df['away_team_normalized'] = df['away_team'].replace(mapping)
    return df


def summarize_changes(df_original: pd.DataFrame, df_norm: pd.DataFrame) -> None:
    def changed_count(col_old: str, col_new: str) -> int:
        return (df_original[col_old] != df_norm[col_new]).sum()
    home_changes = changed_count('home_team', 'home_team_normalized')
    away_changes = changed_count('away_team', 'away_team_normalized')
    print(f"Changed home team names: {home_changes}")
    print(f"Changed away team names: {away_changes}")
    all_old = set(pd.concat([df_original['home_team'], df_original['away_team']]))
    all_new = set(pd.concat([df_norm['home_team_normalized'], df_norm['away_team_normalized']]))
    print(f"Unique teams before: {len(all_old)} | after normalization: {len(all_new)}")


def detect_suspicious_aliases(df_norm: pd.DataFrame, canonical: Set[str]) -> Set[str]:
    """Return names that still look like truncated forms (heuristic) but are not canonical.
    Heuristic: Contains periods ("St.") or spaces and ends with abbreviations, or matches patterns like 'W ', 'N '.
    This is intentionally lightweight; refine as needed.
    """
    remaining = set(pd.concat([df_norm['home_team_normalized'], df_norm['away_team_normalized']]))
    suspicious = set()
    for name in remaining:
        if name in canonical:
            continue
        lowered = name.lower()
        if any(prefix in lowered for prefix in ['st ', 'st.', ' w ', ' n ', ' state']) or lowered.startswith(('w ', 'n ')):
            suspicious.add(name)
    return suspicious


def load_canonical(canonical_file: Path) -> Set[str]:
    if not canonical_file.exists():
        print(f"[canonical] File not found: {canonical_file}. Skipping canonical-based reporting.")
        return set()
    with canonical_file.open('r', encoding='utf-8') as f:
        names = {line.strip() for line in f if line.strip()}
    print(f"[canonical] Loaded {len(names)} canonical names from {canonical_file}")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description='Normalize team names using a mapping dict.')
    parser.add_argument('--input', default='data/Completed_Games_D1_Only.csv', help='Input games CSV path.')
    parser.add_argument('--output', default='data/Completed_Games_Normalized.csv', help='Output CSV path.')
    parser.add_argument('--mapping-json', default=None, help='Optional JSON file containing additional/override mappings.')
    parser.add_argument('--canonical', default='canonical_d1_list.txt', help='Optional canonical D1 list file for reporting.')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    print(f"Loading games: {input_path}")
    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        print(f"Failed to read input CSV: {e}")
        return 1

    effective_mapping = dict(team_name_mapping)  # copy
    if args.mapping_json:
        external = load_external_mapping(Path(args.mapping_json))
        # Override / extend
        effective_mapping.update(external)
        print(f"Total mappings after merge: {len(effective_mapping)}")
    else:
        print(f"Using {len(effective_mapping)} inline mappings.")

    df_norm = apply_mapping(df, effective_mapping)
    summarize_changes(df, df_norm)

    # Optional canonical-based reporting
    canonical_names = load_canonical(Path(args.canonical))
    if canonical_names:
        unmatched_canonical = set(pd.concat([df_norm['home_team_normalized'], df_norm['away_team_normalized']])) - canonical_names
        print(f"Teams NOT in canonical list after normalization: {len(unmatched_canonical)} (sample up to 30)")
        for name in sorted(list(unmatched_canonical))[:30]:
            print(f"  - {name}")
        suspicious = detect_suspicious_aliases(df_norm, canonical_names)
        if suspicious:
            print(f"Heuristic suspicious (potential aliases still): {len(suspicious)}")
            for name in sorted(list(suspicious))[:30]:
                print(f"    * {name}")

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_norm.to_csv(output_path, index=False)
    print(f"Saved normalized data to: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
