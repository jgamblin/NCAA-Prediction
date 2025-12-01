# NCAA Prediction System Refactor Plan
## Database Migration & Web Frontend Development

**Branch**: `feature/database-refactor-webapp`  
**Created**: December 1, 2024  
**Goal**: Migrate from CSV-based system to database (DuckDB/SQLite) and create modern web frontend

---

## 🎯 Executive Summary

### Current Architecture Problems
1. **Performance Bottleneck**: 78+ `pd.read_csv()` calls across 36 files
2. **Data Fragmentation**: 17+ CSV files with no relational integrity
3. **Memory Overhead**: Loading 30K+ game records repeatedly
4. **No Query Optimization**: Full table scans for every analysis
5. **Limited Accessibility**: CLI/Markdown only, no web interface
6. **No Real-time Updates**: Static file generation only

### Proposed Solution
- **Database**: DuckDB (analytics-optimized) or SQLite (simpler deployment)
- **Backend API**: FastAPI for REST endpoints
- **Frontend**: React + TailwindCSS + shadcn/ui components
- **Hosting**: GitHub Pages (static site generation)
- **Betting Flow**: Complete rebuild with database-backed queries

---

## 📊 Current Architecture Analysis

### Data Files (CSV-based)
```
data/
├── Completed_Games.csv              (30,706 games - PRIMARY DATA)
├── Completed_Games_Normalized.csv   (Normalized team names)
├── Upcoming_Games.csv               (Future predictions)
├── NCAA_Game_Predictions.csv        (Daily snapshot)
├── prediction_log.csv               (Historical predictions)
├── Accuracy_Report.csv              (Daily accuracy tracking)
├── Drift_Metrics.csv                (Model drift monitoring)
├── Drift_Metrics_By_Team.csv        (Per-team performance)
├── feature_store/feature_store.csv  (Rolling team features)
└── [10+ other analytics CSVs]
```

### Critical CSV Read Operations
- **daily_pipeline.py**: 5 reads (historical games, upcoming, predictions)
- **betting_tracker.py**: 5 reads (predictions, completed games, logs)
- **publish_artifacts.py**: 17 reads (most intensive)
- **track_accuracy.py**: 5 reads
- **drift_monitor.py**: 4 reads

### Data Flow
```
ESPN API → espn_scraper.py → CSV
                ↓
        normalize_teams.py → CSV
                ↓
        feature_store.py → CSV
                ↓
        adaptive_predictor.py → MODEL
                ↓
        predictions → CSV
                ↓
        markdown reports → STATIC FILES
```

---

## 🏗️ New Architecture Design

### Database Schema (DuckDB/SQLite)

#### Core Tables

**1. games** (replaces Completed_Games.csv)
```sql
CREATE TABLE games (
    game_id VARCHAR PRIMARY KEY,
    date DATE NOT NULL,
    season VARCHAR NOT NULL,
    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,
    home_team_id VARCHAR NOT NULL,
    away_team_id VARCHAR NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    game_status VARCHAR NOT NULL,  -- 'Final', 'Scheduled', 'In Progress'
    neutral_site BOOLEAN DEFAULT FALSE,
    home_moneyline INTEGER,
    away_moneyline INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_date (date),
    INDEX idx_season (season),
    INDEX idx_teams (home_team_id, away_team_id),
    INDEX idx_status (game_status)
);
```

**2. predictions** (replaces NCAA_Game_Predictions.csv + prediction_log.csv)
```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id VARCHAR NOT NULL,
    prediction_date TIMESTAMP NOT NULL,
    home_win_prob FLOAT NOT NULL,
    away_win_prob FLOAT NOT NULL,
    predicted_winner VARCHAR NOT NULL,
    confidence FLOAT NOT NULL,
    model_name VARCHAR NOT NULL,
    model_version VARCHAR,
    config_version VARCHAR,
    commit_hash VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    INDEX idx_game (game_id),
    INDEX idx_date (prediction_date),
    INDEX idx_confidence (confidence)
);
```

