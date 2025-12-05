#!/usr/bin/env python3
"""
Analyze Database Size

Run this to understand database composition and make informed decisions
about splitting strategies.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db_connection
import os


def format_bytes(bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def analyze_database_size():
    """Analyze database to inform splitting decisions."""
    
    print("="*80)
    print("DATABASE SIZE ANALYSIS")
    print("="*80)
    print()
    
    db = get_db_connection()
    db_path = Path(__file__).parent.parent / 'data' / 'ncaa_predictions.duckdb'
    
    # Overall file size
    if db_path.exists():
        file_size = os.path.getsize(db_path)
        print(f"Database file: {db_path.name}")
        print(f"Total size: {format_bytes(file_size)}")
        print(f"GitHub limit: 50.00 MB")
        print(f"Over limit by: {format_bytes(file_size - 50*1024*1024)}")
        print()
    
    # Row counts by table
    print("="*80)
    print("ROW COUNTS BY TABLE")
    print("="*80)
    
    tables = ['games', 'predictions', 'teams', 'team_features', 'bets', 
              'parlays', 'parlay_legs', 'accuracy_metrics', 'drift_metrics']
    
    table_stats = []
    for table in tables:
        try:
            result = db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
            count = result['count'] if result else 0
            table_stats.append((table, count))
            print(f"  {table:<20} {count:>10,} rows")
        except Exception as e:
            print(f"  {table:<20} {'N/A':>10} (table may not exist)")
    
    print()
    
    # Games by season
    print("="*80)
    print("GAMES BY SEASON")
    print("="*80)
    
    games_by_season = db.fetch_df("""
        SELECT 
            season,
            game_status,
            COUNT(*) as game_count
        FROM games
        GROUP BY season, game_status
        ORDER BY season DESC, game_status
    """)
    
    print(games_by_season.to_string(index=False))
    print()
    
    # Total per season
    season_totals = db.fetch_df("""
        SELECT 
            season,
            COUNT(*) as total_games
        FROM games
        GROUP BY season
        ORDER BY season DESC
    """)
    
    print("\nTotal games per season:")
    for _, row in season_totals.iterrows():
        print(f"  {row['season']}: {row['total_games']:,} games")
    print()
    
    # Predictions by season
    print("="*80)
    print("PREDICTIONS BY SEASON")
    print("="*80)
    
    pred_by_season = db.fetch_df("""
        SELECT 
            g.season,
            COUNT(p.id) as prediction_count,
            COUNT(DISTINCT p.game_id) as unique_games
        FROM predictions p
        JOIN games g ON p.game_id = g.game_id
        GROUP BY g.season
        ORDER BY g.season DESC
    """)
    
    print(pred_by_season.to_string(index=False))
    print()
    
    # Estimate size by season
    print("="*80)
    print("ESTIMATED SIZE REDUCTION FROM SEASON SPLIT")
    print("="*80)
    
    total_games = sum(season_totals['total_games'])
    current_season_games = season_totals[season_totals['season'] == '2025-26']['total_games'].values[0] if len(season_totals[season_totals['season'] == '2025-26']) > 0 else 0
    
    estimated_reduction_pct = ((total_games - current_season_games) / total_games * 100) if total_games > 0 else 0
    estimated_new_size = file_size * (current_season_games / total_games) if total_games > 0 else file_size
    
    print(f"\nIf we keep ONLY 2025-26 season:")
    print(f"  Current total games: {total_games:,}")
    print(f"  Current season games: {current_season_games:,}")
    print(f"  Estimated reduction: {estimated_reduction_pct:.1f}%")
    print(f"  Estimated new size: {format_bytes(estimated_new_size)}")
    print(f"  Under 50MB limit: {'✅ Yes' if estimated_new_size < 50*1024*1024 else '❌ No'}")
    print()
    
    # Recommendations
    print("="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print()
    
    if estimated_new_size < 50*1024*1024:
        print("✅ Season split should bring DB under 50MB limit")
        print()
        print("Recommended approach:")
        print("  1. Create ncaa_predictions_2025_26.duckdb (current season)")
        print("  2. Archive older seasons to GitHub Releases")
        print("  3. Update pipeline to use current season DB")
        print()
    else:
        print("⚠️  Season split alone may not be enough")
        print()
        print("Consider:")
        print("  1. Season split + Git LFS")
        print("  2. Hot/cold data separation")
        print("  3. More aggressive data pruning")
        print()
    
    # Betting data
    print("="*80)
    print("BETTING DATA")
    print("="*80)
    
    betting_stats = db.fetch_df("""
        SELECT 
            COUNT(*) as total_bets,
            SUM(CASE WHEN settled_at IS NOT NULL THEN 1 ELSE 0 END) as settled,
            SUM(CASE WHEN settled_at IS NULL THEN 1 ELSE 0 END) as unsettled
        FROM bets
    """)
    
    if not betting_stats.empty:
        print(betting_stats.to_string(index=False))
        print()
        print("Note: Settled bets from old seasons can be archived")
    else:
        print("No betting data found")
    
    print()
    print("="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print()
    print("Next steps:")
    print("  1. Review docs/DATABASE_SPLITTING_PLAN.md")
    print("  2. Choose splitting strategy")
    print("  3. Create migration script")
    print()
    
    db.close()


if __name__ == '__main__':
    analyze_database_size()
