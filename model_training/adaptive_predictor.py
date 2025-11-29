#!/usr/bin/env python3
"""
Adaptive Random Forest predictor for NCAA games.
Used by daily_pipeline.py for daily predictions.

Phase 1 Enhancements (2025-11-29):
- Task 1.2: Smart team encoding (conference-aware, median fallback instead of -1)
- Task 1.3: Improved temperature scaling with dynamic adjustment
- Task 1.4: Early season detection with confidence adjustment

Phase 2 Feature Engineering (2025-11-29):
- Task 2.1: Power ratings (KenPom-style efficiency)
- Task 2.2: Strength of schedule
- Task 2.3: Rest days calculation
- Task 2.4: Home/away performance splits

Phase 3 Model Architecture (2025-11-29):
- Task 3.1: XGBoost integration (via EnsemblePredictor)
- Task 3.2: Temporal train/validation split
- Task 3.3: Model ensemble support

Phase 4 Advanced Features (2025-01-xx):
- Task 4.1: Conference strength adjustment
- Task 4.2: Recency weighting / momentum features
"""

import pandas as pd
import numpy as np
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.calibration import CalibratedClassifierCV

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_collection.team_name_utils import normalize_team_name

# Phase 2 imports - lazy loaded to avoid circular imports
_power_ratings_module = None
_home_away_splits_module = None
_ensemble_module = None

# Phase 4 imports - lazy loaded
_conference_strength_module = None
_recency_weighting_module = None

# Load feature flags
try:
    with open(Path('config') / 'feature_flags.json') as f:
        _feature_flags = json.load(f)
except Exception:
    _feature_flags = {}


def _get_power_ratings():
    """Lazy load power ratings module."""
    global _power_ratings_module
    if _power_ratings_module is None:
        try:
            from model_training import power_ratings
            _power_ratings_module = power_ratings
        except ImportError:
            _power_ratings_module = False
    return _power_ratings_module if _power_ratings_module else None


def _get_home_away_splits():
    """Lazy load home/away splits module."""
    global _home_away_splits_module
    if _home_away_splits_module is None:
        try:
            from model_training import home_away_splits
            _home_away_splits_module = home_away_splits
        except ImportError:
            _home_away_splits_module = False
    return _home_away_splits_module if _home_away_splits_module else None


def _get_ensemble_predictor():
    """Lazy load ensemble predictor module."""
    global _ensemble_module
    if _ensemble_module is None:
        try:
            from model_training import ensemble_predictor
            _ensemble_module = ensemble_predictor
        except ImportError:
            _ensemble_module = False
    return _ensemble_module if _ensemble_module else None


def _get_conference_strength():
    """Lazy load conference strength module (Phase 4)."""
    global _conference_strength_module
    if _conference_strength_module is None:
        try:
            from model_training import conference_strength
            _conference_strength_module = conference_strength
        except ImportError:
            _conference_strength_module = False
    return _conference_strength_module if _conference_strength_module else None


def _get_recency_weighting():
    """Lazy load recency weighting module (Phase 4)."""
    global _recency_weighting_module
    if _recency_weighting_module is None:
        try:
            from model_training import recency_weighting
            _recency_weighting_module = recency_weighting
        except ImportError:
            _recency_weighting_module = False
    return _recency_weighting_module if _recency_weighting_module else None


