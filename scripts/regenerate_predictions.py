#!/usr/bin/env python3
"""
Quick regeneration of predictions using existing trained model.
This skips scraping and training - just generates new predictions with explanations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.database import get_db_connection
from backend.repositories.games_repository import GamesRepository  
from backend.repositories.predictions_repository import PredictionsRepository
from model_training.adaptive_predictor import AdaptivePredictor
from datetime import datetime
import pickle

print("="*80)
print("REGENERATING PREDICTIONS WITH EXPLANATIONS")
print("="*80)
print()

# Setup
db = get_db_connection()
games_repo = GamesRepository(db)
pred_repo = PredictionsRepository(db)

# Load upcoming games
print("1. Loading upcoming games...")
upcoming = games_repo.get_upcoming_games_df()
print(f"   ✓ Found {len(upcoming)} scheduled games")

# Initialize predictor with trained model
print("\n2. Loading trained model...")
predictor = AdaptivePredictor()

# Load the saved model
model_path = 'data/Adaptive_NCAA_Predictor.pkl'
if os.path.exists(model_path):
    with open(model_path, 'rb') as f:
        predictor.model = pickle.load(f)
    print(f"   ✓ Loaded model from {model_path}")
else:
    print(f"   ❌ No trained model found at {model_path}")
    print("   Run full pipeline: python daily_pipeline_db.py")
    sys.exit(1)

# Load completed games for training data (needed for team encodings, etc.)
print("\n3. Loading training data...")
completed = games_repo.get_completed_games_df()
print(f"   ✓ Loaded {len(completed)} completed games")

# Train/fit the predictor (this sets up encodings but doesn't retrain model)
print("\n4. Fitting predictor (creates team encodings)...")
predictor.fit(completed)
print("   ✓ Predictor fitted")

# Generate predictions with explanations
print("\n5. Generating predictions with real explanations...")
predictions_df = predictor.predict(upcoming)
print(f"   ✓ Generated {len(predictions_df)} predictions")

# Check explanations
if 'explanation' in predictions_df.columns:
    explained = predictions_df['explanation'].notna().sum()
    print(f"   ✓ Generated {explained} explanations")
    
    # Show sample
    if explained > 0:
        sample = predictions_df[predictions_df['explanation'].notna()].iloc[0]
        print(f"\n   📝 Sample:")
        print(f"      {sample['away_team']} @ {sample['home_team']}")
        print(f"      Predicted: {sample['predicted_winner']} ({sample['confidence']*100:.1f}%)")
        print(f"      {sample['explanation']}")
else:
    print("   ⚠️  No explanations generated")

# Save to database
print("\n6. Saving to database...")
count = 0
for _, row in predictions_df.iterrows():
    pred_data = {
        'game_id': row['game_id'],
        'prediction_date': datetime.now(),
        'home_win_prob': row['home_win_probability'],
        'away_win_prob': row['away_win_probability'],
        'predicted_winner': row['predicted_winner'],
        'predicted_home_win': row['predicted_home_win'],
        'confidence': row['confidence'],
        'model_name': 'AdaptivePredictor',
        'model_version': predictor.model_version,
        'config_version': predictor.config_version,
        'commit_hash': predictor.commit_hash,
        'source': 'regenerate',
        'explanation': row.get('explanation')
    }
    if pred_repo.upsert_prediction(pred_data):
        count += 1

print(f"   ✓ Saved {count} predictions with explanations")

# Export to JSON
print("\n7. Exporting to JSON...")
os.system('python scripts/export_to_json.py > /dev/null 2>&1')
print("   ✓ Exported to JSON")

print("\n" + "="*80)
print("✅ DONE! Predictions regenerated with real data-driven explanations")
print("="*80)
print("\n🌐 Refresh your browser to see the real explanations!")

db.close()
