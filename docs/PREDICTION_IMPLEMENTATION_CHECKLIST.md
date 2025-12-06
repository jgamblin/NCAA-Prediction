# Prediction Improvement Implementation Checklist

## 🚨 CRITICAL ISSUE
**Your model is 20.4% overconfident!**
- Claims 77.5% average confidence
- Actually achieves 57.1% accuracy
- 80%+ confidence games only 67.7% accurate (should be 80%+)

---

## ✅ Phase 1: Fix Calibration (WEEK 1)

### Task 1.1: Implement Train/Val/Test Split ⏱️ 4 hours
**File**: `model_training/train_val_split.py`

- [ ] Create temporal split function
- [ ] Ensure no data leakage
- [ ] Default: 14 days validation, 7 days test
- [ ] Add to AdaptivePredictor.fit()
- [ ] Test with historical data

**Validation**:
```bash
python -c "
from model_training.train_val_split import temporal_split
from backend.repositories.games_repository import GamesRepository
games = GamesRepository(db).get_completed_games_df()
train, val, test = temporal_split(games)
print(f'Train: {len(train)}, Val: {len(val)}, Test: {len(test)}')
assert len(val) > 0
assert len(test) > 0
"
```

---

### Task 1.2: Add Isotonic Regression Calibration ⏱️ 3 hours
**File**: `model_training/adaptive_predictor.py`

- [ ] Import IsotonicRegression from sklearn
- [ ] Add self.isotonic_calibrator attribute
- [ ] Fit calibrator on validation set (NOT training)
- [ ] Apply in predict() method
- [ ] Test calibration improvement

**Code Location**: After line 913 (after model.fit)
```python
# Calibrate on validation set
from sklearn.isotonic import IsotonicRegression
self.isotonic_calibrator = IsotonicRegression(out_of_bounds='clip')

val_probs = self.model.predict_proba(X_val)[:, 1]
self.isotonic_calibrator.fit(val_probs, y_val)
print(f"✓ Isotonic calibration fitted on {len(y_val)} validation games")
```

**Validation**:
- Check that calibrated probs are different from raw probs
- Measure ECE before/after calibration

---

### Task 1.3: Tune Temperature Scaling on Validation ⏱️ 2 hours
**File**: `model_training/adaptive_predictor.py`

