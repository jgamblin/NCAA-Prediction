#!/usr/bin/env python3
"""
Betting Tracker for NCAA Basketball Predictions
Tracks hypothetical $1 bets on teams with highest win probability that have moneylines.
"""

import pandas as pd
import os
from datetime import datetime, date
import unicodedata


def canonicalize_team_name(name: str):
    """Light normalization for team name comparison.
    - Strip accents
    - Collapse double spaces
    - Remove trailing single mascot token to match shorter prediction names
    """
    if not isinstance(name, str):
        return name
    # Strip accents
    base = unicodedata.normalize('NFKD', name)
    base = ''.join(ch for ch in base if not unicodedata.combining(ch))
    base = base.replace('  ', ' ').strip()
    mascots = {
        'Spartans','Shockers','Panthers','Bulldogs','Boilermakers','Aggies','Mountaineers','Jaguars','Chippewas',
        'Leopards','Bison','Braves','Camels','Mustangs','Lions','Wildcats','Cardinals','Tide'
    }
    parts = base.split()
    if len(parts) > 2 and parts[-1] in mascots:
        return ' '.join(parts[:-1])
    return base

def derive_season_label(date_str: str):
    """Derive NCAA season label (e.g., 2025-26) from a YYYY-MM-DD date.
    Season considered starting July 1 of start year; months < 7 belong to previous start year.
    """
    try:
        year, month, _ = map(int, date_str.split('-'))
    except Exception:
        return 'Unknown'
    if month >= 7:
        start_year = year
    else:
        start_year = year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


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


def is_bettable_moneyline(moneyline):
    """
    Check if a moneyline represents a bettable game.
    Extreme moneylines (< -1000) are considered unbettable.
    
    Args:
        moneyline: American odds (e.g., -110, +150)
    
    Returns:
        True if moneyline is bettable, False otherwise
    """
    if moneyline is None or pd.isna(moneyline):
        return False
    
    try:
        moneyline = int(moneyline)
    except (ValueError, TypeError):
        return False
    
    # Moneylines more extreme than -1000 are considered unbettable
    # (e.g., -3000, -100000 are too extreme to be practical bets)
    if moneyline < -1000:
        return False
    
    return True


