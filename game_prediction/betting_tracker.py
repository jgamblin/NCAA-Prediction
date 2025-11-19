#!/usr/bin/env python3
"""
Betting Tracker for NCAA Basketball Predictions
Tracks hypothetical $1 bets on teams with highest win probability that have moneylines.
"""

import pandas as pd
import os
from datetime import datetime


def american_odds_to_payout(odds, bet_amount=1.0):
    """
    Convert American odds to payout for a winning bet.
    
    Args:
        odds: American odds (e.g., -110, +150)
        bet_amount: Amount bet (default $1.00)
    
    Returns:
        Total return (bet amount + profit) for a win, or 0 for a loss
    """
    if odds is None or pd.isna(odds):
        return None
    
    try:
        odds = int(odds)
    except (ValueError, TypeError):
        return None
    
    if odds > 0:
        # Positive odds: profit = (bet_amount * odds) / 100
        profit = (bet_amount * odds) / 100.0
    else:
        # Negative odds: profit = bet_amount / (abs(odds) / 100)
        profit = bet_amount / (abs(odds) / 100.0)
    
    return bet_amount + profit


def calculate_bet_result(row, bet_amount=1.0):
    """
    Calculate result of a $1 bet on the predicted winner with a moneyline.
    
    Args:
        row: DataFrame row with prediction and game result
        bet_amount: Amount bet per game (default $1.00)
    
    Returns:
        dict with bet details and result
    """
    result = {
        'game_id': row.get('game_id'),
        'date': row.get('date'),
        'away_team': row.get('away_team'),
        'home_team': row.get('home_team'),
        'predicted_winner': row.get('predicted_winner'),
        'confidence': row.get('confidence'),
        'bet_amount': bet_amount,
        'moneyline': None,
        'actual_winner': None,
        'bet_won': None,
        'payout': 0.0,
        'profit': -bet_amount,
        'has_moneyline': False
    }
    
    # Determine who we're betting on (team with highest win probability)
    predicted_home_win = row.get('predicted_home_win', 0)
    home_team = row.get('home_team', '')
    away_team = row.get('away_team', '')
    
    # Get moneylines
    home_moneyline = row.get('home_moneyline')
    away_moneyline = row.get('away_moneyline')
    
    # Determine which team we bet on and their moneyline
    if predicted_home_win == 1:
        bet_team = home_team
        moneyline = home_moneyline
    else:
        bet_team = away_team
        moneyline = away_moneyline
    
    # Check if moneyline is available
    if moneyline is None or pd.isna(moneyline) or moneyline == '':
        # No moneyline available, skip this bet
        return result
    
    result['has_moneyline'] = True
    result['moneyline'] = moneyline
    
    # Determine actual winner
    home_score = row.get('home_score')
    away_score = row.get('away_score')
    
    if home_score is None or away_score is None or pd.isna(home_score) or pd.isna(away_score):
        # Game not completed yet
        return result
    
    if home_score > away_score:
        actual_winner = home_team
    elif away_score > home_score:
        actual_winner = away_team
    else:
        # Tie (very rare in basketball)
        actual_winner = 'TIE'
    
    result['actual_winner'] = actual_winner
    
    # Check if bet won
    if bet_team == actual_winner:
        result['bet_won'] = True
        payout = american_odds_to_payout(moneyline, bet_amount)
        if payout is not None:
            result['payout'] = payout
            result['profit'] = payout - bet_amount
    elif actual_winner == 'TIE':
        result['bet_won'] = None
        result['payout'] = bet_amount  # Push - get bet back
        result['profit'] = 0.0
    else:
        result['bet_won'] = False
        result['payout'] = 0.0
        result['profit'] = -bet_amount
    
    return result


