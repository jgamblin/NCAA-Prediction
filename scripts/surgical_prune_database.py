#!/usr/bin/env python3
"""
Surgical Database Pruning

Reduces database size while preserving ALL games needed for model training.

Strategy:
- ✅ KEEP: All games (needed for training)
- ✅ KEEP: All predictions (current season only anyway)
- ✅ KEEP: All teams (needed for lookups)
- ✅ KEEP: All bets/parlays (betting history)
- ✅ KEEP: All accuracy metrics (performance tracking)
- 🔪 PRUNE: drift_metrics (keep only last 7 days, not ~30K rows)
- 🔪 PRUNE: team_features (keep only last 2 seasons)
- 🔧 VACUUM: Reclaim space from deleted rows

Expected reduction: ~40-50% while maintaining full functionality
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection


def format_bytes(bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def surgical_prune(dry_run=True):
    """
    Surgically prune database to reduce size without losing training data.
    
    Args:
        dry_run: If True, only show what would be deleted
    """
    print("="*80)
    print("SURGICAL DATABASE PRUNING")
    print("="*80)
    print()
    
    data_dir = Path(__file__).parent.parent / 'data'
    db_path = data_dir / 'ncaa_predictions.duckdb'
    
    if not db_path.exists():
        print(f"❌ Error: Database not found at {db_path}")
        return False
    
    old_size = db_path.stat().st_size
    print(f"Current database: {db_path.name}")
    print(f"Current size: {format_bytes(old_size)}")
    print(f"GitHub limit: 50.00 MB")
    print(f"Over limit by: {format_bytes(old_size - 50*1024*1024)}")
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    db = get_db_connection()
    
    # Analyze what will be kept/pruned
    print("="*80)
    print("ANALYSIS: What stays and what goes")
    print("="*80)
    print()
    
    # Games - KEEP ALL
    games_count = db.fetch_one("SELECT COUNT(*) as count FROM games")['count']
    print(f"✅ KEEP: All {games_count:,} games (needed for model training)")
    
    # Predictions - already current season only
    pred_count = db.fetch_one("SELECT COUNT(*) as count FROM predictions")['count']
    print(f"✅ KEEP: All {pred_count:,} predictions (current season)")
    
    # Teams - KEEP ALL
    teams_count = db.fetch_one("SELECT COUNT(*) as count FROM teams")['count']
    print(f"✅ KEEP: All {teams_count:,} teams (needed for lookups)")
    
    # Bets/Parlays - KEEP ALL
    bets_count = db.fetch_one("SELECT COUNT(*) as count FROM bets")['count']
    parlays_count = db.fetch_one("SELECT COUNT(*) as count FROM parlays")['count']
    print(f"✅ KEEP: All {bets_count:,} bets and {parlays_count:,} parlays")
    
    # Accuracy metrics - KEEP ALL
    accuracy_count = db.fetch_one("SELECT COUNT(*) as count FROM accuracy_metrics")['count']
    print(f"✅ KEEP: All {accuracy_count:,} accuracy metrics")
    print()
    
    # Drift metrics - AGGRESSIVE PRUNING (last 7 days only)
    cutoff_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    drift_total = db.fetch_one("SELECT COUNT(*) as count FROM drift_metrics")['count']
    drift_keep = db.fetch_one(f"""
        SELECT COUNT(*) as count FROM drift_metrics 
        WHERE metric_date >= '{cutoff_date}'::DATE
    """)['count']
    drift_delete = drift_total - drift_keep
    
    print(f"🔪 PRUNE: drift_metrics")
    print(f"   Total rows: {drift_total:,}")
    print(f"   Keep (last 7 days): {drift_keep:,}")
    print(f"   DELETE: {drift_delete:,} rows ({(drift_delete/drift_total*100):.1f}%)")
    print()
    
    # Team features - Keep last 2 seasons
    keep_seasons = ['2025-26', '2024-25']
    
    features_total = db.fetch_one("SELECT COUNT(*) as count FROM team_features")['count']
    features_keep = db.fetch_one(f"""
        SELECT COUNT(*) as count FROM team_features 
        WHERE season IN ('2025-26', '2024-25')
    """)['count']
    features_delete = features_total - features_keep
    
    print(f"🔪 PRUNE: team_features")
    print(f"   Total rows: {features_total:,}")
    print(f"   Keep (2024-25, 2025-26): {features_keep:,}")
    print(f"   DELETE: {features_delete:,} rows ({(features_delete/features_total*100):.1f}%)")
    print()
    
    # Estimated space savings
    total_rows_deleted = drift_delete + features_delete
    estimated_reduction_pct = 40  # Conservative estimate with vacuum
    estimated_new_size = old_size * (1 - estimated_reduction_pct / 100)
    
    print("="*80)
    print("ESTIMATED IMPACT")
    print("="*80)
    print(f"Total rows to delete: {total_rows_deleted:,}")
    print(f"Estimated size reduction: ~{estimated_reduction_pct}%")
    print(f"Estimated new size: {format_bytes(estimated_new_size)}")
    print(f"Under 50 MB: {'✅ Yes' if estimated_new_size < 50*1024*1024 else '⚠️  Close'}")
    print()
    
    if dry_run:
        print("="*80)
        print("DRY RUN COMPLETE - No changes made")
        print("="*80)
        print()
        print("To execute the pruning, run:")
        print("  python scripts/surgical_prune_database.py --execute")
        print()
        db.close()
        return True
    
    # Execute pruning
    print("="*80)
    print("EXECUTING PRUNING")
    print("="*80)
    print()
    
    # Backup first
    backup_path = db_path.with_suffix('.duckdb.backup')
    print(f"1. Creating backup: {backup_path.name}")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"   ✓ Backup created")
    print()
    
    # Prune drift_metrics
    print(f"2. Pruning drift_metrics (keeping last 7 days)...")
    try:
        with db.transaction() as conn:
            result = conn.execute(f"""
                DELETE FROM drift_metrics 
                WHERE metric_date < '{cutoff_date}'::DATE
            """)
        print(f"   ✓ Deleted {drift_delete:,} old drift metric rows")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        db.close()
        return False
    print()
    
    # Prune team_features
    print(f"3. Pruning team_features (keeping 2024-25, 2025-26)...")
    try:
        with db.transaction() as conn:
            result = conn.execute("""
                DELETE FROM team_features 
                WHERE season NOT IN ('2025-26', '2024-25')
            """)
        print(f"   ✓ Deleted {features_delete:,} old team feature rows")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        db.close()
        return False
    print()
    
    # VACUUM to reclaim space
    print("4. Vacuuming database to reclaim space...")
    print("   (This may take a minute...)")
    try:
        db.execute("VACUUM")
        print("   ✓ Database vacuumed")
    except Exception as e:
        print(f"   ⚠️  Vacuum warning: {e}")
        print("   (Database may still benefit from space reclamation)")
    print()
    
    # CHECKPOINT to flush changes (DuckDB specific)
    print("5. Checkpointing database...")
    try:
        db.execute("CHECKPOINT")
        print("   ✓ Database checkpointed")
    except Exception as e:
        print(f"   Note: {e}")
    print()
    
    db.close()
    
    # Check new size
    new_size = db_path.stat().st_size
    size_reduction = old_size - new_size
    size_reduction_pct = (size_reduction / old_size * 100) if old_size > 0 else 0
    
    print("="*80)
    print("PRUNING COMPLETE")
    print("="*80)
    print()
    print(f"Old size: {format_bytes(old_size)}")
    print(f"New size: {format_bytes(new_size)}")
    print(f"Space saved: {format_bytes(size_reduction)} ({size_reduction_pct:.1f}%)")
    print()
    print(f"✅ Under GitHub 50 MB limit: {'Yes' if new_size < 50*1024*1024 else 'No'}")
    print()
    print(f"Backup saved at: {backup_path}")
    print()
    
    # Verify critical data intact
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    db = get_db_connection()
    
    verify_games = db.fetch_one("SELECT COUNT(*) as count FROM games")['count']
    verify_preds = db.fetch_one("SELECT COUNT(*) as count FROM predictions")['count']
    
    print(f"✓ Games intact: {verify_games:,} (same as before)")
    print(f"✓ Predictions intact: {verify_preds:,} (same as before)")
    
    if verify_games == games_count and verify_preds == pred_count:
        print()
        print("✅ All critical data preserved!")
        print("   Model training will work as before")
    else:
        print()
        print("⚠️  WARNING: Data counts changed unexpectedly!")
        print("   Restore from backup if needed")
    
    db.close()
    
    print()
    print("="*80)
    print("Next steps:")
    print("  1. Test the application")
    print("  2. Run: python scripts/export_to_json.py")
    print("  3. Commit if everything works")
    print("  4. Delete backup if satisfied: rm data/*.backup")
    print("="*80)
    print()
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Surgically prune database to reduce size'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the pruning (default is dry-run mode)'
    )
    
    args = parser.parse_args()
    
    success = surgical_prune(dry_run=not args.execute)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