**3. teams** (new - canonical team registry)
```sql
CREATE TABLE teams (
    team_id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR NOT NULL UNIQUE,
    display_name VARCHAR NOT NULL,
    conference VARCHAR,
    division VARCHAR,  -- 'D1', 'D2', 'D3'
    espn_team_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conference (conference)
);
```

**4. team_features** (replaces feature_store.csv)
```sql
CREATE TABLE team_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id VARCHAR NOT NULL,
    season VARCHAR NOT NULL,
    games_played INTEGER NOT NULL,
    rolling_win_pct_5 FLOAT,
    rolling_win_pct_10 FLOAT,
    rolling_point_diff_avg_5 FLOAT,
    rolling_point_diff_avg_10 FLOAT,
    win_pct_last5_vs10 FLOAT,
    point_diff_last5_vs10 FLOAT,
    recent_strength_index_5 FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE(team_id, season),
    INDEX idx_team_season (team_id, season)
);
```

**5. bets** (new - betting tracking)
```sql
CREATE TABLE bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id VARCHAR NOT NULL,
    prediction_id INTEGER NOT NULL,
    bet_team VARCHAR NOT NULL,
    bet_amount FLOAT NOT NULL DEFAULT 1.0,
    moneyline INTEGER NOT NULL,
    confidence FLOAT NOT NULL,
    value_score FLOAT,
    bet_won BOOLEAN,
    payout FLOAT,
    profit FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (prediction_id) REFERENCES predictions(id),
    INDEX idx_game (game_id),
    INDEX idx_settled (settled_at),
    INDEX idx_confidence (confidence)
);
```

**6. accuracy_metrics** (replaces Accuracy_Report.csv)
```sql
CREATE TABLE accuracy_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    total_predictions INTEGER NOT NULL,
    correct_predictions INTEGER NOT NULL,
    accuracy FLOAT NOT NULL,
    avg_confidence FLOAT,
    high_conf_accuracy FLOAT,
    low_conf_accuracy FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_date (date)
);
```

**7. drift_metrics** (replaces Drift_Metrics.csv + Drift_Metrics_By_Team.csv)
```sql
CREATE TABLE drift_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    team_id VARCHAR,  -- NULL for global metrics
    metric_type VARCHAR NOT NULL,  -- 'global', 'team', 'conference'
    rolling_accuracy FLOAT,
    cumulative_accuracy FLOAT,
    accuracy_delta FLOAT,
    games_in_window INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    INDEX idx_date_team (metric_date, team_id),
    INDEX idx_type (metric_type)
);
```

### Database Choice: DuckDB vs SQLite

#### **Recommendation: DuckDB**

**DuckDB Advantages:**
- ✅ Optimized for analytics (OLAP workload)
- ✅ Vectorized execution (10-100x faster for aggregations)
- ✅ Native pandas integration (`df.to_sql()`, `con.execute().df()`)
- ✅ Efficient for large scans (30K+ games)
- ✅ Better for time-series queries (rolling windows, aggregations)
- ✅ Parquet export for efficient backups
- ✅ ACID transactions
- ❌ Newer technology (less mature than SQLite)

**SQLite Advantages:**
- ✅ Extremely mature and stable
- ✅ Ubiquitous support
- ✅ Better for write-heavy workloads
- ✅ Simpler deployment (single file)
- ❌ Slower for analytics queries
- ❌ No vectorized execution
- ❌ Less optimized for aggregations

**Decision: Start with DuckDB, provide SQLite fallback**

---

## 🔄 Migration Strategy

### Phase 1: Database Layer (Week 1)

