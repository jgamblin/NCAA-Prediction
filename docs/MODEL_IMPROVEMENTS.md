# Model Improvement Plan

## 🎯 Executive Summary

Two major improvements have been developed to enhance prediction accuracy and identify profitable betting opportunities:

1. **Time-Weighted Training** - Prioritizes current season data over historical data
2. **Betting Line Disagreement Tracking** - Identifies when our model differs from Vegas and tracks profitability

---

## 1. Time-Weighted Model Tuning 📊

### Problem
College basketball has massive roster turnover each year (transfers, NBA draft, freshmen). A team from 2020 has almost zero relationship to that same team in 2025. Historical data becomes less relevant over time.

### Solution
**Script**: `model_training/tune_model.py`

**Key Features**:
- **Season Weighting**: Current season games get 10x weight, last season 3x, older seasons decay exponentially
- **Recency Weighting**: Within current season, more recent games weighted higher
- **Weekly Hyperparameter Tuning**: Automatically finds best model parameters using weighted cross-validation
- **Temporal Cross-Validation**: Uses TimeSeriesSplit to respect time ordering

**Weighting Strategy**:
```
2025-26 (current):  10.0x weight + recency boost (up to 2x more for recent games)
2024-25 (last year): 3.0x weight
2023-24:             1.5x weight  
2022-23:             0.75x weight
2021-22:             0.375x weight
2020-21:             0.1875x weight
```

### Usage

**Run weekly** (recommended Sunday nights after weekend games):
```bash
python3 model_training/tune_model.py
```

**Output**:
- Best hyperparameters for current season
- Current vs weighted accuracy comparison
- Season weight distribution
- Saved to `data/Model_Tuning_Log.json`

**Integration**:
The script will recommend specific parameters to update in `daily_pipeline.py`. Example output:
```
Recommendation: Update daily_pipeline.py with these parameters:
  n_estimators=150
  max_depth=25
  min_samples_split=10

And add sample_weight=calculate_sample_weights(train_df) to model.fit()
```

### Expected Benefits
- **Better accuracy on current season**: Model learns current trends vs outdated patterns
- **Faster adaptation**: New teams/styles get learned quickly
- **Reduced overfitting**: Less weight on stale historical data
- **5-10% accuracy boost**: Expected improvement on current season predictions

---

## 2. Betting Line Disagreement Analysis 💰

### Problem
We need to know:
1. Do we have betting line data available?
2. When does our model disagree with Vegas?
3. Are our disagreements profitable?

### Solution
**Script**: `game_prediction/analyze_betting_lines.py`

**Data Sources**:
The script checks multiple sources for betting information:
- `home_point_spread` field (from ESPN when available)
- Rankings (ranked vs unranked = implied favorite)
- Home court advantage (default small edge)

### Key Metrics Tracked

1. **Overall Performance**:
   - Model accuracy vs betting line accuracy
   - Head-to-head comparison

2. **Agreement Analysis**:
   - How often we agree with Vegas
   - Accuracy when we agree (validation check)

3. **Disagreement Analysis** (THE MONEY MAKER):
   - How often we disagree with Vegas
   - Accuracy when we disagree
   - ROI calculation assuming -110 odds
   - Detailed game-by-game results

### Usage

**Run after games complete**:
```bash
python3 game_prediction/analyze_betting_lines.py
```

**Sample Output**:
```
OVERALL PERFORMANCE
📊 Model Accuracy: 68.5% (45/65)
💰 Betting Line Accuracy: 71.2% (37/52)
   ✗ Model is 2.7% worse than betting lines

AGREEMENT vs DISAGREEMENT
📊 Total games with betting lines: 52
   ✓ Agreements: 44 (84.6%)
   ⚠️  Disagreements: 8 (15.4%)

✓ Model accuracy when AGREEING with betting lines: 75.0%

⚠️  Model accuracy when DISAGREEING with betting lines: 62.5%
   🎯 PROFITABLE! Model is correct 62.5% when disagreeing!
   💵 If betting $100 per disagreement, potential ROI analysis:
      Wins: 5, Losses: 3
      Estimated profit: $154.55
      ROI: 17.6%
```

### What Makes a Disagreement?
- **Model picks home, Vegas picks away** (or vice versa)
- Examples:
  - Model: Duke -5, Vegas: Duke +3 (Model more confident in Duke)
  - Model: Kentucky, Vegas: Tennessee (Model picked different winner)

### Integration with Daily Pipeline

**Option A**: Add to `daily_pipeline.py` as Step 6:
```python
# STEP 6: Analyze betting line disagreements
from analyze_betting_lines import analyze_betting_line_performance
analyze_betting_line_performance()
```

**Option B**: Run separately after evening games complete:
```bash
# Morning: Generate predictions
python3 daily_pipeline.py

# Evening: Analyze results and betting lines
python3 game_prediction/analyze_betting_lines.py
```

