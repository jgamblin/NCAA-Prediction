# Data Collection

This directory contains scripts for fetching NCAA basketball game data.

## Scripts

### all_games.py
Main data collection script that fetches game schedules and results from the ncaahoopR_data repository.

**Configuration:**
- `SEASONS`: List of seasons to fetch (default: last 5 seasons)
- `CURRENT_SEASON`: The season we're making predictions for

**Usage:**
```bash
# Fetch all configured seasons
python data_collection/all_games.py

# Fetch specific season
python data_collection/all_games.py 2024-25
```

**Output:**
- `data/Completed_Games.csv` - All completed games
- `data/Upcoming_Games.csv` - Scheduled games

### check_seasons.py
Utility script to list all available seasons in the ncaahoopR_data repository.

**Usage:**
```bash
python data_collection/check_seasons.py
```

## Data Source

Data is scraped from the [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) repository, which contains game-by-game results scraped from ESPN by the ncaahoopR R package.

## Season Format

Seasons are named by the year they start:
- "2024-25" represents November 2024 through April 2025
- Each season contains ~6,000-6,500 games

## Multi-Season Collection

By default, the script fetches 5 seasons of data (approximately 29,000 games) to provide sufficient training data for machine learning models.
