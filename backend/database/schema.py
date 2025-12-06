"""Database schema initialization and management.

Creates all tables, indexes, views, and triggers for the NCAA prediction system.
"""
import logging
from pathlib import Path
from typing import Optional
from .connection import DatabaseConnection

logger = logging.getLogger(__name__)


def initialize_database(db_conn: DatabaseConnection, drop_existing: bool = False):
    """
    Initialize database schema with all tables, indexes, and views.
    
    Args:
        db_conn: Database connection instance
        drop_existing: If True, drop existing tables before creating
    """
    logger.info("Initializing database schema...")
    
    if drop_existing:
        logger.warning("Dropping existing tables...")
        drop_all_tables(db_conn)
    
    # Create tables in order (respecting foreign key dependencies)
    create_teams_table(db_conn)
    create_games_table(db_conn)
    create_predictions_table(db_conn)
    create_team_features_table(db_conn)
    create_bets_table(db_conn)
    create_parlays_table(db_conn)
    create_parlay_legs_table(db_conn)
    create_accuracy_metrics_table(db_conn)
    create_drift_metrics_table(db_conn)
    create_feature_importance_table(db_conn)
    
    # Create views
    create_views(db_conn)
    
    logger.info("Database schema initialized successfully")


def drop_all_tables(db_conn: DatabaseConnection):
    """Drop all tables (use with caution!)."""
    tables = [
        'feature_importance',
        'drift_metrics',
        'accuracy_metrics',
        'bets',
        'team_features',
        'predictions',
        'games',
        'teams'
    ]
    
    for table in tables:
        try:
            db_conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            logger.info(f"Dropped table: {table}")
        except Exception as e:
            logger.warning(f"Failed to drop table {table}: {e}")


def create_teams_table(db_conn: DatabaseConnection):
    """Create teams table."""
    query = """
    CREATE TABLE IF NOT EXISTS teams (
        team_id VARCHAR PRIMARY KEY,
        canonical_name VARCHAR NOT NULL UNIQUE,
        display_name VARCHAR NOT NULL,
        short_name VARCHAR,
        conference VARCHAR,
        division VARCHAR DEFAULT 'D1',
        espn_team_id VARCHAR,
        mascot VARCHAR,
        colors VARCHAR,
        logo_url VARCHAR,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_teams_conference ON teams(conference)",
        "CREATE INDEX IF NOT EXISTS idx_teams_division ON teams(division)",
        "CREATE INDEX IF NOT EXISTS idx_teams_espn_id ON teams(espn_team_id)",
        "CREATE INDEX IF NOT EXISTS idx_teams_active ON teams(is_active)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created teams table")


def create_games_table(db_conn: DatabaseConnection):
    """Create games table."""
    query = """
    CREATE TABLE IF NOT EXISTS games (
        game_id VARCHAR PRIMARY KEY,
        date DATE NOT NULL,
        season VARCHAR NOT NULL,
        home_team VARCHAR NOT NULL,
        away_team VARCHAR NOT NULL,
        home_team_id VARCHAR NOT NULL,
        away_team_id VARCHAR NOT NULL,
        home_score INTEGER,
        away_score INTEGER,
        game_status VARCHAR NOT NULL,
        neutral_site BOOLEAN DEFAULT FALSE,
        home_moneyline INTEGER,
        away_moneyline INTEGER,
        venue VARCHAR,
        tournament VARCHAR,
        conference_game BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_games_date ON games(date)",
        "CREATE INDEX IF NOT EXISTS idx_games_season ON games(season)",
        "CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id)",
        "CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id)",
        "CREATE INDEX IF NOT EXISTS idx_games_status ON games(game_status)",
        "CREATE INDEX IF NOT EXISTS idx_games_date_status ON games(date, game_status)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created games table")