#### 1.1 Database Abstraction Layer
```
backend/
├── database/
│   ├── __init__.py
│   ├── connection.py         # Connection manager
│   ├── schema.py             # Table definitions
│   ├── migrations.py         # Schema versioning
│   └── models.py             # ORM models (optional)
├── repositories/             # Data access layer
│   ├── __init__.py
│   ├── game_repository.py
│   ├── prediction_repository.py
│   ├── team_repository.py
│   ├── bet_repository.py
│   └── analytics_repository.py
└── services/                 # Business logic
    ├── __init__.py
    ├── prediction_service.py
    ├── betting_service.py
    └── analytics_service.py
```

#### 1.2 CSV to Database Migration Script
```python
# scripts/migrate_csv_to_db.py
"""
One-time migration script to import all CSV data into database.
- Validates data integrity
- Handles duplicates
- Creates indexes
- Generates migration report
"""
```

#### 1.3 Dual-Mode Operation (Transition Period)
- Read from database, write to both DB + CSV (backup)
- Feature flag: `USE_DATABASE=true` in config
- Gradual cutover per module

### Phase 2: Backend API (Week 2)

#### 2.1 FastAPI Application Structure
```
backend/
├── api/
│   ├── __init__.py
│   ├── main.py               # FastAPI app
│   ├── dependencies.py       # Dependency injection
│   └── routes/
│       ├── __init__.py
│       ├── games.py          # GET /api/games
│       ├── predictions.py    # GET /api/predictions
│       ├── teams.py          # GET /api/teams
│       ├── bets.py           # GET /api/bets
│       ├── analytics.py      # GET /api/analytics
│       └── health.py         # GET /api/health
├── schemas/                  # Pydantic models
│   ├── __init__.py
│   ├── game.py
│   ├── prediction.py
│   ├── team.py
│   └── bet.py
└── middleware/
    ├── __init__.py
    ├── cors.py
    └── rate_limit.py
```

#### 2.2 Key API Endpoints

**Games**
```
GET  /api/games                    # List games (paginated)
GET  /api/games/{game_id}          # Get game details
GET  /api/games/upcoming           # Upcoming games
GET  /api/games/today              # Today's games
GET  /api/games/by-date/{date}     # Games by date
```

**Predictions**
```
GET  /api/predictions                      # List predictions
GET  /api/predictions/{prediction_id}      # Get prediction details
GET  /api/predictions/game/{game_id}       # Predictions for game
GET  /api/predictions/today                # Today's predictions
GET  /api/predictions/high-confidence      # High confidence picks
```

**Betting**
```
GET  /api/bets                     # List bets (paginated)
GET  /api/bets/summary             # Overall betting stats
GET  /api/bets/by-confidence       # Performance by confidence level
GET  /api/bets/value-plays         # Best value opportunities
GET  /api/bets/streak              # Current streak stats
```

**Teams**
```
GET  /api/teams                    # List teams
GET  /api/teams/{team_id}          # Team details
GET  /api/teams/{team_id}/stats    # Team statistics
GET  /api/teams/{team_id}/history  # Historical performance
```

**Analytics**
```
GET  /api/analytics/accuracy       # Accuracy metrics over time
GET  /api/analytics/drift          # Drift detection metrics
GET  /api/analytics/features       # Feature importance
GET  /api/analytics/performance    # Overall performance dashboard
```

### Phase 3: Web Frontend (Week 3-4)

#### 3.1 Tech Stack
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: TailwindCSS
- **UI Components**: shadcn/ui
- **Icons**: Lucide React
- **Charts**: Recharts
- **State Management**: React Query (TanStack Query)
- **Routing**: React Router
- **Date Handling**: date-fns

