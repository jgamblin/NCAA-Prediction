#!/usr/bin/env python3
"""
Parlay Betting Tracker

Generates daily 3-leg parlays based on top high-confidence predictions.
Strategy: Pick the 3 highest confidence predictions with real moneylines.
"""

import sys
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection
from backend.repositories import PredictionsRepository


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def calculate_parlay_odds(moneylines: List[int]) -> tuple:
    """
    Calculate combined parlay odds and potential payout.
    
    Returns:
        (combined_decimal_odds, potential_payout_for_$10)
    """
    combined_decimal = 1.0
    for ml in moneylines:
        combined_decimal *= american_to_decimal(ml)
    
    # $10 bet
    potential_payout = 10.0 * combined_decimal
    
    return combined_decimal, potential_payout


def generate_daily_parlay(prediction_date: Optional[date] = None) -> Optional[int]:
    """
    Generate a 3-leg parlay from today's top betting recommendations.
    
    Strategy:
    - Select top 3 bets by confidence from today's recommendations
    - Only use bets that haven't been settled yet
    - All legs must have real moneylines
    
    Returns:
        parlay_id if created, None if insufficient picks
    """
    if prediction_date is None:
        prediction_date = date.today()
    
    db = get_db_connection()
    
    # Get today's unsettled bets (top 3 by confidence)
    query = """
        SELECT 
            b.prediction_id,
            b.game_id,
            b.bet_team,
            b.moneyline,
            b.confidence,
            g.date as game_date
        FROM bets b
        INNER JOIN games g ON b.game_id = g.game_id
        WHERE g.date = ?
          AND b.settled_at IS NULL
          AND g.game_status = 'Scheduled'
        ORDER BY b.confidence DESC
        LIMIT 3
    """
    
    with db.transaction() as conn:
        result = conn.execute(query, (prediction_date,)).fetchall()
    
    if len(result) < 3:
        print(f"⚠️  Insufficient picks for parlay: only {len(result)} eligible games")
        return None
    
    # Check if we already have a parlay for this date
    with db.transaction() as conn:
        existing = conn.execute("""
            SELECT id FROM parlays WHERE parlay_date = ?
        """, (prediction_date,)).fetchone()
    
    if existing:
        print(f"⚠️  Parlay already exists for {prediction_date} (ID: {existing[0]})")
        return existing[0]
    
    # Extract legs
    legs = []
    moneylines = []
    for row in result:
        legs.append({
            'prediction_id': row[0],
            'game_id': row[1],
            'bet_team': row[2],
            'moneyline': row[3],
            'confidence': row[4]
        })
        moneylines.append(row[3])
    
    # Calculate parlay odds
    combined_odds, potential_payout = calculate_parlay_odds(moneylines)
    
    # Insert parlay
    with db.transaction() as conn:
        # Insert parlay record
        parlay_query = """
            INSERT INTO parlays 
            (parlay_date, bet_amount, num_legs, combined_odds, potential_payout, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        conn.execute(parlay_query, (
            prediction_date,
            10.0,
            3,
            combined_odds,
            potential_payout,
            'parlay_high_confidence'
        ))
        
        # Get the parlay_id
        if db.use_duckdb:
            parlay_id = conn.execute("SELECT currval('parlays_seq')").fetchone()[0]
        else:
            parlay_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Insert legs
        for i, leg in enumerate(legs, 1):
            leg_query = """
                INSERT INTO parlay_legs
                (parlay_id, game_id, prediction_id, bet_team, moneyline, confidence, leg_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(leg_query, (
                parlay_id,
                leg['game_id'],
                leg['prediction_id'],
                leg['bet_team'],
                leg['moneyline'],
                leg['confidence'],
                i
            ))
    
    print(f"✓ Created 3-leg parlay (ID: {parlay_id})")
    print(f"  Combined odds: {combined_odds:.2f}")
    print(f"  Potential payout: ${potential_payout:.2f}")
    print(f"  Legs:")
    for i, leg in enumerate(legs, 1):
        odds_str = f"{leg['moneyline']:+d}" if leg['moneyline'] < 0 else f"+{leg['moneyline']}"
        print(f"    {i}. {leg['bet_team']} ({odds_str}) - {leg['confidence']:.1%} confidence")
    
    return parlay_id


def settle_completed_parlays() -> int:
    """
    Settle parlays where all legs have completed games.
    A parlay wins only if ALL legs win.
    
    Returns:
        Number of parlays settled
    """
    db = get_db_connection()
    
    # Get unsettled parlays where all legs have completed
    query = """
        SELECT 
            p.id,
            p.parlay_date,
            p.bet_amount,
            p.potential_payout,
            p.num_legs
        FROM parlays p
        WHERE p.settled_at IS NULL
          AND NOT EXISTS (
              SELECT 1 
              FROM parlay_legs pl
              INNER JOIN games g ON pl.game_id = g.game_id
              WHERE pl.parlay_id = p.id
                AND g.game_status != 'Final'
          )
    """
    
    with db.transaction() as conn:
        unsettled = conn.execute(query).fetchall()
    
    if not unsettled:
        print("✅ No parlays need settlement - all caught up!")
        return 0
    
    print(f"📋 Found {len(unsettled)} parlay(s) to settle\n")
    
    settled_count = 0
    wins = 0
    losses = 0
    
    for parlay_row in unsettled:
        parlay_id = parlay_row[0]
        parlay_date = parlay_row[1]
        bet_amount = parlay_row[2]
        potential_payout = parlay_row[3]
        num_legs = parlay_row[4]
        
        # Get all legs with their results
        leg_query = """
            SELECT 
                pl.id,
                pl.bet_team,
                pl.moneyline,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                CASE 
                    WHEN g.home_score > g.away_score THEN g.home_team
                    WHEN g.away_score > g.home_score THEN g.away_team
                    ELSE NULL
                END as actual_winner
            FROM parlay_legs pl
            INNER JOIN games g ON pl.game_id = g.game_id
            WHERE pl.parlay_id = ?
            ORDER BY pl.leg_number
        """
        
        with db.transaction() as conn:
            legs = conn.execute(leg_query, (parlay_id,)).fetchall()
        
        # Check if all legs won
        all_won = True
        leg_results = []
        
        for leg in legs:
            leg_id = leg[0]
            bet_team = leg[1]
            actual_winner = leg[7]
            
            leg_won = (bet_team == actual_winner)
            leg_results.append(leg_won)
            
            if not leg_won:
                all_won = False
            
            # Update leg result
            with db.transaction() as conn:
                conn.execute("""
                    UPDATE parlay_legs
                    SET leg_won = ?, actual_winner = ?
                    WHERE id = ?
                """, (leg_won, actual_winner, leg_id))
        
        # Calculate payout
        if all_won:
            actual_payout = potential_payout
            profit = actual_payout - bet_amount
            wins += 1
            result_emoji = "✅ WIN "
        else:
            actual_payout = 0.0
            profit = -bet_amount
            losses += 1
            result_emoji = "❌ LOSS"
        
        # Update parlay
        with db.transaction() as conn:
            conn.execute("""
                UPDATE parlays
                SET parlay_won = ?,
                    actual_payout = ?,
                    profit = ?,
                    settled_at = now()
                WHERE id = ?
            """, (all_won, actual_payout, profit, parlay_id))
        
        # Print result
        print(f"{result_emoji} | {num_legs}-leg Parlay | ${profit:7.2f} | {parlay_date}")
        for i, leg in enumerate(legs):
            bet_team = leg[1]
            actual_winner = leg[7]
            won = leg_results[i]
            status = "✓" if won else "✗"
            print(f"    {status} {bet_team}")
        print()
        
        settled_count += 1
    
    print("="*80)
    print("PARLAY SETTLEMENT SUMMARY")
    print("="*80)
    print(f"Total settled: {settled_count}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    if settled_count > 0:
        print(f"Win rate: {wins/settled_count*100:.1f}%")
    print("="*80)
    
    return settled_count


def get_parlay_stats() -> Dict:
    """Get overall parlay betting statistics."""
    db = get_db_connection()
    
    query = """
        SELECT 
            COUNT(*) as total_parlays,
            SUM(CASE WHEN parlay_won = true THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN parlay_won = false THEN 1 ELSE 0 END) as losses,
            SUM(bet_amount) as total_wagered,
            SUM(profit) as total_profit,
            MAX(profit) as biggest_win,
            MIN(profit) as biggest_loss
        FROM parlays
        WHERE settled_at IS NOT NULL
    """
    
    with db.transaction() as conn:
        result = conn.execute(query).fetchone()
    
    if not result or result[0] == 0:
        return None
    
    total_parlays = result[0]
    wins = result[1] or 0
    losses = result[2] or 0
    total_wagered = result[3] or 0.0
    total_profit = result[4] or 0.0
    biggest_win = result[5] or 0.0
    biggest_loss = result[6] or 0.0
    
    win_rate = wins / total_parlays if total_parlays > 0 else 0.0
    roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0.0
    
    return {
        'total_parlays': total_parlays,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_wagered': total_wagered,
        'total_profit': total_profit,
        'roi': roi,
        'biggest_win': biggest_win,
        'biggest_loss': biggest_loss
    }


def main():
    """Main function for parlay tracking."""
    print("="*80)
    print("PARLAY BETTING TRACKER")
    print("="*80)
    print("\nDaily Budget: $100.00")
    print("  - Parlay: $10.00 (this tracker)")
    print("  - Individual bets: $90.00 (9 bets max)")
    print()
    
    # Settle any completed parlays first
    print("Step 1: Settling completed parlays")
    print("-"*80)
    settle_completed_parlays()
    
    print()
    print("Step 2: Generating today's parlay")
    print("-"*80)
    generate_daily_parlay()
    
    # Show overall stats
    print()
    print("="*80)
    print("OVERALL PARLAY STATISTICS")
    print("="*80)
    stats = get_parlay_stats()
    if stats:
        print(f"Total parlays placed: {stats['total_parlays']}")
        print(f"Record: {stats['wins']}W - {stats['losses']}L")
        print(f"Win rate: {stats['win_rate']*100:.1f}%")
        print(f"Total wagered: ${stats['total_wagered']:.2f}")
        print(f"Total profit: ${stats['total_profit']:.2f}")
        print(f"ROI: {stats['roi']:.1f}%")
        print(f"Biggest win: ${stats['biggest_win']:.2f}")
        print(f"Biggest loss: ${stats['biggest_loss']:.2f}")
    else:
        print("No parlays settled yet")
    print("="*80)


if __name__ == "__main__":
    main()
