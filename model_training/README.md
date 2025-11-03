# Model Training

This directory contains scripts for training NCAA basketball prediction models.

## Scripts

### ncaa_predictions_v2.py (Recommended)
Enhanced prediction model with multi-season training and advanced features.

**Features:**
- Multi-season training data (5 seasons = 29,000+ games)
- Rolling window statistics (last 5/10 games)
- Team embeddings and historical features
- Time-weighted training (recent games weighted higher)
- RandomizedSearchCV hyperparameter optimization
- 30 advanced features

**Usage:**
```bash
python model_training/ncaa_predictions_v2.py
```

**Model Performance:**
- Accuracy: ~72-73%
- ROC-AUC: ~0.77-0.78
- Cross-Validation: ~72.5% ± 0.4%

**Output:**
- `data/NCAA_Game_Predictions.csv` - Game predictions
- `data/feature_importance.png` - Feature importance visualization
- Updated `README.md` with high-confidence predictions

### ncaa_predictions.py (Legacy)
Original simpler model using basic features.

**Features:**
- Single or multi-season support
- Basic team statistics
- GridSearchCV hyperparameter tuning
- 15 basic features

**Usage:**
```bash
python model_training/ncaa_predictions.py
```

## Model Architecture

Both models use scikit-learn pipelines with:
1. **Preprocessing**: Imputation + StandardScaler
2. **Classifier**: RandomForestClassifier
3. **Hyperparameter Tuning**: GridSearchCV or RandomizedSearchCV

## Feature Categories

### Team Identity (v2 only)
- Encoded team IDs for pattern recognition

### Rankings
- AP poll rankings (50 for unranked teams)
- Ranking differentials

### Historical Performance
- Season-long averages (points scored/allowed, win %)
- Multi-season aggregated statistics

### Recent Form (v2 only)
- Last 5 games: PPG, OPPG, Win %
- Last 10 games: Win %
- Win/loss streaks

### Context
- Home court advantage
- Neutral site indicators

## Training Strategy

**Time-Weighted Training (v2):**
- Recent seasons weighted higher in model training
- Prevents older data from dominating predictions
- Weights: 2024-25 (1.0), 2023-24 (0.9), 2022-23 (0.8), etc.

**Lagged Statistics:**
- Rolling statistics calculated using only past games
- Prevents look-ahead bias and data leakage
- Ensures realistic model evaluation

## Evaluation Metrics

- **Accuracy**: Overall correctness
- **ROC-AUC**: Ability to distinguish winners from losers
- **Log Loss**: Quality of probability estimates
- **Cross-Validation**: Generalization performance

## Future Improvements

See `IMPROVEMENT_PLAN.md` for detailed enhancement roadmap.
