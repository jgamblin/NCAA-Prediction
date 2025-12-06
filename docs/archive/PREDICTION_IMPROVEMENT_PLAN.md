# Prediction Logic Improvement Plan

## 🚨 Critical Issues Identified

### 1. Severe Overconfidence Problem

**Current Performance (2025-26 Season):**
```
Overall Accuracy: 57.1% (928 games)
Average Confidence: 77.5%

Confidence vs Actual Performance:
├─ 80%+ confidence → 67.7% accuracy (12.3% overconfident)
├─ 70-80% confidence → 48.4% accuracy (21.6% overconfident!)
├─ 60-70% confidence → 37.0% accuracy (23% overconfident!)
└─ <60% confidence → 26.1% accuracy
```

**Problem**: Model claims 80% confidence but only achieves 67.7% accuracy. This is a **severe calibration failure**.

**Impact**:
- Betting decisions based on false confidence
- Users trust predictions that aren't trustworthy
- ROI calculations are wrong
- 77.5% avg confidence vs 57.1% actual = **20.4% overconfidence**

---

## 📊 Root Cause Analysis

### Issue #1: Temperature Scaling Not Working
**Location**: `adaptive_predictor.py` lines 684-693

```python
def _apply_confidence_temperature(self, probabilities):
    """Apply confidence temperature scaling around 0.5."""
    temp = float(self.confidence_temperature_value)
    # ...
    centered = probabilities - 0.5
    adjusted = 0.5 + centered * temp
```

**Problems**:
1. Temperature auto-calibration uses training data (lines 770-782)
2. Should use validation holdout for calibration
3. Current temp = 0.85 isn't aggressive enough
4. Temperature is applied AFTER home court shift, not before

**Proposed Fix**:
- Use proper validation set for temperature tuning
- Target: confidence = accuracy (perfect calibration)
- More aggressive temperature (0.6-0.7 range)

---

### Issue #2: Home Court Shift Miscalibrated
**Location**: `adaptive_predictor.py` lines 695-744

```python
def _configure_home_court_shift(self, X, y):
    """Determine home-court logit adjustment based on configuration."""
```

**Problems**:
1. Calibrates to training data (should use validation)
2. Target of 0.55 home win rate may not match reality
3. Applied before temperature scaling (compounds calibration issues)

**Current Reality Check**:
```sql
-- Historical home win rate in NCAA is ~60%
-- Model is trying to hit 55%
-- This may be creating bias
```

---

### Issue #3: Overfitting to Training Data
**Location**: `adaptive_predictor.py` lines 835-954

**Evidence**:
- Training accuracy: Not logged, but likely 70-75%
- Actual accuracy: 57.1%
- **Gap: 13-18% overfit**

**Causes**:
1. No proper train/validation split (temporal split mentioned but not used)
2. Calibration uses same data as training
3. Feature importance may be overfitted
4. RandomForest max_depth=20 is very deep (prone to overfit)

---

### Issue #4: Early Season Adjustment Too Weak
**Location**: `adaptive_predictor.py` lines 334-364

```python
def _get_early_season_confidence_factor(self, game_date, home_games, away_games):
    """Returns factor between 0.8 and 1.0"""
    # min_games < 3 → factor = 0.80
```

**Problem**:
- Only reduces confidence to 80% minimum
- But those games have <40% accuracy!
- Should reduce to 50-60% confidence

---

### Issue #5: Feature Engineering May Be Excessive
**Current Features**: 40+ features across 4 phases

**Potential Issues**:
- Phase 2: Power ratings (may duplicate existing features)
- Phase 3: Ensemble not being used (flag=false)
- Phase 4: Conference strength, momentum (added complexity)
- Risk of multicollinearity
- Risk of overfitting

**Need to**:
- Feature importance analysis
- Remove redundant features
- Simplify before adding complexity

---

## 🎯 Improvement Plan

### Phase 1: Fix Calibration (CRITICAL - Week 1)

