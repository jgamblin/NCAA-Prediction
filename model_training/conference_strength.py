"""
Conference Strength Module - Phase 4 Task 4.1

Calculates and applies conference-level strength adjustments to predictions.
Uses aggregate team performance within conferences to determine relative strength.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import json
import os


# Known conference mappings (subset of major conferences)
MAJOR_CONFERENCES = {
    'SEC', 'Big Ten', 'Big 12', 'ACC', 'Big East', 'Pac-12',
    'American', 'Mountain West', 'West Coast', 'Atlantic 10'
}


class ConferenceStrength:
    """
    Calculate and track conference-level strength ratings.
    
    Uses team performance aggregated by conference to compute:
    - Conference efficiency ratings
    - Non-conference win rates
    - Cross-conference performance
    """
    
    def __init__(self, 
                 conference_mapping_path: str = None,
                 min_games: int = 5):
        """
        Initialize ConferenceStrength calculator.
        
        Args:
            conference_mapping_path: Path to team->conference mapping JSON
            min_games: Minimum games required for valid conference rating
        """
        self.min_games = min_games
        self.conference_ratings: Dict[str, float] = {}
        self.conference_stats: Dict[str, dict] = {}
        self.team_conferences: Dict[str, str] = {}
        
        # Load conference mapping if provided
        if conference_mapping_path and os.path.exists(conference_mapping_path):
            self._load_conference_mapping(conference_mapping_path)
    
    def _load_conference_mapping(self, path: str) -> None:
        """Load team to conference mapping from JSON file."""
        try:
            with open(path, 'r') as f:
                self.team_conferences = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load conference mapping: {e}")
    
    def calculate_ratings(self, 
                         games_df: pd.DataFrame,
                         team_ratings: Dict[str, float] = None) -> Dict[str, float]:
        """
        Calculate conference strength ratings from game data.
        
        Uses two methods:
        1. Average team rating within conference
        2. Non-conference win rate
        
        Args:
            games_df: DataFrame with game results
            team_ratings: Optional dict of team power ratings
            
        Returns:
            Dict mapping conference name to strength rating
        """
        if games_df.empty:
            return {}
        
        # Ensure we have team conferences
        if not self.team_conferences:
            self._infer_conferences(games_df)
        
        # Method 1: Average team rating in conference
        if team_ratings:
            self._calculate_from_team_ratings(team_ratings)
        
        # Method 2: Non-conference performance
        self._calculate_from_nonconf_games(games_df)
        
        # Normalize ratings to 0-100 scale
        self._normalize_ratings()
        
        return self.conference_ratings
    
    def _infer_conferences(self, games_df: pd.DataFrame) -> None:
        """
        Infer conference assignments from game data patterns.
        
        Teams playing each other repeatedly are likely in same conference.
        """
        # Get all unique teams
        all_teams = set(games_df['home_team'].unique()) | set(games_df['away_team'].unique())
        
        # Count matchup frequency
        matchup_counts = {}
        for _, row in games_df.iterrows():
            teams = tuple(sorted([row['home_team'], row['away_team']]))
            matchup_counts[teams] = matchup_counts.get(teams, 0) + 1
        
        # Teams playing 2+ times are likely conference opponents
        # This is a simple heuristic - real data would be better
        frequent_matchups = {k: v for k, v in matchup_counts.items() if v >= 2}
        
        # For now, assign unknown conference to all teams without mapping
        for team in all_teams:
            if team not in self.team_conferences:
                self.team_conferences[team] = 'Unknown'
    
    def _calculate_from_team_ratings(self, team_ratings: Dict[str, float]) -> None:
        """Calculate conference ratings from individual team ratings."""
        conf_teams: Dict[str, list] = {}
        
        for team, rating in team_ratings.items():
            # Handle dict-style ratings (from PowerRatings) or simple floats
            if isinstance(rating, dict):
                rating_value = rating.get('overall', rating.get('net_rating', 0))
            else:
                rating_value = rating
            
            conf = self.team_conferences.get(team, 'Unknown')
            if conf not in conf_teams:
                conf_teams[conf] = []
            conf_teams[conf].append(rating_value)
        
        for conf, ratings in conf_teams.items():
            if len(ratings) >= self.min_games:
                # Use weighted average - top teams matter more
                sorted_ratings = sorted(ratings, reverse=True)
                weights = [1.5 if i < 4 else 1.0 for i in range(len(sorted_ratings))]
                self.conference_ratings[conf] = np.average(sorted_ratings, weights=weights)
    
    def _calculate_from_nonconf_games(self, games_df: pd.DataFrame) -> None:
        """Calculate conference strength from non-conference game results."""
        conf_results: Dict[str, dict] = {}
        
        for _, row in games_df.iterrows():
            home_conf = self.team_conferences.get(row['home_team'], 'Unknown')
            away_conf = self.team_conferences.get(row['away_team'], 'Unknown')
            
            # Skip conference games
            if home_conf == away_conf:
                continue
            
            home_won = row.get('home_score', 0) > row.get('away_score', 0)
            
            # Track wins/losses for each conference
            for conf, won in [(home_conf, home_won), (away_conf, not home_won)]:
                if conf not in conf_results:
                    conf_results[conf] = {'wins': 0, 'losses': 0, 'point_diff': 0}
                
                if won:
                    conf_results[conf]['wins'] += 1
                else:
                    conf_results[conf]['losses'] += 1
                
                # Track point differential
                if conf == home_conf:
                    diff = row.get('home_score', 0) - row.get('away_score', 0)
                else:
                    diff = row.get('away_score', 0) - row.get('home_score', 0)
                conf_results[conf]['point_diff'] += diff
        
        # Calculate non-conf win rate as strength indicator
        for conf, results in conf_results.items():
            total = results['wins'] + results['losses']
            if total >= self.min_games:
                win_rate = results['wins'] / total
                avg_margin = results['point_diff'] / total
                
                # Combine win rate and margin
                # Scale: 50% win rate = 0, each 10% = +/- 10 points
                rating = (win_rate - 0.5) * 100 + avg_margin * 0.5
                
                # Blend with existing rating if available
                if conf in self.conference_ratings:
                    self.conference_ratings[conf] = (
                        0.6 * self.conference_ratings[conf] + 0.4 * rating
                    )
                else:
                    self.conference_ratings[conf] = rating
                
                self.conference_stats[conf] = {
                    'nonconf_wins': results['wins'],
                    'nonconf_losses': results['losses'],
                    'nonconf_win_rate': win_rate,
                    'avg_margin': avg_margin
                }
    
    def _normalize_ratings(self) -> None:
        """Normalize ratings to 0-100 scale with mean 50."""
        if not self.conference_ratings:
            return
        
        values = list(self.conference_ratings.values())
        if len(values) < 2:
            return
        
        mean_rating = np.mean(values)
        std_rating = np.std(values) or 1.0
        
        for conf in self.conference_ratings:
            # Z-score normalize then scale to 50 +/- 25
            z = (self.conference_ratings[conf] - mean_rating) / std_rating
            self.conference_ratings[conf] = 50 + z * 15
    
    def get_conference(self, team: str) -> str:
        """Get conference for a team."""
        return self.team_conferences.get(team, 'Unknown')
    
    def get_conference_rating(self, conference: str) -> float:
        """Get strength rating for a conference."""
        return self.conference_ratings.get(conference, 50.0)
    
    def get_team_conference_rating(self, team: str) -> float:
        """Get conference rating for a team's conference."""
        conf = self.get_conference(team)
        return self.get_conference_rating(conf)
    
    def get_conference_differential(self, 
                                    home_team: str, 
                                    away_team: str) -> float:
        """
        Get conference strength differential between two teams.
        
        Positive value favors home team's conference.
        """
        home_rating = self.get_team_conference_rating(home_team)
        away_rating = self.get_team_conference_rating(away_team)
        return home_rating - away_rating
    
    def get_rankings(self) -> pd.DataFrame:
        """Get conference rankings as DataFrame."""
        if not self.conference_ratings:
            return pd.DataFrame()
        
        data = []
        for conf, rating in sorted(self.conference_ratings.items(), 
                                   key=lambda x: x[1], reverse=True):
            stats = self.conference_stats.get(conf, {})
            data.append({
                'conference': conf,
                'rating': rating,
                'nonconf_wins': stats.get('nonconf_wins', 0),
                'nonconf_losses': stats.get('nonconf_losses', 0),
                'nonconf_win_rate': stats.get('nonconf_win_rate', 0),
                'avg_margin': stats.get('avg_margin', 0)
            })
        
        return pd.DataFrame(data)
    
    def save_ratings(self, path: str) -> None:
        """Save conference ratings to JSON file."""
        data = {
            'ratings': self.conference_ratings,
            'stats': self.conference_stats
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_ratings(self, path: str) -> None:
        """Load conference ratings from JSON file."""
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                self.conference_ratings = data.get('ratings', {})
                self.conference_stats = data.get('stats', {})


def add_conference_features(df: pd.DataFrame,
                           conference_strength: ConferenceStrength) -> pd.DataFrame:
    """
    Add conference strength features to a games dataframe.
    
    Features added:
    - home_conf_rating: Home team's conference strength
    - away_conf_rating: Away team's conference strength  
    - conf_rating_diff: Conference strength differential (home - away)
    - is_conf_game: Whether teams are in same conference
    """
    df = df.copy()
    
    df['home_conf_rating'] = df['home_team'].apply(
        conference_strength.get_team_conference_rating
    )
    df['away_conf_rating'] = df['away_team'].apply(
        conference_strength.get_team_conference_rating
    )
    df['conf_rating_diff'] = df['home_conf_rating'] - df['away_conf_rating']
    
    df['home_conference'] = df['home_team'].apply(conference_strength.get_conference)
    df['away_conference'] = df['away_team'].apply(conference_strength.get_conference)
    df['is_conf_game'] = df['home_conference'] == df['away_conference']
    
    return df
