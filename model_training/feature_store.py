"""Per-Team Feature Store (Rolling Aggregates)

Provides a lightweight persisted cache of rolling per-team features keyed by team_id.
Intended to accelerate prediction pipelines by avoiding recomputation of common
statistics (e.g., recent win rate, average point differential).

Storage Format:
    data/feature_store/feature_store.csv (wide format; one row per season+team_id)

Columns (initial minimal set, now expanded):
    season, team_id, games_played,
    rolling_win_pct_5, rolling_win_pct_10,
    rolling_point_diff_avg_5, rolling_point_diff_avg_10,
    win_pct_last5_vs10, point_diff_last5_vs10, recent_strength_index_5,
    updated_at

Design Choices:
    - Single CSV for simplicity; could evolve to per-team parquet partitions later.
    - Deterministic team IDs from team_id_utils when missing.
    - Recompute only for teams with new games (compare games_played).

Phase 1 Enhancement (2025-11-29):
    - Added fallback hierarchy for teams with insufficient current season data
    - get_team_features_with_fallback() provides: current -> prior season -> league average
    - Eliminates NaN features that were causing poor predictions

Public API:
    build_feature_store(games_df: pd.DataFrame) -> pd.DataFrame
    load_feature_store(path: Path | str = DEFAULT_PATH) -> pd.DataFrame
    save_feature_store(df: pd.DataFrame, path: Path | str = DEFAULT_PATH) -> None
    get_team_features_with_fallback(team_id, season, feature_store_df, min_games=5) -> dict
    calculate_point_in_time_features(df: pd.DataFrame) -> pd.DataFrame  # For training data without leakage

"""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json
from model_training.team_id_utils import ensure_team_ids
try:
    from config.load_config import get_config
    _cfg = get_config()
except Exception:
    _cfg = {}

# Load feature flags
try:
    with open(Path('config') / 'feature_flags.json') as f:
        _feature_flags = json.load(f)
except Exception:
    _feature_flags = {}

FEATURE_DIR = Path('data') / 'feature_store'
FEATURE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PATH = FEATURE_DIR / 'feature_store.csv'

REQUIRED_COLS = ['game_id','home_team','away_team','home_score','away_score','season','date']

# Feature columns that need fallback handling
NUMERIC_FEATURE_COLS = [
    'rolling_win_pct_5', 'rolling_win_pct_10',
    'rolling_point_diff_avg_5', 'rolling_point_diff_avg_10',
    'win_pct_last5_vs10', 'point_diff_last5_vs10', 'recent_strength_index_5'
]

# League average defaults (neutral baseline)
LEAGUE_AVERAGE_DEFAULTS = {
    'rolling_win_pct_5': 0.5,
    'rolling_win_pct_10': 0.5,
    'rolling_point_diff_avg_5': 0.0,
    'rolling_point_diff_avg_10': 0.0,
    'win_pct_last5_vs10': 0.0,
    'point_diff_last5_vs10': 0.0,
    'recent_strength_index_5': 0.0,
    'games_played': 0
}


def _validate_games_df(df: pd.DataFrame):
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"games_df missing required columns: {missing}")


def load_feature_store(path: Path | str = DEFAULT_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=[
            'season','team_id','games_played','rolling_win_pct_5','rolling_win_pct_10',
            'rolling_point_diff_avg_5','rolling_point_diff_avg_10',
            'win_pct_last5_vs10','point_diff_last5_vs10','recent_strength_index_5','updated_at'
        ])
    return pd.read_csv(p)


def save_feature_store(df: pd.DataFrame, path: Path | str = DEFAULT_PATH) -> None:
    p = Path(path)
    df.to_csv(p, index=False)