#### Task 1.1: Implement Proper Train/Val/Test Split
**File**: `model_training/train_val_split.py` (NEW)

```python
def temporal_split(df, val_days=14, test_days=7):
    """
    Split data temporally:
    - Training: All games up to (latest - val_days - test_days)
    - Validation: Games in (latest - val_days - test_days) to (latest - test_days)
    - Test: Last test_days of games
    """
    df_sorted = df.sort_values('date')
    latest_date = df_sorted['date'].max()
    
    test_start = latest_date - timedelta(days=test_days)
    val_start = test_start - timedelta(days=val_days)
    
    train_df = df_sorted[df_sorted['date'] < val_start]
    val_df = df_sorted[(df_sorted['date'] >= val_start) & (df_sorted['date'] < test_start)]
    test_df = df_sorted[df_sorted['date'] >= test_start]
    
    return train_df, val_df, test_df
```

**Impact**: Prevents overfitting, enables proper calibration

---

#### Task 1.2: Recalibrate Using Validation Set
**File**: `model_training/calibration.py` (NEW)

```python
class TemperatureScaling:
    """Find optimal temperature using validation set."""
    
    def fit(self, val_probs, val_labels):
        """Find temperature that minimizes calibration error."""
        def calibration_loss(temp):
            scaled = 0.5 + (val_probs - 0.5) * temp
            brier = np.mean((scaled - val_labels) ** 2)
            return brier
        
        # Grid search for best temperature
        temps = np.linspace(0.3, 1.0, 50)
        losses = [calibration_loss(t) for t in temps]
        best_temp = temps[np.argmin(losses)]
        
        self.temperature = best_temp
        return self
```

**Target**: Confidence = Accuracy (±2%)

---

#### Task 1.3: Add Isotonic Regression Calibration
**File**: `adaptive_predictor.py` modifications

```python
from sklearn.isotonic import IsotonicRegression

# After model training, calibrate on validation set
self.isotonic_calibrator = IsotonicRegression(out_of_bounds='clip')
self.isotonic_calibrator.fit(val_probs, val_labels)

# In predict():
raw_probs = self.model.predict_proba(X)[:, 1]
calibrated_probs = self.isotonic_calibrator.transform(raw_probs)
```

**Why**: Isotonic regression is more flexible than temperature scaling

---

### Phase 2: Reduce Overfitting (Week 2)

#### Task 2.1: Hyperparameter Tuning
**Current Issues**:
```python
# RandomForest
max_depth=20          # TOO DEEP → Change to 10-12
min_samples_split=10  # TOO LOW → Change to 20-30

# XGBoost
max_depth=6           # OKAY but tune
learning_rate=0.1     # Could be lower for stability
```

**Tuning Grid**:
```python
param_grid = {
    'max_depth': [8, 10, 12],
    'min_samples_split': [20, 30, 50],
    'min_samples_leaf': [10, 15, 20],
    'n_estimators': [100, 150, 200]
}
```

---

#### Task 2.2: Feature Selection & Importance
**File**: `scripts/feature_importance_analysis.py` (NEW)

**Actions**:
1. Calculate permutation importance on validation set
2. Remove features with importance < 0.01
3. Check for multicollinearity (VIF > 5)
4. Create feature importance report

**Expected**: Reduce from 40+ to ~20-25 core features

---

#### Task 2.3: Regularization
**Add**:
```python
# For Random Forest
max_features='sqrt'  # Adds randomness, reduces overfit

# For XGBoost (already has some)
reg_alpha=0.1      # L1 regularization
reg_lambda=1.0     # L2 regularization
```

---

### Phase 3: Model Validation & Testing (Week 3)

#### Task 3.1: Create Comprehensive Test Suite
**File**: `tests/test_prediction_accuracy.py` (NEW)

