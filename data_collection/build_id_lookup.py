#!/usr/bin/env python3
"""Build or update the cross-source ID lookup file.

Currently focuses on ESPN scraped data and historical completed games to seed:
  data/id_lookup.csv

Logic:
 1. Load ESPN current season file if present (data_collection/data/ESPN_Current_Season.csv).
 2. Load Completed_Games.csv for any additional team names.
 3. Ensure team IDs (deterministic fallback) and construct minimal lookup via
    id_mapping.build_minimal_espn_lookup.
 4. Merge with existing lookup (if present) preferring existing non-empty IDs.

Usage:
    python -m data_collection.build_id_lookup
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from data_collection.id_mapping import load_id_lookup, save_id_lookup, build_minimal_espn_lookup
from model_training.team_id_utils import ensure_team_ids

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
ESPN_CURR = ROOT / 'data_collection' / 'data' / 'ESPN_Current_Season.csv'
COMPLETED = DATA / 'Completed_Games.csv'


def load_source_df() -> pd.DataFrame:
    frames = []
    if ESPN_CURR.exists():
        try:
            frames.append(pd.read_csv(ESPN_CURR))
        except Exception:
            pass
    if COMPLETED.exists():
        try:
            frames.append(pd.read_csv(COMPLETED))
        except Exception:
            pass
    if not frames:
        raise FileNotFoundError("No source data (ESPN_Current_Season or Completed_Games) found")
    df = pd.concat(frames, ignore_index=True)
    # Ensure columns
    for col in ['home_team','away_team']:
        if col not in df.columns:
            raise ValueError(f"Missing required column {col} in source data for ID lookup")
    return df


def main():
    print("Building ID lookup ...")
    try:
        src = load_source_df()
    except Exception as e:
        print(f"Failed to load sources: {e}")
        return

    # Ensure IDs (even if ESPN numeric IDs absent we create deterministic ones)
    src = ensure_team_ids(src)

    # Build minimal mapping using current names + espn ids (if available)
    try:
        mapping = build_minimal_espn_lookup(src)
    except Exception as e:
        print(f"Failed to build minimal ESPN lookup: {e}")
        return

    existing = load_id_lookup()
    if existing.empty:
        merged = mapping
    else:
        # Merge on canonical name; keep existing non-empty espn_id values
        merged = existing.merge(mapping[['canonical_name','espn_id']], on='canonical_name', how='outer', suffixes=('_old',''))
        # Consolidate espn_id preference order: existing then new
        merged['espn_id'] = merged.apply(lambda r: r['espn_id_old'] if isinstance(r.get('espn_id_old'), str) and r['espn_id_old'].strip() else r.get('espn_id',''), axis=1)
        if 'espn_id_old' in merged.columns:
            merged = merged.drop(columns=['espn_id_old'])
        # Ensure all expected columns
        for col in ['kenpom_name','kenpom_id','ncaa_name','ncaa_id']:
            if col not in merged.columns:
                merged[col] = ''
    save_id_lookup(merged)
    print(f"Lookup saved with {len(merged)} canonical rows -> {DATA / 'id_lookup.csv'}")

if __name__ == '__main__':
    main()
