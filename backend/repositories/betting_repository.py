"""Repository for betting data access."""

from typing import List, Optional, Dict
from datetime import date, datetime
import pandas as pd
from backend.database.connection import DatabaseConnection


class BettingRepository:
    """Handles all betting-related database operations."""
    
    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn
    
    def get_bet_by_id(self, bet_id: int) -> Optional[Dict]:
        """Get a single bet by ID."""
        query = "SELECT * FROM bets WHERE id = ?"
        return self.db.fetch_one(query, (bet_id,))
    
    def get_bets_by_game(self, game_id: str) -> List[Dict]:
        """Get all bets for a specific game."""
        query = """
            SELECT * FROM bets 
            WHERE game_id = ?
            ORDER BY created_at DESC
        """
        return self.db.fetch_all(query, (game_id,))
    
    def get_active_bets(self) -> List[Dict]:
        """Get all unsettled bets."""
        query = """
            SELECT 
                b.*,
                g.date as game_date,
                g.home_team,
                g.away_team,
                g.game_status
            FROM bets b
            INNER JOIN games g ON b.game_id = g.game_id
            WHERE b.settled_at IS NULL
            ORDER BY g.date, b.value_score DESC
        """
        return self.db.fetch_all(query)
    
    def get_settled_bets(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict]:
        """Get settled bets with optional date range."""
        query = """
            SELECT 
                b.*,
                g.date as game_date,
                g.home_team,
                g.away_team
            FROM bets b
            INNER JOIN games g ON b.game_id = g.game_id
            WHERE b.settled_at IS NOT NULL
        """
        params = []
        
        if start_date:
            query += " AND g.date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND g.date <= ?"
            params.append(end_date)
        
        query += " ORDER BY b.settled_at DESC"
        
        if params:
            return self.db.fetch_all(query, tuple(params))
        return self.db.fetch_all(query)
    
    def insert_bet(self, bet_data: Dict) -> Optional[int]:
        """Insert a new bet and return its ID."""
        query = """
            INSERT INTO bets 
            (game_id, prediction_id, bet_team, bet_amount, moneyline, 
             confidence, value_score, bet_type, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self.db.transaction() as conn:
                result = conn.execute(query, (
                    bet_data['game_id'],
                    bet_data.get('prediction_id'),
                    bet_data['bet_team'],
                    bet_data.get('bet_amount', 1.0),
                    bet_data['moneyline'],
                    bet_data.get('confidence', 0.5),
                    bet_data.get('value_score'),
                    bet_data.get('bet_type', 'moneyline'),
                    bet_data.get('strategy')
                ))
                
                # Get the inserted ID
                if self.db.use_duckdb:
                    id_result = conn.execute("SELECT lastval() as id").fetchone()
                    return id_result[0] if id_result else None
                else:
                    return result.lastrowid
        except Exception as e:
            print(f"Error inserting bet: {e}")
            return None
    
    def settle_bet(
        self, 
        bet_id: int, 
        bet_won: bool, 
        actual_winner: str,
        payout: float = 0.0
    ) -> bool:
        """Mark a bet as settled with the result."""
        # Calculate profit
        bet = self.get_bet_by_id(bet_id)
        if not bet:
            return False
        
        profit = payout - bet['bet_amount']
        
        query = """
            UPDATE bets 
            SET bet_won = ?, 
                actual_winner = ?, 
                payout = ?,
                profit = ?,
                settled_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        
        try:
            with self.db.transaction() as conn:
                conn.execute(query, (bet_won, actual_winner, payout, profit, bet_id))
            return True
        except Exception as e:
            print(f"Error settling bet: {e}")
            return False
    
    def settle_bets_for_game(self, game_id: str, actual_winner: str) -> int:
        """Settle all bets for a completed game."""
        bets = self.get_bets_by_game(game_id)
        settled_count = 0
        
        for bet in bets:
            if bet['settled_at'] is not None:
                continue  # Already settled
            
            bet_won = (bet['bet_team'] == actual_winner)
            
            # Calculate payout using American odds
            if bet_won:
                if bet['moneyline'] > 0:
                    payout = bet['bet_amount'] * (1 + bet['moneyline'] / 100)
                else:
                    payout = bet['bet_amount'] * (1 + 100 / abs(bet['moneyline']))
            else:
                payout = 0.0
            
            if self.settle_bet(bet['id'], bet_won, actual_winner, payout):
                settled_count += 1
        
        return settled_count
    
    def bulk_insert_bets(self, bets: List[Dict]) -> int:
        """Bulk insert multiple bets."""
        inserted = 0
        for bet in bets:
            if self.insert_bet(bet):
                inserted += 1
        return inserted
    
    def get_betting_summary(self) -> Dict:
        """Get overall betting performance summary."""
        query = """
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN NOT bet_won THEN 1 ELSE 0 END) as losses,
                AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END) as win_rate,
                SUM(bet_amount) as total_wagered,
                SUM(payout) as total_payout,
                SUM(profit) as total_profit,
                SUM(profit) / NULLIF(SUM(bet_amount), 0) as roi,
                AVG(confidence) as avg_confidence,
                MAX(profit) as biggest_win,
                MIN(profit) as biggest_loss
            FROM bets
            WHERE settled_at IS NOT NULL
        """
        return self.db.fetch_one(query)
    
    def get_betting_summary_by_strategy(self) -> List[Dict]:
        """Get betting performance grouped by strategy."""
        query = """
            SELECT 
                strategy,
                COUNT(*) as total_bets,
                SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END) as win_rate,
                SUM(profit) as total_profit,
                SUM(profit) / NULLIF(SUM(bet_amount), 0) as roi
            FROM bets
            WHERE settled_at IS NOT NULL AND strategy IS NOT NULL
            GROUP BY strategy
            ORDER BY roi DESC
        """
        return self.db.fetch_all(query)
    
    def get_betting_summary_by_confidence(self) -> List[Dict]:
        """Get betting performance by confidence buckets."""
        query = """
            SELECT 
                CASE 
                    WHEN confidence >= 0.70 THEN 'High (≥70%)'
                    WHEN confidence >= 0.60 THEN 'Medium (60-70%)'
                    ELSE 'Low (<60%)'
                END as confidence_bucket,
                COUNT(*) as total_bets,
                SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END) as win_rate,
                SUM(profit) as total_profit,
                SUM(profit) / NULLIF(SUM(bet_amount), 0) as roi
            FROM bets
            WHERE settled_at IS NOT NULL
            GROUP BY confidence_bucket
            ORDER BY 
                CASE confidence_bucket
                    WHEN 'High (≥70%)' THEN 1
                    WHEN 'Medium (60-70%)' THEN 2
                    ELSE 3
                END
        """
        return self.db.fetch_all(query)
    
    def get_value_bets(
        self, 
        min_value_score: float = 0.1,
        min_confidence: float = 0.55
    ) -> List[Dict]:
        """Get bets with positive value score."""
        query = """
            SELECT 
                b.*,
                g.date as game_date,
                g.home_team,
                g.away_team,
                g.home_moneyline,
                g.away_moneyline
            FROM bets b
            INNER JOIN games g ON b.game_id = g.game_id
            WHERE b.value_score >= ?
              AND b.confidence >= ?
              AND b.settled_at IS NULL
              AND g.game_status = 'Scheduled'
            ORDER BY b.value_score DESC, b.confidence DESC
        """
        return self.db.fetch_all(query, (min_value_score, min_confidence))
    
    def get_betting_history_df(self) -> pd.DataFrame:
        """Get complete betting history as DataFrame."""
        query = """
            SELECT 
                b.*,
                g.date as game_date,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score
            FROM bets b
            INNER JOIN games g ON b.game_id = g.game_id
            ORDER BY g.date DESC
        """
        return self.db.fetch_df(query)
    
    def get_cumulative_profit(self) -> List[Dict]:
        """Get cumulative profit over time."""
        query = """
            SELECT 
                g.date,
                b.profit,
                SUM(b.profit) OVER (ORDER BY g.date, b.settled_at) as cumulative_profit
            FROM bets b
            INNER JOIN games g ON b.game_id = g.game_id
            WHERE b.settled_at IS NOT NULL
            ORDER BY g.date, b.settled_at
        """
        return self.db.fetch_all(query)
    
    def get_best_teams_to_bet(self, min_bets: int = 5) -> List[Dict]:
        """Get teams with best betting performance."""
        query = """
            SELECT 
                bet_team,
                COUNT(*) as total_bets,
                SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END) as win_rate,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit
            FROM bets
            WHERE settled_at IS NOT NULL
            GROUP BY bet_team
            HAVING COUNT(*) >= ?
            ORDER BY win_rate DESC, total_profit DESC
            LIMIT 20
        """
        return self.db.fetch_all(query, (min_bets,))
    
    def get_worst_teams_to_bet(self, min_bets: int = 5) -> List[Dict]:
        """Get teams with worst betting performance."""
        query = """
            SELECT 
                bet_team,
                COUNT(*) as total_bets,
                SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END) as win_rate,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit
            FROM bets
            WHERE settled_at IS NOT NULL
            GROUP BY bet_team
            HAVING COUNT(*) >= ?
            ORDER BY win_rate ASC, total_profit ASC
            LIMIT 20
        """
        return self.db.fetch_all(query, (min_bets,))
    
    def get_pending_settlements(self) -> List[Dict]:
        """Get bets that need to be settled (games are final but bet not settled)."""
        query = """
            SELECT 
                b.*,
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
                END as actual_winner
            FROM bets b
            INNER JOIN games g ON b.game_id = g.game_id
            WHERE b.settled_at IS NULL
              AND g.game_status = 'Final'
              AND g.home_score IS NOT NULL
              AND g.away_score IS NOT NULL
            ORDER BY g.date DESC
        """
        return self.db.fetch_all(query)
    
    def auto_settle_completed_games(self) -> int:
        """Automatically settle bets for completed games."""
        pending = self.get_pending_settlements()
        settled_count = 0
        
        for bet in pending:
            if bet['actual_winner']:
                if self.settle_bets_for_game(bet['game_id'], bet['actual_winner']):
                    settled_count += 1
        
        return settled_count
