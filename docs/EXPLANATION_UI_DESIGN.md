# Explanation UI Design Proposal

**Date**: December 5, 2025  
**Recommendation**: ✅ **Option 2: Expandable with Icon** (Best balance)

---

## Design Options

### Option 1: Always Visible (Simple)
**Pros**: Immediate visibility, no interaction needed  
**Cons**: Can make cards tall/cluttered, takes up space

```
┌─────────────────────────────────────────────┐
│ Virginia Tech @ Duke                         │
│ Predicted: Duke    Confidence: 85%          │
│ 💡 Duke is strongly favored: they have a   │
│    major offensive advantage, they are      │
│    dominant at their home venue, and they   │
│    have the edge in overall team strength.  │
│                              ✓ Predicted    │
└─────────────────────────────────────────────┘
```

**Best for**: Few games per page, high-value predictions

---

### Option 2: Expandable with Icon ⭐ **RECOMMENDED**
**Pros**: Clean default view, user controls detail level, clear interaction  
**Cons**: Requires one click to see explanation

```
┌─────────────────────────────────────────────┐
│ Virginia Tech @ Duke                         │
│ Predicted: Duke    Confidence: 85%          │
│ [💡 Why?]                    ✓ Predicted    │
└─────────────────────────────────────────────┘

After click:
┌─────────────────────────────────────────────┐
│ Virginia Tech @ Duke                         │
│ Predicted: Duke    Confidence: 85%          │
│ [💡 Hide explanation]        ✓ Predicted    │
│ ┌─────────────────────────────────────────┐ │
│ │ Duke is strongly favored: they have a   │ │
│ │ major offensive advantage, they are     │ │
│ │ dominant at their home venue, and they  │ │
│ │ have the edge in overall team strength. │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**Best for**: Most scenarios - clean, scalable, user-controlled

---

### Option 3: Tooltip on Hover
**Pros**: Minimal UI, quick access  
**Cons**: Doesn't work on mobile, can be accidentally triggered, hard to read long text

```
┌─────────────────────────────────────────────┐
│ Virginia Tech @ Duke                         │
│ Predicted: Duke    Confidence: 85% [ℹ]     │
│                              ✓ Predicted    │
└─────────────────────────────────────────────┘
         ↓ (hover on ℹ)
    ┌─────────────────────────────┐
    │ Duke is strongly favored:   │
    │ they have a major offensive │
    │ advantage, they are         │
    │ dominant at their home...   │
    └─────────────────────────────┘
```

**Best for**: Desktop-only, supplementary info

---

### Option 4: Separate "Insights" Tab
**Pros**: Doesn't clutter main view, can show detailed analysis  
**Cons**: Separated from predictions, extra navigation

```
Predictions Tab          Insights Tab
┌──────────────┐        ┌──────────────┐
│ Game cards   │        │ Explanations │
│ (no expl.)   │        │ with details │
└──────────────┘        └──────────────┘
```

**Best for**: Advanced users, detailed analysis mode

---

## ✅ Recommended Implementation: Option 2

### Visual Design

**Collapsed State** (Default):
```jsx
┌──────────────────────────────────────────────────────┐
│  Virginia Tech @ Duke                     2024-12-05 │
│                                                       │
│  Predicted: Duke        Confidence: 85%              │
│  💡 Why Duke?                           ✓ Predicted  │
└──────────────────────────────────────────────────────┘
```

**Expanded State**:
```jsx
┌──────────────────────────────────────────────────────┐
│  Virginia Tech @ Duke                     2024-12-05 │
│                                                       │
│  Predicted: Duke        Confidence: 85%              │
│  💡 Hide explanation                    ✓ Predicted  │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ 💭 Duke is strongly favored: they have a      │  │
│  │    major offensive advantage, they are        │  │
│  │    dominant at their home venue, and they     │  │
│  │    have the edge in overall team strength.    │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Color Coding by Confidence

**High Confidence (75%+)**: Green accent
```jsx
┌────────────────────────────────────────┐
│ 💭 Duke is strongly favored: they...  │ ← Green left border
└────────────────────────────────────────┘
```

