# Prediction Explanations

**Added**: December 5, 2025  
**Status**: ✅ Complete (Backend) | ⏳ Pending (Frontend)

---

## Overview

Added natural language explanations for every prediction without requiring LLM calls. Each game now includes a human-readable explanation of why the model picked that winner.

---

## Example Explanations

### High Confidence
```
Davidson is strongly favored: they are significantly stronger overall, 
they have a vastly superior defense, and they have a major offensive 
advantage.
```

### Medium Confidence
```
Cal State Bakersfield is confidently favored: they are significantly 
stronger overall, they have a vastly superior defense, and they have 
a major offensive advantage.
```

### Low Confidence
```
Wake Forest is narrowly favored: they are dominant at their home venue, 
they have a slight offensive edge, and they are slightly stronger.
```

---

## How It Works

### 1. Rule-Based System (No LLM!)
- Uses model's feature importance + actual feature values
- Calculates contribution of each feature
- Selects top 3 contributing factors
- Generates natural language phrases

### 2. Grammar & Style
- ✅ Team name mentioned **only once** at start
- ✅ Uses "they" pronouns consistently
- ✅ Adjusts confidence language:
  - **85%+**: "strongly favored"
  - **75-85%**: "confidently favored"  
  - **65-75%**: "favored"
  - **<65%**: "narrowly favored"

### 3. Feature Templates
Each feature has natural language templates:

**Offensive/Defensive Rating**:
- Strong: "have a major offensive advantage"
- Moderate: "have a notably better offense"
- Weak: "have a slight offensive edge"

**Venue Performance**:
- Strong: "dominant at their home venue"
- Moderate: "perform well at home"
- Weak: "have a slight home court advantage"

**Overall Strength**:
- Strong: "significantly stronger overall"
- Moderate: "have the edge in overall team strength"
- Weak: "slightly stronger"

**Momentum**:
- Strong: "playing much better lately"
- Moderate: "have momentum on their side"
- Weak: "playing slightly better recently"

---

## Technical Implementation

### Backend (`model_training/prediction_explainer.py`)

**PredictionExplainer class**:
```python
explainer = PredictionExplainer(feature_importance_df)

explanation = explainer.explain_prediction(
    home_team="Duke",
    away_team="UNC",
    predicted_winner="Duke",
    confidence=0.82,
    features={
        'off_rating_diff': 0.18,
        'def_rating_diff': 0.05,
        'power_rating_diff': 0.12,
        'venue_wpct_diff': 0.25,
    }
)
```

### Integration (`model_training/adaptive_predictor.py`)

Automatically added to `predict()` method:
- Loads feature importance from last training
- Extracts feature values for each game
- Generates explanation for each prediction
- Adds 'explanation' column to results DataFrame

### Data Flow

```
1. Model trains → Feature importance saved to CSV
2. predict() called → Loads feature importance
3. For each game:
   - Extract feature values (X_upcoming)
   - Calculate feature contributions
   - Select top 3 factors
   - Generate natural language phrase
4. Add 'explanation' column to predictions
5. Return predictions with explanations
```

---

## Testing

**Test Script**: `scripts/test_explanations.py`

```bash
python scripts/test_explanations.py
```

Shows 10 example predictions with:
- Away team @ Home team
- Predicted winner & confidence
- 💡 Natural language explanation
- ✅/❌ Actual result comparison

---

## Frontend Integration (Next Step)

### 1. Update API Response

The `explanation` column is already included in predictions, so API should automatically include it:

```json
{
  "game_id": "...",
  "home_team": "Davidson",
  "away_team": "Citadel",
  "predicted_winner": "Davidson",
  "confidence": 0.85,
  "explanation": "Davidson is strongly favored: they are significantly stronger overall, they have a vastly superior defense, and they have a major offensive advantage."
}
```

### 2. Display in UI

**Option A: Tooltip** (Hover to see explanation)
```jsx
<div className="game-card">
  <div className="prediction">
    Davidson to win (85%)
    <InfoIcon className="ml-2" data-tooltip={game.explanation} />
  </div>
</div>
```

**Option B: Expand/Collapse**
```jsx
<div className="game-card">
  <div className="prediction">Davidson to win (85%)</div>
  <button onClick={() => setExpanded(!expanded)}>
    Why?
  </button>
  {expanded && (
    <p className="explanation">{game.explanation}</p>
  )}
</div>
```

