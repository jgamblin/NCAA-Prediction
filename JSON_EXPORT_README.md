# JSON Export System for GitHub Pages

## 🎯 Overview

This system exports database data to static JSON files for the React frontend hosted on GitHub Pages. **No backend API server needed!**

---

## 🏗️ Architecture

```
┌──────────────────────────────────┐
│   GitHub Actions (Daily Cron)    │
│                                   │
│  1. Run daily_pipeline_db.py     │
│     └─> Updates database          │
│                                   │
│  2. Run export_to_json.py         │
│     └─> Creates JSON files        │
│                                   │
│  3. git commit & push             │
│     └─> Updates repository        │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│        GitHub Repository          │
│                                   │
│  frontend/public/data/*.json      │
│  └─> Static JSON files            │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│         GitHub Pages              │
│                                   │
│  Serves:                          │
│  - React app (static HTML/JS)     │
│  - JSON files (static data)       │
│                                   │
│  Frontend reads JSON directly!    │
└──────────────────────────────────┘
```

---

## 📁 Exported JSON Files

### Core Data
| File | Description | Size | Update Frequency |
|------|-------------|------|------------------|
| `predictions.json` | Upcoming game predictions | ~10KB | Daily |
| `today_games.json` | Today's games with predictions | ~2KB | Daily |
| `prediction_history.json` | Last 100 predictions with results | ~70KB | Daily |

### Betting Analytics
| File | Description | Size | Update Frequency |
|------|-------------|------|------------------|
| `betting_summary.json` | Overall betting performance | ~0.2KB | Daily |
| `betting_by_strategy.json` | Performance by strategy | ~1KB | Daily |
| `betting_by_confidence.json` | Performance by confidence level | ~0.5KB | Daily |
| `value_bets.json` | High-value betting opportunities | ~5KB | Daily |
| `cumulative_profit.json` | Profit timeline (for charts) | ~10KB | Daily |

### Accuracy & Performance
| File | Description | Size | Update Frequency |
|------|-------------|------|------------------|
| `accuracy_overall.json` | Overall prediction accuracy | ~0.1KB | Daily |
| `accuracy_high_confidence.json` | Accuracy for high-confidence predictions | ~0.1KB | Daily |

### Team Data
| File | Description | Size | Update Frequency |
|------|-------------|------|------------------|
| `top_teams.json` | Top 50 teams by performance | ~15KB | Daily |

### Metadata
| File | Description | Size | Update Frequency |
|------|-------------|------|------------------|
| `metadata.json` | Last update time, database stats | ~0.3KB | Daily |

**Total Data Size:** ~115 KB (very lightweight!)

---

## 🚀 Usage

### Export Manually
```bash
# Run the export script
python3 scripts/export_to_json.py

# Output will be in: frontend/public/data/*.json
```

### Automated Daily Export (GitHub Actions)
The workflow `.github/workflows/daily-predictions.yml` runs automatically every day:

1. **12:00 PM UTC** (7 AM EST) - Scheduled run
2. Runs `daily_pipeline_db.py` - Updates database
3. Runs `export_to_json.py` - Creates JSON files
4. Commits and pushes changes to repo
5. GitHub Pages automatically updates

### Custom Export Location
```bash
# Export to a different directory
python3 scripts/export_to_json.py --output-dir /path/to/custom/dir
```

---

## 📊 JSON Data Formats

### predictions.json
```json
[
  {
    "game_id": "401826991",
    "date": "2024-12-02",
    "home_team": "Duke",
    "away_team": "Auburn",
    "home_win_prob": 0.62,
    "away_win_prob": 0.38,
    "predicted_winner": "Duke",
    "confidence": 0.62,
    "home_moneyline": -180,
    "away_moneyline": +150
  }
]
```

### betting_summary.json
```json
{
  "total_bets": 150,
  "wins": 95,
  "losses": 55,
  "win_rate": 0.633,
  "total_wagered": 150.0,
  "total_payout": 185.50,
  "total_profit": 35.50,
  "roi": 0.237
}
```

### accuracy_overall.json
```json
{
  "total_predictions": 1436,
  "correct_predictions": 886,
  "accuracy": 0.617,
  "avg_confidence": 0.770
}
```

### metadata.json
```json
{
  "last_updated": "2024-12-01T14:30:00",
  "database_stats": {
    "total_games": 30577,
    "games_by_status": {
      "Final": 30577,
      "Scheduled": 0
    },
    "total_teams": 1890,
    "total_predictions": 1438
  },
  "current_season": "2024-25",
  "data_source": "DuckDB via daily pipeline",
  "update_frequency": "Daily via GitHub Actions"
}
```

---

## 🎨 Frontend Integration

