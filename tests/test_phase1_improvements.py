"""
Unit tests for Phase 1 accuracy improvements.

Tests cover:
- Task 1.1: Feature store fallback hierarchy
- Task 1.2: Smart team encoding
- Task 1.3: Confidence temperature scaling
- Task 1.4: Early season detection
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFeatureStoreFallback:
    """Tests for Task 1.1: Feature Store Fallback Hierarchy"""
    
    def test_league_average_defaults(self):
        """Test that league average defaults are sensible."""
        from model_training.feature_store import LEAGUE_AVERAGE_DEFAULTS
        
        # Win percentage should be 0.5 (neutral)
        assert LEAGUE_AVERAGE_DEFAULTS['rolling_win_pct_5'] == 0.5
        assert LEAGUE_AVERAGE_DEFAULTS['rolling_win_pct_10'] == 0.5
        
        # Point differential should be 0 (neutral)
        assert LEAGUE_AVERAGE_DEFAULTS['rolling_point_diff_avg_5'] == 0.0
        assert LEAGUE_AVERAGE_DEFAULTS['rolling_point_diff_avg_10'] == 0.0
    
    def test_get_prior_season(self):
        """Test prior season calculation."""
        from model_training.feature_store import _get_prior_season
        
        assert _get_prior_season('2024-25') == '2023-24'
        assert _get_prior_season('2023-24') == '2022-23'
        assert _get_prior_season('2025') == '2024'
    
    def test_get_team_features_empty_store(self):
        """Test fallback when feature store is empty."""
        from model_training.feature_store import get_team_features_with_fallback
        
        empty_df = pd.DataFrame()
        result = get_team_features_with_fallback('test_team', '2024-25', empty_df)
        
        assert result['is_fallback'] == True
        assert result['fallback_type'] == 'empty_store'
        assert result['rolling_win_pct_5'] == 0.5
    
    def test_get_team_features_current_season(self):
        """Test using current season data when available."""
        from model_training.feature_store import get_team_features_with_fallback
        
        fs_df = pd.DataFrame([{
            'team_id': 'test_team',
            'season': '2024-25',
            'games_played': 10,
            'rolling_win_pct_5': 0.8,
            'rolling_win_pct_10': 0.7,
            'rolling_point_diff_avg_5': 5.0,
            'rolling_point_diff_avg_10': 4.0,
            'win_pct_last5_vs10': 0.1,
            'point_diff_last5_vs10': 1.0,
            'recent_strength_index_5': 4.0
        }])
        
        result = get_team_features_with_fallback('test_team', '2024-25', fs_df, min_games=5)
        
        assert result['is_fallback'] == False
        assert result['rolling_win_pct_5'] == 0.8
    
    def test_get_team_features_prior_season_fallback(self):
        """Test falling back to prior season when current has insufficient games."""
        from model_training.feature_store import get_team_features_with_fallback
        
        fs_df = pd.DataFrame([
            {
                'team_id': 'test_team',
                'season': '2024-25',
                'games_played': 2,  # Less than min_games
                'rolling_win_pct_5': np.nan,
                'rolling_win_pct_10': np.nan,
                'rolling_point_diff_avg_5': np.nan,
                'rolling_point_diff_avg_10': np.nan,
                'win_pct_last5_vs10': np.nan,
                'point_diff_last5_vs10': np.nan,
                'recent_strength_index_5': np.nan
            },
            {
                'team_id': 'test_team',
                'season': '2023-24',
                'games_played': 30,
                'rolling_win_pct_5': 0.6,
                'rolling_win_pct_10': 0.55,
                'rolling_point_diff_avg_5': 3.0,
                'rolling_point_diff_avg_10': 2.5,
                'win_pct_last5_vs10': 0.05,
                'point_diff_last5_vs10': 0.5,
                'recent_strength_index_5': 1.8
            }
        ])
        
        result = get_team_features_with_fallback('test_team', '2024-25', fs_df, min_games=5)
        
        assert result['is_fallback'] == True
        assert result['fallback_type'] == 'prior_season'
        assert result['rolling_win_pct_5'] == 0.6
    
    def test_enrich_dataframe_no_nan(self):
        """Test that enriched dataframe has no NaN values."""
        from model_training.feature_store import enrich_dataframe_with_fallback, NUMERIC_FEATURE_COLS
        
        games_df = pd.DataFrame([{
            'game_id': '123',
            'home_team': 'Team A',
            'away_team': 'Team B',
            'home_team_id': 'team_a_id',
            'away_team_id': 'team_b_id',
            'season': '2024-25',
            'date': '2024-11-15'
        }])
        
        # Empty feature store - should use league averages
        fs_df = pd.DataFrame()
        
        result = enrich_dataframe_with_fallback(games_df, fs_df, min_games=5)
        
        # Check no NaN in feature columns
        for col in NUMERIC_FEATURE_COLS:
            home_col = f'home_fs_{col}'
            away_col = f'away_fs_{col}'
            if home_col in result.columns:
                assert not result[home_col].isna().any(), f"NaN found in {home_col}"
            if away_col in result.columns:
                assert not result[away_col].isna().any(), f"NaN found in {away_col}"


class TestSmartTeamEncoding:
    """Tests for Task 1.2: Smart Team Encoding"""
    
    def test_known_team_encoding(self):
        """Test that known teams get proper encoding."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_smart_encoding = True
        
        # Fit encoder with some teams
        predictor.team_encoder.fit(['Duke', 'Kentucky', 'Kansas'])
        
        # Known team should get proper encoding
        enc = predictor._encode_team_smart('Duke')
        assert enc >= 0
        assert enc < 3
    
    def test_unknown_team_not_negative(self):
        """Test that unknown teams don't get -1 encoding."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_smart_encoding = True
        
        # Fit encoder with some teams
        predictor.team_encoder.fit(['Duke', 'Kentucky', 'Kansas', 'UNC', 'UCLA'])
        
        # Unknown team should get median-ish encoding, not -1
        enc = predictor._encode_team_smart('Unknown University')
        assert enc >= 0
        assert enc < len(predictor.team_encoder.classes_)
    
    def test_different_unknown_teams_get_different_encodings(self):
        """Test that different unknown teams get slightly different encodings."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_smart_encoding = True
        
        # Fit with many teams so there's room for variation
        teams = [f'Team_{i}' for i in range(100)]
        predictor.team_encoder.fit(teams)
        
        # Different unknown teams should get different (or at least possibly different) encodings
        encodings = set()
        for name in ['Unknown A', 'Unknown B', 'Unknown C', 'Unknown D', 'Unknown E']:
            enc = predictor._encode_team_smart(name)
            encodings.add(enc)
        
        # Should have at least some variation (not all the same)
        # With deterministic hash-based offset, they should differ
        assert len(encodings) >= 2
    
    def test_smart_encoding_disabled(self):
        """Test that disabling smart encoding returns -1."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_smart_encoding = False
        
        predictor.team_encoder.fit(['Duke', 'Kentucky'])
        
        enc = predictor._encode_team_smart('Unknown Team')
        assert enc == -1


class TestEarlySeasonDetection:
    """Tests for Task 1.4: Early Season Detection"""
    
    def test_early_season_detection_november(self):
        """Test early season detection in November."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        
        # Early November should be early season
        early_date = datetime(2024, 11, 10)
        assert predictor._is_early_season(early_date) == True
    
    def test_early_season_detection_december(self):
        """Test that late December is not early season."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        
        # Late December should not be early season
        late_date = datetime(2024, 12, 20)
        assert predictor._is_early_season(late_date) == False
    
    def test_early_season_detection_february(self):
        """Test that February is definitely not early season."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        
        feb_date = datetime(2025, 2, 15)
        assert predictor._is_early_season(feb_date) == False
    
    def test_early_season_string_date(self):
        """Test early season detection with string date."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        
        # String format should also work
        assert predictor._is_early_season('2024-11-10') == True
        assert predictor._is_early_season('2024-12-20') == False
    
    def test_confidence_factor_few_games(self):
        """Test that confidence factor is reduced for teams with few games."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_early_season_adjustment = True
        
        early_date = datetime(2024, 11, 15)
        
        # Teams with few games should get lower factor
        factor_few = predictor._get_early_season_confidence_factor(early_date, home_games=2, away_games=3)
        factor_many = predictor._get_early_season_confidence_factor(early_date, home_games=12, away_games=10)
        
        assert factor_few < factor_many
        assert factor_few < 1.0
    
    def test_confidence_factor_late_season(self):
        """Test that late season always returns 1.0."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_early_season_adjustment = True
        
        late_date = datetime(2025, 2, 15)
        
        factor = predictor._get_early_season_confidence_factor(late_date, home_games=2, away_games=3)
        assert factor == 1.0
    
    def test_early_season_adjustment_disabled(self):
        """Test that disabled adjustment always returns 1.0."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.use_early_season_adjustment = False
        
        early_date = datetime(2024, 11, 15)
        
        factor = predictor._get_early_season_confidence_factor(early_date, home_games=2, away_games=3)
        assert factor == 1.0