#### 3.2 Application Structure
```
frontend/
├── public/
│   ├── index.html
│   └── favicon.ico
├── src/
│   ├── main.tsx              # Entry point
│   ├── App.tsx               # Root component
│   ├── components/
│   │   ├── ui/               # shadcn/ui components
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   ├── games/
│   │   │   ├── GameCard.tsx
│   │   │   ├── GameList.tsx
│   │   │   ├── GameDetails.tsx
│   │   │   └── GameFilters.tsx
│   │   ├── predictions/
│   │   │   ├── PredictionCard.tsx
│   │   │   ├── PredictionsList.tsx
│   │   │   ├── ConfidenceMeter.tsx
│   │   │   └── ProbabilityChart.tsx
│   │   ├── betting/
│   │   │   ├── BetCard.tsx
│   │   │   ├── BettingSummary.tsx
│   │   │   ├── ValueBets.tsx
│   │   │   └── BettingHistory.tsx
│   │   ├── analytics/
│   │   │   ├── AccuracyChart.tsx
│   │   │   ├── DriftChart.tsx
│   │   │   ├── PerformanceMetrics.tsx
│   │   │   └── FeatureImportance.tsx
│   │   └── teams/
│   │       ├── TeamCard.tsx
│   │       ├── TeamStats.tsx
│   │       └── TeamHistory.tsx
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── Games.tsx
│   │   ├── Predictions.tsx
│   │   ├── Betting.tsx
│   │   ├── Analytics.tsx
│   │   └── Teams.tsx
│   ├── hooks/
│   │   ├── useGames.ts
│   │   ├── usePredictions.ts
│   │   ├── useBets.ts
│   │   └── useAnalytics.ts
│   ├── services/
│   │   └── api.ts            # API client
│   ├── types/
│   │   ├── game.ts
│   │   ├── prediction.ts
│   │   ├── bet.ts
│   │   └── team.ts
│   ├── utils/
│   │   ├── formatting.ts
│   │   ├── calculations.ts
│   │   └── constants.ts
│   └── styles/
│       └── globals.css
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

#### 3.3 Key Features & Pages

**Home Page**
- Live predictions dashboard
- Today's top picks
- Quick stats (accuracy, ROI, streak)
- Recent performance chart
- High-confidence game cards

**Games Page**
- Filterable game list (date, team, conference)
- Search functionality
- Game cards with predictions
- Detailed game view (modal/page)
- Moneyline odds display

**Predictions Page**
- All predictions (paginated)
- Filter by confidence level
- Sort by date/confidence/value
- Prediction accuracy tracking
- Historical prediction analysis

**Betting Page** (REBUILT FROM SCRATCH)
- Overall betting stats dashboard
- Today's recommended bets
- Value plays (high EV bets)
- Safest bets (high confidence)
- Betting history table
- Performance by confidence level
- ROI tracking chart
- Win/loss streak indicator

**Analytics Page**
- Accuracy over time chart
- Drift detection visualizations
- Feature importance charts
- Performance metrics grid
- Confidence calibration curve
- Conference performance breakdown

**Teams Page**
- Team directory
- Team detail view
- Historical performance
- Recent form chart
- Head-to-head records

#### 3.4 Design System

**Color Scheme (Sports Betting Theme)**
```css
:root {
  --primary: 220 70% 50%;      /* Blue */
  --success: 142 76% 36%;      /* Green (wins) */
  --danger: 0 84% 60%;         /* Red (losses) */
  --warning: 45 93% 47%;       /* Orange (medium confidence) */
  --background: 240 10% 3.9%;  /* Dark background */
  --foreground: 0 0% 98%;      /* Light text */
  --card: 240 10% 8%;          /* Card background */
  --muted: 240 5% 34%;         /* Muted text */
}
```

**Component Styling**
- Glass morphism effects for cards
- Gradient backgrounds for hero sections
- Animated confidence meters
- Interactive charts with tooltips
- Responsive grid layouts
- Mobile-first design

### Phase 4: GitHub Pages Deployment (Week 4)

#### 4.1 Static Site Generation Strategy

**Challenge**: GitHub Pages only supports static files, but we need API data.

**Solution**: Hybrid Approach
1. **Pre-build Static Data**: Generate JSON files during GitHub Actions
2. **Client-side Hydration**: Frontend loads JSON files
3. **Daily Updates**: GitHub Actions rebuilds site daily

#### 4.2 Build Process
```yaml
# .github/workflows/deploy-webapp.yml
name: Deploy Web App