**Option C: Always Visible** (Recommended for high-value predictions)
```jsx
<div className="game-card">
  <div className="prediction">
    <strong>Davidson</strong> to win (85%)
  </div>
  <p className="text-sm text-gray-600 mt-2">
    💡 {game.explanation}
  </p>
</div>
```

### 3. Styling Suggestions

```css
.explanation {
  font-size: 0.875rem;
  color: #6b7280; /* gray-600 */
  font-style: italic;
  padding: 0.5rem;
  background: #f9fafb; /* gray-50 */
  border-left: 3px solid #3b82f6; /* blue-500 */
  border-radius: 0.25rem;
  margin-top: 0.5rem;
}
```

---

## Benefits

### For Users
- ✅ **Understand why** the model picked a winner
- ✅ **Trust the prediction** more with reasoning
- ✅ **Learn patterns** (defense matters, home court, etc.)
- ✅ **Make better bets** by understanding confidence factors

### For Development
- ✅ **No LLM costs** - completely rule-based
- ✅ **Fast** - generates instantly with predictions
- ✅ **Debuggable** - can trace back to exact features
- ✅ **Maintainable** - easy to add new feature templates

---

## Limitations & Future Improvements

### Current Limitations
1. **Top 3 factors only** - doesn't explain all contributing factors
2. **Generic templates** - same phrases for similar situations
3. **No context** - doesn't mention injuries, recent news, etc.

### Potential Improvements
1. **Add more feature templates**:
   - Rest days advantage
   - Recent hot/cold streaks
   - Conference strength
   - Rivalry game indicators

2. **Contextual adjustments**:
   - "This is a rivalry game, adding uncertainty"
   - "Both teams on 3+ game winning streaks"
   - "Home team hasn't lost at home this season"

3. **Confidence qualifiers**:
   - Low data warning: "Limited historical data available"
   - Early season: "Early in season, less data to analyze"
   - Tournament: "Tournament games are especially unpredictable"

4. **Interactive mode**:
   - Click to see all contributing factors (not just top 3)
   - Visualize feature importance for this specific game
   - Compare to other similar matchups

---

## Files Modified

### New Files
- `model_training/prediction_explainer.py` - Core explanation engine
- `scripts/test_explanations.py` - Test/demo script
- `docs/PREDICTION_EXPLANATIONS.md` - This document

### Modified Files
- `model_training/adaptive_predictor.py` - Integrated explanation generation

---

## Example Use Cases

### Use Case 1: Betting Decision
**User sees**: "Duke is strongly favored: they have a major offensive advantage, they are dominant at their home venue, and they have the edge in overall team strength."

**User thinks**: "Strong offensive advantage + home dominance + overall strength = very solid pick. The 85% confidence makes sense."

### Use Case 2: Upset Alert
**User sees**: "Kansas is narrowly favored: they have a slight offensive edge."

**User thinks**: "Only one minor advantage? 60% confidence seems about right. This could easily go either way. Maybe skip betting this one."

### Use Case 3: Learning
**User notices**: Most high-confidence picks mention "vastly superior defense" and "major offensive advantage"

**User learns**: "Defense and offense ratings are the most important factors for strong predictions. Home court is secondary."

---

## Deployment Checklist

### Backend ✅ (Complete)
- [x] PredictionExplainer class created
- [x] Integrated into AdaptivePredictor.predict()
- [x] Feature importance templates defined
- [x] Grammar/pronoun handling working
- [x] Test script created
- [x] Documentation written

### Frontend ⏳ (Pending)
- [ ] Verify 'explanation' column in API response
- [ ] Add explanation display to game cards
- [ ] Style explanation text appropriately
- [ ] Test on various screen sizes
- [ ] Add tooltip/expand option for long explanations
- [ ] Consider icon (💡 or ℹ️) to indicate explanation available

### Testing ⏳ (Pending)
- [ ] Test with upcoming games (not completed games)
- [ ] Verify explanations make sense for edge cases
- [ ] Check performance impact (should be minimal)
- [ ] User feedback on explanation clarity

---

## Summary

✅ **Prediction explanations are now live in the backend!**

Every prediction automatically includes a natural language explanation based on the model's feature importance and actual feature values. The system:

- Uses NO LLM calls (completely rule-based)
- Generates explanations instantly
- Mentions team name only once
- Uses consistent "they" pronouns  
- Adjusts language based on confidence
- Highlights top 3 contributing factors

**Next step**: Display explanations in the frontend UI so users can see WHY the model picked each winner.

---

**Questions?** See `scripts/test_explanations.py` for live examples or review `model_training/prediction_explainer.py` for implementation details.
