# 🏀 NCAA Basketball Prediction Accuracy Improvement Plan

_Generated: November 29, 2025_

## Executive Summary

The model currently achieves **75.65% overall accuracy** but has declined to a **59.43% 7-day rolling accuracy**. This represents a concerning **16+ percentage point deterioration** from historical performance. This document analyzes the root causes and proposes a prioritized improvement plan.

---

## Current State Analysis

### Model Performance Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Overall Accuracy | 75.65% | 80%+ |
| 7-Day Rolling Accuracy | 59.43% | 75%+ |
| Average Confidence | ~80% | Should match accuracy |
| High-Confidence (≥70%) Accuracy | ~60% | 85%+ |

### The Core Problem

**The model is overconfident and underperforming.** When the model predicts with 80% confidence, it's only correct ~60% of the time. This indicates:
1. Poor probability calibration
2. Missing predictive features
3. Insufficient handling of early-season uncertainty

---

## Root Causes Identified

### 🔴 Critical Issues

#### 1. Feature Store Sparsity (HIGH IMPACT)

**Problem:** The model's most important features (rolling win %, point differential) are empty for many current-season games.

```
Feature Importance:
- fs_win_pct10_diff: 19.65% (often empty!)
- fs_point_diff10_diff: 16.19% (often empty!)
- fs_point_diff5_diff: 10.72% (often empty!)
```

**Evidence:** Many teams have played only 5-10 games this season, so rolling 10-game averages are incomplete or entirely missing.

**Impact:** ~50% of model predictive power is unavailable for early-season games.

#### 2. Team Encoding Brittleness (HIGH IMPACT)

**Problem:** Unknown teams (not seen in training) all encode to `-1`, making them indistinguishable.

```python
# Current approach:
def encode_team(team_name, encoder):
    if team_name in encoder.classes_:
        return encoder.transform([team_name])[0]
    return -1  # ALL unknown teams look identical!
```

**Evidence:** ~949 teams have <10 games in training data, many encoding to -1.

**Impact:** Predictions for games involving lesser-known teams are essentially random.

#### 3. No External Power Ratings (HIGH IMPACT)

**Problem:** The model relies on AP/ESPN rankings, which:
- Only cover ~25 teams (top 25 ranked)
- Are poll-based, not predictive
- Treat #30 team same as #300 team (both unranked = 99)

**Better Alternative:** KenPom, Sagarin, BPI ratings which:
- Rate ALL ~360 D1 teams
- Are mathematically derived from game performance
- Have proven predictive power

#### 4. Missing Strength of Schedule (MEDIUM IMPACT)

**Problem:** A team that goes 8-2 against top-50 teams looks identical to 8-2 against D3 teams.

**Evidence:** Feature store calculates raw win % and point differential without opponent adjustment.

#### 5. No Home/Away Performance Split (MEDIUM IMPACT)

**Problem:** Some teams are dominant at home but poor on the road. The model treats them identically.

**Evidence:** The only home court adjustment is a global logit shift to 55%, not team-specific.

---

### 🟠 Moderate Issues

#### 6. Calibration Uses Training Data

**Problem:** Probability calibration is done on the same data used for training, risking overfitting.

```python
# Current:
self.model = CalibratedClassifierCV(self._raw_model, method='sigmoid', cv=5)
self.model.fit(X, y)  # Same X used for both!
```

**Better Approach:** Use a held-out validation set for calibration.

#### 7. No Recency Weighting Within Season

**Problem:** A game from November 1st is weighted the same as November 28th within the current season.

**Reality:** Teams improve (or regress) throughout the season. Recent games are more predictive.

#### 8. No Rest Days Feature

**Problem:** Back-to-back games significantly impact performance, but this isn't captured.

**Evidence:** Tournament games (often back-to-back) show higher upset rates.

#### 9. Single Model Architecture

**Problem:** RandomForest only. No ensemble or alternative models.

**Evidence:** Gradient boosting (XGBoost, LightGBM) typically outperforms RF on tabular data by 2-5%.

---

### 🟡 Minor Issues

#### 10. Limited Hyperparameter Search

Only 5 parameter combinations explored. More thorough search could improve by 0.5-1%.

#### 11. No Conference Strength Adjustment

Playing in the SEC vs. playing in a weaker conference isn't factored in.

#### 12. No Head-to-Head History

Historical matchup results between specific teams aren't used.

---

## Improvement Plan

