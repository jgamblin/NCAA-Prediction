#!/usr/bin/env python3
"""
Update README.md with current model performance metrics.
Run this after model tuning or when accuracy data changes.
"""

import pandas as pd
import json
import os
from datetime import datetime

def update_readme_model_stats():
    """Update the Model Evaluation section in README.md with current stats."""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, 'data')
    readme_path = os.path.join(project_root, 'README.md')
    
    print("="*80)
    print("UPDATING README MODEL EVALUATION")
    print("="*80)
    print()
    
    # Load accuracy report
    accuracy_path = os.path.join(data_dir, 'Accuracy_Report.csv')
    has_accuracy_data = False
    
    if os.path.exists(accuracy_path):
        accuracy_df = pd.read_csv(accuracy_path)
        
        # Calculate current metrics if we have completed predictions
        if len(accuracy_df) > 0:
            has_accuracy_data = True
            overall_accuracy = accuracy_df['correct'].mean()
            total_predictions = len(accuracy_df)
            
            # Calculate by confidence level
            high_conf = accuracy_df[accuracy_df['confidence'] >= 0.7]
            med_conf = accuracy_df[(accuracy_df['confidence'] >= 0.6) & (accuracy_df['confidence'] < 0.7)]
            low_conf = accuracy_df[accuracy_df['confidence'] < 0.6]
            
            high_acc = high_conf['correct'].mean() if len(high_conf) > 0 else 0
            med_acc = med_conf['correct'].mean() if len(med_conf) > 0 else 0
            low_acc = low_conf['correct'].mean() if len(low_conf) > 0 else 0
        else:
            print("⚠️  No completed predictions yet (games pending)")
            overall_accuracy = 0
            total_predictions = 0
            high_conf = med_conf = low_conf = pd.DataFrame()
            high_acc = med_acc = low_acc = 0
    else:
        print("⚠️  No accuracy report found yet")
        overall_accuracy = 0
        total_predictions = 0
        high_conf = med_conf = low_conf = pd.DataFrame()
        high_acc = med_acc = low_acc = 0
    
    # Load training data stats
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    if os.path.exists(completed_path):
        completed_df = pd.read_csv(completed_path)
        total_training_games = len(completed_df)
        
        # Get season breakdown
        if 'season' in completed_df.columns:
            current_season_games = len(completed_df[completed_df['season'] == '2025-26'])
        else:
            current_season_games = 0
    else:
        total_training_games = 0
        current_season_games = 0
    
    # Load tuning log if available
    tuning_path = os.path.join(data_dir, 'Model_Tuning_Log.json')
    current_season_accuracy = None
    if os.path.exists(tuning_path):
        with open(tuning_path, 'r') as f:
            tuning_log = json.load(f)
            if isinstance(tuning_log, list) and len(tuning_log) > 0:
                latest_tune = tuning_log[-1]
                current_season_accuracy = latest_tune.get('current_season_accuracy')
    
    print(f"✓ Loaded metrics:")
    if has_accuracy_data:
        print(f"  - Overall accuracy: {overall_accuracy:.1%} ({total_predictions} predictions)")
    else:
        print(f"  - No completed predictions yet")
    print(f"  - Training games: {total_training_games:,}")
    print(f"  - Current season games: {current_season_games:,}")
    if current_season_accuracy:
        print(f"  - Current season tuning accuracy: {current_season_accuracy:.1%}")
    
    # Build new Model Evaluation section
    new_section = []
    new_section.append("## 📈 Model Evaluation")
    new_section.append("")
    new_section.append("### Current Performance")
    new_section.append("")
    
    if has_accuracy_data:
        new_section.append(f"- **Overall Accuracy**: {overall_accuracy:.1%} (on {total_predictions:,} predictions)")
    else:
        new_section.append(f"- **Overall Accuracy**: Testing in progress ({total_predictions} predictions tracked)")
    
    if current_season_accuracy:
        new_section.append(f"- **Current Season (2025-26) Tuning**: {current_season_accuracy:.1%} accuracy on training data")
    
    new_section.append(f"- **Training Data**: {total_training_games:,} games")
    new_section.append(f"  - Current season: {current_season_games:,} games")
    new_section.append(f"  - Historical: {total_training_games - current_season_games:,} games")
    new_section.append("")
    
    if has_accuracy_data:
        new_section.append("")
        new_section.append("### Accuracy by Confidence Level")
        new_section.append("")
        new_section.append("| Confidence | Accuracy | Games |")
        new_section.append("|------------|----------|-------|")
        new_section.append(f"| High (≥70%) | {high_acc:.1%} | {len(high_conf):,} |")
        new_section.append(f"| Medium (60-70%) | {med_acc:.1%} | {len(med_conf):,} |")
        new_section.append(f"| Low (<60%) | {low_acc:.1%} | {len(low_conf):,} |")
    new_section.append("")
    
    new_section.append("### Model Configuration")
    new_section.append("")
    new_section.append("- **Algorithm**: Random Forest Classifier")
    new_section.append("- **Features**: Team embeddings, AP rankings, neutral site indicator (5 features)")
    new_section.append("- **Training Strategy**: Time-weighted (10x current season, exponential decay for older)")
    new_section.append("- **Hyperparameters**: Auto-tuned weekly via RandomForestClassifier optimization")
    new_section.append("")
    new_section.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    
    # Read current README
    with open(readme_path, 'r') as f:
        readme_lines = f.readlines()
    
    # Find Model Evaluation section
    start_idx = None
    end_idx = None
    
    for i, line in enumerate(readme_lines):
        if '## 📈 Model Evaluation' in line:
            start_idx = i
        elif start_idx is not None and line.startswith('## '):
            end_idx = i
            break
    
    if start_idx is None:
        print("✗ Could not find Model Evaluation section in README")
        return
    
    # If no end found, assume it goes to the next section or end of file
    if end_idx is None:
        # Look for next major section
        for i in range(start_idx + 1, len(readme_lines)):
            if readme_lines[i].startswith('## '):
                end_idx = i
                break
        if end_idx is None:
            end_idx = len(readme_lines)
    
    # Replace section
    new_readme = (
        readme_lines[:start_idx] +
        [line + '\n' for line in new_section] +
        ['\n'] +
        readme_lines[end_idx:]
    )
    
    # Write updated README
    with open(readme_path, 'w') as f:
        f.writelines(new_readme)
    
    print(f"\n✓ Updated {readme_path}")
    print("  - Model Evaluation section refreshed with current stats")
    print("="*80)

if __name__ == "__main__":
    update_readme_model_stats()
