# Confidence Calibration Fix - Priority Plan

## 🚨 THE PROBLEM

**Your 80%+ confidence predictions are only 67.7% accurate.**

This is **catastrophic** for betting because:
- Users bet more on high-confidence picks
- They lose money on what should be "safe" bets
- It destroys trust in the entire system
- **12.3% overconfidence gap on high-confidence picks**

---

## 📊 Current State (BAD)

```
Confidence Bucket    Games    Actual Accuracy    Gap
─────────────────────────────────────────────────────
80%+ confidence      567      67.7%             -12.3%  ❌
70-80% confidence    192      48.4%             -21.6%  ❌❌
60-70% confidence     81      37.0%             -23.0%  ❌❌❌
<60% confidence       88      26.1%             N/A

Overall              928      57.1%             -20.4%  ❌❌❌
```

**This is a total calibration failure!**

---

## 🎯 TARGET STATE (GOOD)

```
Confidence Bucket    Games    Target Accuracy    Acceptable Range
────────────────────────────────────────────────────────────────────
80%+ confidence      500+     78-82%            ±2%  ✅
70-80% confidence    200+     72-77%            ±3%  ✅
60-70% confidence    150+     62-68%            ±3%  ✅

Overall              850+     65-70%            ±3%  ✅
```

---

## 🔧 IMMEDIATE FIXES (Can Do Today)

### Fix 1: Emergency Temperature Override ⏱️ 2 minutes

**Problem**: Current temperature (0.85) is way too high

**Solution**: Force much lower temperature

**File**: `config/feature_flags.json`
```json
{
  "temperature_override": 0.60,  // Was 0.85 or null
  "use_temperature_scaling": true
}
```

**Expected Impact**: Reduces all confidence by ~30%
- 80% → 72% confidence
- 70% → 63% confidence
- 60% → 54% confidence

**This alone should fix the worst of the overconfidence!**

---

### Fix 2: Add Confidence Cap ⏱️ 10 minutes

**Problem**: Model shouldn't claim >85% confidence on NCAA games (too unpredictable)

**Solution**: Hard cap on confidence scores

**File**: `model_training/adaptive_predictor.py`

Add after line 1113 (in predict method):
```python
# HARD CAP: NCAA basketball is too unpredictable for >85% confidence
results_df['confidence'] = results_df['confidence'].clip(upper=0.85)

# Even more conservative for low-data teams
if results_df['has_insufficient_data'].any():
    low_data_mask = results_df['has_insufficient_data']
    results_df.loc[low_data_mask, 'confidence'] = results_df.loc[low_data_mask, 'confidence'].clip(upper=0.75)
```

**Impact**: No prediction above 85% (NCAA is unpredictable!)

---

### Fix 3: Log Confidence vs Reality ⏱️ 15 minutes

**File**: `daily_pipeline_db.py`

Add after predictions are generated:
```python
print("\n" + "="*80)
print("⚠️  CONFIDENCE CALIBRATION WARNING")
print("="*80)
print("\nHistorical Calibration (2025-26 Season):")
print("  80%+ confidence picks: 67.7% actual accuracy (OVERCONFIDENT!)")
print("  70-80% confidence:     48.4% actual accuracy (VERY OVERCONFIDENT!)")
print("  Overall:              57.1% actual accuracy")
print("\nToday's Predictions:")
print(f"  Total predictions:     {len(predictions)}")
print(f"  Average confidence:    {predictions['confidence'].mean():.1%}")
print(f"  80%+ confidence picks: {len(predictions[predictions['confidence'] >= 0.80])}")
print(f"  70%+ confidence picks: {len(predictions[predictions['confidence'] >= 0.70])}")
print("\n⚠️  WARNING: Model is historically overconfident!")
print("   Reduce confidence by ~15% for realistic expectations")
print("   80%+ picks are closer to 68% actual accuracy")
print("="*80 + "\n")
```

**Impact**: Transparency about confidence issues