def generate_betting_report():
    """
    Generate a betting report for all predictions with moneylines and completed games.
    
    Returns:
        DataFrame with betting results
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Load predictions from prediction log (historical predictions)
    pred_log_path = os.path.join(data_dir, 'prediction_log.csv')
    if not os.path.exists(pred_log_path):
        print("✗ No prediction log file found")
        return pd.DataFrame()
    
    predictions = pd.read_csv(pred_log_path)
    print(f"✓ Loaded {len(predictions)} predictions from log")
    
    # Load completed games to get results and moneylines
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    if not os.path.exists(completed_path):
        print("✗ No completed games file found")
        return pd.DataFrame()
    
    completed = pd.read_csv(completed_path)
    print(f"✓ Loaded {len(completed)} completed games")
    
    # Merge predictions with results
    predictions['game_id'] = predictions['game_id'].astype(str)
    completed['game_id'] = completed['game_id'].astype(str)
    
    # Check which columns are available in completed games
    completed_cols = ['game_id', 'home_score', 'away_score']
    if 'home_moneyline' in completed.columns:
        completed_cols.append('home_moneyline')
    if 'away_moneyline' in completed.columns:
        completed_cols.append('away_moneyline')
    
    # Merge to get scores and moneylines (if available)
    merged = predictions.merge(
        completed[completed_cols],
        on='game_id',
        how='left',
        suffixes=('', '_completed')
    )
    
    # Ensure moneyline columns exist
    for ml_col in ['home_moneyline', 'away_moneyline']:
        if ml_col not in merged.columns:
            merged[ml_col] = None
        elif f'{ml_col}_completed' in merged.columns:
            # Fill missing values from completed games
            merged[ml_col] = merged[ml_col].fillna(merged[f'{ml_col}_completed'])
    
    # Calculate bet results for each game
    bet_results = []
    for _, row in merged.iterrows():
        result = calculate_bet_result(row)
        if result['has_moneyline'] and result['actual_winner'] is not None:
            bet_results.append(result)
    
    if not bet_results:
        print("✗ No bets with moneylines and completed results found")
        return pd.DataFrame()
    
    bets_df = pd.DataFrame(bet_results)
    return bets_df


def generate_bets_markdown():
    """
    Generate the bets.md file with betting tracker results.
    """
    print("="*80)
    print("BETTING TRACKER - GENERATING BETS.MD")
    print("="*80)
    print()
    
    bets_df = generate_betting_report()
    
    if bets_df.empty:
        print("No betting data available yet")
        return
    
    # Calculate summary statistics
    total_bets = len(bets_df)
    total_wagered = bets_df['bet_amount'].sum()
    total_payout = bets_df['payout'].sum()
    total_profit = bets_df['profit'].sum()
    win_count = bets_df['bet_won'].sum()
    loss_count = (bets_df['bet_won'] == False).sum()
    win_rate = (win_count / total_bets * 100) if total_bets > 0 else 0
    roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
    
    # Generate markdown
    md_lines = [
        "# 🎲 NCAA Basketball Betting Tracker",
        "",
        f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This tracker shows hypothetical results of betting $1.00 on the team with the highest win probability (from our model) for games that have a moneyline on ESPN.",
        "",
        "---",
        "",
        "## 📊 Season Summary",
        "",
        f"- **Total Bets**: {total_bets}",
        f"- **Total Wagered**: ${total_wagered:.2f}",
        f"- **Total Payout**: ${total_payout:.2f}",
        f"- **Net Profit/Loss**: {'$' + f'{total_profit:.2f}' if total_profit >= 0 else '-$' + f'{abs(total_profit):.2f}'} {'🟢' if total_profit > 0 else '🔴' if total_profit < 0 else '⚪'}",
        f"- **Win Rate**: {win_rate:.1f}% ({win_count}W-{loss_count}L)",
        f"- **ROI**: {roi:.1f}%",
        "",
        "---",
        "",
        "## 📈 Betting Performance",
        "",
    ]
    
    # Add performance by confidence level
    if 'confidence' in bets_df.columns:
        bets_df['confidence_bucket'] = pd.cut(
            bets_df['confidence'], 
            bins=[0, 0.6, 0.7, 0.8, 0.9, 1.0],
            labels=['<60%', '60-70%', '70-80%', '80-90%', '90%+']
        )
        
        md_lines.extend([
            "### Performance by Confidence Level",
            "",
            "| Confidence | Bets | Win Rate | Net Profit | ROI |",
            "|------------|------|----------|------------|-----|"
        ])
        
        for bucket in ['<60%', '60-70%', '70-80%', '80-90%', '90%+']:
            bucket_df = bets_df[bets_df['confidence_bucket'] == bucket]
            if len(bucket_df) > 0:
                bucket_wins = bucket_df['bet_won'].sum()
                bucket_total = len(bucket_df)
                bucket_win_rate = (bucket_wins / bucket_total * 100) if bucket_total > 0 else 0
                bucket_profit = bucket_df['profit'].sum()
                bucket_wagered = bucket_df['bet_amount'].sum()
                bucket_roi = (bucket_profit / bucket_wagered * 100) if bucket_wagered > 0 else 0
                
                md_lines.append(
                    f"| {bucket} | {bucket_total} | {bucket_win_rate:.1f}% | "
                    f"${bucket_profit:.2f} | {bucket_roi:.1f}% |"
                )
        
        md_lines.extend(["", ""])
    
    # Recent bets table
    md_lines.extend([
        "## 📋 Recent Bets (Last 20)",
        "",
        "| Date | Result | Matchup | Bet On | ML | Confidence | Profit |",
        "|------|--------|---------|--------|----|-----------:|-------:|"
    ])
    
    # Show most recent bets first
    recent_bets = bets_df.sort_values('date', ascending=False).head(20)
    for _, bet in recent_bets.iterrows():
        result_icon = "✅" if bet['bet_won'] else "❌" if bet['bet_won'] == False else "⚪"
        matchup = f"{bet['away_team']} @ {bet['home_team']}"
        bet_on = bet['predicted_winner']
        moneyline = f"{int(bet['moneyline']):+d}" if pd.notna(bet['moneyline']) else "N/A"
        confidence = f"{bet['confidence']:.1%}"
        profit = f"${bet['profit']:.2f}" if bet['profit'] >= 0 else f"-${abs(bet['profit']):.2f}"
        
        md_lines.append(
            f"| {bet['date']} | {result_icon} | {matchup} | {bet_on} | {moneyline} | {confidence} | {profit} |"
        )
    
    md_lines.extend([
        "",
        "---",
        "",
        "## 📝 Notes",
        "",
        "- Each bet is $1.00 on the team with the highest predicted win probability",
        "- Only games with moneylines on ESPN are included",
        "- Moneylines shown are American odds (e.g., -110 means risk $110 to win $100)",
        "- ROI = (Total Profit / Total Wagered) × 100",
        "",
        "*Auto-generated by betting_tracker.py*"
    ])
    
    # Write to file
    output_path = os.path.join(os.path.dirname(__file__), '..', 'bets.md')
    with open(output_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    print(f"✓ Generated bets.md at {output_path}")
    print(f"  Total bets: {total_bets}")
    print(f"  Net profit: ${total_profit:.2f}")
    print(f"  Win rate: {win_rate:.1f}%")
    print(f"  ROI: {roi:.1f}%")


if __name__ == "__main__":
    generate_bets_markdown()