- [ ] Change _configure_confidence_temperature to use validation set
- [ ] Grid search temperatures [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
- [ ] Choose temp that minimizes calibration error
- [ ] Log chosen temperature

**Code Location**: Line 746-791 (_configure_confidence_temperature)
```python
def _configure_confidence_temperature(self, X_val, y_val):
    """Tune temperature on VALIDATION set."""
    # Get base probabilities on validation
    val_probs = self.model.predict_proba(X_val)[:, 1]
    val_probs = self._apply_home_court_shift(val_probs)
    
    # Grid search for best temperature
    best_temp = 0.85
    best_ece = float('inf')
    
    for temp in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        scaled = 0.5 + (val_probs - 0.5) * temp
        ece = expected_calibration_error(y_val, scaled)
        if ece < best_ece:
            best_ece = ece
            best_temp = temp
    
    self.confidence_temperature_value = best_temp
    print(f"✓ Temperature tuned on validation: {best_temp:.2f} (ECE: {best_ece:.4f})")
```

---

### Task 1.4: Add Calibration Metrics ⏱️ 2 hours
**File**: `model_training/calibration_metrics.py` (NEW)

- [ ] Implement expected_calibration_error()
- [ ] Implement reliability_diagram()
- [ ] Implement brier_score()
- [ ] Add to prediction pipeline

```python
def expected_calibration_error(y_true, y_pred, n_bins=10):
    """Calculate Expected Calibration Error."""
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

def brier_score(y_true, y_pred):
    """Calculate Brier Score (lower is better)."""
    return np.mean((y_pred - y_true) ** 2)
```

**Validation**:
```bash
pytest tests/test_calibration_metrics.py
```

---

## ✅ Phase 2: Reduce Overfitting (WEEK 2)

### Task 2.1: Hyperparameter Tuning ⏱️ 6 hours
**File**: `scripts/tune_hyperparameters.py` (NEW)

- [ ] Create grid search script
- [ ] Use validation set for evaluation
- [ ] Test RandomForest params: max_depth [8,10,12], min_samples_split [20,30,50]
- [ ] Test XGBoost params: max_depth [4,6,8], learning_rate [0.05,0.1,0.15]
- [ ] Save best params to config

**Grid**:
```python
param_grid = {
    'random_forest': {
        'max_depth': [8, 10, 12],
        'min_samples_split': [20, 30, 50],
        'min_samples_leaf': [10, 15, 20],
        'max_features': ['sqrt', 'log2'],
    },
    'xgboost': {
        'max_depth': [4, 6, 8],
        'learning_rate': [0.05, 0.1, 0.15],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
    }
}
```

**Run**:
```bash
python scripts/tune_hyperparameters.py --val-days 14 --test-days 7
```

---

### Task 2.2: Feature Selection ⏱️ 4 hours
**File**: `scripts/feature_selection.py` (NEW)

- [ ] Calculate permutation importance on validation set
- [ ] Remove features with importance < 0.01
- [ ] Check multicollinearity (VIF)
- [ ] Create feature importance report

```python
from sklearn.inspection import permutation_importance

# Calculate on validation set
result = permutation_importance(
    model, X_val, y_val, 
    n_repeats=10,
    random_state=42
)

# Remove low-importance features
important_features = [
    feat for feat, imp in zip(features, result.importances_mean)
    if imp > 0.01
]

print(f"Reduced features: {len(features)} → {len(important_features)}")
```

**Run**:
```bash
python scripts/feature_selection.py --output data/selected_features.json
```

---

### Task 2.3: Add Regularization ⏱️ 1 hour
**File**: `model_training/adaptive_predictor.py`

- [ ] RandomForest: Add max_features='sqrt'
- [ ] XGBoost: Verify reg_alpha and reg_lambda
- [ ] Test impact on train/val gap

**Code Location**: Lines 198-206
```python
else:
    base_model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,  # Reduce to 10 from 20
        min_samples_split=min_samples_split,  # Increase to 30 from 10
        max_features='sqrt',  # ADD THIS
        random_state=42,
        n_jobs=-1
    )
```

---

## ✅ Phase 3: Testing & Validation (WEEK 3)

### Task 3.1: Create Test Suite ⏱️ 6 hours
**File**: `tests/test_prediction_calibration.py` (NEW)

- [ ] Test overall calibration (gap < 5%)
- [ ] Test confidence buckets (80%+ → >78% accurate)
- [ ] Test ECE < 0.05
- [ ] Test Brier score improvement

```python
class TestPredictionCalibration:
    def test_overall_calibration(self):
        """Overall confidence should match accuracy within 5%."""
        results = evaluate_on_test_set()
        avg_conf = results['confidence'].mean()
        accuracy = results['correct'].mean()
        gap = abs(avg_conf - accuracy)
        
        assert gap < 0.05, f"Calibration gap too large: {gap:.1%}"
    
    def test_high_confidence_accuracy(self):
        """80%+ confidence should be 78%+ accurate."""
        high_conf = results[results['confidence'] >= 0.80]
        accuracy = high_conf['correct'].mean()
        
        assert accuracy >= 0.78, f"High conf games only {accuracy:.1%} accurate"
```

---

### Task 3.2: Backtesting Framework ⏱️ 8 hours
**File**: `scripts/backtest_predictions.py` (NEW)

- [ ] Load historical data (2024-25 season)
- [ ] Implement rolling window backtest
- [ ] Track accuracy, calibration, ROI over time
- [ ] Generate backtest report

```python
def rolling_backtest(data, window=90, step=7):
    """Rolling window backtest."""
    results = []
    
    dates = sorted(data['date'].unique())
    for i in range(window, len(dates), step):
        train_end = dates[i]
        train_start = dates[i - window]
        test_end = dates[min(i + step, len(dates) - 1)]
        
        # Train
        train_data = data[data['date'].between(train_start, train_end)]
        model.fit(train_data)
        
        # Predict
        test_data = data[data['date'].between(train_end, test_end)]
        preds = model.predict(test_data)
        
        # Evaluate
        accuracy = (preds['predicted_winner'] == test_data['actual_winner']).mean()
        ece = expected_calibration_error(
            test_data['actual_winner'], 
            preds['confidence']
        )
        
        results.append({
            'period': f"{train_end} to {test_end}",
            'games': len(test_data),
            'accuracy': accuracy,
            'ece': ece,
            'avg_confidence': preds['confidence'].mean()
        })
    
    return pd.DataFrame(results)
```

**Run**:
```bash
python scripts/backtest_predictions.py --season 2024-25 --window 90 --step 7
```

---

### Task 3.3: Calibration Audit ⏱️ 3 hours
**File**: `scripts/calibration_audit.py` (NEW)

- [ ] Generate calibration curves (reliability diagrams)
- [ ] Calculate ECE for current model
- [ ] Compare before/after improvements
- [ ] Save calibration report

```python
import matplotlib.pyplot as plt

def plot_calibration_curve(y_true, y_pred, n_bins=10):
    """Plot reliability diagram."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bins) - 1
    
    bin_accuracies = []
    bin_confidences = []
    
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_accuracies.append(y_true[mask].mean())
            bin_confidences.append(y_pred[mask].mean())
    
    plt.figure(figsize=(8, 8))
    plt.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration')
    plt.plot(bin_confidences, bin_accuracies, 'o-', label='Model')
    plt.xlabel('Confidence')
    plt.ylabel('Accuracy')
    plt.title('Calibration Curve')
    plt.legend()
    plt.grid(True)
    plt.savefig('docs/calibration_curve.png')
```

**Run**:
```bash
python scripts/calibration_audit.py --output docs/calibration_report.md
```

---

## ✅ Phase 4: Deploy & Monitor (WEEK 4)

### Task 4.1: Update Daily Pipeline ⏱️ 2 hours
**File**: `daily_pipeline_db.py`

- [ ] Add calibration metrics logging
- [ ] Add train/val split
- [ ] Use new calibrated model
- [ ] Log ECE and Brier score

**Code Location**: After predictions generated
```python
# Log calibration metrics
print("\n" + "="*80)
print("CALIBRATION CHECK")
print("="*80)
print(f"  Average Confidence: {predictions['confidence'].mean():.1%}")
print(f"  Expected Accuracy:  ~{predictions['confidence'].mean():.1%}")
print(f"  High Conf (80%+):   {len(predictions[predictions['confidence'] >= 0.80])} games")
print(f"  Note: Actual accuracy will be measured after games complete")
```

---

### Task 4.2: Add Monitoring Dashboard ⏱️ 4 hours
**File**: `scripts/monitor_calibration.py` (NEW)

- [ ] Track daily calibration metrics
- [ ] Store in calibration_tracking table
- [ ] Alert if calibration degrades
- [ ] Generate weekly calibration report

```python
def log_calibration_metrics(predictions, date):
    """Log daily calibration for tracking."""
    metrics = {
        'date': date,
        'predictions_made': len(predictions),
        'avg_confidence': predictions['confidence'].mean(),
        'high_conf_count': len(predictions[predictions['confidence'] >= 0.80]),
        'model_version': get_model_version(),
    }
    
    # Store in database
    db.execute("""
        INSERT INTO calibration_tracking VALUES (?, ?, ?, ?, ?)
    """, metrics.values())
```

---

### Task 4.3: Documentation Update ⏱️ 2 hours
**Files**: `README.md`, `docs/MODEL_PERFORMANCE.md`

- [ ] Document calibration improvements
- [ ] Update performance metrics
- [ ] Add calibration curve images
- [ ] Explain confidence scores

**Add to README**:
```markdown
## Model Confidence Scores

Our predictions include confidence scores that are **well-calibrated**:

- **80%+ confidence**: Historically 80% accurate
- **70-80% confidence**: Historically 75% accurate  
- **60-70% confidence**: Historically 65% accurate

Confidence scores are tuned using validation data and isotonic regression 
to ensure they match actual win rates.
```

---

## 🎯 Quick Wins (Do First!)

### 1. Lower Temperature Immediately ⏱️ 2 minutes
**File**: `config/feature_flags.json`

```json
{
  "temperature_override": 0.65
}
```

**Impact**: Reduces overconfidence immediately

---

### 2. More Conservative Early Season ⏱️ 5 minutes
**File**: `model_training/adaptive_predictor.py` line 362

```python
# Change minimum factor from 0.80 to 0.60
else:
    games_factor = 0.60  # Was 0.80
```

**Impact**: Early season games more realistic confidence

---

### 3. Add Calibration Logging ⏱️ 10 minutes
**File**: `daily_pipeline_db.py` after predictions

```python
print(f"\n{'='*80}")
print("CONFIDENCE CALIBRATION CHECK")
print(f"{'='*80}")
print(f"Predictions generated: {len(predictions)}")
print(f"Average confidence: {predictions['confidence'].mean():.1%}")
print(f"High confidence (80%+): {len(predictions[predictions['confidence'] >= 0.80])} games")
print(f"\n⚠️  Confidence should match actual accuracy after games complete")
print(f"{'='*80}\n")
```

---

## 📊 Success Metrics

### Before (Current)
```
Overall: 57.1% accuracy, 77.5% confidence → 20.4% overconfident
80%+ confidence: 67.7% accuracy → 12.3% overconfident
70-80% confidence: 48.4% accuracy → 21.6% overconfident
ECE: ~0.15 (estimated)
```

### After (Target)
```
Overall: 65% accuracy, 67% confidence → 2% overconfident ✅
80%+ confidence: 80% accuracy → well-calibrated ✅
70-80% confidence: 73% accuracy → well-calibrated ✅
ECE: <0.05 ✅
```

---

## 🧪 Testing Checklist

- [ ] Unit tests for calibration metrics
- [ ] Integration tests for train/val split
- [ ] Backtest on 2024-25 season
- [ ] Validate on held-out test set
- [ ] Check calibration curves
- [ ] Measure ECE improvement
- [ ] Calculate Brier score improvement
- [ ] Test with ensemble model

---

## 📝 Daily Workflow (After Implementation)

1. **Run pipeline**: `python daily_pipeline_db.py`
2. **Check calibration**: Review logged metrics
3. **Monitor accuracy**: Track actual vs predicted
4. **Weekly review**: Run calibration audit
5. **Monthly retune**: Update hyperparameters if needed

---

## 🚨 Red Flags to Watch

- [ ] Calibration gap > 10%
- [ ] ECE > 0.08
- [ ] Overall accuracy < 60%
- [ ] High confidence games < 75% accurate
- [ ] Train/val accuracy gap > 10%

---

## 💡 Key Principles

1. **Never calibrate on training data** - always use validation
2. **Temporal splits only** - random splits leak information
3. **Monitor continuously** - calibration drifts over time
4. **Simpler is better** - fewer features, better calibration
5. **Test everything** - automated tests prevent regression

---

## ✅ Definition of Done

- [ ] ECE < 0.05 on validation set
- [ ] 80%+ confidence games are 78-82% accurate
- [ ] Overall calibration gap < 5%
- [ ] All tests passing
- [ ] Backtest on 2024-25 complete
- [ ] Documentation updated
- [ ] Monitoring in place

---

## 📞 Next Steps

1. **Start with Quick Wins** (30 mins)
2. **Implement Phase 1** (Week 1)
3. **Run backtest to validate** (Week 3)
4. **Deploy to production** (Week 4)

**Goal**: Go from overconfident 57% → well-calibrated 67% in 4 weeks! 🎯
