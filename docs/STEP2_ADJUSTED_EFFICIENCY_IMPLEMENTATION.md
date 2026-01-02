# Step 2: Opponent-Adjusted Efficiency Implementation

## Overview

This document describes the implementation of **opponent-adjusted features** in the NCAA basketball prediction model. This enhancement addresses a critical gap in feature engineering by accounting for opponent quality when evaluating team performance.

## Problem Statement

Previously, the model used raw metrics like:
- Wins/loss percentage
- Point differentials
- Basic rolling averages (last 5, last 10 games)

**Issue**: A team scoring 72 points against Duke (elite defense) is significantly more impressive than scoring 72 points against a mid-tier team. The old system treated both identically.

## Solution: Opponent-Adjusted Efficiency

### Mathematical Foundation

**Raw Offensive Efficiency (PPE)**:
```
PPE = (Points Scored / Estimated Possessions) × 100
```

**Adjusted Offensive Efficiency (AdjOE)**:
```
AdjOE = RawOE - AvgOpponentDefensiveEfficiency
```

**Adjusted Defensive Efficiency (AdjDE)**:
```
AdjDE = RawDE - AvgOpponentOffensiveEfficiency
```

This approach:
- ✅ Normalizes performance against strong vs. weak opponents
- ✅ Identifies teams that inflated stats (e.g., beat weak opponents)
- ✅ Rewards defensive improvement against elite offenses
- ✅ Follows industry best practices (KenPom, BPI, NET)

---

## Implementation Details

### New Functions in `model_training/feature_store.py`

#### 1. `_estimate_possessions()`
Estimates the number of possessions when full box-score data (FGA, ORB, TO) is unavailable.

```python
def _estimate_possessions(points: float, fga: float = None, orb: float = None, to: float = None) -> float:
    """
    Estimate possessions using the standard basketball formula.
    
    NCAA average: ~65 possessions per team per game (conservative estimate)
    """
    if fga is not None and orb is not None and to is not None:
        # Full formula: FGA - ORB + TO + 0.4
        return fga - orb + to + 0.4
    else:
        return 65.0  # NCAA average
```

#### 2. `_calculate_raw_efficiency()`
Converts raw points into efficiency metrics (points per 100 possessions).

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

**Example**:
- Points: 72, Possessions: 65 → Efficiency = 110.77 pts/100 poss

#### 3. `_calculate_opponent_adjusted_efficiency()`
Core algorithm for computing adjusted efficiency metrics.

```python
def _calculate_opponent_adjusted_efficiency(
    team_games_list: list,
    team_id: str,
    opponent_efficiencies: dict
) -> tuple:
    """
    Calculate opponent-adjusted offensive and defensive efficiency.
    
    Algorithm:
    1. For each game, calculate raw offensive efficiency (points / possessions * 100)
    2. For each game, get opponent's defensive efficiency
    3. Adjusted offensive efficiency = raw_off_eff - avg_opponent_def_eff
    4. Adjusted defensive efficiency = raw_def_eff - avg_opponent_off_eff
    
    Args:
        team_games_list: List of game dicts with:
            - opponent_id, points_for, points_against, possessions
        team_id: The team's ID
        opponent_efficiencies: Dict mapping opponent_id -> 
            {'off_eff': X, 'def_eff': Y}
    
    Returns:
        Tuple of (avg_adj_off_eff, avg_adj_def_eff)
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
        
        # Get opponent's efficiency
        opponent_id = game.get('opponent_id')
        opponent_def_eff = 0.0
        opponent_off_eff = 0.0
        
        if opponent_id and opponent_id in opponent_efficiencies:
            opponent_def_eff = opponent_efficiencies[opponent_id].get('def_eff', 0.0)
            opponent_off_eff = opponent_efficiencies[opponent_id].get('off_eff', 0.0)
        
        # Adjusted = Raw - Opponent Strength
        adj_off_eff = raw_off_eff - opponent_def_eff
        adj_def_eff = raw_def_eff - opponent_off_eff
        
        adj_off_effs.append(adj_off_eff)
        adj_def_effs.append(adj_def_eff)
    
    avg_adj_off_eff = np.mean(adj_off_effs) if adj_off_effs else 0.0
    avg_adj_def_eff = np.mean(adj_def_effs) if adj_def_effs else 0.0
    
    return (float(avg_adj_off_eff), float(avg_adj_def_eff))
```

---

### Integration into Feature Store

#### Enhanced `build_feature_store()` Function

The function now:
1. **Tracks efficiency data** for all teams during game processing
2. **Pre-computes opponent efficiencies** before feature extraction
3. **Calculates adjusted efficiency** for rolling windows (5 and 10 games)
4. **Stores new columns** in the feature store CSV

**New feature columns generated**:
- `rolling_adj_off_eff_5`: Adjusted offensive efficiency over last 5 games
- `rolling_adj_off_eff_10`: Adjusted offensive efficiency over last 10 games
- `rolling_adj_def_eff_5`: Adjusted defensive efficiency over last 5 games
- `rolling_adj_def_eff_10`: Adjusted defensive efficiency over last 10 games

