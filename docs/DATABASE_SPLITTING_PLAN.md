# Database Splitting Plan

## Current Issue

DuckDB file is **67.76 MB** - exceeds GitHub's 50 MB recommendation.

```
remote: warning: File data/ncaa_predictions.duckdb is 67.76 MB; 
this is larger than GitHub's recommended maximum file size of 50.00 MB
```

Even after removing 70% of duplicate predictions, the database is still too large for comfortable Git operations.

## Current Database Contents

```
Database: ncaa_predictions.duckdb (67.76 MB)
├─ games: ~10,000+ rows (historical + upcoming)
├─ predictions: 1,222 rows (after cleanup)
├─ teams: ~350+ D1 teams
├─ team_features: ~350+ team-seasons
├─ bets: betting records
├─ parlays: parlay records
├─ accuracy_metrics: performance tracking
└─ drift_metrics: model monitoring
```

## Proposed Solutions

### Option 1: Season-Based Split (Recommended)

**Structure:**
```
data/
├─ ncaa_predictions_2024_25.duckdb (historical, archived)
├─ ncaa_predictions_2025_26.duckdb (current season, active)
└─ ncaa_predictions_live.duckdb (upcoming games + recent predictions only)
```

**Pros:**
- Clean separation by season
- Archive old seasons (can compress/remove from Git)
- Current season stays small
- Easy to understand

**Cons:**
- Need logic to query across seasons for historical analysis
- Migration script needed

**Implementation:**
1. Create season-specific databases
2. Move historical data (2024-25 and earlier) to archive DB
3. Keep only 2025-26 season in active DB
4. Add `.gitignore` for archived DBs (store in releases or external storage)

---

### Option 2: Hot/Cold Data Split

**Structure:**
```
data/
├─ ncaa_hot.duckdb (current season + upcoming games)
│  ├─ games (2025-26 + scheduled)
│  ├─ predictions (active only)
│  ├─ bets (unsettled)
│  └─ team_features (current)
│
└─ ncaa_cold.duckdb (historical data)
   ├─ games (all completed, all seasons)
   ├─ predictions (historical)
   ├─ bets (settled)
   └─ accuracy_metrics (all time)
```

**Pros:**
- Optimal for operational performance
- Small active database for daily pipeline
- Can exclude cold DB from Git entirely

**Cons:**
- More complex query logic
- Need data migration strategy (when to move hot→cold)

---

### Option 3: Table-Based Split

**Structure:**
```
data/
├─ ncaa_games.duckdb (games table only)
├─ ncaa_predictions.duckdb (predictions + accuracy)
├─ ncaa_teams.duckdb (teams + features)
└─ ncaa_betting.duckdb (bets + parlays)
```

**Pros:**
- Logical separation by domain
- Each DB focused on one concern
- Can version control some, exclude others

**Cons:**
- Foreign key relationships broken
- Complex cross-DB queries
- More connection overhead

---

### Option 4: Use Git LFS (Least Effort)

**Keep single database, use Git LFS for large files**

```bash
git lfs install
git lfs track "*.duckdb"
git add .gitattributes
```

**Pros:**
- No code changes needed
- Single source of truth
- Built for large files

**Cons:**
- Requires Git LFS on all machines
- GitHub LFS has storage/bandwidth limits (free: 1GB storage, 1GB/month bandwidth)
- Still growing file size issue

---

## Recommended Approach: Hybrid (Season + Git LFS)

**Best of both worlds:**

1. **Split by season** (Option 1) to keep active DB small
2. **Use Git LFS** (Option 4) for current season DB only
3. **Archive old seasons** to GitHub Releases (not in Git)

**Structure:**
```
data/
├─ ncaa_predictions_current.duckdb  ← Git LFS tracked, ~20-30 MB
└─ archives/
   ├─ 2024_25.duckdb.gz  ← Not in Git, in GitHub Releases
   └─ 2023_24.duckdb.gz  ← Not in Git, in GitHub Releases
```

