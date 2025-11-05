# NCAA Basketball Game Predictions

[![Daily Predictions](https://github.com/jgamblin/NCAA-Prediction/actions/workflows/daily-predictions.yml/badge.svg)](https://github.com/jgamblin/NCAA-Prediction/actions/workflows/daily-predictions.yml)

Predict NCAA basketball game outcomes using machine learning models trained on multi-season historical data. This project uses `scikit-learn` for modeling and fetches data from [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) and ESPN.com.

## 📅 [View Today's Predictions →](predictions.md)

**Current Predictions**: 36 games for November 4, 2025**  
**Last Updated**: Automated daily at 12:00 PM UTC

### 📋 Full Details
- **[Complete Predictions CSV →](data/NCAA_Game_Predictions.csv)** - All games sorted by confidence
- **[Predictions Markdown →](predictions.md)** - Human-readable format with analysis

## 🏀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the daily pipeline (scrape → train → predict → track)
python3 daily_pipeline.py
```

**Training Data**: 29,343 games (2020-21 through Nov 3, 2025)  
**Algorithm**: Random Forest Classifier  
**Features**: Team embeddings, AP rankings, neutral site indicator

## 📁 Project Structure
```
NCAA-Prediction/
├── daily_pipeline.py         # 🚀 Main script: Full daily automation
├── predictions.md            # 📊 Today's predictions (auto-updated)
├── requirements.txt          # Python dependencies
├── scripts/                  # One-off and historical debug utilities (not part of core pipeline)
│   ├── debug_indiana_prediction.py  # Historical name drift investigation
│   └── archive/check_team_ids.py    # Original ESPN team ID exploration (now integrated)
├── data/                     # All data files (CSV, JSON)
│   ├── Completed_Games.csv       # Historical game results
│   ├── Upcoming_Games.csv        # Scheduled games
│   ├── NCAA_Game_Predictions.csv # Model predictions
│   ├── Accuracy_Report.csv       # Prediction tracking
│   └── Model_Tuning_Log.json     # Tuning history
├── data_collection/          # Data fetching modules
│   ├── espn_scraper.py      # ESPN live data scraper
│   ├── all_games.py         # ncaahoopR historical data
│   ├── collect_data.py      # Data orchestrator
│   ├── check_seasons.py     # List available seasons
│   ├── normalize_teams.py   # Team name normalization with alias mapping
│   └── check_unmatched_teams.py  # Identify unmatched teams for cleanup
├── model_training/           # ML training modules
│   ├── simple_predictor.py  # 🆕 Main prediction model
│   ├── tune_model.py        # 🆕 Weekly hyperparameter tuning
│   ├── ncaa_predictions_v2.py  # Enhanced 30-feature model
│   └── ncaa_predictions.py     # Legacy 15-feature model
├── game_prediction/          # Prediction utilities
│   ├── generate_predictions_md.py  # Markdown generator
│   ├── track_accuracy.py           # Accuracy tracker
│   ├── analyze_betting_lines.py    # 🆕 Vegas comparison
│   └── view_predictions.py         # Terminal viewer
├── docs/                     # 📚 Documentation
└── tests/                    # Pytest unit tests (incl. Indiana prediction normalization)
    ├── QUICKSTART.md
    ├── MODEL_IMPROVEMENTS.md
    ├── CODE_REVIEW.md
    └── REFACTORING_SUMMARY.md
```

## 🎯 Features

### Data Collection
- Multi-season data fetching (configurable)
- Currently fetches 5 seasons: 2020-21 through 2024-25
- ~29,000 games, 1,287 unique teams
- Data source: [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) (ESPN data)
- **Rankings**: AP poll rankings, differentials
- **Historical Performance**: Win %, PPG, OPPG, point differential

### Training Strategy
- **Time-Weighted Training**: Recent games weighted higher
- **Lagged Statistics**: Prevents look-ahead bias
- **RandomizedSearchCV**: 50-iteration hyperparameter optimization
- **Cross-Validation**: 5-fold CV for reliable estimates

## 🔧 Configuration

### Advanced Features

**Betting Line Analysis** - Compare model vs Vegas:
```bash
python3 game_prediction/analyze_betting_lines.py
```
- Tracks disagreements with betting lines
- Calculates ROI on contrarian picks
- Identifies profitable prediction patterns

**Change Seasons to Fetch** - Edit `data_collection/all_games.py`:
```python
SEASONS = ["2022-23", "2023-24", "2024-25"]  # Use only recent 3 seasons
CURRENT_SEASON = "2025-26"
```

**Check Available Seasons**:
```bash
python3 data_collection/check_seasons.py
```
Shows all available seasons (23 seasons from 2002-03 to 2024-25).

## 📈 Model Evaluation

### Current Performance

- **Overall Accuracy**: 91.7% (on 36 predictions)
- **Training Data**: 29,417 games
  - Current season: 412 games
  - Historical: 29,005 games

### Model Configuration

- **Algorithm**: Random Forest Classifier
- **Features**: Team embeddings, AP rankings, neutral site indicator (5 features)
- **Training Strategy**: Time-weighted (10x current season, exponential decay for older)
- **Hyperparameters**: Auto-tuned weekly via RandomForestClassifier optimization

*Last updated: 2025-11-05 23:49 UTC*

### Model Lineage

- Config Version: `unknown`
- Commit Hash: `unknown`

## 🚀 Automation

GitHub Actions runs predictions daily at 12:00 PM UTC (7:00 AM EST):
1. **Scrape ESPN** - Fetch completed and upcoming games
2. **Merge Data** - Add completed games to training set
3. **Track Accuracy** - Compare predictions vs actual results
4. **Generate Predictions** - Train model and predict upcoming games
5. **Update Markdown** - Create predictions.md with results
6. **Auto-commit** - Push updates back to repository

See `.github/workflows/daily-predictions.yml`

### Weekly Model Tuning

Run weekly to optimize for current season:
```bash
python3 model_training/tune_model.py
```
- Time-weighted training (10x current season)
- Hyperparameter optimization
- 96.4% accuracy on current season games

## 📝 Output Files

All outputs saved to `data/` directory:

- **Completed_Games.csv**: Historical game results (29,343 games)
- **Upcoming_Games.csv**: Scheduled games awaiting predictions  
- **NCAA_Game_Predictions.csv**: Predictions with confidence scores
- **Accuracy_Report.csv**: Daily prediction accuracy tracking
- **ESPN_Current_Season.csv**: Live scraped current season data
- **Model_Tuning_Log.json**: Weekly tuning results and metrics
- **Betting_Line_Analysis.json**: Vegas comparison analytics

Plus **predictions.md** in root - formatted predictions for GitHub display

## 🔐 Stable Team Identifiers

To ensure long-term consistency as team naming conventions shift (e.g., "Appalachian St" vs "Appalachian State Mountaineers"), the pipeline now captures stable team identifiers:

| Column | Files | Source | Fallback Behavior |
| ------ | ------ | ------ | ---------------- |
| `home_team_id` | `Upcoming_Games.csv`, `NCAA_Game_Predictions.csv` | ESPN event JSON (`competitors[].id`) | If missing, generates `namehash_<hash>` from normalized team name |
| `away_team_id` | `Upcoming_Games.csv`, `NCAA_Game_Predictions.csv` | ESPN event JSON | Same as above |

### Why This Matters
* Provides a durable join key for future advanced features (e.g., roster tracking, conference drift, opponent strength caching).
* Shields models from textual alias volatility and manual mapping churn.
* Enables precise tracking of low-data teams across seasons regardless of name presentation.

### Usage Notes
* When an ESPN numeric ID exists it will be a short integer-like string (e.g., `313`); otherwise a deterministic `namehash_XXXXXX` placeholder appears.
* Modeling still uses normalized textual names today; future iterations can switch embeddings or history joins to ID keys seamlessly.
* If you add enrichment (rosters, coaches, pace metrics), prefer joining on these ID columns rather than raw names.

### Future Enhancements
Planned follow-ups that will leverage IDs:
1. Drift monitoring keyed by `team_id` instead of name.
2. Persisted per-team feature store (e.g., cached rolling averages) invalidated by ID rather than string.
3. Cross-source reconciliation (KenPom / NCAA / ESPN) via lookup map.

## 📚 Documentation

Each directory contains a detailed README:
- [data/README.md](data/README.md) - Data file schemas
- [data_collection/README.md](data_collection/README.md) - Data fetching details
- [model_training/README.md](model_training/README.md) - Model architecture
- [game_prediction/README.md](game_prediction/README.md) - Future utilities

## 🛠 Tech Stack

- **Python 3.x**
- **scikit-learn**: Random Forest classifier, hyperparameter tuning
- **pandas**: Data manipulation
- **matplotlib/seaborn**: Visualization
- **requests**: API calls to ncaahoopR_data

## 📄 License

See [LICENSE](LICENSE)

## 🙏 Acknowledgments

- [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) by Luke Benz - Pre-scraped NCAA basketball data
- ESPN - Original data source

---

## 🆕 Recent Updates

**November 4, 2025**
- ✅ Refactored daily pipeline with extracted model class
- ✅ Added weekly model tuning with time-weighted training
- ✅ Implemented betting line disagreement tracker
- ✅ Fixed all linting issues and improved code quality
- ✅ Updated to Python 3.14 for GitHub Actions
- 🎯 **Current season accuracy: 96.4%**

---

**Last updated:** November 4, 2025
