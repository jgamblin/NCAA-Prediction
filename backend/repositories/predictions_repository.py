"""Repository for prediction data access."""

from typing import List, Optional, Dict
from datetime import date, datetime
import pandas as pd
from backend.database.connection import DatabaseConnection


class PredictionsRepository:
    """Handles all prediction-related database operations."""
    
    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn
    
    def get_prediction_by_id(self, prediction_id: int) -> Optional[Dict]:
        """Get a single prediction by ID."""
        query = "SELECT * FROM predictions WHERE id = ?"
        return self.db.fetch_one(query, (prediction_id,))
    
    def get_predictions_by_game(self, game_id: str) -> List[Dict]:
        """Get all predictions for a specific game."""
        query = """
            SELECT * FROM predictions 
            WHERE game_id = ? 
            ORDER BY prediction_date DESC
        """
        return self.db.fetch_all(query, (game_id,))
    
    def get_latest_prediction(self, game_id: str) -> Optional[Dict]:
        """Get the most recent prediction for a game."""
        query = """
            SELECT * FROM predictions 
            WHERE game_id = ? 
            ORDER BY prediction_date DESC 
            LIMIT 1
        """
        return self.db.fetch_one(query, (game_id,))
    
    def get_predictions_by_date(self, pred_date: date) -> List[Dict]:
        """Get all predictions made on a specific date."""
        query = """
            SELECT * FROM predictions 
            WHERE DATE(prediction_date) = ?
            ORDER BY confidence DESC
        """
        return self.db.fetch_all(query, (pred_date,))
    
    def get_predictions_df(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_confidence: Optional[float] = None
    ) -> pd.DataFrame:
        """Get predictions as DataFrame with optional filters."""
        query = "SELECT * FROM predictions WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND DATE(prediction_date) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(prediction_date) <= ?"
            params.append(end_date)
        
        if min_confidence:
            query += " AND confidence >= ?"
            params.append(min_confidence)
        
        query += " ORDER BY prediction_date DESC"
        
        if params:
            return self.db.fetch_df(query, tuple(params))
        return self.db.fetch_df(query)
    
    def get_upcoming_predictions(self) -> pd.DataFrame:
        """Get predictions for upcoming games (replaces CSV read)."""
        query = """
            SELECT 
                p.*,
                g.date as game_date,
                g.home_team,
                g.away_team,
                g.home_moneyline,
                g.away_moneyline
            FROM predictions p
            INNER JOIN games g ON p.game_id = g.game_id
            WHERE g.game_status = 'Scheduled'
              AND g.date >= CURRENT_DATE
            ORDER BY p.confidence DESC, g.date
        """
        return self.db.fetch_df(query)
    
    def get_prediction_log_df(self) -> pd.DataFrame:
        """Get complete prediction log as DataFrame (replaces prediction_log.csv)."""
        query = """
            SELECT 
                p.*,
                g.date as game_date,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                g.game_status
            FROM predictions p
            INNER JOIN games g ON p.game_id = g.game_id
            ORDER BY p.prediction_date DESC
        """
        return self.db.fetch_df(query)
    
    def insert_prediction(self, prediction_data: Dict) -> Optional[int]:
        """Insert a new prediction and return its ID."""
        query = """
            INSERT INTO predictions 
            (game_id, prediction_date, home_win_prob, away_win_prob,
             predicted_winner, predicted_home_win, confidence,
             model_name, model_version, config_version, commit_hash, source, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.db.transaction() as conn:
                result = conn.execute(query, (
                    prediction_data['game_id'],
                    prediction_data.get('prediction_date', datetime.now()),
                    prediction_data['home_win_prob'],
                    prediction_data['away_win_prob'],
                    prediction_data['predicted_winner'],
                    prediction_data['predicted_home_win'],
                    prediction_data['confidence'],
                    prediction_data.get('model_name', 'Unknown'),
                    prediction_data.get('model_version'),
                    prediction_data.get('config_version'),
                    prediction_data.get('commit_hash'),
                    prediction_data.get('source', 'live'),
                    prediction_data.get('explanation')
                ))
                
                # Get the inserted ID
                if self.db.use_duckdb:
                    id_result = conn.execute("SELECT lastval() as id").fetchone()
                    return id_result[0] if id_result else None
                else:
                    return result.lastrowid
        except Exception as e:
            print(f"Error inserting prediction: {e}")
            return None
    
    def bulk_insert_predictions(self, predictions: List[Dict]) -> int:
        """Bulk insert multiple predictions."""
        query = """
            INSERT INTO predictions 
            (game_id, prediction_date, home_win_prob, away_win_prob,
             predicted_winner, predicted_home_win, confidence,
             model_name, model_version, config_version, commit_hash, source, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        inserted = 0
        try:
            with self.db.transaction() as conn:
                for pred in predictions:
                    try:
                        conn.execute(query, (
                            pred['game_id'],
                            pred.get('prediction_date', datetime.now()),
                            pred['home_win_prob'],
                            pred['away_win_prob'],
                            pred['predicted_winner'],
                            pred['predicted_home_win'],
                            pred['confidence'],
                            pred.get('model_name', 'Unknown'),
                            pred.get('model_version'),
                            pred.get('config_version'),
                            pred.get('commit_hash'),
                            pred.get('source', 'live'),
                            pred.get('explanation')
                        ))
                        inserted += 1
                    except Exception as e:
                        print(f"Error inserting prediction for {pred.get('game_id')}: {e}")
        except Exception as e:
            print(f"Bulk insert failed: {e}")
        
        return inserted
    
    def upsert_prediction(self, prediction_data: Dict) -> Optional[int]:
        """
        Insert or update a prediction. Only keeps one prediction per game.
        Replaces existing prediction if one exists for this game_id.
        """
        # First, try to find existing prediction
        existing = self.get_latest_prediction(prediction_data['game_id'])
        
        if existing:
            # Update existing prediction
            query = """
                UPDATE predictions
                SET prediction_date = ?,
                    home_win_prob = ?,
                    away_win_prob = ?,
                    predicted_winner = ?,
                    predicted_home_win = ?,
                    confidence = ?,
                    model_name = ?,
                    model_version = ?,
                    config_version = ?,
                    commit_hash = ?,
                    source = ?,
                    explanation = ?
                WHERE id = ?
            """
            
            try:
                with self.db.transaction() as conn:
                    conn.execute(query, (
                        prediction_data.get('prediction_date', datetime.now()),
                        prediction_data['home_win_prob'],
                        prediction_data['away_win_prob'],
                        prediction_data['predicted_winner'],
                        prediction_data['predicted_home_win'],
                        prediction_data['confidence'],
                        prediction_data.get('model_name', 'Unknown'),
                        prediction_data.get('model_version'),
                        prediction_data.get('config_version'),
                        prediction_data.get('commit_hash'),
                        prediction_data.get('source', 'live'),
                        prediction_data.get('explanation'),
                        existing['id']
                    ))
                return existing['id']
            except Exception as e:
                print(f"Error updating prediction: {e}")
                return None
        else:
            # Insert new prediction
            return self.insert_prediction(prediction_data)
    
    def bulk_upsert_predictions(self, predictions: List[Dict]) -> int:
        """
        Bulk upsert predictions - replaces existing predictions instead of creating duplicates.
        This is the recommended method for the daily pipeline.
        """
        upserted = 0
        
        for pred in predictions:
            result = self.upsert_prediction(pred)
            if result is not None:
                upserted += 1
        
        return upserted
    
    def get_predictions_with_results(self) -> pd.DataFrame:
        """Get predictions joined with actual game results."""
        query = """
            SELECT 
                p.*,
                g.date as game_date,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                g.game_status,
                CASE 
                    WHEN g.home_score > g.away_score THEN g.home_team
                    WHEN g.away_score > g.home_score THEN g.away_team
                    ELSE NULL
                END as actual_winner,
                CASE 
                    WHEN g.game_status = 'Final' THEN
                        CASE 
                            WHEN p.predicted_winner = 
                                (CASE 
                                    WHEN g.home_score > g.away_score THEN g.home_team
                                    WHEN g.away_score > g.home_score THEN g.away_team
                                    ELSE NULL
                                END)
                            THEN 1 ELSE 0
                        END
                    ELSE NULL
                END as correct_prediction
            FROM predictions p
            INNER JOIN games g ON p.game_id = g.game_id
            WHERE g.game_status = 'Final'
            ORDER BY g.date DESC
        """
        return self.db.fetch_df(query)
    
    def calculate_accuracy(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_confidence: Optional[float] = None
    ) -> Dict:
        """Calculate prediction accuracy metrics."""
        query = """
            SELECT 
                COUNT(*) as total_predictions,
                SUM(CASE 
                    WHEN p.predicted_winner = 
                        (CASE 
                            WHEN g.home_score > g.away_score THEN g.home_team
                            WHEN g.away_score > g.home_score THEN g.away_team
                            ELSE NULL
                        END)
                    THEN 1 ELSE 0
                END) as correct_predictions,
                AVG(p.confidence) as avg_confidence
            FROM predictions p
            INNER JOIN games g ON p.game_id = g.game_id
            WHERE g.game_status = 'Final'
        """
        params = []
        
        if start_date:
            query += " AND g.date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND g.date <= ?"
            params.append(end_date)
        
        if min_confidence:
            query += " AND p.confidence >= ?"
            params.append(min_confidence)
        
        result = self.db.fetch_one(query, tuple(params) if params else None)
        
        if result and result['total_predictions'] > 0:
            result['accuracy'] = result['correct_predictions'] / result['total_predictions']
        else:
            result = {'total_predictions': 0, 'correct_predictions': 0, 'accuracy': 0.0, 'avg_confidence': 0.0}
        
        return result
    
    def get_high_confidence_predictions(
        self, 
        min_confidence: float = 0.65,
        upcoming_only: bool = True
    ) -> List[Dict]:
        """Get high confidence predictions."""
        if upcoming_only:
            query = """
                SELECT 
                    p.*,
                    g.date as game_date,
                    g.home_team,
                    g.away_team,
                    g.home_moneyline,
                    g.away_moneyline
                FROM predictions p
                INNER JOIN games g ON p.game_id = g.game_id
                WHERE p.confidence >= ?
                  AND g.game_status = 'Scheduled'
                  AND g.date >= CURRENT_DATE
                ORDER BY p.confidence DESC
            """
        else:
            query = """
                SELECT 
                    p.*,
                    g.date as game_date,
                    g.home_team,
                    g.away_team
                FROM predictions p
                INNER JOIN games g ON p.game_id = g.game_id
                WHERE p.confidence >= ?
                ORDER BY p.confidence DESC
            """
        
        return self.db.fetch_all(query, (min_confidence,))
    
    def get_predictions_by_model(
        self, 
        model_name: str,
        model_version: Optional[str] = None
    ) -> pd.DataFrame:
        """Get predictions by model name and version."""
        if model_version:
            query = """
                SELECT * FROM predictions 
                WHERE model_name = ? AND model_version = ?
                ORDER BY prediction_date DESC
            """
            return self.db.fetch_df(query, (model_name, model_version))
        else:
            query = """
                SELECT * FROM predictions 
                WHERE model_name = ?
                ORDER BY prediction_date DESC
            """
            return self.db.fetch_df(query, (model_name,))
    
    def delete_old_predictions(self, days_old: int = 365) -> int:
        """Delete predictions older than specified days."""
        query = """
            DELETE FROM predictions 
            WHERE prediction_date < DATE('now', '-' || ? || ' days')
        """
        
        try:
            with self.db.transaction() as conn:
                result = conn.execute(query, (days_old,))
                return result.rowcount if hasattr(result, 'rowcount') else 0
        except Exception as e:
            print(f"Error deleting old predictions: {e}")
            return 0
