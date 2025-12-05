#!/usr/bin/env python3
"""
Cleanup Duplicate Predictions

Removes duplicate predictions for the same game, keeping only the FIRST prediction
(earliest by prediction_date, lowest by id) per game_id.

This significantly reduces database size while maintaining historical accuracy tracking.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection


def cleanup_duplicate_predictions(dry_run=True):
    """
    Remove duplicate predictions, keeping only the first prediction per game.
    
    Args:
        dry_run: If True, only report what would be deleted without actually deleting
    """
    db = get_db_connection()
    
    print("="*80)
    print("CLEANUP DUPLICATE PREDICTIONS")
    print("="*80)
    print()
    
    # Get count before cleanup
    count_query = "SELECT COUNT(*) as total FROM predictions"
    before_count = db.fetch_one(count_query)['total']
    print(f"Total predictions before cleanup: {before_count:,}")
    
    # Find duplicates - games with more than one prediction
    duplicates_query = """
        SELECT 
            game_id,
            COUNT(*) as prediction_count
        FROM predictions
        GROUP BY game_id
        HAVING COUNT(*) > 1
        ORDER BY prediction_count DESC
    """
    
    duplicates_df = db.fetch_df(duplicates_query)
    
    if duplicates_df.empty:
        print("\n✓ No duplicate predictions found!")
        db.close()
        return
    
    print(f"\nFound {len(duplicates_df)} games with duplicate predictions:")
    print(f"  Total duplicate prediction records: {duplicates_df['prediction_count'].sum() - len(duplicates_df):,}")
    print(f"\nTop games with most duplicates:")
    for _, row in duplicates_df.head(10).iterrows():
        print(f"  - {row['game_id']}: {row['prediction_count']} predictions")
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN MODE - No changes made")
        print("="*80)
        print(f"\nTo actually delete duplicates, run:")
        print(f"  python scripts/cleanup_duplicate_predictions.py --execute")
        db.close()
        return
    
    # Delete duplicates, keeping only the first prediction per game
    # Strategy: For each game_id, keep the record with MIN(id) and delete the rest
    print("\n" + "="*80)
    print("DELETING DUPLICATES...")
    print("="*80)
    
    delete_query = """
        DELETE FROM predictions
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM predictions
            GROUP BY game_id
        )
    """
    
    try:
        with db.transaction() as conn:
            result = conn.execute(delete_query)
            # Get row count for DuckDB or SQLite
            if hasattr(result, 'rowcount'):
                deleted_count = result.rowcount
            else:
                # For DuckDB, we need to count explicitly
                after_count = db.fetch_one(count_query)['total']
                deleted_count = before_count - after_count
        
        print(f"\n✓ Deleted {deleted_count:,} duplicate predictions")
        
        # Get count after cleanup
        after_count = db.fetch_one(count_query)['total']
        print(f"Total predictions after cleanup: {after_count:,}")
        
        # Calculate space saved
        space_saved_pct = ((before_count - after_count) / before_count * 100) if before_count > 0 else 0
        print(f"Database size reduction: {space_saved_pct:.1f}%")
        
        # Verify no duplicates remain
        verify_df = db.fetch_df(duplicates_query)
        if verify_df.empty:
            print("\n✅ Verification passed: No duplicates remain!")
        else:
            print(f"\n⚠️ Warning: {len(verify_df)} games still have duplicates")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("CLEANUP COMPLETE")
    print("="*80)
    
    db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Cleanup duplicate predictions in database'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually delete duplicates (default is dry-run mode)'
    )
    
    args = parser.parse_args()
    
    cleanup_duplicate_predictions(dry_run=not args.execute)


if __name__ == '__main__':
    main()