on:
  schedule:
    - cron: '0 12 * * *'  # Daily at noon UTC
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run data pipeline
        run: python daily_pipeline.py
      
      - name: Export database to JSON
        run: python scripts/export_db_to_json.py
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Build frontend
        run: |
          cd frontend
          npm install
          npm run build
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./frontend/dist
```

#### 4.3 JSON Export Structure
```
frontend/public/data/
├── games_today.json           # Today's games
├── games_upcoming.json        # Next 7 days
├── predictions_today.json     # Today's predictions
├── predictions_all.json       # Last 30 days predictions
├── betting_summary.json       # Overall betting stats
├── betting_history.json       # Recent betting results
├── accuracy_metrics.json      # Accuracy over time
├── drift_metrics.json         # Drift detection data
├── teams.json                 # Team directory
└── metadata.json              # Last update time, version
```

#### 4.4 Client-side Data Loading
```typescript
// services/api.ts
const API_BASE = import.meta.env.PROD 
  ? 'https://jgamblin.github.io/NCAA-Prediction/data'
  : 'http://localhost:3000/api';

export const fetchGamesToday = async () => {
  const response = await fetch(`${API_BASE}/games_today.json`);
  return response.json();
};
```

---

## 🔧 Betting Flow Rebuild

### Current Betting Flow Issues
1. **Scattered Logic**: Betting logic spread across multiple files
2. **CSV Dependencies**: Reads from 5+ different CSV files
3. **Inefficient Joins**: Manual pandas merges for every calculation
4. **No History Tracking**: Limited betting history analysis
5. **Slow Aggregations**: Recalculates stats from scratch each time

### New Database-Backed Betting Flow

#### 1. Bet Creation (Automated)
```python
# services/betting_service.py
class BettingService:
    def create_bets_for_predictions(self, predictions: List[Prediction]):
        """
        Automatically create bets for predictions with moneylines.
        Only bet on games with bettable odds (not -1000+).
        """
        bets = []
        for pred in predictions:
            game = self.game_repo.get_by_id(pred.game_id)
            
            # Determine bet team and moneyline
            if pred.predicted_winner == game.home_team:
                moneyline = game.home_moneyline
            else:
                moneyline = game.away_moneyline
            
            # Skip if no moneyline or unbettable
            if not moneyline or moneyline < -1000:
                continue
            
            # Calculate value score
            value_score = self.calculate_value_score(
                pred.confidence, moneyline
            )
            
            bet = Bet(
                game_id=pred.game_id,
                prediction_id=pred.id,
                bet_team=pred.predicted_winner,
                bet_amount=1.0,
                moneyline=moneyline,
                confidence=pred.confidence,
                value_score=value_score
            )
            
            bets.append(bet)
        
        self.bet_repo.create_many(bets)
        return bets
```

#### 2. Bet Settlement (Automated)
```python
def settle_bets(self):
    """
    Settle pending bets for completed games.
    Runs automatically after game completion.
    """
    unsettled = self.bet_repo.get_unsettled()
    
    for bet in unsettled:
        game = self.game_repo.get_by_id(bet.game_id)
        
        if game.game_status != 'Final':
            continue
        
        # Determine winner
        actual_winner = (
            game.home_team 
            if game.home_score > game.away_score 
            else game.away_team
        )
        
        # Calculate result
        bet.bet_won = (bet.bet_team == actual_winner)
        
        if bet.bet_won:
            bet.payout = self.calculate_payout(
                bet.moneyline, bet.bet_amount
            )
            bet.profit = bet.payout - bet.bet_amount
        else:
            bet.payout = 0
            bet.profit = -bet.bet_amount
        
        bet.settled_at = datetime.now()
        
        self.bet_repo.update(bet)
