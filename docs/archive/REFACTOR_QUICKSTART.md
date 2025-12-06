# Refactor Quick Start Guide

Get started with the database migration and web frontend development.

---

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies

#### Python Backend
```bash
# Install new dependencies
pip install duckdb fastapi uvicorn pydantic

# Or update requirements.txt and install all
pip install -r requirements.txt
```

#### Frontend (Optional - for local development)
```bash
# Initialize frontend project
cd frontend  # We'll create this
npm init -y
npm install react react-dom react-router-dom
npm install -D vite @vitejs/plugin-react typescript
npm install @tanstack/react-query axios recharts lucide-react
npm install -D tailwindcss postcss autoprefixer
npm install class-variance-authority clsx tailwind-merge
```

### 2. Create Database

```bash
# Run the migration script (we'll create this)
python scripts/migrate_csv_to_db.py

# This will:
# - Create ncaa_predictions.duckdb
# - Import all CSV data
# - Create indexes
# - Validate data integrity
```

### 3. Test Database Queries

```bash
# Open DuckDB CLI
python -c "import duckdb; con = duckdb.connect('data/ncaa_predictions.duckdb'); print(con.execute('SELECT COUNT(*) FROM games').fetchone())"

# Expected output: (30706,) or similar
```

---

## 📊 Database Quick Reference

### Connection

#### Python
```python
import duckdb

# Connect to database
con = duckdb.connect('data/ncaa_predictions.duckdb')

# Query example
df = con.execute("""
    SELECT * FROM games 
    WHERE date = CURRENT_DATE
""").df()

print(df.head())
```

#### DuckDB CLI
```bash
# Open interactive shell
duckdb data/ncaa_predictions.duckdb

# Run queries
SELECT COUNT(*) FROM games;
SELECT * FROM vw_games_today;
.exit
```

### Common Queries

#### Get today's games with predictions
```sql
SELECT 
    g.home_team,
    g.away_team,
    g.home_moneyline,
    g.away_moneyline,
    p.home_win_prob,
    p.confidence,
    p.predicted_winner
FROM games g
JOIN predictions p ON g.game_id = p.game_id
WHERE g.date = CURRENT_DATE
ORDER BY p.confidence DESC;
```

#### Get betting summary
```sql
SELECT * FROM vw_betting_summary;
```

#### Get recent accuracy
```sql
SELECT 
    date,
    accuracy,
    total_predictions,
    correct_predictions
FROM accuracy_metrics
WHERE date >= CURRENT_DATE - INTERVAL 7 DAY
ORDER BY date DESC;
```

---

## 🏗️ Directory Structure (New)

```
NCAA-Prediction/
├── backend/                   # NEW: Backend API layer
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py      # Database connection manager
│   │   ├── schema.py          # Table definitions (Python)
│   │   └── migrations.py      # Migration utilities
│   ├── repositories/          # Data access layer
│   │   ├── __init__.py
│   │   ├── game_repository.py
│   │   ├── prediction_repository.py
│   │   ├── team_repository.py
│   │   └── bet_repository.py
│   ├── services/              # Business logic
│   │   ├── __init__.py
│   │   ├── prediction_service.py
│   │   └── betting_service.py
│   ├── api/                   # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes/
│   │       ├── games.py
│   │       ├── predictions.py
│   │       ├── bets.py
│   │       └── analytics.py
│   └── schemas/               # Pydantic models
│       ├── game.py
│       ├── prediction.py
│       └── bet.py
├── frontend/                  # NEW: React web application
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── services/
│   ├── package.json
│   └── vite.config.ts
├── scripts/
│   ├── migrate_csv_to_db.py   # NEW: Migration script
│   ├── export_db_to_json.py   # NEW: JSON export for GitHub Pages
│   └── validate_migration.py  # NEW: Data validation
├── data/
│   ├── ncaa_predictions.duckdb  # NEW: Database file
│   └── [existing CSV files]     # Keep as backup
├── database_schema.sql        # NEW: Database schema
├── REFACTOR_PLAN.md          # NEW: Detailed plan
└── REFACTOR_QUICKSTART.md    # NEW: This file
```

---

## 🧪 Testing the Database

### Validate Migration

```bash
# Run validation script
python scripts/validate_migration.py

# Expected output:
# ✓ Games: 30,706 rows match
# ✓ Predictions: 1,542 rows match
# ✓ Teams: 1,907 rows match
# ✓ All foreign keys valid
# ✓ No duplicate game_ids
# Migration successful!
```

### Performance Comparison

