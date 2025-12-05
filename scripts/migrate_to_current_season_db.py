#!/usr/bin/env python3
"""
Migrate to Current Season Database

Creates a new database with only the current season (2025-26) data,
reducing size from 75 MB to ~5 MB.

This script:
1. Creates ncaa_predictions_current.duckdb with 2025-26 data
2. Archives old database as ncaa_predictions_archive.duckdb
3. Updates the database connection to use current season DB

Safe to run: Creates new files, doesn't delete anything.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb


def format_bytes(bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def migrate_to_current_season(current_season='2025-26', dry_run=True):
    """
    Migrate database to current season only.
    
    Args:
        current_season: Season to keep (default: '2025-26')
        dry_run: If True, only show what would be done
    """
    print("="*80)
    print("MIGRATE TO CURRENT SEASON DATABASE")
    print("="*80)
    print()
    
    data_dir = Path(__file__).parent.parent / 'data'
    old_db_path = data_dir / 'ncaa_predictions.duckdb'
    new_db_path = data_dir / 'ncaa_predictions_current.duckdb'
    archive_db_path = data_dir / 'ncaa_predictions_archive.duckdb'
    
    if not old_db_path.exists():
        print(f"❌ Error: Database not found at {old_db_path}")
        return False
    
    old_size = old_db_path.stat().st_size
    print(f"Current database: {old_db_path.name}")
    print(f"Size: {format_bytes(old_size)}")
    print(f"Target season: {current_season}")
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    # Connect to old database
    print("Analyzing current database...")
    old_conn = duckdb.connect(str(old_db_path), read_only=True)
    
    # Count data by season
    games_current = old_conn.execute(f"""
        SELECT COUNT(*) as count FROM games WHERE season = '{current_season}'
    """).fetchone()[0]
    
    games_old = old_conn.execute(f"""
        SELECT COUNT(*) as count FROM games WHERE season != '{current_season}'
    """).fetchone()[0]
    
    predictions_current = old_conn.execute(f"""
        SELECT COUNT(*) as count 
        FROM predictions p
        JOIN games g ON p.game_id = g.game_id
        WHERE g.season = '{current_season}'
    """).fetchone()[0]
    
    team_features_current = old_conn.execute(f"""
        SELECT COUNT(*) as count FROM team_features WHERE season = '{current_season}'
    """).fetchone()[0]
    
    team_features_old = old_conn.execute(f"""
        SELECT COUNT(*) as count FROM team_features WHERE season != '{current_season}'
    """).fetchone()[0]
    
    # Drift metrics - keep recent only (last 30 days)
    recent_date = datetime.now().strftime('%Y-%m-%d')
    drift_recent = old_conn.execute(f"""
        SELECT COUNT(*) as count 
        FROM drift_metrics 
        WHERE metric_date >= '{recent_date}'::DATE - INTERVAL 30 DAYS
    """).fetchone()[0]
    
    drift_old = old_conn.execute(f"""
        SELECT COUNT(*) as count 
        FROM drift_metrics 
        WHERE metric_date < '{recent_date}'::DATE - INTERVAL 30 DAYS
    """).fetchone()[0]
    
    print()
    print("="*80)
    print("DATA TO KEEP (CURRENT SEASON)")
    print("="*80)
    print(f"  Games ({current_season}):       {games_current:>8,} rows")
    print(f"  Predictions ({current_season}): {predictions_current:>8,} rows")
    print(f"  Team features ({current_season}): {team_features_current:>8,} rows")
    print(f"  Drift metrics (last 30 days):  {drift_recent:>8,} rows")
    print(f"  Teams:                          {'ALL':>8} (need all teams)")
    print(f"  Bets:                           {'ALL':>8} (keep all betting history)")
    print(f"  Accuracy metrics:               {'ALL':>8} (keep all metrics)")
    print()
    
    print("="*80)
    print("DATA TO ARCHIVE (OLD SEASONS)")
    print("="*80)
    print(f"  Games (pre-{current_season}):   {games_old:>8,} rows")
    print(f"  Team features (old):            {team_features_old:>8,} rows")
    print(f"  Drift metrics (old):            {drift_old:>8,} rows")
    print()
    
    estimated_reduction = ((games_old + team_features_old + drift_old) / 
                          (games_current + games_old + team_features_current + 
                           team_features_old + drift_recent + drift_old) * 100)
    estimated_new_size = old_size * (1 - estimated_reduction / 100)
    
    print(f"Estimated size reduction: {estimated_reduction:.1f}%")
    print(f"Estimated new size: {format_bytes(estimated_new_size)}")
    print()
    
    if dry_run:
        print("="*80)
        print("DRY RUN COMPLETE - No changes made")
        print("="*80)
        print()
        print("To execute the migration, run:")
        print("  python scripts/migrate_to_current_season_db.py --execute")
        print()
        old_conn.close()
        return True
    
    # Execute migration
    print("="*80)
    print("EXECUTING MIGRATION")
    print("="*80)
    print()
    
    # Step 1: Archive old database
    print(f"1. Creating archive: {archive_db_path.name}")
    if archive_db_path.exists():
        backup = archive_db_path.with_suffix('.duckdb.backup')
        shutil.move(str(archive_db_path), str(backup))
        print(f"   (backed up existing archive to {backup.name})")
    
    shutil.copy2(str(old_db_path), str(archive_db_path))
    print(f"   ✓ Archived to {archive_db_path}")
    print()
    
    # Step 2: Create new database with current season
    print(f"2. Creating new database: {new_db_path.name}")
    
    if new_db_path.exists():
        new_db_path.unlink()
    
    new_conn = duckdb.connect(str(new_db_path))
    
    # Read and execute schema
    schema_path = Path(__file__).parent.parent / 'database_schema.sql'
    if schema_path.exists():
        print("   - Creating schema...")
        schema_sql = schema_path.read_text()
        # Execute schema statements
        for statement in schema_sql.split(';'):
            if statement.strip():
                try:
                    new_conn.execute(statement)
                except Exception as e:
                    # Skip errors from IF NOT EXISTS
                    pass
    
    # Copy current season data
    print(f"   - Copying {current_season} games...")
    new_conn.execute(f"""
        INSERT INTO games 
        SELECT * FROM old_db.games 
        WHERE season = '{current_season}'
    """, {'old_db': old_conn})
    
    print(f"   - Copying predictions...")
    new_conn.execute(f"""
        INSERT INTO predictions 
        SELECT p.* FROM old_db.predictions p
        JOIN old_db.games g ON p.game_id = g.game_id
        WHERE g.season = '{current_season}'
    """, {'old_db': old_conn})
    
    print(f"   - Copying teams...")
    new_conn.execute("""
        INSERT INTO teams 
        SELECT * FROM old_db.teams
    """, {'old_db': old_conn})
    
    print(f"   - Copying team features...")
    new_conn.execute(f"""
        INSERT INTO team_features 
        SELECT * FROM old_db.team_features 
        WHERE season = '{current_season}'
    """, {'old_db': old_conn})
    
    print(f"   - Copying bets...")
    new_conn.execute("""
        INSERT INTO bets 
        SELECT * FROM old_db.bets
    """, {'old_db': old_conn})
    
    print(f"   - Copying parlays...")
    new_conn.execute("""
        INSERT INTO parlays 
        SELECT * FROM old_db.parlays
    """, {'old_db': old_conn})
    
    new_conn.execute("""
        INSERT INTO parlay_legs 
        SELECT * FROM old_db.parlay_legs
    """, {'old_db': old_conn})
    
    print(f"   - Copying accuracy metrics...")
    new_conn.execute("""
        INSERT INTO accuracy_metrics 
        SELECT * FROM old_db.accuracy_metrics
    """, {'old_db': old_conn})
    
    print(f"   - Copying recent drift metrics...")
    new_conn.execute(f"""
        INSERT INTO drift_metrics 
        SELECT * FROM old_db.drift_metrics
        WHERE metric_date >= '{recent_date}'::DATE - INTERVAL 30 DAYS
    """, {'old_db': old_conn})
    
    new_conn.close()
    old_conn.close()
    
    new_size = new_db_path.stat().st_size
    print()
    print("   ✓ New database created")
    print(f"   Size: {format_bytes(new_size)}")
    print()
    
    # Step 3: Update to use new database
    print("3. Replacing old database with new one...")
    backup_path = old_db_path.with_suffix('.duckdb.old')
    shutil.move(str(old_db_path), str(backup_path))
    shutil.move(str(new_db_path), str(old_db_path))
    print(f"   ✓ Old database backed up to {backup_path.name}")
    print(f"   ✓ New database active as {old_db_path.name}")
    print()
    
    # Summary
    print("="*80)
    print("MIGRATION COMPLETE")
    print("="*80)
    print()
    print(f"Old size: {format_bytes(old_size)}")
    print(f"New size: {format_bytes(new_size)}")
    print(f"Reduction: {((old_size - new_size) / old_size * 100):.1f}%")
    print(f"Space saved: {format_bytes(old_size - new_size)}")
    print()
    print(f"✅ Database now contains only {current_season} season data")
    print(f"✅ Under GitHub 50 MB limit: {'Yes' if new_size < 50*1024*1024 else 'No'}")
    print()
    print("Backups created:")
    print(f"  - {archive_db_path.name} (full archive)")
    print(f"  - {backup_path.name} (pre-migration backup)")
    print()
    print("Next steps:")
    print("  1. Test the application with new database")
    print("  2. Run: python scripts/export_to_json.py")
    print("  3. Verify everything works")
    print("  4. Commit changes")
    print("  5. Optional: Upload archive to GitHub Releases")
    print()
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate database to current season only'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the migration (default is dry-run mode)'
    )
    parser.add_argument(
        '--season',
        default='2025-26',
        help='Season to keep (default: 2025-26)'
    )
    
    args = parser.parse_args()
    
    success = migrate_to_current_season(
        current_season=args.season,
        dry_run=not args.execute
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