```python
class TestPredictionAccuracy:
    """Test prediction calibration and accuracy."""
    
    def test_calibration_error(self):
        """Confidence should match accuracy within 5%."""
        for bucket in ['60-70%', '70-80%', '80%+']:
            conf_games = predictions[predictions['confidence'].between(low, high)]
            accuracy = conf_games['correct'].mean()
            expected_conf = (low + high) / 2
            
            assert abs(accuracy - expected_conf) < 0.05, \
                f"{bucket} miscalibrated: {accuracy:.1%} vs {expected_conf:.1%}"
    
    def test_overall_accuracy_threshold(self):
        """Overall accuracy should be > 60%."""
        assert overall_accuracy > 0.60
    
    def test_high_confidence_accuracy(self):
        """80%+ confidence games should be 75%+ accurate."""
        high_conf = predictions[predictions['confidence'] >= 0.80]
        assert high_conf['correct'].mean() >= 0.75
```

---

#### Task 3.2: Backtesting Framework
**File**: `scripts/backtest_predictions.py` (NEW)

```python
def rolling_backtest(historical_data, window_days=90, step_days=7):
    """
    Rolling window backtest:
    - Train on last window_days
    - Predict next step_days
    - Compare predictions vs actuals
    - Track accuracy, calibration, profitability
    """
    results = []
    for start_date in date_range:
        train_end = start_date
        train_start = train_end - timedelta(days=window_days)
        test_end = train_end + timedelta(days=step_days)
        
        # Train model
        train_data = historical_data[
            (historical_data['date'] >= train_start) & 
            (historical_data['date'] < train_end)
        ]
        model.fit(train_data)
        
        # Predict
        test_data = historical_data[
            (historical_data['date'] >= train_end) & 
            (historical_data['date'] < test_end)
        ]
        preds = model.predict(test_data)
        
        # Evaluate
        results.append({
            'period': f"{train_end} to {test_end}",
            'accuracy': accuracy_score(test_data['actual'], preds['predicted']),
            'calibration_error': calibration_error(preds),
            'roi': calculate_roi(preds, test_data)
        })
    
    return pd.DataFrame(results)
```

---

#### Task 3.3: Prediction Confidence Audit
**File**: `scripts/audit_predictions.py` (NEW)

**Check**:
1. **Calibration curve**: Plot predicted prob vs actual win rate
2. **Brier score**: Measure probability accuracy
3. **Log loss**: Penalize confident wrong predictions
4. **ECE (Expected Calibration Error)**: Standard calibration metric

```python
def expected_calibration_error(y_true, y_pred, n_bins=10):
    """Calculate ECE - how miscalibrated are we?"""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bins) - 1
    
    ece = 0.0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_accuracy = y_true[mask].mean()
            bin_confidence = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_accuracy - bin_confidence)
    
    return ece
```

**Target**: ECE < 0.05 (well-calibrated)
**Current**: Likely ECE > 0.15 (poorly calibrated)

---

### Phase 4: Advanced Improvements (Week 4)

#### Task 4.1: Ensemble Model (Currently Disabled)
**File**: `config/feature_flags.json`

```json
{
  "use_ensemble": true,
  "ensemble_weights": {
    "xgboost": 0.40,
    "random_forest": 0.35,
    "logistic": 0.25
  }
}
```

**Why**: Ensemble reduces variance, improves calibration

---

#### Task 4.2: Uncertainty Quantification
**Add**: Prediction intervals, not just point estimates

```python
class PredictionWithUncertainty:
    """Provide confidence intervals for predictions."""
    
    def predict_with_uncertainty(self, X):
        """Return prediction + 95% confidence interval."""
        # Use bootstrap or quantile regression
        predictions = []
        for bootstrap_sample in bootstrap_samples:
            pred = model.predict(bootstrap_sample)
            predictions.append(pred)
        
        return {
            'prediction': np.mean(predictions),
            'confidence_lower': np.percentile(predictions, 2.5),
            'confidence_upper': np.percentile(predictions, 97.5),
            'uncertainty': np.std(predictions)
        }
```