def create_predictions_table(db_conn: DatabaseConnection):
    """Create predictions table."""
    if db_conn.use_duckdb:
        # DuckDB version uses BIGINT with sequence
        query = """
        CREATE SEQUENCE IF NOT EXISTS predictions_seq START 1;
        CREATE TABLE IF NOT EXISTS predictions (
            id BIGINT PRIMARY KEY DEFAULT nextval('predictions_seq'),
            game_id VARCHAR NOT NULL,
            prediction_date TIMESTAMP NOT NULL,
            home_win_prob FLOAT NOT NULL,
            away_win_prob FLOAT NOT NULL,
            predicted_winner VARCHAR NOT NULL,
            predicted_home_win INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            model_name VARCHAR NOT NULL,
            model_version VARCHAR,
            config_version VARCHAR,
            commit_hash VARCHAR,
            source VARCHAR DEFAULT 'live',
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        # SQLite version with AUTOINCREMENT
        query = """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id VARCHAR NOT NULL,
            prediction_date TIMESTAMP NOT NULL,
            home_win_prob FLOAT NOT NULL,
            away_win_prob FLOAT NOT NULL,
            predicted_winner VARCHAR NOT NULL,
            predicted_home_win INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            model_name VARCHAR NOT NULL,
            model_version VARCHAR,
            config_version VARCHAR,
            commit_hash VARCHAR,
            source VARCHAR DEFAULT 'live',
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id)",
        "CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date)",
        "CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON predictions(confidence)",
        "CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_name, model_version)",
        "CREATE INDEX IF NOT EXISTS idx_predictions_source ON predictions(source)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created predictions table")


def create_team_features_table(db_conn: DatabaseConnection):
    """Create team_features table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS team_features_seq START 1;
        CREATE TABLE IF NOT EXISTS team_features (
            id BIGINT PRIMARY KEY DEFAULT nextval('team_features_seq'),
            team_id VARCHAR NOT NULL,
            season VARCHAR NOT NULL,
            games_played INTEGER NOT NULL DEFAULT 0,
            rolling_win_pct_5 FLOAT,
            rolling_win_pct_10 FLOAT,
            rolling_point_diff_avg_5 FLOAT,
            rolling_point_diff_avg_10 FLOAT,
            win_pct_last5_vs10 FLOAT,
            point_diff_last5_vs10 FLOAT,
            recent_strength_index_5 FLOAT,
            total_wins INTEGER DEFAULT 0,
            total_losses INTEGER DEFAULT 0,
            avg_points_scored FLOAT,
            avg_points_allowed FLOAT,
            home_win_pct FLOAT,
            away_win_pct FLOAT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, season)
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS team_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id VARCHAR NOT NULL,
            season VARCHAR NOT NULL,
            games_played INTEGER NOT NULL DEFAULT 0,
            rolling_win_pct_5 FLOAT,
            rolling_win_pct_10 FLOAT,
            rolling_point_diff_avg_5 FLOAT,
            rolling_point_diff_avg_10 FLOAT,
            win_pct_last5_vs10 FLOAT,
            point_diff_last5_vs10 FLOAT,
            recent_strength_index_5 FLOAT,
            total_wins INTEGER DEFAULT 0,
            total_losses INTEGER DEFAULT 0,
            avg_points_scored FLOAT,
            avg_points_allowed FLOAT,
            home_win_pct FLOAT,
            away_win_pct FLOAT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, season)
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_features_team ON team_features(team_id)",
        "CREATE INDEX IF NOT EXISTS idx_features_season ON team_features(season)",
        "CREATE INDEX IF NOT EXISTS idx_features_team_season ON team_features(team_id, season)",
        "CREATE INDEX IF NOT EXISTS idx_features_updated ON team_features(updated_at)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created team_features table")


def create_bets_table(db_conn: DatabaseConnection):
    """Create bets table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS bets_seq START 1;
        CREATE TABLE IF NOT EXISTS bets (
            id BIGINT PRIMARY KEY DEFAULT nextval('bets_seq'),
            game_id VARCHAR NOT NULL,
            prediction_id BIGINT NOT NULL,
            bet_team VARCHAR NOT NULL,
            bet_amount FLOAT NOT NULL DEFAULT 1.0,
            moneyline INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            value_score FLOAT,
            bet_won BOOLEAN,
            actual_winner VARCHAR,
            payout FLOAT DEFAULT 0.0,
            profit FLOAT,
            bet_type VARCHAR DEFAULT 'moneyline',
            strategy VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id VARCHAR NOT NULL,
            prediction_id INTEGER NOT NULL,
            bet_team VARCHAR NOT NULL,
            bet_amount FLOAT NOT NULL DEFAULT 1.0,
            moneyline INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            value_score FLOAT,
            bet_won BOOLEAN,
            actual_winner VARCHAR,
            payout FLOAT DEFAULT 0.0,
            profit FLOAT,
            bet_type VARCHAR DEFAULT 'moneyline',
            strategy VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_bets_game ON bets(game_id)",
        "CREATE INDEX IF NOT EXISTS idx_bets_prediction ON bets(prediction_id)",
        "CREATE INDEX IF NOT EXISTS idx_bets_settled ON bets(settled_at)",
        "CREATE INDEX IF NOT EXISTS idx_bets_confidence ON bets(confidence)",
        "CREATE INDEX IF NOT EXISTS idx_bets_value ON bets(value_score)",
        "CREATE INDEX IF NOT EXISTS idx_bets_strategy ON bets(strategy)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created bets table")


