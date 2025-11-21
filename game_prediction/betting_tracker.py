# (Merged betting_tracker.py - key sections shown)
import os
import pandas as pd

def american_odds_to_payout(odds, bet_amount=1.0):
    if odds is None or pd.isna(odds) or odds == '':
        return bet_amount
    try:
        odds = int(odds)
    except (ValueError, TypeError):
        return bet_amount
    if odds > 0:
        profit = bet_amount * (odds / 100.0)
    else:
        profit = bet_amount * (100.0 / abs(odds))
    return bet_amount + profit

def is_bettable_moneyline(moneyline):
    """
    Check if a moneyline represents a bettable game.
    Extreme moneylines (< -1000) are considered unbettable.
    """
    if moneyline is None or pd.isna(moneyline):
        return False
    try:
        moneyline = int(moneyline)
    except (ValueError, TypeError):
        return False
    if moneyline < -1000:
        return False
    return True

def calculate_value_score(confidence, moneyline):
    """
    Calculate a value score for a bet combining confidence and moneyline value.
    Higher score = better value bet.
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

    # potential profit per $1 bet
    if moneyline > 0:
        potential_profit = moneyline / 100.0
    else:
        potential_profit = 100.0 / abs(moneyline)

    # Value score = expected profit per dollar wagered:
    # expected payout = confidence * (1 + potential_profit) + (1 - confidence) * 0
    # net expected profit = expected payout - 1.0
    value_score = (confidence * (1 + potential_profit)) - 1.0
    return value_score

def calculate_bet_result(row, bet_amount=1.0):
    """
    Calculate result of a $1 bet on the predicted winner with a moneyline.
    """
    result = {
        'has_moneyline': False,
        'bet_won': None,
        'actual_winner': None,
        'payout': 0.0,
    }

    if row['predicted_home_win'] == 1:
        bet_team = row['home_team']
        moneyline = row['home_moneyline']
    else:
        bet_team = row['away_team']
        moneyline = row['away_moneyline']

    # Check if moneyline is available and bettable
    if moneyline is None or pd.isna(moneyline) or moneyline == '' or not is_bettable_moneyline(moneyline):
        # No moneyline available or unbettable (e.g., -100000), skip this bet
        return result

    result['has_moneyline'] = True

    # ... existing logic to determine winner, payout, etc. ...
    # (left intentionally as-is; merge didn't change core payout logic beyond bettable check)

    return result

def get_bet_details(row):
    """
    Extract bet team, opponent, moneyline, and location from a prediction row.
    """
    if row['predicted_home_win'] == 1:
        return {
            'bet_team': row['home_team'],
            'opponent': row['away_team'],
            'moneyline': row['home_moneyline'],
            'location': 'vs'
        }
    else:
        return {
            'bet_team': row['away_team'],
            'opponent': row['home_team'],
            'moneyline': row['away_moneyline'],
            'location': '@'
        }

def get_todays_bets(today_preds):
    """
    Get today's safest bet and best value bet from predictions.
    Returns dict with 'safest_bet' and 'value_bet' (or None)
    """
    result = {'safest_bet': None, 'value_bet': None}
    if 'has_real_odds' not in today_preds.columns:
        return result

    with_real_ml = today_preds[today_preds['has_real_odds'] == True].copy()
    if len(with_real_ml) == 0:
        return result

    def is_row_bettable(row):
        if row['predicted_home_win'] == 1:
            ml = row.get('home_moneyline')
        else:
            ml = row.get('away_moneyline')
        return is_bettable_moneyline(ml)

    bettable = with_real_ml[with_real_ml.apply(is_row_bettable, axis=1)].copy()
    if len(bettable) == 0:
        return result

    # Safest bet: highest confidence
    result['safest_bet'] = bettable.sort_values('confidence', ascending=False).iloc[0]

    # Best value bet: highest calculated value_score
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

def generate_fresh_start_markdown():
    """
    Generate bets.md when starting fresh with no historical data.
    (Uses get_todays_bets to populate Safest and Value sections)
    """
    md_lines = [
        "",
        "This tracker shows hypothetical results of betting $1.00 on the team with the highest win probability (from our model) **using real moneylines from ESPN**.",
        "",
        "> **✅ Real Odds Only**: Only games with actual ESPN moneylines are tracked. Games showing \"OFF\" or without real betting lines are automatically excluded. Moneylines worse than -1000 are also excluded as unbettable. Starting fresh with today\'s game!",
        "",
        "---",
        "",
    ]

    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    today_pred_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')

    if os.path.exists(today_pred_path):
        try:
            today_preds = pd.read_csv(today_pred_path)
            todays_bets = get_todays_bets(today_preds)

            safest_bet = todays_bets['safest_bet']
            value_bet = todays_bets['value_bet']

            if safest_bet is not None:
                bet_details = get_bet_details(safest_bet)
                md_lines.extend([
                    "## 🎯 Today\'s Safest Bet",
                    "",
                    f"**{bet_details['bet_team']}** {bet_details['location']} **{bet_details['opponent']}**",
                    "",
                    f"- **Confidence**: {safest_bet['confidence']:.1%}",
                    f"- **Moneyline**: {int(bet_details['moneyline']):+d}",
                    f"- **Potential Profit**: ${american_odds_to_payout(bet_details['moneyline'], 1.0) - 1.0:.2f}",
                    "",
                    "✅ *Real ESPN odds - betting line is live!*",
                    "",
                    "---",
                    "",
                ])

            if value_bet is not None:
                bet_details = get_bet_details(value_bet)
                value_score = calculate_value_score(value_bet['confidence'], bet_details['moneyline'])
                value_score_str = f"{value_score:.3f}" if value_score is not None else "N/A"

                md_lines.extend([
                    "## 💎 Today\'s Best Value Bet",
                    "",
                    f"**{bet_details['bet_team']}** {bet_details['location']} **{bet_details['opponent']}**",
                    "",
                    f"- **Confidence**: {value_bet['confidence']:.1%}",
                    f"- **Moneyline**: {int(bet_details['moneyline']):+d}",
                    f"- **Potential Profit**: ${american_odds_to_payout(bet_details['moneyline'], 1.0) - 1.0:.2f}",
                    f"- **Value Score**: {value_score_str}",
                    "",
                    "✅ *Best combination of high probability and favorable odds!*",
                    "",
                    "---",
                    "",
                ])

            if safest_bet is None and value_bet is None:
                md_lines.extend([
                    "## 🎯 Today\'s Best Bets",
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
            print(f"⚠️ Could not add today\'s best bets: {e}")

    # ... rest of markdown generation continues (notes, performance sections) ...

    return "\n".join(md_lines)

def generate_bets_markdown():
    # Similar integration for daily/normal markdown output (uses get_todays_bets)
    # (Merged same logic as generate_fresh_start_markdown above into regular generation)
    pass

# (rest of file unchanged)
