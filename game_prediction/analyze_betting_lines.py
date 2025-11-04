#!/usr/bin/env python3
"""
Betting Line Comparison and Disagreement Tracker
Analyzes when our model disagrees with Vegas/ESPN betting lines and tracks success rate.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import json

def determine_betting_favorite(row):
    """
    Determine the betting favorite from available data.
    
    Returns: 'home', 'away', or None
    """
    # Check if we have point spread data
    if pd.notna(row.get('home_point_spread')) and row['home_point_spread'] != '':
        try:
            spread = float(row['home_point_spread'])
            if spread < 0:
                # Negative spread means home is favored
                return 'home', abs(spread)
            elif spread > 0:
                # Positive spread means away is favored
                return 'away', spread
            else:
                # Pick 'em
                return None, 0
        except (ValueError, TypeError):
            pass
    
    # Check if one team is ranked and the other isn't
    home_ranked = pd.notna(row.get('home_rank')) and row['home_rank'] != 99
    away_ranked = pd.notna(row.get('away_rank')) and row['away_rank'] != 99
    
    if home_ranked and not away_ranked:
        return 'home', None
    elif away_ranked and not home_ranked:
        return 'away', None
    elif home_ranked and away_ranked:
        # Lower rank number = better team = favorite
        if row['home_rank'] < row['away_rank']:
            return 'home', None
        elif row['away_rank'] < row['home_rank']:
            return 'away', None
    
    # If we're still here and game is at home (not neutral), assume small home advantage
    if row.get('is_neutral', 0) == 0:
        # Home team is default favorite by a small margin
        return 'home', None
    
    return None, None

def analyze_betting_line_performance():
    """Analyze our model's performance vs betting lines."""
    
    print("="*80)
    print("BETTING LINE COMPARISON & DISAGREEMENT ANALYSIS")
    print("="*80)
    print()
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Load predictions and completed games
    predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    
    if not os.path.exists(predictions_path):
        print("✗ No predictions file found")
        return
    
    predictions = pd.read_csv(predictions_path)
    print(f"✓ Loaded {len(predictions)} predictions")
    
    if not os.path.exists(completed_path):
        print("✗ No completed games file found")
        return
    
    completed = pd.read_csv(completed_path)
    print(f"✓ Loaded {len(completed)} completed games")
    
    # Merge predictions with actual results
    predictions['game_id'] = predictions['game_id'].astype(str)
    completed['game_id'] = completed['game_id'].astype(str)
    
    merged = predictions.merge(
        completed[['game_id', 'home_score', 'away_score', 'home_rank', 'away_rank', 
                   'home_point_spread', 'is_neutral']],
        on='game_id',
        how='inner',
        suffixes=('_pred', '_actual')
    )
    
    if len(merged) == 0:
        print("\n✗ No completed predictions found yet")
        return
    
    print(f"\n✓ Found {len(merged)} predictions with results")
    
    # Determine actual winner
    merged['actual_home_win'] = (merged['home_score'] > merged['away_score']).astype(int)
    merged['model_correct'] = (merged['predicted_home_win'] == merged['actual_home_win']).astype(int)
    
    # Determine betting favorite
    betting_info = merged.apply(determine_betting_favorite, axis=1, result_type='expand')
    merged['betting_favorite'] = betting_info[0]
    merged['point_spread'] = betting_info[1]
    
    # Determine if betting line was correct
    merged['betting_correct'] = merged.apply(
        lambda row: (
            (row['betting_favorite'] == 'home' and row['actual_home_win'] == 1) or
            (row['betting_favorite'] == 'away' and row['actual_home_win'] == 0)
        ) if row['betting_favorite'] is not None else None,
        axis=1
    )
    
    # Determine model favorite
    merged['model_favorite'] = merged.apply(
        lambda row: 'home' if row['predicted_home_win'] == 1 else 'away',
        axis=1
    )
    
    # Find disagreements
    merged['disagree'] = merged.apply(
        lambda row: (
            row['model_favorite'] != row['betting_favorite']
            if row['betting_favorite'] is not None else False
        ),
        axis=1
    )
    
    # =========================================================================
    # Analysis Section
    # =========================================================================
    
    print("\n" + "="*80)
    print("OVERALL PERFORMANCE")
    print("="*80)
    
    # Model performance
    model_accuracy = merged['model_correct'].mean()
    print(f"\n📊 Model Accuracy: {model_accuracy:.1%} ({merged['model_correct'].sum()}/{len(merged)})")
    
    # Betting line performance (where available)
    betting_available = merged[merged['betting_favorite'].notna()]
    if len(betting_available) > 0:
        betting_accuracy = betting_available['betting_correct'].mean()
        print(f"💰 Betting Line Accuracy: {betting_accuracy:.1%} ({betting_available['betting_correct'].sum()}/{len(betting_available)})")
        
        accuracy_diff = model_accuracy - betting_accuracy
        if accuracy_diff > 0:
            print(f"   ✓ Model is {accuracy_diff:.1%} better than betting lines!")
        elif accuracy_diff < 0:
            print(f"   ✗ Model is {abs(accuracy_diff):.1%} worse than betting lines")
        else:
            print(f"   = Model matches betting line accuracy")
    
    # =========================================================================
    # Agreement/Disagreement Analysis
    # =========================================================================
    
    print("\n" + "="*80)
    print("AGREEMENT vs DISAGREEMENT")
    print("="*80)
    
    agreements = merged[merged['disagree'] == False]
    disagreements = merged[merged['disagree'] == True]
    
    print(f"\n📊 Total games with betting lines: {len(betting_available)}")
    print(f"   ✓ Agreements: {len(agreements)} ({len(agreements)/len(betting_available)*100:.1f}%)")
    print(f"   ⚠️  Disagreements: {len(disagreements)} ({len(disagreements)/len(betting_available)*100:.1f}%)")
    
    # Performance on agreements
    if len(agreements) > 0:
        agreement_accuracy = agreements['model_correct'].mean()
        print(f"\n✓ Model accuracy when AGREEING with betting lines: {agreement_accuracy:.1%}")
    
    # Performance on disagreements - THE MONEY MAKER!
    if len(disagreements) > 0:
        disagreement_accuracy = disagreements['model_correct'].mean()
        print(f"\n⚠️  Model accuracy when DISAGREEING with betting lines: {disagreement_accuracy:.1%}")
        
        if disagreement_accuracy > 0.5:
            print(f"   🎯 PROFITABLE! Model is correct {disagreement_accuracy:.1%} when disagreeing!")
            print(f"   💵 If betting $100 per disagreement, potential ROI analysis:")
            
            # Simple ROI calculation (assumes -110 odds for simplicity)
            wins = disagreements['model_correct'].sum()
            losses = len(disagreements) - wins
            profit = (wins * 90.91) - (losses * 100)  # -110 odds = risk $110 to win $100
            roi = (profit / (len(disagreements) * 110)) * 100
            
            print(f"      Wins: {wins}, Losses: {losses}")
            print(f"      Estimated profit: ${profit:.2f}")
            print(f"      ROI: {roi:.1f}%")
        else:
            print(f"   ⚠️  Not profitable - only {disagreement_accuracy:.1%} correct when disagreeing")
    
    # =========================================================================
    # Disagreement Details
    # =========================================================================
    
    if len(disagreements) > 0:
        print("\n" + "="*80)
        print("DISAGREEMENT DETAILS (Where Model Differed from Betting Lines)")
        print("="*80)
        
        # Sort by confidence
        disagreements_sorted = disagreements.sort_values('confidence', ascending=False)
        
        print(f"\nTop {min(20, len(disagreements_sorted))} highest confidence disagreements:\n")
        print(f"{'Result':<8} {'Confidence':<12} {'Spread':<8} {'Teams'}")
        print("-" * 80)
        
        for _, game in disagreements_sorted.head(20).iterrows():
            result = "✓ WIN" if game['model_correct'] == 1 else "✗ LOSS"
            confidence = f"{game['confidence']:.1%}"
            spread_str = f"{game['point_spread']:.1f}" if pd.notna(game['point_spread']) else "N/A"
            
            model_pick = game['home_team'] if game['model_favorite'] == 'home' else game['away_team']
            betting_pick = game['home_team'] if game['betting_favorite'] == 'home' else game['away_team']
            
            matchup = f"{game['away_team']} @ {game['home_team']}"
            print(f"{result:<8} {confidence:<12} {spread_str:<8} {matchup}")
            print(f"         Model: {model_pick} | Betting: {betting_pick}")
            print(f"         Final: {game['away_score']}-{game['home_score']}")
            print()
    
    # =========================================================================
    # Save Analysis Results
    # =========================================================================
    
    # Initialize variables to avoid unbound errors
    betting_accuracy = None
    if len(betting_available) > 0:
        betting_accuracy = betting_available['betting_correct'].mean()
    
    disagreement_accuracy = None
    if len(disagreements) > 0:
        disagreement_accuracy = disagreements['model_correct'].mean()
    
    agreement_accuracy = None
    if len(agreements) > 0:
        agreement_accuracy = agreements['model_correct'].mean()
    
    analysis_results = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_predictions': len(merged),
        'model_accuracy': float(model_accuracy),
        'betting_line_accuracy': float(betting_accuracy) if betting_accuracy is not None else None,
        'games_with_betting_lines': len(betting_available),
        'agreements': len(agreements),
        'disagreements': len(disagreements),
        'disagreement_accuracy': float(disagreement_accuracy) if disagreement_accuracy is not None else None,
        'agreement_accuracy': float(agreement_accuracy) if agreement_accuracy is not None else None,
    }
    
    results_path = os.path.join(data_dir, 'Betting_Line_Analysis.json')
    
    # Append to existing log
    if os.path.exists(results_path):
        with open(results_path, 'r') as f:
            log = json.load(f)
        if not isinstance(log, list):
            log = [log]
        log.append(analysis_results)
    else:
        log = [analysis_results]
    
    with open(results_path, 'w') as f:
        json.dump(log, f, indent=2)
    
    print("\n" + "="*80)
    print(f"✓ Saved analysis to {results_path}")
    print("="*80)

if __name__ == "__main__":
    analyze_betting_line_performance()