class AdaptivePredictor:
    """Dynamic prediction model for NCAA basketball games."""

    # Season start date (approximately first Monday of November)
    SEASON_START_MONTH = 11
    SEASON_START_DAY = 4
    
    # Early season threshold in days
    EARLY_SEASON_DAYS = 30

    def __init__(
        self,
        n_estimators=100,
        max_depth=20,
        min_samples_split=10,
        min_games_threshold='auto',
        calibrate=True,
        calibration_method='sigmoid',
        feature_importance_path='data/Adaptive_Feature_Importance.csv',
        home_court_logit_shift='auto:0.55',
        confidence_temperature='auto',
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        use_power_ratings=True,
        use_home_away_splits=True,
        use_rest_days=True,
        model_type='random_forest',
        use_ensemble=False,
    ):
        """
        Initialize the predictor.

        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum depth of trees
            min_samples_split: Minimum samples required to split a node
            min_games_threshold: Either an integer minimum, or 'auto' to derive a dynamic threshold from recent training data
            home_court_logit_shift: Options:
                - numeric value: fixed logit offset to subtract from home probabilities
                - 'none'/'off': disable adjustment
                - 'auto' or 'auto:<target>': calibrate shift so mean home probability hits target (default 0.55)
            use_smart_encoding: Use conference-aware team encoding instead of -1 for unknown teams
            use_early_season_adjustment: Apply confidence reduction during early season
            use_power_ratings: Calculate and use KenPom-style efficiency ratings (Phase 2)
            use_home_away_splits: Calculate and use venue-specific performance stats (Phase 2)
            use_rest_days: Calculate and use rest day advantages (Phase 2)
            model_type: 'random_forest', 'xgboost', or 'ensemble' (Phase 3)
            use_ensemble: If True, use EnsemblePredictor (XGB + RF + LR) (Phase 3)
        """
        # Phase 3: Model type selection
        self.model_type = _feature_flags.get('model_type', model_type)
        self.use_ensemble = _feature_flags.get('use_ensemble', use_ensemble)
        self._ensemble_predictor = None  # Will be initialized if use_ensemble=True
        
        # Create base model based on type
        if self.model_type == 'xgboost':
            try:
                import xgboost as xgb
                base_model = xgb.XGBClassifier(
                    n_estimators=n_estimators * 2,  # XGBoost typically uses more
                    max_depth=min(max_depth, 8),    # XGBoost works better with shallower trees
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=-1,
                    verbosity=0,
                )
                print("  Using XGBoost model (Phase 3)")
            except ImportError:
                print("  XGBoost not available, falling back to RandomForest")
                base_model = RandomForestClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    min_samples_split=min_samples_split,
                    random_state=42,
                    n_jobs=-1
                )
        else:
            base_model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_split=min_samples_split,
                random_state=42,
                n_jobs=-1
            )
        
        self._raw_model = base_model  # before optional calibration
        self.model = base_model       # will be replaced by calibrated wrapper if enabled
        self.team_encoder = LabelEncoder()
        # Base features; additional derived feature store diffs appended dynamically
        self.feature_cols = [
            'home_team_encoded',
            'away_team_encoded',
            'is_neutral',
            'home_rank',
            'away_rank',
            'rank_diff',
            'is_ranked_matchup',
        ]
        
        # Phase 2 feature columns (added dynamically when available)
        self.phase2_feature_cols = [
            # Power ratings features
            'power_rating_diff',
            'off_rating_diff',
            'def_rating_diff',
            'home_sos',
            'away_sos',
            'sos_diff',
            # Rest days features
            'home_rest_days',
            'away_rest_days',
            'rest_advantage',
            # Home/away splits
            'home_team_home_wpct',
            'home_team_home_margin',
            'home_team_home_adv',
            'away_team_away_wpct',
            'away_team_away_margin',
            'away_team_venue_consistency',
            'venue_wpct_diff',
            'combined_home_adv',
        ]
        
        # Phase 4 feature columns (added dynamically when available)
        self.phase4_feature_cols = [
            # Conference strength features (Task 4.1)
            'home_conf_rating',
            'away_conf_rating',
            'conf_rating_diff',
            # Momentum features (Task 4.2)
            'home_momentum',
            'away_momentum',
            'momentum_diff',
            'home_hot_streak',
            'away_hot_streak',
        ]
        
        self.min_games_threshold_mode = min_games_threshold
        if isinstance(min_games_threshold, (int, float)):
            self.min_games_threshold = int(min_games_threshold)
            self.min_games_threshold_source = 'fixed'
        elif isinstance(min_games_threshold, str) and min_games_threshold.lower() == 'auto':
            self.min_games_threshold = 75  # placeholder until after fit()
            self.min_games_threshold_source = 'auto'
        else:
            try:
                self.min_games_threshold = int(min_games_threshold)
                self.min_games_threshold_source = 'coerced'
            except Exception:
                self.min_games_threshold = 75
                self.min_games_threshold_source = 'default'
        self.team_game_counts = {}  # Store game counts per team
        self.training_data = None  # Store reference to training data
        self.calibrate = calibrate
        self.calibration_method = calibration_method
        self.feature_importance_path = feature_importance_path
        self.home_court_logit_shift_mode = home_court_logit_shift
        self.home_court_logit_shift_value = 0.0
        self.home_court_logit_shift_source = 'uninitialized'
        self.home_court_logit_shift_target = None
        self.confidence_temperature_mode = confidence_temperature
        if isinstance(confidence_temperature, (int, float)):
            self.confidence_temperature_value = float(confidence_temperature)
            self.confidence_temperature_source = 'fixed'
        else:
            self.confidence_temperature_value = 0.85
            self.confidence_temperature_source = 'default'
        self.last_low_data_games: list[dict[str, object]] = []
        
        # Phase 1 enhancements
        self.use_smart_encoding = _feature_flags.get('use_smart_team_encoding', use_smart_encoding)
        self.use_early_season_adjustment = _feature_flags.get('use_early_season_adjustment', use_early_season_adjustment)
        self._team_to_encoding_fallback = {}  # Cache for unknown team encodings
        
        # Phase 2 feature engineering
        self.use_power_ratings = _feature_flags.get('use_power_ratings', use_power_ratings)
        self.use_home_away_splits = _feature_flags.get('use_home_away_splits', use_home_away_splits)
        self.use_rest_days = _feature_flags.get('use_rest_days', use_rest_days)
        self._power_ratings = None  # Will be initialized during fit()
        self._home_away_splits = None  # Will be initialized during fit()
        self._historical_games = None  # For rest day calculations
        
        # Phase 4 advanced features
        self.use_conference_strength = _feature_flags.get('use_conference_strength', True)
        self.use_recency_weighting = _feature_flags.get('use_recency_weighting', True)
        self._conference_strength = None  # Will be initialized during fit()
        self._recency_weighting = None  # Will be initialized during fit()
        
    def _is_early_season(self, game_date: datetime = None) -> bool:
        """
        Determine if we're in early season (first 30 days).
        Early season predictions should be more conservative.
        """
        if game_date is None:
            game_date = datetime.now()
        
        if isinstance(game_date, str):
            try:
                game_date = datetime.strptime(game_date[:10], '%Y-%m-%d')
            except Exception:
                return False
        
        # Determine season start
        year = game_date.year
        if game_date.month < self.SEASON_START_MONTH:
            year -= 1  # We're in the second half of the season
        
        season_start = datetime(year, self.SEASON_START_MONTH, self.SEASON_START_DAY)
        days_into_season = (game_date - season_start).days
        
        return 0 <= days_into_season < self.EARLY_SEASON_DAYS
    
    def _get_early_season_confidence_factor(self, game_date: datetime = None, 
                                             home_games: int = 0, 
                                             away_games: int = 0) -> float:
        """
        Get confidence adjustment factor for early season games.
        
        Returns a factor between 0.8 and 1.0 based on:
        - Days into season
        - Number of games each team has played
        """
        if not self.use_early_season_adjustment:
            return 1.0
        
        if not self._is_early_season(game_date):
            return 1.0
        
        # Calculate factor based on games played
        min_games = min(home_games, away_games)
        
        if min_games >= 10:
            games_factor = 1.0
        elif min_games >= 7:
            games_factor = 0.95
        elif min_games >= 5:
            games_factor = 0.90
        elif min_games >= 3:
            games_factor = 0.85
        else:
            games_factor = 0.80
        
        return games_factor
    
    def _encode_team_smart(self, team_name: str) -> int:
        """
        Encode team with intelligent fallback for unknown teams.
        
        Instead of returning -1 for unknown teams:
        1. Check if we've seen this team before and cached a fallback
        2. Use median encoding value (middle of the pack assumption)
        
        This prevents all unknown teams from looking identical.
        """
        if team_name in self.team_encoder.classes_:
            return int(self.team_encoder.transform([team_name])[0])
        
        if not self.use_smart_encoding:
            return -1  # Old behavior
        
        # Check cache
        if team_name in self._team_to_encoding_fallback:
            return self._team_to_encoding_fallback[team_name]
        
        # Use median encoding (assumes middle-of-the-pack performance)
        median_encoding = len(self.team_encoder.classes_) // 2
        
        # Add small deterministic offset based on team name hash
        # This ensures different unknown teams get slightly different encodings
        name_hash = hash(team_name) % 100
        offset = (name_hash - 50) // 10  # Range: -5 to +4
        
        final_encoding = max(0, min(len(self.team_encoder.classes_) - 1, median_encoding + offset))
        
        # Cache it
        self._team_to_encoding_fallback[team_name] = final_encoding
        
        return final_encoding

    def prepare_data(self, df):
        """
        Prepare dataframe for training/prediction.

        Args:
            df: DataFrame with game data

        Returns:
            Prepared DataFrame
        """
        df = df.copy()

        # Normalize team names to handle inconsistencies
        # (e.g., "Indiana" vs "Indiana Hoosiers")
        if 'home_team' in df.columns:
            df['home_team'] = df['home_team'].apply(normalize_team_name)
        if 'away_team' in df.columns:
            df['away_team'] = df['away_team'].apply(normalize_team_name)

        # Add home_win if scores exist
        if 'home_score' in df.columns and 'away_score' in df.columns:
            df['home_win'] = (df['home_score'] > df['away_score']).astype(int)

        # Fill missing values - check if columns exist first
        if 'is_neutral' in df.columns:
            df['is_neutral'] = df['is_neutral'].fillna(0).astype(int)
        else:
            df['is_neutral'] = 0

        if 'home_rank' in df.columns:
            df['home_rank'] = df['home_rank'].fillna(99).astype(int)
        else:
            df['home_rank'] = 99

        if 'away_rank' in df.columns:
            df['away_rank'] = df['away_rank'].fillna(99).astype(int)
        else:
            df['away_rank'] = 99

        # Rank differential & ranked matchup indicator (helps highlight mismatches)
        try:
            df['rank_diff'] = (df['home_rank'] - df['away_rank']).astype(float)
        except Exception:
            df['rank_diff'] = 0.0
        df['is_ranked_matchup'] = ((df['home_rank'] <= 25) | (df['away_rank'] <= 25)).astype(int)

        # Feature store diff features (if enriched via pipeline)
        # Expect columns like home_fs_rolling_win_pct_5, away_fs_rolling_win_pct_5, etc.
        fs_pairs = [
            ('rolling_win_pct_5', 'fs_win_pct5_diff'),
            ('rolling_win_pct_10', 'fs_win_pct10_diff'),
            ('rolling_point_diff_avg_5', 'fs_point_diff5_diff'),
            ('rolling_point_diff_avg_10', 'fs_point_diff10_diff'),
            ('win_pct_last5_vs10', 'fs_win_pct_last5_vs10_diff'),
            ('point_diff_last5_vs10', 'fs_point_diff_last5_vs10_diff'),
            ('recent_strength_index_5', 'fs_recent_strength_index5_diff'),
        ]
        for base, diff_name in fs_pairs:
            h_col = f'home_fs_{base}'
            a_col = f'away_fs_{base}'
            if h_col in df.columns and a_col in df.columns:
                df[diff_name] = df[h_col] - df[a_col]
                if diff_name not in self.feature_cols:
                    self.feature_cols.append(diff_name)
        
        # Phase 2: Add power rating features if available
        if self.use_power_ratings and self._power_ratings is not None:
            df = self._add_power_rating_features(df)
        
        # Phase 2: Add rest day features if available
        if self.use_rest_days and self._historical_games is not None:
            df = self._add_rest_day_features(df)
        
        # Phase 2: Add home/away split features if available
        if self.use_home_away_splits and self._home_away_splits is not None:
            df = self._add_home_away_split_features(df)
        
        # Phase 4: Add conference strength features if available
        if self.use_conference_strength and self._conference_strength is not None:
            df = self._add_conference_strength_features(df)
        
        # Phase 4: Add momentum features if available
        if self.use_recency_weighting and self._recency_weighting is not None:
            df = self._add_momentum_features(df)
        
        # Ensure Phase 2 feature columns are in feature_cols if present in df
        for col in self.phase2_feature_cols:
            if col in df.columns and col not in self.feature_cols:
                self.feature_cols.append(col)
        
        # Ensure Phase 4 feature columns are in feature_cols if present in df
        for col in self.phase4_feature_cols:
            if col in df.columns and col not in self.feature_cols:
                self.feature_cols.append(col)
        
        return df
    
    def _add_power_rating_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add power rating features to dataframe (Phase 2 Task 2.1)."""
        if self._power_ratings is None:
            return df
        
        try:
            df = self._power_ratings.enrich_dataframe_with_power_features(df)
        except Exception as e:
            print(f"  Warning: Power rating enrichment failed: {e}")
        
        return df
    
    def _add_rest_day_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add rest day features to dataframe (Phase 2 Task 2.3)."""
        ha_module = _get_home_away_splits()
        if ha_module is None:
            return df
        
        try:
            df = ha_module.add_rest_days_features(df, self._historical_games)
        except Exception as e:
            print(f"  Warning: Rest days calculation failed: {e}")
        
        return df
    
    def _add_home_away_split_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add home/away split features to dataframe (Phase 2 Task 2.4)."""
        if self._home_away_splits is None:
            return df
        
        try:
            df = self._home_away_splits.enrich_dataframe(df)
        except Exception as e:
            print(f"  Warning: Home/away split enrichment failed: {e}")
        
        return df
    
    def _add_conference_strength_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add conference strength features to dataframe (Phase 4 Task 4.1)."""
        if self._conference_strength is None:
            return df
        
        try:
            # add_conference_features is a module-level function
            cs_module = _get_conference_strength()
            if cs_module is not None:
                df = cs_module.add_conference_features(df, self._conference_strength)
        except Exception as e:
            print(f"  Warning: Conference strength enrichment failed: {e}")
        
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum/recency features to dataframe (Phase 4 Task 4.2)."""
        if self._recency_weighting is None:
            return df
        
        try:
            # add_momentum_features is a module-level function
            rw_module = _get_recency_weighting()
            if rw_module is not None:
                df = rw_module.add_momentum_features(df, self._recency_weighting, self._historical_games)
        except Exception as e:
            print(f"  Warning: Momentum feature enrichment failed: {e}")
        
        return df
    
    def _init_phase2_features(self, train_df: pd.DataFrame) -> None:
        """Initialize Phase 2 feature calculators from training data."""
        
        # Task 2.1 & 2.2: Power Ratings and Strength of Schedule
        if self.use_power_ratings:
            pr_module = _get_power_ratings()
            if pr_module is not None:
                try:
                    print("  Initializing power ratings (Phase 2)...")
                    self._power_ratings = pr_module.PowerRatings(n_iterations=10)
                    self._power_ratings.calculate_ratings(train_df)
                    n_teams = len(self._power_ratings.ratings)
                    print(f"    ✓ Calculated power ratings for {n_teams} teams")
                except Exception as e:
                    print(f"    Warning: Power ratings init failed: {e}")
                    self._power_ratings = None
        
        # Task 2.4: Home/Away Splits
        if self.use_home_away_splits:
            ha_module = _get_home_away_splits()
            if ha_module is not None:
                try:
                    print("  Initializing home/away splits (Phase 2)...")
                    self._home_away_splits = ha_module.HomeAwaySplits(
                        min_home_games=3, 
                        min_away_games=3
                    )
                    self._home_away_splits.calculate_splits(train_df)
                    n_splits = len(self._home_away_splits.splits)
                    print(f"    ✓ Calculated venue splits for {n_splits} team-seasons")
                except Exception as e:
                    print(f"    Warning: Home/away splits init failed: {e}")
                    self._home_away_splits = None
        
        # Task 2.3: Rest days - uses _historical_games set in fit()
        if self.use_rest_days:
            print("  Rest days feature enabled (Phase 2)")

    def _init_phase4_features(self, train_df: pd.DataFrame) -> None:
        """Initialize Phase 4 feature calculators from training data."""
        
        # Task 4.1: Conference Strength
        if self.use_conference_strength:
            cs_module = _get_conference_strength()
            if cs_module is not None:
                try:
                    print("  Initializing conference strength (Phase 4)...")
                    self._conference_strength = cs_module.ConferenceStrength()
                    # Calculate conference ratings from game data and power ratings
                    if self._power_ratings is not None and hasattr(self._power_ratings, 'ratings'):
                        self._conference_strength.calculate_ratings(
                            train_df,
                            team_ratings=self._power_ratings.ratings
                        )
                        n_conferences = len(self._conference_strength.conference_ratings)
                        print(f"    ✓ Calculated conference strength for {n_conferences} conferences")
                    else:
                        # Can still calculate from game data alone
                        self._conference_strength.calculate_ratings(train_df)
                        n_conferences = len(self._conference_strength.conference_ratings)
                        print(f"    ✓ Calculated conference strength for {n_conferences} conferences (no ratings)")
                except Exception as e:
                    print(f"    Warning: Conference strength init failed: {e}")
                    self._conference_strength = None
        
        # Task 4.2: Recency Weighting / Momentum
        if self.use_recency_weighting:
            rw_module = _get_recency_weighting()
            if rw_module is not None:
                try:
                    print("  Initializing recency weighting (Phase 4)...")
                    self._recency_weighting = rw_module.RecencyWeighting(
                        decay_rate=0.1,
                        half_life_days=14,
                        min_games=3
                    )
                    print(f"    ✓ Recency weighting initialized (decay=0.1, half_life=14)")
                except Exception as e:
                    print(f"    Warning: Recency weighting init failed: {e}")
                    self._recency_weighting = None

    @staticmethod
    def _team_game_counts_from_frame(df: pd.DataFrame) -> dict[str, int]:
        if df is None or df.empty:
            return {}
        cols = [c for c in ['home_team', 'away_team'] if c in df.columns]
        if len(cols) != 2:
            return {}
        combined = pd.concat([df['home_team'], df['away_team']], ignore_index=True)
        return combined.value_counts(dropna=True).astype(int).to_dict()

    @staticmethod
    def _solve_logit_shift(probabilities: np.ndarray, target: float) -> float:
        """Find additive logit shift so mean probability matches target."""
        probs = np.clip(np.asarray(probabilities, dtype=float), 1e-5, 1 - 1e-5)
        logits = np.log(probs / (1 - probs))
        target = float(np.clip(target, 1e-5, 1 - 1e-5))
        lo, hi = -10.0, 10.0
        # Ensure bounds cover target
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            adj = 1.0 / (1.0 + np.exp(-(logits - mid)))
            mean = float(adj.mean())
            if mean > target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _apply_home_court_shift(self, probabilities: np.ndarray) -> np.ndarray:
        """Apply stored home-court logit shift to probability array."""
        if not self.home_court_logit_shift_value:
            return np.clip(probabilities, 1e-6, 1 - 1e-6)
        probs = np.clip(probabilities.astype(float), 1e-5, 1 - 1e-5)
        logits = np.log(probs / (1 - probs))
        logits_adj = logits - self.home_court_logit_shift_value
        adjusted = 1.0 / (1.0 + np.exp(-logits_adj))
        return np.clip(adjusted, 1e-6, 1 - 1e-6)

    def _apply_confidence_temperature(self, probabilities: np.ndarray) -> np.ndarray:
        """Apply confidence temperature scaling around 0.5."""
        temp = float(self.confidence_temperature_value)
        if temp <= 0:
            return np.clip(probabilities, 1e-6, 1 - 1e-6)
        if abs(temp - 1.0) < 1e-6:
            return np.clip(probabilities, 1e-6, 1 - 1e-6)
        centered = probabilities - 0.5
        adjusted = 0.5 + centered * temp
        return np.clip(adjusted, 1e-6, 1 - 1e-6)

    def _configure_home_court_shift(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Determine home-court logit adjustment based on configuration."""
        mode = self.home_court_logit_shift_mode
        self.home_court_logit_shift_target = None
        if isinstance(mode, (int, float)):
            self.home_court_logit_shift_value = float(mode)
            self.home_court_logit_shift_source = 'fixed'
            print(f"Using fixed home-court logit shift {self.home_court_logit_shift_value:.4f}")
            return
        if isinstance(mode, str):
            mode_lower = mode.lower().strip()
            if mode_lower in {'none', 'off', 'disable'}:
                self.home_court_logit_shift_value = 0.0
                self.home_court_logit_shift_source = mode_lower
                print("Home-court logit shift disabled")
                return
            target = float(np.clip(y.mean(), 1e-5, 1 - 1e-5))
            if ':' in mode_lower:
                _, tail = mode_lower.split(':', 1)
                tail = tail.strip()
                if tail in {'even', 'neutral', 'balanced'}:
                    target = 0.5
                else:
                    try:
                        target = float(tail)
                    except ValueError:
                        print(f"Unrecognized home_court_logit_shift target '{tail}', defaulting to empirical mean")
            # Auto-calibrate shift to align mean predicted probability with target
            try:
                home_probs = self.model.predict_proba(X)[:, 1]
                shift = self._solve_logit_shift(home_probs, target)
                self.home_court_logit_shift_value = float(shift)
                self.home_court_logit_shift_target = target
                self.home_court_logit_shift_source = f'auto:{target:.4f}'
                print(
                    "Home-court logit shift calibrated: "
                    f"target={target:.3f}, shift={self.home_court_logit_shift_value:.4f}"
                )
                return
            except Exception as exc:
                print(f"Home-court auto calibration failed ({exc}); falling back to empirical baseline")
        # Fallback to empirical baseline logit if auto calibration fails or mode unrecognized
        base = float(np.clip(y.mean(), 1e-4, 1 - 1e-4))
        self.home_court_logit_shift_value = float(np.log(base / (1 - base)))
        self.home_court_logit_shift_source = 'fallback:empirical_logit'
        self.home_court_logit_shift_target = base
        print(
            "Home-court logit shift fallback: "
            f"target={base:.3f}, shift={self.home_court_logit_shift_value:.4f}"
        )

    def _configure_confidence_temperature(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Determine confidence temperature scaling."""
        mode = self.confidence_temperature_mode
        try:
            base_probs = self.model.predict_proba(X)[:, 1]
        except Exception:
            base_probs = np.full(len(y), 0.5, dtype=float)
        shifted = self._apply_home_court_shift(base_probs)

        def _set(value: float, source: str) -> None:
            clipped = float(np.clip(value, 0.05, 1.5))
            self.confidence_temperature_value = clipped
            self.confidence_temperature_source = source

        if isinstance(mode, (int, float)):
            _set(float(mode), 'fixed')
            print(f"Using fixed confidence_temperature={self.confidence_temperature_value:.3f}")
            return
        if isinstance(mode, str):
            lower = mode.lower().strip()
            if lower in {'off', 'none', 'disable', 'unity', '1', 'baseline'}:
                _set(1.0, lower)
                print("Confidence tempering disabled (temperature=1.0)")
                return
            if lower.startswith('auto'):
                diffs = shifted - 0.5
                denom = float(np.sum(diffs ** 2))
                if denom <= 1e-10:
                    _set(0.85, 'auto:fallback_denominator')
                    print("Confidence temperature auto-calibration fallback (denominator too small)")
                    return
                numerator = float(np.sum((y.astype(float) - 0.5) * diffs))
                temp = numerator / denom
                temp = float(np.clip(temp, 0.3, 1.0))
                _set(temp, f'auto:{temp:.3f}')
                print(f"Confidence temperature auto-calibrated: {self.confidence_temperature_value:.3f}")
                return
            try:
                numeric = float(mode)
                _set(numeric, 'coerced')
                print(f"Confidence temperature coerced to {self.confidence_temperature_value:.3f}")
                return
            except Exception:
                pass
        _set(0.85, 'default')
        print("Confidence temperature fallback to default 0.85")

    def _update_min_games_threshold(self, train_df: pd.DataFrame) -> None:
        mode = self.min_games_threshold_mode
        # Explicit numeric overrides take precedence
        if isinstance(mode, (int, float)):
            self.min_games_threshold = int(mode)
            self.min_games_threshold_source = 'fixed'
            print(f"Using fixed min_games_threshold={self.min_games_threshold}")
            return
        if isinstance(mode, str) and mode.lower() != 'auto':
            try:
                self.min_games_threshold = int(float(mode))
                self.min_games_threshold_source = 'coerced'
                print(f"Using coerced min_games_threshold={self.min_games_threshold}")
                return
            except Exception:
                print(f"Invalid min_games_threshold '{mode}'; fallback to dynamic auto mode")
        # Auto mode derives threshold from most recent season coverage
        floor, ceiling = 10, 120
        chosen = None
        if 'season' in train_df.columns:
            season_values = train_df['season']
            season_non_null = season_values[season_values.notna()].astype(str)
            if not season_non_null.empty:
                current_season = season_non_null.sort_values().iloc[-1]
                season_mask = season_values.astype(str) == current_season
                season_df = train_df[season_mask]
                latest_counts = self._team_game_counts_from_frame(season_df)
                if latest_counts:
                    chosen = int(round(np.percentile(list(latest_counts.values()), 40)))
                    self.min_games_threshold_source = f'auto:{current_season}'
        if chosen is None:
            all_counts = list(self.team_game_counts.values())
            if all_counts:
                chosen = int(round(np.percentile(all_counts, 30)))
                self.min_games_threshold_source = 'auto:global'
        if chosen is None or chosen <= 0:
            chosen = floor
            self.min_games_threshold_source = 'auto:fallback'
        chosen = int(np.clip(chosen, floor, ceiling))
        self.min_games_threshold = chosen
        print(f"Dynamic min_games_threshold set to {self.min_games_threshold} ({self.min_games_threshold_source})")

    def fit(self, train_df):
        """
        Train the model on historical data.

        Args:
            train_df: DataFrame with training data

        Returns:
            self for method chaining
        """
        # Store raw training data for Phase 2 feature calculations
        self._historical_games = train_df.copy()
        
        # Initialize Phase 2 features before prepare_data
        self._init_phase2_features(train_df)
        
        # Initialize Phase 4 features (depends on Phase 2 for power ratings)
        self._init_phase4_features(train_df)
        
        train_df = self.prepare_data(train_df)
        self.training_data = train_df  # Store for game count lookups

        # Calculate game counts per team
        print(f"Calculating game counts for {len(train_df)} training games...")
        for team in pd.concat([train_df['home_team'], train_df['away_team']]).unique():  # type: ignore[attr-defined]
            team_games = train_df[(train_df['home_team'] == team) | (train_df['away_team'] == team)]
            self.team_game_counts[team] = len(team_games)

        # Derive dynamic minimum games threshold if configured
        self._update_min_games_threshold(train_df)

        # Report teams with low game counts
        low_game_teams = {team: count for team, count in self.team_game_counts.items()
                          if count < self.min_games_threshold}
        if low_game_teams:
            print(f"Warning: {len(low_game_teams)} teams have < {self.min_games_threshold} games in training data")

        # Encode teams
        all_teams_series = pd.concat([train_df['home_team'], train_df['away_team']])
        all_teams = all_teams_series.unique()  # type: ignore
        self.team_encoder.fit(all_teams)

        train_df['home_team_encoded'] = self.team_encoder.transform(train_df['home_team'])
        train_df['away_team_encoded'] = self.team_encoder.transform(train_df['away_team'])

        # Train model
        # Filter feature columns that exist (dynamic expansion with feature store)
        available = [c for c in self.feature_cols if c in train_df.columns]
        if set(self.feature_cols) - set(available):
            missing = set(self.feature_cols) - set(available)
            if missing:
                print(f"Note: Skipping missing feature columns: {sorted(missing)}")
        X = train_df[available]
        y = train_df['home_win']

        print(f"Training model on {len(train_df)} games...")
        self._raw_model.fit(X, y)
        if self.calibrate and self.calibration_method in ('sigmoid', 'isotonic'):
            try:
                self.model = CalibratedClassifierCV(self._raw_model, method=self.calibration_method, cv=5)
                self.model.fit(X, y)  # calibration wrapper fit
            except Exception as exc:
                print(f"Calibration failed ({exc}); using raw model.")
                self.model = self._raw_model
        else:
            self.model = self._raw_model

        # Calculate accuracy
        train_accuracy = self.model.score(X, y)
        print(f"Training accuracy: {train_accuracy:.1%}")
        # Feature importance (only available on raw RandomForest)
        try:
            importances = self._raw_model.feature_importances_
            imp_df = pd.DataFrame({
                'feature': available,
                'importance': importances[:len(available)]
            }).sort_values('importance', ascending=False)
            os.makedirs(os.path.dirname(self.feature_importance_path), exist_ok=True)
            imp_df.to_csv(self.feature_importance_path, index=False)
            top = imp_df.head(8)
            print("Top features (adaptive predictor):")
            for _, r in top.iterrows():
                print(f"  {r['feature']}: {r['importance']:.4f}")
            print(f"Feature importances written to {self.feature_importance_path}")
        except Exception as exc:
            print(f"Feature importance logging skipped: {exc}")

        # Store home-court logit adjustment (shifts probabilities away from automatic home bias)
        # Configure home-court probability adjustment
        try:
            self._configure_home_court_shift(X, y)
        except Exception as exc:
            print(f"Home-court shift configuration failed ({exc}); defaulting to zero shift")
            self.home_court_logit_shift_value = 0.0
            self.home_court_logit_shift_source = 'error'
            self.home_court_logit_shift_target = None

        try:
            self._configure_confidence_temperature(X, y)
        except Exception as exc:
            print(f"Confidence temperature configuration failed ({exc}); using default 0.85")
            self.confidence_temperature_value = 0.85
            self.confidence_temperature_source = 'error'

        return self

    def predict(self, upcoming_df, skip_low_data=True, low_data_log_path='data/Low_Data_Games.csv'):
        """
        Generate predictions for upcoming games.

        Args:
            upcoming_df: DataFrame with upcoming games
            skip_low_data: If True, skip predictions for teams with < min_games_threshold games
            low_data_log_path: Path to CSV file for logging skipped low-data games

        Returns:
            DataFrame with predictions and probabilities (only for high-data games if skip_low_data=True)
        """
        upcoming_df = self.prepare_data(upcoming_df.copy())

        # Check game counts and identify low-data games
        low_data_games = []
        valid_game_indices = []

        for idx, row in upcoming_df.iterrows():
            home_team = row['home_team']
            away_team = row['away_team']

            home_games = self.team_game_counts.get(home_team, 0)
            away_games = self.team_game_counts.get(away_team, 0)

            if skip_low_data and (home_games < self.min_games_threshold or away_games < self.min_games_threshold):
                # Log this game as low-data
                low_data_games.append({
                    'game_id': row['game_id'],
                    'date': row['date'],
                    'away_team': away_team,
                    'away_games': away_games,
                    'home_team': home_team,
                    'home_games': home_games,
                    'min_games': min(home_games, away_games),
                    'reason': (
                        f"Team with only {min(home_games, away_games)} games "
                        f"(threshold: {self.min_games_threshold} | source: {self.min_games_threshold_source})"
                    ),
                    'game_url': row['game_url']
                })
            else:
                valid_game_indices.append(idx)

        # Log low-data games if any
        if low_data_games:
            low_data_df = pd.DataFrame(low_data_games)

            # Append to existing file or create new
            if os.path.exists(low_data_log_path):
                existing_df = pd.read_csv(low_data_log_path)
                combined_df = pd.concat([existing_df, low_data_df], ignore_index=True)
                # Remove duplicates based on game_id
                combined_df = combined_df.drop_duplicates(subset=['game_id'], keep='last')
                combined_df.to_csv(low_data_log_path, index=False)
            else:
                low_data_df.to_csv(low_data_log_path, index=False)

            print(f"\n⚠️  Skipped {len(low_data_games)} low-data games (logged to {low_data_log_path})")
            for game in low_data_games:
                print(f"   {game['away_team']} @ {game['home_team']} - "
                      f"Min games: {game['min_games']} (away: {game['away_games']}, home: {game['home_games']})")
        self.last_low_data_games = low_data_games

        # If no valid games, return empty DataFrame with correct structure
        if not valid_game_indices:
            print("⚠️  No games with sufficient data to predict!")
            return pd.DataFrame(columns=['game_id', 'date', 'away_team', 'home_team',
                                        'predicted_home_win', 'home_win_probability',
                                        'away_win_probability', 'predicted_winner',
                                        'confidence', 'game_url'])

        # Filter to valid games only
        upcoming_valid = upcoming_df.loc[valid_game_indices].copy()

        # Encode teams using smart encoding (Phase 1 Task 1.2)
        upcoming_valid['home_team_encoded'] = upcoming_valid['home_team'].apply(
            lambda x: self._encode_team_smart(x)
        )
        upcoming_valid['away_team_encoded'] = upcoming_valid['away_team'].apply(
            lambda x: self._encode_team_smart(x)
        )
        
        # Track unknown teams for logging
        unknown_teams = []
        for team in pd.concat([upcoming_valid['home_team'], upcoming_valid['away_team']]).unique():
            if team not in self.team_encoder.classes_:
                unknown_teams.append(team)
        if unknown_teams and self.use_smart_encoding:
            print(f"  ℹ️  {len(unknown_teams)} unknown teams encoded with smart fallback")

        # Make predictions
        trained_features = getattr(self.model, 'feature_names_in_', None)
        if trained_features is not None:
            # Align upcoming features exactly to trained feature ordering; fill missing with 0
            X_upcoming = upcoming_valid.reindex(columns=list(trained_features), fill_value=0)
        else:
            available = [c for c in self.feature_cols if c in upcoming_valid.columns]
            X_upcoming = upcoming_valid[available]
        base_probs = self.model.predict_proba(X_upcoming)[:, 1]
        home_probs_adj = self._apply_home_court_shift(base_probs)
        probabilities = self._apply_confidence_temperature(home_probs_adj)
        
        # Apply early season adjustment (Phase 1 Task 1.4)
        if self.use_early_season_adjustment:
            early_season_adjustments = []
            for idx, row in upcoming_valid.iterrows():
                game_date = row.get('date')
                home_games = self.team_game_counts.get(row['home_team'], 0)
                away_games = self.team_game_counts.get(row['away_team'], 0)
                factor = self._get_early_season_confidence_factor(game_date, home_games, away_games)
                early_season_adjustments.append(factor)
            
            early_season_adjustments = np.array(early_season_adjustments)
            
            # Apply adjustment: move probabilities toward 0.5
            # If factor < 1.0, reduce confidence
            adjusted_probs = 0.5 + (probabilities - 0.5) * early_season_adjustments
            probabilities = np.clip(adjusted_probs, 0.01, 0.99)
            
            # Log if adjustments were applied
            adjusted_count = np.sum(early_season_adjustments < 1.0)
            if adjusted_count > 0:
                avg_factor = np.mean(early_season_adjustments[early_season_adjustments < 1.0])
                print(f"  ℹ️  Applied early season confidence adjustment to {adjusted_count} games (avg factor: {avg_factor:.2f})")
        
        probabilities = np.column_stack([1 - probabilities, probabilities])

        # Derive predictions from calibrated probabilities (pre-temperature)
        predictions = (home_probs_adj >= 0.5).astype(int)

        # Create results dataframe
        results_df = pd.DataFrame({
            'game_id': upcoming_valid['game_id'],
            'date': upcoming_valid['date'],
            'away_team': upcoming_valid['away_team'],
            'home_team': upcoming_valid['home_team'],
            'predicted_home_win': predictions,
            'home_win_probability': probabilities[:, 1],
            'away_win_probability': probabilities[:, 0],
            'game_url': upcoming_valid['game_url']
        })

        # Preserve moneyline columns if they exist in the input data
        moneyline_cols = ['home_moneyline', 'away_moneyline', 'has_real_odds']
        for col in moneyline_cols:
            if col in upcoming_valid.columns:
                results_df[col] = upcoming_valid[col].values

        results_df['predicted_winner'] = results_df.apply(
            lambda row: row['home_team'] if row['predicted_home_win'] == 1 else row['away_team'],
            axis=1
        )
        results_df['confidence'] = results_df[['home_win_probability', 'away_win_probability']].max(axis=1)

        print(f"✓ Generated predictions for {len(results_df)} games with sufficient data")

        return results_df


# Backward compatibility alias until downstream scripts migrate fully
SimplePredictor = AdaptivePredictor

__all__ = ["AdaptivePredictor", "SimplePredictor"]
