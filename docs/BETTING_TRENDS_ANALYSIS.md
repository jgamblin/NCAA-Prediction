# Betting Trends Analysis & Improvement Recommendations
**Date**: December 8, 2025  
**Analysis Period**: 22 settled bets  
**Current Performance**: -$58.43 total profit (ROI: -13.4%)

---

## Executive Summary

The betting system is **significantly underperforming** despite the underlying prediction model showing solid accuracy (73%). After deep analysis, the root cause has been identified: **the value score formula is selecting too many underdog bets, and the model is severely overconfident on these picks**.

### Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| **Overall Win Rate** | 40.9% (9W-13L) | 🔴 Poor |
| **Total Profit/Loss** | -$29.48 on $220 wagered | 🔴 -13.4% ROI |
| **Model Prediction Accuracy** | 73% overall | ✅ Good |
| **Bet Selection Accuracy** | 41% | 🔴 Critical Gap |

---

## Critical Findings

### 1. **Underdog Betting is Hemorrhaging Money** 🚨

| Bet Type | Count | Win Rate | Profit | Avg Confidence | Avg Value Score |
|----------|-------|----------|--------|----------------|-----------------|
| **Underdog (+odds)** | 12 (55%) | 25.0% 🔴 | **-$28.60** | 71.9% | 33.9% |
| **Favorite (-odds)** | 10 (45%) | 60.0% ✅ | -$0.88 | 85.7% | 25.2% |

**The Problem:**
- **55% of all bets are on underdogs**, despite only winning 25% of the time
- Underdogs account for **$28.60 of the $29.48 total loss** (97% of losses!)
- Model confidence of 71.9% on underdog bets is wildly inflated vs 25% actual performance
- **Confidence gap on underdogs: 47 percentage points!**

**Why This Happens:**
The value score formula `confidence - implied_probability` naturally favors underdogs because:
- Underdogs have better odds (e.g., +200) → lower implied probability (33%)
- Model predicts 70% confidence → value score = +37% (looks great!)
- But model is **overconfident on underdogs**, making these "value bets" actually terrible bets

### 2. **Favorites are Performing Much Better**

- **60% win rate** on favorite bets vs 25% on underdogs
- Still losing money overall (-$0.88) due to juice/vigorish
- **15 point confidence gap** (85.7% predicted vs 60% actual) - still overconfident but manageable

### 3. **Model Calibration by Confidence Level**

Comparing predicted confidence to actual betting results:

| Confidence Range | Bets | Actual Win Rate | Expected Win Rate | Gap |
|------------------|------|-----------------|-------------------|-----|
| 60-70% | 6 | 33.3% | 64.4% | -31.1 🔴 |
| 70-75% | 3 | 66.7% | 74.1% | -7.4 ✅ |
| 75-80% | 2 | 0% | 76.5% | -76.5 🔴 |
| 80-85% | 3 | 66.7% | 81.5% | -14.8 ⚠️ |
| 85-90% | 5 | 40.0% | 88.0% | -48.0 🔴 |
| 90%+ | 3 | 33.3% | 91.5% | -58.2 🔴 |

**Critical Insight:** The highest confidence bets (85%+) are performing the **worst**, winning only 37.5% of the time. This is backwards from expectations!

### 4. **Overall Model vs Betting Performance** 

For context, here's how the prediction model performs on all games (not just bets):

| Confidence Range | Total Predictions | Accuracy |
|------------------|-------------------|----------|
| 75-80% | 126 | 74.6% ✅ |
| 80-85% | 461 | 75.5% ✅ |
| 85-90% | 107 | 88.8% ✅ |
| 90%+ | 6 | 50.0% (tiny sample) |

**The model itself is well-calibrated!** The problem is the **betting selection process** is choosing the wrong subset of predictions to bet on.

---

## Root Cause Analysis

### Problem #1: Value Score Biases Toward Underdogs

**Current Formula:**
```python
value_score = confidence - implied_probability
```

**Example of the Bias:**
- **Underdog pick**: 70% confidence, +200 odds (33% implied) → value_score = +37%
- **Favorite pick**: 85% confidence, -200 odds (67% implied) → value_score = +18%

The system selects the underdog because it has a higher value score, even though:
1. The favorite has higher confidence (85% vs 70%)
2. The favorite's calibration is better (closer to reality)
3. Favorites are winning 60% vs underdogs at 25%

### Problem #2: No Odds-Based Filters

The current system has:
- ✅ Minimum confidence threshold (75%)
- ✅ Minimum value threshold (15%)
- ❌ **No filter for underdog odds**
- ❌ **No differentiated thresholds by odds type**

### Problem #3: Small Sample Size with High Variance

- Only 22 settled bets total
- High-confidence buckets have 2-6 bets each
- Results could improve with more data, but trend is clearly negative

---

## Immediate Recommendations

### 🔴 PRIORITY 1: Stop Betting Underdogs

