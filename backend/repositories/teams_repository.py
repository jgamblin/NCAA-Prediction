"""Repository for team data access."""

from typing import List, Optional, Dict
import pandas as pd
from backend.database.connection import DatabaseConnection


class TeamsRepository:
    """Handles all team-related database operations."""
    
    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn
    
    def get_team_by_id(self, team_id: str) -> Optional[Dict]:
        """Get a single team by ID."""
        query = "SELECT * FROM teams WHERE team_id = ?"
        return self.db.fetch_one(query, (team_id,))
    
    def get_team_by_name(self, team_name: str) -> Optional[Dict]:
        """Get team by canonical name."""
        query = "SELECT * FROM teams WHERE canonical_name = ?"
        return self.db.fetch_one(query, (team_name,))
    
    def search_teams(self, search_term: str) -> List[Dict]:
        """Search teams by name."""
        query = """
            SELECT * FROM teams 
            WHERE canonical_name LIKE ? 
               OR display_name LIKE ?
               OR short_name LIKE ?
            ORDER BY canonical_name
        """
        pattern = f"%{search_term}%"
        return self.db.fetch_all(query, (pattern, pattern, pattern))
    
    def get_all_teams(self, active_only: bool = True) -> List[Dict]:
        """Get all teams."""
        if active_only:
            query = "SELECT * FROM teams WHERE is_active = TRUE ORDER BY canonical_name"
        else:
            query = "SELECT * FROM teams ORDER BY canonical_name"
        
        return self.db.fetch_all(query)
    
    def get_teams_by_conference(self, conference: str) -> List[Dict]:
        """Get all teams in a conference."""
        query = """
            SELECT * FROM teams 
            WHERE conference = ? AND is_active = TRUE
            ORDER BY canonical_name
        """
        return self.db.fetch_all(query, (conference,))
    
    def get_all_conferences(self) -> List[str]:
        """Get list of all conferences."""
        query = """
            SELECT DISTINCT conference 
            FROM teams 
            WHERE conference IS NOT NULL AND is_active = TRUE
            ORDER BY conference
        """
        results = self.db.fetch_all(query)
        return [r['conference'] for r in results]
    
    def insert_team(self, team_data: Dict) -> bool:
        """Insert a new team."""
        query = """
            INSERT OR IGNORE INTO teams 
            (team_id, canonical_name, display_name, short_name, conference, 
             division, espn_team_id, mascot, colors, logo_url, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, (
                    team_data['team_id'],
                    team_data['canonical_name'],
                    team_data.get('display_name', team_data['canonical_name']),
                    team_data.get('short_name'),
                    team_data.get('conference'),
                    team_data.get('division', 'D1'),
                    team_data.get('espn_team_id'),
                    team_data.get('mascot'),
                    team_data.get('colors'),
                    team_data.get('logo_url'),
                    team_data.get('is_active', True)
                ))
            return True
        except Exception as e:
            print(f"Error inserting team: {e}")
            return False
    
    def update_team(self, team_id: str, team_data: Dict) -> bool:
        """Update team information."""
        # Build dynamic update query
        fields = []
        values = []
        
        for key, value in team_data.items():
            if key != 'team_id':
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(team_id)
        query = f"""
            UPDATE teams 
            SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE team_id = ?
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating team: {e}")
            return False
    
    def upsert_team(self, team_data: Dict) -> bool:
        """Insert or update team (upsert)."""
        existing = self.get_team_by_id(team_data['team_id'])
        
        if existing:
            return self.update_team(team_data['team_id'], team_data)
        else:
            return self.insert_team(team_data)
    
    def get_team_record(self, team_id: str, season: Optional[str] = None) -> Optional[Dict]:
        """Get team's win-loss record."""
        if season:
            query = """
                SELECT 
                    COUNT(*) as games_played,
                    SUM(CASE 
                        WHEN (home_team_id = ? AND home_score > away_score) OR
                             (away_team_id = ? AND away_score > home_score)
                        THEN 1 ELSE 0
                    END) as wins,
                    SUM(CASE 
                        WHEN (home_team_id = ? AND home_score < away_score) OR
                             (away_team_id = ? AND away_score < home_score)
                        THEN 1 ELSE 0
                    END) as losses
                FROM games
                WHERE (home_team_id = ? OR away_team_id = ?)
                  AND season = ?
                  AND game_status = 'Final'
            """
            return self.db.fetch_one(query, (team_id, team_id, team_id, team_id, team_id, team_id, season))
        else:
            query = """
                SELECT 
                    COUNT(*) as games_played,
                    SUM(CASE 
                        WHEN (home_team_id = ? AND home_score > away_score) OR
                             (away_team_id = ? AND away_score > home_score)
                        THEN 1 ELSE 0
                    END) as wins,
                    SUM(CASE 
                        WHEN (home_team_id = ? AND home_score < away_score) OR
                             (away_team_id = ? AND away_score < home_score)
                        THEN 1 ELSE 0
                    END) as losses
                FROM games
                WHERE (home_team_id = ? OR away_team_id = ?)
                  AND game_status = 'Final'
            """
            return self.db.fetch_one(query, (team_id, team_id, team_id, team_id, team_id, team_id))
    
    def get_team_stats(self, team_id: str, season: str) -> Optional[Dict]:
        """Get comprehensive team statistics."""
        query = """
            SELECT 
                t.display_name,
                t.conference,
                COUNT(*) as games_played,
                SUM(CASE 
                    WHEN (g.home_team_id = ? AND g.home_score > g.away_score) OR
                         (g.away_team_id = ? AND g.away_score > g.home_score)
                    THEN 1 ELSE 0
                END) as wins,
                AVG(CASE 
                    WHEN g.home_team_id = ? THEN g.home_score 
                    ELSE g.away_score 
                END) as avg_points_scored,
                AVG(CASE 
                    WHEN g.home_team_id = ? THEN g.away_score 
                    ELSE g.home_score 
                END) as avg_points_allowed,
                SUM(CASE 
                    WHEN g.home_team_id = ? AND g.neutral_site = FALSE THEN 1 
                    ELSE 0 
                END) as home_games,
                SUM(CASE 
                    WHEN g.away_team_id = ? AND g.neutral_site = FALSE THEN 1 
                    ELSE 0 
                END) as away_games
            FROM teams t
            LEFT JOIN games g ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
                AND g.season = ? AND g.game_status = 'Final'
            WHERE t.team_id = ?
            GROUP BY t.team_id, t.display_name, t.conference
        """
        return self.db.fetch_one(query, (team_id, team_id, team_id, team_id, team_id, team_id, season, team_id))
    
    def bulk_upsert_teams(self, teams: List[Dict]) -> int:
        """Bulk insert or update teams."""
        updated = 0
        for team in teams:
            if self.upsert_team(team):
                updated += 1
        return updated
    
    def deactivate_team(self, team_id: str) -> bool:
        """Mark a team as inactive."""
        return self.update_team(team_id, {'is_active': False})