```bash
# Benchmark CSV vs Database
python scripts/benchmark_performance.py

# Expected output:
# CSV Load Time: 2.34 seconds
# DB Load Time: 0.08 seconds
# Speedup: 29.25x
```

---

## 🔧 Development Workflow

### Daily Development Loop

1. **Make schema changes**
   ```bash
   # Edit database_schema.sql
   # Run migration
   python scripts/migrate_csv_to_db.py --reset
   ```

2. **Update backend code**
   ```bash
   # Edit repository/service files
   # Test queries
   python -m pytest tests/backend/
   ```

3. **Run local API server**
   ```bash
   cd backend
   uvicorn api.main:app --reload
   # Visit http://localhost:8000/docs for API documentation
   ```

4. **Develop frontend**
   ```bash
   cd frontend
   npm run dev
   # Visit http://localhost:5173
   ```

### Testing Changes

```bash
# Backend tests
pytest tests/backend/

# Frontend tests
cd frontend
npm test

# Integration tests
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/
```

---

## 🐛 Troubleshooting

### Issue: Migration fails with "table already exists"
```bash
# Solution: Drop all tables and re-run
python scripts/migrate_csv_to_db.py --reset
```

### Issue: Database file locked
```bash
# Solution: Close all connections
pkill -f duckdb
rm data/ncaa_predictions.duckdb-wal  # Remove write-ahead log
```

### Issue: Slow queries
```bash
# Solution: Analyze and optimize
duckdb data/ncaa_predictions.duckdb
> PRAGMA explain_output='all';
> EXPLAIN SELECT * FROM games WHERE date = '2024-12-01';
> -- Look for missing indexes
```

### Issue: Memory usage too high
```python
# Solution: Limit memory in connection
import duckdb
con = duckdb.connect('data/ncaa_predictions.duckdb')
con.execute("PRAGMA memory_limit='2GB'")
con.execute("PRAGMA threads=2")
```

---

## 📚 Useful Commands

### Database Management

```bash
# Backup database
cp data/ncaa_predictions.duckdb data/ncaa_predictions.duckdb.backup

# Export to CSV
python scripts/export_db_to_csv.py

# Export to Parquet (efficient)
python -c "import duckdb; con = duckdb.connect('data/ncaa_predictions.duckdb'); con.execute(\"COPY games TO 'data/games.parquet'\")"

# Vacuum (reclaim space)
python -c "import duckdb; con = duckdb.connect('data/ncaa_predictions.duckdb'); con.execute('VACUUM')"
```

### API Development

```bash
# Start API server
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Test API endpoint
curl http://localhost:8000/api/games/today

# View API docs (Swagger UI)
open http://localhost:8000/docs

# View alternative API docs (ReDoc)
open http://localhost:8000/redoc
```

### Frontend Development

```bash
# Start dev server
cd frontend
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Lint code
npm run lint
```

---

## 🎯 Next Steps

### Phase 1: Database (This Week)
1. ✅ Review REFACTOR_PLAN.md
2. ✅ Create database schema
3. ⏳ Create migration script
4. ⏳ Run migration and validate
5. ⏳ Update daily_pipeline.py to use database

### Phase 2: Backend API (Next Week)
1. ⏳ Setup FastAPI application
2. ⏳ Create repository layer
3. ⏳ Build API endpoints
4. ⏳ Write API tests

### Phase 3: Frontend (Week 3-4)
1. ⏳ Initialize React project
2. ⏳ Setup UI component library
3. ⏳ Build core pages
4. ⏳ Connect to API

### Phase 4: Deployment (Week 5)
1. ⏳ Setup GitHub Actions
2. ⏳ Create JSON export
3. ⏳ Deploy to GitHub Pages

---

## 📖 Additional Resources

### Documentation
- [DuckDB Documentation](https://duckdb.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [TailwindCSS Documentation](https://tailwindcss.com/)
- [shadcn/ui Documentation](https://ui.shadcn.com/)

### Examples
- See `examples/` directory for code samples
- Review `tests/` for usage patterns
- Check `backend/api/main.py` for API structure

### Getting Help
- Review REFACTOR_PLAN.md for detailed architecture
- Check database_schema.sql for table definitions
- Open an issue for questions or problems

---

## 🎉 Ready to Start?

```bash
# 1. Create migration script
python scripts/migrate_csv_to_db.py

# 2. Test queries
python -c "import duckdb; print(duckdb.connect('data/ncaa_predictions.duckdb').execute('SELECT COUNT(*) FROM games').fetchone())"

# 3. Start building!
code .  # Open in VS Code
```

**Happy coding! 🚀**