def calculate_value_score(confidence, moneyline):
    """
    Calculate a value score for a bet combining confidence and moneyline value.
    Higher score = better value bet.
    
    Args:
        confidence: Model's predicted win probability (0.0 to 1.0)
        moneyline: American odds (e.g., -110, +150)
    
    Returns:
        Value score (higher is better), or None if invalid inputs
    """
    if confidence is None or pd.isna(confidence) or moneyline is None or pd.isna(moneyline):
        return None
    
    if not is_bettable_moneyline(moneyline):
        return None
    
    try:
        moneyline = int(moneyline)
        confidence = float(confidence)
    except (ValueError, TypeError):
        return None
    
    # Calculate potential profit per dollar bet
    if moneyline > 0:
        potential_profit = moneyline / 100.0
    else:
        potential_profit = 100.0 / abs(moneyline)
    
    # Value score = expected value = (confidence * potential_profit) - ((1 - confidence) * 1)
    # This represents the expected profit per dollar wagered
    value_score = (confidence * (1 + potential_profit)) - 1.0
    
    return value_score


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
    # Original predicted home/away labels
    home_team = row.get('home_team', '')
    away_team = row.get('away_team', '')
    scoreboard_home = row.get('home_team_completed')
    scoreboard_away = row.get('away_team_completed')
    
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
    
    # Check if moneyline is available and bettable
    if moneyline is None or pd.isna(moneyline) or moneyline == '' or not is_bettable_moneyline(moneyline):
        # No moneyline available or unbettable (e.g., -100000), skip this bet
        return result
    
    result['has_moneyline'] = True
    result['moneyline'] = moneyline
    
    # Determine actual winner
    home_score = row.get('home_score')
    away_score = row.get('away_score')
    
    if home_score is None or away_score is None or pd.isna(home_score) or pd.isna(away_score):
        # Game not completed yet
        return result
    
    # Handle potential home/away label mismatches between prediction log and completed games.
    # Previous logic flipped scores, which inverted many heavy favorite wins into losses.
    if (
        scoreboard_home is not None and pd.notna(scoreboard_home) and
        canonicalize_team_name(scoreboard_home) != canonicalize_team_name(home_team)
    ):
        # Use the scoreboard team names to determine winner, then map back to predicted naming
        if home_score > away_score:
            raw_winner = scoreboard_home
        elif away_score > home_score:
            raw_winner = scoreboard_away
        else:
            raw_winner = 'TIE'

        def map_team(raw, pred_home, pred_away):
            if not isinstance(raw, str):
                return raw
            raw_can = canonicalize_team_name(raw)
            home_can = canonicalize_team_name(pred_home)
            away_can = canonicalize_team_name(pred_away)
            if home_can and home_can in raw_can:
                return pred_home
            if away_can and away_can in raw_can:
                return pred_away
            return raw

        mapped_winner = map_team(raw_winner, home_team, away_team)
        actual_winner = mapped_winner
    else:
        # Normal case: names already aligned
        if home_score > away_score:
            actual_winner = home_team
        elif away_score > home_score:
            actual_winner = away_team
        else:
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
    
    # Filter out backfilled synthetic predictions - only use real predictions going forward
    if 'source' in predictions.columns:
        real_predictions = predictions[predictions['source'] != 'backfill']
        print(f"✓ Filtered to {len(real_predictions)} real predictions (excluded {len(predictions) - len(real_predictions)} synthetic backfills)")
        predictions = real_predictions
    
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
    # Include home/away team names from completed games so we can detect mismatches
    completed_cols = ['game_id', 'home_score', 'away_score', 'home_team', 'away_team']
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
    mismatch_count = 0
    for _, row in merged.iterrows():
        # Detect mismatch only if canonical forms differ and neither contains the other (reduce noise)
        if 'home_team_completed' in row and 'home_team' in row:
            comp = row['home_team_completed']
            pred = row['home_team']
            if pd.notna(comp) and pd.notna(pred):
                comp_can = canonicalize_team_name(comp)
                pred_can = canonicalize_team_name(pred)
                if comp_can != pred_can and pred_can not in comp_can and comp_can not in pred_can:
                    mismatch_count += 1
        result = calculate_bet_result(row)
        if result['has_moneyline'] and result['actual_winner'] is not None:
            bet_results.append(result)
    
    if not bet_results:
        print("✗ No bets with moneylines and completed results found")
        return pd.DataFrame()
    
    bets_df = pd.DataFrame(bet_results)
    
    # Determine real odds directly from moneyline presence & bettability instead of relying on completed.has_real_odds
    # This avoids losing tracking if the scraper fails to populate has_real_odds in Completed_Games.csv
    real_odds_mask = []
    for _, bet in bets_df.iterrows():
        ml = bet.get('moneyline')
        real_odds_mask.append(ml is not None and pd.notna(ml) and ml != '' and is_bettable_moneyline(ml))
    real_bets = bets_df[real_odds_mask].copy()
    if real_bets.empty:
        print("✗ No completed bets with usable moneylines found (moneyline missing or unbettable)")
        return pd.DataFrame()
    print(f"✓ Retained {len(real_bets)} completed bets with usable moneylines")
    if mismatch_count > 0:
        print(f"⚠️ Detected {mismatch_count} home/away label mismatches between predictions and completed games; using scoreboard teams for actual results.")
    bets_df = real_bets
    
    # Don't filter to one bet per day anymore - we'll handle that in the markdown generation
    # We want to track both strategies: safest bet AND best value bet
    return bets_df


def get_todays_bets(today_preds):
    """
    Get today's safest bet and best value bet from predictions.
    
    Args:
        today_preds: DataFrame with today's predictions
    
    Returns:
        dict with 'safest_bet' and 'value_bet' (or None if not found)
    """
    result = {
        'safest_bet': None,
        'value_bet': None
    }
    
    if 'has_real_odds' not in today_preds.columns or 'date' not in today_preds.columns:
        return result

    # Restrict strictly to games scheduled for *today's* date in local time
    try:
        today_str = date.today().strftime('%Y-%m-%d')
        preds_today = today_preds[today_preds['date'] == today_str].copy()
    except Exception:
        return result

    # Filter to games with real odds
    with_real_ml = preds_today[preds_today['has_real_odds'] == True].copy()
    
    if len(with_real_ml) == 0:
        return result
    
    # Add bettable moneyline filter
    def is_row_bettable(row):
        if row['predicted_home_win'] == 1:
            ml = row.get('home_moneyline')
        else:
            ml = row.get('away_moneyline')
        return is_bettable_moneyline(ml)
    
    # Filter to only bettable games
    bettable = with_real_ml[with_real_ml.apply(is_row_bettable, axis=1)].copy()
    
    if len(bettable) == 0:
        return result
    
    # Safest bet: highest confidence
    result['safest_bet'] = bettable.sort_values('confidence', ascending=False).iloc[0]
    
    # Best value bet: calculate value scores
    def calc_value(row):
        if row['predicted_home_win'] == 1:
            ml = row.get('home_moneyline')
        else:
            ml = row.get('away_moneyline')
        return calculate_value_score(row['confidence'], ml)
    
    bettable['value_score'] = bettable.apply(calc_value, axis=1)
    bettable_with_scores = bettable[bettable['value_score'].notna()].copy()
    
    if len(bettable_with_scores) > 0:
        result['value_bet'] = bettable_with_scores.sort_values('value_score', ascending=False).iloc[0]
    
    return result


