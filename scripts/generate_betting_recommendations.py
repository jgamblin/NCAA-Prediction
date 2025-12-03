#!/usr/bin/env python3
"""
Generate Betting Recommendations

Analyzes predictions and creates betting recommendations based on:
- Confidence levels
- Moneyline odds (implied probability)
- Value score (edge over the market)
"""

import sys
from pathlib import Path
from datetime import datetime, date
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection
from backend.repositories import PredictionsRepository, GamesRepository, BettingRepository


def american_odds_to_probability(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def calculate_value_score(confidence: float, implied_prob: float) -> float:
    """
    Calculate betting value score.
    Positive value = our confidence is higher than market odds
    """
    return confidence - implied_prob


def calculate_kelly_bet(
    confidence: float,
    odds: int,
    bankroll: float = 100.0,
    kelly_fraction: float = 0.25
) -> float:
    """
    Calculate recommended bet size using Kelly Criterion.
    Uses fractional Kelly (25%) for more conservative betting.
    
    Note: For simplicity, we use a flat $10 per game approach.
    """
    # Flat betting: $10 per game regardless of odds or confidence
    # This is a simple, conservative approach that's easy to manage
    return 10.0


def generate_betting_recommendations(
    min_confidence: float = 0.60,
    min_value: float = 0.05,
    max_recommendations: int = 20,
    daily_budget: float = 100.0,
    parlay_amount: float = 10.0
):
    """Generate betting recommendations from today's predictions."""
    
    db = get_db_connection()
    pred_repo = PredictionsRepository(db)
    games_repo = GamesRepository(db)
    betting_repo = BettingRepository(db)
    
    # Calculate available budget for individual bets (reserve parlay amount)
    available_budget = daily_budget - parlay_amount
    bet_amount = 10.0  # Flat $10 per bet
    max_bets = int(available_budget / bet_amount)
    
    # Limit to available budget
    if max_recommendations > max_bets:
        max_recommendations = max_bets
    
    print("=" * 80)
    print("GENERATING BETTING RECOMMENDATIONS")
    print("=" * 80)
    print(f"\nDaily Budget: ${daily_budget:.2f}")
    print(f"  - Parlay allocation: ${parlay_amount:.2f}")
    print(f"  - Individual bets allocation: ${available_budget:.2f} ({max_bets} bets max)")
    print(f"\nCriteria:")
    print(f"  - Minimum confidence: {min_confidence:.1%}")
    print(f"  - Minimum value edge: {min_value:.1%}")
    print(f"  - Maximum recommendations: {max_recommendations}")
    
    # Get today's games with predictions
    today = date.today()
    upcoming_query = """
        SELECT 
            p.*,
            g.home_team,
            g.away_team,
            g.home_moneyline,
            g.away_moneyline,
            g.date as game_date,
            g.game_status
        FROM predictions p
        JOIN games g ON p.game_id = g.game_id
        WHERE g.date >= ?
          AND g.game_status = 'Scheduled'
          AND p.predicted_winner IS NOT NULL
          AND p.confidence >= ?
        ORDER BY p.confidence DESC, g.date
    """
    
    upcoming_predictions = db.fetch_df(upcoming_query, (today, min_confidence))
    
    if upcoming_predictions.empty:
        print(f"\n⚠️  No predictions found meeting criteria for {today}")
        return
    
    print(f"\n📊 Analyzing {len(upcoming_predictions)} predictions...")
    
    recommendations = []
    
    for _, pred in upcoming_predictions.iterrows():
        # Determine which team we're betting on and their odds
        if pred['predicted_winner'] == pred['home_team']:
            bet_team = pred['home_team']
            odds = pred['home_moneyline']
        elif pred['predicted_winner'] == pred['away_team']:
            bet_team = pred['away_team']
            odds = pred['away_moneyline']
        else:
            continue  # Skip if predicted_winner doesn't match either team
        
        # Skip if no odds available
        if pd.isna(odds) or odds == 0:
            continue
        
        # Calculate value
        implied_prob = american_odds_to_probability(odds)
        value_score = calculate_value_score(pred['confidence'], implied_prob)
        
        # Only recommend if positive value
        if value_score < min_value:
            continue
        
        # Calculate recommended bet size
        bet_amount = calculate_kelly_bet(pred['confidence'], odds)
        
        recommendations.append({
            'game_id': pred['game_id'],
            'prediction_id': pred['id'],
            'bet_team': bet_team,
            'opponent': pred['away_team'] if bet_team == pred['home_team'] else pred['home_team'],
            'bet_amount': round(bet_amount, 2),
            'moneyline': int(odds),
            'confidence': float(pred['confidence']),
            'value_score': float(value_score),
            'implied_prob': float(implied_prob),
            'bet_type': 'moneyline',
            'strategy': 'value_betting',
            'game_date': pred['game_date']
        })
    
    # Deduplicate by game_id (keep best value for each game)
    seen_games = {}
    for bet in recommendations:
        game_id = bet['game_id']
        if game_id not in seen_games or bet['value_score'] > seen_games[game_id]['value_score']:
            seen_games[game_id] = bet
    
    # Convert back to list and sort by value score
    recommendations = list(seen_games.values())
    recommendations.sort(key=lambda x: x['value_score'], reverse=True)
    
    # Limit recommendations
    recommendations = recommendations[:max_recommendations]
    
    if not recommendations:
        print(f"\n⚠️  No betting opportunities found with +{min_value:.1%} edge")
        return
    
    print(f"\n✅ Found {len(recommendations)} betting opportunities\n")
    print("=" * 80)
    print("TOP BETTING RECOMMENDATIONS")
    print("=" * 80)
    
    total_amount = 0
    for i, bet in enumerate(recommendations, 1):
        print(f"\n#{i}. {bet['bet_team']} vs {bet['opponent']}")
        print(f"   Confidence: {bet['confidence']:.1%}")
        print(f"   Odds: {'+' if bet['moneyline'] > 0 else ''}{bet['moneyline']} (implied: {bet['implied_prob']:.1%})")
        print(f"   Edge: +{bet['value_score']:.1%}")
        print(f"   Recommended bet: ${bet['bet_amount']:.2f}")
        print(f"   Date: {bet['game_date']}")
        
        total_amount += bet['bet_amount']
    
    print(f"\n" + "=" * 80)
    print(f"Individual bets total: ${total_amount:.2f}")
    print(f"Parlay bet (reserved): ${parlay_amount:.2f}")
    print(f"TOTAL DAILY ALLOCATION: ${total_amount + parlay_amount:.2f} / ${daily_budget:.2f}")
    remaining = daily_budget - (total_amount + parlay_amount)
    print(f"Remaining budget: ${remaining:.2f}")
    print("=" * 80)
    
    # Insert into database
    print(f"\n💾 Saving recommendations to database...")
    inserted = 0
    
    for bet in recommendations:
        # Remove extra fields before inserting
        bet_data = {k: v for k, v in bet.items() 
                   if k not in ['opponent', 'implied_prob', 'game_date']}
        
        if betting_repo.insert_bet(bet_data):
            inserted += 1
    
    print(f"✅ Inserted {inserted} betting recommendations")
    
    print(f"\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate betting recommendations")
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.60,
        help='Minimum prediction confidence (default: 0.60)'
    )
    parser.add_argument(
        '--min-value',
        type=float,
        default=0.05,
        help='Minimum value edge over market (default: 0.05)'
    )
    parser.add_argument(
        '--max-recs',
        type=int,
        default=20,
        help='Maximum number of recommendations (default: 20)'
    )
    parser.add_argument(
        '--daily-budget',
        type=float,
        default=100.0,
        help='Total daily betting budget (default: 100.0)'
    )
    parser.add_argument(
        '--parlay-amount',
        type=float,
        default=10.0,
        help='Amount reserved for daily parlay (default: 10.0)'
    )
    
    args = parser.parse_args()
    
    generate_betting_recommendations(
        min_confidence=args.min_confidence,
        min_value=args.min_value,
        max_recommendations=args.max_recs,
        daily_budget=args.daily_budget,
        parlay_amount=args.parlay_amount
    )
