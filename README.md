# NCAA Basketball Game Predictions

[![Daily Predictions](https://github.com/jgamblin/NCAA-Prediction/actions/workflows/daily-predictions.yml/badge.svg)](https://github.com/jgamblin/NCAA-Prediction/actions/workflows/daily-predictions.yml)

Predict NCAA basketball game outcomes using machine learning models trained on multi-season historical data. This project uses `scikit-learn` for modeling and fetches data from [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) and ESPN.com.

## 📅 [View Today's Predictions →](predictions.md)

**Current Predictions**: 36 games for November 4, 2025  
**Last Updated**: Automated daily at 12:00 PM UTC

## 🏀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the daily pipeline (scrape → train → predict → track)
python3 daily_pipeline.py

# View today's predictions
python3 view_predictions.py
```

## 📊 Model Performance

- **Training Data**: 29,343 games (2020-21 through Nov 3, 2025)
- **Algorithm**: Random Forest Classifier
- **Features**: Team embeddings, AP rankings, neutral site indicator
- **Historical Accuracy**: 72.4% (on 29K games)
- **Current Season**: 2025-26 (Nov 4, 2025 - ongoing)
- **Data Sources**: 
  - Historical: [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data)
  - Live: ESPN.com (real-time scraping)

## 📁 Project Structure

```
NCAA-Prediction/
├── collect_data.py           # Main script: Run data collection
├── run_predictions.py        # Main script: Run predictions
├── requirements.txt          # Python dependencies
├── data/                     # All data files (CSV, plots)
│   ├── Completed_Games.csv
│   ├── Upcoming_Games.csv
│   ├── NCAA_Game_Predictions.csv
│   └── feature_importance.png
├── data_collection/          # Data fetching scripts
│   ├── all_games.py         # Fetch games from ncaahoopR_data
│   └── check_seasons.py     # List available seasons
├── model_training/           # ML model scripts
│   ├── ncaa_predictions_v2.py  # Enhanced model (recommended)
│   └── ncaa_predictions.py     # Legacy model
└── game_prediction/          # Future prediction utilities
```

## 🎯 Features

### Data Collection
- Multi-season data fetching (configurable)
- Currently fetches 5 seasons: 2020-21 through 2024-25
- ~29,000 games, 1,287 unique teams
- Data source: [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) (ESPN data)

### Model Features (30 total)
- **Team Identity**: Encoded team IDs
- **Rankings**: AP poll rankings, differentials
- **Historical Performance**: Win %, PPG, OPPG, point differential
- **Recent Form**: Last 5/10 game averages, momentum
- **Win Streaks**: Current win/loss streaks
- **Context**: Home court advantage, neutral sites

### Training Strategy
- **Time-Weighted Training**: Recent games weighted higher
- **Lagged Statistics**: Prevents look-ahead bias
- **RandomizedSearchCV**: 50-iteration hyperparameter optimization
- **Cross-Validation**: 5-fold CV for reliable estimates

## 🔧 Configuration

### Change Seasons to Fetch

Edit `data_collection/all_games.py`:

```python
SEASONS = ["2022-23", "2023-24", "2024-25"]  # Use only recent 3 seasons
CURRENT_SEASON = "2024-25"
```

Or fetch a specific season from command line:

```bash
python3 data_collection/all_games.py 2024-25
```

### Check Available Seasons

```bash
python3 data_collection/check_seasons.py
```

Shows all available seasons in the repository (currently 23 seasons from 2002-03 to 2024-25).

## 📈 Model Evaluation

### Top Features by Importance

1. **Historical Win % Differential** (14.2%)
2. **Historical Point Differential** (11.2%)
3. **Historical OPPG Differential** (5.7%)
4. **Away Team Historical Win %** (5.4%)
5. **Home Team Historical Win %** (4.7%)
6. **Recent Form (Last 5 games)** (4.2%)

### Performance Metrics
- **Precision**: Home wins (75%), Away wins (64%)
- **Recall**: Home wins (86%), Away wins (47%)
- **Log Loss**: 0.530 (lower is better)

## 🚀 Automation

GitHub Actions runs predictions daily at 12:00 PM UTC (6:00 AM CST):
- Fetches latest game data
- Trains model on historical data
- Generates predictions for upcoming games
- Commits results to repository

See `.github/workflows/run_notebooks.yml`

## 📝 Output Files

All outputs saved to `data/` directory:

- **Completed_Games.csv**: Historical game results with statistics
- **Upcoming_Games.csv**: Scheduled games awaiting predictions  
- **NCAA_Game_Predictions.csv**: Predictions with confidence scores
- **feature_importance.png**: Model feature importance visualization

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

**Last updated:** November 3, 2025