**Action:** Add a maximum odds filter to exclude or severely restrict underdog bets.

**Implementation Options:**

**Option A - No Underdogs (Most Conservative)**
```python
# In generate_betting_recommendations.py
if odds > 0:  # Positive odds = underdog
    continue  # Skip this bet
```

**Option B - Only Small Underdogs**
```python
# Only bet underdogs with odds +100 to +150 (near pick'em games)
if odds > 150:  # Skip big underdogs
    continue
if odds > 0:  # Raise confidence requirement for underdogs
    if confidence < 0.85:
        continue
```

**Expected Impact:** Would have avoided $28.60 of losses (97% of total loss)

### 🟡 PRIORITY 2: Adjust Value Score Formula

**Problem:** Current formula doesn't account for model's differential performance on favorites vs underdogs.

**Proposed New Formula:**
```python
def calculate_value_score_v2(confidence, moneyline):
    """
    Enhanced value score that penalizes underdogs and rewards favorites.
    """
    implied_prob = moneyline_to_probability(moneyline)
    
    # Base edge
    edge = confidence - implied_prob
    
    # Apply penalty/bonus based on odds
    if moneyline > 0:  # Underdog
        # Require much larger edge for underdogs
        edge_required = 0.25  # 25% edge minimum
        if edge < edge_required:
            return None  # Don't bet
        # Apply penalty factor to reduce underdog appeal
        edge = edge * 0.5  # Cut value score in half
    else:  # Favorite
        # Reward favorites slightly
        edge = edge * 1.2
    
    return edge
```

### 🟡 PRIORITY 3: Raise Thresholds

The "conservative" strategy from December 6th wasn't conservative enough.

**Current Settings:**
- Min confidence: 75%
- Min value: 15%
- Max bets: 10

**Recommended New Settings:**

```python
# For favorites
min_confidence_favorites = 0.80  # Up from 0.75
min_value_favorites = 0.10  # Down from 0.15 (formula change compensates)
max_odds_favorites = -110  # New: Don't bet heavy favorites

# For underdogs (if allowed at all)
min_confidence_underdogs = 0.90  # Much higher bar
min_value_underdogs = 0.30  # Massive edge required
max_odds_underdogs = 150  # Only near pick'em games
```

### 🟢 PRIORITY 4: Improve Model Calibration

The model's calibration on betting selections needs work. Recommended approaches:

**A. Separate Calibration by Game Type**
- Track accuracy for favorites vs underdogs
- Track accuracy by conference (Power 5 vs mid-major)
- Track accuracy by score margin (close games vs blowouts)

**B. Implement Confidence Adjustment**
```python
# Adjust confidence based on historical calibration
def adjust_confidence(confidence, is_underdog, conference_strength):
    """
    Adjust model confidence based on known calibration issues.
    """
    if is_underdog:
        # Reduce confidence on underdogs by 20 points
        confidence = confidence * 0.75
    
    if conference_strength == 'mid_major':
        # More uncertainty in mid-major games
        confidence = confidence * 0.90
    
    return min(confidence, 0.98)  # Cap at 98%
```

**C. Platt Scaling/Isotonic Regression**
- Use historical prediction results to recalibrate probabilities
- Particularly important for high-confidence predictions (85%+)

### 🟢 PRIORITY 5: Add Bankroll Protection

**Implement Loss Limits:**
```python
# In daily_pipeline_db.py or generate_betting_recommendations.py
MAX_DAILY_LOSS = 30.0  # Stop betting after losing $30 in a day
MAX_WEEKLY_LOSS = 100.0  # Stop betting after losing $100 in a week

if total_loss_today >= MAX_DAILY_LOSS:
    print("⛔ Loss limit reached - no more bets today")
    return
```

**Implement Win Streak Scaling:**
```python
# Scale bet size based on recent performance
if last_5_bets_win_rate >= 0.80:
    bet_size = 15.0  # Increase bet size on hot streak
elif last_5_bets_win_rate <= 0.20:
    bet_size = 5.0   # Reduce bet size on cold streak
else:
    bet_size = 10.0  # Standard bet size
```

---

## Long-Term Recommendations

### 1. **Separate Betting Strategies**

Instead of one unified strategy, implement multiple strategies:

**Strategy A: "Safe Favorites"**
- Only bet favorites with odds -110 to -200
- Minimum 85% confidence
- Target: 65-70% win rate, small but steady profit

**Strategy B: "Value Underdogs"** (if calibration improves)
- Only bet underdogs after model calibration is fixed
- Require 30%+ edge
- Target: 45-50% win rate, higher profit per win

**Strategy C: "High Conviction"**
- Only bet on 90%+ confidence picks
- Mix of favorites and underdogs allowed
- Target: 80%+ win rate

### 2. **Track Performance by Game Context**

Add these features to predictions and track accuracy:
- **Home/Away/Neutral site**
- **Conference strength** (Power 5 vs mid-major)
- **Tournament vs regular season**
- **Back-to-back games** (fatigue factor)
- **Rest days**
- **Rivalry games**

