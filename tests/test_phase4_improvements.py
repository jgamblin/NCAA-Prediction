"""
Tests for Phase 4: Advanced Improvements

Task 4.1: Conference Strength Adjustment
Task 4.2: Recency Weighting / Momentum
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_training.conference_strength import ConferenceStrength, add_conference_features
from model_training.recency_weighting import (
    RecencyWeighting, 
    add_momentum_features,
    apply_recency_weights
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_games_df():
    """Create sample games data for testing."""
    np.random.seed(42)
    
    teams = ['Duke', 'UNC', 'Kentucky', 'Kansas', 'Gonzaga', 
             'UCLA', 'Michigan', 'Ohio State', 'Villanova', 'Baylor']
    
    games = []
    base_date = datetime(2025, 11, 1)
    
    for i in range(50):
        home = np.random.choice(teams)
        away = np.random.choice([t for t in teams if t != home])
        
        home_score = np.random.randint(60, 100)
        away_score = np.random.randint(60, 100)
        
        games.append({
            'game_id': f'game_{i}',
            'date': base_date + timedelta(days=i % 30),
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score
        })
    
    return pd.DataFrame(games)


@pytest.fixture
def team_ratings():
    """Create sample team power ratings."""
    return {
        'Duke': 25.0,
        'UNC': 22.0,
        'Kentucky': 20.0,
        'Kansas': 23.0,
        'Gonzaga': 21.0,
        'UCLA': 18.0,
        'Michigan': 15.0,
        'Ohio State': 14.0,
        'Villanova': 19.0,
        'Baylor': 17.0
    }


@pytest.fixture
def conference_mapping():
    """Create sample conference mapping."""
    return {
        'Duke': 'ACC',
        'UNC': 'ACC',
        'Kentucky': 'SEC',
        'Kansas': 'Big 12',
        'Gonzaga': 'WCC',
        'UCLA': 'Big Ten',
        'Michigan': 'Big Ten',
        'Ohio State': 'Big Ten',
        'Villanova': 'Big East',
        'Baylor': 'Big 12'
    }


# ============================================================================
# Task 4.1: Conference Strength Tests
# ============================================================================

class TestConferenceStrength:
    """Tests for conference strength calculations."""
    
    def test_conference_strength_init(self):
        """Test ConferenceStrength initialization."""
        cs = ConferenceStrength()
        
        assert cs.min_games == 5
        assert cs.conference_ratings == {}
        assert cs.team_conferences == {}
    
    def test_calculate_ratings_from_team_ratings(self, sample_games_df, team_ratings, conference_mapping):
        """Test calculating conference ratings from team ratings."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        
        ratings = cs.calculate_ratings(sample_games_df, team_ratings)
        
        assert len(ratings) > 0
        # Ratings should be normalized around 50
        assert 30 <= np.mean(list(ratings.values())) <= 70
    
    def test_calculate_ratings_without_team_ratings(self, sample_games_df, conference_mapping):
        """Test calculating ratings from non-conference games only."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        
        ratings = cs.calculate_ratings(sample_games_df)
        
        # Should still produce some ratings (may be empty if insufficient games)
        assert isinstance(ratings, dict)
    
    def test_get_conference(self, conference_mapping):
        """Test getting conference for a team."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        
        assert cs.get_conference('Duke') == 'ACC'
        assert cs.get_conference('Kentucky') == 'SEC'
        assert cs.get_conference('UnknownTeam') == 'Unknown'
    
    def test_get_conference_rating(self, sample_games_df, team_ratings, conference_mapping):
        """Test getting conference rating."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        rating = cs.get_conference_rating('ACC')
        assert isinstance(rating, (int, float))
    
    def test_get_conference_differential(self, sample_games_df, team_ratings, conference_mapping):
        """Test getting conference differential between two teams."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        diff = cs.get_conference_differential('Duke', 'Kentucky')
        
        # Differential should be a number (positive or negative)
        assert isinstance(diff, (int, float))
    
    def test_get_rankings(self, sample_games_df, team_ratings, conference_mapping):
        """Test getting conference rankings as DataFrame."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        rankings = cs.get_rankings()
        
        assert isinstance(rankings, pd.DataFrame)
        if not rankings.empty:
            assert 'conference' in rankings.columns
            assert 'rating' in rankings.columns


class TestAddConferenceFeatures:
    """Tests for adding conference features to dataframe."""
    
    def test_add_conference_features(self, sample_games_df, team_ratings, conference_mapping):
        """Test adding conference features to games dataframe."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        enriched = add_conference_features(sample_games_df, cs)
        
        assert 'home_conf_rating' in enriched.columns
        assert 'away_conf_rating' in enriched.columns
        assert 'conf_rating_diff' in enriched.columns
        assert 'is_conf_game' in enriched.columns
    
    def test_conference_features_values(self, sample_games_df, team_ratings, conference_mapping):
        """Test that conference features have valid values."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        enriched = add_conference_features(sample_games_df, cs)
        
        # Ratings should be positive numbers
        assert enriched['home_conf_rating'].notna().all()
        assert enriched['away_conf_rating'].notna().all()
        
        # Differential should be calculated correctly
        expected_diff = enriched['home_conf_rating'] - enriched['away_conf_rating']
        assert np.allclose(enriched['conf_rating_diff'], expected_diff)


# ============================================================================
# Task 4.2: Recency Weighting Tests
# ============================================================================

class TestRecencyWeighting:
    """Tests for recency weighting calculations."""
    
    def test_recency_init(self):
        """Test RecencyWeighting initialization."""
        rw = RecencyWeighting()
        
        assert rw.half_life_days == 14
        assert rw.min_games == 3
        assert rw.team_momentum == {}
    
    def test_calculate_weight_today(self):
        """Test weight calculation for today's game."""
        rw = RecencyWeighting(half_life_days=14)
        
        today = datetime.now()
        weight = rw.calculate_weight(today, today)
        
        assert weight == 1.0  # Today should have full weight
    
    def test_calculate_weight_half_life(self):
        """Test weight calculation at half-life."""
        rw = RecencyWeighting(half_life_days=14)
        
        reference = datetime(2025, 11, 15)
        game_date = datetime(2025, 11, 1)  # 14 days ago
        
        weight = rw.calculate_weight(game_date, reference)
        
        # Should be approximately 0.5 at half-life
        assert 0.45 <= weight <= 0.55
    
    def test_calculate_weight_old_game(self):
        """Test weight calculation for old game."""
        rw = RecencyWeighting(half_life_days=14)
        
        reference = datetime(2025, 11, 29)
        game_date = datetime(2025, 10, 1)  # ~59 days ago
        
        weight = rw.calculate_weight(game_date, reference)
        
        # Old games should have low weight
        assert weight < 0.1
        assert weight >= 0.01  # But at least minimum
    
    def test_calculate_weighted_average(self):
        """Test weighted average calculation."""
        rw = RecencyWeighting(half_life_days=14)
        
        reference = datetime(2025, 11, 15)
        values = [1.0, 0.0, 1.0, 1.0]  # W, L, W, W
        dates = [
            datetime(2025, 11, 14),  # 1 day ago (high weight)
            datetime(2025, 11, 10),  # 5 days ago
            datetime(2025, 11, 5),   # 10 days ago
            datetime(2025, 11, 1),   # 14 days ago (half weight)
        ]
        
        avg = rw.calculate_weighted_average(values, dates, reference)
        
        # Recent win should pull average up
        assert avg > 0.5  # Above simple average (3/4 = 0.75)
    
    def test_calculate_momentum(self, sample_games_df):
        """Test momentum calculation for all teams."""
        rw = RecencyWeighting()
        
        momentum = rw.calculate_momentum(sample_games_df)
        
        assert len(momentum) > 0
        
        # All momentum values should be between -1 and 1
        for team, m in momentum.items():
            assert -1.0 <= m <= 1.0
    
    def test_get_momentum(self, sample_games_df):
        """Test getting momentum for a specific team."""
        rw = RecencyWeighting()
        rw.calculate_momentum(sample_games_df)
        
        momentum = rw.get_momentum('Duke')
        
        assert -1.0 <= momentum <= 1.0
    
    def test_get_streak(self, sample_games_df):
        """Test getting streak for a team."""
        rw = RecencyWeighting()
        rw.calculate_momentum(sample_games_df)
        
        streak = rw.get_streak('Duke')
        
        assert isinstance(streak, int)
    
    def test_is_hot_cold(self, sample_games_df):
        """Test hot/cold detection."""
        rw = RecencyWeighting()
        rw.calculate_momentum(sample_games_df)
        
        # Set a team to be hot for testing
        rw.team_momentum['TestHot'] = 0.5
        rw.team_momentum['TestCold'] = -0.5
        
        assert rw.is_hot('TestHot')
        assert not rw.is_cold('TestHot')
        assert rw.is_cold('TestCold')
        assert not rw.is_hot('TestCold')


