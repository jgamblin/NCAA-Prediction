#!/usr/bin/env python3
"""
DEPRECATED: Use publish_artifacts.py instead.

This legacy script generated predictions.md with current predictions and accuracy.
It now simply delegates to publish_artifacts.py for backward compatibility.
Will be removed in a future cleanup.
"""

import pandas as pd
from datetime import datetime
import os
import sys
import subprocess

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calculate_streak import calculate_perfect_streak, get_streak_emoji

def generate_predictions_md():
    """Backward-compatible wrapper calling unified publisher."""
    try:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'publish_artifacts.py')
        result = subprocess.run(['python3', script, '--predictions-only'], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(result.stdout)
            return
        else:
            print(result.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"Fallback legacy generation path engaged due to error: {exc}")
    # If unified script fails, run legacy logic below.
    
    # Use absolute paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')
    output_file = os.path.join(project_root, 'predictions.md')
    
    # Get current timestamp
    now = datetime.now()
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S UTC')
    today = now.strftime('%Y-%m-%d')
    
    # Calculate high confidence streak
    streak, last_miss, total_perfect, streak_days = calculate_perfect_streak()
    streak_emoji = get_streak_emoji(streak)
    
    # Start building the markdown
    md = []
    md.append("# 🏀 NCAA Basketball Predictions")
    md.append("")
    md.append(f"**Last Updated**: {timestamp}")
    md.append("")
    
    # Add streak tracker if we have data
    if streak > 0:
        md.append(f"## {streak_emoji} High Confidence Streak")
        md.append("")
        md.append(f"**{streak} consecutive day(s)** with perfect high confidence (≥70%) predictions!")
        if last_miss:
            md.append(f"*(Last miss: {last_miss})*")
        md.append("")
    
    md.append("---")
    md.append("")
    
    # =========================================================================
    # Section 1: Today's Predictions
    # =========================================================================
    md.append("## 📅 Today's Predictions")
    md.append("")
    
    try:
        predictions = pd.read_csv(os.path.join(data_dir, 'NCAA_Game_Predictions.csv'))
        today_games = predictions[predictions['date'] == today].copy()
        
        if len(today_games) > 0:
            md.append(f"**{len(today_games)} games** predicted for **{today}**")
            md.append("")
            
            # Sort by confidence
            today_games = today_games.sort_values('confidence', ascending=False)
            
            # High confidence picks
            high = today_games[today_games['confidence'] >= 0.7]
            if len(high) > 0:
                md.append(f"### 🎯 High Confidence Picks (≥70%)")
                md.append("")
                md.append("| # | Winner | vs | Loser | Confidence |")
                md.append("|---|--------|----|----|------------|")
                for i, (_, game) in enumerate(high.iterrows(), 1):
                    winner = game['predicted_winner']
                    loser = game['home_team'] if winner == game['away_team'] else game['away_team']
                    conf = game['confidence']
                    md.append(f"| {i} | **{winner}** | vs | {loser} | {conf:.1%} |")
                md.append("")
            
            # Medium confidence picks
            medium = today_games[(today_games['confidence'] >= 0.6) & (today_games['confidence'] < 0.7)]
            if len(medium) > 0:
                md.append(f"### 📊 Medium Confidence Picks (60-70%)")
                md.append("")
                md.append("| # | Winner | vs | Loser | Confidence |")
                md.append("|---|--------|----|----|------------|")
                for i, (_, game) in enumerate(medium.iterrows(), 1):
                    winner = game['predicted_winner']
                    loser = game['home_team'] if winner == game['away_team'] else game['away_team']
                    conf = game['confidence']
                    md.append(f"| {i} | **{winner}** | vs | {loser} | {conf:.1%} |")
                md.append("")
            
            # Summary stats
            md.append("### 📈 Prediction Summary")
            md.append("")
            home_favored = len(today_games[today_games['predicted_home_win'] == 1])
            away_favored = len(today_games[today_games['predicted_home_win'] == 0])
            avg_conf = today_games['confidence'].mean()
            
            md.append(f"- **Total Games**: {len(today_games)}")
            md.append(f"- **Home Teams Favored**: {home_favored}")
            md.append(f"- **Away Teams Favored**: {away_favored}")
            md.append(f"- **Average Confidence**: {avg_conf:.1%}")
            md.append("")
            
            # Link to full CSV
            md.append("### 📋 View All Games")
            md.append("")
            md.append(f"**[→ See all {len(today_games)} predictions with details (CSV)](data/NCAA_Game_Predictions.csv)**")
            md.append("")
            md.append("The CSV includes game IDs, team names, probabilities, confidence scores, and game URLs.")
            md.append("")
            
        else:
            md.append(f"*No predictions available for {today}*")
            md.append("")
            md.append("Run `python3 daily_pipeline.py` to generate predictions.")
            md.append("")
    
    except FileNotFoundError:
        md.append("*No predictions file found*")
        md.append("")
        md.append("Run `python3 daily_pipeline.py` to generate predictions.")
        md.append("")
    
    md.append("---")
    md.append("")
    
    # =========================================================================
    # Section 2: Historical Accuracy
    # =========================================================================
    md.append("## 📊 Historical Accuracy")
    md.append("")
    
    try:
        accuracy_report = pd.read_csv(os.path.join(data_dir, 'Accuracy_Report.csv'))
        
        if len(accuracy_report) > 0:
            # Overall stats
            total_completed = accuracy_report['games_completed'].sum()
            total_correct = accuracy_report['correct_predictions'].sum()
            
            if total_completed > 0:
                overall_accuracy = total_correct / total_completed
                
                md.append("### 🎯 Overall Performance")
                md.append("")
                md.append(f"- **Total Predictions Evaluated**: {total_completed}")
                md.append(f"- **Correct Predictions**: {total_correct}")
                md.append(f"- **Overall Accuracy**: {overall_accuracy:.1%}")
                md.append("")
                
                # Recent performance (last 10 days)
                recent = accuracy_report.tail(10)
                recent_completed = recent['games_completed'].sum()
                recent_correct = recent['correct_predictions'].sum()
                
                if recent_completed > 0:
                    recent_accuracy = recent_correct / recent_completed
                    md.append("### 📅 Recent Performance (Last 10 Days)")
                    md.append("")
                    md.append(f"- **Games Evaluated**: {recent_completed}")
                    md.append(f"- **Correct Predictions**: {recent_correct}")
                    md.append(f"- **Accuracy**: {recent_accuracy:.1%}")
                    md.append("")
                
                # Daily breakdown (last 7 days)
                last_7 = accuracy_report.tail(7)
                if len(last_7) > 0:
                    md.append("### 📆 Daily Breakdown (Last 7 Days)")
                    md.append("")
                    md.append("| Date | Games | Correct | Accuracy | Avg Confidence |")
                    md.append("|------|-------|---------|----------|----------------|")
                    
                    for _, row in last_7.iterrows():
                        date = row['date']
                        games = int(row['games_completed']) if row['games_completed'] > 0 else 0
                        correct = int(row['correct_predictions']) if row['correct_predictions'] > 0 else 0
                        acc = row['accuracy'] if pd.notna(row['accuracy']) else 0.0
                        conf = row['avg_confidence'] if pd.notna(row['avg_confidence']) else 0.0
                        
                        if games > 0:
                            md.append(f"| {date} | {games} | {correct} | {acc:.1%} | {conf:.1%} |")
                        else:
                            md.append(f"| {date} | - | - | - | - |")
                    
                    md.append("")
            else:
                md.append("*No completed predictions to evaluate yet*")
                md.append("")
        else:
            md.append("*No accuracy data available yet*")
            md.append("")
    
    except FileNotFoundError:
        md.append("*No accuracy report found*")
        md.append("")
        md.append("Accuracy tracking will begin once predictions are made and games are completed.")
        md.append("")
    
    md.append("---")
    md.append("")
    
    # =========================================================================
    # Section 3: Model Information
    # =========================================================================
    md.append("## 🤖 Model Information")
    md.append("")
    
    try:
        completed_games = pd.read_csv(os.path.join(data_dir, 'Completed_Games.csv'))
        
        md.append(f"- **Training Data**: {len(completed_games):,} completed games")
        
        seasons = sorted(completed_games['season'].unique())
        md.append(f"- **Seasons**: {', '.join(seasons)}")
        
        date_range = f"{completed_games['game_day'].min()} to {completed_games['game_day'].max()}"
        md.append(f"- **Date Range**: {date_range}")
        
        md.append("- **Algorithm**: Random Forest Classifier")
        md.append("- **Features**: Team embeddings, rankings, neutral site indicator")
        md.append("")
    
    except FileNotFoundError:
        md.append("*Training data information unavailable*")
        md.append("")
    
    md.append("---")
    md.append("")
    
    # =========================================================================
    # Section 4: How to Use
    # =========================================================================
    md.append("## 🚀 How to Use")
    md.append("")
    md.append("### Running Predictions Locally")
    md.append("```bash")
    md.append("# Run the daily pipeline")
    md.append("python3 daily_pipeline.py")
    md.append("")
    md.append("# View predictions")
    md.append("python3 view_predictions.py")
    md.append("```")
    md.append("")
    md.append("### Automation")
    md.append("This repository uses GitHub Actions to automatically:")
    md.append("1. Scrape completed and upcoming games from ESPN daily")
    md.append("2. Update training data with completed games")
    md.append("3. Generate predictions for upcoming games")
    md.append("4. Track accuracy of previous predictions")
    md.append("5. Update this predictions.md file")
    md.append("")
    md.append("---")
    md.append("")
    
    # =========================================================================
    # Section 5: Data Sources
    # =========================================================================
    md.append("## 📚 Data Sources")
    md.append("")
    md.append("- **Historical Data**: [ncaahoopR_data](https://github.com/lbenz730/ncaahoopR_data) (2020-2025)")
    md.append("- **Current Season**: ESPN.com (real-time scraping)")
    md.append("")
    md.append("---")
    md.append("")
    
    md.append("*This file is automatically generated by `generate_predictions_md.py`*")
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(md))
    
    print(f"✓ Generated {output_file}")
    print(f"  - Timestamp: {timestamp}")
    print(f"  - Today's date: {today}")

if __name__ == "__main__":
    generate_predictions_md()