---

## 🔬 PROPER FIX (Week 1)

### Step 1: Create Validation Set ⏱️ 4 hours

**Why**: Must calibrate on data the model hasn't seen

**File**: `model_training/train_val_split.py` (NEW)

```python
def create_validation_split(df, val_days=14):
    """
    Create temporal validation split.
    
    Training: All games up to (latest - val_days)
    Validation: Last val_days of games
    
    This simulates real prediction: train on past, validate on "future"
    """
    df_sorted = df.sort_values('date')
    latest_date = df_sorted['date'].max()
    val_cutoff = latest_date - pd.Timedelta(days=val_days)
    
    train_df = df_sorted[df_sorted['date'] < val_cutoff].copy()
    val_df = df_sorted[df_sorted['date'] >= val_cutoff].copy()
    
    print(f"Training games: {len(train_df)} (up to {val_cutoff.date()})")
    print(f"Validation games: {len(val_df)} (last {val_days} days)")
    
    return train_df, val_df


def validate_split(train_df, val_df):
    """Ensure no data leakage."""
    assert len(train_df) > 0, "Training set is empty!"
    assert len(val_df) > 0, "Validation set is empty!"
    assert train_df['date'].max() < val_df['date'].min(), "Data leakage! Train/val overlap"
    print("✓ Validation split is clean (no leakage)")
```

**Usage in AdaptivePredictor.fit()**:
```python
def fit(self, train_df):
    # Split into train/val
    from model_training.train_val_split import create_validation_split
    train_data, val_data = create_validation_split(train_df, val_days=14)
    
    # Train on training set
    # ... existing training code ...
    
    # Store validation set for calibration
    self._validation_data = val_data
```

---

### Step 2: Isotonic Regression Calibration ⏱️ 3 hours

**Why**: Isotonic regression is the gold standard for probability calibration

**File**: `model_training/adaptive_predictor.py`

Add after line 913 (after model.fit):
```python
# ================================================================
# CRITICAL: Calibrate probabilities on VALIDATION set
# ================================================================
from sklearn.isotonic import IsotonicRegression

print("\nCalibrating probabilities on validation set...")

# Get predictions on validation set (held-out data)
val_prepared = self.prepare_data(self._validation_data.copy())
val_features = [c for c in self.feature_cols if c in val_prepared.columns]
X_val = val_prepared[val_features]
y_val = val_prepared['home_win']

# Get RAW probabilities (before any adjustments)
val_probs_raw = self._raw_model.predict_proba(X_val)[:, 1]

# Fit isotonic regression: maps raw probs → calibrated probs
self.isotonic_calibrator = IsotonicRegression(out_of_bounds='clip')
self.isotonic_calibrator.fit(val_probs_raw, y_val)

# Test calibration quality
val_probs_calibrated = self.isotonic_calibrator.transform(val_probs_raw)
ece_before = expected_calibration_error(y_val, val_probs_raw)
ece_after = expected_calibration_error(y_val, val_probs_calibrated)

print(f"  Validation set: {len(y_val)} games")
print(f"  ECE before calibration: {ece_before:.4f}")
print(f"  ECE after calibration:  {ece_after:.4f}")
print(f"  ✓ Improvement: {(ece_before - ece_after) / ece_before * 100:.1f}%")

# Check high-confidence accuracy
high_conf_mask = val_probs_calibrated >= 0.80
if high_conf_mask.sum() > 0:
    high_conf_acc = y_val[high_conf_mask].mean()
    print(f"  80%+ confidence accuracy: {high_conf_acc:.1%} ({high_conf_mask.sum()} games)")
```

**Then in predict() method, ADD calibration step:**

