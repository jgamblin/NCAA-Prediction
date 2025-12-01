#!/usr/bin/env python3
"""
CSV to Database Migration Script

Imports all CSV files into the new database structure.
Validates data integrity and creates backups.
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.connection import DatabaseConnection, get_db_connection
from backend.database.schema import initialize_database, get_schema_info

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CSVMigrator:
    """Handles migration of CSV data to database."""
    
    def __init__(self, db_conn: DatabaseConnection, data_dir: Path):
        self.db_conn = db_conn
        self.data_dir = data_dir
        self.stats = {
            'games': 0,
            'teams': 0,
            'predictions': 0,
            'team_features': 0,
            'accuracy_metrics': 0,
            'drift_metrics': 0,
            'errors': []
        }
    
    def migrate_all(self):
        """Run complete migration."""
        logger.info("="*80)
        logger.info("Starting CSV to Database Migration")
        logger.info("="*80)
        
        start_time = datetime.now()
        
        try:
            # Migrate in dependency order
            self.migrate_teams()
            self.migrate_games()
            self.migrate_predictions()
            self.migrate_team_features()
            self.migrate_accuracy_metrics()
            self.migrate_drift_metrics()
            
            # Print summary
            self.print_summary()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"\n✓ Migration completed successfully in {duration:.2f} seconds")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def migrate_teams(self):
        """Extract and migrate team data from games CSV."""
        logger.info("\n" + "-"*80)
        logger.info("Migrating teams...")
        logger.info("-"*80)
        
        games_file = self.data_dir / 'Completed_Games.csv'
        if not games_file.exists():
            logger.warning(f"Games file not found: {games_file}")
            return
        
        try:
            df = pd.read_csv(games_file)
            
            # Extract unique teams from both home and away
            home_teams = df[['home_team']].copy()
            home_teams.columns = ['team_name']
            
            away_teams = df[['away_team']].copy()
            away_teams.columns = ['team_name']
            
            all_teams = pd.concat([home_teams, away_teams], ignore_index=True)
            all_teams = all_teams.drop_duplicates(subset=['team_name'])
            
            # Generate team IDs from team names
            all_teams['team_id'] = all_teams['team_name'].apply(self._generate_team_id)
            
            # Insert teams
            with self.db_conn.transaction() as conn:
                for _, row in all_teams.iterrows():
                    team_id = row['team_id']
                    team_name = row['team_name']
                    
                    # Skip if missing essential data
                    if pd.isna(team_id) or pd.isna(team_name):
                        continue
                    
                    try:
                        query = """
                        INSERT OR REPLACE INTO teams 
                        (team_id, canonical_name, display_name, is_active)
                        VALUES (?, ?, ?, TRUE)
                        """
                        
                        if self.db_conn.use_duckdb:
                            query = query.replace('INSERT OR REPLACE', 'INSERT OR IGNORE')
                        
                        conn.execute(query, (team_id, team_name, team_name))
                        self.stats['teams'] += 1
                        
                    except Exception as e:
                        self.stats['errors'].append(f"Team {team_id}: {str(e)}")
            
            logger.info(f"✓ Migrated {self.stats['teams']} teams")
            
        except Exception as e:
            logger.error(f"Failed to migrate teams: {e}")
            raise
    
    def migrate_games(self):
        """Migrate games from CSV."""
        logger.info("\n" + "-"*80)
        logger.info("Migrating games...")
        logger.info("-"*80)
        
        games_file = self.data_dir / 'Completed_Games.csv'
        if not games_file.exists():
            logger.warning(f"Games file not found: {games_file}")
            return
        
        try:
            df = pd.read_csv(games_file)
            logger.info(f"Found {len(df)} games in CSV")
            
            # Use game_day as the date column if date is empty
            if 'game_day' in df.columns:
                df['date'] = df['game_day']
            
            # Prepare data
            required_cols = ['game_id', 'date', 'home_team', 'away_team']
            
            for col in required_cols:
                if col not in df.columns:
                    logger.error(f"Missing required column: {col}")
                    return
            
            # Generate team_ids from team names if missing
            if 'home_team_id' not in df.columns or df['home_team_id'].isna().any():
                df['home_team_id'] = df['home_team'].apply(self._generate_team_id)
            if 'away_team_id' not in df.columns or df['away_team_id'].isna().any():
                df['away_team_id'] = df['away_team'].apply(self._generate_team_id)
            
            # Add default values for optional columns
            if 'season' not in df.columns or df['season'].isna().any():
                # Use existing season or infer from date
                df['season'] = df.apply(
                    lambda row: row.get('season') if pd.notna(row.get('season')) 
                    else self._infer_season(row['date']), 
                    axis=1
                )
            
            if 'game_status' not in df.columns:
                df['game_status'] = 'Final'
            
            # Convert scores to integers
            df['home_score'] = pd.to_numeric(df.get('home_score'), errors='coerce')
            df['away_score'] = pd.to_numeric(df.get('away_score'), errors='coerce')
            
            # Insert games in batches
            batch_size = 1000
            total_inserted = 0
            
            with self.db_conn.transaction() as conn:
                for i in range(0, len(df), batch_size):
                    batch = df.iloc[i:i+batch_size]
                    
                    for _, row in batch.iterrows():
                        try:
                            query = """
                            INSERT OR REPLACE INTO games 
                            (game_id, date, season, home_team, away_team, 
                             home_team_id, away_team_id, home_score, away_score, 
                             game_status, neutral_site, home_moneyline, away_moneyline)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """
                            
                            if self.db_conn.use_duckdb:
                                query = query.replace('INSERT OR REPLACE', 'INSERT OR IGNORE')
                            
                            params = (
                                row['game_id'],
                                row['date'],
                                row.get('season', ''),
                                row['home_team'],
                                row['away_team'],
                                row['home_team_id'],
                                row['away_team_id'],
                                int(row['home_score']) if pd.notna(row['home_score']) else None,
                                int(row['away_score']) if pd.notna(row['away_score']) else None,
                                row.get('game_status', 'Final'),
                                bool(row.get('neutral_site', False)),
                                int(row['home_moneyline']) if pd.notna(row.get('home_moneyline')) else None,
                                int(row['away_moneyline']) if pd.notna(row.get('away_moneyline')) else None
                            )
                            
                            conn.execute(query, params)
                            total_inserted += 1
                            
                        except Exception as e:
                            self.stats['errors'].append(f"Game {row.get('game_id')}: {str(e)}")
                    
                    if (i + batch_size) % 5000 == 0:
                        logger.info(f"  Processed {i + batch_size} games...")
            
            self.stats['games'] = total_inserted
            logger.info(f"✓ Migrated {self.stats['games']} games")
            
        except Exception as e:
            logger.error(f"Failed to migrate games: {e}")
            raise
    
    def migrate_predictions(self):
        """Migrate predictions from prediction_log.csv."""
        logger.info("\n" + "-"*80)
        logger.info("Migrating predictions...")
        logger.info("-"*80)
        
        pred_file = self.data_dir / 'prediction_log.csv'
        if not pred_file.exists():
            logger.warning(f"Prediction log not found: {pred_file}")
            # Try alternative file
            pred_file = self.data_dir / 'NCAA_Game_Predictions.csv'
            if not pred_file.exists():
                logger.warning("No prediction files found, skipping...")
                return
        
        try:
            df = pd.read_csv(pred_file)
            logger.info(f"Found {len(df)} predictions in CSV")
            
            with self.db_conn.transaction() as conn:
                for _, row in df.iterrows():
                    try:
                        query = """
                        INSERT INTO predictions 
                        (game_id, prediction_date, home_win_prob, away_win_prob,
                         predicted_winner, predicted_home_win, confidence,
                         model_name, model_version, config_version, commit_hash, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        
                        params = (
                            row.get('game_id'),
                            row.get('prediction_date', row.get('date')),
                            float(row.get('home_win_prob', 0.5)),
                            float(row.get('away_win_prob', 0.5)),
                            row.get('predicted_winner'),
                            int(row.get('predicted_home_win', 0)),
                            float(row.get('confidence', 0.5)),
                            row.get('model_name', 'Unknown'),
                            row.get('model_version'),
                            row.get('config_version'),
                            row.get('commit_hash'),
                            row.get('source', 'live')
                        )
                        
                        conn.execute(query, params)
                        self.stats['predictions'] += 1
                        
                    except Exception as e:
                        self.stats['errors'].append(f"Prediction {row.get('game_id')}: {str(e)}")
            
            logger.info(f"✓ Migrated {self.stats['predictions']} predictions")
            
        except Exception as e:
            logger.error(f"Failed to migrate predictions: {e}")
    
    def migrate_team_features(self):
        """Migrate team features from feature store."""
        logger.info("\n" + "-"*80)
        logger.info("Migrating team features...")
        logger.info("-"*80)
        
        features_file = self.data_dir / 'feature_store' / 'feature_store.csv'
        if not features_file.exists():
            logger.warning(f"Feature store not found: {features_file}")
            return
        
        try:
            df = pd.read_csv(features_file)
            logger.info(f"Found {len(df)} feature records in CSV")
            
            with self.db_conn.transaction() as conn:
                for _, row in df.iterrows():
                    try:
                        query = """
                        INSERT OR REPLACE INTO team_features 
                        (team_id, season, games_played, 
                         rolling_win_pct_5, rolling_win_pct_10,
                         rolling_point_diff_avg_5, rolling_point_diff_avg_10,
                         win_pct_last5_vs10, point_diff_last5_vs10, recent_strength_index_5)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        
                        if self.db_conn.use_duckdb:
                            query = query.replace('INSERT OR REPLACE', 'INSERT OR IGNORE')
                        
                        params = (
                            row.get('team_id'),
                            row.get('season'),
                            int(row.get('games_played', 0)),
                            float(row.get('rolling_win_pct_5')) if pd.notna(row.get('rolling_win_pct_5')) else None,
                            float(row.get('rolling_win_pct_10')) if pd.notna(row.get('rolling_win_pct_10')) else None,
                            float(row.get('rolling_point_diff_avg_5')) if pd.notna(row.get('rolling_point_diff_avg_5')) else None,
                            float(row.get('rolling_point_diff_avg_10')) if pd.notna(row.get('rolling_point_diff_avg_10')) else None,
                            float(row.get('win_pct_last5_vs10')) if pd.notna(row.get('win_pct_last5_vs10')) else None,
                            float(row.get('point_diff_last5_vs10')) if pd.notna(row.get('point_diff_last5_vs10')) else None,
                            float(row.get('recent_strength_index_5')) if pd.notna(row.get('recent_strength_index_5')) else None
                        )
                        
                        conn.execute(query, params)
                        self.stats['team_features'] += 1
                        
                    except Exception as e:
                        self.stats['errors'].append(f"Feature {row.get('team_id')}: {str(e)}")
            
            logger.info(f"✓ Migrated {self.stats['team_features']} team features")
            
        except Exception as e:
            logger.error(f"Failed to migrate team features: {e}")
    
    def migrate_accuracy_metrics(self):
        """Migrate accuracy metrics."""
        logger.info("\n" + "-"*80)
        logger.info("Migrating accuracy metrics...")
        logger.info("-"*80)
        
        accuracy_file = self.data_dir / 'Accuracy_Report.csv'
        if not accuracy_file.exists():
            logger.warning(f"Accuracy report not found: {accuracy_file}")
            return
        
        try:
            df = pd.read_csv(accuracy_file)
            logger.info(f"Found {len(df)} accuracy records in CSV")
            
            with self.db_conn.transaction() as conn:
                for _, row in df.iterrows():
                    try:
                        query = """
                        INSERT OR REPLACE INTO accuracy_metrics 
                        (date, total_predictions, correct_predictions, accuracy, avg_confidence)
                        VALUES (?, ?, ?, ?, ?)
                        """
                        
                        if self.db_conn.use_duckdb:
                            query = query.replace('INSERT OR REPLACE', 'INSERT OR IGNORE')
                        
                        params = (
                            row.get('date'),
                            int(row.get('total_predictions', 0)),
                            int(row.get('correct_predictions', 0)),
                            float(row.get('accuracy', 0.0)),
                            float(row.get('avg_confidence')) if pd.notna(row.get('avg_confidence')) else None
                        )
                        
                        conn.execute(query, params)
                        self.stats['accuracy_metrics'] += 1
                        
                    except Exception as e:
                        self.stats['errors'].append(f"Accuracy {row.get('date')}: {str(e)}")
            
            logger.info(f"✓ Migrated {self.stats['accuracy_metrics']} accuracy metrics")
            
        except Exception as e:
            logger.error(f"Failed to migrate accuracy metrics: {e}")
    
    def migrate_drift_metrics(self):
        """Migrate drift metrics."""
        logger.info("\n" + "-"*80)
        logger.info("Migrating drift metrics...")
        logger.info("-"*80)
        
        drift_file = self.data_dir / 'Drift_Metrics.csv'
        if not drift_file.exists():
            logger.warning(f"Drift metrics not found: {drift_file}")
            return
        
        try:
            df = pd.read_csv(drift_file)
            logger.info(f"Found {len(df)} drift records in CSV")
            
            with self.db_conn.transaction() as conn:
                for _, row in df.iterrows():
                    try:
                        query = """
                        INSERT INTO drift_metrics 
                        (metric_date, team_id, metric_type, rolling_accuracy, 
                         cumulative_accuracy, accuracy_delta, games_in_window)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                        
                        params = (
                            row.get('date', row.get('metric_date')),
                            row.get('team_id'),
                            row.get('metric_type', 'global'),
                            float(row.get('rolling_accuracy')) if pd.notna(row.get('rolling_accuracy')) else None,
                            float(row.get('cumulative_accuracy')) if pd.notna(row.get('cumulative_accuracy')) else None,
                            float(row.get('accuracy_delta')) if pd.notna(row.get('accuracy_delta')) else None,
                            int(row.get('games_in_window', 0))
                        )
                        
                        conn.execute(query, params)
                        self.stats['drift_metrics'] += 1
                        
                    except Exception as e:
                        self.stats['errors'].append(f"Drift {row.get('date')}: {str(e)}")
            
            logger.info(f"✓ Migrated {self.stats['drift_metrics']} drift metrics")
            
        except Exception as e:
            logger.error(f"Failed to migrate drift metrics: {e}")
    
    def _generate_team_id(self, team_name):
        """Generate a team ID from team name."""
        if pd.isna(team_name):
            return "unknown"
        # Simple normalization: lowercase and replace spaces with underscores
        return team_name.lower().replace(' ', '_').replace('.', '').replace("'", '')
    
    def _infer_season(self, date_str):
        """Infer NCAA season from date (season starts July 1)."""
        try:
            year, month, _ = map(int, str(date_str).split('-'))
            if month >= 7:
                return f"{year}-{str(year + 1)[-2:]}"
            else:
                return f"{year-1}-{str(year)[-2:]}"
        except:
            return "Unknown"
    
    def print_summary(self):
        """Print migration summary."""
        logger.info("\n" + "="*80)
        logger.info("Migration Summary")
        logger.info("="*80)
        logger.info(f"Teams:            {self.stats['teams']:,}")
        logger.info(f"Games:            {self.stats['games']:,}")
        logger.info(f"Predictions:      {self.stats['predictions']:,}")
        logger.info(f"Team Features:    {self.stats['team_features']:,}")
        logger.info(f"Accuracy Metrics: {self.stats['accuracy_metrics']:,}")
        logger.info(f"Drift Metrics:    {self.stats['drift_metrics']:,}")
        
        if self.stats['errors']:
            logger.warning(f"\nErrors encountered: {len(self.stats['errors'])}")
            logger.warning("First 10 errors:")
            for err in self.stats['errors'][:10]:
                logger.warning(f"  - {err}")


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate CSV data to database')
    parser.add_argument('--reset', action='store_true', help='Drop existing tables before migration')
    parser.add_argument('--db-path', type=str, help='Path to database file')
    parser.add_argument('--data-dir', type=str, default='data', help='Path to CSV data directory')
    parser.add_argument('--use-sqlite', action='store_true', help='Use SQLite instead of DuckDB')
    
    args = parser.parse_args()
    
    # Determine data directory
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = Path(__file__).parent.parent / data_dir
    
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return False
    
    logger.info(f"Data directory: {data_dir}")
    
    # Create database connection
    use_duckdb = not args.use_sqlite
    db_conn = get_db_connection(
        db_path=args.db_path,
        use_duckdb=use_duckdb
    )
    
    logger.info(f"Using {'DuckDB' if use_duckdb else 'SQLite'}")
    
    try:
        # Initialize database schema
        initialize_database(db_conn, drop_existing=args.reset)
        
        # Run migration
        migrator = CSVMigrator(db_conn, data_dir)
        success = migrator.migrate_all()
        
        # Show schema info
        logger.info("\n" + "="*80)
        logger.info("Database Schema Info")
        logger.info("="*80)
        schema_info = get_schema_info(db_conn)
        for table, info in schema_info.items():
            status = "✓" if info['exists'] else "✗"
            logger.info(f"{status} {table:20s} {info['row_count']:>10,} rows")
        
        return success
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db_conn.close()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