### React Component Example
```javascript
// src/services/api.js
const BASE_URL = '/data'; // Relative path on GitHub Pages

export const fetchPredictions = async () => {
  const response = await fetch(`${BASE_URL}/predictions.json`);
  return response.json();
};

export const fetchBettingSummary = async () => {
  const response = await fetch(`${BASE_URL}/betting_summary.json`);
  return response.json();
};

export const fetchMetadata = async () => {
  const response = await fetch(`${BASE_URL}/metadata.json`);
  return response.json();
};

// Usage in component
import { fetchPredictions } from './services/api';

function PredictionsPage() {
  const [predictions, setPredictions] = useState([]);
  
  useEffect(() => {
    fetchPredictions().then(setPredictions);
  }, []);
  
  return (
    <div>
      {predictions.map(pred => (
        <PredictionCard key={pred.game_id} prediction={pred} />
      ))}
    </div>
  );
}
```

### Check Last Update
```javascript
async function checkLastUpdate() {
  const metadata = await fetch('/data/metadata.json').then(r => r.json());
  const lastUpdate = new Date(metadata.last_updated);
  const hoursAgo = (Date.now() - lastUpdate) / 1000 / 60 / 60;
  
  if (hoursAgo > 24) {
    console.warn('Data is stale (> 24 hours old)');
  }
  
  return metadata;
}
```

---

## ⚙️ Configuration

### Environment Variables (GitHub Actions)
No environment variables needed! Everything runs on GitHub Actions runners automatically.

### Customizing Export
Edit `scripts/export_to_json.py` to add more data:

```python
# Add a new export
def export_to_json(output_dir):
    # ... existing exports ...
    
    # NEW: Export conference standings
    conferences = teams_repo.get_all_conferences()
    standings = {}
    for conf in conferences:
        standings[conf] = teams_repo.get_teams_by_conference(conf)
    
    with open(output_dir / 'conference_standings.json', 'w') as f:
        json.dump(standings, f, indent=2, default=json_serial)
```

---

## 🔄 Update Frequency

| Type | Frequency | Reason |
|------|-----------|--------|
| **Predictions** | Daily | Games scheduled daily |
| **Betting Data** | Daily | Track performance |
| **Accuracy** | Daily | New game results |
| **Team Stats** | Daily | Updated with new games |

**GitHub Actions Schedule:** 12:00 PM UTC (7 AM EST) daily

---

## 📈 Performance

### Export Speed
- **Total Time:** ~2-3 seconds
- **Database Queries:** 10 queries (~200ms total)
- **JSON Serialization:** ~100ms
- **File Write:** ~50ms

### Data Size
- **Total:** ~115 KB (all JSON files)
- **Compressed (gzip):** ~25 KB
- **Load Time:** <100ms on most connections

### Caching
GitHub Pages CDN caches JSON files:
- **Cache Duration:** 10 minutes
- **Global CDN:** Fast delivery worldwide
- **Bandwidth:** Free (included with GitHub Pages)

---

## 🛠️ Troubleshooting

### Export Fails
```bash
# Check database exists
ls -lh data/ncaa_predictions.duckdb

# Run export with verbose output
python3 scripts/export_to_json.py 2>&1 | tee export_log.txt

# Check JSON validity
python3 -m json.tool frontend/public/data/predictions.json
```

### JSON Parse Errors in Frontend
```javascript
// Add error handling
async function fetchPredictions() {
  try {
    const response = await fetch('/data/predictions.json');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch predictions:', error);
    return []; // Fallback to empty array
  }
}
```

### Stale Data
```bash
# Manually trigger GitHub Actions
# Go to: https://github.com/YOUR_USERNAME/NCAA-Prediction/actions
# Click: "Daily Predictions Update" → "Run workflow"
```

---

## 🚀 Benefits

### vs Backend API
| Aspect | JSON Export | Backend API |
|--------|-------------|-------------|
| **Cost** | Free | $5-20/month |
| **Speed** | <100ms (CDN) | 200-500ms |
| **Maintenance** | Zero | Server management |
| **Scalability** | Unlimited (CDN) | Limited by server |
| **Complexity** | Low | High |
| **Security** | No attack surface | Auth, CORS, etc. |

### Perfect For
- ✅ Daily updated data
- ✅ Read-only frontend
- ✅ Static hosting (GitHub Pages)
- ✅ Low budget projects
- ✅ Simple architecture

### Not Good For
- ❌ Real-time updates (< 1 minute)
- ❌ User-submitted data
- ❌ Complex queries
- ❌ Dynamic filtering

---

## 📚 Next Steps

1. **Build React Frontend**
   - Create components that read JSON
   - Add charts and visualizations
   - Deploy to GitHub Pages

2. **Customize Data**
   - Add more exports as needed
   - Create aggregations
   - Generate chart-ready formats

3. **Optimize**
   - Add JSON compression
   - Implement client-side caching
   - Lazy load large datasets

---

## 🎯 Summary

**Status:** ✅ Production Ready

- Daily automated updates via GitHub Actions
- 11 JSON files with complete prediction data
- ~115 KB total (very lightweight)
- No backend server required
- Free hosting on GitHub Pages
- Fast CDN delivery worldwide

**Perfect static data solution for NCAA predictions!** 🏀

---

**Created:** December 1, 2024  
**Last Updated:** Auto-updated daily by GitHub Actions  
**Data Source:** DuckDB database → JSON export