def separate_bet_strategies(bets_df, predictions_log):
    """
    Separate bets into two strategies: safest (highest confidence) and best value.
    For each date, determines which bet would have been selected by each strategy.
    
    Args:
        bets_df: DataFrame with all bets
        predictions_log: DataFrame with all predictions (to calculate value scores)
    
    Returns:
        tuple: (safest_bets_df, value_bets_df)
    """
    if bets_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    safest_bets = []
    value_bets = []
    
    # Group by date
    for date, date_games in bets_df.groupby('date'):
        # Safest bet: highest confidence
        safest = date_games.sort_values('confidence', ascending=False).iloc[0]
        safest_bets.append(safest)
        
        # Best value bet: calculate value scores
        date_games = date_games.copy()
        date_games['value_score'] = date_games.apply(
            lambda row: calculate_value_score(row['confidence'], row['moneyline']),
            axis=1
        )
        date_games_with_scores = date_games[date_games['value_score'].notna()].copy()
        
        if len(date_games_with_scores) > 0:
            value = date_games_with_scores.sort_values('value_score', ascending=False).iloc[0]
            value_bets.append(value)
    
    safest_df = pd.DataFrame(safest_bets) if safest_bets else pd.DataFrame()
    value_df = pd.DataFrame(value_bets) if value_bets else pd.DataFrame()
    
    return safest_df, value_df