Find line 1056 (base_probs = self.model.predict_proba...)
```python
# Get BASE probabilities
base_probs = self._raw_model.predict_proba(X_upcoming)[:, 1]

# CRITICAL: Apply isotonic calibration FIRST
if hasattr(self, 'isotonic_calibrator'):
    base_probs = self.isotonic_calibrator.transform(base_probs)
    print(f"  ✓ Applied isotonic calibration")

# Then apply home court shift
home_probs_adj = self._apply_home_court_shift(base_probs)

# Then apply temperature
probabilities = self._apply_confidence_temperature(home_probs_adj)
```

**Impact**: This is the #1 most important fix!

---

### Step 3: Tune Temperature on Validation ⏱️ 2 hours

**File**: `model_training/adaptive_predictor.py`

Replace _configure_confidence_temperature (line 746):
```python
def _configure_confidence_temperature(self, val_probs, val_labels):
    """
    Find optimal temperature on VALIDATION set.
    Temperature that minimizes calibration error.
    """
    print("\nTuning temperature on validation set...")
    
    # Grid search for best temperature
    best_temp = 0.85
    best_ece = float('inf')
    
    temperatures = np.linspace(0.4, 1.0, 13)  # 0.4, 0.45, 0.5, ..., 1.0
    
    for temp in temperatures:
        # Apply temperature scaling
        scaled_probs = 0.5 + (val_probs - 0.5) * temp
        scaled_probs = np.clip(scaled_probs, 0.01, 0.99)
        
        # Calculate calibration error
        ece = expected_calibration_error(val_labels, scaled_probs)
        
        if ece < best_ece:
            best_ece = ece
            best_temp = temp
    
    self.confidence_temperature_value = best_temp
    self.confidence_temperature_source = f'validation_tuned'
    
    print(f"  Best temperature: {best_temp:.2f} (ECE: {best_ece:.4f})")
    
    # Show calibration at different confidence levels
    scaled_final = 0.5 + (val_probs - 0.5) * best_temp
    for threshold in [0.80, 0.70, 0.60]:
        mask = scaled_final >= threshold
        if mask.sum() > 0:
            acc = val_labels[mask].mean()
            print(f"  {threshold:.0%}+ confidence: {acc:.1%} accuracy ({mask.sum()} games)")
```

---

### Step 4: Add Expected Calibration Error (ECE) ⏱️ 1 hour

**File**: `model_training/calibration_metrics.py` (NEW)

```python
import numpy as np

def expected_calibration_error(y_true, y_pred, n_bins=10):
    """
    Calculate Expected Calibration Error.
    
    Measures average difference between confidence and accuracy.
    Lower is better (0 = perfect calibration).
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
        n_bins: Number of confidence bins
    
    Returns:
        ECE score (0-1, lower is better)
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    
    # Create bins
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    ece = 0.0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_accuracy = y_true[mask].mean()
            bin_confidence = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_accuracy - bin_confidence)
    
    return ece


def calibration_by_bucket(y_true, y_pred):
    """
    Show calibration for confidence buckets.
    """
    results = []
    
    buckets = [
        (0.80, 1.00, '80%+'),
        (0.70, 0.80, '70-80%'),
        (0.60, 0.70, '60-70%'),
        (0.00, 0.60, '<60%'),
    ]
    
    for low, high, label in buckets:
        mask = (y_pred >= low) & (y_pred < high)
        if mask.sum() > 0:
            accuracy = y_true[mask].mean()
            avg_conf = y_pred[mask].mean()
            gap = avg_conf - accuracy
            results.append({
                'bucket': label,
                'games': mask.sum(),
                'avg_confidence': avg_conf,
                'accuracy': accuracy,
                'gap': gap
            })
    
    return results
```

---

## 📊 VALIDATION & TESTING

### Test 1: Validation Set Calibration ⏱️ 30 minutes

**File**: `tests/test_calibration.py` (NEW)