**Medium Confidence (60-75%)**: Yellow accent
```jsx
┌────────────────────────────────────────┐
│ 💭 Wake Forest is favored: they...    │ ← Yellow left border
└────────────────────────────────────────┘
```

**Low Confidence (<60%)**: Gray accent
```jsx
┌────────────────────────────────────────┐
│ 💭 Kansas is narrowly favored: they...│ ← Gray left border
└────────────────────────────────────────┘
```

---

## Implementation Code

### 1. Update PredictionsPage.jsx

```jsx
import { useState, useEffect } from 'react'
import { fetchUpcomingGames } from '../services/api'
import { TrendingUp, Trophy, AlertCircle, ChevronDown, ChevronUp, Lightbulb } from 'lucide-react'

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('with-predictions')
  const [dateFilter, setDateFilter] = useState('today')
  const [expandedGames, setExpandedGames] = useState(new Set()) // Track expanded games
  
  // ... existing useEffect and filters ...
  
  const toggleExplanation = (gameId) => {
    setExpandedGames(prev => {
      const next = new Set(prev)
      if (next.has(gameId)) {
        next.delete(gameId)
      } else {
        next.add(gameId)
      }
      return next
    })
  }
  
  const getConfidenceBorderColor = (confidence) => {
    if (confidence >= 0.75) return 'border-green-500'
    if (confidence >= 0.60) return 'border-yellow-500'
    return 'border-gray-400'
  }
  
  return (
    <div className="space-y-6">
      {/* ... existing filters ... */}
      
      <div className="space-y-3">
        {filteredPredictions.map((game) => {
          const hasPrediction = game.predicted_winner && game.confidence
          const hasExplanation = game.explanation
          const isExpanded = expandedGames.has(game.game_id)
          
          return (
            <div key={game.game_id} className="card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  {/* Game matchup */}
                  <div className="flex items-center space-x-4 mb-2">
                    <span className="text-sm text-gray-500">{game.date}</span>
                    <span className="font-medium">{game.away_team}</span>
                    <span className="text-gray-400">@</span>
                    <span className="font-medium">{game.home_team}</span>
                  </div>
                  
                  {/* Prediction info */}
                  {hasPrediction ? (
                    <div className="text-sm">
                      <span className="text-gray-600">Predicted: </span>
                      <span className="font-semibold">{game.predicted_winner}</span>
                      <span className="text-gray-600 ml-3">Confidence: </span>
                      <span className="font-semibold">{(game.confidence * 100).toFixed(1)}%</span>
                    </div>
                  ) : (
                    <div className="text-sm text-gray-500">
                      No prediction available (insufficient team data)
                    </div>
                  )}
                  
                  {/* Explanation toggle button */}
                  {hasPrediction && hasExplanation && (
                    <button
                      onClick={() => toggleExplanation(game.game_id)}
                      className="mt-2 flex items-center space-x-1 text-sm text-primary-600 hover:text-primary-700 font-medium transition-colors"
                    >
                      <Lightbulb size={16} />
                      <span>{isExpanded ? 'Hide explanation' : 'Why ' + game.predicted_winner + '?'}</span>
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                  )}
                  
                  {/* Expanded explanation */}
                  {isExpanded && hasExplanation && (
                    <div 
                      className={`mt-3 p-3 bg-gray-50 rounded-lg border-l-4 ${getConfidenceBorderColor(game.confidence)} transition-all`}
                    >
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {game.explanation}
                      </p>
                    </div>
                  )}
                </div>
                
                {/* Status badge */}
                <div className="flex items-center space-x-3">
                  {hasPrediction ? (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-700">
                      ✓ Predicted
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600">
                      Scheduled
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

### 2. Update HomePage.jsx (Similar Pattern)

```jsx
import { Lightbulb, ChevronDown, ChevronUp } from 'lucide-react'

// Add to component state
const [expandedGames, setExpandedGames] = useState(new Set())

// Add same toggle function and border color function

