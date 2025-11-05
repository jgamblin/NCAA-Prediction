"""Cross-Source ID Mapping (Stub)

Provides a unified lookup layer to reconcile team identifiers across sources:
- ESPN numeric team IDs (when available)
- Canonical normalized team name (this repo's internal standard)
- Future: KenPom name/ID, NCAA official ID

Current Implementation:
    Loads a CSV at data/id_lookup.csv if present with columns:
        canonical_name, espn_id, kenpom_name, kenpom_id, ncaa_name, ncaa_id
    Missing file -> returns empty DataFrame.

Public Functions:
    load_id_lookup() -> pd.DataFrame
    build_minimal_espn_lookup(games_df: pd.DataFrame) -> pd.DataFrame
    save_id_lookup(df: pd.DataFrame)
    resolve_any(identifier: str, df: pd.DataFrame) -> dict | None

The stub keeps interface stable for later enrichment with external data.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from data_collection.team_name_utils import normalize_team_name

LOOKUP_PATH = Path('data') / 'id_lookup.csv'

COLUMNS = ['canonical_name','espn_id','kenpom_name','kenpom_id','ncaa_name','ncaa_id']


def load_id_lookup(path: Path | str = LOOKUP_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(p, dtype=str)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ''
    # Normalize canonical_name
    if 'canonical_name' in df.columns:
        df['canonical_name'] = df['canonical_name'].apply(lambda x: normalize_team_name(x) if isinstance(x,str) else x)
    return df[COLUMNS]


def save_id_lookup(df: pd.DataFrame, path: Path | str = LOOKUP_PATH) -> None:
    p = Path(path)
    df.to_csv(p, index=False)


def build_minimal_espn_lookup(games_df: pd.DataFrame) -> pd.DataFrame:
    """Construct a minimal lookup using ESPN team names + IDs from a games dataframe.

    Expects columns home_team, away_team, home_team_id, away_team_id (IDs may be blank).
    """
    cols_need = ['home_team','away_team','home_team_id','away_team_id']
    missing = [c for c in cols_need if c not in games_df.columns]
    if missing:
        raise ValueError(f"games_df missing columns needed for lookup: {missing}")
    pairs = []
    for _, r in games_df.iterrows():
        for name_col, id_col in [('home_team','home_team_id'), ('away_team','away_team_id')]:
            raw_name = r[name_col]
            espn_id = str(r[id_col]).strip()
            if not raw_name:
                continue
            canonical = normalize_team_name(raw_name)
            pairs.append((canonical, espn_id if espn_id else ''))
    df = pd.DataFrame(pairs, columns=['canonical_name','espn_id']).drop_duplicates('canonical_name')
    # Expand to full schema
    for extra in ['kenpom_name','kenpom_id','ncaa_name','ncaa_id']:
        df[extra] = ''
    return df[COLUMNS]


def resolve_any(identifier: str, df: pd.DataFrame | None = None):
    """Attempt to resolve a provided identifier (name or espn_id) into a mapping row.

    Returns dict with keys in COLUMNS or None if not found.
    """
    if df is None:
        df = load_id_lookup()
    if df.empty or not identifier:
        return None
    identifier = str(identifier).strip()
    # Try direct espn_id match
    if 'espn_id' in df.columns and identifier.isdigit():
        match = df[df['espn_id'] == identifier]
        if not match.empty:
            return match.iloc[0].to_dict()
    # Try canonical name normalization
    canon = normalize_team_name(identifier)
    match = df[df['canonical_name'].str.lower() == canon.lower()]
    if not match.empty:
        return match.iloc[0].to_dict()
    return None

__all__ = [
    'load_id_lookup','save_id_lookup','build_minimal_espn_lookup','resolve_any'
]
