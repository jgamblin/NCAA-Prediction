# 🏀 NCAA Prediction Accuracy - Implementation & Testing Plan

_Created: November 29, 2025_
_Last Updated: November 29, 2025_

This document provides detailed implementation steps, code changes, and testing procedures for each accuracy improvement.

---

## Implementation Status

| Phase | Status | Completion Date |
|-------|--------|-----------------|
| **Phase 1: Quick Wins** | ✅ **COMPLETE** | Nov 29, 2025 |
| **Phase 2: Feature Engineering** | ✅ **COMPLETE** | Nov 29, 2025 |
| **Phase 3: Model Architecture** | ✅ **COMPLETE** | Nov 29, 2025 |
| Phase 4: Advanced Improvements | 🔲 Pending | - |

---

## Table of Contents

1. [Phase 1: Quick Wins (Days 1-3)](#phase-1-quick-wins) ✅
2. [Phase 2: Feature Engineering (Days 4-10)](#phase-2-feature-engineering) ✅
3. [Phase 3: Model Architecture (Days 11-20)](#phase-3-model-architecture) ✅
4. [Phase 4: Advanced Improvements (Days 21-30)](#phase-4-advanced-improvements)
5. [Testing Framework](#testing-framework)
6. [Rollback Procedures](#rollback-procedures)

---

## Phase 1: Quick Wins ✅ COMPLETE

**Implemented:** November 29, 2025

### Changes Made:

| Task | File | Description |
|------|------|-------------|
| 1.1 Feature Store Fallback | `model_training/feature_store.py` | Added `get_team_features_with_fallback()` and `enrich_dataframe_with_fallback()` |
| 1.2 Smart Team Encoding | `model_training/adaptive_predictor.py` | Added `_encode_team_smart()` with median-based fallback |
| 1.3 Temperature Scaling | `model_training/adaptive_predictor.py` | Enhanced existing scaling with feature flag control |
| 1.4 Early Season Detection | `model_training/adaptive_predictor.py` | Added `_is_early_season()` and `_get_early_season_confidence_factor()` |
| Config | `config/feature_flags.json` | Feature flags for toggling improvements |
| Tests | `tests/test_phase1_improvements.py` | Unit tests for all Phase 1 features |
| Pipeline | `daily_pipeline.py` | Updated to use fallback-aware feature enrichment |

### Observed Results:
- Feature fallback working: 174 current season lookups, 618 league average fallbacks (early season)
- No NaN values in enriched features
- Early season confidence adjustment applied

---

## Phase 2: Feature Engineering ✅ COMPLETE

**Implemented:** November 29, 2025

### Changes Made:

| Task | File | Description |
|------|------|-------------|
| 2.1 Power Ratings | `model_training/power_ratings.py` | New `PowerRatings` class with KenPom-style efficiency calculations |
| 2.2 Strength of Schedule | `model_training/power_ratings.py` | `calculate_sos()` method with opponent rating aggregation |
| 2.3 Rest Days | `model_training/home_away_splits.py` | `calculate_rest_days()` and `add_rest_days_features()` |
| 2.4 Home/Away Splits | `model_training/home_away_splits.py` | `HomeAwaySplits` class with venue-specific performance stats |
| Integration | `model_training/adaptive_predictor.py` | Phase 2 feature initialization and enrichment |
| Config | `config/feature_flags.json` | Added Phase 2 feature flags |
| Tests | `tests/test_phase2_improvements.py` | 13 unit tests for Phase 2 features |

### New Features Added:
- **power_rating_diff**: Net efficiency rating difference between teams
- **off_rating_diff**: Offensive efficiency difference
- **def_rating_diff**: Defensive efficiency difference
- **home_sos / away_sos**: Strength of schedule ratings
- **home_rest_days / away_rest_days**: Days since last game
- **rest_advantage**: Rest day differential
- **home_team_home_wpct**: Home team's home win percentage
- **away_team_away_wpct**: Away team's road win percentage
- **venue_wpct_diff**: Home vs away performance differential
- **combined_home_adv**: Team-specific home court advantage

### Feature Importance (from training):
- power_rating_diff: 0.0965
- def_rating_diff: 0.1002
- off_rating_diff: 0.0901

### Observed Results:
- Power ratings calculated for 1428 teams
- Venue splits calculated for 20904 team-seasons
- All 35 tests passing (22 Phase 1 + 13 Phase 2)

---

### Task 1.1: Fix Feature Store Sparsity

**Goal:** Eliminate NaN values in feature store by implementing fallback hierarchy

**Files to Modify:**
- `scripts/feature_store.py`

**Implementation Steps:**

```python
# Step 1: Add prior season fallback method to FeatureStore class

def get_team_features_with_fallback(self, team: str, season: str) -> dict:
    """
    Get team features with fallback hierarchy:
    1. Current season data (if >= 5 games played)
    2. Prior season end-of-year data
    3. Conference average
    4. League average
    """
    current = self._get_current_season_features(team, season)
    
    if current is not None and current.get('games_played', 0) >= 5:
        return current
    
    # Fallback to prior season
    prior_season = str(int(season) - 1)
    prior = self._get_season_end_features(team, prior_season)
    if prior is not None:
        prior['is_fallback'] = True
        prior['fallback_type'] = 'prior_season'
        return prior
    
    # Fallback to conference average
    conference = self._get_team_conference(team)
    if conference:
        conf_avg = self._get_conference_average(conference, season)
        if conf_avg is not None:
            conf_avg['is_fallback'] = True
            conf_avg['fallback_type'] = 'conference_avg'
            return conf_avg
    
    # Fallback to league average
    league_avg = self._get_league_average(season)
    league_avg['is_fallback'] = True
    league_avg['fallback_type'] = 'league_avg'
    return league_avg
```

```python
# Step 2: Add helper methods

def _get_season_end_features(self, team: str, season: str) -> dict:
    """Get team's final features from a completed season."""
    team_data = self.data[
        (self.data['team'] == team) & 
        (self.data['season'] == season)
    ]
    if team_data.empty:
        return None
    return team_data.sort_values('date').iloc[-1].to_dict()

def _get_conference_average(self, conference: str, season: str) -> dict:
    """Get average features for all teams in a conference."""
    conf_data = self.data[
        (self.data['conference'] == conference) & 
        (self.data['season'] == season)
    ]
    if conf_data.empty:
        return None
    numeric_cols = conf_data.select_dtypes(include=[np.number]).columns
    return conf_data[numeric_cols].mean().to_dict()

def _get_league_average(self, season: str) -> dict:
    """Get league-wide average features."""
    season_data = self.data[self.data['season'] == season]
    if season_data.empty:
        # Use all available data
        season_data = self.data
    numeric_cols = season_data.select_dtypes(include=[np.number]).columns
    return season_data[numeric_cols].mean().to_dict()
```

**Testing:**

| Test Case | Input | Expected Output | Validation |
|-----------|-------|-----------------|------------|
| Team with 10+ games | Duke, 2025 | Current season features | `is_fallback` = False |
| Team with 3 games | New Team, 2025 | Prior season or conference avg | `is_fallback` = True |
| Unknown team | "Random U", 2025 | League average | `fallback_type` = 'league_avg' |
| Prior season exists | Duke, 2025 (early) | 2024 end-of-season data | Features match 2024 final |

```python
# Unit tests to add to tests/test_feature_store.py

def test_fallback_to_prior_season():
    fs = FeatureStore()
    # Mock team with only 2 games in current season
    features = fs.get_team_features_with_fallback("Duke", "2025")
    assert features is not None
    assert 'win_pct5' in features or features.get('is_fallback') == True

def test_fallback_to_league_average():
    fs = FeatureStore()
    features = fs.get_team_features_with_fallback("Nonexistent University", "2025")
    assert features is not None
    assert features.get('fallback_type') == 'league_avg'

def test_no_nan_in_features():
    fs = FeatureStore()
    for team in ['Duke', 'Kentucky', 'Unknown Team']:
        features = fs.get_team_features_with_fallback(team, "2025")
        for key, value in features.items():
            if isinstance(value, (int, float)):
                assert not np.isnan(value), f"NaN found in {key} for {team}"
```

**Acceptance Criteria:**
- [ ] No NaN values in any feature for any team
- [ ] Fallback type is tracked for monitoring
- [ ] Prior season data loads correctly
- [ ] All unit tests pass

---

### Task 1.2: Improve Unknown Team Handling

**Goal:** Replace `-1` encoding with meaningful defaults

**Files to Modify:**
- `scripts/adaptive_predictor.py`

**Implementation Steps:**

```python
# Step 1: Create team encoding with conference-based fallback

def encode_team_smart(self, team_name: str, encoder: LabelEncoder) -> int:
    """
    Encode team with intelligent fallback:
    1. Known team -> use label encoder
    2. Unknown team -> use conference representative
    3. Still unknown -> use median encoding value
    """
    if team_name in encoder.classes_:
        return encoder.transform([team_name])[0]
    
    # Try to find a team from same conference
    conference = self._get_team_conference(team_name)
    if conference:
        conf_teams = self._get_conference_teams(conference)
        for conf_team in conf_teams:
            if conf_team in encoder.classes_:
                return encoder.transform([conf_team])[0]
    
    # Return median encoding (middle of the pack assumption)
    return len(encoder.classes_) // 2

def _get_team_conference(self, team_name: str) -> str:
    """Look up team's conference from reference data."""
    # Load from conference mapping file
    if not hasattr(self, '_conference_map'):
        self._load_conference_map()
    return self._conference_map.get(team_name)
```

```python
# Step 2: Create conference mapping data file
# data/conference_map.json

{
    "Duke": "ACC",
    "North Carolina": "ACC",
    "Kentucky": "SEC",
    "Kansas": "Big 12",
    "UCLA": "Big Ten",
    ...
}
```

**Testing:**

| Test Case | Input | Expected Output | Validation |
|-----------|-------|-----------------|------------|
| Known team | "Duke" | Unique integer | Matches label encoder |
| Unknown ACC team | "ACC School" | ACC team's encoding | Not -1 |
| Completely unknown | "Random U" | Median value | len(classes) // 2 |

```python
# Unit tests

def test_known_team_encoding():
    predictor = AdaptivePredictor()
    predictor.train(training_data)
    enc = predictor.encode_team_smart("Duke", predictor.home_encoder)
    assert enc >= 0
    assert enc < len(predictor.home_encoder.classes_)

def test_unknown_team_not_negative():
    predictor = AdaptivePredictor()
    predictor.train(training_data)
    enc = predictor.encode_team_smart("Fake University", predictor.home_encoder)
    assert enc >= 0  # Never -1

def test_unknown_team_uses_median():
    predictor = AdaptivePredictor()
    predictor.train(training_data)
    enc = predictor.encode_team_smart("Completely Unknown", predictor.home_encoder)
    expected_median = len(predictor.home_encoder.classes_) // 2
    assert enc == expected_median
```

**Acceptance Criteria:**
- [ ] No team encodes to -1
- [ ] Conference mapping file created with all D1 teams
- [ ] Unknown teams get reasonable default encoding
- [ ] All unit tests pass

---

### Task 1.3: Add Confidence Temperature Scaling

**Goal:** Reduce overconfident predictions until model accuracy improves

**Files to Modify:**
- `scripts/adaptive_predictor.py`

**Implementation Steps:**

```python
# Step 1: Add temperature scaling to prediction method

def predict_with_temperature(self, X: np.ndarray, temperature: float = 1.5) -> tuple:
    """
    Make predictions with temperature-scaled confidence.
    
    Temperature > 1.0 reduces confidence (makes predictions more uncertain)
    Temperature < 1.0 increases confidence
    Temperature = 1.0 is unchanged
    """
    raw_proba = self.model.predict_proba(X)
    
    # Apply temperature scaling
    scaled_proba = self._apply_temperature(raw_proba, temperature)
    
    predictions = (scaled_proba[:, 1] > 0.5).astype(int)
    confidences = np.maximum(scaled_proba[:, 0], scaled_proba[:, 1])
    
    return predictions, confidences

def _apply_temperature(self, proba: np.ndarray, temperature: float) -> np.ndarray:
    """Apply temperature scaling to probability distribution."""
    if temperature == 1.0:
        return proba
    
    # Convert to logits, scale, convert back
    epsilon = 1e-10
    logits = np.log(proba + epsilon)
    scaled_logits = logits / temperature
    
    # Softmax
    exp_logits = np.exp(scaled_logits - np.max(scaled_logits, axis=1, keepdims=True))
    scaled_proba = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
    
    return scaled_proba
```

```python
# Step 2: Add dynamic temperature based on recent accuracy

def get_optimal_temperature(self) -> float:
    """
    Calculate optimal temperature based on recent calibration.
    If predictions are overconfident, increase temperature.
    """
    recent_accuracy = self._get_recent_accuracy(days=7)
    recent_avg_confidence = self._get_recent_avg_confidence(days=7)
    
    if recent_accuracy is None or recent_avg_confidence is None:
        return 1.5  # Default conservative temperature
    
    # If confidence exceeds accuracy by more than 5%, increase temperature
    confidence_gap = recent_avg_confidence - recent_accuracy
    
    if confidence_gap > 0.15:
        return 2.0  # Very overconfident
    elif confidence_gap > 0.10:
        return 1.75
    elif confidence_gap > 0.05:
        return 1.5
    elif confidence_gap > 0:
        return 1.25
    else:
        return 1.0  # Well calibrated
```

**Testing:**

| Test Case | Raw Confidence | Temperature | Expected Output |
|-----------|----------------|-------------|-----------------|
| High confidence | 0.90 | 1.0 | 0.90 |
| High confidence | 0.90 | 1.5 | ~0.78 |
| High confidence | 0.90 | 2.0 | ~0.71 |
| Low confidence | 0.55 | 1.5 | ~0.53 |

```python
# Unit tests

def test_temperature_scaling_reduces_confidence():
    predictor = AdaptivePredictor()
    proba = np.array([[0.1, 0.9]])
    
    scaled_1 = predictor._apply_temperature(proba, 1.0)
    scaled_15 = predictor._apply_temperature(proba, 1.5)
    scaled_2 = predictor._apply_temperature(proba, 2.0)
    
    # Higher temperature should reduce max probability
    assert scaled_15[0, 1] < scaled_1[0, 1]
    assert scaled_2[0, 1] < scaled_15[0, 1]

def test_temperature_preserves_prediction():
    predictor = AdaptivePredictor()
    proba = np.array([[0.3, 0.7]])
    
    scaled = predictor._apply_temperature(proba, 1.5)
    
    # Winner should still be the same
    assert np.argmax(scaled[0]) == np.argmax(proba[0])

def test_dynamic_temperature_overconfident():
    predictor = AdaptivePredictor()
    # Mock: 60% accuracy, 80% avg confidence
    predictor._get_recent_accuracy = lambda days: 0.60
    predictor._get_recent_avg_confidence = lambda days: 0.80
    
    temp = predictor.get_optimal_temperature()
    assert temp >= 1.75  # Should increase temperature significantly
```

**Acceptance Criteria:**
- [ ] Temperature scaling implemented and tested
- [ ] Dynamic temperature adjusts based on recent performance
- [ ] Confidence values are more aligned with actual accuracy
- [ ] All unit tests pass

---

### Task 1.4: Add Early Season Detection

**Goal:** Apply more conservative predictions during early season

**Files to Modify:**
- `scripts/adaptive_predictor.py`
- `scripts/daily_pipeline.py`

**Implementation Steps:**

```python
# Step 1: Detect early season conditions

def is_early_season(self, current_date: datetime = None) -> bool:
    """
    Determine if we're in early season (less reliable predictions).
    Early season = first 4 weeks of season (typically Nov 1 - Dec 1)
    """
    if current_date is None:
        current_date = datetime.now()
    
    # NCAA season typically starts first week of November
    season_start = datetime(current_date.year, 11, 1)
    if current_date.month < 11:
        season_start = datetime(current_date.year - 1, 11, 1)
    
    days_into_season = (current_date - season_start).days
    return days_into_season < 30

def get_early_season_adjustment(self, games_played: int) -> float:
    """
    Get confidence adjustment factor based on games played.
    Fewer games = less reliable prediction = lower confidence.
    """
    if games_played >= 15:
        return 1.0  # Full confidence
    elif games_played >= 10:
        return 0.95
    elif games_played >= 5:
        return 0.90
    elif games_played >= 3:
        return 0.85
    else:
        return 0.80  # Very uncertain
```

**Testing:**

| Test Case | Date | Games Played | Adjustment |
|-----------|------|--------------|------------|
| Early November | Nov 10, 2025 | 3 | 0.85 |
| Late November | Nov 29, 2025 | 8 | 0.90 |
| December | Dec 15, 2025 | 12 | 0.95 |
| February | Feb 1, 2026 | 25 | 1.0 |

**Acceptance Criteria:**
- [ ] Early season detected correctly
- [ ] Confidence adjusted based on games played
- [ ] Adjustments logged for monitoring

---

## Phase 2: Feature Engineering

### Task 2.1: Integrate External Power Ratings

**Goal:** Add KenPom-style efficiency ratings for all teams

**New Files:**
- `scripts/power_ratings.py`
- `data/power_ratings.csv`

**Implementation Steps:**

```python
# scripts/power_ratings.py

import pandas as pd
import numpy as np
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup

class PowerRatings:
    """
    Calculate and manage team power ratings.
    Uses adjusted efficiency margin similar to KenPom methodology.
    """
    
    def __init__(self, data_path: str = "data/power_ratings.csv"):
        self.data_path = data_path
        self.ratings: Dict[str, dict] = {}
    
    def calculate_ratings(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate power ratings from game results.
        
        Methodology:
        1. Calculate raw offensive/defensive efficiency
        2. Adjust for opponent strength (iteratively)
        3. Compute net rating (AdjO - AdjD)
        """
        teams = set(games_df['home_team']) | set(games_df['away_team'])
        
        # Initialize ratings
        for team in teams:
            self.ratings[team] = {
                'adj_offense': 100.0,
                'adj_defense': 100.0,
                'adj_tempo': 70.0,
                'net_rating': 0.0
            }
        
        # Iterative adjustment (10 iterations)
        for _ in range(10):
            self._update_ratings(games_df)
        
        # Convert to DataFrame
        ratings_df = pd.DataFrame.from_dict(self.ratings, orient='index')
        ratings_df['team'] = ratings_df.index
        ratings_df['net_rating'] = ratings_df['adj_offense'] - ratings_df['adj_defense']
        ratings_df['rank'] = ratings_df['net_rating'].rank(ascending=False)
        
        return ratings_df
    
    def _update_ratings(self, games_df: pd.DataFrame):
        """Single iteration of rating updates."""
        for team in self.ratings:
            team_games = games_df[
                (games_df['home_team'] == team) | 
                (games_df['away_team'] == team)
            ]
            
            if len(team_games) == 0:
                continue
            
            off_effs = []
            def_effs = []
            
            for _, game in team_games.iterrows():
                is_home = game['home_team'] == team
                
                if is_home:
                    pts_scored = game['home_score']
                    pts_allowed = game['away_score']
                    opponent = game['away_team']
                else:
                    pts_scored = game['away_score']
                    pts_allowed = game['home_score']
                    opponent = game['home_team']
                
                # Estimate possessions (simplified)
                possessions = (pts_scored + pts_allowed) / 2 * 0.96
                
                # Raw efficiency
                raw_off = pts_scored / possessions * 100 if possessions > 0 else 100
                raw_def = pts_allowed / possessions * 100 if possessions > 0 else 100
                
                # Adjust for opponent
                opp_rating = self.ratings.get(opponent, {'adj_defense': 100, 'adj_offense': 100})
                adj_off = raw_off * (100 / opp_rating['adj_defense'])
                adj_def = raw_def * (100 / opp_rating['adj_offense'])
                
                off_effs.append(adj_off)
                def_effs.append(adj_def)
            
            # Update with weighted average (more recent games weighted higher)
            if off_effs:
                weights = np.linspace(0.5, 1.0, len(off_effs))
                self.ratings[team]['adj_offense'] = np.average(off_effs, weights=weights)
                self.ratings[team]['adj_defense'] = np.average(def_effs, weights=weights)
    
    def get_team_rating(self, team: str) -> dict:
        """Get rating for a specific team."""
        return self.ratings.get(team, {
            'adj_offense': 100.0,
            'adj_defense': 100.0,
            'net_rating': 0.0,
            'rank': 180  # Middle of D1
        })
    
    def scrape_kenpom(self) -> pd.DataFrame:
        """
        Scrape current KenPom ratings (requires subscription).
        Returns empty DataFrame if unavailable.
        """
        # Note: This requires a KenPom subscription
        # Implementing as placeholder for manual data entry
        try:
            # Would need authentication
            pass
        except Exception:
            return pd.DataFrame()
    
    def scrape_massey(self) -> pd.DataFrame:
        """
        Scrape Massey Composite ratings (free).
        """
        try:
            url = "https://masseyratings.com/cb/ncaa-d1/ratings"
            response = requests.get(url, timeout=10)
            # Parse HTML table
            soup = BeautifulSoup(response.text, 'html.parser')
            # ... parsing logic
            return pd.DataFrame()  # Placeholder
        except Exception:
            return pd.DataFrame()
    
    def save(self):
        """Save ratings to CSV."""
        df = pd.DataFrame.from_dict(self.ratings, orient='index')
        df.to_csv(self.data_path)
    
    def load(self):
        """Load ratings from CSV."""
        try:
            df = pd.read_csv(self.data_path, index_col=0)
            self.ratings = df.to_dict('index')
        except FileNotFoundError:
            pass
```

**Integration with Predictor:**

```python
# In adaptive_predictor.py, add power rating features

def _add_power_rating_features(self, df: pd.DataFrame) -> pd.DataFrame:
    """Add power rating features to prediction dataframe."""
    power = PowerRatings()
    power.load()
    
    df['home_net_rating'] = df['home_team'].apply(
        lambda t: power.get_team_rating(t).get('net_rating', 0)
    )
    df['away_net_rating'] = df['away_team'].apply(
        lambda t: power.get_team_rating(t).get('net_rating', 0)
    )
    df['net_rating_diff'] = df['home_net_rating'] - df['away_net_rating']
    
    df['home_adj_offense'] = df['home_team'].apply(
        lambda t: power.get_team_rating(t).get('adj_offense', 100)
    )
    df['away_adj_defense'] = df['away_team'].apply(
        lambda t: power.get_team_rating(t).get('adj_defense', 100)
    )
    df['matchup_off_def'] = df['home_adj_offense'] - df['away_adj_defense']
    
    return df
```

**Testing:**

```python
# tests/test_power_ratings.py

def test_power_ratings_calculation():
    """Test that ratings are calculated correctly."""
    games = pd.DataFrame({
        'home_team': ['Duke', 'Kentucky', 'Duke'],
        'away_team': ['Kentucky', 'Duke', 'UNC'],
        'home_score': [75, 70, 80],
        'away_score': [70, 72, 65]
    })
    
    pr = PowerRatings()
    ratings = pr.calculate_ratings(games)
    
    assert 'Duke' in ratings.index
    assert 'net_rating' in ratings.columns
    # Duke won 2 of 3, should have positive net rating
    assert ratings.loc['Duke', 'net_rating'] > 0

def test_unknown_team_rating():
    """Test default rating for unknown team."""
    pr = PowerRatings()
    rating = pr.get_team_rating("Unknown University")
    
    assert rating['adj_offense'] == 100.0
    assert rating['adj_defense'] == 100.0
    assert rating['net_rating'] == 0.0

def test_ratings_converge():
    """Test that iterative ratings converge."""
    games = create_sample_games(100)
    
    pr = PowerRatings()
    ratings = pr.calculate_ratings(games)
    
    # Best team should have positive rating, worst negative
    assert ratings['net_rating'].max() > 0
    assert ratings['net_rating'].min() < 0
```

**Acceptance Criteria:**
- [ ] Power ratings calculated for all teams with games
- [ ] Ratings update daily with new game results
- [ ] Features integrated into predictor
- [ ] All unit tests pass
- [ ] Expected accuracy improvement: +3-5%

---

### Task 2.2: Add Strength of Schedule

**Goal:** Factor in opponent quality when evaluating team performance

**Files to Modify:**
- `scripts/feature_store.py`
- `scripts/power_ratings.py`

**Implementation Steps:**

```python
# Add to feature_store.py

def calculate_strength_of_schedule(self, team: str, season: str) -> dict:
    """
    Calculate strength of schedule metrics.
    
    Returns:
        sos_rating: Average opponent net rating
        sos_rank: Rank of SOS (1 = hardest)
        quality_wins: Wins against top-50 teams
        quality_losses: Losses against 200+ teams
    """
    team_games = self._get_team_games(team, season)
    if team_games.empty:
        return {'sos_rating': 0, 'sos_rank': 180, 'quality_wins': 0, 'quality_losses': 0}
    
    power = PowerRatings()
    power.load()
    
    opponents = []
    for _, game in team_games.iterrows():
        opp = game['away_team'] if game['home_team'] == team else game['home_team']
        opponents.append(opp)
    
    opp_ratings = [power.get_team_rating(opp).get('net_rating', 0) for opp in opponents]
    
    # Quality wins/losses
    quality_wins = 0
    quality_losses = 0
    for _, game in team_games.iterrows():
        is_home = game['home_team'] == team
        opp = game['away_team'] if is_home else game['home_team']
        won = (is_home and game['home_score'] > game['away_score']) or \
              (not is_home and game['away_score'] > game['home_score'])
        
        opp_rank = power.get_team_rating(opp).get('rank', 180)
        
        if won and opp_rank <= 50:
            quality_wins += 1
        elif not won and opp_rank > 200:
            quality_losses += 1
    
    return {
        'sos_rating': np.mean(opp_ratings) if opp_ratings else 0,
        'sos_rank': 0,  # Will be calculated across all teams
        'quality_wins': quality_wins,
        'quality_losses': quality_losses
    }
```

**Testing:**

```python
def test_sos_calculation():
    fs = FeatureStore()
    sos = fs.calculate_strength_of_schedule("Duke", "2025")
    
    assert 'sos_rating' in sos
    assert 'quality_wins' in sos
    assert isinstance(sos['sos_rating'], (int, float))

def test_sos_harder_schedule():
    """Team playing top teams should have higher SOS."""
    fs = FeatureStore()
    # Duke plays many ranked teams
    duke_sos = fs.calculate_strength_of_schedule("Duke", "2025")
    # Small school plays weak opponents
    small_sos = fs.calculate_strength_of_schedule("Small School", "2025")
    
    assert duke_sos['sos_rating'] > small_sos['sos_rating']
```

**Acceptance Criteria:**
- [ ] SOS calculated for all teams
- [ ] Quality wins/losses tracked
- [ ] SOS features added to predictor
- [ ] All unit tests pass

---

### Task 2.3: Add Rest Days Feature

**Goal:** Capture fatigue/rest advantage in predictions

**Files to Modify:**
- `scripts/adaptive_predictor.py`

**Implementation Steps:**

```python
def calculate_rest_days(self, team: str, game_date: datetime, 
                         schedule_df: pd.DataFrame) -> int:
    """
    Calculate days since team's last game.
    
    Returns:
        rest_days: Integer days of rest (capped at 14)
    """
    prior_games = schedule_df[
        ((schedule_df['home_team'] == team) | (schedule_df['away_team'] == team)) &
        (pd.to_datetime(schedule_df['date']) < game_date)
    ]
    
    if prior_games.empty:
        return 7  # Default for season opener
    
    last_game_date = pd.to_datetime(prior_games['date']).max()
    rest_days = (game_date - last_game_date).days
    
    return min(rest_days, 14)  # Cap at 14 days

def add_rest_features(self, df: pd.DataFrame, schedule_df: pd.DataFrame) -> pd.DataFrame:
    """Add rest day features to prediction dataframe."""
    df['home_rest_days'] = df.apply(
        lambda row: self.calculate_rest_days(
            row['home_team'], 
            pd.to_datetime(row['date']),
            schedule_df
        ), axis=1
    )
    
    df['away_rest_days'] = df.apply(
        lambda row: self.calculate_rest_days(
            row['away_team'],
            pd.to_datetime(row['date']),
            schedule_df
        ), axis=1
    )
    
    df['rest_advantage'] = df['home_rest_days'] - df['away_rest_days']
    
    # Flag back-to-back games
    df['home_back_to_back'] = (df['home_rest_days'] <= 1).astype(int)
    df['away_back_to_back'] = (df['away_rest_days'] <= 1).astype(int)
    
    return df
```

**Testing:**

| Scenario | Home Rest | Away Rest | Expected Advantage |
|----------|-----------|-----------|-------------------|
| Normal | 3 | 3 | 0 |
| Home rested | 7 | 2 | +5 |
| Away rested | 1 | 5 | -4 |
| Both back-to-back | 1 | 1 | 0 |

```python
def test_rest_days_calculation():
    predictor = AdaptivePredictor()
    schedule = pd.DataFrame({
        'home_team': ['Duke', 'Duke'],
        'away_team': ['UNC', 'Kentucky'],
        'date': ['2025-11-25', '2025-11-20']
    })
    
    rest = predictor.calculate_rest_days(
        'Duke', 
        datetime(2025, 11, 29),
        schedule
    )
    
    assert rest == 4  # 4 days since Nov 25

def test_back_to_back_flag():
    predictor = AdaptivePredictor()
    df = pd.DataFrame({
        'home_team': ['Duke'],
        'away_team': ['UNC'],
        'date': ['2025-11-29']
    })
    schedule = pd.DataFrame({
        'home_team': ['Duke'],
        'away_team': ['Kentucky'],
        'date': ['2025-11-28']  # Yesterday
    })
    
    result = predictor.add_rest_features(df, schedule)
    assert result['home_back_to_back'].iloc[0] == 1
```

**Acceptance Criteria:**
- [ ] Rest days calculated correctly
- [ ] Back-to-back games flagged
- [ ] Rest advantage feature added
- [ ] All unit tests pass

---

### Task 2.4: Add Home/Away Performance Split

**Goal:** Capture team's home vs road performance differential

**Files to Modify:**
- `scripts/feature_store.py`

**Implementation Steps:**

```python
def calculate_home_away_splits(self, team: str, season: str) -> dict:
    """
    Calculate separate home and away performance metrics.
    
    Returns:
        home_win_pct: Win percentage at home
        away_win_pct: Win percentage on road
        home_point_diff: Average point differential at home
        away_point_diff: Average point differential on road
        home_away_split: Difference in home vs away performance
    """
    team_games = self._get_team_games(team, season)
    
    home_games = team_games[team_games['home_team'] == team]
    away_games = team_games[team_games['away_team'] == team]
    
    def calc_metrics(games, is_home):
        if games.empty:
            return {'win_pct': 0.5, 'point_diff': 0, 'games': 0}
        
        if is_home:
            wins = (games['home_score'] > games['away_score']).sum()
            point_diff = (games['home_score'] - games['away_score']).mean()
        else:
            wins = (games['away_score'] > games['home_score']).sum()
            point_diff = (games['away_score'] - games['home_score']).mean()
        
        return {
            'win_pct': wins / len(games),
            'point_diff': point_diff,
            'games': len(games)
        }
    
    home_metrics = calc_metrics(home_games, True)
    away_metrics = calc_metrics(away_games, False)
    
    return {
        'home_win_pct': home_metrics['win_pct'],
        'away_win_pct': away_metrics['win_pct'],
        'home_point_diff': home_metrics['point_diff'],
        'away_point_diff': away_metrics['point_diff'],
        'home_games': home_metrics['games'],
        'away_games': away_metrics['games'],
        'home_away_split': home_metrics['win_pct'] - away_metrics['win_pct']
    }
```

**Testing:**

```python
def test_home_away_split():
    fs = FeatureStore()
    splits = fs.calculate_home_away_splits("Duke", "2025")
    
    assert 0 <= splits['home_win_pct'] <= 1
    assert 0 <= splits['away_win_pct'] <= 1
    assert 'home_away_split' in splits

def test_home_advantage_detected():
    """Teams typically perform better at home."""
    fs = FeatureStore()
    
    # Check multiple teams
    home_advantage_count = 0
    for team in ['Duke', 'Kentucky', 'Kansas', 'UNC']:
        splits = fs.calculate_home_away_splits(team, "2024")
        if splits['home_win_pct'] > splits['away_win_pct']:
            home_advantage_count += 1
    
    # Most teams should show home advantage
    assert home_advantage_count >= 2
```

**Acceptance Criteria:**
- [ ] Home/away splits calculated
- [ ] Splits integrated into features
- [ ] All unit tests pass

---

## Phase 3: Model Architecture ✅ COMPLETE

**Implemented:** November 29, 2025

### Changes Made:

| Task | File | Description |
|------|------|-------------|
| 3.1 XGBoost Integration | `model_training/ensemble_predictor.py` | New `_create_xgboost_model()` with optimized hyperparameters |
| 3.1 XGBoost Requirements | `requirements.txt` | Added `xgboost>=1.7.0` |
| 3.2 Temporal Split | `model_training/ensemble_predictor.py` | `create_temporal_split()` using last N days for validation |
| 3.3 Model Ensemble | `model_training/ensemble_predictor.py` | `EnsemblePredictor` combining XGBoost + RandomForest + LogisticRegression |
| Integration | `model_training/adaptive_predictor.py` | Added `model_type` and `use_ensemble` parameters |
| Config | `config/feature_flags.json` | Added Phase 3 feature flags |
| Tests | `tests/test_phase3_improvements.py` | 16 unit tests for Phase 3 features |

### New Components:

**EnsemblePredictor Class:**
- `_create_xgboost_model()`: XGBoost classifier with tuned hyperparameters
- `_create_rf_model()`: RandomForest classifier
- `_create_lr_model()`: LogisticRegression for baseline
- `create_temporal_split()`: Proper train/val split preventing data leakage
- `fit()`: Trains all models with temporal validation
- `predict_proba()`: Weighted average of model predictions
- `build_from_adaptive_predictor()`: Integration with existing pipeline

### Feature Flags Added:
- `use_ensemble`: false (off by default)
- `model_type`: "random_forest" (default, can be "xgboost" or "ensemble")
- `xgb_params`: XGBoost hyperparameter configuration
- `ensemble_weights`: Model weight configuration (XGB 45%, RF 35%, LR 20%)

### Observed Results:
- All 51 tests passing (22 Phase 1 + 13 Phase 2 + 16 Phase 3)
- XGBoost falls back gracefully when not installed
- Ensemble feature importance saved to `data/Ensemble_Feature_Importance.csv`
- Note: Ensemble disabled by default; set `use_ensemble: true` to enable

---

### Task 3.1: Switch to XGBoost

**Goal:** Replace RandomForest with XGBoost for better performance

**Files to Modify:**
- `scripts/adaptive_predictor.py`
- `requirements.txt`

**Implementation Steps:**

```python
# Add XGBoost model option

import xgboost as xgb

def _create_xgboost_model(self, params: dict = None) -> xgb.XGBClassifier:
    """Create XGBoost classifier with optimized parameters."""
    default_params = {
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'min_child_weight': 3,
        'gamma': 0.1,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'use_label_encoder': False,
        'random_state': 42,
        'n_jobs': -1
    }
    
    if params:
        default_params.update(params)
    
    return xgb.XGBClassifier(**default_params)

def train(self, df: pd.DataFrame, model_type: str = 'xgboost'):
    """Train model with specified architecture."""
    if model_type == 'xgboost':
        self._raw_model = self._create_xgboost_model()
    elif model_type == 'random_forest':
        self._raw_model = self._create_rf_model()
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    # Continue with training...
```

**requirements.txt addition:**
```
xgboost>=1.7.0
```

**Testing:**

```python
def test_xgboost_training():
    predictor = AdaptivePredictor()
    predictor.train(training_data, model_type='xgboost')
    
    assert predictor._raw_model is not None
    assert hasattr(predictor._raw_model, 'predict_proba')

def test_xgboost_vs_rf_accuracy():
    """XGBoost should match or exceed RF accuracy."""
    # Train both models
    xgb_predictor = AdaptivePredictor()
    xgb_predictor.train(training_data, model_type='xgboost')
    
    rf_predictor = AdaptivePredictor()
    rf_predictor.train(training_data, model_type='random_forest')
    
    # Evaluate on test set
    xgb_acc = evaluate_accuracy(xgb_predictor, test_data)
    rf_acc = evaluate_accuracy(rf_predictor, test_data)
    
    assert xgb_acc >= rf_acc - 0.01  # XGBoost at least as good

def test_xgboost_feature_importance():
    predictor = AdaptivePredictor()
    predictor.train(training_data, model_type='xgboost')
    
    importance = predictor._raw_model.feature_importances_
    assert len(importance) > 0
    assert sum(importance) > 0
```

**Acceptance Criteria:**
- [ ] XGBoost model integrated
- [ ] Can switch between RF and XGBoost
- [ ] Hyperparameters tuned
- [ ] All unit tests pass
- [ ] Expected improvement: +2-4%

---

### Task 3.2: Proper Train/Validation Split

**Goal:** Prevent data leakage by using temporal split

**Files to Modify:**
- `scripts/adaptive_predictor.py`

**Implementation Steps:**

```python
def create_temporal_split(self, df: pd.DataFrame, 
                          val_days: int = 14) -> tuple:
    """
    Create train/validation split respecting temporal order.
    
    Uses most recent 'val_days' of data for validation.
    This simulates real prediction scenario.
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    max_date = df['date'].max()
    val_cutoff = max_date - timedelta(days=val_days)
    
    train_mask = df['date'] < val_cutoff
    val_mask = df['date'] >= val_cutoff
    
    return df[train_mask], df[val_mask]

def train_with_validation(self, df: pd.DataFrame):
    """Train with proper validation for calibration."""
    train_df, val_df = self.create_temporal_split(df)
    
    X_train, y_train = self._prepare_features(train_df)
    X_val, y_val = self._prepare_features(val_df)
    
    # Train raw model
    self._raw_model.fit(X_train, y_train)
    
    # Calibrate on validation set
    val_proba = self._raw_model.predict_proba(X_val)[:, 1]
    self.calibrator = IsotonicRegression(out_of_bounds='clip')
    self.calibrator.fit(val_proba, y_val)
    
    # Log validation performance
    val_pred = (val_proba > 0.5).astype(int)
    val_accuracy = (val_pred == y_val).mean()
    print(f"Validation accuracy: {val_accuracy:.2%}")
```

**Testing:**

```python
def test_temporal_split_no_leakage():
    predictor = AdaptivePredictor()
    df = create_sample_games(1000)
    
    train_df, val_df = predictor.create_temporal_split(df)
    
    # Ensure no overlap
    train_max = train_df['date'].max()
    val_min = val_df['date'].min()
    
    assert train_max < val_min

def test_validation_calibration():
    predictor = AdaptivePredictor()
    predictor.train_with_validation(training_data)
    
    # Calibrator should exist
    assert predictor.calibrator is not None
```

**Acceptance Criteria:**
- [ ] Temporal split implemented
- [ ] No data leakage in calibration
- [ ] Validation metrics logged
- [ ] All unit tests pass

---

### Task 3.3: Model Ensemble

**Goal:** Combine multiple models for more robust predictions

**Files to Modify:**
- `scripts/adaptive_predictor.py`

**Implementation Steps:**

```python
class EnsemblePredictor:
    """Ensemble of multiple model types."""
    
    def __init__(self):
        self.models = {}
        self.weights = {}
    
    def train(self, df: pd.DataFrame):
        """Train all models in ensemble."""
        X, y = self._prepare_features(df)
        
        # Random Forest
        rf = RandomForestClassifier(n_estimators=100, max_depth=15)
        rf.fit(X, y)
        self.models['rf'] = rf
        self.weights['rf'] = 0.3
        
        # XGBoost
        xgb_model = xgb.XGBClassifier(n_estimators=200, max_depth=6)
        xgb_model.fit(X, y)
        self.models['xgb'] = xgb_model
        self.weights['xgb'] = 0.4
        
        # Logistic Regression (for calibration)
        lr = LogisticRegression(max_iter=1000)
        lr.fit(X, y)
        self.models['lr'] = lr
        self.weights['lr'] = 0.3
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Weighted average of model predictions."""
        weighted_proba = np.zeros((X.shape[0], 2))
        
        for name, model in self.models.items():
            proba = model.predict_proba(X)
            weighted_proba += proba * self.weights[name]
        
        return weighted_proba
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Ensemble prediction."""
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)
```

**Testing:**

```python
def test_ensemble_training():
    ensemble = EnsemblePredictor()
    ensemble.train(training_data)
    
    assert len(ensemble.models) == 3
    assert sum(ensemble.weights.values()) == 1.0

def test_ensemble_prediction():
    ensemble = EnsemblePredictor()
    ensemble.train(training_data)
    
    predictions = ensemble.predict(X_test)
    assert len(predictions) == len(X_test)
    assert set(predictions).issubset({0, 1})

def test_ensemble_improves_accuracy():
    """Ensemble should be at least as good as best individual model."""
    ensemble = EnsemblePredictor()
    ensemble.train(training_data)
    
    ensemble_acc = evaluate_accuracy(ensemble, test_data)
    
    # Compare to individual models
    for name, model in ensemble.models.items():
        model_acc = evaluate_accuracy(model, test_data)
        assert ensemble_acc >= model_acc - 0.02
```

**Acceptance Criteria:**
- [ ] Ensemble with 3+ models
- [ ] Weights can be tuned
- [ ] Ensemble improves or matches best single model
- [ ] All unit tests pass

---

## Phase 4: Advanced Improvements

### Task 4.1: Conference Strength Adjustment

**Goal:** Factor in conference quality

**Implementation:**

```python
# data/conference_strength.json - updated weekly
{
    "SEC": {"rating": 12.5, "rank": 1},
    "Big Ten": {"rating": 11.2, "rank": 2},
    "Big 12": {"rating": 10.8, "rank": 3},
    "ACC": {"rating": 9.5, "rank": 4},
    ...
}

def get_conference_adjustment(self, team: str, opponent: str) -> float:
    """
    Get adjustment based on conference strength differential.
    """
    team_conf = self._get_team_conference(team)
    opp_conf = self._get_team_conference(opponent)
    
    team_rating = self.conf_strength.get(team_conf, {}).get('rating', 0)
    opp_rating = self.conf_strength.get(opp_conf, {}).get('rating', 0)
    
    return team_rating - opp_rating
```

---

### Task 4.2: Travel Distance Feature

**Goal:** Capture travel fatigue impact

**Implementation:**

```python
# data/team_locations.json
{
    "Duke": {"lat": 36.0014, "lon": -78.9382, "city": "Durham, NC"},
    "UCLA": {"lat": 34.0689, "lon": -118.4452, "city": "Los Angeles, CA"},
    ...
}

def calculate_travel_distance(self, away_team: str, venue_location: tuple) -> float:
    """Calculate distance team travels (in miles)."""
    from math import radians, sin, cos, sqrt, atan2
    
    team_loc = self.team_locations.get(away_team)
    if not team_loc:
        return 0
    
    # Haversine formula
    lat1, lon1 = radians(team_loc['lat']), radians(team_loc['lon'])
    lat2, lon2 = radians(venue_location[0]), radians(venue_location[1])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return 3959 * c  # Earth radius in miles
```

---

## Testing Framework

### Automated Test Suite

Create `tests/` directory with comprehensive tests:

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── test_feature_store.py    # Feature store tests
├── test_power_ratings.py    # Power rating tests
├── test_predictor.py        # Predictor tests
├── test_integration.py      # End-to-end tests
└── test_data_quality.py     # Data validation tests
```

### Test Fixtures

```python
# tests/conftest.py

import pytest
import pandas as pd
from datetime import datetime, timedelta

@pytest.fixture
def sample_games():
    """Create sample game data for testing."""
    return pd.DataFrame({
        'date': pd.date_range('2025-11-01', periods=100),
        'home_team': ['Duke', 'Kentucky', 'Kansas'] * 33 + ['UNC'],
        'away_team': ['UNC', 'Louisville', 'Baylor'] * 33 + ['Duke'],
        'home_score': np.random.randint(60, 100, 100),
        'away_score': np.random.randint(60, 100, 100)
    })

@pytest.fixture
def trained_predictor(sample_games):
    """Provide a trained predictor for testing."""
    predictor = AdaptivePredictor()
    predictor.train(sample_games)
    return predictor

@pytest.fixture
def feature_store():
    """Provide initialized feature store."""
    fs = FeatureStore()
    fs.update()
    return fs
```

### Integration Tests

```python
# tests/test_integration.py

def test_full_prediction_pipeline():
    """Test entire pipeline from raw data to prediction."""
    # 1. Load completed games
    games = pd.read_csv('Completed_Games.csv')
    
    # 2. Update feature store
    fs = FeatureStore()
    fs.update(games)
    
    # 3. Train predictor
    predictor = AdaptivePredictor()
    predictor.train(games)
    
    # 4. Make predictions for upcoming games
    upcoming = pd.read_csv('Upcoming_Games.csv')
    predictions = predictor.predict(upcoming)
    
    # Validate predictions
    assert len(predictions) == len(upcoming)
    assert all(0 <= p <= 1 for p in predictions['confidence'])

def test_accuracy_tracking():
    """Test that accuracy tracking works correctly."""
    from scripts.track_accuracy import track_accuracy
    
    # Run accuracy tracking
    report = track_accuracy()
    
    assert 'overall_accuracy' in report
    assert 'rolling_7day' in report
    assert 0 <= report['overall_accuracy'] <= 1
```

### Performance Benchmarks

```python
# tests/test_performance.py

import time

def test_prediction_speed():
    """Ensure predictions complete in reasonable time."""
    predictor = load_trained_predictor()
    games = create_sample_games(1000)
    
    start = time.time()
    predictor.predict(games)
    elapsed = time.time() - start
    
    assert elapsed < 5.0  # Should complete in < 5 seconds

def test_feature_store_update_speed():
    """Feature store update should be fast."""
    fs = FeatureStore()
    games = create_sample_games(10000)
    
    start = time.time()
    fs.update(games)
    elapsed = time.time() - start
    
    assert elapsed < 30.0  # Should complete in < 30 seconds
```

---

## Rollback Procedures

### Configuration Backup

Before each phase, create backup:

```bash
# Backup current state
cp scripts/adaptive_predictor.py scripts/adaptive_predictor.py.backup
cp scripts/feature_store.py scripts/feature_store.py.backup
cp models/model.pkl models/model.pkl.backup
cp tuned_params.json tuned_params.json.backup
```

### Feature Flags

```python
# config/feature_flags.json
{
    "use_xgboost": false,
    "use_power_ratings": false,
    "use_rest_days": false,
    "use_temperature_scaling": true,
    "temperature_value": 1.5,
    "use_prior_season_fallback": true,
    "use_ensemble": false
}
```

```python
# In adaptive_predictor.py
def load_feature_flags(self):
    with open('config/feature_flags.json') as f:
        self.flags = json.load(f)

def predict(self, X):
    if self.flags.get('use_temperature_scaling'):
        return self.predict_with_temperature(X, self.flags['temperature_value'])
    return self._raw_predict(X)
```

### Rollback Commands

```bash
# Rollback to previous version
git checkout HEAD~1 -- scripts/adaptive_predictor.py

# Rollback model
cp models/model.pkl.backup models/model.pkl

# Disable new feature
jq '.use_power_ratings = false' config/feature_flags.json > tmp && mv tmp config/feature_flags.json
```

---

## Success Metrics & Monitoring

### Daily Metrics Dashboard

Track in `docs/performance.md`:

| Date | Overall Acc | 7-Day Acc | Avg Confidence | Calibration Error | Notes |
|------|-------------|-----------|----------------|-------------------|-------|
| 2025-11-29 | 75.6% | 59.4% | 80.2% | 20.8% | Baseline |
| 2025-11-30 | - | - | - | - | Phase 1.1 deployed |

### Phase Success Criteria

| Phase | Target Improvement | Minimum Acceptable | Rollback Trigger |
|-------|-------------------|-------------------|------------------|
| Phase 1 | +5% 7-day accuracy | +2% | Accuracy drops |
| Phase 2 | +5% 7-day accuracy | +3% | Accuracy drops >2% |
| Phase 3 | +3% 7-day accuracy | +1% | Accuracy drops >1% |
| Phase 4 | +2% 7-day accuracy | +0% | Accuracy drops >1% |

### Alert Thresholds

```python
# In daily_pipeline.py
def check_accuracy_alerts(metrics: dict):
    alerts = []
    
    if metrics['rolling_7day'] < 0.55:
        alerts.append("CRITICAL: 7-day accuracy below 55%")
    
    if metrics['calibration_error'] > 0.20:
        alerts.append("WARNING: Calibration error exceeds 20%")
    
    if metrics['high_confidence_accuracy'] < 0.65:
        alerts.append("WARNING: High-confidence predictions underperforming")
    
    return alerts
```

---

## Timeline Summary

| Week | Focus | Tasks | Expected Outcome |
|------|-------|-------|------------------|
| 1 | Quick Wins | 1.1-1.4 | 65%+ 7-day accuracy |
| 2 | Features | 2.1-2.2 | 70%+ 7-day accuracy |
| 3 | Features + Model | 2.3-2.4, 3.1 | 73%+ 7-day accuracy |
| 4 | Model Architecture | 3.2-3.3 | 75%+ 7-day accuracy |
| 5+ | Advanced | 4.1-4.2 | 77%+ 7-day accuracy |

---

## Getting Started

### Immediate Next Steps

1. **Create feature branch for Phase 1:**
   ```bash
   git checkout -b feature/phase1-quick-wins
   ```

2. **Run baseline tests:**
   ```bash
   python -m pytest tests/ -v
   ```

3. **Implement Task 1.1** (Feature Store Sparsity Fix)

4. **Validate improvement:**
   ```bash
   python scripts/daily_pipeline.py
   cat docs/performance.md
   ```

5. **Commit and iterate:**
   ```bash
   git commit -am "Phase 1.1: Feature store fallback hierarchy"
   ```

---

_Last Updated: November 29, 2025_
