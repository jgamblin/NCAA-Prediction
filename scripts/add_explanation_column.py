#!/usr/bin/env python3
"""
Add explanation column to predictions table.

This migration adds the missing 'explanation' TEXT column to the predictions table,
which is required by the predictions repository but was missing from the schema.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection


def main():
    """Add explanation column to predictions table."""
    
    print("="*80)
    print("DATABASE MIGRATION: Add explanation column to predictions")
    print("="*80)
    print()
    
    db = get_db_connection()
    
    try:
        # Check if column already exists
        result = db.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'predictions' AND column_name = 'explanation'
        """).fetchall()
        
        if result:
            print("✓ Column 'explanation' already exists in predictions table")
            print("  No migration needed")
            return 0
        
        # Add the column
        print("Adding 'explanation' TEXT column to predictions table...")
        db.execute("""
            ALTER TABLE predictions 
            ADD COLUMN explanation TEXT
        """)
        
        print("✓ Successfully added 'explanation' column")
        print()
        print("="*80)
        print("✅ MIGRATION COMPLETE")
        print("="*80)
        print()
        print("Next steps:")
        print("  1. Re-run the daily pipeline: python daily_pipeline_db.py")
        print("  2. Predictions should now save to database successfully")
        print()
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
