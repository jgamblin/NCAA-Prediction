# Root Cause Analysis: Why is Alabama A&M Predicted to Beat Indiana?

## Summary
The model predicts Alabama A&M will beat Indiana with 88.8% confidence, while sports books have Indiana favored by 27 points. This is **completely wrong** and caused by a critical data quality issue: **team name inconsistency**.

## Root Cause

### The Problem
ESPN changed their team naming convention in recent data:
- **Historical data (2020-2025)**: "Indiana", "Alabama A&M"
- **Current season (2025-26)**: "Indiana Hoosiers", "Alabama A&M Bulldogs"

### How This Breaks the Model

1. **Training Phase**: Model learns from 29,415 historical games
   - "Indiana" appears in 100s of games (Big Ten team, high quality)
   - "Alabama A&M" appears in ~10 games (SWAC team, lower division)

2. **Prediction Phase**: Model encounters "Indiana Hoosiers" vs "Alabama A&M Bulldogs"
   - "Indiana Hoosiers" → **NOT FOUND** in training data → Encoded as -1
   - "Alabama A&M Bulldogs" → **NOT FOUND** in training data → Encoded as -1
   - Random Forest sees two "unknown" teams (-1, -1) and makes nonsensical prediction

3. **Why Alabama A&M?**: The model essentially guesses randomly when both teams are unknown, and happened to predict the away team (Alabama A&M) with high confidence due to how the unknown team encoding interacts with the decision trees.

## Evidence

```bash
# Check training data
$ grep -i "Indiana Hoosiers" data/Completed_Games.csv
# Returns: 0 matches

$ grep -i "^Indiana," data/Completed_Games.csv | wc -l
# Returns: 100+ matches

$ grep -i "Alabama A&M Bulldogs" data/Completed_Games.csv  
# Returns: 1 match (Nov 3, 2025)

$ grep -i "Alabama A&M," data/Completed_Games.csv | wc -l
# Returns: 10 matches
```

## Impact Analysis

This affects **many teams** that ESPN added mascot names to:
- Indiana → Indiana Hoosiers
- Alabama A&M → Alabama A&M Bulldogs  
- Likely dozens more teams across all conferences

Any game with these teams will have unreliable predictions.

## Solutions

### Option 1: Team Name Normalization (RECOMMENDED - Quick Fix)
**Pros**: Simple, can implement today
**Cons**: Maintenance burden, may break again with future ESPN changes

**Implementation**:
1. Create a team name mapping function
2. Strip common suffixes ("Hoosiers", "Bulldogs", "Tigers", etc.)
3. Apply normalization before encoding

```python
def normalize_team_name(name):
    """Normalize team names by removing mascot suffixes."""
    # Remove common mascots
    mascots = ['Hoosiers', 'Bulldogs', 'Wildcats', 'Tigers', 'Eagles', 
               'Bears', 'Panthers', 'Lions', 'Cougars', 'Rams', etc.]
    
    for mascot in mascots:
        if name.endswith(f' {mascot}'):
            return name.replace(f' {mascot}', '')
    return name
```

### Option 2: Use Team IDs from ESPN (RECOMMENDED - Long Term)
**Pros**: Permanent solution, immune to name changes  
**Cons**: Requires more extensive changes, need to capture team IDs from ESPN

**Implementation**:
1. Modify `espn_scraper.py` to extract team IDs from competitor data
2. Add `home_team_id` and `away_team_id` columns to all CSVs
3. Use team IDs for model training instead of team names
4. Keep team names for display purposes only

ESPN provides team IDs in their API responses:
```json
{
  "competitors": [
    {
      "team": {
        "id": "84",      // Indiana's team ID
        "uid": "s:40~l:41~t:84",
        "displayName": "Indiana Hoosiers"
      }
    }
  ]
}
```

### Option 3: Hybrid Approach (BEST)
1. **Immediate**: Implement team name normalization (Option 1)
2. **Next iteration**: Add team ID support (Option 2)
3. **Validation**: Use team IDs as primary key, names as fallback

## Recommended Action Plan

### Phase 1: Emergency Fix (Today)
1. Create `normalize_team_name()` function in `simple_predictor.py`
2. Apply to both training and prediction data before encoding
3. Re-run predictions for today's games
4. Commit and push fix

### Phase 2: Proper Solution (This Week)
1. Modify `espn_scraper.py` to capture team IDs from `competitors[i]['team']['id']`
2. Add team ID columns to CSV schema
3. Update `simple_predictor.py` to use team IDs for encoding
4. Create team ID → name mapping for display
5. Re-scrape historical data to backfill team IDs

### Phase 3: Validation (Ongoing)
1. Add data quality checks to detect team name mismatches
2. Monitor for new team name variations
3. Alert if unknown teams detected in predictions

## Testing the Fix

After implementing Option 1 (normalization):
```python
# Test that Indiana variants map correctly
assert normalize_team_name("Indiana Hoosiers") == "Indiana"
assert normalize_team_name("Alabama A&M Bulldogs") == "Alabama A&M"

# Verify both appear in training data
assert "Indiana" in completed_games['home_team'].values
assert "Alabama A&M" in completed_games['home_team'].values
```

## Expected Outcome

After fix, the model should:
- Recognize "Indiana Hoosiers" as "Indiana" (major conference team)
- Recognize "Alabama A&M Bulldogs" as "Alabama A&M" (SWAC team)
- Predict Indiana to win by large margin (matching betting lines)
- Show realistic confidence levels based on historical performance

Indiana should be heavily favored (~95%+ confidence) based on:
- Conference strength (Big Ten vs SWAC)
- Historical performance
- Home court advantage
- Talent disparity

---

**Priority**: CRITICAL  
**Effort**: Option 1 = 1-2 hours, Option 2 = 4-6 hours  
**Impact**: Fixes predictions for dozens of teams
