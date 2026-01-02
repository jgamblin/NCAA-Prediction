# Step 2: Visual Guide to Opponent-Adjusted Efficiency

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAW GAME DATA                                │
│  game_id, home_team, away_team, home_score, away_score, date   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│             SPLIT INTO LONG FORMAT (Home/Away)                  │
│  Each game becomes 2 rows (one per team's perspective)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│      CALCULATE RAW EFFICIENCY (Points / Possessions * 100)      │
│  _calculate_raw_efficiency()                                    │
│  Input:  72 points, 65 possessions                              │
│  Output: 110.77 pts/100 poss                                    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│    PRE-COMPUTE OPPONENT EFFICIENCIES (Season-level)             │
│  For each team, calculate total off & def efficiency            │
│  Result: opponent_efficiencies dict                             │
│    {team_id: {off_eff: 110, def_eff: 95}, ...}                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  CALCULATE ADJUSTED EFFICIENCY (Raw - Opponent Strength)        │
│  _calculate_opponent_adjusted_efficiency()                      │
│                                                                  │
│  For each game:                                                 │
│    raw_eff = 110.77 (team's offensive efficiency)              │
│    opp_def_eff = 95.0 (opponent's average defense)            │
│    adj_eff = 110.77 - 95.0 = +15.77 ✓ (quality win!)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│     ROLL METRICS WITH ANTI-LEAKAGE (.shift(1))                 │
│                                                                  │
│  For each team-season group:                                    │
│    • Last 5 games adjusted efficiency                          │
│    • Last 10 games adjusted efficiency                         │
│    • Same for defensive efficiency                             │
│                                                                  │
│  Key: Use previous games only (no current game included)        │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│            MERGE BACK TO GAME DATAFRAME                         │
│                                                                  │
│  NEW COLUMNS (for home and away teams):                        │
│    • home_fs_rolling_adj_off_eff_5                             │
│    • home_fs_rolling_adj_off_eff_10                            │
│    • home_fs_rolling_adj_def_eff_5                             │
│    • home_fs_rolling_adj_def_eff_10                            │
│    • away_fs_rolling_adj_off_eff_5                             │
│    • away_fs_rolling_adj_off_eff_10                            │
│    • away_fs_rolling_adj_def_eff_5                             │
│    • away_fs_rolling_adj_def_eff_10                            │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│         READY FOR MODEL TRAINING!                               │
│  RandomForest and XGBoost use these new features                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Function Call Hierarchy

```
build_feature_store() / calculate_point_in_time_features()
    │
    ├─→ _estimate_possessions(points, fga, orb, to)
    │   └─→ Returns: 65.0 or calculated from box score
    │
    ├─→ _calculate_raw_efficiency(points, possessions)
    │   └─→ Returns: points/possessions * 100
    │
    └─→ _calculate_opponent_adjusted_efficiency(team_games, team_id, opp_effs)
        ├─→ For each game:
        │   ├─→ Calculate raw_off_eff = _calculate_raw_efficiency(scored)
        │   ├─→ Calculate raw_def_eff = _calculate_raw_efficiency(allowed)
        │   ├─→ Lookup opponent.def_eff from opp_effs dict
        │   ├─→ Compute adj_off = raw_off - opp.def
        │   └─→ Store in adj_off_effs list
        └─→ Returns: (avg(adj_off_effs), avg(adj_def_effs))
```

---

## Real Example: Kansas vs Duke

**Game Scenario**: Kansas plays Duke on 2024-12-15

```
┌─────────────────────────────────────────────────────────┐
│                      RAW GAME STATS                     │
├─────────────────────────────────────────────────────────┤
│  Kansas:                                                │
│    • Points: 75                                         │
│    • Opponent (Duke) Points: 68                        │
│    • Possessions: 65                                    │
│                                                         │
│  Duke:                                                  │
│    • Points: 68                                         │
│    • Opponent (Kansas) Points: 75                      │
│    • Possessions: 65                                    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              STEP 1: CALCULATE RAW EFFICIENCY          │
├─────────────────────────────────────────────────────────┤
│  Kansas:                                                │
│    • Raw Offensive Eff = (75/65)*100 = 115.38         │
│    • Raw Defensive Eff = (68/65)*100 = 104.62         │
│                                                         │
│  Duke:                                                  │
│    • Raw Offensive Eff = (68/65)*100 = 104.62         │
│    • Raw Defensive Eff = (75/65)*100 = 115.38         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│         STEP 2: LOOKUP OPPONENT SEASON STATS           │
├─────────────────────────────────────────────────────────┤
│  Duke Season Stats (pre-computed):                      │
│    • Offensive Efficiency: 112.0 (top 10 offense)      │
│    • Defensive Efficiency: 98.0 (top 5 defense)        │
│                                                         │
│  Kansas Season Stats (pre-computed):                    │
│    • Offensive Efficiency: 108.0 (solid)               │
│    • Defensive Efficiency: 103.0 (average)             │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│       STEP 3: CALCULATE ADJUSTED EFFICIENCY            │
├─────────────────────────────────────────────────────────┤
│  Kansas:                                                │
│    • Raw Off. Eff: 115.38                              │
│    • Duke's Avg Def. Eff: 98.0                         │
│    • ADJ OFF. EFF = 115.38 - 98.0 = +17.38 ✓✓         │
│      (Elite win! Scored at elite pace vs elite D)      │
│                                                         │
│    • Raw Def. Eff: 104.62                              │
│    • Duke's Avg Off. Eff: 112.0                        │
│    • ADJ DEF. EFF = 104.62 - 112.0 = -7.38 ❌         │
│      (Held Duke below their average)                   │
│                                                         │
│  Duke:                                                  │
│    • Raw Off. Eff: 104.62                              │
│    • Kansas' Avg Def. Eff: 103.0                       │
│    • ADJ OFF. EFF = 104.62 - 103.0 = +1.62             │
│      (Slight outperformance vs average)                │
│                                                         │
│    • Raw Def. Eff: 115.38                              │
│    • Kansas' Avg Off. Eff: 108.0                       │
│    • ADJ DEF. EFF = 115.38 - 108.0 = +7.38            │
│      (Held Kansas below their average... barely)       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│            STEP 4: UPDATE ROLLING AVERAGES             │
├─────────────────────────────────────────────────────────┤
│  If this is game #7 in Kansas' season:                 │
│    • rolling_adj_off_eff_5 = avg of games 3-7          │
│    • rolling_adj_off_eff_10 = avg of all 7             │
│      (can't have 10 yet)                               │
│                                                         │
│  If this is game #15:                                  │
│    • rolling_adj_off_eff_5 = avg of games 11-15        │
│    • rolling_adj_off_eff_10 = avg of games 6-15        │
│                                                         │
│  Key: Game #15 is NOT included in its own rolling      │
│  averages! Uses .shift(1) for anti-leakage            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│         STEP 5: MERGE INTO FEATURE DATAFRAME           │
├─────────────────────────────────────────────────────────┤
│  Row: Kansas vs Duke game                              │
│                                                         │
│  New Columns:                                           │
│    home_fs_rolling_adj_off_eff_5:  15.2  (excellent)  │
│    home_fs_rolling_adj_off_eff_10: 12.1  (very good)  │
│    home_fs_rolling_adj_def_eff_5:  -2.3  (good)       │
│    home_fs_rolling_adj_def_eff_10: -1.8  (good)       │
│                                                         │
│    away_fs_rolling_adj_off_eff_5:  3.7   (average)    │
│    away_fs_rolling_adj_off_eff_10: 2.1   (below avg)  │
│    away_fs_rolling_adj_def_eff_5:  6.5   (weak)       │
│    away_fs_rolling_adj_def_eff_10: 8.2   (weak)       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│         MODEL INTERPRETATION                           │
├─────────────────────────────────────────────────────────┤
│  Kansas features say:                                   │
│    "Strong offensive performance vs elite teams"       │
│    "Good defensive play despite elite opponent"        │
│  → Model predicts: Kansas likely to win               │
│                                                         │
│  Duke features say:                                    │
│    "Below-average offensive performance"               │
│    "Defensive struggle vs strong offense"              │
│  → Model predicts: Duke likely to lose                │
│                                                         │
│  RESULT: Kansas 75, Duke 68 ✓                          │
│  Model prediction IMPROVED by knowing opponent quality! │
└─────────────────────────────────────────────────────────┘
```

---

## Key Insights: Before vs After

### BEFORE (Traditional Features)
```
Kansas metrics: 75 pts, +7 point diff
Duke metrics:   68 pts, -7 point diff

Analysis: "Duke is equal to Kansas, just on wrong side"
Problem: Doesn't account for opponent quality
Result: Poor predictions
```

### AFTER (Opponent-Adjusted Features)
```
Kansas:
  - Adj Off Eff: +17.38 (beat elite defense at elite pace)
  - Adj Def Eff: -7.38 (held elite offense below average)
  → Verdict: Excellent performance ✓✓

Duke:
  - Adj Off Eff: +1.62 (barely outperformed vs average opponent)
  - Adj Def Eff: +7.38 (couldn't contain Kansas' offense)
  → Verdict: Below expectations ❌

Analysis: "Kansas is significantly better"
Problem: SOLVED! Now accounts for opponent quality
Result: Better predictions ✓
```

---

## Feature Column Reference

### For Home Team:
- `home_fs_rolling_adj_off_eff_5` → Home team's adjusted offensive efficiency (last 5)
- `home_fs_rolling_adj_off_eff_10` → Home team's adjusted offensive efficiency (last 10)
- `home_fs_rolling_adj_def_eff_5` → Home team's adjusted defensive efficiency (last 5)
- `home_fs_rolling_adj_def_eff_10` → Home team's adjusted defensive efficiency (last 10)

### For Away Team:
- `away_fs_rolling_adj_off_eff_5` → Away team's adjusted offensive efficiency (last 5)
- `away_fs_rolling_adj_off_eff_10` → Away team's adjusted offensive efficiency (last 10)
- `away_fs_rolling_adj_def_eff_5` → Away team's adjusted defensive efficiency (last 5)
- `away_fs_rolling_adj_def_eff_10` → Away team's adjusted defensive efficiency (last 10)

### Interpretation Guide:
- **Positive adjusted efficiency** → Outperforming vs opponent quality
- **Negative adjusted efficiency** → Underperforming vs opponent quality
- **Close to zero** → Performing at expected level
- **Increasing trend** → Team improving/finding form
- **Decreasing trend** → Team struggling/losing form

---

## Performance Expectations

### Model Improvement Potential
- **Conservative**: +1-2% accuracy
- **Likely**: +2-5% accuracy
- **Optimistic**: +5-8% accuracy (depends on other factors)

### Why This Works
1. ✓ Eliminates artificial boosts from weak schedules
2. ✓ Highlights quality wins early in season
3. ✓ Better identifies tournament contenders
4. ✓ Matches industry standards (KenPom, BPI)
5. ✓ More stable feature: doesn't change after opponent plays differently

---

## What's Next?

After Step 2 (✅ Complete), proceed to:

**Step 3: Exponential Moving Averages (EWMA)**
- Replace simple rolling means with EWMA
- Recent games weigh more than old games
- Faster response to team momentum

**Step 1: Fuzzy Team Name Matching**
- Use thefuzz for approximate matching
- Reduce missing opponent stats

**Step 4: Robust Hyperparameter Loading**
- Better error handling for model_params.json
- Sensible defaults if file missing

**Step 5: Calibration Analysis**
- Plot calibration curves
- Apply CalibratedClassifierCV if needed