def create_parlays_table(db_conn: DatabaseConnection):
    """Create parlays table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS parlays_seq START 1;
        CREATE TABLE IF NOT EXISTS parlays (
            id BIGINT PRIMARY KEY DEFAULT nextval('parlays_seq'),
            parlay_date DATE NOT NULL,
            bet_amount FLOAT NOT NULL DEFAULT 10.0,
            num_legs INTEGER NOT NULL,
            combined_odds FLOAT NOT NULL,
            potential_payout FLOAT NOT NULL,
            parlay_won BOOLEAN,
            actual_payout FLOAT DEFAULT 0.0,
            profit FLOAT,
            strategy VARCHAR DEFAULT 'parlay_high_confidence',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS parlays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parlay_date DATE NOT NULL,
            bet_amount FLOAT NOT NULL DEFAULT 10.0,
            num_legs INTEGER NOT NULL,
            combined_odds FLOAT NOT NULL,
            potential_payout FLOAT NOT NULL,
            parlay_won BOOLEAN,
            actual_payout FLOAT DEFAULT 0.0,
            profit FLOAT,
            strategy VARCHAR DEFAULT 'parlay_high_confidence',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_parlays_date ON parlays(parlay_date)",
        "CREATE INDEX IF NOT EXISTS idx_parlays_settled ON parlays(settled_at)",
        "CREATE INDEX IF NOT EXISTS idx_parlays_strategy ON parlays(strategy)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created parlays table")


def create_parlay_legs_table(db_conn: DatabaseConnection):
    """Create parlay_legs table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS parlay_legs_seq START 1;
        CREATE TABLE IF NOT EXISTS parlay_legs (
            id BIGINT PRIMARY KEY DEFAULT nextval('parlay_legs_seq'),
            parlay_id BIGINT NOT NULL,
            game_id VARCHAR NOT NULL,
            prediction_id BIGINT NOT NULL,
            bet_team VARCHAR NOT NULL,
            moneyline INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            leg_won BOOLEAN,
            actual_winner VARCHAR,
            leg_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS parlay_legs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parlay_id BIGINT NOT NULL,
            game_id VARCHAR NOT NULL,
            prediction_id BIGINT NOT NULL,
            bet_team VARCHAR NOT NULL,
            moneyline INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            leg_won BOOLEAN,
            actual_winner VARCHAR,
            leg_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_parlay_legs_parlay ON parlay_legs(parlay_id)",
        "CREATE INDEX IF NOT EXISTS idx_parlay_legs_game ON parlay_legs(game_id)",
        "CREATE INDEX IF NOT EXISTS idx_parlay_legs_prediction ON parlay_legs(prediction_id)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created parlay_legs table")