Only bet on game contexts where the model has proven accuracy.

### 3. **Implement A/B Testing**

Split daily bets between:
- 50% using current strategy (as control)
- 50% using new strategy (as test)

Track results separately to validate improvements.

### 4. **Add Ensemble Confidence**

Currently using a single model. Consider:
- Train multiple models with different approaches
- Only bet when all models agree (>80% confidence)
- Use ensemble variance as an uncertainty measure

### 5. **Market Timing**

- Track line movements (opening lines vs closing lines)
- Bet only when line moves in our favor
- Avoid betting right when lines open (highest uncertainty)

---

## Projected Impact of Recommendations

### Conservative Estimate (Implementing Priority 1-3)

**Assuming we eliminate underdog bets and raise favorite thresholds:**

| Metric | Current | Projected | Change |
|--------|---------|-----------|--------|
| Bets per week | ~7-8 | ~3-4 | -50% |
| Win rate | 41% | 60-65% | +20-24 pts |
| ROI | -13.4% | +5-10% | +18-23 pts |
| Weekly P&L | -$15 | +$2-5 | +$17-20 |

### Optimistic Estimate (All recommendations + model calibration)

| Metric | Current | Projected | Change |
|--------|---------|-----------|--------|
| Bets per week | ~7-8 | ~5-6 | -25% |
| Win rate | 41% | 68-72% | +27-31 pts |
| ROI | -13.4% | +12-18% | +25-31 pts |
| Weekly P&L | -$15 | +$8-12 | +$23-27 |

---

## Implementation Plan

### Phase 1: Emergency Fixes (Implement ASAP)
- [ ] Add underdog betting filter (no bets on odds > +150)
- [ ] Raise minimum confidence to 80% for all bets
- [ ] Add maximum odds filter for favorites (no worse than -250)
- [ ] Update `generate_betting_recommendations.py`

### Phase 2: Formula Improvements (This week)
- [ ] Implement new value score formula with odds-based adjustments
- [ ] Add confidence adjustment factors
- [ ] Create separate thresholds for favorites vs underdogs
- [ ] Update `betting_tracker.py` to track by odds category

### Phase 3: Calibration Analysis (Next week)
- [ ] Analyze prediction accuracy by game context
- [ ] Implement Platt scaling or isotonic regression
- [ ] Create calibration curves for different game types
- [ ] Add calibration metrics to monitoring dashboard

### Phase 4: Advanced Features (2+ weeks)
- [ ] Implement separate betting strategies (Safe Favorites, Value Picks, High Conviction)
- [ ] Add ensemble modeling
- [ ] Track line movements
- [ ] Implement A/B testing framework

---

## Monitoring & Success Metrics

### Daily Monitoring
- [ ] Win rate by bet type (favorite vs underdog)
- [ ] Profit/loss tracking
- [ ] Confidence calibration (predicted vs actual)
- [ ] Number of bets skipped due to filters

### Weekly Review
- [ ] ROI trend
- [ ] Win rate by confidence bucket
- [ ] Best/worst performing game types
- [ ] Calibration curve updates

### Monthly Goals
- **Month 1**: Achieve break-even (0% ROI)
- **Month 2**: Achieve 5%+ ROI
- **Month 3**: Achieve 10%+ ROI with 60%+ win rate

---

## Conclusion

The betting system is underperforming not because the prediction model is bad (it's actually quite good at 73% accuracy), but because the **bet selection process is fundamentally flawed**. The value score formula is systematically choosing the wrong games to bet on, particularly underdogs where the model is severely overconfident.

**The good news:** This is fixable! By implementing the recommendations above—especially eliminating underdog bets and raising thresholds—we can likely turn this system profitable within 2-4 weeks.

**Key Principle:** When in doubt, **don't bet**. It's better to skip questionable opportunities than to force bets on games where the edge is unclear.

---

## Files to Modify

### High Priority
1. **`scripts/generate_betting_recommendations.py`**
   - Add underdog filters (lines 160-162)
   - Update value score formula (lines 105-140)
   - Raise thresholds (lines 57-59)

2. **`game_prediction/betting_tracker.py`**
   - Update value score calculation (lines 105-140)
   - Add odds category tracking

### Medium Priority
3. **`model_training/adaptive_predictor.py`** or equivalent
   - Add confidence calibration
   - Implement Platt scaling

4. **`backend/repositories/betting_repository.py`**
   - Add methods for tracking by odds category
   - Add calibration metrics

### Low Priority
5. Create new files:
   - `scripts/analyze_betting_calibration.py` - Deep calibration analysis
   - `scripts/betting_strategy_ab_test.py` - A/B testing framework
   - `docs/BETTING_STRATEGY_COMPARISON.md` - Strategy performance tracking

---

**Generated:** December 8, 2025  
**Author:** Automated Analysis  
**Review Status:** Ready for review and implementation
