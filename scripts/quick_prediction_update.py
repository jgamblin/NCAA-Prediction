#!/usr/bin/env python3
"""
Quick prediction update with explanations.
Skips training - just loads existing model and generates new predictions with explanations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.database import get_db_connection
from backend.repositories.games_repository import GamesRepository
from backend.repositories.predictions_repository import PredictionsRepository
from model_training.adaptive_predictor import AdaptivePredictor
import pandas as pd
from datetime import datetime

print("="*80)
print("QUICK PREDICTION UPDATE WITH EXPLANATIONS")
print("="*80)
print()

# Connect to database
db = get_db_connection()
games_repo = GamesRepository(db)
pred_repo = PredictionsRepository(db)

# Get scheduled games
print("📅 Loading scheduled games...")
scheduled = games_repo.get_upcoming_games_df()
print(f"   ✓ Found {len(scheduled)} scheduled games")

if len(scheduled) == 0:
    print("   ⚠️  No scheduled games to predict")
    sys.exit(0)

# Initialize predictor
print("\n🤖 Initializing predictor...")
predictor = AdaptivePredictor()

# Generate predictions with explanations
# The predict() method will train if needed, or load existing model
print("\n🎯 Generating predictions with explanations...")
print("   (This loads games from DB, trains/loads model, generates real explanations)")
print("   This may take a minute...")

try:
    predictions = predictor.predict(scheduled)
    
    if predictions is None or len(predictions) == 0:
        print("   ❌ No predictions generated")
        sys.exit(1)
    
    print(f"   ✓ Generated {len(predictions)} predictions")
    
    # Check for explanations
    if 'explanation' in predictions.columns:
        explained = predictions['explanation'].notna().sum()
        print(f"   ✓ Generated {explained} explanations")
        
        # Show a sample
        if explained > 0:
            sample = predictions[predictions['explanation'].notna()].iloc[0]
            print("\n   📝 Sample explanation:")
            print(f"      Game: {sample['away_team']} @ {sample['home_team']}")
            print(f"      Predicted: {sample['predicted_winner']} ({sample['confidence']*100:.1f}%)")
            print(f"      Explanation: {sample['explanation']}")
    else:
        print("   ⚠️  No explanation column in predictions")
    
    # Save to database
    print("\n💾 Saving predictions to database...")
    saved_count = 0
    for _, pred in predictions.iterrows():
        pred_data = {
            'game_id': pred['game_id'],
            'prediction_date': datetime.now(),
            'home_win_prob': pred['home_win_prob'],
            'away_win_prob': pred['away_win_prob'],
            'predicted_winner': pred['predicted_winner'],
            'predicted_home_win': pred['predicted_home_win'],
            'confidence': pred['confidence'],
            'model_name': predictor.model_name,
            'model_version': predictor.model_version,
            'config_version': predictor.config_version,
            'commit_hash': predictor.commit_hash,
            'source': 'quick_update',
            'explanation': pred.get('explanation')
        }
        
        result = pred_repo.upsert_prediction(pred_data)
        if result:
            saved_count += 1
    
    print(f"   ✓ Saved {saved_count} predictions to database")
    
    # Export to JSON
    print("\n📤 Exporting to JSON...")
    os.system('python scripts/export_to_json.py')
    
    print("\n" + "="*80)
    print("✅ DONE! Predictions updated with real data-driven explanations")
    print("="*80)
    print("\n💡 Refresh your browser to see the explanations!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
