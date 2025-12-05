#!/usr/bin/env python3
"""
Add Unique Constraint to Predictions Table

Adds a unique constraint on game_id to prevent duplicate predictions.
This must be run AFTER cleanup_duplicate_predictions.py to remove existing duplicates.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection


def add_unique_constraint():
    """Add unique constraint to predictions.game_id."""
    db = get_db_connection()
    
    print("="*80)
    print("ADD UNIQUE CONSTRAINT TO PREDICTIONS TABLE")
    print("="*80)
    print()
    
    # First, verify no duplicates exist
    check_query = """
        SELECT 
            game_id,
            COUNT(*) as count
        FROM predictions
        GROUP BY game_id
        HAVING COUNT(*) > 1
    """
    
    duplicates = db.fetch_df(check_query)
    
    if not duplicates.empty:
        print(f"❌ ERROR: {len(duplicates)} games still have duplicate predictions!")
        print(f"\nYou must run cleanup_duplicate_predictions.py first:")
        print(f"  python scripts/cleanup_duplicate_predictions.py --execute")
        print()
        db.close()
        return False
    
    print("✓ Verified: No duplicate predictions exist")
    
    # Check if constraint already exists by trying to query it
    # For DuckDB, we can check information_schema
    try:
        if db.use_duckdb:
            constraint_check = """
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'predictions' 
                  AND constraint_type = 'UNIQUE'
                  AND constraint_name LIKE '%game_id%'
            """
        else:
            # SQLite: Check pragma
            constraint_check = "PRAGMA index_list('predictions')"
        
        existing = db.fetch_df(constraint_check)
        
        if not existing.empty and any('game_id' in str(row).lower() for row in existing.values):
            print("\n✓ Unique constraint already exists on game_id")
            db.close()
            return True
            
    except Exception as e:
        print(f"Note: Could not check existing constraints: {e}")
    
    # Add unique index (works for both DuckDB and SQLite)
    print("\nAdding unique constraint on game_id...")
    
    try:
        with db.transaction() as conn:
            # Create unique index which enforces uniqueness
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_game_id_unique 
                ON predictions(game_id)
            """)
        
        print("✓ Successfully added unique constraint")
        print("\n✅ Database now enforces one prediction per game")
        
    except Exception as e:
        print(f"\n❌ Error adding constraint: {e}")
        print("\nNote: If the error is about duplicates, run cleanup first:")
        print("  python scripts/cleanup_duplicate_predictions.py --execute")
        db.close()
        return False
    
    print("\n" + "="*80)
    print("MIGRATION COMPLETE")
    print("="*80)
    
    db.close()
    return True


def main():
    """Main entry point."""
    success = add_unique_constraint()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