```python
import pytest
from model_training.calibration_metrics import expected_calibration_error, calibration_by_bucket

def test_validation_calibration():
    """Test that validation set is well-calibrated."""
    # Load model and validation data
    model = load_trained_model()
    val_data = load_validation_data()
    
    # Get predictions
    predictions = model.predict(val_data)
    y_true = val_data['home_win']
    y_pred = predictions['home_win_probability']
    
    # Check ECE
    ece = expected_calibration_error(y_true, y_pred)
    assert ece < 0.05, f"ECE too high: {ece:.4f} (target: <0.05)"
    
    # Check high-confidence accuracy
    high_conf = predictions[predictions['confidence'] >= 0.80]
    if len(high_conf) > 10:  # Need reasonable sample size
        accuracy = (high_conf['predicted_winner'] == val_data.loc[high_conf.index, 'actual_winner']).mean()
        assert accuracy >= 0.78, f"80%+ confidence only {accuracy:.1%} accurate"


def test_confidence_buckets():
    """Test that each confidence bucket is well-calibrated."""
    model = load_trained_model()
    val_data = load_validation_data()
    predictions = model.predict(val_data)
    
    buckets = calibration_by_bucket(
        val_data['home_win'], 
        predictions['home_win_probability']
    )
    
    for bucket in buckets:
        # Allow ±5% calibration error
        assert abs(bucket['gap']) < 0.05, \
            f"{bucket['bucket']} miscalibrated: {bucket['gap']:.1%}"
```

**Run**:
```bash
pytest tests/test_calibration.py -v
```

---

### Test 2: Historical Backtest ⏱️ 2 hours

**File**: `scripts/test_calibration_on_2024_season.py` (NEW)

```python
#!/usr/bin/env python3
"""
Test calibration on 2024-25 season data.
Simulates what would have happened with improved calibration.
"""

import sys
sys.path.insert(0, '.')

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.calibration_metrics import calibration_by_bucket, expected_calibration_error
import pandas as pd

def main():
    print("="*80)
    print("BACKTEST: 2024-25 Season Calibration")
    print("="*80)
    print()
    
    # Load 2024-25 season data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    
    # Get completed games from 2024-25
    all_games = games_repo.get_completed_games_df()
    season_2024 = all_games[all_games['season'] == '2024-25'].copy()
    
    print(f"Total 2024-25 games: {len(season_2024)}")
    
    # Train on first 80%, validate on last 20%
    split_idx = int(len(season_2024) * 0.8)
    train_data = season_2024.iloc[:split_idx]
    test_data = season_2024.iloc[split_idx:]
    
    print(f"Training on first {len(train_data)} games")
    print(f"Testing on last {len(test_data)} games")
    print()
    
    # Train model
    model = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True
    )
    model.fit(train_data)
    
    # Predict on test set
    predictions = model.predict(test_data)
    
    # Calculate actual outcomes
    test_data_with_preds = test_data.merge(
        predictions[['game_id', 'confidence', 'predicted_winner']],
        on='game_id'
    )
    
    # Determine actual winners
    test_data_with_preds['actual_winner'] = test_data_with_preds.apply(
        lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
        axis=1
    )
    
    # Calculate accuracy
    test_data_with_preds['correct'] = (
        test_data_with_preds['predicted_winner'] == test_data_with_preds['actual_winner']
    )
    
    overall_accuracy = test_data_with_preds['correct'].mean()
    avg_confidence = test_data_with_preds['confidence'].mean()
    
    print("Results:")
    print(f"  Overall accuracy: {overall_accuracy:.1%}")
    print(f"  Average confidence: {avg_confidence:.1%}")
    print(f"  Calibration gap: {abs(avg_confidence - overall_accuracy):.1%}")
    print()
    
    # By confidence bucket
    print("By Confidence Bucket:")
    print(f"{'Bucket':15} {'Games':>6} {'Confidence':>10} {'Accuracy':>10} {'Gap':>8}")
    print("-" * 60)
    
    for low, high, label in [(0.80, 1.0, '80%+'), (0.70, 0.80, '70-80%'), (0.60, 0.70, '60-70%')]:
        mask = (test_data_with_preds['confidence'] >= low) & (test_data_with_preds['confidence'] < high)
        if mask.sum() > 0:
            bucket_data = test_data_with_preds[mask]
            bucket_acc = bucket_data['correct'].mean()
            bucket_conf = bucket_data['confidence'].mean()
            gap = bucket_conf - bucket_acc
            
            print(f"{label:15} {mask.sum():6} {bucket_conf:10.1%} {bucket_acc:10.1%} {gap:8.1%}")
    
    # ECE
    ece = expected_calibration_error(
        test_data_with_preds['correct'].values,
        test_data_with_preds['confidence'].values
    )
    print()
    print(f"Expected Calibration Error (ECE): {ece:.4f}")
    print(f"Target: <0.05 {'✅' if ece < 0.05 else '❌'}")
    
    db.close()

if __name__ == '__main__':
    main()
```

