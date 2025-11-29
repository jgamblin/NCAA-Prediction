"""Home/Away Splits Feature Engineering (Phase 2 Task 2.4)

Calculates venue-specific performance splits for each team.
Some teams perform very differently at home vs away.

Features Generated:
    - home_win_pct: Win percentage in home games
    - away_win_pct: Win percentage in away games
    - home_margin_avg: Average scoring margin at home
    - away_margin_avg: Average scoring margin on the road
    - venue_consistency: How consistent is performance across venues
    - home_advantage_factor: Team-specific home court advantage multiplier

Design:
    - Requires minimum games at each venue for reliable splits
    - Falls back to overall stats if insufficient venue-specific data
    - Integrates with feature store for per-team caching
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

# Default values for teams with insufficient data
DEFAULT_SPLITS = {
    'home_win_pct': 0.6,       # NCAA average home win rate
    'away_win_pct': 0.4,       # NCAA average away win rate
    'home_margin_avg': 4.0,    # Typical home advantage in points
    'away_margin_avg': -4.0,
    'venue_consistency': 0.5,   # Neutral (0 = wildly different, 1 = same everywhere)
    'home_advantage_factor': 1.0,
    'games_home': 0,
    'games_away': 0,
}


class HomeAwaySplits:
    """Calculate and store home/away performance splits for all teams."""
    
    def __init__(self, min_home_games: int = 3, min_away_games: int = 3):
        """
        Initialize the home/away splits calculator.
        
        Args:
            min_home_games: Minimum home games required for reliable home stats
            min_away_games: Minimum away games required for reliable away stats
        """
        self.min_home_games = min_home_games
        self.min_away_games = min_away_games
        self.splits: Dict[Tuple[str, str], Dict] = {}  # (team_id, season) -> splits
        
    def calculate_splits(self, games_df: pd.DataFrame) -> Dict[Tuple[str, str], Dict]:
        """
        Calculate home/away splits for all teams in the games data.
        
        Args:
            games_df: DataFrame with game results (needs team ids, scores, dates)
            
        Returns:
            Dictionary mapping (team_id, season) to split statistics
        """
        if games_df.empty:
            return {}
        
        df = games_df.copy()
        
        # Ensure we have required columns
        required = ['home_team_id', 'away_team_id', 'home_score', 'away_score', 'season']
        missing = [c for c in required if c not in df.columns]
        if missing:
            # Try to get team IDs
            try:
                from model_training.team_id_utils import ensure_team_ids
                df = ensure_team_ids(df)
            except Exception:
                pass
        
        # Check again
        required = ['home_team_id', 'away_team_id', 'home_score', 'away_score']
        missing = [c for c in required if c not in df.columns]
        if missing:
            print(f"  HomeAwaySplits: Missing columns {missing}, using defaults")
            return {}
        
        # Ensure season column
        if 'season' not in df.columns:
            if 'Season' in df.columns:
                df['season'] = df['Season']
            else:
                df['season'] = 'unknown'
        
        # Filter to completed games only
        df = df[(df['home_score'].notna()) & (df['away_score'].notna())]
        if df.empty:
            return {}
            
        # Calculate results
        df['home_margin'] = df['home_score'] - df['away_score']
        df['home_win'] = (df['home_margin'] > 0).astype(int)
        
        # Get all unique teams
        all_teams = set(df['home_team_id'].unique()) | set(df['away_team_id'].unique())
        seasons = df['season'].unique()
        
        for season in seasons:
            season_df = df[df['season'] == season]
            
            for team_id in all_teams:
                # Home games for this team
                home_games = season_df[season_df['home_team_id'] == team_id]
                # Away games for this team
                away_games = season_df[season_df['away_team_id'] == team_id]
                
                n_home = len(home_games)
                n_away = len(away_games)
                
                splits = {
                    'games_home': n_home,
                    'games_away': n_away,
                }
                
                # Calculate home stats
                if n_home >= self.min_home_games:
                    splits['home_win_pct'] = home_games['home_win'].mean()
                    splits['home_margin_avg'] = home_games['home_margin'].mean()
                else:
                    # Fallback: use overall team performance or defaults
                    splits['home_win_pct'] = DEFAULT_SPLITS['home_win_pct']
                    splits['home_margin_avg'] = DEFAULT_SPLITS['home_margin_avg']
                
                # Calculate away stats (inverted margins - team is away)
                if n_away >= self.min_away_games:
                    splits['away_win_pct'] = (away_games['home_margin'] < 0).mean()
                    splits['away_margin_avg'] = -away_games['home_margin'].mean()  # Invert for away perspective
                else:
                    splits['away_win_pct'] = DEFAULT_SPLITS['away_win_pct']
                    splits['away_margin_avg'] = DEFAULT_SPLITS['away_margin_avg']
                
                # Calculate derived features
                splits['venue_consistency'] = self._calculate_consistency(splits)
                splits['home_advantage_factor'] = self._calculate_home_advantage(splits)
                
                self.splits[(team_id, season)] = splits
        
        return self.splits
    
    def _calculate_consistency(self, splits: Dict) -> float:
        """
        Calculate how consistently a team performs across venues.
        
        Returns:
            0.0 = Very different performance at home vs away
            1.0 = Same performance regardless of venue
        """
        home_pct = splits.get('home_win_pct', 0.5)
        away_pct = splits.get('away_win_pct', 0.5)
        
        # Difference from expected (home should be ~60%, away ~40%)
        home_margin = splits.get('home_margin_avg', 0)
        away_margin = splits.get('away_margin_avg', 0)
        
        # Consistency based on win pct difference
        pct_diff = abs(home_pct - away_pct)
        # Expected difference is about 0.2 (60% - 40%)
        # If diff is 0.2, consistency = 0.5 (average)
        # If diff is 0, consistency = 1.0 (same everywhere)
        # If diff is 0.5+, consistency = 0.0 (very different)
        consistency = max(0.0, 1.0 - (pct_diff / 0.4))
        
        return round(consistency, 3)
    
    def _calculate_home_advantage(self, splits: Dict) -> float:
        """
        Calculate team-specific home court advantage multiplier.
        
        Returns:
            < 1.0: Team performs worse at home relative to league avg
            = 1.0: Team has average home court advantage
            > 1.0: Team has stronger than average home court advantage
        """
        # League average difference is about 4 points
        LEAGUE_AVG_HOME_ADV = 4.0
        
        home_margin = splits.get('home_margin_avg', 0)
        away_margin = splits.get('away_margin_avg', 0)
        
        # Team's home advantage = (home margin - away margin) / 2
        team_home_adv = (home_margin - away_margin) / 2
        
        # Ratio to league average
        if LEAGUE_AVG_HOME_ADV > 0:
            factor = team_home_adv / LEAGUE_AVG_HOME_ADV
        else:
            factor = 1.0
            
        # Clamp to reasonable range
        return round(max(0.5, min(2.0, factor)), 3)
    
    def get_team_splits(
        self, 
        team_id: str, 
        season: str
    ) -> Dict:
        """
        Get home/away splits for a specific team.
        
        Args:
            team_id: Team identifier
            season: Season string
            
        Returns:
            Dictionary with split statistics
        """
        key = (team_id, season)
        if key in self.splits:
            return self.splits[key]
        return DEFAULT_SPLITS.copy()
    
    def get_matchup_features(
        self,
        home_team_id: str,
        away_team_id: str,
        season: str
    ) -> Dict[str, float]:
        """
        Get venue-adjusted features for a specific matchup.
        
        Args:
            home_team_id: Home team identifier
            away_team_id: Away team identifier  
            season: Season string
            
        Returns:
            Dictionary with matchup-specific venue features
        """
        home_splits = self.get_team_splits(home_team_id, season)
        away_splits = self.get_team_splits(away_team_id, season)
        
        return {
            # Home team's home performance
            'home_team_home_wpct': home_splits['home_win_pct'],
            'home_team_home_margin': home_splits['home_margin_avg'],
            'home_team_home_adv': home_splits['home_advantage_factor'],
            
            # Away team's away performance
            'away_team_away_wpct': away_splits['away_win_pct'],
            'away_team_away_margin': away_splits['away_margin_avg'],
            'away_team_venue_consistency': away_splits['venue_consistency'],
            
            # Matchup-specific derived features
            'venue_wpct_diff': home_splits['home_win_pct'] - away_splits['away_win_pct'],
            'combined_home_adv': home_splits['home_advantage_factor'] * (2.0 - away_splits['venue_consistency']),
        }
    
    def enrich_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add home/away split features to a games dataframe.
        
        Args:
            df: DataFrame with home_team_id, away_team_id, and season
            
        Returns:
            DataFrame with additional venue split columns
        """
        if df.empty:
            return df
            
        df = df.copy()
        
        # Ensure we have required columns
        if 'season' not in df.columns:
            if 'Season' in df.columns:
                df['season'] = df['Season']
            else:
                df['season'] = '2024-25'
        
        if 'home_team_id' not in df.columns or 'away_team_id' not in df.columns:
            try:
                from model_training.team_id_utils import ensure_team_ids
                df = ensure_team_ids(df)
            except Exception:
                pass
        
        # Initialize feature columns
        feature_cols = [
            'home_team_home_wpct', 'home_team_home_margin', 'home_team_home_adv',
            'away_team_away_wpct', 'away_team_away_margin', 'away_team_venue_consistency',
            'venue_wpct_diff', 'combined_home_adv'
        ]
        for col in feature_cols:
            df[col] = 0.0
        
        for idx, row in df.iterrows():
            try:
                home_id = row.get('home_team_id', '')
                away_id = row.get('away_team_id', '')
                season = row.get('season', '2024-25')
                
                if home_id and away_id:
                    features = self.get_matchup_features(home_id, away_id, season)
                    for col, val in features.items():
                        if col in df.columns:
                            df.at[idx, col] = val
            except Exception:
                pass
        
        return df
    
    def save(self, path: Path | str = None) -> None:
        """Save splits to CSV file."""
        if path is None:
            path = Path('data') / 'feature_store' / 'home_away_splits.csv'
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        for (team_id, season), splits in self.splits.items():
            row = {'team_id': team_id, 'season': season}
            row.update(splits)
            rows.append(row)
        
        if rows:
            pd.DataFrame(rows).to_csv(path, index=False)
    
    def load(self, path: Path | str = None) -> bool:
        """Load splits from CSV file."""
        if path is None:
            path = Path('data') / 'feature_store' / 'home_away_splits.csv'
        
        try:
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                key = (row['team_id'], row['season'])
                splits = row.to_dict()
                del splits['team_id']
                del splits['season']
                self.splits[key] = splits
            return True
        except Exception:
            return False


