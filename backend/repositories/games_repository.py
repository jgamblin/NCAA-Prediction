"""Repository for game data access."""

from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
import pandas as pd
from backend.database.connection import DatabaseConnection


class GamesRepository:
    """Handles all game-related database operations."""
    
    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn
    
    def get_game_by_id(self, game_id: str) -> Optional[Dict]:
        """Get a single game by ID."""
        query = "SELECT * FROM games WHERE game_id = ?"
        return self.db.fetch_one(query, (game_id,))
    
    def get_games_by_date(self, game_date: date) -> List[Dict]:
        """Get all games for a specific date."""
        query = "SELECT * FROM games WHERE date = ? ORDER BY date"
        return self.db.fetch_all(query, (game_date,))
    
    def get_games_by_date_range(
        self, 
        start_date: date, 
        end_date: date,
        status: Optional[str] = None
    ) -> List[Dict]:
        """Get games within a date range."""
        if status:
            query = """
                SELECT * FROM games 
                WHERE date >= ? AND date <= ? AND game_status = ?
                ORDER BY date
            """
            return self.db.fetch_all(query, (start_date, end_date, status))
        else:
            query = """
                SELECT * FROM games 
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """
            return self.db.fetch_all(query, (start_date, end_date))
    
    def get_completed_games(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all completed games."""
        query = """
            SELECT * FROM games 
            WHERE game_status = 'Final'
            ORDER BY date DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        
        return self.db.fetch_all(query)
    
    def get_completed_games_df(self) -> pd.DataFrame:
        """Get all completed games as DataFrame (replaces CSV read)."""
        query = """
            SELECT * FROM games 
            WHERE game_status = 'Final'
            ORDER BY date
        """
        return self.db.fetch_df(query)
    
    def get_upcoming_games(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming scheduled games."""
        end_date = date.today() + timedelta(days=days_ahead)
        query = """
            SELECT * FROM games 
            WHERE game_status = 'Scheduled' 
              AND date >= CURRENT_DATE 
              AND date <= ?
            ORDER BY date
        """
        return self.db.fetch_all(query, (end_date,))
    
    def get_upcoming_games_df(self) -> pd.DataFrame:
        """Get upcoming games as DataFrame (replaces CSV read)."""
        query = """
            SELECT * FROM games 
            WHERE game_status = 'Scheduled' 
              AND date >= CURRENT_DATE
            ORDER BY date
        """
        return self.db.fetch_df(query)
    
    def get_team_games(
        self, 
        team_id: str, 
        season: Optional[str] = None,
        completed_only: bool = True
    ) -> List[Dict]:
        """Get all games for a specific team."""
        if season:
            if completed_only:
                query = """
                    SELECT * FROM games 
                    WHERE (home_team_id = ? OR away_team_id = ?)
                      AND season = ?
                      AND game_status = 'Final'
                    ORDER BY date
                """
                return self.db.fetch_all(query, (team_id, team_id, season))
            else:
                query = """
                    SELECT * FROM games 
                    WHERE (home_team_id = ? OR away_team_id = ?)
                      AND season = ?
                    ORDER BY date
                """
                return self.db.fetch_all(query, (team_id, team_id, season))
        else:
            if completed_only:
                query = """
                    SELECT * FROM games 
                    WHERE (home_team_id = ? OR away_team_id = ?)
                      AND game_status = 'Final'
                    ORDER BY date DESC
                """
            else:
                query = """
                    SELECT * FROM games 
                    WHERE (home_team_id = ? OR away_team_id = ?)
                    ORDER BY date DESC
                """
            return self.db.fetch_all(query, (team_id, team_id))
    
    def insert_game(self, game_data: Dict) -> bool:
        """Insert a new game."""
        query = """
            INSERT INTO games 
            (game_id, date, season, home_team, away_team, home_team_id, away_team_id,
             home_score, away_score, game_status, neutral_site, home_moneyline, away_moneyline,
             venue, tournament, conference_game)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, (
                    game_data['game_id'],
                    game_data['date'],
                    game_data.get('season'),
                    game_data['home_team'],
                    game_data['away_team'],
                    game_data['home_team_id'],
                    game_data['away_team_id'],
                    game_data.get('home_score'),
                    game_data.get('away_score'),
                    game_data.get('game_status', 'Scheduled'),
                    game_data.get('neutral_site', False),
                    game_data.get('home_moneyline'),
                    game_data.get('away_moneyline'),
                    game_data.get('venue'),
                    game_data.get('tournament'),
                    game_data.get('conference_game', False)
                ))
            return True
        except Exception as e:
            print(f"Error inserting game: {e}")
            return False
    
    def update_game_score(
        self, 
        game_id: str, 
        home_score: int, 
        away_score: int,
        status: str = 'Final'
    ) -> bool:
        """Update game score and status."""
        query = """
            UPDATE games 
            SET home_score = ?, away_score = ?, game_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE game_id = ?
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, (home_score, away_score, status, game_id))
            return True
        except Exception as e:
            print(f"Error updating game score: {e}")
            return False
    
    def update_game_moneylines(
        self, 
        game_id: str, 
        home_moneyline: int, 
        away_moneyline: int
    ) -> bool:
        """Update game moneylines."""
        query = """
            UPDATE games 
            SET home_moneyline = ?, away_moneyline = ?, updated_at = CURRENT_TIMESTAMP
            WHERE game_id = ?
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, (home_moneyline, away_moneyline, game_id))
            return True
        except Exception as e:
            print(f"Error updating moneylines: {e}")
            return False
    
    def bulk_insert_games(self, games: List[Dict]) -> int:
        """Bulk insert multiple games."""
        query = """
            INSERT OR REPLACE INTO games 
            (game_id, date, season, home_team, away_team, home_team_id, away_team_id,
             home_score, away_score, game_status, neutral_site, home_moneyline, away_moneyline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        if self.db.use_duckdb:
            query = query.replace('INSERT OR REPLACE', 'INSERT OR IGNORE')
        
        inserted = 0
        try:
            with self.db.transaction() as conn:
                for game in games:
                    try:
                        conn.execute(query, (
                            game['game_id'],
                            game['date'],
                            game.get('season', ''),
                            game['home_team'],
                            game['away_team'],
                            game['home_team_id'],
                            game['away_team_id'],
                            game.get('home_score'),
                            game.get('away_score'),
                            game.get('game_status', 'Scheduled'),
                            game.get('neutral_site', False),
                            game.get('home_moneyline'),
                            game.get('away_moneyline')
                        ))
                        inserted += 1
                    except Exception as e:
                        print(f"Error inserting game {game.get('game_id')}: {e}")
        except Exception as e:
            print(f"Bulk insert failed: {e}")
        
        return inserted
    
    def get_games_needing_scores(self) -> List[Dict]:
        """Get scheduled games that may need score updates."""
        query = """
            SELECT * FROM games 
            WHERE game_status = 'Scheduled' 
              AND date < CURRENT_DATE
            ORDER BY date DESC
        """
        return self.db.fetch_all(query)
    
    def get_game_count_by_status(self) -> Dict[str, int]:
        """Get count of games by status."""
        query = """
            SELECT game_status, COUNT(*) as count 
            FROM games 
            GROUP BY game_status
        """
        results = self.db.fetch_all(query)
        return {r['game_status']: r['count'] for r in results}
    
    def get_season_summary(self, season: str) -> Dict:
        """Get summary statistics for a season."""
        query = """
            SELECT 
                COUNT(*) as total_games,
                COUNT(DISTINCT home_team_id) + COUNT(DISTINCT away_team_id) as total_teams,
                AVG(home_score + away_score) as avg_total_points,
                AVG(ABS(home_score - away_score)) as avg_margin
            FROM games
            WHERE season = ? AND game_status = 'Final'
        """
        return self.db.fetch_one(query, (season,))
