"""
Power Ratings Module for NCAA Basketball

Calculates adjusted efficiency ratings for all teams based on game results.
Similar methodology to KenPom but simplified for our use case.

Key Metrics:
- Adjusted Offensive Efficiency (AdjO): Points per 100 possessions, adjusted for opponent
- Adjusted Defensive Efficiency (AdjD): Points allowed per 100 possessions, adjusted for opponent
- Net Rating: AdjO - AdjD (positive = good team)

Phase 2 Implementation - November 29, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import json

# Default paths
DATA_DIR = Path('data')
RATINGS_PATH = DATA_DIR / 'power_ratings.csv'
RATINGS_CACHE_PATH = DATA_DIR / 'power_ratings_cache.json'


class PowerRatings:
    """
    Calculate and manage team power ratings using adjusted efficiency margin.
    """
    
    # League average efficiency (baseline)
    LEAGUE_AVG_EFFICIENCY = 100.0
    
    # Default rating for unknown teams
    DEFAULT_RATING = {
        'adj_offense': 100.0,
        'adj_defense': 100.0,
        'net_rating': 0.0,
        'rank': 180,
        'games_played': 0,
        'sos_rating': 0.0,
        'overall': 0.0,
        'offensive': 100.0,
        'defensive': 100.0,
    }
    
    def __init__(self, data_path: str = None, n_iterations: int = 15):
        """
        Initialize PowerRatings calculator.
        
        Args:
            data_path: Path to save/load ratings
            n_iterations: Number of iterations for convergence
        """
        self.data_path = Path(data_path) if data_path else RATINGS_PATH
        self.ratings: Dict[str, dict] = {}
        self.team_games: Dict[str, list] = {}
        self.last_updated: Optional[str] = None
        self.n_iterations = n_iterations
        
    def calculate_ratings(self, games_df: pd.DataFrame, iterations: int = None) -> pd.DataFrame:
        """
        Calculate power ratings from completed game results.
        
        Uses iterative adjustment:
        1. Start with raw efficiency (points per estimated possession)
        2. Adjust for opponent strength
        3. Repeat until convergence
        
        Args:
            games_df: DataFrame with home_team, away_team, home_score, away_score
            iterations: Number of iterative adjustments (defaults to self.n_iterations)
            
        Returns:
            DataFrame with ratings for all teams
        """
        if iterations is None:
            iterations = self.n_iterations
        # Filter to completed games with valid scores
        games_df = games_df.copy()
        games_df = games_df.dropna(subset=['home_score', 'away_score'])
        games_df = games_df[
            (games_df['home_score'] > 0) | (games_df['away_score'] > 0)
        ]
        
        if games_df.empty:
            print("Warning: No valid games for power ratings calculation")
            return pd.DataFrame()
        
        # Get all teams
        all_teams = set(games_df['home_team'].unique()) | set(games_df['away_team'].unique())
        
        # Initialize ratings
        for team in all_teams:
            self.ratings[team] = {
                'adj_offense': self.LEAGUE_AVG_EFFICIENCY,
                'adj_defense': self.LEAGUE_AVG_EFFICIENCY,
                'raw_offense': self.LEAGUE_AVG_EFFICIENCY,
                'raw_defense': self.LEAGUE_AVG_EFFICIENCY,
                'net_rating': 0.0,
                'games_played': 0,
                'wins': 0,
                'losses': 0,
                'total_points_scored': 0,
                'total_points_allowed': 0,
                'sos_rating': 0.0
            }
        
        # Store games for each team
        self._build_team_games(games_df)
        
        # Calculate raw efficiency first
        self._calculate_raw_efficiency(games_df)
        
        # Iterative adjustment for opponent strength
        print(f"  Calculating power ratings ({iterations} iterations)...")
        for i in range(iterations):
            self._adjust_for_opponents()
            
        # Calculate final net ratings and ranks
        self._finalize_ratings()
        
        # Calculate SOS
        self._calculate_sos()
        
        self.last_updated = datetime.now(timezone.utc).isoformat()
        
        # Convert to DataFrame
        ratings_df = pd.DataFrame.from_dict(self.ratings, orient='index')
        ratings_df['team'] = ratings_df.index
        ratings_df = ratings_df.reset_index(drop=True)
        
        # Sort by net rating
        ratings_df = ratings_df.sort_values('net_rating', ascending=False).reset_index(drop=True)
        ratings_df['rank'] = range(1, len(ratings_df) + 1)
        
        return ratings_df
    
    def _build_team_games(self, games_df: pd.DataFrame):
        """Build dictionary of games per team."""
        self.team_games = {team: [] for team in self.ratings}
        
        for _, game in games_df.iterrows():
            home = game['home_team']
            away = game['away_team']
            
            try:
                h_score = int(game['home_score'])
                a_score = int(game['away_score'])
            except (ValueError, TypeError):
                continue
            
            # Home team perspective
            if home in self.team_games:
                self.team_games[home].append({
                    'opponent': away,
                    'scored': h_score,
                    'allowed': a_score,
                    'is_home': True,
                    'won': h_score > a_score,
                    'date': game.get('date', '')
                })
            
            # Away team perspective
            if away in self.team_games:
                self.team_games[away].append({
                    'opponent': home,
                    'scored': a_score,
                    'allowed': h_score,
                    'is_home': False,
                    'won': a_score > h_score,
                    'date': game.get('date', '')
                })
    
    def _calculate_raw_efficiency(self, games_df: pd.DataFrame):
        """Calculate raw efficiency for each team."""
        for team, games in self.team_games.items():
            if not games:
                continue
            
            total_scored = 0
            total_allowed = 0
            total_possessions = 0
            wins = 0
            
            for game in games:
                scored = game['scored']
                allowed = game['allowed']
                
                # Estimate possessions (simplified formula)
                # Real formula would use FGA, TO, FTA, OREB
                possessions = (scored + allowed) / 2 * 0.96
                
                total_scored += scored
                total_allowed += allowed
                total_possessions += possessions
                
                if game['won']:
                    wins += 1
            
            n_games = len(games)
            
            if total_possessions > 0:
                raw_off = (total_scored / total_possessions) * 100
                raw_def = (total_allowed / total_possessions) * 100
            else:
                raw_off = self.LEAGUE_AVG_EFFICIENCY
                raw_def = self.LEAGUE_AVG_EFFICIENCY
            
            self.ratings[team]['raw_offense'] = raw_off
            self.ratings[team]['raw_defense'] = raw_def
            self.ratings[team]['adj_offense'] = raw_off
            self.ratings[team]['adj_defense'] = raw_def
            self.ratings[team]['games_played'] = n_games
            self.ratings[team]['wins'] = wins
            self.ratings[team]['losses'] = n_games - wins
            self.ratings[team]['total_points_scored'] = total_scored
            self.ratings[team]['total_points_allowed'] = total_allowed
    
    def _adjust_for_opponents(self):
        """Single iteration of opponent-adjusted efficiency."""
        new_adj_off = {}
        new_adj_def = {}
        
        for team, games in self.team_games.items():
            if not games:
                continue
            
            adj_offs = []
            adj_defs = []
            weights = []
            
            for i, game in enumerate(games):
                opp = game['opponent']
                scored = game['scored']
                allowed = game['allowed']
                
                # Estimate possessions
                possessions = (scored + allowed) / 2 * 0.96
                if possessions <= 0:
                    continue
                
                # Raw efficiency this game
                raw_off = (scored / possessions) * 100
                raw_def = (allowed / possessions) * 100
                
                # Get opponent's current adjusted ratings
                opp_rating = self.ratings.get(opp, self.DEFAULT_RATING)
                opp_adj_off = opp_rating.get('adj_offense', self.LEAGUE_AVG_EFFICIENCY)
                opp_adj_def = opp_rating.get('adj_defense', self.LEAGUE_AVG_EFFICIENCY)
                
                # Adjust: if opponent has strong defense, boost our offense
                # Formula: adj_eff = raw_eff * (league_avg / opponent_rating)
                if opp_adj_def > 0:
                    adj_off = raw_off * (self.LEAGUE_AVG_EFFICIENCY / opp_adj_def)
                else:
                    adj_off = raw_off
                    
                if opp_adj_off > 0:
                    adj_def = raw_def * (self.LEAGUE_AVG_EFFICIENCY / opp_adj_off)
                else:
                    adj_def = raw_def
                
                # Recency weight (more recent games weighted higher)
                weight = 0.5 + 0.5 * (i / len(games))
                
                adj_offs.append(adj_off)
                adj_defs.append(adj_def)
                weights.append(weight)
            
            if adj_offs:
                new_adj_off[team] = np.average(adj_offs, weights=weights)
                new_adj_def[team] = np.average(adj_defs, weights=weights)
        
        # Update ratings
        for team in new_adj_off:
            self.ratings[team]['adj_offense'] = new_adj_off[team]
            self.ratings[team]['adj_defense'] = new_adj_def[team]
    
    def _finalize_ratings(self):
        """Calculate final net ratings."""
        for team in self.ratings:
            adj_off = self.ratings[team]['adj_offense']
            adj_def = self.ratings[team]['adj_defense']
            self.ratings[team]['net_rating'] = adj_off - adj_def
            # Add compatibility fields for external access
            self.ratings[team]['overall'] = adj_off - adj_def
            self.ratings[team]['offensive'] = adj_off
            self.ratings[team]['defensive'] = adj_def
    
    def _calculate_sos(self):
        """Calculate strength of schedule for each team."""
        for team, games in self.team_games.items():
            if not games:
                self.ratings[team]['sos_rating'] = 0.0
                continue
            
            opp_ratings = []
            for game in games:
                opp = game['opponent']
                opp_net = self.ratings.get(opp, self.DEFAULT_RATING).get('net_rating', 0.0)
                opp_ratings.append(opp_net)
            
            self.ratings[team]['sos_rating'] = np.mean(opp_ratings) if opp_ratings else 0.0
    
    def calculate_sos(self, team: str, season: str = None) -> float:
        """
        Public method to get strength of schedule for a team.
        
        Args:
            team: Team name or ID
            season: Season string (optional, for future multi-season support)
            
        Returns:
            SOS rating (average opponent net rating)
        """
        rating = self.ratings.get(team, self.DEFAULT_RATING)
        return rating.get('sos_rating', 0.0)
    
    def get_matchup_features(self, home_team: str, away_team: str, 
                              season: str = None) -> dict:
        """
        Get power rating features for a specific matchup.
        
        Args:
            home_team: Home team name or ID
            away_team: Away team name or ID
            season: Season string (optional)
            
        Returns:
            Dictionary of matchup features for model input
        """
        home_rating = self.get_team_rating(home_team)
        away_rating = self.get_team_rating(away_team)
        
        home_sos = self.calculate_sos(home_team)
        away_sos = self.calculate_sos(away_team)
        
        return {
            'power_rating_diff': home_rating['net_rating'] - away_rating['net_rating'],
            'off_rating_diff': home_rating['adj_offense'] - away_rating['adj_offense'],
            'def_rating_diff': home_rating['adj_defense'] - away_rating['adj_defense'],
            'home_sos': home_sos,
            'away_sos': away_sos,
            'sos_diff': home_sos - away_sos,
            'home_net_rating': home_rating['net_rating'],
            'away_net_rating': away_rating['net_rating'],
        }
    
    def enrich_dataframe_with_power_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add power rating features to a games dataframe.
        
        Args:
            df: DataFrame with home_team and away_team columns
            
        Returns:
            DataFrame with power rating feature columns added
        """
        if df.empty:
            return df
        
        df = df.copy()
        
        # Initialize columns
        feature_cols = [
            'power_rating_diff', 'off_rating_diff', 'def_rating_diff',
            'home_sos', 'away_sos', 'sos_diff'
        ]
        for col in feature_cols:
            df[col] = 0.0
        
        for idx, row in df.iterrows():
            home = row.get('home_team', '')
            away = row.get('away_team', '')
            
            if home and away:
                features = self.get_matchup_features(home, away)
                for col in feature_cols:
                    if col in features:
                        df.at[idx, col] = features[col]
        
        return df

    def get_team_rating(self, team: str) -> dict:
        """Get rating for a specific team."""
        return self.ratings.get(team, self.DEFAULT_RATING.copy())
    
    def get_matchup_prediction(self, home_team: str, away_team: str, 
                                neutral: bool = False) -> dict:
        """
        Predict game outcome based on power ratings.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            neutral: If True, no home court advantage
            
        Returns:
            dict with predicted margin, win probability
        """
        home_rating = self.get_team_rating(home_team)
        away_rating = self.get_team_rating(away_team)
        
        home_net = home_rating.get('net_rating', 0.0)
        away_net = away_rating.get('net_rating', 0.0)
        
        # Raw expected margin from ratings
        expected_margin = home_net - away_net
        
        # Add home court advantage (~3.5 points historically)
        if not neutral:
            expected_margin += 3.5
        
        # Convert margin to win probability (logistic function)
        # Based on historical data: ~11 point margin = ~85% win prob
        k = 0.15  # Steepness parameter
        home_win_prob = 1 / (1 + np.exp(-k * expected_margin))
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'expected_margin': expected_margin,
            'home_win_probability': home_win_prob,
            'away_win_probability': 1 - home_win_prob,
            'home_net_rating': home_net,
            'away_net_rating': away_net,
            'rating_diff': home_net - away_net
        }
    
    def save(self, path: str = None):
        """Save ratings to CSV."""
        save_path = Path(path) if path else self.data_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        df = pd.DataFrame.from_dict(self.ratings, orient='index')
        df['team'] = df.index
        df['updated_at'] = self.last_updated
        df.to_csv(save_path, index=False)
        
        print(f"  Saved power ratings for {len(df)} teams to {save_path}")
    
    def load(self, path: str = None) -> bool:
        """Load ratings from CSV."""
        load_path = Path(path) if path else self.data_path
        
        try:
            df = pd.read_csv(load_path)
            self.ratings = {}
            
            for _, row in df.iterrows():
                team = row['team']
                self.ratings[team] = {
                    'adj_offense': row.get('adj_offense', 100.0),
                    'adj_defense': row.get('adj_defense', 100.0),
                    'net_rating': row.get('net_rating', 0.0),
                    'rank': row.get('rank', 180),
                    'games_played': row.get('games_played', 0),
                    'sos_rating': row.get('sos_rating', 0.0),
                    'wins': row.get('wins', 0),
                    'losses': row.get('losses', 0)
                }
            
            self.last_updated = df['updated_at'].iloc[0] if 'updated_at' in df.columns else None
            return True
            
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Warning: Failed to load power ratings: {e}")
            return False


def build_power_ratings(games_df: pd.DataFrame = None) -> PowerRatings:
    """
    Build power ratings from games data.
    
    Args:
        games_df: Optional DataFrame of completed games. 
                  If None, loads from Completed_Games.csv
    
    Returns:
        PowerRatings instance with calculated ratings
    """
    if games_df is None:
        games_path = DATA_DIR / 'Completed_Games.csv'
        if not games_path.exists():
            print("Warning: Completed_Games.csv not found")
            return PowerRatings()
        games_df = pd.read_csv(games_path)
    
    # Filter to Final games only
    if 'game_status' in games_df.columns:
        games_df = games_df[games_df['game_status'] == 'Final']
    
    pr = PowerRatings()
    pr.calculate_ratings(games_df)
    pr.save()
    
    return pr


__all__ = ['PowerRatings', 'build_power_ratings', 'RATINGS_PATH']