def calculate_rest_days(
    game_date: str | datetime,
    team_id: str,
    games_df: pd.DataFrame,
    max_rest: int = 10
) -> int:
    """
    Calculate days of rest for a team before a game.
    
    Args:
        game_date: Date of the upcoming game
        team_id: Team to calculate rest for
        games_df: Historical games dataframe
        max_rest: Cap rest days at this value (avoid outliers)
        
    Returns:
        Number of days since last game (capped at max_rest)
    """
    if games_df.empty:
        return max_rest  # Assume well-rested if no data
    
    # Convert game_date to datetime
    try:
        if isinstance(game_date, str):
            game_date = pd.to_datetime(game_date)
        elif not isinstance(game_date, (datetime, pd.Timestamp)):
            game_date = pd.to_datetime(str(game_date))
    except Exception:
        return 3  # Default to average rest
    
    df = games_df.copy()
    
    # Ensure date column
    if 'date' not in df.columns:
        if 'Date' in df.columns:
            df['date'] = df['Date']
        else:
            return 3
    
    # Convert to datetime with error handling
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        # Drop rows where date conversion failed
        df = df.dropna(subset=['date'])
    except Exception:
        return 3
    
    if df.empty:
        return max_rest
    
    # Ensure team IDs
    if 'home_team_id' not in df.columns or 'away_team_id' not in df.columns:
        try:
            from model_training.team_id_utils import ensure_team_ids
            df = ensure_team_ids(df)
        except Exception:
            return 3
    
    # Find this team's games before the target date
    try:
        team_games = df[
            ((df['home_team_id'] == team_id) | (df['away_team_id'] == team_id)) &
            (df['date'] < game_date)
        ]
    except Exception:
        return 3
    
    if team_games.empty:
        return max_rest  # First game of season
    
    last_game_date = team_games['date'].max()
    rest_days = (game_date - last_game_date).days
    
    return min(max(1, rest_days), max_rest)


