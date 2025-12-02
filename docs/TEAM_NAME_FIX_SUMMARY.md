# Team Name Normalization - Comprehensive Fix

## Problem Statement
ESPN API returns team names with inconsistent formatting (with/without mascots, abbreviations, etc.), causing teams to appear as separate entities in our database. This resulted in:
- Duplicate team records (e.g., "UConn", "UConn Huskies", "Connecticut")
- Teams appearing to have insufficient historical data for predictions
- Only ~12% prediction coverage for games

## Solution Implemented

### 1. Enhanced Mascot Normalization (`team_name_utils.py`)
**Added missing mascots:**
- Big, Black, Buccaneers, Builders
- 49ers, Fighting, Sharks, Skyhawks

**Fixed special cases:**
- Connecticut → UConn (170 games)
- Army Black → Army
- Campbell Fighting → Campbell
- Charlotte 49ers → Charlotte
- Cornell Big → Cornell

### 2. Comprehensive Database Fix (`scripts/fix_team_names_comprehensive.py`)
**Created automated script that:**
1. Analyzes all team name variations in database
2. Identifies duplicates (same base name with different suffixes)
3. Maps aliases to canonical names (ESPN → Database)
4. Re-normalizes ALL games from season start
5. Consolidates duplicate team records

**Results:**
- **474 aliases** mapped to canonical names
- **427 duplicate teams** consolidated
- **540 team names** normalized in games table
- Created `data/espn_alias_map.json` for future lookups

### 3. Major Teams Fixed
| ESPN Name | Variations | Canonical | Total Games |
|-----------|-----------|-----------|-------------|
| Connecticut | UConn, UConn Huskies, Connecticut | UConn | 177 |
| Mississippi State | Miss St, Mississippi State, Mississippi State Bulldogs | Miss St | 177 |
| Houston | Houston, Houston Cougars | Houston | 192 |
| Duke | Duke, Duke Blue Devils | Duke | 182 |
| Kansas | Kansas, Kansas Jayhawks | Kansas | 182 |
| Purdue | Purdue, Purdue Boilermakers | Purdue | 182 |

## Current Status

### ✅ Fixed
- Team name normalization from ESPN aliases
- Historical game data properly consolidated
- UConn now recognized correctly (was "Connecticut")
- Major programs have proper historical records

### 🔄 In Progress  
- Prediction coverage improvement
  - Before: 7/58 games (12%)
  - Now: 35/86 games (41%)
  - Target: 100% with confidence multipliers

### 🎯 Next Steps
1. **Verify ESPN scraper fetches ALL scheduled games**
   - Currently only getting 57 games when database has 86
   - May need to expand date range or use different API endpoint

2. **Ensure predictor uses skip_low_data=False**
   - Default is set correctly
   - Need to verify it's predicting ALL games with 0.75x confidence for low-data teams

3. **Test full pipeline end-to-end**
   - Run daily_pipeline_db.py
   - Export to JSON
   - Verify frontend shows all games with predictions

## Files Modified
- `data_collection/team_name_utils.py` - Enhanced normalization
- `data_collection/espn_scraper.py` - Fixed imports
- `model_training/adaptive_predictor.py` - Changed skip_low_data default to False
- `daily_pipeline_db.py` - Updated to use new prediction logic
- `scripts/fix_team_names_comprehensive.py` - NEW comprehensive fix script
- `data/espn_alias_map.json` - NEW alias mapping file

## Usage

### One-time fix (already run):
```bash
python3 scripts/fix_team_names_comprehensive.py
```

### Daily pipeline (with fixes applied):
```bash
python3 daily_pipeline_db.py
python3 scripts/export_to_json.py
```

### Verify improvements:
```python
import duckdb
conn = duckdb.connect('data/ncaa_predictions.duckdb')

# Check coverage
result = conn.execute('''
    SELECT 
        COUNT(*) as total_games,
        COUNT(CASE WHEN p.game_id IS NOT NULL THEN 1 END) as with_predictions
    FROM games g
    LEFT JOIN predictions p ON g.game_id = p.game_id
    WHERE g.date = DATE('now') AND g.game_status = 'Scheduled'
''').fetchone()

print(f'Coverage: {result[1]}/{result[0]} ({result[1]/result[0]*100:.1f}%)')
```

## Impact
- **Robust matching:** Teams properly matched from season start
- **No daily fixes needed:** Automated normalization handles new aliases
- **Better predictions:** Teams have full historical data
- **Maintainable:** Centralized alias map can be updated as needed
