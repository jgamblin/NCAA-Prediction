# Betting Accuracy Analytics Page

## Overview

A comprehensive betting performance analytics page that provides detailed visualizations and insights into betting wins, losses, profitability, and performance across different confidence levels and strategies.

## Location

- **Route**: `/betting-accuracy`
- **File**: `frontend/src/pages/BettingAccuracyPage.jsx`
- **Navigation**: "Bet Analytics" in main menu

## Features

### 1. Summary Stats Dashboard
- **Win Rate** - Overall success percentage with W-L record
- **Total Profit** - Cumulative profit/loss with amount wagered
- **ROI** - Return on investment percentage
- **Total Bets** - Number of bets placed
- **Parlay Stats** - Dedicated parlay performance metrics

### 2. Win/Loss Distribution (Pie Chart)
- Visual breakdown of wins vs losses
- Percentage distribution
- Total counts for each category
- Color-coded (Green for wins, Red for losses)

### 3. Profit Timeline (Area Chart)
- Cumulative profit over time
- Date-based progression
- Visual trend analysis
- Current total profit display
- Gradient fill for better visualization

### 4. Performance by Confidence Level (Bar Chart)
- Win rate comparison across confidence tiers
  - High (≥70%)
  - Medium (60-70%)
- ROI comparison for each tier
- Dual Y-axis for different metrics
- Detailed cards showing:
  - Total bets per tier
  - Win rate percentage
  - Win-Loss record
  - Total profit/loss
  - ROI percentage

### 5. Performance by Strategy
- Breakdown of different betting strategies
- Currently tracks:
  - Value Betting (bets where model confidence exceeds implied odds)
- Metrics per strategy:
  - Total bets
  - Win rate
  - Record (W-L)
  - Total profit
  - ROI

### 6. Parlay Performance Section
- Dedicated parlay analytics
- Metrics:
  - Total parlays placed
  - Win rate
  - Record (W-L)
  - Total profit/loss
  - ROI
  - Biggest win
  - Biggest loss

### 7. Key Insights Panel
- Best performing confidence tier
- Average bet size
- Actionable recommendations

## Data Sources

The page fetches data from the following JSON endpoints:

```javascript
- betting_summary.json         // Overall betting statistics
- betting_by_confidence.json   // Performance by confidence level
- betting_by_strategy.json     // Performance by betting strategy
- cumulative_profit.json       // Daily profit timeline
- parlay_stats.json           // Parlay-specific metrics
```

## Technical Details

### Dependencies
- **React** - UI framework
- **Recharts** - Charting library
- **Lucide React** - Icon library

### Components Used
- LineChart / AreaChart - For profit timeline
- BarChart - For confidence level comparison
- PieChart - For win/loss distribution
- Responsive containers for all charts

### Color Scheme
```javascript
COLORS = {
  win: '#10b981',      // Green
  loss: '#ef4444',     // Red
  primary: '#3b82f6',  // Blue
  secondary: '#8b5cf6', // Purple
  accent: '#f59e0b'    // Orange
}
```

## Usage

### Accessing the Page
1. Navigate to the web dashboard: `https://jgamblin.github.io/NCAA-Prediction/`
2. Click "Bet Analytics" in the navigation menu
3. Or visit directly: `https://jgamblin.github.io/NCAA-Prediction/betting-accuracy`

### Local Development
```bash
cd frontend
npm install
npm run dev
```

Then navigate to: `http://localhost:5173/betting-accuracy`

## Future Enhancements

Potential additions:
- [ ] Filtering by date range
- [ ] Downloadable reports (PDF/CSV)
- [ ] More granular time-based analysis (weekly, monthly)
- [ ] Team-specific betting performance
- [ ] Bankroll management recommendations
- [ ] Streak analysis (winning/losing streaks)
- [ ] Expected value (EV) tracking
- [ ] Comparison against Vegas closing lines

## Screenshots

The page includes:
- **5 summary stat cards** at the top
- **2 large charts** (Win/Loss pie + Profit timeline)
- **1 confidence analysis section** with bar chart + detailed cards
- **Strategy performance cards**
- **Parlay dedicated section**
- **Key insights panel**

All charts are:
- ✅ Fully responsive
- ✅ Interactive (hover tooltips)
- ✅ Color-coded for quick insights
- ✅ Real-time data from JSON feeds

## Related Pages

- **Betting Page** (`/betting`) - View current value bets and parlays
- **Accuracy Page** (`/accuracy`) - Model prediction accuracy
- **History Page** (`/history`) - Historical prediction results

## Data Update Frequency

Data updates every 3 hours via GitHub Actions:
1. Daily pipeline runs
2. Bets are settled when games complete
3. JSON files are exported
4. Frontend auto-refreshes on next load

## Notes

- Empty state handled gracefully when no betting data exists
- All monetary values displayed with 2 decimal precision
- Percentages rounded to 1 decimal place
- Charts use memoization for performance
- Responsive design for mobile and desktop
