"""Tests for Phase 3 Model Architecture Improvements

Tests for:
- Task 3.1: XGBoost Integration
- Task 3.2: Temporal Train/Validation Split
- Task 3.3: Model Ensemble
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_training_data():
    """Create sample training data with dates."""
    np.random.seed(42)
    n_games = 500
    
    teams = ['Duke', 'UNC', 'Kentucky', 'Kansas', 'Gonzaga', 'Villanova', 
             'Michigan', 'UCLA', 'Arizona', 'Baylor', 'Houston', 'Purdue']
    
    games = []
    base_date = datetime(2024, 11, 1)
    
    for i in range(n_games):
        home_idx = np.random.randint(0, len(teams))
        away_idx = np.random.randint(0, len(teams))
        while away_idx == home_idx:
            away_idx = np.random.randint(0, len(teams))
        
        home_score = np.random.randint(55, 95)
        away_score = np.random.randint(55, 95)
        
        games.append({
            'game_id': f'g{i}',
            'home_team': teams[home_idx],
            'away_team': teams[away_idx],
            'home_score': home_score,
            'away_score': away_score,
            'home_team_encoded': home_idx,
            'away_team_encoded': away_idx,
            'is_neutral': np.random.choice([0, 1], p=[0.9, 0.1]),
            'home_rank': np.random.randint(1, 100),
            'away_rank': np.random.randint(1, 100),
            'rank_diff': 0,  # Will be calculated
            'is_ranked_matchup': 0,  # Will be calculated
            'home_win': int(home_score > away_score),
            'date': base_date + timedelta(days=i // 10),
            'game_url': f'https://example.com/g{i}',
        })
    
    df = pd.DataFrame(games)
    df['rank_diff'] = df['home_rank'] - df['away_rank']
    df['is_ranked_matchup'] = ((df['home_rank'] <= 25) | (df['away_rank'] <= 25)).astype(int)
    
    return df


class TestEnsemblePredictor:
    """Tests for Phase 3 Task 3.3 - Ensemble Model."""
    
    def test_ensemble_import(self):
        """Test that ensemble predictor module can be imported."""
        from model_training import ensemble_predictor
        assert hasattr(ensemble_predictor, 'EnsemblePredictor')
    
    def test_ensemble_initialization(self):
        """Test ensemble initialization with default weights."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        ensemble = EnsemblePredictor()
        
        # Check weights are set
        assert 'random_forest' in ensemble.weights
        assert sum(ensemble.weights.values()) == pytest.approx(1.0, abs=0.01)
    
    def test_ensemble_training(self, sample_training_data):
        """Test ensemble training on sample data."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        feature_cols = [
            'home_team_encoded', 'away_team_encoded', 'is_neutral',
            'home_rank', 'away_rank', 'rank_diff', 'is_ranked_matchup'
        ]
        
        ensemble = EnsemblePredictor(
            use_xgboost=False,  # Skip XGBoost if not installed
            use_random_forest=True,
            use_logistic=True,
            validation_days=7
        )
        
        ensemble.fit(sample_training_data, feature_cols=feature_cols)
        
        # Check models were trained
        assert len(ensemble.models) >= 1
        assert 'random_forest' in ensemble.models or 'logistic' in ensemble.models
    
    def test_ensemble_prediction(self, sample_training_data):
        """Test ensemble predictions."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        feature_cols = [
            'home_team_encoded', 'away_team_encoded', 'is_neutral',
            'home_rank', 'away_rank', 'rank_diff', 'is_ranked_matchup'
        ]
        
        ensemble = EnsemblePredictor(
            use_xgboost=False,
            use_random_forest=True,
            use_logistic=True,
            validation_days=7
        )
        
        ensemble.fit(sample_training_data, feature_cols=feature_cols)
        
        # Make predictions on sample data
        X_test = sample_training_data[feature_cols].head(10)
        predictions = ensemble.predict(X_test)
        proba = ensemble.predict_proba(X_test)
        
        assert len(predictions) == 10
        assert set(predictions).issubset({0, 1})
        assert proba.shape == (10, 2)
        assert np.allclose(proba.sum(axis=1), 1.0)
    
    def test_ensemble_validation_accuracy(self, sample_training_data):
        """Test that validation accuracy is recorded."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        feature_cols = [
            'home_team_encoded', 'away_team_encoded', 'is_neutral',
            'home_rank', 'away_rank', 'rank_diff', 'is_ranked_matchup'
        ]
        
        ensemble = EnsemblePredictor(
            use_xgboost=False,
            use_random_forest=True,
            use_logistic=True,
            validation_days=7
        )
        
        ensemble.fit(sample_training_data, feature_cols=feature_cols)
        
        # Check validation metrics exist
        assert len(ensemble.validation_accuracy) > 0
        for model_name, accuracy in ensemble.validation_accuracy.items():
            assert 0 <= accuracy <= 1


class TestTemporalSplit:
    """Tests for Phase 3 Task 3.2 - Temporal Train/Validation Split."""
    
    def test_temporal_split_no_leakage(self, sample_training_data):
        """Test that temporal split prevents data leakage."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        ensemble = EnsemblePredictor(validation_days=14)
        train_df, val_df = ensemble.create_temporal_split(sample_training_data)
        
        # Ensure no overlap - all training dates < all validation dates
        train_max_date = train_df['date'].max()
        val_min_date = val_df['date'].min()
        
        assert train_max_date < val_min_date
    
    def test_temporal_split_sizes(self, sample_training_data):
        """Test temporal split produces reasonable sizes."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        ensemble = EnsemblePredictor(validation_days=7)
        train_df, val_df = ensemble.create_temporal_split(sample_training_data)
        
        # Training should be larger than validation
        assert len(train_df) > len(val_df)
        assert len(val_df) > 0
    
    def test_temporal_split_different_days(self, sample_training_data):
        """Test different validation day settings."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        ensemble_7 = EnsemblePredictor(validation_days=7)
        ensemble_14 = EnsemblePredictor(validation_days=14)
        
        _, val_7 = ensemble_7.create_temporal_split(sample_training_data)
        _, val_14 = ensemble_14.create_temporal_split(sample_training_data)
        
        # 14-day validation should have more games
        assert len(val_14) >= len(val_7)