class TestTemperatureScaling:
    """Tests for Task 1.3: Temperature Scaling"""
    
    def test_temperature_reduces_confidence(self):
        """Test that temperature < 1 reduces confidence."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.confidence_temperature_value = 0.8
        
        # High probability should be reduced
        probs = np.array([0.9])
        result = predictor._apply_confidence_temperature(probs)
        
        # Should move toward 0.5
        assert result[0] < 0.9
        assert result[0] > 0.5
    
    def test_temperature_unity_no_change(self):
        """Test that temperature = 1.0 doesn't change probabilities."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.confidence_temperature_value = 1.0
        
        probs = np.array([0.75])
        result = predictor._apply_confidence_temperature(probs)
        
        assert np.isclose(result[0], 0.75)
    
    def test_temperature_preserves_direction(self):
        """Test that temperature doesn't flip predictions."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor()
        predictor.confidence_temperature_value = 0.7
        
        # Probability > 0.5 should stay > 0.5
        probs_high = np.array([0.8])
        result_high = predictor._apply_confidence_temperature(probs_high)
        assert result_high[0] > 0.5
        
        # Probability < 0.5 should stay < 0.5
        probs_low = np.array([0.3])
        result_low = predictor._apply_confidence_temperature(probs_low)
        assert result_low[0] < 0.5


class TestFeatureFlagsConfig:
    """Tests for feature flags configuration"""
    
    def test_feature_flags_file_exists(self):
        """Test that feature flags config file exists."""
        flags_path = Path('config/feature_flags.json')
        assert flags_path.exists(), "Feature flags config file should exist"
    
    def test_feature_flags_has_required_keys(self):
        """Test that feature flags has all required keys."""
        import json
        
        with open('config/feature_flags.json') as f:
            flags = json.load(f)
        
        required_keys = [
            'use_feature_fallback',
            'use_smart_team_encoding',
            'use_early_season_adjustment',
            'use_temperature_scaling',
            'fallback_min_games'
        ]
        
        for key in required_keys:
            assert key in flags, f"Missing required flag: {key}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
