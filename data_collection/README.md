# Data Collection

This directory contains scripts for fetching NCAA basketball game data from multiple sources.

## Scripts

### all_games.py
Fetches **historical** game data from the ncaahoopR_data repository (seasons 2020-21 through 2024-25).

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

### espn_scraper.py
Scrapes **current season** (2025-26) game data directly from ESPN.com.

**Features:**
- Real-time game data for the current season
- Both completed and upcoming games
- Rankings, records, scores, and neutral site info
- Optional enrichment with additional game details

**Usage:**
```bash
# Run standalone to scrape current season
python data_collection/espn_scraper.py

# Or use as part of the full pipeline
python collect_data.py
```

**Output:**
- `data/ESPN_Current_Season.csv` - Current season games from ESPN

**Why ESPN Scraper?**
The ncaahoopR_data repository updates weekly/monthly and won't have a complete 2025-26 season until late 2025 or early 2026. The ESPN scraper gets real-time data so we can make predictions for current season games as they're scheduled.

### check_seasons.py
Utility script to list all available seasons in the ncaahoopR_data repository.

**Usage:**
```bash
python data_collection/check_seasons.py
```

## Data Sources

### Historical Data (2020-21 through 2024-25)
- **Source:** [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) repository
- **Method:** Pre-scraped data from ESPN, curated by the ncaahoopR R package team
- **Coverage:** Complete seasons with ~6,000-6,500 games per season
- **Update Frequency:** Weekly/monthly during season, final data after season ends

### Current Season Data (2025-26)
- **Source:** ESPN.com direct scraping
- **Method:** Custom Python scraper using BeautifulSoup
- **Coverage:** Real-time data as games are played
- **Update Frequency:** Updated each time `collect_data.py` runs (daily via GitHub Actions)

## Season Format

Seasons are named by the year they start:
- "2024-25" represents November 2024 through April 2025
- "2025-26" represents November 2025 through April 2026
- Each season contains ~6,000-6,500 games

## Multi-Season Strategy

Our data collection strategy uses:
1. **5 seasons of historical data** (~29,000 games) from ncaahoopR_data for model training
2. **Current season data** from ESPN scraper for making live predictions
3. **Automatic merging** in `collect_data.py` to combine both sources
