#!/usr/bin/env python3
"""
Rebuild Database (Compact)

Rebuilds the database from scratch to eliminate all internal overhead.
This should reduce the 44+ MB of overhead significantly.

Strategy:
- Export all data to temporary storage
- Create fresh database
- Import only needed data
- Result: Compact database with minimal overhead
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
import pandas as pd


def format_bytes(bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def rebuild_database_compact(dry_run=True):
    """
    Rebuild database from scratch to eliminate overhead.
    """
    print("="*80)
    print("REBUILD DATABASE (COMPACT)")
    print("="*80)
    print()
    
    data_dir = Path(__file__).parent.parent / 'data'
    old_db_path = data_dir / 'ncaa_predictions.duckdb'
    new_db_path = data_dir / 'ncaa_predictions_rebuilt.duckdb'
    
    if not old_db_path.exists():
        print(f"❌ Error: Database not found at {old_db_path}")
        return False
    
    old_size = old_db_path.stat().st_size
    print(f"Current database: {old_db_path.name}")
    print(f"Current size: {format_bytes(old_size)}")
    print(f"Target: Under 50 MB")
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - Analyzing only")
        print()
    
    # Connect to old database
    old_conn = duckdb.connect(str(old_db_path), read_only=True)
    
    # Get row counts
    tables = {}
    table_list = ['games', 'predictions', 'teams', 'team_features', 
                  'bets', 'parlays', 'parlay_legs', 'accuracy_metrics', 'drift_metrics']
    
    print("Current database contents:")
    total_rows = 0
    for table in table_list:
        try:
            count = old_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            tables[table] = count
            total_rows += count
            print(f"  {table:20} {count:>8,} rows")
        except:
            print(f"  {table:20} {'N/A':>8}")
    
    print()
    print(f"Total rows: {total_rows:,}")
    print(f"Actual size: {format_bytes(old_size)}")
    print(f"Overhead: {format_bytes(old_size - (total_rows * 300))}")  # ~300 bytes per row estimate
    print()
    
    if dry_run:
        # Estimate new size
        estimated_bytes_per_row = 250  # Compact storage
        estimated_size = total_rows * estimated_bytes_per_row
        estimated_overhead = estimated_size * 0.15  # 15% overhead for indexes
        total_estimated = estimated_size + estimated_overhead
        
        print("Estimated rebuilt size:")
        print(f"  Data: {format_bytes(estimated_size)}")
        print(f"  Overhead (15%): {format_bytes(estimated_overhead)}")
        print(f"  Total: {format_bytes(total_estimated)}")
        print(f"  Under 50 MB: {'✅ Yes' if total_estimated < 50*1024*1024 else '⚠️  Might be close'}")
        print()
        print("="*80)
        print("DRY RUN COMPLETE")
        print("="*80)
        print()
        print("To execute the rebuild, run:")
        print("  python scripts/rebuild_database_compact.py --execute")
        print()
        old_conn.close()
        return True
    
    # Execute rebuild
    print("="*80)
    print("EXECUTING REBUILD")
    print("="*80)
    print()
    
    print("1. Exporting data from old database...")
    
    # Export each table to pandas DataFrame (in memory)
    data_cache = {}
    for table in table_list:
        if tables.get(table, 0) > 0:
            print(f"   - Exporting {table}... ", end='', flush=True)
            try:
                df = old_conn.execute(f"SELECT * FROM {table}").df()
                data_cache[table] = df
                print(f"✓ ({len(df):,} rows)")
            except Exception as e:
                print(f"⚠️  Skipped: {e}")
    
    old_conn.close()
    print()
    
    # Create new database
    print("2. Creating new compact database...")
    if new_db_path.exists():
        new_db_path.unlink()
    
    new_conn = duckdb.connect(str(new_db_path))
    
    # Create schema
    print("   - Creating schema...")
    schema_path = Path(__file__).parent.parent / 'database_schema.sql'
    if schema_path.exists():
        schema_sql = schema_path.read_text()
        # Execute schema (split by semicolon and execute each statement)
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        for stmt in statements:
            if stmt and not stmt.startswith('--'):
                try:
                    new_conn.execute(stmt)
                except Exception as e:
                    # Skip errors from IF NOT EXISTS, etc.
                    pass
        print("   ✓ Schema created")
    
    # Import data
    print("   - Importing data...")
    for table, df in data_cache.items():
        print(f"     • {table}... ", end='', flush=True)
        try:
            new_conn.execute(f"INSERT INTO {table} SELECT * FROM df")
            print(f"✓ ({len(df):,} rows)")
        except Exception as e:
            print(f"⚠️  Error: {e}")
    
    # VACUUM to optimize
    print("   - Optimizing database...")
    try:
        new_conn.execute("VACUUM")
        new_conn.execute("CHECKPOINT")
        print("   ✓ Optimized")
    except Exception as e:
        print(f"   Note: {e}")
    
    new_conn.close()
    print()
    
    # Check new size
    new_size = new_db_path.stat().st_size
    
    print("3. Replacing old database...")
    backup_path = old_db_path.with_name('ncaa_predictions.duckdb.old')
    if backup_path.exists():
        backup_path.unlink()
    shutil.move(str(old_db_path), str(backup_path))
    shutil.move(str(new_db_path), str(old_db_path))
    print(f"   ✓ Old database backed up to {backup_path.name}")
    print(f"   ✓ New database active")
    print()
    
    # Summary
    print("="*80)
    print("REBUILD COMPLETE")
    print("="*80)
    print()
    print(f"Old size: {format_bytes(old_size)}")
    print(f"New size: {format_bytes(new_size)}")
    print(f"Reduction: {format_bytes(old_size - new_size)} ({((old_size - new_size) / old_size * 100):.1f}%)")
    print()
    print(f"✅ Under GitHub 50 MB limit: {'Yes' if new_size < 50*1024*1024 else 'No (but closer!)'}")
    print()
    
    # Verify data
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    
    verify_conn = duckdb.connect(str(old_db_path), read_only=True)
    
    print()
    for table in table_list:
        if table in tables:
            try:
                new_count = verify_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                old_count = tables[table]
                status = "✓" if new_count == old_count else "⚠️"
                print(f"{status} {table:20} {new_count:>8,} rows (was {old_count:,})")
            except:
                pass
    
    verify_conn.close()
    
    print()
    print("="*80)
    print("Next steps:")
    print("  1. Test the application")
    print("  2. Run: python scripts/export_to_json.py")
    print("  3. Commit if everything works")
    print("  4. Delete old backup: rm data/*.old")
    print("="*80)
    print()
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Rebuild database to eliminate overhead'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually rebuild the database (default is dry-run)'
    )
    
    args = parser.parse_args()
    
    success = rebuild_database_compact(dry_run=not args.execute)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
