#!/usr/bin/env python3
"""
Relocated debug script: Investigates Indiana vs Alabama A&M prediction anomaly.
Originally at repo root (debug_indiana_prediction.py). Kept for historical analysis.
"""

import pandas as pd
from model_training.adaptive_predictor import AdaptivePredictor

print("="*80)
print("DEBUGGING INDIANA vs ALABAMA A&M PREDICTION")
print("="*80)

completed = pd.read_csv('data/Completed_Games.csv')
upcoming = pd.read_csv('data/Upcoming_Games.csv')

indiana_game = upcoming[upcoming['game_id'] == 401827172]
print("\n1. UPCOMING GAME DATA:")
print(indiana_game[['game_id', 'away_team', 'home_team']].to_string(index=False))

print("\n2. TEAM NAME CHECK IN TRAINING DATA:")
print(f"   'Indiana Hoosiers' in training: {( 'Indiana Hoosiers' in completed['home_team'].values) or ('Indiana Hoosiers' in completed['away_team'].values)}")
print(f"   'Indiana' in training: {( 'Indiana' in completed['home_team'].values) or ('Indiana' in completed['away_team'].values)}")
print(f"   'Alabama A&M Bulldogs' in training: {( 'Alabama A&M Bulldogs' in completed['home_team'].values) or ('Alabama A&M Bulldogs' in completed['away_team'].values)}")
print(f"   'Alabama A&M' in training: {( 'Alabama A&M' in completed['home_team'].values) or ('Alabama A&M' in completed['away_team'].values)}")

print("\n3. INDIANA TEAM NAME VARIATIONS IN TRAINING DATA:")
indiana_variations = set()
for col in ['home_team', 'away_team']:
    indiana_teams = completed[completed[col].str.contains('Indiana', case=False, na=False)][col].unique()
    indiana_variations.update(indiana_teams)
print(f"   Found {len(indiana_variations)} variations:")
for team in sorted(indiana_variations):
    count = len(completed[(completed['home_team'] == team) | (completed['away_team'] == team)])
    print(f"   - '{team}': {count} games")

print("\n4. ALABAMA A&M TEAM NAME VARIATIONS IN TRAINING DATA:")
aamu_variations = set()
for col in ['home_team', 'away_team']:
    aamu_teams = completed[completed[col].str.contains('Alabama A&M', case=False, na=False)][col].unique()
    aamu_variations.update(aamu_teams)
print(f"   Found {len(aamu_variations)} variations:")
for team in sorted(aamu_variations):
    count = len(completed[(completed['home_team'] == team) | (completed['away_team'] == team)])
    print(f"   - '{team}': {count} games")

print("\n5. MODEL TRAINING AND TEAM ENCODING:")
predictor = AdaptivePredictor()
predictor.fit(completed)

print(f"   Teams in encoder: {len(predictor.team_encoder.classes_)}")
for candidate in ['Indiana Hoosiers', 'Indiana', 'Alabama A&M Bulldogs', 'Alabama A&M']:
    print(f"   '{candidate}' encoded as: ", end="")
    if candidate in predictor.team_encoder.classes_:
        encoded_arr = predictor.team_encoder.transform([candidate])
        encoded_idx = int(encoded_arr[0])  # type: ignore[index]
        print(encoded_idx)
    else:
        print("NOT FOUND (-1 will be used)")

print("\n6. PREDICTION FOR ALABAMA A&M @ INDIANA:")
predictions = predictor.predict(indiana_game)
pred_row = predictions.iloc[0]
print(f"   Predicted winner: {pred_row['predicted_winner']}")
print(f"   Confidence: {pred_row['confidence']:.1%}")
print(f"   Home win probability (Indiana): {pred_row['home_win_probability']:.1%}")
print(f"   Away win probability (Alabama A&M): {pred_row['away_win_probability']:.1%}")

print("\n7. HISTORICAL PERFORMANCE:")
indiana_games = completed[(completed['home_team'] == 'Indiana') | (completed['away_team'] == 'Indiana')]
if len(indiana_games) > 0:
    indiana_home = indiana_games[indiana_games['home_team'] == 'Indiana']
    indiana_home_wins = (indiana_home['home_score'] > indiana_home['away_score']).sum()
    print(f"   Indiana (in training data): {len(indiana_games)} total, {indiana_home_wins/len(indiana_home)*100:.1f}% home win rate")

aamu_games = completed[(completed['home_team'] == 'Alabama A&M') | (completed['away_team'] == 'Alabama A&M')]
if len(aamu_games) > 0:
    aamu_away = aamu_games[aamu_games['away_team'] == 'Alabama A&M']
    aamu_away_wins = (aamu_away['away_score'] > aamu_away['home_score']).sum()
    print(f"   Alabama A&M (in training data): {len(aamu_games)} total, {aamu_away_wins/len(aamu_away)*100 if len(aamu_away)>0 else 0:.1f}% away win rate")

aamu_bulldogs_games = completed[(completed['home_team'] == 'Alabama A&M Bulldogs') | (completed['away_team'] == 'Alabama A&M Bulldogs')]
if len(aamu_bulldogs_games) > 0:
    print(f"   Alabama A&M Bulldogs (in training data): {len(aamu_bulldogs_games)} games")

print("\n" + "="*80)
print("ROOT CAUSE")
print("="*80)
print("Name drift (Hoosiers/Bulldogs suffix) introduced unseen variants. Normalization + ID capture mitigates.")
print("="*80)
