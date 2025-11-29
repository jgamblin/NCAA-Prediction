"""
Recency Weighting / Momentum Module - Phase 4 Task 4.2

Applies time-based weighting to give more importance to recent games
and captures team momentum/hot streaks.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List


class RecencyWeighting:
    """
    Apply recency-based weighting to team statistics and predictions.
    
    Recent games are weighted more heavily than older games when
    calculating rolling statistics and making predictions.
    """
    
    def __init__(self,
                 decay_rate: float = 0.1,
                 half_life_days: int = 14,
                 min_games: int = 3):
        """
        Initialize RecencyWeighting calculator.
        
        Args:
            decay_rate: Exponential decay rate for older games
            half_life_days: Days after which a game has half weight
            min_games: Minimum games required for valid calculation
        """
        self.decay_rate = decay_rate
        self.half_life_days = half_life_days
        self.min_games = min_games
        
        # Momentum tracking
        self.team_momentum: Dict[str, float] = {}
        self.team_streak: Dict[str, int] = {}
        self.team_last_results: Dict[str, List[int]] = {}
    
    def calculate_weight(self, 
                        game_date: datetime, 
                        reference_date: datetime = None) -> float:
        """
        Calculate weight for a game based on recency.
        
        Uses exponential decay with configurable half-life.
        
        Args:
            game_date: Date of the game
            reference_date: Reference date (default: today)
            
        Returns:
            Weight between 0 and 1
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        if isinstance(game_date, str):
            game_date = pd.to_datetime(game_date)
        if isinstance(reference_date, str):
            reference_date = pd.to_datetime(reference_date)
        
        days_ago = (reference_date - game_date).days
        
        if days_ago < 0:
            return 1.0  # Future games get full weight
        
        # Exponential decay: weight = 0.5^(days/half_life)
        weight = 0.5 ** (days_ago / self.half_life_days)
        
        return max(0.01, weight)  # Minimum 1% weight
    
    def calculate_weighted_average(self,
                                   values: List[float],
                                   dates: List[datetime],
                                   reference_date: datetime = None) -> float:
        """
        Calculate weighted average of values based on recency.
        
        Args:
            values: List of values to average
            dates: Corresponding dates for each value
            reference_date: Reference date for weighting
            
        Returns:
            Weighted average
        """
        if not values or not dates:
            return 0.0
        
        weights = [self.calculate_weight(d, reference_date) for d in dates]
        
        return np.average(values, weights=weights)
    
    def calculate_momentum(self,
                          games_df: pd.DataFrame,
                          reference_date: datetime = None) -> Dict[str, float]:
        """
        Calculate momentum scores for all teams.
        
        Momentum considers:
        - Recent win rate (weighted by recency)
        - Win/loss streak
        - Margin of victory trend
        
        Args:
            games_df: DataFrame with game results
            reference_date: Reference date for calculations
            
        Returns:
            Dict mapping team to momentum score (-1 to 1)
        """
        if games_df.empty:
            return {}
        
        if reference_date is None:
            reference_date = pd.to_datetime(games_df['date'].max())
        
        # Ensure date column is datetime
        games_df = games_df.copy()
        games_df['date'] = pd.to_datetime(games_df['date'])
        
        # Calculate momentum for each team
        all_teams = set(games_df['home_team'].unique()) | set(games_df['away_team'].unique())
        
        for team in all_teams:
            # Get team's recent games
            team_games = games_df[
                (games_df['home_team'] == team) | (games_df['away_team'] == team)
            ].sort_values('date', ascending=False)
            
            if len(team_games) < self.min_games:
                self.team_momentum[team] = 0.0
                self.team_streak[team] = 0
                continue
            
            # Calculate weighted win rate
            results = []
            margins = []
            dates = []
            
            for _, game in team_games.head(10).iterrows():  # Last 10 games
                is_home = game['home_team'] == team
                home_score = game.get('home_score', 0) or 0
                away_score = game.get('away_score', 0) or 0
                
                if is_home:
                    won = home_score > away_score
                    margin = home_score - away_score
                else:
                    won = away_score > home_score
                    margin = away_score - home_score
                
                results.append(1 if won else 0)
                margins.append(margin)
                dates.append(game['date'])
            
            self.team_last_results[team] = results[:5]  # Store last 5 results
            
            # Calculate weighted win rate
            weighted_win_rate = self.calculate_weighted_average(results, dates, reference_date)
            
            # Calculate streak
            streak = 0
            if results:
                current = results[0]
                for r in results:
                    if r == current:
                        streak += 1 if current == 1 else -1
                    else:
                        break
            self.team_streak[team] = streak
            
            # Calculate momentum: weighted win rate + streak bonus
            # Scale: -1 (cold) to +1 (hot)
            streak_bonus = min(abs(streak), 5) * 0.05 * (1 if streak > 0 else -1)
            momentum = (weighted_win_rate - 0.5) * 2 + streak_bonus
            
            self.team_momentum[team] = np.clip(momentum, -1.0, 1.0)
        
        return self.team_momentum
    
    def get_momentum(self, team: str) -> float:
        """Get momentum score for a team."""
        return self.team_momentum.get(team, 0.0)
    
    def get_streak(self, team: str) -> int:
        """Get current streak for a team (positive=wins, negative=losses)."""
        return self.team_streak.get(team, 0)
    
    def get_momentum_differential(self, home_team: str, away_team: str) -> float:
        """Get momentum differential between two teams."""
        return self.get_momentum(home_team) - self.get_momentum(away_team)
    
    def is_hot(self, team: str, threshold: float = 0.3) -> bool:
        """Check if team is on a hot streak."""
        return self.get_momentum(team) > threshold
    
    def is_cold(self, team: str, threshold: float = -0.3) -> bool:
        """Check if team is on a cold streak."""
        return self.get_momentum(team) < threshold