#### Enhanced `calculate_point_in_time_features()` Function

For training data, this function now:
1. **Calculates raw efficiency** for each game (before leakage prevention)
2. **Pre-computes opponent efficiencies** by season and team
3. **Computes game-level adjusted efficiency** (raw - opponent strength)
4. **Rolls adjusted efficiency metrics** using `.shift(1)` to prevent data leakage
5. **Merges adjusted features** back to the original game DataFrame

**Key anti-leakage mechanism**:
```python
def get_rolling(series, window):
    return series.shift(1).rolling(window=window, min_periods=1).mean()
```

The `.shift(1)` ensures that a game's adjusted efficiency is calculated using only PRIOR games, not including the current game's result.

---

## New Feature Columns

Added to `NUMERIC_FEATURE_COLS`:

| Column | Description | Calculation |
|--------|-------------|-------------|
| `rolling_adj_off_eff_5` | Adjusted offensive efficiency (last 5) | avg(raw_off_eff - opp_def_eff) |
| `rolling_adj_off_eff_10` | Adjusted offensive efficiency (last 10) | avg(raw_off_eff - opp_def_eff) |
| `rolling_adj_def_eff_5` | Adjusted defensive efficiency (last 5) | avg(raw_def_eff - opp_off_eff) |
| `rolling_adj_def_eff_10` | Adjusted defensive efficiency (last 10) | avg(raw_def_eff - opp_off_eff) |

Updated `LEAGUE_AVERAGE_DEFAULTS`:
```python
LEAGUE_AVERAGE_DEFAULTS = {
    'rolling_adj_off_eff_5': 0.0,
    'rolling_adj_off_eff_10': 0.0,
    'rolling_adj_def_eff_5': 0.0,
    'rolling_adj_def_eff_10': 0.0,
    # ... existing fields ...
}
```

---

## Example Scenario

### Before (Raw Metrics):
```
Team A (last 5 games):
  - Avg Points: 72
  - Opponent Avg Points: 65
  - Point Differential: +7

Team B (last 5 games):
  - Avg Points: 72
  - Opponent Avg Points: 65
  - Point Differential: +7
```

Both teams appear identical in traditional metrics.

### After (Adjusted Efficiency):
```
Team A (last 5 games):
  - Raw Offensive Efficiency: 110.77
  - Opponent Avg Defensive Eff: 100.0 (strong defenses)
  - Adjusted Offensive Eff: 110.77 - 100.0 = 10.77 ✅

Team B (last 5 games):
  - Raw Offensive Efficiency: 110.77
  - Opponent Avg Defensive Eff: 105.0 (weak defenses)
  - Adjusted Offensive Eff: 110.77 - 105.0 = 5.77 ❌
```

Team A is revealed as stronger despite identical raw stats!

---

## Testing & Validation

The implementation has been tested with:
1. ✅ Syntax validation (no Python errors)
2. ✅ Function unit tests (raw efficiency, adjusted efficiency calculations)
3. ✅ Edge case handling (zero possessions, missing opponents, empty games)
4. ✅ Integration with existing feature store API

### Quick Test Results:
```
Points: 72, Possessions: 65.0
Raw Offensive Efficiency: 110.77 pts/100 possessions ✓

Opponent-Adjusted Efficiency (3 games):
  Adjusted Offensive Eff: 12.59
  Adjusted Defensive Eff: -6.13 ✓
```

---

## Impact on Model Training

These features will be used by RandomForest and XGBoost models as additional predictors:
- **Higher predictive power**: Accounts for schedule strength automatically
- **Better calibration**: Model learns that beating elite opponents matters more
- **Reduced overfitting**: Efficiency metrics are more stable than raw points
- **Interpretability**: Can explain predictions based on quality wins/losses

---

## Next Steps

After deployment, consider:
1. **Monitor feature importance** to confirm adjusted efficiency adds value
2. **Tune rolling windows** (currently 5/10 games - try 3/7 or 7/15)
3. **Add opponent strength index** as a separate feature
4. **Incorporate full box-score data** when available (FGA, ORB, TO) for more accurate possession estimates
5. **Proceed with Step 3**: Implement Exponential Moving Averages (EWMA) for better recency weighting

---

## File Changes Summary

- **Modified**: `model_training/feature_store.py`
  - Added 3 new helper functions
  - Updated `NUMERIC_FEATURE_COLS` (added 4 columns)
  - Updated `LEAGUE_AVERAGE_DEFAULTS`
  - Enhanced `build_feature_store()`
  - Enhanced `calculate_point_in_time_features()`

- **No breaking changes**: All existing APIs remain backward compatible
- **Feature store persistence**: New columns saved to CSV automatically

---

**Status**: ✅ Complete and tested
**Ready for**: Step 3 (Exponential Moving Averages)
