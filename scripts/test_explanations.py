#!/usr/bin/env python3
"""
Test Prediction Explanations

Generates predictions with explanations to demonstrate the new feature.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
import pandas as pd

def main():
    print("="*80)
    print("TESTING PREDICTION EXPLANATIONS")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    completed_games = games_repo.get_completed_games_df()
    
    # Use recent games for training
    recent = completed_games.tail(1000).copy()
    
    # Split: train on most, predict on last 10
    train_data = recent.iloc[:-10].copy()
    predict_data = recent.iloc[-10:].copy()
    
    print(f"Training on {len(train_data)} games...")
    print(f"Predicting {len(predict_data)} games...\n")
    
    # Train model
    model = AdaptivePredictor(
        model_type='xgboost',
        xgb_learning_rate=0.05,
        xgb_reg_alpha=0.1,
        xgb_reg_lambda=1.0,
        remove_useless_features=True,
    )
    
    model.fit(train_data, use_validation=False)
    
    # Generate predictions with explanations
    predictions = model.predict(predict_data)
    
    print("\n" + "="*80)
    print("PREDICTIONS WITH EXPLANATIONS")
    print("="*80)
    print()
    
    # Display predictions
    for idx, row in predictions.iterrows():
        print(f"📍 {row['away_team']} @ {row['home_team']}")
        print(f"   Winner: {row['predicted_winner']} ({row['confidence']:.1%} confidence)")
        
        # Check if explanation column exists
        if 'explanation' in row:
            print(f"   💡 {row['explanation']}")
        else:
            print("   💡 No explanation available")
        
        # Show actual result if available
        if 'home_score' in predict_data.columns and 'away_score' in predict_data.columns:
            game = predict_data[predict_data['game_id'] == row['game_id']].iloc[0]
            actual_winner = game['home_team'] if game['home_score'] > game['away_score'] else game['away_team']
            correct = "✅" if actual_winner == row['predicted_winner'] else "❌"
            print(f"   Actual: {game['away_team']} {game['away_score']}, {game['home_team']} {game['home_score']} {correct}")
        
        print()
    
    db.close()

if __name__ == '__main__':
    main()