def add_rest_days_features(df: pd.DataFrame, historical_games: pd.DataFrame = None) -> pd.DataFrame:
    """
    Add rest days features to a games dataframe.
    
    Args:
        df: DataFrame with upcoming/current games
        historical_games: DataFrame with historical results for rest calculation
        
    Returns:
        DataFrame with home_rest_days and away_rest_days columns
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # If no historical games provided, try to load completed games
    if historical_games is None:
        try:
            historical_games = pd.read_csv('Completed_Games.csv')
        except Exception:
            historical_games = pd.DataFrame()
    
    if historical_games.empty:
        df['home_rest_days'] = 3
        df['away_rest_days'] = 3
        df['rest_advantage'] = 0
        return df
    
    # Ensure date column in target df
    if 'date' not in df.columns:
        if 'Date' in df.columns:
            df['date'] = df['Date']
        else:
            df['date'] = datetime.now().strftime('%Y-%m-%d')
    
    # Ensure team IDs
    if 'home_team_id' not in df.columns or 'away_team_id' not in df.columns:
        try:
            from model_training.team_id_utils import ensure_team_ids
            df = ensure_team_ids(df)
        except Exception:
            df['home_rest_days'] = 3
            df['away_rest_days'] = 3
            df['rest_advantage'] = 0
            return df
    
    # Calculate rest for each game
    home_rest = []
    away_rest = []
    
    for _, row in df.iterrows():
        game_date = row.get('date', row.get('Date', datetime.now()))
        home_id = row.get('home_team_id', '')
        away_id = row.get('away_team_id', '')
        
        h_rest = calculate_rest_days(game_date, home_id, historical_games)
        a_rest = calculate_rest_days(game_date, away_id, historical_games)
        
        home_rest.append(h_rest)
        away_rest.append(a_rest)
    
    df['home_rest_days'] = home_rest
    df['away_rest_days'] = away_rest
    df['rest_advantage'] = df['home_rest_days'] - df['away_rest_days']
    
    return df


__all__ = [
    'HomeAwaySplits', 'DEFAULT_SPLITS',
    'calculate_rest_days', 'add_rest_days_features'
]