**Benefits:**
- Active DB stays small (current season only)
- Git LFS handles the ~30MB current season file
- Old seasons archived and compressed
- Clean, maintainable solution

---

## Data Retention Strategy

### What to Keep in Active DB
- ✅ Current season games (2025-26)
- ✅ Upcoming games (all scheduled)
- ✅ Current season predictions
- ✅ Current team features
- ✅ Unsettled bets/parlays
- ✅ Last 30 days of accuracy metrics

### What to Archive
- 📦 Previous season games (2024-25 and older)
- 📦 Historical predictions (older seasons)
- 📦 Settled bets from previous seasons
- 📦 Historical accuracy data (older than 30 days)

---

## Implementation Plan

### Phase 1: Analysis (Tomorrow Morning)
- [ ] Analyze database size by table
- [ ] Identify largest tables
- [ ] Check games distribution by season
- [ ] Estimate size after season split

### Phase 2: Design (Tomorrow Afternoon)
- [ ] Choose splitting strategy
- [ ] Design migration script
- [ ] Plan backup strategy
- [ ] Document query changes needed

### Phase 3: Implementation
- [ ] Create migration script
- [ ] Test on local copy
- [ ] Update pipeline to use new structure
- [ ] Update export scripts
- [ ] Test end-to-end

### Phase 4: Deployment
- [ ] Run migration on production DB
- [ ] Set up Git LFS (if needed)
- [ ] Archive old seasons
- [ ] Update documentation
- [ ] Monitor for issues

---

## Quick Analysis Queries

Run these tomorrow to make informed decision:

```python
# Size by table
import duckdb
conn = duckdb.connect('data/ncaa_predictions.duckdb')

print("Database size analysis:")
print(conn.execute("""
    SELECT 
        table_name,
        COUNT(*) as row_count,
        pg_size_pretty(pg_total_relation_size(table_name)) as size
    FROM information_schema.tables
    WHERE table_schema = 'main'
    GROUP BY table_name
    ORDER BY pg_total_relation_size(table_name) DESC
""").df())

# Games by season
print("\nGames by season:")
print(conn.execute("""
    SELECT 
        season,
        game_status,
        COUNT(*) as game_count
    FROM games
    GROUP BY season, game_status
    ORDER BY season DESC, game_status
""").df())

# Predictions by season
print("\nPredictions by season:")
print(conn.execute("""
    SELECT 
        g.season,
        COUNT(p.id) as prediction_count
    FROM predictions p
    JOIN games g ON p.game_id = g.game_id
    GROUP BY g.season
    ORDER BY g.season DESC
""").df())
```

---

## Cost-Benefit Analysis

| Solution | Effort | Git Size | Complexity | Recommended |
|----------|--------|----------|------------|-------------|
| Season Split | Medium | Small | Low | ⭐⭐⭐⭐⭐ |
| Hot/Cold Split | High | Small | Medium | ⭐⭐⭐ |
| Table Split | High | Small | High | ⭐⭐ |
| Git LFS Only | Low | N/A | Low | ⭐⭐⭐ |
| Hybrid (Season + LFS) | Medium | Medium | Low | ⭐⭐⭐⭐⭐ |

---

## Next Steps for Tomorrow

1. **Run analysis queries** to understand current data distribution
2. **Review solutions** and pick one (recommend Hybrid approach)
3. **Create migration script** to split database
4. **Test thoroughly** on local copy before production
5. **Update pipeline** and export scripts
6. **Deploy** with backup plan

---

## Questions to Answer Tomorrow

- How many games are in each season?
- What's the size breakdown by table?
- Do we need all historical data in Git?
- Should we use GitHub Releases for archives?
- What's our backup strategy?

---

## Resources

- [Git LFS Documentation](https://git-lfs.github.com/)
- [DuckDB ATTACH DATABASE](https://duckdb.org/docs/sql/statements/attach)
- [DuckDB EXPORT/IMPORT](https://duckdb.org/docs/sql/statements/export)
- [GitHub Releases for Large Files](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
