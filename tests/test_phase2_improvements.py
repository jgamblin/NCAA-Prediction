"""Tests for Phase 2 Feature Engineering Improvements

Tests for:
- Task 2.1: Power Ratings (KenPom-style)
- Task 2.2: Strength of Schedule
- Task 2.3: Rest Days Calculation
- Task 2.4: Home/Away Splits
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPowerRatings:
    """Tests for Phase 2 Task 2.1 - Power Ratings."""
    
    @pytest.fixture
    def sample_games(self):
        """Create sample game data for testing."""
        return pd.DataFrame({
            'game_id': ['g1', 'g2', 'g3', 'g4', 'g5', 'g6'],
            'home_team': ['Duke', 'Kentucky', 'Duke', 'UNC', 'Kansas', 'Duke'],
            'away_team': ['UNC', 'Duke', 'Kansas', 'Kentucky', 'Duke', 'UNC'],
            'home_score': [85, 70, 90, 78, 65, 82],
            'away_score': [78, 75, 85, 82, 70, 79],
            'home_team_id': ['duke', 'kentucky', 'duke', 'unc', 'kansas', 'duke'],
            'away_team_id': ['unc', 'duke', 'kansas', 'kentucky', 'duke', 'unc'],
            'season': ['2024-25'] * 6,
            'date': [datetime(2024, 11, i+1) for i in range(6)],
        })
    
    def test_power_ratings_import(self):
        """Test that power ratings module can be imported."""
        from model_training import power_ratings
        assert hasattr(power_ratings, 'PowerRatings')
    
    def test_power_ratings_calculation(self, sample_games):
        """Test that power ratings are calculated for all teams."""
        from model_training.power_ratings import PowerRatings
        
        pr = PowerRatings(n_iterations=5)
        pr.calculate_ratings(sample_games)
        
        # All teams should have ratings (stored in pr.ratings dict)
        assert 'Duke' in pr.ratings or 'duke' in pr.ratings
        assert 'UNC' in pr.ratings or 'unc' in pr.ratings
        
        # Get a team rating using the public method
        duke_rating = pr.get_team_rating('Duke')
        
        # Each rating should have expected keys
        assert 'overall' in duke_rating or 'net_rating' in duke_rating
        assert 'offensive' in duke_rating or 'adj_offense' in duke_rating
        assert 'defensive' in duke_rating or 'adj_defense' in duke_rating
        assert 'games_played' in duke_rating
    
    def test_power_ratings_strength_of_schedule(self, sample_games):
        """Test strength of schedule calculation."""
        from model_training.power_ratings import PowerRatings
        
        pr = PowerRatings(n_iterations=5)
        pr.calculate_ratings(sample_games)
        
        # Duke plays against UNC, Kansas, Kentucky - should have calculable SOS
        sos = pr.calculate_sos('duke', '2024-25')
        assert isinstance(sos, float)
        assert -50 < sos < 50  # Reasonable range
    
    def test_power_ratings_matchup_features(self, sample_games):
        """Test matchup feature generation."""
        from model_training.power_ratings import PowerRatings
        
        pr = PowerRatings(n_iterations=5)
        pr.calculate_ratings(sample_games)
        
        features = pr.get_matchup_features('duke', 'unc', '2024-25')
        
        assert 'power_rating_diff' in features
        assert 'off_rating_diff' in features
        assert 'def_rating_diff' in features
        assert 'home_sos' in features
        assert 'away_sos' in features


class TestHomeAwaySplits:
    """Tests for Phase 2 Task 2.4 - Home/Away Splits."""
    
    @pytest.fixture
    def sample_games(self):
        """Create sample game data with home/away patterns."""
        # Duke: 3-0 at home, 1-2 on road
        # UNC: 2-1 at home, 1-2 on road
        games = [
            # Duke home games (all wins)
            ('g1', 'Duke', 'UNC', 85, 78, 'duke', 'unc'),
            ('g2', 'Duke', 'Kansas', 90, 82, 'duke', 'kansas'),
            ('g3', 'Duke', 'Kentucky', 88, 80, 'duke', 'kentucky'),
            # Duke away games (1 win, 2 losses)
            ('g4', 'UNC', 'Duke', 82, 79, 'unc', 'duke'),
            ('g5', 'Kansas', 'Duke', 78, 75, 'kansas', 'duke'),
            ('g6', 'Kentucky', 'Duke', 72, 85, 'kentucky', 'duke'),  # Duke wins this one
        ]
        
        return pd.DataFrame({
            'game_id': [g[0] for g in games],
            'home_team': [g[1] for g in games],
            'away_team': [g[2] for g in games],
            'home_score': [g[3] for g in games],
            'away_score': [g[4] for g in games],
            'home_team_id': [g[5] for g in games],
            'away_team_id': [g[6] for g in games],
            'season': ['2024-25'] * len(games),
            'date': [datetime(2024, 11, i+1) for i in range(len(games))],
        })
    
    def test_home_away_splits_import(self):
        """Test that home/away splits module can be imported."""
        from model_training import home_away_splits
        assert hasattr(home_away_splits, 'HomeAwaySplits')
    
    def test_splits_calculation(self, sample_games):
        """Test that splits are calculated correctly."""
        from model_training.home_away_splits import HomeAwaySplits
        
        splits = HomeAwaySplits(min_home_games=3, min_away_games=3)
        splits.calculate_splits(sample_games)
        
        duke_splits = splits.get_team_splits('duke', '2024-25')
        
        # Duke: 3-0 at home = 100% home win rate
        assert duke_splits['home_win_pct'] == 1.0
        assert duke_splits['games_home'] == 3
        
        # Duke: 1-2 on road = 33.3% away win rate
        assert duke_splits['games_away'] == 3
        assert abs(duke_splits['away_win_pct'] - 0.333) < 0.01
    
    def test_matchup_features(self, sample_games):
        """Test matchup feature generation."""
        from model_training.home_away_splits import HomeAwaySplits
        
        splits = HomeAwaySplits(min_home_games=2, min_away_games=2)
        splits.calculate_splits(sample_games)
        
        features = splits.get_matchup_features('duke', 'unc', '2024-25')
        
        assert 'home_team_home_wpct' in features
        assert 'away_team_away_wpct' in features
        assert 'venue_wpct_diff' in features
        assert 'combined_home_adv' in features


class TestRestDays:
    """Tests for Phase 2 Task 2.3 - Rest Days Calculation."""
    
    @pytest.fixture
    def sample_games(self):
        """Create sample game data with dates."""
        base_date = datetime(2024, 11, 1)
        return pd.DataFrame({
            'game_id': ['g1', 'g2', 'g3', 'g4'],
            'home_team': ['Duke', 'UNC', 'Duke', 'Kansas'],
            'away_team': ['UNC', 'Duke', 'Kansas', 'Duke'],
            'home_score': [85, 78, 90, 82],
            'away_score': [78, 82, 85, 79],
            'home_team_id': ['duke', 'unc', 'duke', 'kansas'],
            'away_team_id': ['unc', 'duke', 'kansas', 'duke'],
            'season': ['2024-25'] * 4,
            # Duke plays Nov 1, Nov 3, Nov 5, Nov 10
            'date': [base_date, base_date + timedelta(days=2), 
                     base_date + timedelta(days=4), base_date + timedelta(days=9)],
        })
    
    def test_rest_days_import(self):
        """Test that rest days functions can be imported."""
        from model_training.home_away_splits import calculate_rest_days, add_rest_days_features
        assert callable(calculate_rest_days)
        assert callable(add_rest_days_features)
    
    def test_rest_days_calculation(self, sample_games):
        """Test rest days calculation for a specific game."""
        from model_training.home_away_splits import calculate_rest_days
        
        # Duke's last game before Nov 10 was Nov 5
        # So rest days should be 5
        rest = calculate_rest_days(
            game_date=datetime(2024, 11, 10),
            team_id='duke',
            games_df=sample_games
        )
        
        assert rest == 5
    
    def test_rest_days_first_game(self, sample_games):
        """Test rest days for first game of season."""
        from model_training.home_away_splits import calculate_rest_days
        
        # Kansas has no games before Nov 5
        rest = calculate_rest_days(
            game_date=datetime(2024, 11, 5),
            team_id='kansas',
            games_df=sample_games
        )
        
        # Should return max_rest (10) for first game
        assert rest == 10
    
    def test_add_rest_days_features(self, sample_games):
        """Test adding rest day features to dataframe."""
        from model_training.home_away_splits import add_rest_days_features
        
        upcoming = pd.DataFrame({
            'home_team_id': ['duke'],
            'away_team_id': ['unc'],
            'date': [datetime(2024, 11, 15)],
        })
        
        result = add_rest_days_features(upcoming, sample_games)
        
        assert 'home_rest_days' in result.columns
        assert 'away_rest_days' in result.columns
        assert 'rest_advantage' in result.columns


class TestPhase2Integration:
    """Integration tests for Phase 2 features with AdaptivePredictor."""
    
    @pytest.fixture
    def sample_training_data(self):
        """Create larger sample training dataset."""
        teams = ['Duke', 'UNC', 'Kentucky', 'Kansas', 'Gonzaga', 'Villanova', 
                 'Michigan', 'UCLA', 'Arizona', 'Baylor']
        team_ids = [t.lower().replace(' ', '_') for t in teams]
        
        games = []
        game_id = 0
        base_date = datetime(2024, 11, 1)
        
        # Generate matchups
        for i, home in enumerate(teams):
            for j, away in enumerate(teams):
                if i != j and np.random.random() > 0.7:  # Random subset of games
                    game_id += 1
                    home_score = np.random.randint(60, 100)
                    away_score = np.random.randint(60, 100)
                    games.append({
                        'game_id': f'g{game_id}',
                        'home_team': home,
                        'away_team': away,
                        'home_score': home_score,
                        'away_score': away_score,
                        'home_team_id': team_ids[i],
                        'away_team_id': team_ids[j],
                        'season': '2024-25',
                        'date': base_date + timedelta(days=game_id),
                        'game_url': f'https://example.com/g{game_id}',
                    })
        
        return pd.DataFrame(games)
    
    def test_predictor_phase2_init(self, sample_training_data):
        """Test that predictor initializes Phase 2 features."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor(
            use_power_ratings=True,
            use_home_away_splits=True,
            use_rest_days=True
        )
        
        predictor.fit(sample_training_data)
        
        # Check Phase 2 components initialized
        assert predictor._power_ratings is not None or not predictor.use_power_ratings
        assert predictor._home_away_splits is not None or not predictor.use_home_away_splits
        assert predictor._historical_games is not None
    
    def test_predictor_phase2_prediction(self, sample_training_data):
        """Test that predictions work with Phase 2 features."""
        from model_training.adaptive_predictor import AdaptivePredictor
        
        predictor = AdaptivePredictor(
            use_power_ratings=True,
            use_home_away_splits=True,
            use_rest_days=True
        )
        
        predictor.fit(sample_training_data)
        
        # Create upcoming game
        upcoming = pd.DataFrame({
            'game_id': ['upcoming1'],
            'home_team': ['Duke'],
            'away_team': ['UNC'],
            'home_team_id': ['duke'],
            'away_team_id': ['unc'],
            'season': ['2024-25'],
            'date': [datetime(2024, 12, 1)],
            'game_url': ['https://example.com/upcoming1'],
        })
        
        results = predictor.predict(upcoming, skip_low_data=False)
        
        assert len(results) == 1
        assert 'predicted_winner' in results.columns
        assert 'confidence' in results.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
