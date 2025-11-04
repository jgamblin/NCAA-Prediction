#!/usr/bin/env python3
"""
Simple Random Forest predictor for NCAA games.
Used by daily_pipeline.py for quick predictions.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder


class SimplePredictor:
    """Simple prediction model for NCAA basketball games."""
    
    def __init__(self, n_estimators=100, max_depth=20, min_samples_split=10):
        """
        Initialize the predictor.
        
        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum depth of trees
            min_samples_split: Minimum samples required to split a node
        """
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=42,
            n_jobs=-1
        )
        self.team_encoder = LabelEncoder()
        self.feature_cols = ['home_team_encoded', 'away_team_encoded', 
                            'is_neutral', 'home_rank', 'away_rank']
    
    def prepare_data(self, df):
        """
        Prepare dataframe for training/prediction.
        
        Args:
            df: DataFrame with game data
            
        Returns:
            Prepared DataFrame
        """
        df = df.copy()
        
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
        
        # Encode teams
        all_teams_series = pd.concat([train_df['home_team'], train_df['away_team']])
        all_teams = all_teams_series.unique()  # type: ignore
        self.team_encoder.fit(all_teams)
        
        train_df['home_team_encoded'] = self.team_encoder.transform(train_df['home_team'])
        train_df['away_team_encoded'] = self.team_encoder.transform(train_df['away_team'])
        
        # Train model
        X = train_df[self.feature_cols]
        y = train_df['home_win']
        
        print(f"Training model on {len(train_df)} games...")
        self.model.fit(X, y)
        
        # Calculate accuracy
        train_accuracy = self.model.score(X, y)
        print(f"Training accuracy: {train_accuracy:.1%}")
        
        return self
    
    def predict(self, upcoming_df):
        """
        Generate predictions for upcoming games.
        
        Args:
            upcoming_df: DataFrame with upcoming games
            
        Returns:
            DataFrame with predictions and probabilities
        """
        upcoming_df = self.prepare_data(upcoming_df.copy())
        
        # Encode teams (handle unknown teams)
        def encode_team(team_name, encoder):
            """Encode team name, return -1 for unknown teams."""
            if team_name in encoder.classes_:
                return encoder.transform([team_name])[0]
            return -1
        
        upcoming_df['home_team_encoded'] = upcoming_df['home_team'].apply(
            lambda x: encode_team(x, self.team_encoder)
        )
        upcoming_df['away_team_encoded'] = upcoming_df['away_team'].apply(
            lambda x: encode_team(x, self.team_encoder)
        )
        
        # Make predictions
        X_upcoming = upcoming_df[self.feature_cols]
        predictions = self.model.predict(X_upcoming)
        probabilities = self.model.predict_proba(X_upcoming)
        
        # Create results dataframe
        results_df = pd.DataFrame({
            'game_id': upcoming_df['game_id'],
            'date': upcoming_df['date'],
            'away_team': upcoming_df['away_team'],
            'home_team': upcoming_df['home_team'],
            'predicted_home_win': predictions,
            'home_win_probability': probabilities[:, 1],
            'away_win_probability': probabilities[:, 0],
            'game_url': upcoming_df['game_url']
        })
        
        results_df['predicted_winner'] = results_df.apply(
            lambda row: row['home_team'] if row['predicted_home_win'] == 1 else row['away_team'],
            axis=1
        )
        results_df['confidence'] = results_df[['home_win_probability', 'away_win_probability']].max(axis=1)
        
        return results_df
