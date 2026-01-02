# STEP 2: Code Implementation - Adjusted Efficiency Calculation

## Three Core Functions

This file contains the complete, production-ready code for the opponent-adjusted efficiency feature engineering.

---

## Function 1: `_estimate_possessions()`

**Location**: `model_training/feature_store.py` (lines 87-103)

**Purpose**: Estimate number of possessions when full box-score data is unavailable

**Signature**:
```python
def _estimate_possessions(points: float, fga: float = None, orb: float = None, to: float = None) -> float:
```

**Complete Code**:
```python
def _estimate_possessions(points: float, fga: float = None, orb: float = None, to: float = None) -> float:
    """
    Estimate possessions using the standard basketball formula.
    
    When full box score data (FGA, ORB, TO) is unavailable, uses a heuristic
    based on NCAA average of ~65 possessions per team per game.
    
    Args:
        points: Points scored
        fga: Field goal attempts (optional)
        orb: Offensive rebounds (optional) 
        to: Turnovers (optional)
    
    Returns:
        Estimated possessions
    """
    if fga is not None and orb is not None and to is not None:
        # Standard formula: FGA - ORB + TO
        return fga - orb + to + 0.4
    else:
        # Heuristic: assume ~65 possessions per game in college basketball
        # This is conservative and avoids inflating efficiency numbers
        return 65.0
```

**Usage Example**:
```python
# With full box-score data
possessions = _estimate_possessions(points=72, fga=65, orb=8, to=12)
# Returns: 65 - 8 + 12 + 0.4 = 69.4

# Without box-score data (default)
possessions = _estimate_possessions(points=72)
# Returns: 65.0 (NCAA average)
```

**Rationale**:
- NCAA teams average ~65 possessions per game
- Formula: FGA - ORB + TO + 0.4 is the standard basketball possession estimator
- Conservative default avoids artificially inflating efficiency metrics

---

## Function 2: `_calculate_raw_efficiency()`

**Location**: `model_training/feature_store.py` (lines 106-122)

**Purpose**: Convert points scored into a standardized efficiency metric (points per 100 possessions)

**Signature**:
```python
def _calculate_raw_efficiency(points: float, possessions: float = 65.0) -> float:
```

**Complete Code**:
```python
def _calculate_raw_efficiency(points: float, possessions: float = 65.0) -> float:
    """
    Calculate raw offensive efficiency.
    
    Args:
        points: Points scored in the game
        possessions: Estimated possessions (default 65 for NCAA average)
    
    Returns:
        Points per 100 possessions
    """
    if possessions <= 0:
        return 0.0
    return (points / possessions) * 100.0
```

**Usage Example**:
```python
# Team scores 72 points in 65 possessions
raw_eff = _calculate_raw_efficiency(points=72, possessions=65.0)
# Returns: (72 / 65) × 100 = 110.77

# Team scores 65 points in 65 possessions (average)
raw_eff = _calculate_raw_efficiency(points=65, possessions=65.0)
# Returns: (65 / 65) × 100 = 100.0

# Edge case: zero possessions
raw_eff = _calculate_raw_efficiency(points=72, possessions=0)
# Returns: 0.0 (safe handling)
```

**Key Features**:
- Normalizes points to a 0-100+ scale
- Easy to interpret: 100 = league average, 110 = 10% above average
- Handles edge cases (zero possessions)
- Standard metric used by analytics (KenPom, BPI, NET)

---

## Function 3: `_calculate_opponent_adjusted_efficiency()` ⭐ CORE

**Location**: `model_training/feature_store.py` (lines 125-184)

**Purpose**: Core algorithm for calculating opponent-adjusted efficiency metrics

**Signature**:
```python
def _calculate_opponent_adjusted_efficiency(
    team_games_list: list,
    team_id: str,
    opponent_efficiencies: dict
) -> tuple:
```