### Phase 1: Quick Wins (1-3 Days)

These changes can be implemented quickly with high expected impact.

| Task | Expected Impact | Effort | Priority |
|------|-----------------|--------|----------|
| **1.1 Fix empty feature store columns** | +3-5% | Low | P0 |
| **1.2 Use prior season data for early-season games** | +2-3% | Low | P0 |
| **1.3 Improve unknown team handling** | +2-3% | Low | P0 |
| **1.4 Increase confidence temperature** | +1-2% (calibration) | Low | P1 |

#### 1.1 Fix Empty Feature Store

```python
# Before: Return NaN if insufficient games
# After: Fall back to prior season data, then conference average, then league average

def get_team_features(team, season, feature_store):
    current = feature_store.query(f"team == '{team}' and season == '{season}'")
    if current.empty or current['games_played'].iloc[0] < 5:
        # Fall back to prior season
        prior = feature_store.query(f"team == '{team}' and season == '{prior_season}'")
        if not prior.empty:
            return prior.iloc[-1]  # Most recent from prior season
        # Fall back to conference average
        return get_conference_average(team, season)
    return current.iloc[-1]
```

#### 1.2 Prior Season Fallback

For teams with <5 games this season, use their end-of-prior-season statistics as a baseline.

#### 1.3 Unknown Team Handling

Instead of encoding to -1, use:
- Conference average statistics
- Division level (D1 vs non-D1)
- Region-based defaults

#### 1.4 Confidence Temperature

Increase the temperature parameter to reduce overconfidence:
```python
# Current: temperature = 1.0 (auto-calibrated)
# Proposed: temperature = 1.5-2.0 until accuracy improves
```

---

### Phase 2: Feature Engineering (1 Week)

| Task | Expected Impact | Effort | Priority |
|------|-----------------|--------|----------|
| **2.1 Integrate KenPom/Sagarin ratings** | +5-8% | Medium | P0 |
| **2.2 Add strength of schedule** | +2-4% | Medium | P1 |
| **2.3 Add rest days feature** | +1-2% | Low | P1 |
| **2.4 Add home/away performance split** | +1-2% | Medium | P2 |

#### 2.1 External Power Ratings

**Option A: Scrape KenPom** (requires subscription)
- Adjusted Efficiency Margin (AdjEM)
- Offensive/Defensive efficiency
- Tempo

**Option B: Build Simple Efficiency Ratings**
```python
def calculate_efficiency_rating(team, games):
    """Simple per-possession efficiency approximation"""
    possessions = (games['field_goal_attempts'] + 0.44 * games['free_throw_attempts'] 
                   - games['offensive_rebounds'] + games['turnovers'])
    off_eff = games['points_scored'] / possessions * 100
    def_eff = games['points_allowed'] / possessions * 100
    return off_eff - def_eff  # Net efficiency margin
```

**Option C: Use free public ratings**
- Sagarin (free on USA Today)
- Massey Composite (aggregates multiple ratings)
- Warren Nolan (free RPI and SOS data)

#### 2.2 Strength of Schedule

```python
def calculate_sos(team, games, all_ratings):
    """Calculate strength of schedule based on opponent ratings"""
    opponents = games['opponent']
    opp_ratings = [all_ratings.get(opp, 0) for opp in opponents]
    return np.mean(opp_ratings)
```

#### 2.3 Rest Days Feature

```python
def get_rest_days(team, game_date, schedule):
    """Days since team's last game"""
    prior_games = schedule[(schedule['team'] == team) & (schedule['date'] < game_date)]
    if prior_games.empty:
        return 7  # Default for season opener
    last_game = prior_games['date'].max()
    return (game_date - last_game).days
```

---

### Phase 3: Model Architecture (2 Weeks)

| Task | Expected Impact | Effort | Priority |
|------|-----------------|--------|----------|
| **3.1 Switch to XGBoost/LightGBM** | +2-4% | Medium | P1 |
| **3.2 Proper train/validation split** | +1-2% | Low | P1 |
| **3.3 Team embeddings** | +2-3% | High | P2 |
| **3.4 Model ensemble** | +1-2% | Medium | P2 |

#### 3.1 Gradient Boosting

```python
import xgboost as xgb

model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    objective='binary:logistic',
    eval_metric='logloss'
)
```

#### 3.2 Proper Validation Split

