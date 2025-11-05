#!/usr/bin/env python3
"""
Simple Random Forest predictor for NCAA games.
Used by daily_pipeline.py for quick predictions.
"""

import pandas as pd
import numpy as np
import sys
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.calibration import CalibratedClassifierCV

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_collection.team_name_utils import normalize_team_name


class SimplePredictor:
    """Simple prediction model for NCAA basketball games."""
    
    def __init__(self, n_estimators=100, max_depth=20, min_samples_split=10, min_games_threshold=75,
                 calibrate=True, calibration_method='sigmoid', feature_importance_path='data/Simple_Feature_Importance.csv'):
        """
        Initialize the predictor.
        
        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum depth of trees
            min_samples_split: Minimum samples required to split a node
            min_games_threshold: Minimum number of historical games required to make a prediction (default: 75 = ~15 games/season over 5 seasons)
        """
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
            'home_team_encoded', 'away_team_encoded', 'is_neutral', 'home_rank', 'away_rank'
        ]
        self.min_games_threshold = min_games_threshold
        self.team_game_counts = {}  # Store game counts per team
        self.training_data = None  # Store reference to training data
        self.calibrate = calibrate
        self.calibration_method = calibration_method
        self.feature_importance_path = feature_importance_path
    
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
        
        # Feature store diff features (if enriched via pipeline)
        # Expect columns like home_fs_rolling_win_pct_5, away_fs_rolling_win_pct_5, etc.
        fs_pairs = [
            ('rolling_win_pct_5','fs_win_pct5_diff'),
            ('rolling_win_pct_10','fs_win_pct10_diff'),
            ('rolling_point_diff_avg_5','fs_point_diff5_diff'),
            ('rolling_point_diff_avg_10','fs_point_diff10_diff'),
            ('win_pct_last5_vs10','fs_win_pct_last5_vs10_diff'),
            ('point_diff_last5_vs10','fs_point_diff_last5_vs10_diff'),
            ('recent_strength_index_5','fs_recent_strength_index5_diff'),
        ]
        for base, diff_name in fs_pairs:
            h_col = f'home_fs_{base}'
            a_col = f'away_fs_{base}'
            if h_col in df.columns and a_col in df.columns:
                df[diff_name] = df[h_col] - df[a_col]
                if diff_name not in self.feature_cols:
                    self.feature_cols.append(diff_name)
        return df
    
    def fit(self, train_df):
        """
        Train the model on historical data.
        
        Args:
            train_df: DataFrame with training data
            
        Returns:
            self for method chaining
        """
        train_df = self.prepare_data(train_df)
        self.training_data = train_df  # Store for game count lookups
        
        # Calculate game counts per team
        print(f"Calculating game counts for {len(train_df)} training games...")
        for team in pd.concat([train_df['home_team'], train_df['away_team']]).unique():  # type: ignore[attr-defined]
            team_games = train_df[(train_df['home_team'] == team) | (train_df['away_team'] == team)]
            self.team_game_counts[team] = len(team_games)
        
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
        if self.calibrate and self.calibration_method in ('sigmoid','isotonic'):
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
            print("Top features (simple predictor):")
            for _, r in top.iterrows():
                print(f"  {r['feature']}: {r['importance']:.4f}")
            print(f"Feature importances written to {self.feature_importance_path}")
        except Exception as exc:
            print(f"Feature importance logging skipped: {exc}")
        
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
                    'reason': f"Team with only {min(home_games, away_games)} games (threshold: {self.min_games_threshold})",
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
        
        # If no valid games, return empty DataFrame with correct structure
        if not valid_game_indices:
            print("⚠️  No games with sufficient data to predict!")
            return pd.DataFrame(columns=['game_id', 'date', 'away_team', 'home_team', 
                                        'predicted_home_win', 'home_win_probability', 
                                        'away_win_probability', 'predicted_winner', 
                                        'confidence', 'game_url'])
        
        # Filter to valid games only
        upcoming_valid = upcoming_df.loc[valid_game_indices].copy()
        
        # Encode teams (handle unknown teams)
        def encode_team(team_name, encoder):
            """Encode team name, return -1 for unknown teams."""
            if team_name in encoder.classes_:
                return encoder.transform([team_name])[0]
            return -1
        
        upcoming_valid['home_team_encoded'] = upcoming_valid['home_team'].apply(
            lambda x: encode_team(x, self.team_encoder)
        )
        upcoming_valid['away_team_encoded'] = upcoming_valid['away_team'].apply(
            lambda x: encode_team(x, self.team_encoder)
        )
        
        # Make predictions
        trained_features = getattr(self.model, 'feature_names_in_', None)
        if trained_features is not None:
            # Align upcoming features exactly to trained feature ordering; fill missing with 0
            X_upcoming = upcoming_valid.reindex(columns=list(trained_features), fill_value=0)
        else:
            available = [c for c in self.feature_cols if c in upcoming_valid.columns]
            X_upcoming = upcoming_valid[available]
        predictions = self.model.predict(X_upcoming)
        probabilities = self.model.predict_proba(X_upcoming)
        
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
        
        results_df['predicted_winner'] = results_df.apply(
            lambda row: row['home_team'] if row['predicted_home_win'] == 1 else row['away_team'],
            axis=1
        )
        results_df['confidence'] = results_df[['home_win_probability', 'away_win_probability']].max(axis=1)
        
        print(f"✓ Generated predictions for {len(results_df)} games with sufficient data")
        
        return results_df