def create_accuracy_metrics_table(db_conn: DatabaseConnection):
    """Create accuracy_metrics table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS accuracy_metrics_seq START 1;
        CREATE TABLE IF NOT EXISTS accuracy_metrics (
            id BIGINT PRIMARY KEY DEFAULT nextval('accuracy_metrics_seq'),
            date DATE NOT NULL UNIQUE,
            total_predictions INTEGER NOT NULL DEFAULT 0,
            correct_predictions INTEGER NOT NULL DEFAULT 0,
            accuracy FLOAT NOT NULL,
            avg_confidence FLOAT,
            high_conf_predictions INTEGER DEFAULT 0,
            high_conf_correct INTEGER DEFAULT 0,
            high_conf_accuracy FLOAT,
            low_conf_predictions INTEGER DEFAULT 0,
            low_conf_correct INTEGER DEFAULT 0,
            low_conf_accuracy FLOAT,
            log_loss FLOAT,
            brier_score FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS accuracy_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            total_predictions INTEGER NOT NULL DEFAULT 0,
            correct_predictions INTEGER NOT NULL DEFAULT 0,
            accuracy FLOAT NOT NULL,
            avg_confidence FLOAT,
            high_conf_predictions INTEGER DEFAULT 0,
            high_conf_correct INTEGER DEFAULT 0,
            high_conf_accuracy FLOAT,
            low_conf_predictions INTEGER DEFAULT 0,
            low_conf_correct INTEGER DEFAULT 0,
            low_conf_accuracy FLOAT,
            log_loss FLOAT,
            brier_score FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        db_conn.execute(query)
    db_conn.execute("CREATE INDEX IF NOT EXISTS idx_accuracy_date ON accuracy_metrics(date)")
    
    logger.info("Created accuracy_metrics table")


def create_drift_metrics_table(db_conn: DatabaseConnection):
    """Create drift_metrics table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS drift_metrics_seq START 1;
        CREATE TABLE IF NOT EXISTS drift_metrics (
            id BIGINT PRIMARY KEY DEFAULT nextval('drift_metrics_seq'),
            metric_date DATE NOT NULL,
            team_id VARCHAR,
            metric_type VARCHAR NOT NULL,
            rolling_accuracy FLOAT,
            cumulative_accuracy FLOAT,
            accuracy_delta FLOAT,
            games_in_window INTEGER,
            total_games INTEGER,
            is_anomaly BOOLEAN DEFAULT FALSE,
            anomaly_score FLOAT,
            window_size INTEGER DEFAULT 25,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS drift_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            team_id VARCHAR,
            metric_type VARCHAR NOT NULL,
            rolling_accuracy FLOAT,
            cumulative_accuracy FLOAT,
            accuracy_delta FLOAT,
            games_in_window INTEGER,
            total_games INTEGER,
            is_anomaly BOOLEAN DEFAULT FALSE,
            anomaly_score FLOAT,
            window_size INTEGER DEFAULT 25,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_drift_date ON drift_metrics(metric_date)",
        "CREATE INDEX IF NOT EXISTS idx_drift_team ON drift_metrics(team_id)",
        "CREATE INDEX IF NOT EXISTS idx_drift_type ON drift_metrics(metric_type)",
        "CREATE INDEX IF NOT EXISTS idx_drift_anomaly ON drift_metrics(is_anomaly)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created drift_metrics table")


def create_feature_importance_table(db_conn: DatabaseConnection):
    """Create feature_importance table."""
    if db_conn.use_duckdb:
        query = """
        CREATE SEQUENCE IF NOT EXISTS feature_importance_seq START 1;
        CREATE TABLE IF NOT EXISTS feature_importance (
            id BIGINT PRIMARY KEY DEFAULT nextval('feature_importance_seq'),
            model_name VARCHAR NOT NULL,
            model_version VARCHAR,
            feature_name VARCHAR NOT NULL,
            importance_score FLOAT NOT NULL,
            rank INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        for q in query.split(';'):
            if q.strip():
                db_conn.execute(q)
    else:
        query = """
        CREATE TABLE IF NOT EXISTS feature_importance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name VARCHAR NOT NULL,
            model_version VARCHAR,
            feature_name VARCHAR NOT NULL,
            importance_score FLOAT NOT NULL,
            rank INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        db_conn.execute(query)
    
    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_importance_model ON feature_importance(model_name, model_version)",
        "CREATE INDEX IF NOT EXISTS idx_importance_feature ON feature_importance(feature_name)",
        "CREATE INDEX IF NOT EXISTS idx_importance_timestamp ON feature_importance(timestamp)"
    ]
    
    for idx in indexes:
        db_conn.execute(idx)
    
    logger.info("Created feature_importance table")


