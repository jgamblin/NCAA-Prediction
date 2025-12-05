-- NCAA Basketball Prediction System Database Schema
-- Database: DuckDB (recommended) or SQLite
-- Version: 1.0.0
-- Created: 2024-12-01

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Games Table (replaces Completed_Games.csv)
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
    game_status VARCHAR NOT NULL CHECK (game_status IN ('Final', 'Scheduled', 'In Progress')),
    neutral_site BOOLEAN DEFAULT FALSE,
    home_moneyline INTEGER,
    away_moneyline INTEGER,
    venue VARCHAR,
    tournament VARCHAR,
    conference_game BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for games table
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(game_status);
CREATE INDEX IF NOT EXISTS idx_games_date_status ON games(date, game_status);

-- ============================================================================

-- Teams Table (new - canonical team registry)
CREATE TABLE IF NOT EXISTS teams (
    team_id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR NOT NULL UNIQUE,
    display_name VARCHAR NOT NULL,
    short_name VARCHAR,
    conference VARCHAR,
    division VARCHAR DEFAULT 'D1' CHECK (division IN ('D1', 'D2', 'D3', 'NAIA', 'Other')),
    espn_team_id VARCHAR,
    mascot VARCHAR,
    colors VARCHAR,  -- JSON array of hex colors
    logo_url VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for teams table
CREATE INDEX IF NOT EXISTS idx_teams_conference ON teams(conference);
CREATE INDEX IF NOT EXISTS idx_teams_division ON teams(division);
CREATE INDEX IF NOT EXISTS idx_teams_espn_id ON teams(espn_team_id);
CREATE INDEX IF NOT EXISTS idx_teams_active ON teams(is_active);

-- ============================================================================

-- Predictions Table (replaces NCAA_Game_Predictions.csv + prediction_log.csv)
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    prediction_date TIMESTAMP NOT NULL,
    home_win_prob FLOAT NOT NULL CHECK (home_win_prob BETWEEN 0.0 AND 1.0),
    away_win_prob FLOAT NOT NULL CHECK (away_win_prob BETWEEN 0.0 AND 1.0),
    predicted_winner VARCHAR NOT NULL,
    predicted_home_win INTEGER NOT NULL CHECK (predicted_home_win IN (0, 1)),
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    model_name VARCHAR NOT NULL,
    model_version VARCHAR,
    config_version VARCHAR,
    commit_hash VARCHAR,
    source VARCHAR DEFAULT 'live' CHECK (source IN ('live', 'backtest', 'tuning')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

-- Indexes for predictions table
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON predictions(confidence);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_predictions_source ON predictions(source);

-- Unique constraint to enforce one prediction per game (reduces database bloat)
CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_game_id_unique ON predictions(game_id);

-- ============================================================================

-- Team Features Table (replaces feature_store/feature_store.csv)
CREATE TABLE IF NOT EXISTS team_features (
    id INTEGER PRIMARY KEY,
    team_id VARCHAR NOT NULL,
    season VARCHAR NOT NULL,
    games_played INTEGER NOT NULL DEFAULT 0,
    
    -- Rolling performance metrics
    rolling_win_pct_5 FLOAT,
    rolling_win_pct_10 FLOAT,
    rolling_point_diff_avg_5 FLOAT,
    rolling_point_diff_avg_10 FLOAT,
    
    -- Momentum indicators
    win_pct_last5_vs10 FLOAT,
    point_diff_last5_vs10 FLOAT,
    recent_strength_index_5 FLOAT,
    
    -- Additional aggregates
    total_wins INTEGER DEFAULT 0,
    total_losses INTEGER DEFAULT 0,
    avg_points_scored FLOAT,
    avg_points_allowed FLOAT,
    home_win_pct FLOAT,
    away_win_pct FLOAT,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    UNIQUE(team_id, season)
);

-- Indexes for team_features table
CREATE INDEX IF NOT EXISTS idx_features_team ON team_features(team_id);
CREATE INDEX IF NOT EXISTS idx_features_season ON team_features(season);
CREATE INDEX IF NOT EXISTS idx_features_team_season ON team_features(team_id, season);
CREATE INDEX IF NOT EXISTS idx_features_updated ON team_features(updated_at);

-- ============================================================================

-- Bets Table (new - betting tracking)
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    prediction_id INTEGER NOT NULL,
    bet_team VARCHAR NOT NULL,
    bet_amount FLOAT NOT NULL DEFAULT 1.0,
    moneyline INTEGER NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    value_score FLOAT,  -- Expected value calculation
    
    -- Result tracking
    bet_won BOOLEAN,
    actual_winner VARCHAR,
    payout FLOAT DEFAULT 0.0,
    profit FLOAT,
    
    -- Metadata
    bet_type VARCHAR DEFAULT 'moneyline' CHECK (bet_type IN ('moneyline', 'spread', 'total')),
    strategy VARCHAR,  -- 'value', 'high_confidence', 'streak', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP,
    
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE
);

-- Indexes for bets table
CREATE INDEX IF NOT EXISTS idx_bets_game ON bets(game_id);
CREATE INDEX IF NOT EXISTS idx_bets_prediction ON bets(prediction_id);
CREATE INDEX IF NOT EXISTS idx_bets_settled ON bets(settled_at);
CREATE INDEX IF NOT EXISTS idx_bets_confidence ON bets(confidence);
CREATE INDEX IF NOT EXISTS idx_bets_value ON bets(value_score);
CREATE INDEX IF NOT EXISTS idx_bets_strategy ON bets(strategy);
CREATE INDEX IF NOT EXISTS idx_bets_unsettled ON bets(settled_at) WHERE settled_at IS NULL;

-- ============================================================================
-- ANALYTICS TABLES
-- ============================================================================

-- Accuracy Metrics Table (replaces Accuracy_Report.csv)
CREATE TABLE IF NOT EXISTS accuracy_metrics (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    
    -- Overall metrics
    total_predictions INTEGER NOT NULL DEFAULT 0,
    correct_predictions INTEGER NOT NULL DEFAULT 0,
    accuracy FLOAT NOT NULL CHECK (accuracy BETWEEN 0.0 AND 1.0),
    
    -- Confidence-based metrics
    avg_confidence FLOAT,
    high_conf_predictions INTEGER DEFAULT 0,
    high_conf_correct INTEGER DEFAULT 0,
    high_conf_accuracy FLOAT,
    low_conf_predictions INTEGER DEFAULT 0,
    low_conf_correct INTEGER DEFAULT 0,
    low_conf_accuracy FLOAT,
    
    -- Additional metrics
    log_loss FLOAT,
    brier_score FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for accuracy_metrics table
CREATE INDEX IF NOT EXISTS idx_accuracy_date ON accuracy_metrics(date);

-- ============================================================================

-- Drift Metrics Table (replaces Drift_Metrics.csv + Drift_Metrics_By_Team.csv)
CREATE TABLE IF NOT EXISTS drift_metrics (
    id INTEGER PRIMARY KEY,
    metric_date DATE NOT NULL,
    team_id VARCHAR,  -- NULL for global metrics
    metric_type VARCHAR NOT NULL CHECK (metric_type IN ('global', 'team', 'conference')),
    
    -- Accuracy metrics
    rolling_accuracy FLOAT,
    cumulative_accuracy FLOAT,
    accuracy_delta FLOAT,
    
    -- Volume metrics
    games_in_window INTEGER,
    total_games INTEGER,
    
    -- Drift indicators
    is_anomaly BOOLEAN DEFAULT FALSE,
    anomaly_score FLOAT,
    
    -- Metadata
    window_size INTEGER DEFAULT 25,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
);

-- Indexes for drift_metrics table
CREATE INDEX IF NOT EXISTS idx_drift_date ON drift_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_drift_team ON drift_metrics(team_id);
CREATE INDEX IF NOT EXISTS idx_drift_type ON drift_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_drift_anomaly ON drift_metrics(is_anomaly);

-- ============================================================================

-- Feature Importance Table (replaces Simple_Feature_Importance.csv, etc.)
CREATE TABLE IF NOT EXISTS feature_importance (
    id INTEGER PRIMARY KEY,
    model_name VARCHAR NOT NULL,
    model_version VARCHAR,
    feature_name VARCHAR NOT NULL,
    importance_score FLOAT NOT NULL,
    rank INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for feature_importance table
CREATE INDEX IF NOT EXISTS idx_importance_model ON feature_importance(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_importance_feature ON feature_importance(feature_name);
CREATE INDEX IF NOT EXISTS idx_importance_timestamp ON feature_importance(timestamp);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Today's Games View
CREATE VIEW IF NOT EXISTS vw_games_today AS
SELECT 
    g.*,
    p.home_win_prob,
    p.confidence,
    p.predicted_winner
FROM games g
LEFT JOIN predictions p ON g.game_id = p.game_id
WHERE g.date = CURRENT_DATE
  AND g.game_status = 'Scheduled'
ORDER BY g.date;

-- Upcoming Games with Predictions View
CREATE VIEW IF NOT EXISTS vw_upcoming_predictions AS
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
ORDER BY g.date, p.confidence DESC;

-- Active Bets View
CREATE VIEW IF NOT EXISTS vw_active_bets AS
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
ORDER BY b.value_score DESC, b.confidence DESC;

-- Betting Performance Summary View
CREATE VIEW IF NOT EXISTS vw_betting_summary AS
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
WHERE settled_at IS NOT NULL;

-- Recent Performance View (Last 30 Days)
CREATE VIEW IF NOT EXISTS vw_recent_performance AS
SELECT 
    a.date,
    a.total_predictions,
    a.correct_predictions,
    a.accuracy,
    a.avg_confidence
FROM accuracy_metrics a
WHERE a.date >= CURRENT_DATE - INTERVAL 30 DAY
ORDER BY a.date DESC;

-- Team Statistics View
CREATE VIEW IF NOT EXISTS vw_team_stats AS
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
ORDER BY t.canonical_name;

-- ============================================================================
-- UTILITY FUNCTIONS (DuckDB specific - remove for SQLite)
-- ============================================================================

-- Calculate American Odds to Decimal Probability
CREATE MACRO IF NOT EXISTS american_to_prob(odds) AS
    CASE 
        WHEN odds > 0 THEN 100.0 / (odds + 100.0)
        WHEN odds < 0 THEN ABS(odds) / (ABS(odds) + 100.0)
        ELSE NULL
    END;

-- Calculate Expected Value for a Bet
CREATE MACRO IF NOT EXISTS expected_value(win_prob, odds, bet_amount) AS
    CASE
        WHEN odds > 0 THEN 
            (win_prob * (bet_amount + (bet_amount * odds / 100.0))) - ((1 - win_prob) * bet_amount)
        WHEN odds < 0 THEN
            (win_prob * (bet_amount + (bet_amount / (ABS(odds) / 100.0)))) - ((1 - win_prob) * bet_amount)
        ELSE 0
    END;

-- ============================================================================
-- DATA INTEGRITY CONSTRAINTS
-- ============================================================================

-- Ensure win probabilities sum to 1.0
CREATE TRIGGER IF NOT EXISTS trg_validate_probabilities
BEFORE INSERT ON predictions
BEGIN
    SELECT CASE
        WHEN ABS((NEW.home_win_prob + NEW.away_win_prob) - 1.0) > 0.01
        THEN RAISE(ABORT, 'Win probabilities must sum to 1.0')
    END;
END;

-- Auto-update updated_at timestamp on games
CREATE TRIGGER IF NOT EXISTS trg_games_updated_at
BEFORE UPDATE ON games
BEGIN
    UPDATE games SET updated_at = CURRENT_TIMESTAMP WHERE game_id = NEW.game_id;
END;

-- Auto-update updated_at timestamp on teams
CREATE TRIGGER IF NOT EXISTS trg_teams_updated_at
BEFORE UPDATE ON teams
BEGIN
    UPDATE teams SET updated_at = CURRENT_TIMESTAMP WHERE team_id = NEW.team_id;
END;

-- Auto-update updated_at timestamp on team_features
CREATE TRIGGER IF NOT EXISTS trg_features_updated_at
BEFORE UPDATE ON team_features
BEGIN
    UPDATE team_features SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ============================================================================
-- INITIAL DATA / SEED DATA (Optional)
-- ============================================================================

-- Example: Insert some common conferences
-- INSERT INTO teams (team_id, canonical_name, display_name, conference, division)
-- VALUES 
--     ('duke', 'Duke', 'Duke Blue Devils', 'ACC', 'D1'),
--     ('unc', 'North Carolina', 'North Carolina Tar Heels', 'ACC', 'D1');

-- ============================================================================
-- PERFORMANCE NOTES
-- ============================================================================

-- For DuckDB:
-- - Use PRAGMA threads=4; for parallel execution
-- - Use PRAGMA memory_limit='4GB'; to set memory limit
-- - Run VACUUM; periodically to reclaim space
-- - Use Parquet format for archiving: COPY (SELECT * FROM games) TO 'games_backup.parquet';

-- For SQLite:
-- - Run VACUUM; periodically to reclaim space
-- - Use PRAGMA journal_mode=WAL; for better concurrency
-- - Use PRAGMA synchronous=NORMAL; for better performance
-- - Create additional indexes for frequently queried columns

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

-- To import from CSV (DuckDB):
-- COPY games FROM 'data/Completed_Games.csv' (AUTO_DETECT TRUE);

-- To export to CSV (DuckDB):
-- COPY games TO 'data/games_export.csv' (HEADER, DELIMITER ',');

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