// In the game card rendering:
{hasPrediction && game.explanation && (
  <>
    <button
      onClick={() => toggleExplanation(game.game_id)}
      className="mt-2 flex items-center space-x-1 text-sm text-primary-600 hover:text-primary-700 font-medium"
    >
      <Lightbulb size={16} />
      <span>{expandedGames.has(game.game_id) ? 'Hide' : 'Why ' + game.predicted_winner + '?'}</span>
      {expandedGames.has(game.game_id) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
    </button>
    
    {expandedGames.has(game.game_id) && (
      <div className={`mt-3 p-3 bg-gray-50 rounded-lg border-l-4 ${getConfidenceBorderColor(game.confidence)}`}>
        <p className="text-sm text-gray-700 leading-relaxed">
          {game.explanation}
        </p>
      </div>
    )}
  </>
)}
```

---

## CSS Additions

Add to your global CSS or Tailwind config:

```css
/* Smooth expand/collapse animation */
.explanation-enter {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: all 0.3s ease-in-out;
}

.explanation-enter-active {
  max-height: 200px;
  opacity: 1;
}

.explanation-exit {
  max-height: 200px;
  opacity: 1;
  transition: all 0.3s ease-in-out;
}

.explanation-exit-active {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
}
```

---

## Mobile Optimization

```jsx
{/* Responsive design - stack on mobile */}
<div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between">
  <div className="flex-1 w-full">
    {/* Game content */}
  </div>
  
  {/* Badge moves below on mobile */}
  <div className="mt-2 sm:mt-0 sm:ml-4">
    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-700">
      ✓ Predicted
    </span>
  </div>
</div>
```

---

## Alternative: Auto-Expand for High Confidence

For high-confidence games (80%+), you could auto-expand explanations:

```jsx
useEffect(() => {
  // Auto-expand high confidence predictions
  const highConfidenceGames = new Set(
    filteredPredictions
      .filter(g => g.confidence >= 0.80 && g.explanation)
      .map(g => g.game_id)
  )
  setExpandedGames(highConfidenceGames)
}, [filteredPredictions])
```

---

## Accessibility Features

```jsx
<button
  onClick={() => toggleExplanation(game.game_id)}
  className="..."
  aria-label={`${isExpanded ? 'Hide' : 'Show'} explanation for ${game.predicted_winner}`}
  aria-expanded={isExpanded}
>
  <Lightbulb size={16} aria-hidden="true" />
  <span>{isExpanded ? 'Hide explanation' : 'Why ' + game.predicted_winner + '?'}</span>
  {isExpanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
</button>
```

---

## Icon Options

**Current**: 💡 Lightbulb  
**Alternatives**:
- `<Info />` - ℹ️ (More subtle)
- `<MessageCircle />` - 💬 (Conversational)
- `<Brain />` - 🧠 (AI/intelligence)
- `<TrendingUp />` - 📈 (Analysis)

**Recommendation**: Stick with `<Lightbulb />` - universally understood as "insight"

---

## Testing Checklist

- [ ] Explanations display correctly on PredictionsPage
- [ ] Explanations display correctly on HomePage
- [ ] Click to expand/collapse works smoothly
- [ ] Border colors match confidence levels
- [ ] Mobile responsive (stacks properly)
- [ ] Accessible (keyboard navigation, screen readers)
- [ ] Works with missing explanations (graceful fallback)
- [ ] Performance good with 50+ games

---

## Performance Considerations

```jsx
// Memoize expensive computations
const gameCards = useMemo(() => {
  return filteredPredictions.map((game) => {
    // ... render game card
  })
}, [filteredPredictions, expandedGames])

// Virtualize long lists (optional, for 100+ games)
import { FixedSizeList } from 'react-window'
```

---

## Summary

✅ **Recommended Approach**: Expandable with icon (Option 2)

**Why?**
1. Clean default view (not cluttered)
2. User controls when to see details
3. Works great on mobile and desktop
4. Scalable to many games
5. Clear interaction pattern (button with icon)
6. Color-coded for quick scanning

**Next Steps**:
1. Implement expandable UI in PredictionsPage
2. Apply same pattern to HomePage
3. Test with real explanation data
4. Gather user feedback
5. Iterate based on usage patterns

**Optional Enhancements**:
- "Expand all" button for power users
- Remember expanded state in localStorage
- Add animation for expand/collapse
- Show explanation preview on hover (desktop only)
