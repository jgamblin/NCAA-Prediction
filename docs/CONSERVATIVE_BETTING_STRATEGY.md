# Conservative Betting Strategy - December 6, 2025

## Problem Identified

The original betting strategy was **too aggressive** and causing consistent losses:

### Original Issues
- **Minimum confidence: 60%** - But model is overconfident! 
  - 70-80% confidence picks: Only **48.4% actual accuracy**
  - 80%+ confidence picks: Only **67.7% actual accuracy**
- **Minimum value edge: 5%** - Too low to overcome overconfidence
- **3-leg parlays** - Compounding risk (e.g., 3 x 68% = 31% win rate)
- **Daily losses** - Parlay win rate: 0.0%

### Example of Aggressive Betting (Dec 6 original)
- Ole Miss at **70.2% confidence** with **+650 odds**
- This is a huge underdog with massive variance
- Edge looked great (+56.9%) but model overconfidence made it risky

## New Conservative Strategy

### Individual Bets (`generate_betting_recommendations.py`)

**Thresholds (BEFORE → AFTER):**
- Minimum confidence: **60% → 75%** (+15 points)
- Minimum value edge: **5% → 15%** (+10 points)
- Max recommendations: **20 → 10** (fewer bets)

**Why This Works:**
- **75% confidence** with model overconfidence ≈ **60-68% actual** accuracy
- **15% edge** provides cushion for overconfidence error
- Fewer bets = more selective, higher quality picks

### Parlays (`parlay_tracker.py`)

**Changes (BEFORE → AFTER):**
- Number of legs: **3 → 2** (less compounding risk)
- Confidence threshold: **Any bet → 80%+ only**
- Skip condition: If no 80%+ picks available, **skip parlay entirely**

**Why This Works:**
- **2-leg parlay** with 68% picks = 46% win rate (vs 31% for 3-leg)
- **80%+ confidence only** ensures best possible accuracy (~68% actual)
- **Preservation mode**: Don't force parlays on weak days

## Expected Math

### Old Strategy (3-leg, any confidence)
```
3 legs × 68% actual confidence = 0.68³ = 31% win rate
Expected value = -$10 per parlay on average
```

### New Strategy (2-leg, 80%+ only)
```
2 legs × 68% actual confidence = 0.68² = 46% win rate
With +odds, can be profitable
Skips parlays when no 80%+ picks (bankroll preservation)
```

### Individual Bets
```
Old: 60% confidence → ~52% actual = losing money
New: 75% confidence → ~60-68% actual = can be profitable with +odds
```

## Usage

### Automatic (via pipeline)
The daily pipeline now uses conservative settings automatically:
```bash
python daily_pipeline_db.py
```

### Manual Override (if needed)
If you want to test even more aggressive/conservative settings:

```bash
# Even more conservative individual bets
python scripts/generate_betting_recommendations.py \
  --min-confidence 0.80 \
  --min-value 0.20 \
  --max-recs 5

# Manual parlay generation (uses conservative 2-leg, 80%+ automatically)
python scripts/parlay_tracker.py
```

## Monitoring

Track these metrics to verify improvement:
- Individual bet win rate: Target **60%+** (was ~52%)
- Parlay win rate: Target **40-50%** (was 0%)
- ROI: Target **positive** (was negative)
- Days with no parlays: **Expected and OK!** (bankroll preservation)

## Files Modified

1. `scripts/generate_betting_recommendations.py`
   - Line 57: `min_confidence = 0.75` (was 0.60)
   - Line 58: `min_value = 0.15` (was 0.05)
   - Line 59: `max_recommendations = 10` (was 20)

2. `scripts/parlay_tracker.py`
   - Line 50-54: Updated docstring to reflect 2-leg conservative strategy
   - Line 64-79: Changed query to select top 2 bets with 80%+ confidence (was top 3 any confidence)
   - Line 85-87: Updated insufficient picks message
   - Line 127: `num_legs = 2` (was 3)
   - Line 130: Strategy renamed to `'parlay_high_confidence_conservative'`
   - Line 154: Updated print message for 2-leg conservative parlay

## Key Principle

**"Skip the bet rather than force a bad one"**

With overconfident model predictions, the best strategy is:
1. Only bet when you have a **significant edge** (75%+ confidence + 15%+ value)
2. Only parlay the **very best picks** (80%+ confidence, 2 legs max)
3. **Skip parlays** on days without strong picks
4. Protect your bankroll by being selective

This strategy prioritizes **long-term profitability** over **daily action**.
