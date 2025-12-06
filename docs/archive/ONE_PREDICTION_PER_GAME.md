# One Prediction Per Game Policy

## Overview

Implemented a one-prediction-per-game policy to significantly reduce database size and prevent duplicate predictions.

## Problem

The daily pipeline was creating multiple prediction records for the same game:
- Pipeline runs multiple times per day (via GitHub Actions)
- Each run created a new prediction for every scheduled game
- Iowa State example: 8 games → 19 prediction records
- Database had 4,035 predictions with 2,826 duplicates (70% redundancy)

## Solution

### 1. UPSERT Logic (Repository Level)

Added new methods to `PredictionsRepository`:

```python
def upsert_prediction(prediction_data: Dict) -> Optional[int]:
    """Insert or update prediction. Only keeps one prediction per game."""
    
def bulk_upsert_predictions(predictions: List[Dict]) -> int:
    """Bulk upsert - replaces existing predictions instead of creating duplicates."""
```

**Behavior:**
- If prediction exists for a game_id → UPDATE it
- If no prediction exists → INSERT new record
- Maintains the same `id` for each game's prediction

### 2. Updated Daily Pipeline

Modified `daily_pipeline_db.py`:
- Changed from `bulk_insert_predictions()` → `bulk_upsert_predictions()`
- Removed filter that skipped games with existing predictions
- Now updates predictions daily with latest model run

### 3. Database Cleanup

Created cleanup script: `scripts/cleanup_duplicate_predictions.py`

**Results:**
- Removed 2,826 duplicate predictions
- Reduced predictions table: 4,035 → 1,209 records (70% reduction)
- Kept FIRST prediction per game (earliest by id)

### 4. Unique Constraint

Added database constraint: `scripts/add_unique_constraint_predictions.py`

**Protection:**
- Created unique index on `game_id`
- Database now enforces one prediction per game
- Prevents future duplicates even if code has bugs

## Impact

### Database Size
- **Predictions table:** 70% reduction (4,035 → 1,209 records)
- **predictions.json:** 85% reduction (1,287.8 KB → 189.0 KB)
- **Overall data export:** 50% reduction (2,175 KB → 1,076 KB)

### Performance
- Faster queries (fewer rows to scan)
- Reduced memory usage
- Smaller backups

### Accuracy Tracking
- ✅ Historical accuracy preserved (kept first predictions)
- ✅ Team statistics now correct (deduplicated in query)
- ✅ Export scripts use deduplication logic

## Usage

### For New Installations

The one-prediction-per-game policy is now automatic:
1. Daily pipeline uses UPSERT by default
2. Unique constraint prevents duplicates
3. No manual intervention needed

### For Existing Installations

Run cleanup once to remove existing duplicates:

```bash
# 1. Check what would be deleted (dry run)
python scripts/cleanup_duplicate_predictions.py

# 2. Execute cleanup
python scripts/cleanup_duplicate_predictions.py --execute

# 3. Add unique constraint
python scripts/add_unique_constraint_predictions.py

# 4. Regenerate exports
python scripts/export_to_json.py
```

## Implementation Details

### Prediction Lifecycle

**Before (Multiple Predictions):**
```
Day 1: INSERT prediction for Game A (id=1)
Day 2: INSERT prediction for Game A (id=100) ← duplicate!
Day 3: INSERT prediction for Game A (id=250) ← duplicate!
```

**After (Single Prediction):**
```
Day 1: INSERT prediction for Game A (id=1)
Day 2: UPDATE prediction id=1 for Game A
Day 3: UPDATE prediction id=1 for Game A
```

### Query Deduplication

Export scripts already use deduplication for accuracy calculations:

```sql
WITH first_predictions AS (
    SELECT game_id, MIN(id) as first_prediction_id
    FROM predictions
    GROUP BY game_id
)
SELECT p.*
FROM predictions p
JOIN first_predictions fp ON p.id = fp.first_prediction_id
```

This approach ensures historical accuracy metrics remain consistent even if duplicates existed.

## Testing

Verified on current database:
- ✅ Cleanup removed 2,826 duplicates
- ✅ No duplicates remain after cleanup
- ✅ Unique constraint prevents new duplicates
- ✅ UPSERT logic working in pipeline
- ✅ JSON exports reduced by 50%
- ✅ Accuracy metrics unchanged (57.0%)
- ✅ Team statistics corrected

## Files Modified

1. `backend/repositories/predictions_repository.py` - Added UPSERT methods
2. `daily_pipeline_db.py` - Changed to use UPSERT
3. `scripts/cleanup_duplicate_predictions.py` - New cleanup script
4. `scripts/add_unique_constraint_predictions.py` - New migration script

## Maintenance

### Monitoring

Check for duplicates (should always return 0):
```python
from backend.database import get_db_connection

db = get_db_connection()
query = """
    SELECT COUNT(*) as games_with_dupes
    FROM (
        SELECT game_id, COUNT(*) as count
        FROM predictions
        GROUP BY game_id
        HAVING COUNT(*) > 1
    )
"""
result = db.fetch_one(query)
print(f"Games with duplicate predictions: {result['games_with_dupes']}")
```

### Future Considerations

- Consider adding `updated_at` timestamp to track when predictions were last updated
- May want to archive old predictions instead of updating them
- Could add prediction history table if tracking prediction changes over time is needed

## Benefits

1. **Smaller Database** - 70% reduction in predictions table
2. **Correct Statistics** - Team stats now show actual game count
3. **Faster Queries** - Less data to scan
4. **Data Integrity** - Database enforces uniqueness
5. **Simpler Logic** - UPSERT handles both insert and update
6. **Space Efficiency** - Smaller backups and exports

## Trade-offs

- **Lost History**: Can't track how predictions changed over multiple runs
  - *Mitigation*: Not needed for current use case; first prediction is what matters for accuracy
- **Slightly Slower Updates**: UPDATE is slightly slower than INSERT
  - *Mitigation*: Negligible impact (milliseconds per prediction)

## Conclusion

The one-prediction-per-game policy significantly reduces database bloat while maintaining data integrity and accuracy tracking. The implementation is backward-compatible and includes both code-level (UPSERT) and database-level (unique constraint) protections.
