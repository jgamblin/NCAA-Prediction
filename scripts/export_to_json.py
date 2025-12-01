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
    with open(output_dir / 'value_bets.json', 'w') as f:
        json.dump(value_bets, f, indent=2, default=json_serial)
    print(f"   ✓ Exported {len(value_bets)} value bets")
    
    # =========================================================================
    # 6. Export Accuracy Metrics
    # =========================================================================
    print("\n6. Exporting accuracy metrics...")
    
    overall_accuracy = pred_repo.calculate_accuracy()
    with open(output_dir / 'accuracy_overall.json', 'w') as f:
        json.dump(overall_accuracy, f, indent=2, default=json_serial)
    print(f"   ✓ Overall accuracy: {overall_accuracy.get('accuracy', 0):.1%}")
    
    # High confidence accuracy
    high_conf_accuracy = pred_repo.calculate_accuracy(min_confidence=0.65)
    with open(output_dir / 'accuracy_high_confidence.json', 'w') as f:
        json.dump(high_conf_accuracy, f, indent=2, default=json_serial)
    print(f"   ✓ High confidence (≥65%): {high_conf_accuracy.get('accuracy', 0):.1%}")
    
    # =========================================================================
    # 7. Export Team Statistics (Top performers)
    # =========================================================================
    print("\n7. Exporting team statistics...")
    
    current_season = "2024-25"
    top_teams = features_repo.get_top_teams_by_metric(
        season=current_season,
        metric='rolling_win_pct_10',
        limit=50
    )
    
    # Clean up for JSON
    top_teams_data = []
    for team in top_teams:
        team_data = dict(team)
        for key, value in team_data.items():
            if pd.isna(value):
                team_data[key] = None
        top_teams_data.append(team_data)
    
    with open(output_dir / 'top_teams.json', 'w') as f:
        json.dump(top_teams_data, f, indent=2, default=json_serial)
    print(f"   ✓ Exported top {len(top_teams_data)} teams")
    
    # =========================================================================
    # 8. Export Prediction History (Recent)
    # =========================================================================
    print("\n8. Exporting prediction history...")
    
    # Get last 100 predictions with results
    history_df = pred_repo.get_predictions_with_results()
    if not history_df.empty:
        history_df = history_df.head(100)
        history_data = history_df.to_dict('records')
        
        # Clean up
        for record in history_data:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
        
        with open(output_dir / 'prediction_history.json', 'w') as f:
            json.dump(history_data, f, indent=2, default=json_serial)
        print(f"   ✓ Exported {len(history_data)} historical predictions")
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