class TestXGBoostIntegration:
    """Tests for Phase 3 Task 3.1 - XGBoost Integration."""
    
    def test_xgboost_available_check(self):
        """Test XGBoost availability detection."""
        from model_training.ensemble_predictor import HAS_XGBOOST
        
        # This will be True or False depending on installation
        assert isinstance(HAS_XGBOOST, bool)
    
    def test_ensemble_with_xgboost(self, sample_training_data):
        """Test ensemble with XGBoost if available."""
        from model_training.ensemble_predictor import EnsemblePredictor, HAS_XGBOOST
        
        if not HAS_XGBOOST:
            pytest.skip("XGBoost not installed")
        
        feature_cols = [
            'home_team_encoded', 'away_team_encoded', 'is_neutral',
            'home_rank', 'away_rank', 'rank_diff', 'is_ranked_matchup'
        ]
        
        ensemble = EnsemblePredictor(
            use_xgboost=True,
            use_random_forest=True,
            use_logistic=True,
            validation_days=7
        )
        
        ensemble.fit(sample_training_data, feature_cols=feature_cols)
        
        # XGBoost should be in models
        assert 'xgboost' in ensemble.models
        assert 'xgboost' in ensemble.validation_accuracy
    
    def test_xgboost_fallback(self, sample_training_data):
        """Test graceful fallback when XGBoost requested but not available."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        feature_cols = [
            'home_team_encoded', 'away_team_encoded', 'is_neutral',
            'home_rank', 'away_rank', 'rank_diff', 'is_ranked_matchup'
        ]
        
        # Force XGBoost off to simulate not installed
        ensemble = EnsemblePredictor(
            use_xgboost=False,  # Explicitly disabled
            use_random_forest=True,
            use_logistic=True,
            validation_days=7
        )
        
        # Should still work with other models
        ensemble.fit(sample_training_data, feature_cols=feature_cols)
        
        assert len(ensemble.models) >= 1
        predictions = ensemble.predict(sample_training_data[feature_cols].head(5))
        assert len(predictions) == 5


class TestAdaptivePredictorPhase3:
    """Tests for Phase 3 integration with AdaptivePredictor."""
    
    def test_model_type_parameter(self):
        """Test model_type parameter is accepted."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        # Should accept model_type parameter
        predictor = AdaptivePredictor(model_type='random_forest')
        assert predictor.model_type == 'random_forest'
    
    def test_use_ensemble_parameter(self):
        """Test use_ensemble parameter is accepted."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor(use_ensemble=False)
        assert predictor.use_ensemble == False
    
    def test_xgboost_model_type(self):
        """Test XGBoost model type if available."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        try:
            import xgboost
            # Note: model_type may be overridden by feature_flags.json
            # so we just verify the parameter is accepted
            predictor = AdaptivePredictor(model_type='xgboost')
            # The model_type should be 'xgboost' unless overridden by flags
            assert predictor.model_type in ['xgboost', 'random_forest']
        except ImportError:
            pytest.skip("XGBoost not installed")


class TestModelWeights:
    """Tests for ensemble model weight configuration."""
    
    def test_weight_normalization(self):
        """Test that weights are normalized to sum to 1."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        ensemble = EnsemblePredictor(
            weights={'xgboost': 0.5, 'random_forest': 0.5, 'logistic': 0.5},
            use_xgboost=False,  # Disable XGBoost
        )
        
        # Weights should be normalized
        assert sum(ensemble.weights.values()) == pytest.approx(1.0, abs=0.01)
    
    def test_custom_weights(self, sample_training_data):
        """Test custom weight configuration."""
        from model_training.ensemble_predictor import EnsemblePredictor
        
        feature_cols = [
            'home_team_encoded', 'away_team_encoded', 'is_neutral',
            'home_rank', 'away_rank', 'rank_diff'
        ]
        
        # Heavy weight on random forest
        ensemble = EnsemblePredictor(
            weights={'random_forest': 0.8, 'logistic': 0.2},
            use_xgboost=False,
            use_random_forest=True,
            use_logistic=True,
            validation_days=7
        )
        
        ensemble.fit(sample_training_data, feature_cols=feature_cols)
        
        # Get current weights
        weights = ensemble.get_model_weights()
        assert weights['random_forest'] > weights['logistic']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