def build_feature_store(games_df: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling aggregates per team and merge with existing store.

    games_df: Completed games (Final) only recommended.
    """
    _validate_games_df(games_df)
    games_df = ensure_team_ids(games_df, home_col='home_team', away_col='away_team')

    # Construct per-team perspective simplified rows (point differential from team's POV)
    rows = []
    for _, r in games_df.iterrows():
        # Skip if scores not numeric
        try:
            h_score = int(r['home_score'])
            a_score = int(r['away_score'])
        except Exception:
            continue
        season = r.get('season') or r.get('Season')
        date_val = r.get('date') or r.get('Date')
        # Home perspective
        rows.append({
            'team_id': r['home_team_id'],
            'season': season,
            'date': date_val,
            'won': 1 if h_score > a_score else 0,
            'point_diff': h_score - a_score,
            'game_id': r['game_id']
        })
        # Away perspective
        rows.append({
            'team_id': r['away_team_id'],
            'season': season,
            'date': date_val,
            'won': 1 if a_score > h_score else 0,
            'point_diff': a_score - h_score,
            'game_id': r['game_id']
        })
    team_df = pd.DataFrame(rows)
    if team_df.empty:
        return load_feature_store()

    team_df = team_df.sort_values(['season','team_id','date','game_id']).reset_index(drop=True)

    feature_rows = []
    for (season, team_id), grp in team_df.groupby(['season','team_id']):
        wins = grp['won'].tolist()
        diffs = grp['point_diff'].tolist()
        n_games = len(grp)

        def rolling_pct(seq, window):
            if len(seq) < window:
                return np.nan
            window_seq = seq[-window:]
            return float(sum(window_seq)/len(window_seq))
        def rolling_avg(seq, window):
            if len(seq) < window:
                return np.nan
            return float(np.mean(seq[-window:]))

        rw5 = rolling_pct(wins, 5)
        rw10 = rolling_pct(wins, 10)
        pd5 = rolling_avg(diffs, 5)
        pd10 = rolling_avg(diffs, 10)
        win_pct_last5_vs10 = (rw5 - rw10) if (not np.isnan(rw5) and not np.isnan(rw10)) else np.nan
        point_diff_last5_vs10 = (pd5 - pd10) if (not np.isnan(pd5) and not np.isnan(pd10)) else np.nan
        recent_strength_index_5 = (rw5 * pd5) if (not np.isnan(rw5) and not np.isnan(pd5)) else np.nan
        feature_rows.append({
            'season': season,
            'team_id': team_id,
            'games_played': n_games,
            'rolling_win_pct_5': rw5,
            'rolling_win_pct_10': rw10,
            'rolling_point_diff_avg_5': pd5,
            'rolling_point_diff_avg_10': pd10,
            'win_pct_last5_vs10': win_pct_last5_vs10,
            'point_diff_last5_vs10': point_diff_last5_vs10,
            'recent_strength_index_5': recent_strength_index_5,
            'updated_at': datetime.now(timezone.utc).isoformat()
        })

    new_features = pd.DataFrame(feature_rows)
    existing = load_feature_store()
    if existing.empty:
        return new_features

    # Merge preferring new rows (override same season+team_id)
    combined = pd.concat([existing, new_features], ignore_index=True)
    combined = combined.sort_values(['season','team_id','games_played']).drop_duplicates(['season','team_id'], keep='last')
    return combined


def _get_prior_season(season: str) -> str:
    """Get the prior season string (e.g., '2024-25' -> '2023-24')."""
    if not season:
        return ""
    try:
        # Handle formats like "2024-25" or "2025"
        if '-' in str(season):
            parts = str(season).split('-')
            year1 = int(parts[0]) - 1
            year2 = int(parts[1]) - 1
            return f"{year1}-{year2:02d}"
        else:
            return str(int(season) - 1)
    except Exception:
        return ""


def _compute_league_average(df: pd.DataFrame, season: str = None) -> dict:
    """Compute league-wide average features from the feature store."""
    if df.empty:
        return LEAGUE_AVERAGE_DEFAULTS.copy()
    
    # Filter to season if provided
    if season and 'season' in df.columns:
        season_df = df[df['season'] == season]
        if season_df.empty:
            season_df = df  # Fall back to all data
    else:
        season_df = df
    
    result = {'is_fallback': True, 'fallback_type': 'league_avg'}
    for col in NUMERIC_FEATURE_COLS:
        if col in season_df.columns:
            valid_values = season_df[col].dropna()
            if len(valid_values) > 0:
                result[col] = float(valid_values.mean())
            else:
                result[col] = LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0)
        else:
            result[col] = LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0)
    
    result['games_played'] = 0
    return result


def get_team_features_with_fallback(
    team_id: str,
    season: str,
    feature_store_df: pd.DataFrame = None,
    min_games: int = 5
) -> dict:
    """
    Get team features with fallback hierarchy for sparse data.
    
    Fallback order:
    1. Current season data (if team has >= min_games played)
    2. Prior season end-of-year data
    3. League average for the season
    
    Args:
        team_id: The team's unique identifier
        season: The season string (e.g., "2024-25")
        feature_store_df: Pre-loaded feature store DataFrame (optional, will load if None)
        min_games: Minimum games required to use current season data
    
    Returns:
        dict with feature values and fallback metadata
    """
    if feature_store_df is None:
        feature_store_df = load_feature_store()
    
    if feature_store_df.empty:
        result = LEAGUE_AVERAGE_DEFAULTS.copy()
        result['is_fallback'] = True
        result['fallback_type'] = 'empty_store'
        result['team_id'] = team_id
        result['season'] = season
        return result
    
    # Try current season
    current_mask = (feature_store_df['team_id'] == team_id) & (feature_store_df['season'] == season)
    current_data = feature_store_df[current_mask]
    
    if not current_data.empty:
        current_row = current_data.sort_values('games_played').iloc[-1]
        games_played = int(current_row.get('games_played', 0))
        
        if games_played >= min_games:
            # Use current season data
            result = current_row.to_dict()
            result['is_fallback'] = False
            result['fallback_type'] = 'none'
            # Fill any NaN values with defaults
            for col in NUMERIC_FEATURE_COLS:
                if col in result and (pd.isna(result[col]) or result[col] is None):
                    result[col] = LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0)
            return result
    
    # Try prior season
    prior_season = _get_prior_season(season)
    if prior_season:
        prior_mask = (feature_store_df['team_id'] == team_id) & (feature_store_df['season'] == prior_season)
        prior_data = feature_store_df[prior_mask]
        
        if not prior_data.empty:
            prior_row = prior_data.sort_values('games_played').iloc[-1]
            result = prior_row.to_dict()
            result['is_fallback'] = True
            result['fallback_type'] = 'prior_season'
            result['original_season'] = prior_season
            result['season'] = season  # Update to current season for merging
            # Fill any NaN values with defaults
            for col in NUMERIC_FEATURE_COLS:
                if col in result and (pd.isna(result[col]) or result[col] is None):
                    result[col] = LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0)
            return result
    
    # Fall back to league average
    result = _compute_league_average(feature_store_df, season)
    result['team_id'] = team_id
    result['season'] = season
    return result


def enrich_dataframe_with_fallback(
    df: pd.DataFrame,
    feature_store_df: pd.DataFrame = None,
    min_games: int = 5
) -> pd.DataFrame:
    """
    Enrich a games dataframe with feature store data using fallback hierarchy.
    
    This replaces the simple merge approach and ensures no NaN values in features.
    
    Args:
        df: DataFrame with home_team_id, away_team_id, and season columns
        feature_store_df: Pre-loaded feature store (optional)
        min_games: Minimum games for current season data
    
    Returns:
        DataFrame with home_fs_* and away_fs_* columns filled (no NaN)
    """
    if feature_store_df is None:
        feature_store_df = load_feature_store()
    
    df = df.copy()
    
    # Ensure we have season
    if 'season' not in df.columns:
        if 'Season' in df.columns:
            df['season'] = df['Season']
        elif not feature_store_df.empty:
            df['season'] = feature_store_df['season'].max()
        else:
            df['season'] = '2024-25'
    
    # Ensure team IDs
    if 'home_team_id' not in df.columns or 'away_team_id' not in df.columns:
        df = ensure_team_ids(df)
    
    # Initialize feature columns with defaults
    for col in NUMERIC_FEATURE_COLS:
        df[f'home_fs_{col}'] = LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0)
        df[f'away_fs_{col}'] = LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0)
    
    df['home_fs_is_fallback'] = True
    df['away_fs_is_fallback'] = True
    df['home_fs_fallback_type'] = 'pending'
    df['away_fs_fallback_type'] = 'pending'
    
    # Cache for team features to avoid repeated lookups
    feature_cache = {}
    
    fallback_stats = {'current': 0, 'prior_season': 0, 'league_avg': 0, 'empty_store': 0}
    
    for idx, row in df.iterrows():
        season = row['season']
        
        # Home team features
        home_id = row['home_team_id']
        cache_key_home = (home_id, season)
        if cache_key_home not in feature_cache:
            feature_cache[cache_key_home] = get_team_features_with_fallback(
                home_id, season, feature_store_df, min_games
            )
        home_features = feature_cache[cache_key_home]
        
        for col in NUMERIC_FEATURE_COLS:
            df.at[idx, f'home_fs_{col}'] = home_features.get(col, LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0))
        df.at[idx, 'home_fs_is_fallback'] = home_features.get('is_fallback', True)
        df.at[idx, 'home_fs_fallback_type'] = home_features.get('fallback_type', 'unknown')
        
        # Track stats
        fallback_type = home_features.get('fallback_type', 'unknown')
        if fallback_type == 'none':
            fallback_stats['current'] += 1
        elif fallback_type == 'prior_season':
            fallback_stats['prior_season'] += 1
        else:
            fallback_stats['league_avg'] += 1
        
        # Away team features
        away_id = row['away_team_id']
        cache_key_away = (away_id, season)
        if cache_key_away not in feature_cache:
            feature_cache[cache_key_away] = get_team_features_with_fallback(
                away_id, season, feature_store_df, min_games
            )
        away_features = feature_cache[cache_key_away]
        
        for col in NUMERIC_FEATURE_COLS:
            df.at[idx, f'away_fs_{col}'] = away_features.get(col, LEAGUE_AVERAGE_DEFAULTS.get(col, 0.0))
        df.at[idx, 'away_fs_is_fallback'] = away_features.get('is_fallback', True)
        df.at[idx, 'away_fs_fallback_type'] = away_features.get('fallback_type', 'unknown')
        
        # Track stats
        fallback_type = away_features.get('fallback_type', 'unknown')
        if fallback_type == 'none':
            fallback_stats['current'] += 1
        elif fallback_type == 'prior_season':
            fallback_stats['prior_season'] += 1
        else:
            fallback_stats['league_avg'] += 1
    
    total = sum(fallback_stats.values())
    if total > 0:
        print(f"  Feature fallback stats: current={fallback_stats['current']}, "
              f"prior_season={fallback_stats['prior_season']}, "
              f"league_avg={fallback_stats['league_avg']} "
              f"(of {total} team-game lookups)")
    
    return df


def calculate_point_in_time_features(df):
    """
    Calculates rolling features (Win Pct, Point Diff, etc.) correctly for training data.
    CRITICAL: Uses .shift(1) to ensure a game's result is not included in its own average.
    """
    # 1. Sort by date
    df = df.sort_values(['season', 'date'])
    
    # 2. Create Long Format (Stack Home and Away)
    # We need a single timeline of games per team
    home_df = df[['date', 'season', 'home_team_id', 'home_win', 'home_score', 'away_score', 'game_id']].copy()
    home_df.columns = ['date', 'season', 'team_id', 'won', 'score', 'opponent_score', 'game_id']
    
    away_df = df[['date', 'season', 'away_team_id', 'home_win', 'away_score', 'home_score', 'game_id']].copy()
    away_df['won'] = 1 - away_df['home_win']  # Inverse win for away
    away_df = away_df[['date', 'season', 'away_team_id', 'won', 'away_score', 'home_score', 'game_id']]
    away_df.columns = ['date', 'season', 'team_id', 'won', 'score', 'opponent_score', 'game_id']
    
    # Combined timeline
    team_df = pd.concat([home_df, away_df]).sort_values(['season', 'team_id', 'date'])
    
    # 3. Calculate Derived Metrics (Point Diff)
    team_df['point_diff'] = team_df['score'] - team_df['opponent_score']
    
    # 4. Calculate Rolling Stats using SHIFT(1) to prevent leakage
    # We group by season+team, then look at the PREVIOUS N games
    grouped = team_df.groupby(['season', 'team_id'])
    
    # Helper for rolling calculations
    def get_rolling(series, window):
        return series.shift(1).rolling(window=window, min_periods=1).mean()

    # Calculate base rolling stats
    team_df['rolling_win_pct_5'] = grouped['won'].transform(lambda x: get_rolling(x, 5))
    team_df['rolling_win_pct_10'] = grouped['won'].transform(lambda x: get_rolling(x, 10))
    team_df['rolling_point_diff_avg_5'] = grouped['point_diff'].transform(lambda x: get_rolling(x, 5))
    team_df['rolling_point_diff_avg_10'] = grouped['point_diff'].transform(lambda x: get_rolling(x, 10))

    # Calculate derived stats (Phase 2/Advanced)
    team_df['win_pct_last5_vs10'] = team_df['rolling_win_pct_5'] - team_df['rolling_win_pct_10']
    team_df['point_diff_last5_vs10'] = team_df['rolling_point_diff_avg_5'] - team_df['rolling_point_diff_avg_10']
    team_df['recent_strength_index_5'] = team_df['rolling_win_pct_5'] * team_df['rolling_point_diff_avg_5']

    # 5. Merge back to the original Matchup DataFrame (Home and Away sides)
    features = ['rolling_win_pct_5', 'rolling_win_pct_10', 'rolling_point_diff_avg_5', 
                'rolling_point_diff_avg_10', 'win_pct_last5_vs10', 'point_diff_last5_vs10', 
                'recent_strength_index_5']
    
    # Merge for Home
    df = df.merge(team_df[['game_id', 'team_id'] + features], 
                  left_on=['game_id', 'home_team_id'], 
                  right_on=['game_id', 'team_id'], 
                  how='left').rename(columns={f: f'home_fs_{f}' for f in features}).drop(columns=['team_id'])
                  
    # Merge for Away
    df = df.merge(team_df[['game_id', 'team_id'] + features], 
                  left_on=['game_id', 'away_team_id'], 
                  right_on=['game_id', 'team_id'], 
                  how='left').rename(columns={f: f'away_fs_{f}' for f in features}).drop(columns=['team_id'])

    # Fill NaNs with defaults (for first game of season)
    for col in [c for c in df.columns if 'fs_' in c]:
        df[col] = df[col].fillna(0.0)
        
    return df


__all__ = [
    'build_feature_store', 'load_feature_store', 'save_feature_store',
    'get_team_features_with_fallback', 'enrich_dataframe_with_fallback',
    'calculate_point_in_time_features',
    'LEAGUE_AVERAGE_DEFAULTS', 'NUMERIC_FEATURE_COLS'
]
