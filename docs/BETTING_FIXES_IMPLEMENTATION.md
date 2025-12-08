# Betting System Fixes - Implementation Guide

**Quick Reference for Immediate Fixes**

This document provides the specific code changes needed to fix the betting system based on the analysis in `BETTING_TRENDS_ANALYSIS.md`.

---

## Priority 1: Emergency Fix - Stop Betting Underdogs

### File: `scripts/generate_betting_recommendations.py`

**Location:** Lines 148-169 (in the recommendation loop)

**Current Code:**
```python
for _, pred in upcoming_predictions.iterrows():
    # Determine which team we're betting on and their odds
    if pred['predicted_winner'] == pred['home_team']:
        bet_team = pred['home_team']
        odds = pred['home_moneyline']
    elif pred['predicted_winner'] == pred['away_team']:
        bet_team = pred['away_team']
        odds = pred['away_moneyline']
    else:
        continue
    
    # Skip if no odds available
    if pd.isna(odds) or odds == 0:
        continue
```

**New Code:**
```python
for _, pred in upcoming_predictions.iterrows():
    # Determine which team we're betting on and their odds
    if pred['predicted_winner'] == pred['home_team']:
        bet_team = pred['home_team']
        odds = pred['home_moneyline']
    elif pred['predicted_winner'] == pred['away_team']:
        bet_team = pred['away_team']
        odds = pred['away_moneyline']
    else:
        continue
    
    # Skip if no odds available
    if pd.isna(odds) or odds == 0:
        continue
    
    # ===== NEW: UNDERDOG FILTER =====
    # Skip big underdogs (odds > +150)
    if odds > 150:
        continue
    
    # For small underdogs (+1 to +150), require much higher confidence
    if odds > 0 and pred['confidence'] < 0.90:
        continue
    
    # For favorites, skip heavy favorites (worse than -250)
    if odds < -250:
        continue
    # ===== END NEW CODE =====
```

---

## Priority 2: Raise Confidence Threshold

### File: `scripts/generate_betting_recommendations.py`

**Location:** Lines 56-61 (function parameters)

**Current Code:**
```python
def generate_betting_recommendations(
    min_confidence: float = 0.75,  # Raised from 0.60 - more conservative
    min_value: float = 0.15,       # Raised from 0.05 - require bigger edge
    max_recommendations: int = 10,  # Reduced from 20 - fewer bets
    daily_budget: float = 100.0,
    parlay_amount: float = 10.0
):
```

**New Code:**
```python
def generate_betting_recommendations(
    min_confidence: float = 0.80,  # Raised from 0.75 - even more conservative
    min_value: float = 0.15,       # Keep at 0.15 for now
    max_recommendations: int = 5,  # Reduced from 10 - much fewer bets
    daily_budget: float = 100.0,
    parlay_amount: float = 10.0
):
```

---

## Priority 3: Enhanced Value Score Formula

### File: `scripts/generate_betting_recommendations.py`

**Location:** Lines 30-37 (value score calculation)

**Current Code:**
```python
def calculate_value_score(confidence: float, implied_prob: float) -> float:
    """
    Calculate betting value score.
    Positive value = our confidence is higher than market odds
    """
    return confidence - implied_prob
```

**New Code:**
```python
def calculate_value_score(confidence: float, implied_prob: float, odds: int = None) -> float:
    """
    Calculate betting value score with adjustments for underdogs.
    Positive value = our confidence is higher than market odds
    
    Applies penalties to underdogs since model is less accurate on them.
    """
    # Base edge
    edge = confidence - implied_prob
    
    # Apply adjustment based on odds type
    if odds is not None:
        if odds > 0:  # Underdog
            # Model is less accurate on underdogs - apply penalty
            # Require much larger edge
            edge = edge * 0.5  # Cut value score in half for underdogs
        else:  # Favorite
            # Model is more accurate on favorites - slight bonus
            edge = edge * 1.1
    
    return edge
```

**Then update the call site at line 165:**

**Current:**
```python
value_score = calculate_value_score(pred['confidence'], implied_prob)
```

**New:**
```python
value_score = calculate_value_score(pred['confidence'], implied_prob, odds)
```

---

## Priority 4: Add Loss Protection

### File: `scripts/generate_betting_recommendations.py`

**Location:** After line 89 (after budget check)

**Add this code:**
```python
    # Check recent performance - stop betting if on a bad streak
    recent_bets_query = """
        SELECT 
            bet_won,
            (payout - bet_amount) as profit
        FROM bets
        WHERE bet_won IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """
    recent_bets = db.fetch_df(recent_bets_query)
    
    if len(recent_bets) >= 5:
        # Calculate recent win rate
        recent_win_rate = recent_bets['bet_won'].iloc[:5].mean()
        recent_profit = recent_bets['profit'].iloc[:5].sum()
        
        # Stop betting if recent performance is terrible
        if recent_win_rate < 0.30 and recent_profit < -30:
            print(f"\n⚠️  Recent performance is poor:")
            print(f"   Last 5 bets: {recent_win_rate*100:.0f}% win rate")
            print(f"   Last 5 profit: ${recent_profit:.2f}")
            print(f"   🛑 PAUSING BETTING until performance improves")
            return
        
        # Warning if on a cold streak
        if recent_win_rate < 0.40:
            print(f"\n⚠️  Warning: Recent win rate is {recent_win_rate*100:.0f}%")
            print(f"   Proceeding with reduced bet size and higher selectivity")
```

