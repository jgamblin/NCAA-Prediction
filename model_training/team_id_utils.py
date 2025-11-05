"""Team ID Utilities

Provides stable team_id derivation when source-specific numeric IDs (e.g. ESPN) are
missing. We prefer provided IDs if present; otherwise we generate a deterministic
hash based on the normalized canonical team name.

Rationale:
- Historical datasets often lack stable numeric IDs.
- Python's built-in hash() is randomized per process (hash seed) so we avoid it.
- We use SHA1 truncated to 12 hex chars for compactness while keeping extremely
  low collision probability for ~1000 teams.

Public Functions:
- derive_team_id(raw_name: str) -> str
- ensure_team_ids(df: pd.DataFrame, home_col="home_team", away_col="away_team") -> pd.DataFrame

"""
from __future__ import annotations
import hashlib
import pandas as pd
from typing import Iterable
from data_collection.team_name_utils import normalize_team_name

PREFIX = "name_"  # prefix for generated IDs


def _canonical(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""  # caller will handle
    return normalize_team_name(name).strip().lower()


def derive_team_id(raw_name: str) -> str:
    """Return a deterministic pseudo-ID from a raw or canonical team name.

    We normalize, lower-case, then SHA1 hash and keep first 12 hex chars.
    """
    canon = _canonical(raw_name)
    if not canon:
        return ""  # allow caller to fill later
    digest = hashlib.sha1(canon.encode("utf-8")).hexdigest()[:12]
    return f"{PREFIX}{digest}"


def ensure_team_ids(df: pd.DataFrame, home_col: str = "home_team", away_col: str = "away_team") -> pd.DataFrame:
    """Ensure DataFrame has home_team_id & away_team_id columns.

    If columns already exist, fill missing/blank IDs with derived ones. If absent,
    create them. Returns a copy.
    """
    out = df.copy()
    # Prepare columns
    if "home_team_id" not in out.columns:
        out["home_team_id"] = ""
    if "away_team_id" not in out.columns:
        out["away_team_id"] = ""

    # Fill blanks deterministically
    for col_id, col_name in [("home_team_id", home_col), ("away_team_id", away_col)]:
        mask = (out[col_id].isna()) | (out[col_id].astype(str).str.strip() == "")
        if col_name in out.columns:
            out.loc[mask, col_id] = out.loc[mask, col_name].apply(derive_team_id)
    return out


def melt_games_to_team_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-team perspective rows from a game-level dataframe.

    Input expectations (columns may include extra fields):
    - game_id
    - season or Season
    - date or Date
    - home_team_id, away_team_id (will be ensured but may be derived)
    - pred_prob (home team win probability) optional; if missing we allow None
    - label (1 if home team won) optional (required for metrics later)

    Output columns:
    - game_id, season, date, team_id, side (home/away), team_pred_prob, team_label,
      opponent_team_id

    team_pred_prob is perspective-adjusted: for home rows it's pred_prob; for away
    it's (1 - pred_prob) if pred_prob provided else None.
    team_label: 1 if the team itself won the game.
    """
    # Handle possible suffixes introduced by merges (e.g., _c / _p)
    if "home_team_id" not in df.columns:
        for cand in ["home_team_id_c", "home_team_id_p", "home_team_id_x", "home_team_id_y"]:
            if cand in df.columns:
                df = df.copy()
                df["home_team_id"] = df[cand]
                break
    if "away_team_id" not in df.columns:
        for cand in ["away_team_id_c", "away_team_id_p", "away_team_id_x", "away_team_id_y"]:
            if cand in df.columns:
                df = df.copy()
                df["away_team_id"] = df[cand]
                break
    required = ["game_id", "home_team_id", "away_team_id"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' for melting to team rows")
    # Season / date normalization
    season_col = "Season" if "Season" in df.columns else ("season" if "season" in df.columns else None)
    date_col = "Date" if "Date" in df.columns else ("date" if "date" in df.columns else None)

    rows = []
    for _, r in df.iterrows():
        pred = r.get("pred_prob", None)
        label_home = r.get("label", None)
        # Derive away label if we have home label
        label_away = None if label_home is None else (1 - int(label_home))
        season_val = r.get(season_col) if season_col else None
        date_val = r.get(date_col) if date_col else None

        rows.append({
            "game_id": r.game_id,
            "season": season_val,
            "date": date_val,
            "team_id": r.home_team_id,
            "side": "home",
            "team_pred_prob": pred if pred is not None else None,
            "team_label": label_home,
            "opponent_team_id": r.away_team_id,
        })
        rows.append({
            "game_id": r.game_id,
            "season": season_val,
            "date": date_val,
            "team_id": r.away_team_id,
            "side": "away",
            "team_pred_prob": (1 - pred) if pred is not None else None,
            "team_label": label_away,
            "opponent_team_id": r.home_team_id,
        })
    return pd.DataFrame(rows)

__all__ = ["derive_team_id", "ensure_team_ids", "melt_games_to_team_rows"]