def create_views(db_conn: DatabaseConnection):
    """Create database views for common queries."""
    
    # View: Today's games with predictions
    view_games_today = """
    CREATE OR REPLACE VIEW vw_games_today AS
    SELECT 
        g.*,
        p.home_win_prob,
        p.confidence,
        p.predicted_winner
    FROM games g
    LEFT JOIN predictions p ON g.game_id = p.game_id
    WHERE g.date = CURRENT_DATE
      AND g.game_status = 'Scheduled'
    ORDER BY g.date
    """
    
    # View: Upcoming predictions
    view_upcoming = """
    CREATE OR REPLACE VIEW vw_upcoming_predictions AS
    SELECT 
        g.game_id,
        g.date,
        g.home_team,
        g.away_team,
        g.home_moneyline,
        g.away_moneyline,
        p.home_win_prob,
        p.away_win_prob,
        p.confidence,
        p.predicted_winner,
        p.model_name
    FROM games g
    INNER JOIN predictions p ON g.game_id = p.game_id
    WHERE g.game_status = 'Scheduled'
      AND g.date >= CURRENT_DATE
    ORDER BY g.date, p.confidence DESC
    """
    
    # View: Active bets
    view_active_bets = """
    CREATE OR REPLACE VIEW vw_active_bets AS
    SELECT 
        b.id,
        b.game_id,
        g.date,
        g.home_team,
        g.away_team,
        b.bet_team,
        b.moneyline,
        b.bet_amount,
        b.confidence,
        b.value_score,
        b.strategy
    FROM bets b
    INNER JOIN games g ON b.game_id = g.game_id
    WHERE b.settled_at IS NULL
      AND g.game_status = 'Scheduled'
    ORDER BY b.value_score DESC, b.confidence DESC
    """
    
    # View: Betting summary
    view_betting_summary = """
    CREATE OR REPLACE VIEW vw_betting_summary AS
    SELECT 
        COUNT(*) as total_bets,
        SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN NOT bet_won THEN 1 ELSE 0 END) as losses,
        ROUND(AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END), 3) as win_rate,
        SUM(bet_amount) as total_wagered,
        SUM(payout) as total_payout,
        SUM(profit) as total_profit,
        ROUND(SUM(profit) / NULLIF(SUM(bet_amount), 0), 3) as roi,
        MAX(settled_at) as last_settlement
    FROM bets
    WHERE settled_at IS NOT NULL
    """
    
    # View: Team stats
    view_team_stats = """
    CREATE OR REPLACE VIEW vw_team_stats AS
    SELECT 
        t.team_id,
        t.canonical_name,
        t.display_name,
        t.conference,
        tf.season,
        tf.games_played,
        tf.total_wins,
        tf.total_losses,
        ROUND(CAST(tf.total_wins AS FLOAT) / NULLIF(tf.games_played, 0), 3) as win_pct,
        tf.avg_points_scored,
        tf.avg_points_allowed,
        tf.rolling_win_pct_10,
        tf.recent_strength_index_5
    FROM teams t
    LEFT JOIN team_features tf ON t.team_id = tf.team_id
    ORDER BY t.canonical_name
    """
    
    views = [
        view_games_today,
        view_upcoming,
        view_active_bets,
        view_betting_summary,
        view_team_stats
    ]
    
    for view in views:
        try:
            db_conn.execute(view)
        except Exception as e:
            logger.warning(f"Failed to create view: {e}")
    
    logger.info("Created database views")


def get_schema_info(db_conn: DatabaseConnection) -> dict:
    """Get information about the database schema."""
    tables = [
        'teams', 'games', 'predictions', 'team_features',
        'bets', 'accuracy_metrics', 'drift_metrics', 'feature_importance'
    ]
    
    info = {}
    for table in tables:
        if db_conn.table_exists(table):
            count = db_conn.get_table_row_count(table)
            info[table] = {'exists': True, 'row_count': count}
        else:
            info[table] = {'exists': False, 'row_count': 0}
    
    return info
