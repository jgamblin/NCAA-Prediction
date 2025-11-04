# NCAA Basketball Predictions - Quick Start Guide

## 🏀 Overview
This repository predicts NCAA Division I basketball games using machine learning trained on 29,000+ historical games.

## 📊 Current Status (Nov 4, 2025)
- **Training Data**: 29,343 games (2020-21 through Nov 3, 2025)
- **Model**: Random Forest with 72.4% historical accuracy
- **Today's Predictions**: 36 games for Nov 4, 2025
- **Data Source**: ESPN.com (real-time scraping)

## 🚀 Daily Usage

### Run the complete pipeline:
```bash
python3 daily_pipeline.py
```

This single script:
1. ✅ Scrapes ESPN for completed and upcoming games
2. ✅ Merges completed games into training data
3. ✅ Tracks accuracy of previous predictions
4. ✅ Generates new predictions for upcoming games

### View today's predictions:
```bash
cat data/NCAA_Game_Predictions.csv
```

## 📁 Key Files

### Root Scripts
- **`daily_pipeline.py`** - Main automation script (run daily)
- `collect_data.py` - Data collection orchestrator
- `run_predictions.py` - Prediction orchestrator

### Data Files (`data/`)
- **`Completed_Games.csv`** - Historical training data (29,343 games)
- **`Upcoming_Games.csv`** - Games scheduled for today/tomorrow
- **`NCAA_Game_Predictions.csv`** - Model predictions with confidence scores
- **`Accuracy_Report.csv`** - Prediction performance tracking

### Data Collection (`data_collection/`)
- **`espn_scraper.py`** - Scrapes ESPN for current season games
- `all_games.py` - Fetches historical data from ncaahoopR_data
- `check_seasons.py` - Lists available seasons

### Model Training (`model_training/`)
- `ncaa_predictions_v2.py` - Enhanced model (30 features, recommended)
- `ncaa_predictions.py` - Legacy model (15 features)

### Game Prediction (`game_prediction/`)
- **`track_accuracy.py`** - Compares predictions vs actual results

## 🔄 Workflow

```
┌─────────────────┐
│  ESPN Scraper   │  Scrape completed + upcoming games
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Merge Data     │  Add completed games to training set
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Train Model    │  Random Forest on 29K+ games
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Predict Games  │  Generate predictions for upcoming
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Track Accuracy  │  Compare predictions vs actual results
└─────────────────┘
```

## 📈 Model Features
- Team embeddings (encoded team IDs)
- AP Rankings (Top 25)
- Neutral site indicator
- Historical performance

## 🎯 Prediction Format
```csv
game_id,date,away_team,home_team,predicted_winner,home_win_probability,confidence
401826885,2025-11-04,Evansville Purple Aces,Purdue Boilermakers,Purdue Boilermakers,0.814,0.814
```

## 🏆 Today's Top Picks (Nov 4, 2025)
1. **Rice** over College Of Biblical Studies (87.9% confidence)
2. **Kentucky** over Nicholls (81.4% confidence)
3. **Purdue** over Evansville (81.4% confidence)
4. **Duke** over Texas (81.4% confidence)
5. **Texas Tech** over Lindenwood (81.4% confidence)

## 📅 Automation
Run `daily_pipeline.py` every morning to:
- Pull overnight completed games
- Update training data
- Generate fresh predictions
- Track prediction accuracy

## 🛠 Manual Operations

### Collect historical data only:
```bash
python3 data_collection/all_games.py
```

### Scrape ESPN only:
```bash
python3 data_collection/espn_scraper.py
```

### Track accuracy only:
```bash
python3 game_prediction/track_accuracy.py
```

## 📊 Data Sources
- **Historical**: ncaahoopR_data GitHub repository (2020-2025)
- **Current Season**: ESPN.com direct scraping (2025-26)

## 🔍 Monitoring
Check `data/Accuracy_Report.csv` to track prediction performance over time.

---

**Last Updated**: November 4, 2025  
**Next Update**: Run `python3 daily_pipeline.py` tomorrow morning
