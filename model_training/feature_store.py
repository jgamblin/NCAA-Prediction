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

Public API:
    build_feature_store(games_df: pd.DataFrame) -> pd.DataFrame
    load_feature_store(path: Path | str = DEFAULT_PATH) -> pd.DataFrame
    save_feature_store(df: pd.DataFrame, path: Path | str = DEFAULT_PATH) -> None

"""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from model_training.team_id_utils import ensure_team_ids
try:
    from config.load_config import get_config
    _cfg = get_config()
except Exception:
    _cfg = {}

FEATURE_DIR = Path('data') / 'feature_store'
FEATURE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PATH = FEATURE_DIR / 'feature_store.csv'

REQUIRED_COLS = ['game_id','home_team','away_team','home_score','away_score','season','date']


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

__all__ = [
    'build_feature_store','load_feature_store','save_feature_store'
]