def add_momentum_features(df: pd.DataFrame,
                         recency: RecencyWeighting,
                         games_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Add momentum-based features to a games dataframe.
    
    Features added:
    - home_momentum: Home team's momentum score
    - away_momentum: Away team's momentum score
    - momentum_diff: Momentum differential (home - away)
    - home_streak: Home team's current streak
    - away_streak: Away team's current streak
    - home_is_hot: Whether home team is hot
    - away_is_hot: Whether away team is hot
    """
    df = df.copy()
    
    # Calculate momentum if not already done
    if games_df is not None and not recency.team_momentum:
        recency.calculate_momentum(games_df)
    
    df['home_momentum'] = df['home_team'].apply(recency.get_momentum)
    df['away_momentum'] = df['away_team'].apply(recency.get_momentum)
    df['momentum_diff'] = df['home_momentum'] - df['away_momentum']
    
    df['home_streak'] = df['home_team'].apply(recency.get_streak)
    df['away_streak'] = df['away_team'].apply(recency.get_streak)
    
    df['home_is_hot'] = df['home_team'].apply(recency.is_hot)
    df['away_is_hot'] = df['away_team'].apply(recency.is_hot)
    
    return df


def apply_recency_weights(stats_df: pd.DataFrame,
                         date_col: str = 'date',
                         half_life_days: int = 14,
                         reference_date: datetime = None) -> pd.DataFrame:
    """
    Apply recency weights to a statistics dataframe.
    
    Adds a 'weight' column that can be used in weighted calculations.
    
    Args:
        stats_df: DataFrame with statistics
        date_col: Name of date column
        half_life_days: Days for weight to halve
        reference_date: Reference date for weighting
        
    Returns:
        DataFrame with 'weight' column added
    """
    df = stats_df.copy()
    
    if reference_date is None:
        reference_date = pd.to_datetime(df[date_col].max())
    
    df[date_col] = pd.to_datetime(df[date_col])
    
    recency = RecencyWeighting(half_life_days=half_life_days)
    df['weight'] = df[date_col].apply(
        lambda d: recency.calculate_weight(d, reference_date)
    )
    
    return df
