#!/usr/bin/env python3
"""Regenerate a normalized version of Completed_Games.csv applying latest team name normalization.

Creates a new file data/Completed_Games_Normalized.csv and prints a summary of:
- Total games
- Number of rows whose home or away team name changed
- Before/after counts for problematic aliases (San Jose State variants, California, Miami)
- Sample of changed rows

Does NOT overwrite the original Completed_Games.csv by default.
Set OVERWRITE=1 environment variable to replace original file if desired.
"""
import os
import sys
import pandas as pd
from collections import Counter

# Ensure we can import normalization utilities
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(ROOT_DIR, 'data')
sys.path.insert(0, ROOT_DIR)
from data_collection.team_name_utils import normalize_team_name

INPUT_PATH = os.path.join(DATA_DIR, 'Completed_Games.csv')
OUTPUT_PATH = os.path.join(DATA_DIR, 'Completed_Games_Normalized.csv')

SAN_JOSE_VARIANTS = [
    'San Jose State','San Jose St','San José State','San José State Spartans',
    'San Jose State Spartans','SJSU','SJSU Spartans','San JosÃ© State','San JosÃ© State Spartans'
]

FOCUS_TEAMS = {
    'San Jose State': SAN_JOSE_VARIANTS,
    'California': ['California Golden Bears','Cal','Cal Golden Bears','Cal Bears'],
    'Miami (FL)': ['Miami','Miami Hurricanes','Miami (FL) Hurricanes'],
}

def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Error: {INPUT_PATH} not found.")
        sys.exit(1)

    df = pd.read_csv(INPUT_PATH)
    total_games = len(df)

    # Capture before counts for focus teams
    before_counts = {canon: 0 for canon in FOCUS_TEAMS}
    for canon, variants in FOCUS_TEAMS.items():
        mask = (df['home_team'].isin(variants)) | (df['away_team'].isin(variants))
        before_counts[canon] = int(mask.sum())

    # Apply normalization
    norm_df = df.copy()
    norm_df['home_team_normalized'] = norm_df['home_team'].apply(normalize_team_name)
    norm_df['away_team_normalized'] = norm_df['away_team'].apply(normalize_team_name)

    # Determine changed rows
    changed_mask = (norm_df['home_team'] != norm_df['home_team_normalized']) | \
                   (norm_df['away_team'] != norm_df['away_team_normalized'])
    changed_rows = norm_df[changed_mask]

    # Build output dataframe (replace original columns for downstream compatibility)
    output_df = norm_df.copy()
    output_df['home_team'] = output_df['home_team_normalized']
    output_df['away_team'] = output_df['away_team_normalized']
    output_df.drop(columns=['home_team_normalized','away_team_normalized'], inplace=True)

    # After counts using normalized columns
    after_counts = {canon: 0 for canon in FOCUS_TEAMS}
    for canon in FOCUS_TEAMS:
        mask = (output_df['home_team'] == canon) | (output_df['away_team'] == canon)
        after_counts[canon] = int(mask.sum())

    # Write normalized file
    output_df.to_csv(OUTPUT_PATH, index=False)

    # Optional overwrite
    overwrite = os.environ.get('OVERWRITE', '0') == '1'
    if overwrite:
        backup_path = INPUT_PATH.replace('.csv', '_backup_before_normalization.csv')
        os.replace(INPUT_PATH, backup_path)
        output_df.to_csv(INPUT_PATH, index=False)
        print(f"Original file overwritten. Backup saved to {backup_path}")

    # Report summary
    print("="*80)
    print("Completed_Games Normalization Summary")
    print("="*80)
    print(f"Total games: {total_games}")
    print(f"Rows with at least one team name changed: {len(changed_rows)} ({len(changed_rows)/total_games:.1%})")
    print()
    print("Focus team before/after counts:")
    for canon in FOCUS_TEAMS:
        print(f"  {canon:14} {before_counts[canon]:5} -> {after_counts[canon]:5} (Δ {after_counts[canon]-before_counts[canon]:+})")

    # San Jose specific variant breakdown after normalization
    print("\nSan Jose State variant occurrences BEFORE normalization:")
    sj_counter = Counter()
    for v in SAN_JOSE_VARIANTS:
        mask = (df['home_team'] == v) | (df['away_team'] == v)
        count = int(mask.sum())
        if count:
            sj_counter[v] = count
    for v,count in sj_counter.most_common():
        print(f"  {v:28} {count:5}")
    print(f"  TOTAL (all variants)       {sum(sj_counter.values()):5}")

    print("\nSan Jose State occurrences AFTER normalization:")
    sj_after = (output_df['home_team'] == 'San Jose State') | (output_df['away_team'] == 'San Jose State')
    print(f"  San Jose State             {int(sj_after.sum()):5}")

    # Show sample of changed rows (limit 10)
    print("\nSample changed rows (up to 10):")
    sample = changed_rows.head(10).copy()
    if not sample.empty:
        sample = sample[['game_id','season','home_team','away_team','home_score','away_score']]
        print(sample.to_string(index=False))
    else:
        print("  (No changes detected)")

    print(f"\nNormalized file written to: {OUTPUT_PATH}")
    if not overwrite:
        print("Set OVERWRITE=1 to replace original Completed_Games.csv after review.")
    print("="*80)

if __name__ == '__main__':
    main()