```python
# Use games from last 14 days of prior season as validation
# This better simulates real-world prediction scenario
train_mask = df['date'] < (season_end - timedelta(days=14))
val_mask = ~train_mask

X_train, y_train = X[train_mask], y[train_mask]
X_val, y_val = X[val_mask], y[val_mask]

model.fit(X_train, y_train)
calibrator.fit(model.predict_proba(X_val)[:, 1], y_val)
```

#### 3.3 Team Embeddings

Replace label encoding with learned embeddings:
```python
# Use entity embeddings (like in TabNet or similar)
# Or train Word2Vec on team co-occurrence in games
from gensim.models import Word2Vec

# Create "sentences" of teams that played each other
sentences = [[game['home_team'], game['away_team']] for game in games]
embedding_model = Word2Vec(sentences, vector_size=32, window=1, min_count=1)

def get_team_embedding(team):
    return embedding_model.wv[team] if team in embedding_model.wv else np.zeros(32)
```

---

### Phase 4: Advanced Improvements (1 Month)

| Task | Expected Impact | Effort | Priority |
|------|-----------------|--------|----------|
| **4.1 Conference strength adjustment** | +1-2% | Medium | P2 |
| **4.2 Tournament detection** | +0.5-1% | Low | P3 |
| **4.3 Travel distance** | +0.5-1% | Medium | P3 |
| **4.4 Injury/roster data** | +2-3% | High | P3 |

---

## Implementation Priority

### Week 1 Focus (Highest ROI)
1. ✅ Fix feature store sparsity (Phase 1.1, 1.2)
2. ✅ Add prior season fallback
3. ✅ Improve unknown team handling
4. ✅ Integrate external power ratings (even simple SOS)

### Week 2 Focus
1. Add rest days feature
2. Switch to XGBoost
3. Implement proper validation split

### Week 3+ Focus
1. Home/away splits
2. Team embeddings
3. Full model ensemble

---

## Success Metrics

### Target Goals

| Timeframe | Accuracy Target | Calibration Target |
|-----------|-----------------|-------------------|
| 1 Week | 70% 7-day rolling | Confidence within 5% of accuracy |
| 2 Weeks | 75% 7-day rolling | Confidence within 3% of accuracy |
| 1 Month | 78%+ sustained | Brier score < 0.20 |

### Monitoring Dashboard

Track these metrics daily:
- Overall accuracy
- 7-day rolling accuracy
- High-confidence (≥70%) accuracy
- Average confidence vs actual accuracy (calibration)
- Accuracy by confidence bucket (50-60%, 60-70%, 70-80%, 80%+)
- Accuracy by game type (ranked vs unranked, conference vs non-conference)

---

## Appendix: Feature Importance Analysis

Current top features (from model training):

| Feature | Importance | Status |
|---------|------------|--------|
| fs_win_pct10_diff | 19.65% | ⚠️ Often empty |
| fs_point_diff10_diff | 16.19% | ⚠️ Often empty |
| fs_point_diff5_diff | 10.72% | ⚠️ Often empty |
| fs_win_pct5_diff | 9.90% | ⚠️ Often empty |
| fs_point_diff_last5_vs10_diff | 9.84% | ⚠️ Often empty |
| fs_recent_strength_index5_diff | 9.41% | ⚠️ Often empty |
| away_team_encoded | 8.78% | ⚠️ Many unknowns |
| home_team_encoded | 8.45% | ⚠️ Many unknowns |
| fs_win_pct_last5_vs10_diff | 4.28% | ⚠️ Often empty |
| home_rank | 0.87% | Underutilized |
| away_rank | 0.81% | Underutilized |
| rank_diff | 0.45% | Underutilized |
| is_ranked_matchup | 0.36% | Underutilized |
| is_neutral | 0.29% | Underutilized |

**Key Insight:** ~79% of model importance comes from feature store features that are often empty early in the season!

---

## Appendix: Data Quality Checklist

Before each prediction run, verify:

- [ ] Feature store updated with latest games
- [ ] No games with 0-0 scores marked as "Final"
- [ ] Team names normalized consistently
- [ ] Rolling averages have sufficient game counts
- [ ] Calibration temperature is appropriate for current accuracy

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Prioritize Phase 1 tasks** for immediate implementation
3. **Create tracking issue** for each improvement task
4. **Set up A/B testing** to measure impact of each change
5. **Establish weekly review** of accuracy metrics

---

_This document should be updated as improvements are implemented and accuracy metrics change._