---

#### Task 4.3: Contextual Confidence Adjustment
**Idea**: Adjust confidence based on game context

```python
def adjust_confidence_contextually(base_confidence, game_features):
    """Reduce confidence in uncertain situations."""
    multipliers = []
    
    # Rivalry game → more unpredictable
    if game_features['is_rivalry']:
        multipliers.append(0.90)
    
    # Tournament game → higher variance
    if game_features['is_tournament']:
        multipliers.append(0.85)
    
    # First game of season → very uncertain
    if game_features['games_played'] < 3:
        multipliers.append(0.70)
    
    # Conference championship → unpredictable
    if game_features['is_championship']:
        multipliers.append(0.88)
    
    return base_confidence * np.prod(multipliers)
```

---

## 📈 Success Metrics

### Calibration Metrics (PRIMARY)
| Metric | Current | Target | Critical |
|--------|---------|--------|----------|
| Overall Calibration Gap | 20.4% | <5% | ✅ |
| ECE (Expected Calibration Error) | ~0.15 | <0.05 | ✅ |
| 80%+ confidence accuracy | 67.7% | >78% | ✅ |
| 70-80% confidence accuracy | 48.4% | >68% | ✅ |
| 60-70% confidence accuracy | 37.0% | >58% | ✅ |

### Accuracy Metrics (SECONDARY)
| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| Overall Accuracy | 57.1% | >65% | High |
| High Confidence (80%+) Games | 67.7% | >75% | High |
| ROI (if betting $100/game) | Unknown | >10% | Medium |

### Model Health Metrics
| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| Train/Val Accuracy Gap | Unknown | <8% | High |
| Feature Count | 40+ | 20-25 | Medium |
| Training Time | Unknown | <5 min | Low |

---

## 🧪 Testing Strategy

### Unit Tests
```bash
# Test calibration
pytest tests/test_calibration.py

# Test feature engineering
pytest tests/test_features.py

# Test model accuracy
pytest tests/test_model_accuracy.py
```

### Integration Tests
```bash
# End-to-end prediction pipeline
pytest tests/test_prediction_pipeline.py

# Database integration
pytest tests/test_database_predictions.py
```

### Performance Tests
```bash
# Backtest on historical data (2024-25 season)
python scripts/backtest_predictions.py --season 2024-25

# Rolling window validation
python scripts/rolling_validation.py --window 90 --step 7
```

---

## 📅 Implementation Timeline

### Week 1: Critical Calibration Fixes
- [ ] Day 1-2: Implement train/val/test split
- [ ] Day 3-4: Add isotonic regression calibration
- [ ] Day 5: Tune temperature scaling on validation set
- [ ] Day 6-7: Test and validate improvements

**Expected Impact**: Calibration gap 20% → 8%

---

### Week 2: Overfit Reduction
- [ ] Day 1-2: Hyperparameter tuning with cross-validation
- [ ] Day 3-4: Feature selection and importance analysis
- [ ] Day 5: Add regularization
- [ ] Day 6-7: Test and measure accuracy improvement

**Expected Impact**: Accuracy 57% → 63%

---

### Week 3: Testing & Validation
- [ ] Day 1-2: Build comprehensive test suite
- [ ] Day 3-4: Create backtesting framework
- [ ] Day 5: Run historical backtest (2024-25)
- [ ] Day 6-7: Analyze results, iterate

**Expected Impact**: Confidence in model improvements

---

### Week 4: Advanced Features
- [ ] Day 1-2: Enable and tune ensemble model
- [ ] Day 3-4: Add uncertainty quantification
- [ ] Day 5: Contextual confidence adjustment
- [ ] Day 6-7: Final testing and deployment

**Expected Impact**: Accuracy 63% → 67%, Calibration gap → <5%

---

## 🚀 Quick Wins (Can Do Today)

