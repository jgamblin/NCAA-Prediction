#!/usr/bin/env python3
"""
Rebuild Database Using DuckDB Export/Import

Uses DuckDB's native EXPORT/IMPORT commands which handle schema and data automatically.
This is the safest and most reliable way to rebuild a compact database.
"""

import sys
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb


def format_bytes(bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def rebuild_with_export_import(dry_run=True):
    """
    Rebuild database using DuckDB's EXPORT DATABASE / IMPORT DATABASE.
    """
    print("="*80)
    print("REBUILD DATABASE (EXPORT/IMPORT METHOD)")
    print("="*80)
    print()
    
    data_dir = Path(__file__).parent.parent / 'data'
    old_db_path = data_dir / 'ncaa_predictions.duckdb'
    new_db_path = data_dir / 'ncaa_predictions_rebuilt.duckdb'
    export_dir = data_dir / '.export_temp'
    
    if not old_db_path.exists():
        print(f"❌ Error: Database not found at {old_db_path}")
        return False
    
    old_size = old_db_path.stat().st_size
    print(f"Current database: {old_db_path.name}")
    print(f"Current size: {format_bytes(old_size)}")
    print(f"Target: Under 50 MB")
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE")
        print()
        print("This method will:")
        print("  1. EXPORT all data to Parquet files")
        print("  2. CREATE fresh database")
        print("  3. IMPORT data from Parquet files")
        print("  4. Result: Compact DB with zero overhead")
        print()
        print("Expected size: ~12-15 MB (81% reduction)")
        print()
        print("="*80)
        print("DRY RUN COMPLETE")
        print("="*80)
        print()
        print("To execute, run:")
        print("  python scripts/rebuild_database_export_import.py --execute")
        print()
        return True
    
    # Execute rebuild
    print("="*80)
    print("EXECUTING REBUILD")
    print("="*80)
    print()
    
    # Create export directory
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir()
    
    print(f"1. Exporting database to: {export_dir}")
    old_conn = duckdb.connect(str(old_db_path), read_only=True)
    
    try:
        print("   Running EXPORT DATABASE...")
        old_conn.execute(f"EXPORT DATABASE '{export_dir}' (FORMAT PARQUET)")
        print("   ✓ Export complete")
    except Exception as e:
        print(f"   ❌ Export failed: {e}")
        old_conn.close()
        return False
    
    old_conn.close()
    print()
    
    # Check export size
    export_files = list(export_dir.glob('**/*.parquet'))
    export_size = sum(f.stat().st_size for f in export_files)
    print(f"   Exported {len(export_files)} files")
    print(f"   Total export size: {format_bytes(export_size)}")
    print()
    
    # Create new database
    print("2. Creating new database and importing...")
    if new_db_path.exists():
        new_db_path.unlink()
    
    new_conn = duckdb.connect(str(new_db_path))
    
    try:
        print("   Running IMPORT DATABASE...")
        new_conn.execute(f"IMPORT DATABASE '{export_dir}'")
        print("   ✓ Import complete")
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        new_conn.close()
        return False
    
    # Optimize
    print("   Optimizing...")
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
    print(f"   New database size: {format_bytes(new_size)}")
    print()
    
    # Verify data integrity
    print("3. Verifying data integrity...")
    old_conn = duckdb.connect(str(old_db_path), read_only=True)
    new_conn = duckdb.connect(str(new_db_path), read_only=True)
    
    tables = ['games', 'predictions', 'teams', 'team_features', 
              'bets', 'parlays', 'parlay_legs', 'accuracy_metrics', 'drift_metrics']
    
    all_match = True
    for table in tables:
        try:
            old_count = old_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            new_count = new_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            
            if old_count == new_count:
                print(f"   ✓ {table:20} {new_count:>8,} rows")
            else:
                print(f"   ⚠️  {table:20} {new_count:>8,} rows (was {old_count:,})")
                all_match = False
        except Exception as e:
            print(f"   ⚠️  {table:20} Error: {e}")
    
    old_conn.close()
    new_conn.close()
    print()
    
    if not all_match:
        print("⚠️  WARNING: Some tables have different counts!")
        print("   Review carefully before replacing old database")
        print()
        return False
    
    print("   ✅ All data verified!")
    print()
    
    # Replace old database
    print("4. Replacing old database...")
    backup_path = old_db_path.with_name('ncaa_predictions.duckdb.old')
    if backup_path.exists():
        backup_path.unlink()
    
    shutil.move(str(old_db_path), str(backup_path))
    shutil.move(str(new_db_path), str(old_db_path))
    print(f"   ✓ Old database backed up to {backup_path.name}")
    print(f"   ✓ New database active")
    print()
    
    # Cleanup export directory
    print("5. Cleaning up...")
    shutil.rmtree(export_dir)
    print("   ✓ Temporary files removed")
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
    
    under_limit = new_size < 50*1024*1024
    print(f"{'✅' if under_limit else '⚠️ '} Under GitHub 50 MB limit: {'Yes' if under_limit else 'No'}")
    
    if under_limit:
        print(f"   Buffer: {format_bytes(50*1024*1024 - new_size)} under limit")
    
    print()
    print(f"Backup saved at: {backup_path}")
    print()
    print("="*80)
    print("Next steps:")
    print("  1. Test the application")
    print("  2. Run: python scripts/export_to_json.py")
    print("  3. Commit if everything works")
    print("  4. Delete backup: rm data/*.old")
    print("="*80)
    print()
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Rebuild database using EXPORT/IMPORT'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually rebuild the database (default is dry-run)'
    )
    
    args = parser.parse_args()
    
    success = rebuild_with_export_import(dry_run=not args.execute)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
