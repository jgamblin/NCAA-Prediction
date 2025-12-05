#!/usr/bin/env python3
"""
Export Database to Static JSON Files

Exports database data to JSON files for GitHub Pages frontend.
This replaces the need for a FastAPI backend - frontend reads JSON directly.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, date
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection
from backend.repositories import (
    GamesRepository,
    PredictionsRepository,
    TeamsRepository,
    FeaturesRepository,
    BettingRepository
)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def export_to_json(output_dir: Path = None):
    """
    Export database to JSON files for static hosting on GitHub Pages.
    
    Args:
        output_dir: Output directory for JSON files (default: frontend/public/data)
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / 'frontend' / 'public' / 'data'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("EXPORTING DATABASE TO JSON FILES")
    print(f"Output directory: {output_dir}")
    print("="*80)
    print()
    
    # Initialize database connection and repositories
    db = get_db_connection()
    games_repo = GamesRepository(db)
    pred_repo = PredictionsRepository(db)
    teams_repo = TeamsRepository(db)
    features_repo = FeaturesRepository(db)
    betting_repo = BettingRepository(db)
    
    # =========================================================================
    # 1. Export Upcoming Predictions
    # =========================================================================
    print("1. Exporting upcoming predictions...")
    
    upcoming_preds = pred_repo.get_upcoming_predictions()
    if not upcoming_preds.empty:
        # Convert to records for JSON
        predictions_data = upcoming_preds.to_dict('records')
        
        # Clean up data types
        for pred in predictions_data:
            for key, value in pred.items():
                if pd.isna(value):
                    pred[key] = None
        
        with open(output_dir / 'predictions.json', 'w') as f:
            json.dump(predictions_data, f, indent=2, default=json_serial)
        
        print(f"   ✓ Exported {len(predictions_data)} upcoming predictions")
    else:
        print("   ⚠️ No upcoming predictions to export")
        with open(output_dir / 'predictions.json', 'w') as f:
            json.dump([], f)
    
    # =========================================================================
    # 2. Export Today's Games (Highlighted)
    # =========================================================================
    print("\n2. Exporting today's games...")
    
    today = date.today()
    today_games = games_repo.get_games_by_date(today)
    
    # Enrich with predictions
    today_with_preds = []
    for game in today_games:
        pred = pred_repo.get_latest_prediction(game['game_id'])
        if pred:
            game_data = {**game, **pred}
        else:
            game_data = game
        today_with_preds.append(game_data)
    
    with open(output_dir / 'today_games.json', 'w') as f:
        json.dump(today_with_preds, f, indent=2, default=json_serial)
    
    print(f"   ✓ Exported {len(today_with_preds)} today's games")
    
    # =========================================================================
    # 2b. Export ALL Upcoming Scheduled Games (with predictions if available)
    # =========================================================================
    print("\n2b. Exporting all upcoming scheduled games...")
    
    # Collect games from today forward (up to 14 days ahead)
    from datetime import timedelta
    upcoming_with_preds = []
    
    for days_ahead in range(14):  # Check next 2 weeks
        check_date = today + timedelta(days=days_ahead)
        day_games = games_repo.get_games_by_date(check_date)
        
        for game in day_games:
            # Only include scheduled games
            if game.get('game_status') == 'Scheduled':
                pred = pred_repo.get_latest_prediction(game['game_id'])
                if pred:
                    game.update(pred)
                # Clean up NaN values
                for key, value in game.items():
                    if pd.isna(value) if isinstance(value, float) else value is None:
                        game[key] = None
                upcoming_with_preds.append(game)
    
    # Sort by date and home team
    upcoming_with_preds.sort(key=lambda x: (x.get('date', ''), x.get('home_team', '')))
    
    with open(output_dir / 'upcoming_games.json', 'w') as f:
        json.dump(upcoming_with_preds, f, indent=2, default=json_serial)
    
    pred_count = sum(1 for g in upcoming_with_preds if g.get('predicted_winner'))
    print(f"   ✓ Exported {len(upcoming_with_preds)} upcoming games ({pred_count} with predictions)")
    
    # =========================================================================
    # 3. Export Betting Summary
    # =========================================================================
    print("\n3. Exporting betting summary...")
    
    betting_summary = betting_repo.get_betting_summary()
    if betting_summary:
        with open(output_dir / 'betting_summary.json', 'w') as f:
            json.dump(betting_summary, f, indent=2, default=json_serial)
        print(f"   ✓ Exported betting summary")
    else:
        with open(output_dir / 'betting_summary.json', 'w') as f:
            json.dump({
                'total_bets': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_profit': 0,
                'roi': 0
            }, f, indent=2)
        print("   ⚠️ No betting data available")
    
    # =========================================================================
    # 4. Export Betting Performance by Strategy
    # =========================================================================
    print("\n4. Exporting betting performance...")
    
    by_strategy = betting_repo.get_betting_summary_by_strategy()
    with open(output_dir / 'betting_by_strategy.json', 'w') as f:
        json.dump(by_strategy, f, indent=2, default=json_serial)
    print(f"   ✓ Exported {len(by_strategy)} strategy summaries")
    
    by_confidence = betting_repo.get_betting_summary_by_confidence()
    with open(output_dir / 'betting_by_confidence.json', 'w') as f:
        json.dump(by_confidence, f, indent=2, default=json_serial)
    print(f"   ✓ Exported {len(by_confidence)} confidence buckets")
    
    # =========================================================================
    # 5. Export Value Bets (High ROI opportunities)
    # =========================================================================
    print("\n5. Exporting value bets...")
    
    value_bets = betting_repo.get_value_bets(min_value_score=0.05, min_confidence=0.55)
    
    # Add explanations from predictions
    for bet in value_bets:
        if bet.get('prediction_id'):
            pred = pred_repo.get_prediction_by_id(bet['prediction_id'])
            if pred and pred.get('explanation'):
                bet['explanation'] = pred['explanation']
    
    with open(output_dir / 'value_bets.json', 'w') as f:
        json.dump(value_bets, f, indent=2, default=json_serial)
    print(f"   ✓ Exported {len(value_bets)} value bets")
    
    # =========================================================================
    # 5b. Export Parlays
    # =========================================================================
    print("\n5b. Exporting parlays...")
    
    # Get all parlays with their legs
    parlays_query = """
        SELECT 
            p.id,
            p.parlay_date,
            p.bet_amount,
            p.num_legs,
            p.combined_odds,
            p.potential_payout,
            p.parlay_won,
            p.actual_payout,
            p.profit,
            p.strategy,
            p.settled_at
        FROM parlays p
        ORDER BY p.parlay_date DESC
    """
    parlays_df = db.fetch_df(parlays_query)
    parlays = []
    
    for _, parlay in parlays_df.iterrows():
        # Get legs for this parlay
        legs_query = """
            SELECT 
                pl.id,
                pl.game_id,
                pl.bet_team,
                pl.moneyline,
                pl.confidence,
                pl.leg_won,
                pl.actual_winner,
                pl.leg_number,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                g.game_status
            FROM parlay_legs pl
            JOIN games g ON pl.game_id = g.game_id
            WHERE pl.parlay_id = ?
            ORDER BY pl.leg_number
        """
        legs_df = db.fetch_df(legs_query, (parlay['id'],))
        
        parlay_data = {
            'id': int(parlay['id']),
            'date': parlay['parlay_date'].isoformat() if parlay['parlay_date'] else None,
            'bet_amount': float(parlay['bet_amount']),
            'num_legs': int(parlay['num_legs']),
            'combined_odds': float(parlay['combined_odds']),
            'potential_payout': float(parlay['potential_payout']),
            'won': bool(parlay['parlay_won']) if pd.notna(parlay['parlay_won']) else None,
            'actual_payout': float(parlay['actual_payout']) if pd.notna(parlay['actual_payout']) else 0.0,
            'profit': float(parlay['profit']) if pd.notna(parlay['profit']) else None,
            'strategy': parlay['strategy'],
            'settled': pd.notna(parlay['settled_at']) and parlay['settled_at'] is not None,
            'settled_at': parlay['settled_at'].isoformat() if pd.notna(parlay['settled_at']) else None,
            'legs': []
        }
        
        for _, leg in legs_df.iterrows():
            leg_data = {
                'leg_number': int(leg['leg_number']),
                'game_id': leg['game_id'],
                'bet_team': leg['bet_team'],
                'opponent': leg['away_team'] if leg['bet_team'] == leg['home_team'] else leg['home_team'],
                'moneyline': int(leg['moneyline']),
                'confidence': float(leg['confidence']),
                'won': bool(leg['leg_won']) if pd.notna(leg['leg_won']) else None,
                'actual_winner': leg['actual_winner'] if pd.notna(leg['actual_winner']) else None,
                'home_team': leg['home_team'],
                'away_team': leg['away_team'],
                'home_score': int(leg['home_score']) if pd.notna(leg['home_score']) else None,
                'away_score': int(leg['away_score']) if pd.notna(leg['away_score']) else None,
                'game_status': leg['game_status']
            }
            parlay_data['legs'].append(leg_data)
        
        parlays.append(parlay_data)
    
    with open(output_dir / 'parlays.json', 'w') as f:
        json.dump(parlays, f, indent=2, default=json_serial)
    print(f"   ✓ Exported {len(parlays)} parlays")
    
    # Parlay statistics
    parlay_stats_query = """
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
    stats_df = db.fetch_df(parlay_stats_query)
    
    if not stats_df.empty and stats_df['total_parlays'].iloc[0] > 0:
        total = int(stats_df['total_parlays'].iloc[0])
        wins = int(stats_df['wins'].iloc[0]) if pd.notna(stats_df['wins'].iloc[0]) else 0
        parlay_stats = {
            'total_parlays': total,
            'wins': wins,
            'losses': int(stats_df['losses'].iloc[0]) if pd.notna(stats_df['losses'].iloc[0]) else 0,
            'win_rate': wins / total if total > 0 else 0.0,
            'total_wagered': float(stats_df['total_wagered'].iloc[0]),
            'total_profit': float(stats_df['total_profit'].iloc[0]) if pd.notna(stats_df['total_profit'].iloc[0]) else 0.0,
            'roi': (float(stats_df['total_profit'].iloc[0]) / float(stats_df['total_wagered'].iloc[0]) * 100) if float(stats_df['total_wagered'].iloc[0]) > 0 else 0.0,
            'biggest_win': float(stats_df['biggest_win'].iloc[0]) if pd.notna(stats_df['biggest_win'].iloc[0]) else 0.0,
            'biggest_loss': float(stats_df['biggest_loss'].iloc[0]) if pd.notna(stats_df['biggest_loss'].iloc[0]) else 0.0
        }
    else:
        parlay_stats = {
            'total_parlays': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_wagered': 0.0,
            'total_profit': 0.0,
            'roi': 0.0,
            'biggest_win': 0.0,
            'biggest_loss': 0.0
        }
    
    with open(output_dir / 'parlay_stats.json', 'w') as f:
        json.dump(parlay_stats, f, indent=2, default=json_serial)
    print(f"   ✓ Exported parlay statistics")
    
    # =========================================================================
    # 6. Export Accuracy Metrics (2025-26 Season Only)
    # =========================================================================
    print("\n6. Exporting accuracy metrics...")
    
    # Overall accuracy for current season (deduplicated - first prediction per game)
    current_season = "2025-26"
    today = datetime.now().date()
    
    overall_query = """
        WITH first_predictions AS (
            SELECT 
                p.game_id,
                MIN(p.id) as first_prediction_id
            FROM predictions p
            JOIN games g ON p.game_id = g.game_id
            WHERE g.season = ?
              AND g.game_status = 'Final'
              AND g.date <= ?
              AND p.predicted_winner IS NOT NULL
              AND g.home_score IS NOT NULL
              AND g.away_score IS NOT NULL
            GROUP BY p.game_id
        )
        SELECT 
            COUNT(*) as total_predictions,
            SUM(CASE 
                WHEN p.predicted_winner = 
                    CASE 
                        WHEN g.home_score > g.away_score THEN g.home_team
                        WHEN g.away_score > g.home_score THEN g.away_team
                    END 
                THEN 1 ELSE 0 END) as correct_predictions,
            AVG(p.confidence) as avg_confidence
        FROM predictions p
        JOIN games g ON p.game_id = g.game_id
        JOIN first_predictions fp ON p.id = fp.first_prediction_id
        WHERE g.season = ?
          AND g.game_status = 'Final'
          AND g.date <= ?
          AND p.predicted_winner IS NOT NULL
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
    """
    
    accuracy_df = db.fetch_df(overall_query, (current_season, today, current_season, today))
    
    if not accuracy_df.empty and accuracy_df.iloc[0]['total_predictions'] > 0:
        row = accuracy_df.iloc[0]
        overall_accuracy = {
            'total_predictions': int(row['total_predictions']),
            'correct_predictions': int(row['correct_predictions']),
            'avg_confidence': float(row['avg_confidence']) if pd.notna(row['avg_confidence']) else 0.0,
            'accuracy': float(row['correct_predictions']) / float(row['total_predictions'])
        }
    else:
        overall_accuracy = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'avg_confidence': 0.0,
            'accuracy': 0.0
        }
    
    with open(output_dir / 'accuracy_overall.json', 'w') as f:
        json.dump(overall_accuracy, f, indent=2, default=json_serial)
    print(f"   ✓ Overall accuracy ({current_season}): {overall_accuracy.get('accuracy', 0):.1%}")
    
    # High confidence accuracy (≥65%)
    high_conf_query = overall_query.replace(
        "AND g.away_score IS NOT NULL",
        "AND g.away_score IS NOT NULL\n          AND p.confidence >= 0.65"
    )
    
    high_conf_df = db.fetch_df(high_conf_query, (current_season, today, current_season, today))
    
    if not high_conf_df.empty and high_conf_df.iloc[0]['total_predictions'] > 0:
        row = high_conf_df.iloc[0]
        high_conf_accuracy = {
            'total_predictions': int(row['total_predictions']),
            'correct_predictions': int(row['correct_predictions']),
            'avg_confidence': float(row['avg_confidence']) if pd.notna(row['avg_confidence']) else 0.0,
            'accuracy': float(row['correct_predictions']) / float(row['total_predictions'])
        }
    else:
        high_conf_accuracy = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'avg_confidence': 0.0,
            'accuracy': 0.0
        }
    
    with open(output_dir / 'accuracy_high_confidence.json', 'w') as f:
        json.dump(high_conf_accuracy, f, indent=2, default=json_serial)
    print(f"   ✓ High confidence (≥65%): {high_conf_accuracy.get('accuracy', 0):.1%}")
    
    # =========================================================================
    # 7. Export Team Statistics (Top performers)
    # =========================================================================
    print("\n7. Exporting team statistics...")
    
    # Calculate prediction accuracy per team (not their actual win %)
    current_season = "2025-26"
    today = datetime.now().date()
    
    # Get prediction accuracy for each team
    team_accuracy_query = """
        WITH first_predictions AS (
            SELECT 
                p.game_id,
                MIN(p.id) as first_prediction_id
            FROM predictions p
            JOIN games g ON p.game_id = g.game_id
            WHERE g.season = ?
              AND g.game_status = 'Final'
              AND g.date <= ?
              AND p.predicted_winner IS NOT NULL
              AND g.home_score IS NOT NULL
              AND g.away_score IS NOT NULL
            GROUP BY p.game_id
        ),
        team_predictions AS (
            SELECT 
                p.game_id,
                p.predicted_winner,
                p.confidence,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                CASE 
                    WHEN p.predicted_winner = g.home_team OR p.predicted_winner = g.away_team 
                    THEN p.predicted_winner 
                END as team,
                CASE 
                    WHEN g.home_score > g.away_score THEN g.home_team
                    WHEN g.away_score > g.home_score THEN g.away_team
                END as actual_winner
            FROM predictions p
            JOIN games g ON p.game_id = g.game_id
            JOIN first_predictions fp ON p.id = fp.first_prediction_id
            WHERE g.season = ?
              AND g.game_status = 'Final'
              AND g.date <= ?
              AND p.predicted_winner IS NOT NULL
              AND g.home_score IS NOT NULL
              AND g.away_score IS NOT NULL
        ),
        team_stats AS (
            SELECT 
                team,
                COUNT(*) as predictions_made,
                SUM(CASE WHEN predicted_winner = actual_winner THEN 1 ELSE 0 END) as correct_predictions,
                CAST(SUM(CASE WHEN predicted_winner = actual_winner THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as prediction_accuracy,
                AVG(confidence) as avg_confidence
            FROM team_predictions
            WHERE team IS NOT NULL
            GROUP BY team
            HAVING COUNT(*) >= 5  -- Only teams with at least 5 predictions
        ),
        game_stats AS (
            SELECT 
                team,
                SUM(wins) as team_wins,
                SUM(losses) as team_losses
            FROM (
                SELECT 
                    home_team as team,
                    SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) as losses
                FROM games
                WHERE season = ? AND game_status = 'Final' AND date <= ?
                GROUP BY home_team
                UNION ALL
                SELECT 
                    away_team as team,
                    SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN away_score < home_score THEN 1 ELSE 0 END) as losses
                FROM games
                WHERE season = ? AND game_status = 'Final' AND date <= ?
                GROUP BY away_team
            )
            GROUP BY team
        )
        SELECT 
            ts.team,
            ts.predictions_made,
            ts.correct_predictions,
            ts.prediction_accuracy,
            ts.avg_confidence,
            gs.team_wins,
            gs.team_losses
        FROM team_stats ts
        LEFT JOIN game_stats gs ON ts.team = gs.team
        ORDER BY ts.prediction_accuracy DESC, ts.predictions_made DESC
        LIMIT 50
    """
    
    top_teams_df = db.fetch_df(team_accuracy_query, (
        current_season, today, current_season, today, current_season, today, current_season, today
    ))
    
    # Add display names and conferences from teams table
    teams_df = db.fetch_df("SELECT team_id, display_name, conference FROM teams")
    top_teams_df = top_teams_df.merge(
        teams_df,
        left_on='team',
        right_on='team_id',
        how='left'
    )
    
    # Clean up for JSON
    top_teams_data = []
    for _, row in top_teams_df.iterrows():
        team_data = {
            'team_id': row['team'],
            'display_name': row['display_name'] if pd.notna(row.get('display_name')) else row['team'],
            'conference': row['conference'] if pd.notna(row.get('conference')) else None,
            'predictions_made': int(row['predictions_made']),
            'correct_predictions': int(row['correct_predictions']),
            'prediction_accuracy': float(row['prediction_accuracy']),
            'avg_confidence': float(row['avg_confidence']),
            'team_wins': int(row['team_wins']) if pd.notna(row['team_wins']) else 0,
            'team_losses': int(row['team_losses']) if pd.notna(row['team_losses']) else 0
        }
        top_teams_data.append(team_data)
    
    with open(output_dir / 'top_teams.json', 'w') as f:
        json.dump(top_teams_data, f, indent=2, default=json_serial)
    print(f"   ✓ Exported top {len(top_teams_data)} teams")
    
    # =========================================================================
    # 8. Export Prediction History (Complete 2025-26 Season)
    # =========================================================================
    print("\n8. Exporting prediction history...")
    
    # Get ALL completed predictions from current season (2025-26)
    current_season = "2025-26"
    today = datetime.now().date()
    
    season_predictions_query = """
        WITH first_predictions AS (
            SELECT 
                p.game_id,
                MIN(p.id) as first_prediction_id
            FROM predictions p
            JOIN games g ON p.game_id = g.game_id
            WHERE g.season = ?
              AND g.game_status = 'Final'
              AND g.date <= ?
              AND p.predicted_winner IS NOT NULL
            GROUP BY p.game_id
        )
        SELECT 
            p.*,
            g.date as game_date,
            g.home_team,
            g.away_team,
            g.home_score,
            g.away_score,
            g.game_status,
            g.season
        FROM predictions p
        JOIN games g ON p.game_id = g.game_id
        JOIN first_predictions fp ON p.id = fp.first_prediction_id
        WHERE g.season = ?
          AND g.game_status = 'Final'
          AND g.date <= ?
          AND p.predicted_winner IS NOT NULL
        ORDER BY g.date DESC
    """
    
    history_df = db.fetch_df(season_predictions_query, (current_season, today, current_season, today))
    
    if not history_df.empty:
        history_data = history_df.to_dict('records')
        
        # Clean up
        for record in history_data:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
        
        with open(output_dir / 'prediction_history.json', 'w') as f:
            json.dump(history_data, f, indent=2, default=json_serial)
        print(f"   ✓ Exported {len(history_data)} predictions from {current_season} season")
    else:
        with open(output_dir / 'prediction_history.json', 'w') as f:
            json.dump([], f)
        print("   ⚠️ No prediction history available")
    
    # =========================================================================
    # 9. Export Cumulative Profit (For charts)
    # =========================================================================
    print("\n9. Exporting profit timeline...")
    
    cumulative_profit = betting_repo.get_cumulative_profit()
    with open(output_dir / 'cumulative_profit.json', 'w') as f:
        json.dump(cumulative_profit, f, indent=2, default=json_serial)
    print(f"   ✓ Exported {len(cumulative_profit)} profit data points")
    
    # =========================================================================
    # 10. Export Metadata (Last update time, stats)
    # =========================================================================
    print("\n10. Exporting metadata...")
    
    stats = games_repo.get_game_count_by_status()
    total_teams = len(teams_repo.get_all_teams())
    
    metadata = {
        'last_updated': datetime.now().isoformat(),
        'database_stats': {
            'total_games': sum(stats.values()),
            'games_by_status': stats,
            'total_teams': total_teams,
            'total_predictions': len(pred_repo.get_prediction_log_df())
        },
        'current_season': current_season,
        'data_source': 'DuckDB via daily pipeline',
        'update_frequency': 'Daily via GitHub Actions'
    }
    
    with open(output_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2, default=json_serial)
    print(f"   ✓ Exported metadata")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "="*80)
    print("EXPORT COMPLETE")
    print("="*80)
    print(f"\nExported files to: {output_dir}")
    print("\nFiles created:")
    for json_file in sorted(output_dir.glob('*.json')):
        size_kb = json_file.stat().st_size / 1024
        print(f"  ✓ {json_file.name:<30} ({size_kb:>6.1f} KB)")
    
    total_size = sum(f.stat().st_size for f in output_dir.glob('*.json'))
    print(f"\nTotal size: {total_size / 1024:.1f} KB")
    print("\n✅ Frontend can now read these JSON files directly!")
    print("="*80)
    
    db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Export database to JSON files')
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for JSON files'
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) if args.output_dir else None
    export_to_json(output_dir)


if __name__ == '__main__':
    main()