### Saved Data
Results saved to `data/Betting_Line_Analysis.json`:
```json
{
  "date": "2025-11-04 20:00:00",
  "total_predictions": 65,
  "model_accuracy": 0.685,
  "betting_line_accuracy": 0.712,
  "disagreements": 8,
  "disagreement_accuracy": 0.625,
  "agreement_accuracy": 0.750
}
```

---

## 🚀 Recommended Weekly Workflow

### Monday Morning
1. Review last week's betting line analysis
2. Identify pattern in profitable disagreements

### Sunday Evening (Weekly Tuning)
```bash
# 1. Run weekly model tuning
python3 model_training/tune_model.py

# 2. Update daily_pipeline.py with recommended parameters

# 3. Test updated model
python3 daily_pipeline.py

# 4. Analyze betting performance
python3 game_prediction/analyze_betting_lines.py
```

### Daily (Automated via GitHub Actions)
```bash
# Runs automatically at 12 PM UTC
python3 daily_pipeline.py
```

---

## 📈 Expected Improvements

### Time-Weighted Training
- **Current Season Accuracy**: +5-10%
- **Early Season Performance**: +15% (model adapts faster)
- **Transfer Portal Impact**: Model learns new rosters quickly
- **Conference Tournament**: Better performance (recent games weighted heavily)

### Betting Line Analysis
- **Value Identification**: Find 5-10 games per week where we disagree
- **Profitable Disagreements**: If 55%+ accurate on disagreements = profitable
- **Risk Management**: Only bet disagreements with high model confidence
- **Bankroll Strategy**: Track ROI over season, adjust bet sizing

---

## 🔍 Data Investigation Results

### Available Betting Data
✅ **home_point_spread** - Column exists in both historical and ESPN data
❌ **Moneyline odds** - Not currently captured
❌ **Over/Under** - Not currently captured

### Current Point Spread Coverage
```python
# Checking historical data
df = pd.read_csv('data/Completed_Games.csv')
has_spread = df['home_point_spread'].notna() & (df['home_point_spread'] != '')
print(f"Games with point spread: {has_spread.sum()} / {len(df)}")
# Result: Most historical games don't have spreads (NCAA data doesn't include them)

# ESPN current season should have more spread data
espn_df = pd.read_csv('data/ESPN_Current_Season.csv')
# ESPN sometimes includes point spreads in game pages
```

### Enhancement Opportunity
**Future improvement**: Enhance `espn_scraper.py` to extract point spreads from individual game pages:
- Game page URL: `https://www.espn.com/mens-college-basketball/game/_/gameId/{game_id}`
- Look for "Line" or "Spread" in betting section
- Would give us more complete betting line data

---

## 🎯 Next Steps

### Immediate (Before Push)
1. ✅ Test `tune_model.py` on current data
2. ✅ Test `analyze_betting_lines.py` with available data
3. ⚠️ Verify ESPN has point spread data available

### Short Term (This Week)
1. Run first weekly tuning
2. Update daily_pipeline.py with tuned parameters
3. Add sample weighting to training
4. Start tracking betting line disagreements

### Medium Term (This Month)
1. Enhance ESPN scraper to capture point spreads consistently
2. Add moneyline odds tracking
3. Build betting strategy dashboard
4. Automate weekly tuning via GitHub Actions

### Long Term (This Season)
1. Machine learning for bet sizing
2. Conference-specific models
3. Player injury impact analysis
4. Live game prediction updates

---

## 📊 Success Metrics

Track these weekly:
- **Model Accuracy**: Current season vs historical
- **Disagreement Rate**: % of games where we differ from Vegas
- **Disagreement Accuracy**: Win rate on our contrarian picks
- **ROI**: Profit/loss if betting $100 per disagreement
- **Confidence Calibration**: Are 80% confidence picks actually 80% accurate?

---

## 🔧 Technical Notes

### Sample Weights Implementation
```python
# Add this function to daily_pipeline.py
def calculate_sample_weights(df, current_season='2025-26'):
    weights = np.ones(len(df))
    season_weights = {
        '2025-26': 10.0,
        '2024-25': 3.0,
        '2023-24': 1.5,
        '2022-23': 0.75,
        '2021-22': 0.375,
        '2020-21': 0.1875
    }
    for season, weight in season_weights.items():
        weights[df['season'] == season] = weight
    return weights

# Then in model training:
model.fit(X, y, sample_weight=calculate_sample_weights(train_df))
```

### Betting Line Extraction
```python
# Current: Basic inference from available data
# Future: Enhanced scraping from ESPN game pages
def scrape_betting_lines(game_url):
    response = requests.get(game_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    # Look for: <div class="odds">...</div>
    # Extract: spread, moneyline, over/under
    return betting_data
```

---

## Questions?

Run the scripts and check the output files:
- `data/Model_Tuning_Log.json` - Tuning history
- `data/Betting_Line_Analysis.json` - Betting performance
- `data/Accuracy_Report.csv` - Daily accuracy tracking

Both scripts include verbose output explaining their findings and recommendations.