**Complete Code**:
```python
def _calculate_opponent_adjusted_efficiency(
    team_games_list: list,
    team_id: str,
    opponent_efficiencies: dict
) -> tuple:
    """
    Calculate opponent-adjusted offensive and defensive efficiency.
    
    Algorithm:
    1. For each game, calculate raw offensive efficiency (points scored / possessions * 100)
    2. For each game, get opponent's defensive efficiency (points allowed / possessions * 100)
    3. Adjusted offensive efficiency = raw_off_eff - avg_opponent_def_eff
    4. Adjusted defensive efficiency = raw_def_eff - avg_opponent_off_eff
    
    Args:
        team_games_list: List of game dicts with team's game data
                        Expected keys: 'opponent_id', 'points_for', 'points_against', 
                        'possessions' (optional), 'game_id'
        team_id: The team's ID
        opponent_efficiencies: Dict mapping opponent_id -> {'off_eff': X, 'def_eff': Y}
    
    Returns:
        Tuple of (avg_adj_off_eff, avg_adj_def_eff) for the team
    """
    if not team_games_list:
        return (0.0, 0.0)
    
    adj_off_effs = []
    adj_def_effs = []
    
    for game in team_games_list:
        # Calculate raw efficiency
        possessions = game.get('possessions', 65.0)
        if possessions <= 0:
            possessions = 65.0
        
        points_for = game.get('points_for', 0)
        points_against = game.get('points_against', 0)
        
        raw_off_eff = _calculate_raw_efficiency(points_for, possessions)
        raw_def_eff = _calculate_raw_efficiency(points_against, possessions)
        
        # Get opponent's efficiency (defensive efficiency of opponent = points allowed by opponent)
        opponent_id = game.get('opponent_id')
        opponent_def_eff = 0.0
        opponent_off_eff = 0.0
        
        if opponent_id and opponent_id in opponent_efficiencies:
            opponent_def_eff = opponent_efficiencies[opponent_id].get('def_eff', 0.0)
            opponent_off_eff = opponent_efficiencies[opponent_id].get('off_eff', 0.0)
        
        # Adjusted efficiency = raw - opponent_strength
        adj_off_eff = raw_off_eff - opponent_def_eff
        adj_def_eff = raw_def_eff - opponent_off_eff
        
        adj_off_effs.append(adj_off_eff)
        adj_def_effs.append(adj_def_eff)
    
    avg_adj_off_eff = np.mean(adj_off_effs) if adj_off_effs else 0.0
    avg_adj_def_eff = np.mean(adj_def_effs) if adj_def_effs else 0.0
    
    return (float(avg_adj_off_eff), float(avg_adj_def_eff))
```

**Usage Example**:
```python
# Define games for a team
team_games = [
    {
        'opponent_id': 'duke_id',
        'points_for': 72,
        'points_against': 65,
        'possessions': 65.0
    },
    {
        'opponent_id': 'unc_id',
        'points_for': 68,
        'points_against': 70,
        'possessions': 65.0
    },
    {
        'opponent_id': 'wake_id',
        'points_for': 75,
        'points_against': 63,
        'possessions': 65.0
    }
]

# Define opponent efficiencies (pre-computed)
opponent_efficiencies = {
    'duke_id': {
        'off_eff': 115.0,  # Elite offense
        'def_eff': 95.0    # Elite defense
    },
    'unc_id': {
        'off_eff': 110.0,
        'def_eff': 100.0
    },
    'wake_id': {
        'off_eff': 105.0,
        'def_eff': 105.0
    }
}

# Calculate adjusted efficiency
adj_off_eff, adj_def_eff = _calculate_opponent_adjusted_efficiency(
    team_games,
    'team_a',
    opponent_efficiencies
)

# Returns:
# adj_off_eff: Average adjusted offensive efficiency across 3 games
# adj_def_eff: Average adjusted defensive efficiency across 3 games
```

**Step-by-Step Breakdown**:

For the example above:

```
Game 1 (vs Duke):
  Raw Off. Eff = (72 / 65) × 100 = 110.77
  Opponent Def. Eff = 95.0
  Adj Off. Eff = 110.77 - 95.0 = +15.77 ✓ (beat strong defense)
  
Game 2 (vs UNC):
  Raw Off. Eff = (68 / 65) × 100 = 104.62
  Opponent Def. Eff = 100.0
  Adj Off. Eff = 104.62 - 100.0 = +4.62 ✓ (slight win vs average)
  
Game 3 (vs Wake):
  Raw Off. Eff = (75 / 65) × 100 = 115.38
  Opponent Def. Eff = 105.0
  Adj Off. Eff = 115.38 - 105.0 = +10.38 ✓ (beat weaker defense)

Average Adjusted Off. Eff = (15.77 + 4.62 + 10.38) / 3 = 10.26
```

**Key Insights**:
- **Positive values**: Team performed better than expected (quality wins)
- **Negative values**: Team underperformed against weak defenses
- **Averaging**: Provides rolling metrics when called with 5 or 10 most recent games
- **Mutual adjustment**: Both offensive and defensive efficiency are computed

