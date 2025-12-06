# Accuracy Fix Summary - December 6, 2025

## Problem

Prediction accuracy dropped catastrophically from **70%** to **36%** starting November 24, 2025.

## Root Cause Analysis

### The Issue
Starting Nov 24, team names in the database began including mascots (e.g., "Indiana Hoosiers", "DePaul Blue Demons") instead of normalized names without mascots (e.g., "Indiana", "DePaul").

### Why This Broke Predictions

1. **Model Training**: The model was trained on normalized team names like "Indiana"
2. **Prediction Input**: After Nov 24, predictions used non-normalized names like "Indiana Hoosiers"  
3. **Team Mismatch**: The model treated "Indiana" and "Indiana Hoosiers" as completely different teams
4. **Fallback Encoding**: Unknown teams got median encoding values → predictions became essentially random

### Evidence

**Before Nov 24 (Good Accuracy):**
- Nov 9: 79.4% accuracy
- Nov 10: 82.5% accuracy  
- Nov 11-23: 70-90% accuracy range

**After Nov 24 (Bad Accuracy):**
- Nov 24: 53.8% accuracy (dropped from 70%+)
- Nov 25: 56.8% accuracy
- Nov 26: 58.8% accuracy
- Nov 27: 44.4% accuracy
- Nov 30: 57.9% accuracy

## The Fix

### 1. Pipeline Fix (`daily_pipeline_db.py`)
**Changed:** Normalize team names immediately after scraping, before any database operations

```python
# Added after line 158
from data_collection.team_name_utils import normalize_game_dataframe
df = normalize_game_dataframe(df, team_columns=['home_team', 'away_team'])
print("✓ Normalized team names from ESPN")
```

**Impact:** All future games will be stored with normalized names

### 2. Model Fix (`adaptive_predictor.py`)  
**Changed:** Always normalize team names in `prepare_data()`, regardless of canonical column availability

```python
# Updated lines 443-457
# ALWAYS normalize team names to ensure consistency
# This is critical - the model trains on normalized names like "Indiana"
# but ESPN might provide "Indiana Hoosiers" which breaks predictions

# First, use canonical names if available
if 'home_team_canonical' in df.columns and 'away_team_canonical' in df.columns:
    df['home_team'] = df['home_team_canonical']
    df['away_team'] = df['away_team_canonical']

# ALWAYS apply normalization (even if canonical columns exist)
# to handle any edge cases or inconsistencies
if 'home_team' in df.columns:
    df['home_team'] = df['home_team'].apply(normalize_team_name)
if 'away_team' in df.columns:
    df['away_team'] = df['away_team'].apply(normalize_team_name)
```

**Impact:** Model now defensively normalizes all inputs

### 3. Database Migration (`scripts/fix_database_team_names.py`)
**Created:** Migration script to normalize all existing team names in the database

**Results:**
- **Games Table:** 0 games needed fixing (already normalized or A&M teams skipped)
- **Teams Table:** 2 teams fixed, 54 duplicates skipped to avoid constraint violations
- **Predictions Table:** **188 predictions fixed** (removed mascots from predicted_winner)

**Examples of Fixes:**
- "Marquette Golden Eagles" → "Marquette"
- "Purdue Fort Wayne Mastodons" → "Purdue Fort Wayne"  
- "Bowling Green Falcons" → "Bowling Green"
- "Baylor Bears" → "Baylor"
- "Illinois State Redbirds" → "Illinois State"
- "James Madison Dukes" → "James Madison"

## What Was Left Unfixed

### A&M Schools (Intentionally Skipped)
Teams with "A&M" (e.g., "Texas A&M", "Alabama A&M") were skipped due to URL encoding complications. These teams were already in the database correctly, so no harm done.

### Duplicate Teams
55 team aliases were skipped to avoid unique constraint violations. These duplicates will need to be cleaned up separately. Examples:
- "jmu" and "james_madison" both map to "James Madison"
- "fau" and "florida_atlantic" both map to "Florida Atlantic"
- "cal" and "california" both map to "California"

## Expected Results

After running the daily pipeline with these fixes:

1. **All new games** will have normalized team names
2. **All predictions** will match training data team names
3. **Accuracy should recover** to 70%+ range
4. **No more random predictions** from unknown team fallbacks

## Verification Steps

1. ✅ Run database migration: `python3 scripts/fix_database_team_names.py`
2. ⏳ Run daily pipeline: `python daily_pipeline_db.py`
3. ⏳ Check today's predictions for normalized names
4. ⏳ Wait for games to complete and track accuracy
5. ⏳ Confirm accuracy returns to 70%+ range

## Prevention

This issue is now prevented by:
- **Early normalization** in pipeline (line 163 of `daily_pipeline_db.py`)
- **Defensive normalization** in model (lines 443-457 of `adaptive_predictor.py`)
- **Double-check normalization** before predictions

## Files Modified

1. `/Users/gamblin/Documents/Github/NCAA-Prediction/daily_pipeline_db.py`
2. `/Users/gamblin/Documents/Github/NCAA-Prediction/model_training/adaptive_predictor.py`
3. `/Users/gamblin/Documents/Github/NCAA-Prediction/scripts/fix_database_team_names.py` (new)

## Technical Details

### Team Name Normalization Rules

The `normalize_team_name()` function in `data_collection/team_name_utils.py`:
1. URL decodes (e.g., %26 → &)
2. Strips whitespace
3. Checks ESPN alias map
4. Checks special cases (St. schools, abbreviations, etc.)
5. Removes common mascot suffixes (longest-first matching)
6. Returns normalized name

### Why This Matters

The Random Forest model uses `LabelEncoder` to convert team names to integers. When it sees an unknown team name, it uses the "smart encoding" fallback which assigns median values. This makes predictions essentially random because the model can't differentiate between different unknown teams.

**Example:**
- Training: "Indiana" = encoding 100 (knows their strength)
- Prediction: "Indiana Hoosiers" = unknown → encoding 180 (median fallback)
- Result: Model predicts for a "median team" instead of Indiana → wrong prediction

## Lessons Learned

1. **Normalize early, normalize often** - Don't wait until model input to normalize
2. **Data consistency is critical** - Small naming differences break ML models
3. **Defensive programming** - Always normalize, even if you think data is already clean
4. **Monitor data quality** - This issue took 6 days to notice (Nov 24-30)
5. **Test with production-like data** - Testing with clean data missed this issue