class TestAddMomentumFeatures:
    """Tests for adding momentum features to dataframe."""
    
    def test_add_momentum_features(self, sample_games_df):
        """Test adding momentum features to games dataframe."""
        rw = RecencyWeighting()
        
        enriched = add_momentum_features(
            sample_games_df, 
            rw, 
            games_df=sample_games_df
        )
        
        assert 'home_momentum' in enriched.columns
        assert 'away_momentum' in enriched.columns
        assert 'momentum_diff' in enriched.columns
        assert 'home_streak' in enriched.columns
        assert 'away_streak' in enriched.columns
    
    def test_momentum_features_values(self, sample_games_df):
        """Test that momentum features have valid values."""
        rw = RecencyWeighting()
        
        enriched = add_momentum_features(
            sample_games_df,
            rw,
            games_df=sample_games_df
        )
        
        # Momentum should be between -1 and 1
        assert enriched['home_momentum'].between(-1, 1).all()
        assert enriched['away_momentum'].between(-1, 1).all()
        
        # Differential should be calculated correctly
        expected_diff = enriched['home_momentum'] - enriched['away_momentum']
        assert np.allclose(enriched['momentum_diff'], expected_diff)


class TestApplyRecencyWeights:
    """Tests for applying recency weights to dataframe."""
    
    def test_apply_recency_weights(self, sample_games_df):
        """Test applying recency weights to dataframe."""
        weighted = apply_recency_weights(sample_games_df, date_col='date')
        
        assert 'weight' in weighted.columns
        assert weighted['weight'].between(0, 1).all()
    
    def test_recent_games_higher_weight(self, sample_games_df):
        """Test that recent games have higher weights."""
        weighted = apply_recency_weights(sample_games_df, date_col='date')
        
        # Sort by date and check weights decrease
        sorted_df = weighted.sort_values('date', ascending=False)
        weights = sorted_df['weight'].values
        
        # Most recent should have highest weight
        assert weights[0] >= weights[-1]


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase4Integration:
    """Integration tests for Phase 4 features."""
    
    def test_all_phase4_features(self, sample_games_df, team_ratings, conference_mapping):
        """Test combining all Phase 4 features."""
        # Conference strength
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        # Recency weighting
        rw = RecencyWeighting()
        
        # Apply both
        enriched = add_conference_features(sample_games_df, cs)
        enriched = add_momentum_features(enriched, rw, games_df=sample_games_df)
        
        # Check all features present
        expected_cols = [
            'home_conf_rating', 'away_conf_rating', 'conf_rating_diff',
            'home_momentum', 'away_momentum', 'momentum_diff',
            'home_streak', 'away_streak'
        ]
        
        for col in expected_cols:
            assert col in enriched.columns, f"Missing column: {col}"
    
    def test_phase4_features_no_nan(self, sample_games_df, team_ratings, conference_mapping):
        """Test that Phase 4 features don't introduce NaN values."""
        cs = ConferenceStrength()
        cs.team_conferences = conference_mapping
        cs.calculate_ratings(sample_games_df, team_ratings)
        
        rw = RecencyWeighting()
        
        enriched = add_conference_features(sample_games_df, cs)
        enriched = add_momentum_features(enriched, rw, games_df=sample_games_df)
        
        phase4_cols = [
            'home_conf_rating', 'away_conf_rating', 'conf_rating_diff',
            'home_momentum', 'away_momentum', 'momentum_diff'
        ]
        
        for col in phase4_cols:
            assert enriched[col].notna().all(), f"NaN values in {col}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