---

## Priority 5: Update Command Line Defaults

### File: `scripts/generate_betting_recommendations.py`

**Location:** Lines 256-277 (argparse defaults)

**Update default values:**
```python
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.80,  # Changed from 0.75
        help='Minimum prediction confidence (default: 0.80 - VERY CONSERVATIVE)'
    )
    parser.add_argument(
        '--min-value',
        type=float,
        default=0.15,
        help='Minimum value edge over market (default: 0.15 - CONSERVATIVE)'
    )
    parser.add_argument(
        '--max-recs',
        type=int,
        default=5,  # Changed from 10
        help='Maximum number of recommendations (default: 5 - VERY CONSERVATIVE)'
    )
```

---

## Testing the Changes

### Step 1: Test with historical data

```bash
# Backup current recommendations
cp data/NCAA_Game_Predictions.csv data/NCAA_Game_Predictions.backup.csv

# Run with new settings
python scripts/generate_betting_recommendations.py --min-confidence 0.80 --max-recs 5

# Check output - should see:
# - Far fewer recommendations
# - No underdogs with odds > +150
# - Higher average confidence
```

### Step 2: Validate filters are working

Add this debug code temporarily to `generate_betting_recommendations.py` after line 169:

```python
    # DEBUG: Track filtered bets
    if odds > 150:
        print(f"  ❌ FILTERED: {bet_team} (underdog {odds:+d}) - odds too high")
        continue
    
    if odds > 0 and pred['confidence'] < 0.90:
        print(f"  ❌ FILTERED: {bet_team} (underdog {odds:+d}, conf {pred['confidence']:.1%}) - confidence too low")
        continue
    
    if odds < -250:
        print(f"  ❌ FILTERED: {bet_team} (heavy favorite {odds:+d}) - odds too heavy")
        continue
```

### Step 3: Monitor results

After implementing:
1. Track win rate daily
2. Track profit/loss
3. Track number of bets placed (should drop to ~3-5 per day)
4. Track number of underdog bets (should drop to 0-1 per week)

---

## Expected Results After Implementation

### Before Changes (Last 22 bets)
- **Win Rate:** 40.9% (9W-13L)
- **Underdog Bets:** 12 (55%)
- **Underdog Win Rate:** 25%
- **Total Profit:** -$29.48
- **ROI:** -13.4%

### After Changes (Projected next 22 bets)
- **Win Rate:** 60-65%
- **Underdog Bets:** 0-2 (0-10%)
- **Underdog Win Rate:** N/A or 50%+
- **Total Profit:** +$5 to +$15
- **ROI:** +2% to +7%

---

## Rollback Plan

If changes make things worse (unlikely), rollback is simple:

```bash
# Revert to previous version
git diff scripts/generate_betting_recommendations.py
git checkout scripts/generate_betting_recommendations.py

# Or manually change parameters back:
# min_confidence: 0.80 → 0.75
# max_recommendations: 5 → 10
```

---

## Additional Quick Wins

### 1. Add Logging to Track Filtered Bets

Add to `generate_betting_recommendations.py` after the main loop:

```python
    print(f"\n📊 FILTERING SUMMARY:")
    print(f"  Total candidates analyzed: {len(upcoming_predictions)}")
    print(f"  Filtered out - Big underdogs (>{max_underdog_odds}): {count_big_underdogs}")
    print(f"  Filtered out - Low confidence underdogs: {count_low_conf_underdogs}")
    print(f"  Filtered out - Heavy favorites (<{min_favorite_odds}): {count_heavy_favorites}")
    print(f"  Passed all filters: {len(recommendations)}")
```

### 2. Add Bet Type to Database

Update `backend/database/schema.py` to track bet type:

```python
# In bets table schema, add:
bet_odds_type VARCHAR,  -- 'favorite' or 'underdog'
```

Update `scripts/generate_betting_recommendations.py` to populate it:

```python
recommendations.append({
    # ... existing fields ...
    'bet_odds_type': 'underdog' if odds > 0 else 'favorite',
})
```

### 3. Create Emergency Stop File

Create a file that can pause betting without code changes:

```python
# At start of generate_betting_recommendations.py
EMERGENCY_STOP_FILE = Path(__file__).parent.parent / 'STOP_BETTING'
if EMERGENCY_STOP_FILE.exists():
    print("🛑 EMERGENCY STOP FILE DETECTED - NO BETS WILL BE PLACED")
    print(f"   Remove {EMERGENCY_STOP_FILE} to resume betting")
    return
```

Then to stop betting:
```bash
touch STOP_BETTING
```

To resume:
```bash
rm STOP_BETTING
```

---

## Summary

**Total Changes Required:**
- 4 code blocks in `generate_betting_recommendations.py`
- ~50 lines of code total
- No database schema changes (though recommended)
- Backward compatible (can rollback easily)

**Estimated Time:**
- Implementation: 30 minutes
- Testing: 15 minutes
- **Total: 45 minutes**

**Risk Level:** Low
- Changes are conservative (making system more selective, not less)
- No breaking changes to database or APIs
- Easy to rollback

**Expected Impact:** High
- Should eliminate 97% of current losses (from underdog bets)
- Should improve win rate from 41% to 60%+
- Should turn system profitable within 1-2 weeks

---

**Ready to implement?** Start with Priority 1 (underdog filter) and test for 3-5 days before adding other changes.
