#!/usr/bin/env python3
"""
Add sample explanations to existing predictions for UI testing.
These are generic but will let you see the UI working immediately.
Run the full pipeline later for real data-driven explanations.
"""

import json
import sys

print("="*80)
print("ADDING SAMPLE EXPLANATIONS TO PREDICTIONS")
print("="*80)
print()

# Read current data
print("📖 Reading upcoming_games.json...")
with open('frontend/public/data/upcoming_games.json', 'r') as f:
    games = json.load(f)

print(f"   ✓ Loaded {len(games)} games")

# Add explanation to games with predictions
count = 0
for game in games:
    if game.get('predicted_winner') and game.get('confidence'):
        team = game['predicted_winner']
        conf = game['confidence']
        
        # Generate explanation based on confidence level
        if conf >= 0.80:
            level = 'strongly favored'
            reasons = 'they have a major offensive advantage, they are dominant at their home venue, and they have the edge in overall team strength'
        elif conf >= 0.70:
            level = 'confidently favored'
            reasons = 'they have a notably better offense, they perform well at home, and they are playing much better lately'
        elif conf >= 0.60:
            level = 'favored'
            reasons = 'they have a slight offensive edge, they have momentum on their side, and they have a slight home court advantage'
        else:
            level = 'narrowly favored'
            reasons = 'they have a slight edge in overall team strength'
        
        game['explanation'] = f'{team} is {level}: {reasons}.'
        count += 1

print(f"   ✅ Added explanations to {count} games with predictions")

# Save back
print("\n💾 Saving updated data...")
with open('frontend/public/data/upcoming_games.json', 'w') as f:
    json.dump(games, f, indent=2)

print("   ✓ Saved to frontend/public/data/upcoming_games.json")

print("\n" + "="*80)
print("✅ DONE!")
print("="*80)
print()
print("🎨 These are sample explanations for UI testing")
print("📝 For real data-driven explanations, run the full pipeline:")
print("   python daily_pipeline_db.py")
print()
print("🌐 Refresh your browser to see the explanations!")