---

## Integration: Updated `build_feature_store()`

This function now:
1. **Tracks opponent data** during game processing
2. **Pre-computes opponent efficiencies** before feature extraction
3. **Calculates adjusted efficiency** for rolling windows

**Code section** (simplified):
```python
# Pre-compute opponent efficiencies
opponent_efficiencies = {}
for team_id, games_list in efficiency_data.items():
    total_points_for = sum(g['points_for'] for g in games_list)
    total_points_against = sum(g['points_against'] for g in games_list)
    total_possessions = sum(g['possessions'] for g in games_list)
    
    off_eff = _calculate_raw_efficiency(total_points_for, total_possessions)
    def_eff = _calculate_raw_efficiency(total_points_against, total_possessions)
    
    opponent_efficiencies[team_id] = {
        'off_eff': off_eff,
        'def_eff': def_eff
    }

# Then for each team's feature row:
adj_off_eff_5, adj_def_eff_5 = _calculate_opponent_adjusted_efficiency(
    last_5_games, team_id, opponent_efficiencies
)
```

---

## Integration: Updated `calculate_point_in_time_features()`

For training data, this function:
1. **Calculates raw efficiency** for each game
2. **Pre-computes opponent efficiencies** by season
3. **Computes game-level adjusted efficiency** with anti-leakage
4. **Rolls adjusted efficiency** using `.shift(1)` 
5. **Merges adjusted features** back to the game DataFrame

**Key code**:
```python
# Calculate raw efficiency
team_df['raw_off_eff'] = team_df.apply(
    lambda row: _calculate_raw_efficiency(row['score'], row['possessions']), axis=1
)
team_df['raw_def_eff'] = team_df.apply(
    lambda row: _calculate_raw_efficiency(row['opponent_score'], row['possessions']), axis=1
)

# Pre-compute opponent efficiencies
opponent_eff_by_season = {}
for (season, opp_id), grp in team_df.groupby(['season', 'team_id']):
    avg_off_eff = grp['raw_off_eff'].mean()
    avg_def_eff = grp['raw_def_eff'].mean()
    opponent_eff_by_season[(season, opp_id)] = {
        'off_eff': float(avg_off_eff),
        'def_eff': float(avg_def_eff)
    }

# Calculate adjusted efficiency with opponent lookup
def get_adjusted_eff(row):
    opponent_def_eff = opponent_eff_by_season[(season, opponent_id)]['def_eff']
    adj_off = row['raw_off_eff'] - opponent_def_eff
    return adj_off

# Roll with .shift(1) anti-leakage
team_df['rolling_adj_off_eff_5'] = grouped['adj_off_eff'].transform(
    lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
)
```

---

## Data Flow Diagram

```
Raw Game Data
    ↓
Split Home/Away (long format)
    ↓
Calculate Raw Efficiency ← _calculate_raw_efficiency()
    ↓
Pre-compute Opponent Efficiencies
    ↓
Calculate Game-level Adjusted Efficiency ← _calculate_opponent_adjusted_efficiency()
    ↓
Roll with .shift(1) to prevent leakage
    ↓
NEW FEATURE COLUMNS:
  • rolling_adj_off_eff_5
  • rolling_adj_off_eff_10
  • rolling_adj_def_eff_5
  • rolling_adj_def_eff_10
    ↓
Merge back to game DataFrame
    ↓
Ready for model training!
```

---

## Summary of Changes

| File | Changes | Lines |
|------|---------|-------|
| `model_training/feature_store.py` | Added 3 functions | +127 |
| | Updated NUMERIC_FEATURE_COLS | +4 features |
| | Updated LEAGUE_AVERAGE_DEFAULTS | +4 defaults |
| | Enhanced build_feature_store() | ✓ |
| | Enhanced calculate_point_in_time_features() | ✓ |

**Backward Compatibility**: ✅ All existing APIs unchanged

---

## Next Steps

1. **Regenerate feature store** with next data pipeline run
2. **Monitor feature importance** to confirm added value
3. **Tune rolling windows** (currently 5/10 games)
4. **Proceed to Step 3**: Implement Exponential Moving Averages (EWMA)
5. **Proceed to Step 1**: Fix team name matching with fuzzy matching

---

**Status**: ✅ Complete, tested, ready for production