def generate_fresh_start_markdown():
    """
    Generate bets.md when starting fresh with no historical data.
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    today_pred_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
    
    md_lines = [
        "# 🎲 NCAA Basketball Betting Tracker",
        "",
        f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Tracking Started**: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "This tracker shows hypothetical results of betting $1.00 on the team with the highest win probability (from our model) **using real moneylines from ESPN**.",
        "",
        "> **✅ Real Odds Only**: Only games with actual ESPN moneylines are tracked. Games showing \"OFF\" or without real betting lines are automatically excluded. Moneylines worse than -1000 are also excluded as unbettable. Starting fresh with today's game!",
        "",
        "---",
        "",
        "## 📊 Season Summary",
        "",
        "**No bets placed yet** - Track starts with today's game!",
        "",
        "Check back tomorrow to see results.",
        "",
        "---",
        "",
    ]
    
    # Add today's best bets section
    if os.path.exists(today_pred_path):
        try:
            today_preds = pd.read_csv(today_pred_path)
            todays_bets = get_todays_bets(today_preds)
            
            safest_bet = todays_bets['safest_bet']
            value_bet = todays_bets['value_bet']
            
            if safest_bet is not None:
                # Determine which team we're betting on and their moneyline
                if safest_bet['predicted_home_win'] == 1:
                    bet_team = safest_bet['home_team']
                    opponent = safest_bet['away_team']
                    moneyline = safest_bet['home_moneyline']
                    location = 'vs'
                else:
                    bet_team = safest_bet['away_team']
                    opponent = safest_bet['home_team']
                    moneyline = safest_bet['away_moneyline']
                    location = '@'
                
                md_lines.extend([
                    "## 🎯 Today's Safest Bet",
                    "",
                    f"**{bet_team}** {location} **{opponent}**",
                    "",
                    f"- **Confidence**: {safest_bet['confidence']:.1%}",
                    f"- **Moneyline**: {int(moneyline):+d}",
                    f"- **Potential Profit**: ${american_odds_to_payout(moneyline, 1.0) - 1.0:.2f}",
                    "",
                    "✅ *Real ESPN odds - betting line is live!*",
                    "",
                    "---",
                    "",
                ])
            
            if value_bet is not None:
                # Determine which team we're betting on and their moneyline for value bet
                if value_bet['predicted_home_win'] == 1:
                    bet_team = value_bet['home_team']
                    opponent = value_bet['away_team']
                    moneyline = value_bet['home_moneyline']
                    location = 'vs'
                else:
                    bet_team = value_bet['away_team']
                    opponent = value_bet['home_team']
                    moneyline = value_bet['away_moneyline']
                    location = '@'
                
                value_score = calculate_value_score(value_bet['confidence'], moneyline)
                
                md_lines.extend([
                    "## 💎 Today's Best Value Bet",
                    "",
                    f"**{bet_team}** {location} **{opponent}**",
                    "",
                    f"- **Confidence**: {value_bet['confidence']:.1%}",
                    f"- **Moneyline**: {int(moneyline):+d}",
                    f"- **Potential Profit**: ${american_odds_to_payout(moneyline, 1.0) - 1.0:.2f}",
                    f"- **Value Score**: {value_score:.3f}",
                    "",
                    "✅ *Best combination of high probability and favorable odds!*",
                    "",
                    "---",
                    "",
                ])
            
            if safest_bet is None and value_bet is None:
                # No games with real odds today
                md_lines.extend([
                    "## 🎯 Today's Best Bets",
                    "",
                    "**No games with bettable ESPN moneylines available today**",
                    "",
                    "Games may have moneylines set to \"OFF\", be more extreme than -1000, or not be available for betting.",
                    "Check back tomorrow for the next bet opportunity!",
                    "",
                    "---",
                    "",
                ])
        except Exception as e:
            print(f"⚠️ Could not add today's best bets: {e}")
    
    md_lines.extend([
        "## 📝 Notes",
        "",
        "### Betting Strategy",
        "- **Safest Bet**: The game with the highest predicted win probability",
        "- **Best Value Bet**: The game with the best combination of high probability and favorable odds",
        "- Each bet is $1.00 on the team with the highest win probability",
        "- **Only games with real ESPN moneylines** are tracked",
        "- **Moneylines more extreme than -1000 are excluded** as unbettable",
        "- Moneylines shown are American odds (e.g., -110 means risk $110 to win $100)",
        "- Value Score represents expected profit per dollar wagered",
        "",
        "### Important Disclaimers",
        "- **Real moneylines from ESPN API** extracted from official scoreboard endpoint",
        "- Games showing \"OFF\" for moneyline are excluded (no betting available)",
        "- Moneylines < -1000 (e.g., -3000, -100000) are excluded as unbettable",
        "- **Tracking started fresh** - no historical synthetic data",
        "- **Not all games have betting lines** - especially games involving small schools or lower-tier matchups",
        "- This tracker is for **educational/entertainment purposes** to demonstrate prediction accuracy",
        "",
        "*Auto-generated by betting_tracker.py*"
    ])
    
    # Write to file
    output_path = os.path.join(os.path.dirname(__file__), '..', 'bets.md')
    with open(output_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    print(f"✓ Generated bets.md at {output_path}")
    print(f"  Starting fresh - check back tomorrow for first bet result!")


def generate_bets_markdown():
    """
    Generate the bets.md file with betting tracker results.
    """
    print("="*80)
    print("BETTING TRACKER - GENERATING BETS.MD")
    print("="*80)
    print()
    
    bets_df = generate_betting_report()
    
    # Handle case with no historical bets (starting fresh)
    if bets_df.empty:
        print("No betting history yet - starting fresh with today's game")
        # Still generate the file with today's best bet
        generate_fresh_start_markdown()
        return
    
    # Separate bets into two strategies
    safest_bets_df, value_bets_df = separate_bet_strategies(bets_df, None)
    
    # Calculate statistics for each strategy
    def calc_stats(df):
        if df.empty:
            return {
                'total_bets': 0,
                'win_count': 0,
                'loss_count': 0,
                'win_rate': 0,
                'total_wagered': 0,
                'total_payout': 0,
                'total_profit': 0,
                'roi': 0
            }
        total_bets = len(df)
        win_count = df['bet_won'].sum()
        loss_count = (df['bet_won'] == False).sum()
        win_rate = (win_count / total_bets * 100) if total_bets > 0 else 0
        total_wagered = df['bet_amount'].sum()
        total_payout = df['payout'].sum()
        total_profit = df['profit'].sum()
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        
        return {
            'total_bets': total_bets,
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'total_wagered': total_wagered,
            'total_payout': total_payout,
            'total_profit': total_profit,
            'roi': roi
        }
    
    safest_stats = calc_stats(safest_bets_df)
    value_stats = calc_stats(value_bets_df)
    
    # Generate markdown - Simple comparison page
    md_lines = [
        "# 🎲 NCAA Basketball Betting Strategies Comparison",
        "",
        f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This page compares two independent betting strategies. Each strategy is tracked separately in its own file:",
        "",
        "- 📄 **[Safest Bet Strategy](safest_bets.md)** - Full details and history",
        "- 📄 **[Best Value Strategy](value_bets.md)** - Full details and history",
        "",
        "> **✅ Real Odds Only**: All strategies use only real ESPN moneylines. Synthetic odds are never used.",
        "",
        "---",
        "",
        "## 🎯 Safest Bet Strategy",
        "",
        "**Approach**: Bet $1 daily on the game with **highest predicted win probability**",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Bets | {safest_stats['total_bets']} |",
        f"| Win Rate | {safest_stats['win_rate']:.1f}% ({safest_stats['win_count']}W-{safest_stats['loss_count']}L) |",
        f"| Net Profit | ${safest_stats['total_profit']:.2f} {'🟢' if safest_stats['total_profit'] > 0 else '🔴'} |",
        f"| ROI | {safest_stats['roi']:.1f}% |",
        "",
        "**[→ View Complete Safest Bet Tracker](safest_bets.md)**",
        "",
        "---",
        "",
        "## 💎 Best Value Strategy",
        "",
        "**Approach**: Bet $1 daily on the game with **best value score** (probability × odds)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Bets | {value_stats['total_bets']} |",
        f"| Win Rate | {value_stats['win_rate']:.1f}% ({value_stats['win_count']}W-{value_stats['loss_count']}L) |",
        f"| Net Profit | ${value_stats['total_profit']:.2f} {'🟢' if value_stats['total_profit'] > 0 else '🔴'} |",
        f"| ROI | {value_stats['roi']:.1f}% |",
        "",
        "**[→ View Complete Value Bet Tracker](value_bets.md)**",
        "",
        "---",
        "",
    ]
    
    # Add quick strategy comparison
    md_lines.extend([
        "## 📊 Quick Comparison",
        "",
        "| Metric | 🎯 Safest | 💎 Value | Winner |",
        "|--------|-----------|----------|--------|",
        f"| Win Rate | {safest_stats['win_rate']:.1f}% | {value_stats['win_rate']:.1f}% | {'🎯 Safest' if safest_stats['win_rate'] > value_stats['win_rate'] else '💎 Value' if value_stats['win_rate'] > safest_stats['win_rate'] else 'Tie'} |",
        f"| Total Profit | ${safest_stats['total_profit']:.2f} | ${value_stats['total_profit']:.2f} | {'🎯 Safest' if safest_stats['total_profit'] > value_stats['total_profit'] else '💎 Value' if value_stats['total_profit'] > safest_stats['total_profit'] else 'Tie'} |",
        f"| ROI | {safest_stats['roi']:.1f}% | {value_stats['roi']:.1f}% | {'🎯 Safest' if safest_stats['roi'] > value_stats['roi'] else '💎 Value' if value_stats['roi'] > safest_stats['roi'] else 'Tie'} |",
        f"| Total Bets | {safest_stats['total_bets']} | {value_stats['total_bets']} | - |",
        "",
        "---",
        "",
        "## 📝 Strategy Differences",
        "",
        "### 🎯 Safest Bet Strategy",
        "- Selects game with **highest confidence** each day",
        "- Typical confidence range: 80-90%+",
        "- Typical odds: Heavy favorites (-500 to -650)",
        "- Best for: Risk-averse bettors prioritizing win rate",
        "",
        "### 💎 Best Value Strategy",
        "- Selects game with **best value score** each day",
        "- Typical confidence range: 50-80%",
        "- Typical odds: More favorable (-110 to -300)",
        "- Best for: Profit-focused bettors willing to accept moderate risk",
        "",
        "---",
        "",
        "*Auto-generated by betting_tracker.py*"
    ])
    
    # Add today's best bets section
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    today_pred_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')

    
    # Write comparison file
    output_path = os.path.join(os.path.dirname(__file__), '..', 'bets.md')
    with open(output_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    # Generate individual strategy files
    generate_safest_bets_file(safest_bets_df, safest_stats, today_pred_path)
    generate_value_bets_file(value_bets_df, value_stats, today_pred_path)
    
    print(f"✓ Generated bets.md (comparison) at {output_path}")
    print(f"  Safest Bet Strategy: {safest_stats['total_bets']} bets, ${safest_stats['total_profit']:.2f} profit, {safest_stats['win_rate']:.1f}% win rate")
    print(f"  Best Value Strategy: {value_stats['total_bets']} bets, ${value_stats['total_profit']:.2f} profit, {value_stats['win_rate']:.1f}% win rate")


def generate_safest_bets_file(safest_bets_df, safest_stats, today_pred_path):
    """Generate safest_bets.md file for the Safest Bet Strategy."""
    md_lines = [
        "# 🎯 Safest Bet Strategy Tracker",
        "",
        f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Tracking Started**: {safest_bets_df['date'].min() if not safest_bets_df.empty else 'Today'}",
        "",
        "## 📋 Strategy Description",
        "",
        "**The Safest Bet Strategy** selects ONE game each day with the **highest predicted win probability** from our model.",
        "",
        "- **Goal**: Maximize win rate by betting on the most confident predictions",
        "- **Bet Amount**: $1.00 per game",
        "- **Selection Criteria**: Highest confidence prediction with real ESPN moneyline",
        "- **Risk Profile**: Conservative - prioritizes high probability of winning over potential profit",
        "",
        "> **✅ Real Odds Only**: Only games with actual ESPN moneylines are tracked. Games showing \"OFF\" or moneylines worse than -1000 are excluded.",
        "",
        "---",
        "",
        "## 📊 Season Performance",
        "",
        f"- **Total Bets**: {safest_stats['total_bets']}",
        f"- **Win Rate**: {safest_stats['win_rate']:.1f}% ({safest_stats['win_count']}W-{safest_stats['loss_count']}L)",
        f"- **Total Wagered**: ${safest_stats['total_wagered']:.2f}",
        f"- **Total Payout**: ${safest_stats['total_payout']:.2f}",
        f"- **Net Profit**: ${safest_stats['total_profit']:.2f} {'🟢' if safest_stats['total_profit'] > 0 else '🔴' if safest_stats['total_profit'] < 0 else '⚪'}",
        f"- **ROI**: {safest_stats['roi']:.1f}%",
        "",
        "---",
        "",
    ]
    
    # Add today's bet
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    if os.path.exists(today_pred_path):
        try:
            today_preds = pd.read_csv(today_pred_path)
            todays_bets = get_todays_bets(today_preds)
            safest_bet = todays_bets['safest_bet']
            
            if safest_bet is not None:
                if safest_bet['predicted_home_win'] == 1:
                    bet_team = safest_bet['home_team']
                    opponent = safest_bet['away_team']
                    moneyline = safest_bet['home_moneyline']
                    location = 'vs'
                else:
                    bet_team = safest_bet['away_team']
                    opponent = safest_bet['home_team']
                    moneyline = safest_bet['away_moneyline']
                    location = '@'
                
                md_lines.extend([
                    "## 🎯 Today's Bet",
                    "",
                    f"**{bet_team}** {location} **{opponent}**",
                    "",
                    f"- **Bet On**: {bet_team}",
                    f"- **Confidence**: {safest_bet['confidence']:.1%}",
                    f"- **Moneyline**: {int(moneyline):+d}",
                    f"- **Potential Profit**: ${american_odds_to_payout(moneyline, 1.0) - 1.0:.2f}",
                    "",
                    "✅ *Highest confidence game today with real ESPN odds*",
                    "",
                    "---",
                    "",
                ])
            else:
                md_lines.extend([
                    "## 🎯 Today's Bet",
                    "",
                    "**No bettable games available today**",
                    "",
                    "Games may have moneylines set to \"OFF\" or be more extreme than -1000.",
                    "",
                    "---",
                    "",
                ])
        except Exception as e:
            print(f"⚠️ Could not add today's safest bet: {e}")
    
    # Performance by confidence level
    if not safest_bets_df.empty and 'confidence' in safest_bets_df.columns:
        df = safest_bets_df.copy()
        df['confidence_bucket'] = pd.cut(
            df['confidence'], 
            bins=[0, 0.6, 0.7, 0.8, 0.9, 1.0],
            labels=['<60%', '60-70%', '70-80%', '80-90%', '90%+']
        )
        
        md_lines.extend([
            "## 📈 Performance by Confidence Level",
            "",
            "| Confidence | Bets | Win Rate | Net Profit | ROI |",
            "|------------|------|----------|------------|-----|"
        ])
        
        for bucket in ['<60%', '60-70%', '70-80%', '80-90%', '90%+']:
            bucket_df = df[df['confidence_bucket'] == bucket]
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
        
        md_lines.extend(["", "---", ""])
    
    # Recent bets history
    if not safest_bets_df.empty:
        md_lines.extend([
            "## 📋 Complete Bet History",
            "",
            "| Date | Result | Matchup | Bet On | ML | Confidence | Profit |",
            "|------|--------|---------|--------|----|-----------:|-------:|"
        ])
        
        all_bets = safest_bets_df.sort_values('date', ascending=False)
        for _, bet in all_bets.iterrows():
            result_icon = "✅" if bet['bet_won'] else "❌" if bet['bet_won'] == False else "⚪"
            matchup = f"{bet['away_team']} @ {bet['home_team']}"
            bet_on = bet['predicted_winner']
            moneyline = f"{int(bet['moneyline']):+d}" if pd.notna(bet['moneyline']) else "N/A"
            confidence = f"{bet['confidence']:.1%}"
            profit = f"${bet['profit']:.2f}" if bet['profit'] >= 0 else f"-${abs(bet['profit']):.2f}"
            
            md_lines.append(
                f"| {bet['date']} | {result_icon} | {matchup} | {bet_on} | {moneyline} | {confidence} | {profit} |"
            )
        
        md_lines.extend(["", ""])
    
    md_lines.extend([
        "---",
        "",
        "## 🗂 Season Breakdown",
        "",
    ])
    if not safest_bets_df.empty:
        season_groups = safests = []  # placeholder to avoid linter complaining unused variable
        df_season = safest_bets_df.copy()
        df_season['season'] = df_season['date'].apply(derive_season_label)
        season_lines = ["| Season | Bets | Win Rate | Profit | ROI |", "|--------|------|----------|--------|-----|"]
        for season, grp in df_season.groupby('season'):
            wins = grp['bet_won'].sum()
            total = len(grp)
            win_rate = (wins / total * 100) if total else 0
            profit = grp['profit'].sum()
            wagered = grp['bet_amount'].sum()
            roi = (profit / wagered * 100) if wagered else 0
            season_lines.append(f"| {season} | {total} | {win_rate:.1f}% | ${profit:.2f} | {roi:.1f}% |")
        md_lines.extend(season_lines + ["", "---", ""])
    md_lines.extend([
        "## 📝 Notes",
        "",
        "- **Only games with real ESPN moneylines** are tracked",
        "- **Moneylines more extreme than -1000 are excluded** as unbettable",
        "- Moneylines shown are American odds (e.g., -110 means risk $110 to win $100)",
        "- This tracker is for **educational/entertainment purposes** to demonstrate prediction accuracy",
        "",
        "*Auto-generated by betting_tracker.py*"
    ])
    
    output_path = os.path.join(os.path.dirname(__file__), '..', 'safest_bets.md')
    with open(output_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    print(f"✓ Generated safest_bets.md at {output_path}")


def generate_value_bets_file(value_bets_df, value_stats, today_pred_path):
    """Generate value_bets.md file for the Best Value Strategy."""
    md_lines = [
        "# 💎 Best Value Strategy Tracker",
        "",
        f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Tracking Started**: {value_bets_df['date'].min() if not value_bets_df.empty else 'Today'}",
        "",
        "## 📋 Strategy Description",
        "",
        "**The Best Value Strategy** selects ONE game each day with the **best value score** - the optimal combination of high win probability and favorable odds.",
        "",
        "- **Goal**: Maximize profit by finding the best risk/reward opportunities",
        "- **Bet Amount**: $1.00 per game",
        "- **Selection Criteria**: Highest value score (confidence × potential profit - risk)",
        "- **Risk Profile**: Moderate - balances probability with potential profit",
        "",
        "> **✅ Real Odds Only**: Only games with actual ESPN moneylines are tracked. Games showing \"OFF\" or moneylines worse than -1000 are excluded.",
        "",
        "---",
        "",
        "## 📊 Season Performance",
        "",
        f"- **Total Bets**: {value_stats['total_bets']}",
        f"- **Win Rate**: {value_stats['win_rate']:.1f}% ({value_stats['win_count']}W-{value_stats['loss_count']}L)",
        f"- **Total Wagered**: ${value_stats['total_wagered']:.2f}",
        f"- **Total Payout**: ${value_stats['total_payout']:.2f}",
        f"- **Net Profit**: ${value_stats['total_profit']:.2f} {'🟢' if value_stats['total_profit'] > 0 else '🔴' if value_stats['total_profit'] < 0 else '⚪'}",
        f"- **ROI**: {value_stats['roi']:.1f}%",
        "",
        "---",
        "",
    ]
    
    # Add today's bet
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    if os.path.exists(today_pred_path):
        try:
            today_preds = pd.read_csv(today_pred_path)
            todays_bets = get_todays_bets(today_preds)
            value_bet = todays_bets['value_bet']
            
            if value_bet is not None:
                if value_bet['predicted_home_win'] == 1:
                    bet_team = value_bet['home_team']
                    opponent = value_bet['away_team']
                    moneyline = value_bet['home_moneyline']
                    location = 'vs'
                else:
                    bet_team = value_bet['away_team']
                    opponent = value_bet['home_team']
                    moneyline = value_bet['away_moneyline']
                    location = '@'
                
                value_score = calculate_value_score(value_bet['confidence'], moneyline)
                
                md_lines.extend([
                    "## 💎 Today's Bet",
                    "",
                    f"**{bet_team}** {location} **{opponent}**",
                    "",
                    f"- **Bet On**: {bet_team}",
                    f"- **Confidence**: {value_bet['confidence']:.1%}",
                    f"- **Moneyline**: {int(moneyline):+d}",
                    f"- **Value Score**: {value_score:.3f}",
                    f"- **Potential Profit**: ${american_odds_to_payout(moneyline, 1.0) - 1.0:.2f}",
                    "",
                    "✅ *Best value opportunity today - optimal balance of probability and odds*",
                    "",
                    "---",
                    "",
                ])
            else:
                md_lines.extend([
                    "## 💎 Today's Bet",
                    "",
                    "**No bettable games available today**",
                    "",
                    "Games may have moneylines set to \"OFF\" or be more extreme than -1000.",
                    "",
                    "---",
                    "",
                ])
        except Exception as e:
            print(f"⚠️ Could not add today's value bet: {e}")
    
    # Performance by confidence level
    if not value_bets_df.empty and 'confidence' in value_bets_df.columns:
        df = value_bets_df.copy()
        df['confidence_bucket'] = pd.cut(
            df['confidence'], 
            bins=[0, 0.6, 0.7, 0.8, 0.9, 1.0],
            labels=['<60%', '60-70%', '70-80%', '80-90%', '90%+']
        )
        
        md_lines.extend([
            "## 📈 Performance by Confidence Level",
            "",
            "| Confidence | Bets | Win Rate | Net Profit | ROI |",
            "|------------|------|----------|------------|-----|"
        ])
        
        for bucket in ['<60%', '60-70%', '70-80%', '80-90%', '90%+']:
            bucket_df = df[df['confidence_bucket'] == bucket]
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
        
        md_lines.extend(["", "---", ""])
    
    # Recent bets history
    if not value_bets_df.empty:
        md_lines.extend([
            "## 📋 Complete Bet History",
            "",
            "| Date | Result | Matchup | Bet On | ML | Confidence | Value Score | Profit |",
            "|------|--------|---------|--------|----|-----------:|------------:|-------:|"
        ])
        
        all_bets = value_bets_df.sort_values('date', ascending=False)
        for _, bet in all_bets.iterrows():
            result_icon = "✅" if bet['bet_won'] else "❌" if bet['bet_won'] == False else "⚪"
            matchup = f"{bet['away_team']} @ {bet['home_team']}"
            bet_on = bet['predicted_winner']
            moneyline = f"{int(bet['moneyline']):+d}" if pd.notna(bet['moneyline']) else "N/A"
            confidence = f"{bet['confidence']:.1%}"
            value_score = calculate_value_score(bet['confidence'], bet['moneyline'])
            value_str = f"{value_score:.3f}" if value_score is not None else "N/A"
            profit = f"${bet['profit']:.2f}" if bet['profit'] >= 0 else f"-${abs(bet['profit']):.2f}"
            
            md_lines.append(
                f"| {bet['date']} | {result_icon} | {matchup} | {bet_on} | {moneyline} | {confidence} | {value_str} | {profit} |"
            )
        
        md_lines.extend(["", ""])
    
    md_lines.extend([
        "---",
        "",
        "## 🗂 Season Breakdown",
        "",
    ])
    if not value_bets_df.empty:
        df_season = value_bets_df.copy()
        df_season['season'] = df_season['date'].apply(derive_season_label)
        season_lines = ["| Season | Bets | Win Rate | Profit | ROI |", "|--------|------|----------|--------|-----|"]
        for season, grp in df_season.groupby('season'):
            wins = grp['bet_won'].sum()
            total = len(grp)
            win_rate = (wins / total * 100) if total else 0
            profit = grp['profit'].sum()
            wagered = grp['bet_amount'].sum()
            roi = (profit / wagered * 100) if wagered else 0
            season_lines.append(f"| {season} | {total} | {win_rate:.1f}% | ${profit:.2f} | {roi:.1f}% |")
        md_lines.extend(season_lines + ["", "---", ""])
    md_lines.extend([
        "## 📝 Notes",
        "",
        "- **Value Score** = (Confidence × Potential Profit) - Risk",
        "- **Only games with real ESPN moneylines** are tracked",
        "- **Moneylines more extreme than -1000 are excluded** as unbettable",
        "- Moneylines shown are American odds (e.g., -110 means risk $110 to win $100)",
        "- This tracker is for **educational/entertainment purposes** to demonstrate prediction accuracy",
        "",
        "*Auto-generated by betting_tracker.py*"
    ])
    
    output_path = os.path.join(os.path.dirname(__file__), '..', 'value_bets.md')
    with open(output_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    print(f"✓ Generated value_bets.md at {output_path}")


if __name__ == "__main__":
    generate_bets_markdown()