```

#### 3. Betting Analytics (Optimized Queries)
```python
def get_betting_summary(self, season: str = None):
    """
    Get overall betting performance.
    Single database query instead of multiple CSV loads.
    """
    query = """
    SELECT 
        COUNT(*) as total_bets,
        SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN bet_won THEN 0 ELSE 1 END) as losses,
        ROUND(AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END), 3) as win_rate,
        SUM(bet_amount) as total_wagered,
        SUM(payout) as total_payout,
        SUM(profit) as total_profit,
        ROUND(SUM(profit) / SUM(bet_amount), 3) as roi
    FROM bets
    WHERE settled_at IS NOT NULL
    """
    
    if season:
        query += f" AND game_id IN (SELECT game_id FROM games WHERE season = '{season}')"
    
    return self.db.execute(query).fetchone()
```

#### 4. Value Bet Identification
```python
def get_value_bets(self, min_value_score: float = 0.1):
    """
    Find bets with positive expected value.
    """
    query = """
    SELECT 
        b.*,
        g.home_team,
        g.away_team,
        g.date,
        p.confidence
    FROM bets b
    JOIN games g ON b.game_id = g.game_id
    JOIN predictions p ON b.prediction_id = p.id
    WHERE 
        b.settled_at IS NULL
        AND b.value_score >= ?
        AND g.game_status = 'Scheduled'
    ORDER BY b.value_score DESC
    LIMIT 20
    """
    
    return self.db.execute(query, [min_value_score]).fetchall()
```

#### 5. Performance by Confidence Level
```python
def get_performance_by_confidence(self):
    """
    Analyze betting performance across confidence ranges.
    """
    query = """
    SELECT 
        CASE 
            WHEN confidence >= 0.9 THEN '90%+'
            WHEN confidence >= 0.8 THEN '80-90%'
            WHEN confidence >= 0.7 THEN '70-80%'
            WHEN confidence >= 0.6 THEN '60-70%'
            ELSE '50-60%'
        END as confidence_range,
        COUNT(*) as bets,
        SUM(CASE WHEN bet_won THEN 1 ELSE 0 END) as wins,
        ROUND(AVG(CASE WHEN bet_won THEN 1.0 ELSE 0.0 END), 3) as win_rate,
        SUM(profit) as profit,
        ROUND(SUM(profit) / SUM(bet_amount), 3) as roi
    FROM bets
    WHERE settled_at IS NOT NULL
    GROUP BY confidence_range
    ORDER BY MIN(confidence) DESC
    """
    
    return self.db.execute(query).fetchall()