### 1. Disable Overconfident Predictions
**File**: `config/feature_flags.json`
```json
{
  "temperature_override": 0.65  // Force more conservative confidence
}
```

### 2. Early Season Adjustment
**File**: `adaptive_predictor.py` line 362
```python
# Change from 0.80 minimum to 0.60
else:
    games_factor = 0.60  # Was 0.80
```

### 3. Add Calibration Logging
**File**: `daily_pipeline_db.py`
```python
# After generating predictions
print(f"\nCalibration Check:")
print(f"  Avg Confidence: {predictions['confidence'].mean():.1%}")
print(f"  Expected Accuracy: ~{predictions['confidence'].mean():.1%}")
print(f"  (Will verify after games complete)")
```

---

## 📊 Monitoring Dashboard (Future)

### Real-Time Calibration Tracking
```python
# Track daily calibration
calibration_metrics = {
    'date': today,
    'predictions_made': count,
    'avg_confidence': avg_conf,
    'actual_accuracy': actual_acc,
    'calibration_error': abs(avg_conf - actual_acc),
    'brier_score': brier,
    'log_loss': logloss
}
```

### Alerts
- Alert if calibration_error > 10%
- Alert if accuracy drops below 55%
- Alert if high-confidence games < 70% accurate

---

## 🎓 Learning Resources

### Probability Calibration
- [Scikit-learn Calibration Guide](https://scikit-learn.org/stable/modules/calibration.html)
- [On Calibration of Modern Neural Networks (2017)](https://arxiv.org/abs/1706.04599)

### NCAA Basketball Prediction
- Historical home win rate: ~60%
- Upset rate (unranked beats ranked): ~25%
- Tournament variance: Much higher than regular season

### Metrics
- **Brier Score**: Measures probability accuracy (lower is better)
- **ECE**: Expected Calibration Error (lower is better)
- **Sharpness**: How far from 50% are predictions (higher = more decisive)

---

## 💡 Key Insights

1. **Calibration > Accuracy**: A 60% accurate, well-calibrated model is better than a 70% accurate, overconfident model
2. **Validation is Critical**: Never calibrate on training data
3. **Temporal Splits Matter**: Random splits leak future information
4. **Simple Often Better**: Fewer features, simpler models, better calibration
5. **Monitor Continuously**: Calibration drifts over time, needs tracking

---

## ✅ Definition of Done

### Calibration Fixed
- [ ] ECE < 0.05
- [ ] 80%+ confidence games are 78%+ accurate
- [ ] Overall calibration gap < 5%
- [ ] Brier score improved by >20%

### Accuracy Improved
- [ ] Overall accuracy > 65%
- [ ] High confidence games > 75%
- [ ] Train/val gap < 8%

### Testing Complete
- [ ] All unit tests passing
- [ ] Backtest on 2024-25 season complete
- [ ] Rolling validation passing
- [ ] Documentation updated

---

## 🔄 Continuous Improvement

### Monthly Reviews
- Review calibration metrics
- Analyze prediction errors
- Feature importance refresh
- Hyperparameter retuning

### Seasonal Updates
- Retrain on new season data
- Update team encodings
- Refresh power ratings
- Validate calibration

---

## 📝 Notes

- **Current model is significantly overconfident** - this is the #1 priority
- **57% accuracy is below acceptable** - should be 65%+
- **Lots of features may be causing overfitting** - need feature selection
- **No proper validation split** - must fix before anything else
- **Good foundation** - phases 1-4 are well-structured, just need calibration

---

## 🎯 Bottom Line

**The prediction engine has good bones but critical calibration issues.**

**Priority 1**: Fix calibration (confidence should = accuracy)
**Priority 2**: Reduce overfitting (improve actual accuracy)
**Priority 3**: Better testing (prevent regression)

**Timeline**: 4 weeks to go from 57% accuracy + overconfident → 67% accuracy + well-calibrated

**Success = Users can trust the confidence scores for betting decisions**
