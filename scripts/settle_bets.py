#!/usr/bin/env python3
"""
Settle Completed Bets

Automatically settles bets for games that have finished.
Should be run daily after game results are updated.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection
from backend.repositories import BettingRepository


def settle_completed_bets():
    """Settle all bets for completed games."""
    
    print("=" * 80)
    print("SETTLING COMPLETED BETS")
    print("=" * 80)
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    db = get_db_connection()
    betting_repo = BettingRepository(db)
    
    # Get pending settlements
    pending = betting_repo.get_pending_settlements()
    
    if not pending:
        print("✅ No bets need settlement - all caught up!")
        return
    
    print(f"📋 Found {len(pending)} bets to settle\n")
    
    settled_count = 0
    wins = 0
    losses = 0
    total_profit = 0.0
    
    for bet in pending:
        actual_winner = bet['actual_winner']
        bet_won = (bet['bet_team'] == actual_winner)
        
        # Calculate payout using American odds
        if bet_won:
            if bet['moneyline'] > 0:
                payout = bet['bet_amount'] * (1 + bet['moneyline'] / 100)
            else:
                payout = bet['bet_amount'] * (1 + 100 / abs(bet['moneyline']))
            profit = payout - bet['bet_amount']
        else:
            payout = 0.0
            profit = -bet['bet_amount']
        
        # Settle the bet
        if betting_repo.settle_bet(bet['id'], bet_won, actual_winner, payout):
            settled_count += 1
            total_profit += profit
            
            if bet_won:
                wins += 1
                print(f"✅ WIN  | {bet['bet_team']:20s} | ${profit:>7.2f} | {bet['away_team']:20s} @ {bet['home_team']:20s}")
            else:
                losses += 1
                print(f"❌ LOSS | {bet['bet_team']:20s} | ${profit:>7.2f} | {bet['away_team']:20s} @ {bet['home_team']:20s}")
    
    print("\n" + "=" * 80)
    print("SETTLEMENT SUMMARY")
    print("=" * 80)
    print(f"Total settled: {settled_count}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win rate: {(wins/settled_count*100):.1f}%" if settled_count > 0 else "Win rate: N/A")
    print(f"Net profit: ${total_profit:.2f}")
    print(f"ROI: {(total_profit/(settled_count*10)*100):.1f}%" if settled_count > 0 else "ROI: N/A")
    print("=" * 80)
    
    # Show overall stats
    summary = betting_repo.get_betting_summary()
    if summary and summary['total_bets'] > 0:
        print("\n" + "=" * 80)
        print("OVERALL BETTING STATISTICS")
        print("=" * 80)
        print(f"Total bets placed: {summary['total_bets']}")
        print(f"Record: {summary['wins']}W - {summary['losses']}L")
        print(f"Win rate: {summary['win_rate']*100:.1f}%")
        print(f"Total wagered: ${summary['total_wagered']:.2f}")
        print(f"Total profit: ${summary['total_profit']:.2f}")
        print(f"ROI: {summary['roi']*100:.1f}%")
        print(f"Biggest win: ${summary['biggest_win']:.2f}")
        print(f"Biggest loss: ${summary['biggest_loss']:.2f}")
        print("=" * 80)


if __name__ == "__main__":
    settle_completed_bets()