```

---

## 📋 Implementation Checklist

### Week 1: Database Foundation
- [ ] Choose database (DuckDB recommended)
- [ ] Design and create schema
- [ ] Write database abstraction layer
- [ ] Create repository pattern classes
- [ ] Write CSV migration script
- [ ] Test data integrity after migration
- [ ] Create dual-mode operation flag
- [ ] Update daily_pipeline.py to use database

### Week 2: Backend API
- [ ] Setup FastAPI application
- [ ] Create API routes and endpoints
- [ ] Write Pydantic schemas
- [ ] Implement CORS middleware
- [ ] Add API documentation (Swagger)
- [ ] Create health check endpoints
- [ ] Test API endpoints locally
- [ ] Setup API versioning

### Week 3: Frontend Development
- [ ] Initialize React + Vite project
- [ ] Setup TailwindCSS + shadcn/ui
- [ ] Create component library
- [ ] Build page layouts
- [ ] Implement routing
- [ ] Connect to API/JSON data
- [ ] Add responsive design
- [ ] Implement dark/light themes

### Week 4: Betting Flow Rebuild
- [ ] Refactor betting_tracker.py to use database
- [ ] Implement BettingService class
- [ ] Create bet settlement automation
- [ ] Build betting analytics queries
- [ ] Add value bet identification
- [ ] Create betting history views
- [ ] Test betting calculations

### Week 5: Deployment & Testing
- [ ] Setup GitHub Actions workflow
- [ ] Create JSON export script
- [ ] Configure GitHub Pages
- [ ] Test static site deployment
- [ ] Performance optimization
- [ ] Mobile responsiveness testing
- [ ] Cross-browser testing
- [ ] Documentation updates

---

## 🎨 UI/UX Design Mockups

### Home Page
```
┌─────────────────────────────────────────────────────┐
│  NCAA Basketball Predictions                  🌙   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │  📊 Quick Stats                               │ │
│  │  ┌──────────┬──────────┬──────────┬─────────┐ │ │
│  │  │ 77.1%    │  $127.50 │   5 🔥   │  30,706 │ │ │
│  │  │ Accuracy │  Profit  │  Streak  │  Games  │ │ │
│  │  └──────────┴──────────┴──────────┴─────────┘ │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │  🎯 Today's Top Picks                         │ │
│  │                                               │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │ 🏀 Duke vs UNC                          │ │ │
│  │  │ Duke to win • 87% confidence           │ │ │
│  │  │ Moneyline: -150 • Value Score: 0.23    │ │ │
│  │  │ [View Details]                          │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  │                                               │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │ 🏀 Kansas vs Kentucky                   │ │ │
│  │  │ Kansas to win • 82% confidence         │ │ │
│  │  │ Moneyline: +120 • Value Score: 0.45    │ │ │
│  │  │ [View Details]                          │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │  📈 Recent Performance                        │ │
│  │  [Accuracy Line Chart - Last 30 Days]        │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Betting Page
```
┌─────────────────────────────────────────────────────┐
│  💰 Betting Dashboard                               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌────────────────┬────────────────┬──────────────┐ │
│  │ Win Rate       │ Total Profit   │ ROI          │ │
│  │ 64.2% ✅       │ +$127.50 📈    │ 8.3% 🎯      │ │
│  └────────────────┴────────────────┴──────────────┘ │
│                                                     │
│  🌟 Value Plays (High EV)                          │
│  ┌──────────────────────────────────────────────┐  │
│  │ Game          Bet    ML    Conf   Value  Win │  │
│  ├──────────────────────────────────────────────┤  │
│  │ Duke vs UNC   Duke  -150   87%   0.45   ✓   │  │
│  │ Kansas vs UK  Kansas +120  82%   0.38   ✓   │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  🛡️ Safest Bets (High Confidence)                  │
│  ┌──────────────────────────────────────────────┐  │
│  │ Game          Bet      ML    Conf   Win      │  │
│  ├──────────────────────────────────────────────┤  │
│  │ Duke vs UNC   Duke    -150   92%    ✓       │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  📊 Performance by Confidence                      │
│  [Bar Chart: Confidence Range vs Win Rate]        │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Performance Improvements

### Expected Performance Gains

| Operation | Current (CSV) | With Database | Improvement |
|-----------|---------------|---------------|-------------|
| Load historical games | ~2-3 seconds | ~50-100ms | **20-60x faster** |
| Calculate betting stats | ~5-10 seconds | ~100-200ms | **25-50x faster** |
| Accuracy aggregations | ~3-5 seconds | ~50-100ms | **30-50x faster** |
| Feature store queries | ~2-4 seconds | ~50-150ms | **15-30x faster** |
| Generate reports | ~15-30 seconds | ~1-3 seconds | **10-15x faster** |

### Memory Reduction
- Current: Loads entire CSV into memory (30K+ rows, ~50-100MB)
- With DB: Loads only needed rows (~1-10MB for typical queries)
- **Reduction: 80-90% less memory usage**

---

## 📚 Dependencies to Add

### Backend (Python)
```txt
# requirements.txt additions
duckdb>=0.9.0          # Database engine
fastapi>=0.104.0       # API framework
uvicorn>=0.24.0        # ASGI server
pydantic>=2.5.0        # Data validation
python-multipart       # File uploads
sqlalchemy>=2.0.0      # ORM (optional)
alembic>=1.12.0        # Migrations (optional)
```

### Frontend (Node.js)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.12.0",
    "axios": "^1.6.0",
    "date-fns": "^2.30.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.294.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.3.6",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

---

## 🔍 Testing Strategy

### Database Testing
- Unit tests for repository methods
- Integration tests for service layer
- Migration validation tests
- Performance benchmarks (CSV vs DB)
- Data integrity tests

### API Testing
- Unit tests for endpoints
- Integration tests for full flows
- Load testing (concurrent requests)
- API contract tests

### Frontend Testing
- Component unit tests (Vitest)
- Integration tests (Cypress/Playwright)
- Visual regression tests
- Mobile responsiveness tests
- Accessibility tests (WCAG AA)

### End-to-End Testing
- Daily pipeline with database
- Betting flow from prediction → settlement
- Frontend data loading
- GitHub Pages deployment

---

## 📝 Documentation Updates

### New Documentation
- [ ] Database schema documentation
- [ ] API endpoint documentation (Swagger/OpenAPI)
- [ ] Frontend component storybook
- [ ] Deployment guide for GitHub Pages
- [ ] Migration guide (CSV → Database)
- [ ] Developer setup guide

### Updated Documentation
- [ ] README.md (new architecture)
- [ ] CONTRIBUTING.md
- [ ] Architecture diagrams
- [ ] Data flow diagrams

---

## 🎯 Success Metrics

### Performance Metrics
- [ ] Database query times < 200ms for 95th percentile
- [ ] API response times < 500ms for 95th percentile
- [ ] Frontend initial load < 3 seconds
- [ ] Lighthouse score > 90 (Performance, Accessibility, Best Practices)

### Functional Metrics
- [ ] All existing features working with database
- [ ] Betting calculations match CSV implementation
- [ ] Zero data loss during migration
- [ ] Daily pipeline completes successfully

### User Experience Metrics
- [ ] Mobile-responsive on all screen sizes
- [ ] Dark/light theme support
- [ ] Accessible to screen readers
- [ ] Fast navigation (no loading spinners > 1s)

---

## 🚨 Risk Mitigation

### Risks & Mitigation Strategies

1. **Data Loss During Migration**
   - Mitigation: Keep CSV files as backup, validate all data post-migration
   
2. **Performance Regression**
   - Mitigation: Benchmark before/after, optimize queries, add indexes
   
3. **Breaking Changes**
   - Mitigation: Dual-mode operation during transition, feature flags
   
4. **GitHub Pages Limitations**
   - Mitigation: Static JSON export, client-side hydration, CDN caching
   
5. **Database File Size**
   - Mitigation: Regular vacuuming, archiving old data, Parquet backups

---

## 📅 Timeline Summary

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | Database Layer | Schema, migration script, repository pattern |
| 2 | Backend API | FastAPI app, endpoints, documentation |
| 3 | Frontend | React app, components, pages |
| 4 | Betting Flow | Refactored betting logic, analytics |
| 5 | Deployment | GitHub Actions, JSON export, testing |

**Total Estimated Time**: 5 weeks (full-time) or 10 weeks (part-time)

---

## 🎉 Next Steps

1. **Review this plan** - Adjust based on priorities and constraints
2. **Setup development environment** - Install dependencies
3. **Create database schema** - Start with `backend/database/schema.py`
4. **Run migration** - Convert CSV → Database
5. **Test queries** - Validate performance improvements
6. **Start frontend** - Initialize React project
7. **Iterate** - Build incrementally, test continuously

---

**Questions? Concerns? Suggestions?**

This is a living document. Update as the project evolves.
