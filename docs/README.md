# Documentation

This folder contains user guides and documentation for the NCAA Basketball Predictions project.

## Files

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide for new users
  - Daily usage instructions
  - File structure overview
  - Model information
  - Top predictions

## Helper Scripts

The following helper scripts are located in their respective subfolders:

### Data Collection (`data_collection/`)
- **`collect_data.py`** - Standalone data collection script
  - Fetches historical data from ncaahoopR_data
  - Scrapes current season from ESPN
  - Merges both data sources

### Model Training & Predictions (`model_training/`)
- **`run_predictions.py`** - Standalone prediction generation
  - Trains model on historical data
  - Generates predictions for upcoming games

### Game Prediction Utilities (`game_prediction/`)
- **`view_predictions.py`** - View today's predictions in terminal
  ```bash
  python3 game_prediction/view_predictions.py
  ```
- **`generate_predictions_md.py`** - Generate predictions.md file
  - Auto-called by daily_pipeline.py
  - Creates markdown display for GitHub

## Main Workflow

For daily automated predictions, simply run:
```bash
python3 daily_pipeline.py
```

This orchestrates all the helper scripts to:
1. Scrape ESPN for new games
2. Update training data
3. Generate predictions
4. Track accuracy
5. Update predictions.md
