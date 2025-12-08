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


def calculate_value_score(confidence: float, implied_prob: float, odds: int = None) -> float:
    """
    Calculate betting value score with adjustments for underdogs.
    Positive value = our confidence is higher than market odds
    
    Applies penalties to underdogs since model is less accurate on them.
    Model shows 25% win rate on underdogs vs 60% on favorites.
    """
    # Base edge
    edge = confidence - implied_prob
    
    # Apply adjustment based on odds type
    if odds is not None:
        if odds > 0:  # Underdog
            # Model is severely overconfident on underdogs (72% predicted, 25% actual)
            # Apply heavy penalty to reduce underdog appeal
            edge = edge * 0.5  # Cut value score in half for underdogs
        else:  # Favorite
            # Model is more accurate on favorites (86% predicted, 60% actual)
            # Slight bonus to encourage favorite bets
            edge = edge * 1.1
    
    return edge


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
    min_confidence: float = 0.80,  # Raised from 0.75 - VERY conservative after analysis
    min_value: float = 0.15,       # Keep at 0.15 (formula change compensates)
    max_recommendations: int = 5,  # Reduced from 10 - much fewer bets
    daily_budget: float = 100.0,
    parlay_amount: float = 10.0
):
    """Generate betting recommendations from today's predictions."""
    
    db = get_db_connection()
    pred_repo = PredictionsRepository(db)
    games_repo = GamesRepository(db)
    betting_repo = BettingRepository(db)
    
    # Check how much we've already spent today
    today = date.today()
    spent_query = """
        SELECT COALESCE(SUM(bet_amount), 0) as total_spent
        FROM bets b
        JOIN games g ON b.game_id = g.game_id
        WHERE g.date = ?
    """
    today_spent = db.fetch_df(spent_query, (today,))['total_spent'].iloc[0]
    
    # Check if parlay exists for today
    parlay_query = """
        SELECT COALESCE(SUM(bet_amount), 0) as parlay_spent
        FROM parlays
        WHERE parlay_date = ?
    """
    parlay_spent = db.fetch_df(parlay_query, (today,))['parlay_spent'].iloc[0]
    
    total_spent = today_spent + parlay_spent
    remaining_budget = daily_budget - total_spent
    
    if remaining_budget <= 0:
        print(f"\n⚠️  Daily budget exhausted: ${total_spent:.2f} / ${daily_budget:.2f}")
        print(f"   No more bets today!")
        return
    
    # Check recent performance - stop betting if on a bad streak
    recent_bets_query = """
        SELECT 
            bet_won,
            (payout - bet_amount) as profit
        FROM bets
        WHERE bet_won IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """
    recent_bets = db.fetch_df(recent_bets_query)
    
    if len(recent_bets) >= 5:
        # Calculate recent win rate
        recent_win_rate = recent_bets['bet_won'].iloc[:5].mean()
        recent_profit = recent_bets['profit'].iloc[:5].sum()
        
        # Stop betting if recent performance is terrible
        if recent_win_rate < 0.30 and recent_profit < -30:
            print(f"\n⚠️  Recent performance is poor:")
            print(f"   Last 5 bets: {recent_win_rate*100:.0f}% win rate")
            print(f"   Last 5 profit: ${recent_profit:.2f}")
            print(f"   🛑 PAUSING BETTING until performance improves")
            print(f"   (Performance protection triggered)")
            return
        
        # Warning if on a cold streak
        if recent_win_rate < 0.40:
            print(f"\n⚠️  Warning: Recent win rate is {recent_win_rate*100:.0f}%")
            print(f"   Proceeding with reduced selectivity and higher standards")
    
    # Calculate available budget for individual bets
    bet_amount = 10.0  # Flat $10 per bet
    max_bets = int(remaining_budget / bet_amount)
    
    # Limit to available budget
    if max_recommendations > max_bets:
        max_recommendations = max_bets
    
    print("=" * 80)
    print("GENERATING BETTING RECOMMENDATIONS")
    print("=" * 80)
    print(f"\nDaily Budget: ${daily_budget:.2f}")
    print(f"  - Already spent: ${total_spent:.2f}")
    print(f"    • Individual bets: ${today_spent:.2f}")
    print(f"    • Parlay: ${parlay_spent:.2f}")
    print(f"  - Remaining: ${remaining_budget:.2f} ({max_bets} bets max @ $10 each)")
    print(f"\nCriteria:")
    print(f"  - Minimum confidence: {min_confidence:.1%}")
    print(f"  - Minimum value edge: {min_value:.1%}")
    print(f"  - Maximum recommendations: {max_recommendations}")
    print(f"  - Underdog filter: Max +150 odds, 90%+ confidence required")
    print(f"  - Heavy favorite filter: No worse than -250")
    
    # Get today's games with predictions (excluding games we already bet on)
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
        LEFT JOIN bets b ON p.game_id = b.game_id
        WHERE g.date >= ?
          AND g.game_status = 'Scheduled'
          AND p.predicted_winner IS NOT NULL
          AND p.confidence >= ?
          AND b.id IS NULL
        ORDER BY p.confidence DESC, g.date
    """
    
    upcoming_predictions = db.fetch_df(upcoming_query, (today, min_confidence))
    
    if upcoming_predictions.empty:
        print(f"\n⚠️  No predictions found meeting criteria for {today}")
        return
    
    print(f"\n📊 Analyzing {len(upcoming_predictions)} predictions...")
    
    recommendations = []
    filtered_stats = {
        'big_underdogs': 0,
        'low_conf_underdogs': 0,
        'heavy_favorites': 0,
        'no_value': 0
    }
    
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
        
        # ===== UNDERDOG FILTER =====
        # Skip big underdogs (odds > +150)
        # Analysis showed 12 underdog bets with only 25% win rate cost us $28.60
        if odds > 150:
            filtered_stats['big_underdogs'] += 1
            continue
        
        # For small underdogs (+1 to +150), require much higher confidence
        # Model is overconfident on underdogs (72% predicted, 25% actual)
        if odds > 0 and pred['confidence'] < 0.90:
            filtered_stats['low_conf_underdogs'] += 1
            continue
        
        # For favorites, skip heavy favorites (worse than -250)
        # These provide minimal value and high risk
        if odds < -250:
            filtered_stats['heavy_favorites'] += 1
            continue
        # ===== END UNDERDOG FILTER =====
        
        # Calculate value with new formula (includes odds-based adjustments)
        implied_prob = american_odds_to_probability(odds)
        value_score = calculate_value_score(pred['confidence'], implied_prob, odds)
        
        # Only recommend if positive value
        if value_score < min_value:
            filtered_stats['no_value'] += 1
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
        print(f"\n📊 FILTERING SUMMARY:")
        print(f"  Total candidates analyzed: {len(upcoming_predictions)}")
        print(f"  Filtered out - Big underdogs (>+150): {filtered_stats['big_underdogs']}")
        print(f"  Filtered out - Low confidence underdogs: {filtered_stats['low_conf_underdogs']}")
        print(f"  Filtered out - Heavy favorites (<-250): {filtered_stats['heavy_favorites']}")
        print(f"  Filtered out - Insufficient value: {filtered_stats['no_value']}")
        print(f"  ✅ Passed all filters: 0")
        return
    
    print(f"\n✅ Found {len(recommendations)} betting opportunities\n")
    print(f"📊 FILTERING SUMMARY:")
    print(f"  Total candidates analyzed: {len(upcoming_predictions)}")
    print(f"  Filtered out - Big underdogs (>+150): {filtered_stats['big_underdogs']}")
    print(f"  Filtered out - Low confidence underdogs: {filtered_stats['low_conf_underdogs']}")
    print(f"  Filtered out - Heavy favorites (<-250): {filtered_stats['heavy_favorites']}")
    print(f"  Filtered out - Insufficient value: {filtered_stats['no_value']}")
    print(f"  ✅ Passed all filters: {len(recommendations)}")
    print()
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
        default=0.80,
        help='Minimum prediction confidence (default: 0.80 - VERY CONSERVATIVE)'
    )
    parser.add_argument(
        '--min-value',
        type=float,
        default=0.15,
        help='Minimum value edge over market (default: 0.15 - CONSERVATIVE)'
    )
    parser.add_argument(
        '--max-recs',
        type=int,
        default=5,
        help='Maximum number of recommendations (default: 5 - VERY CONSERVATIVE)'
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