**Run**:
```bash
python scripts/test_calibration_on_2024_season.py
```

---

## 📈 MONITORING (Ongoing)

### Daily Calibration Check

**File**: Add to `daily_pipeline_db.py` at end:

```python
# ================================================================
# CALIBRATION TRACKING
# ================================================================
print("\n" + "="*80)
print("CALIBRATION MONITORING")
print("="*80)

# Save predictions with metadata for later evaluation
calibration_log = predictions[[
    'game_id', 'date', 'predicted_winner', 'confidence'
]].copy()

calibration_log['prediction_date'] = datetime.now()
calibration_log['model_version'] = model_version

# Save to tracking table
calibration_log.to_sql(
    'calibration_tracking',
    db.conn,
    if_exists='append',
    index=False
)

# Report confidence distribution
print(f"\nToday's Confidence Distribution:")
print(f"  80%+ confidence: {len(predictions[predictions['confidence'] >= 0.80])} games")
print(f"  70-80%:          {len(predictions[predictions['confidence'].between(0.70, 0.80)])} games")
print(f"  60-70%:          {len(predictions[predictions['confidence'].between(0.60, 0.70)])} games")
print(f"  <60%:            {len(predictions[predictions['confidence'] < 0.60])} games")
print(f"\n⚠️  Remember: Historical 80%+ picks are ~68% accurate (not 80%)")
print("="*80 + "\n")
```

---

## ✅ SUCCESS CRITERIA

### BEFORE (Current - BAD)
```
✗ 80%+ confidence: 67.7% accuracy (12.3% overconfident)
✗ ECE: ~0.15
✗ Overall calibration gap: 20.4%
✗ User trust: LOW
```

### AFTER (Target - GOOD)
```
✓ 80%+ confidence: 78-82% accuracy (well-calibrated!)
✓ ECE: <0.05
✓ Overall calibration gap: <5%
✓ User trust: HIGH
```

---

## 🚀 ACTION PLAN

### TODAY (2 hours)
1. ✅ Set temperature_override to 0.60 in feature_flags.json
2. ✅ Add confidence cap (max 85%)
3. ✅ Add calibration warning logging
4. ✅ Test predictions with new settings

### WEEK 1 (10 hours)
1. ✅ Implement train/val split
2. ✅ Add isotonic regression calibration
3. ✅ Tune temperature on validation set
4. ✅ Test on 2024-25 backtest
5. ✅ Validate ECE < 0.05

### ONGOING
1. ✅ Monitor daily calibration
2. ✅ Monthly calibration review
3. ✅ Alert if calibration degrades
4. ✅ Retune quarterly

---

## 🎯 BOTTOM LINE

**Your 80%+ confidence picks are only 67.7% accurate. This is killing your betting ROI.**

**Fix Priority:**
1. Emergency temperature drop (TODAY)
2. Isotonic calibration on validation set (WEEK 1)
3. Continuous monitoring (ONGOING)

**Expected Result:**
- 80%+ picks → 78-82% accurate ✅
- Users can trust confidence scores ✅
- Betting ROI improves dramatically ✅

**Let's fix this immediately!** 🚀
