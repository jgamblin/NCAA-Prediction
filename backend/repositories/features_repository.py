"""Repository for team features data access."""

from typing import List, Optional, Dict
import pandas as pd
from backend.database.connection import DatabaseConnection


class FeaturesRepository:
    """Handles all team features database operations."""
    
    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn
    
    def get_team_features(self, team_id: str, season: str) -> Optional[Dict]:
        """Get features for a specific team and season."""
        query = """
            SELECT * FROM team_features 
            WHERE team_id = ? AND season = ?
        """
        return self.db.fetch_one(query, (team_id, season))
    
    def get_all_features_for_season(self, season: str) -> pd.DataFrame:
        """Get all team features for a season as DataFrame."""
        query = """
            SELECT * FROM team_features 
            WHERE season = ?
            ORDER BY team_id
        """
        return self.db.fetch_df(query, (season,))
    
    def get_feature_store_df(self) -> pd.DataFrame:
        """Get complete feature store as DataFrame (replaces feature_store.csv)."""
        query = """
            SELECT * FROM team_features 
            ORDER BY season DESC, team_id
        """
        return self.db.fetch_df(query)
    
    def insert_features(self, features_data: Dict) -> bool:
        """Insert team features for a season."""
        query = """
            INSERT INTO team_features 
            (team_id, season, games_played, rolling_win_pct_5, rolling_win_pct_10,
             rolling_point_diff_avg_5, rolling_point_diff_avg_10,
             win_pct_last5_vs10, point_diff_last5_vs10, recent_strength_index_5,
             total_wins, total_losses, avg_points_scored, avg_points_allowed,
             home_win_pct, away_win_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, (
                    features_data['team_id'],
                    features_data['season'],
                    features_data.get('games_played', 0),
                    features_data.get('rolling_win_pct_5'),
                    features_data.get('rolling_win_pct_10'),
                    features_data.get('rolling_point_diff_avg_5'),
                    features_data.get('rolling_point_diff_avg_10'),
                    features_data.get('win_pct_last5_vs10'),
                    features_data.get('point_diff_last5_vs10'),
                    features_data.get('recent_strength_index_5'),
                    features_data.get('total_wins', 0),
                    features_data.get('total_losses', 0),
                    features_data.get('avg_points_scored'),
                    features_data.get('avg_points_allowed'),
                    features_data.get('home_win_pct'),
                    features_data.get('away_win_pct')
                ))
            return True
        except Exception as e:
            print(f"Error inserting features: {e}")
            return False
    
    def update_features(self, team_id: str, season: str, features_data: Dict) -> bool:
        """Update team features."""
        # Build dynamic update query
        fields = []
        values = []
        
        for key, value in features_data.items():
            if key not in ['team_id', 'season', 'id']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.extend([team_id, season])
        query = f"""
            UPDATE team_features 
            SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE team_id = ? AND season = ?
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating features: {e}")
            return False
    
    def upsert_features(self, features_data: Dict) -> bool:
        """Insert or update team features (upsert)."""
        existing = self.get_team_features(
            features_data['team_id'],
            features_data['season']
        )
        
        if existing:
            return self.update_features(
                features_data['team_id'],
                features_data['season'],
                features_data
            )
        else:
            return self.insert_features(features_data)
    
    def bulk_upsert_features(self, features_list: List[Dict]) -> int:
        """Bulk insert or update features."""
        updated = 0
        for features in features_list:
            if self.upsert_features(features):
                updated += 1
        return updated
    
    def get_teams_needing_updates(
        self, 
        season: str,
        min_games_played: int = 5
    ) -> List[str]:
        """Get list of teams that may need feature updates."""
        query = """
            SELECT DISTINCT team_id 
            FROM team_features 
            WHERE season = ? AND games_played >= ?
            ORDER BY updated_at ASC
            LIMIT 100
        """
        results = self.db.fetch_all(query, (season, min_games_played))
        return [r['team_id'] for r in results]
    
    def get_top_teams_by_metric(
        self,
        season: str,
        metric: str = 'rolling_win_pct_10',
        limit: int = 25
    ) -> List[Dict]:
        """Get top teams ranked by a specific metric."""
        # Validate metric to prevent SQL injection
        valid_metrics = [
            'rolling_win_pct_5', 'rolling_win_pct_10',
            'rolling_point_diff_avg_5', 'rolling_point_diff_avg_10',
            'recent_strength_index_5', 'avg_points_scored'
        ]
        
        if metric not in valid_metrics:
            metric = 'rolling_win_pct_10'
        
        query = f"""
            SELECT 
                tf.*,
                t.display_name,
                t.conference
            FROM team_features tf
            JOIN teams t ON tf.team_id = t.team_id
            WHERE tf.season = ? AND tf.{metric} IS NOT NULL
            ORDER BY tf.{metric} DESC
            LIMIT ?
        """
        return self.db.fetch_all(query, (season, limit))
    
    def calculate_league_averages(self, season: str) -> Dict:
        """Calculate league-wide average statistics."""
        query = """
            SELECT 
                AVG(rolling_win_pct_10) as avg_win_pct,
                AVG(rolling_point_diff_avg_10) as avg_point_diff,
                AVG(recent_strength_index_5) as avg_strength_index,
                AVG(avg_points_scored) as avg_points_scored,
                AVG(avg_points_allowed) as avg_points_allowed,
                COUNT(*) as total_teams
            FROM team_features
            WHERE season = ? AND games_played >= 5
        """
        return self.db.fetch_one(query, (season,))
    
    def get_features_with_fallback(
        self,
        team_id: str,
        current_season: str,
        prior_season: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get team features with fallback to prior season.
        Implements the fallback hierarchy from feature_store.py.
        """
        # Try current season first
        features = self.get_team_features(team_id, current_season)
        
        if features and features.get('games_played', 0) >= 5:
            return features
        
        # Try prior season
        if prior_season:
            prior_features = self.get_team_features(team_id, prior_season)
            if prior_features and prior_features.get('games_played', 0) >= 5:
                return prior_features
        
        # Fallback to league averages
        league_avg = self.calculate_league_averages(current_season)
        if league_avg:
            return {
                'team_id': team_id,
                'season': current_season,
                'games_played': 0,
                'rolling_win_pct_5': league_avg.get('avg_win_pct', 0.5),
                'rolling_win_pct_10': league_avg.get('avg_win_pct', 0.5),
                'rolling_point_diff_avg_5': league_avg.get('avg_point_diff', 0.0),
                'rolling_point_diff_avg_10': league_avg.get('avg_point_diff', 0.0),
                'recent_strength_index_5': league_avg.get('avg_strength_index', 0.0),
                'source': 'league_average'
            }
        
        return None
    
    def delete_old_features(self, seasons_to_keep: int = 5) -> int:
        """Delete features for old seasons."""
        query = """
            DELETE FROM team_features 
            WHERE season NOT IN (
                SELECT DISTINCT season 
                FROM team_features 
                ORDER BY season DESC 
                LIMIT ?
            )
        """
        
        try:
            with self.db.transaction() as conn:
                result = conn.execute(query, (seasons_to_keep,))
                return result.rowcount if hasattr(result, 'rowcount') else 0
        except Exception as e:
            print(f"Error deleting old features: {e}")
            return 0
