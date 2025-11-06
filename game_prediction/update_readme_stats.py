#!/usr/bin/env python3
"""
Update README.md with current model performance metrics.
Run this after model tuning or when accuracy data changes.
"""

import pandas as pd
import json
import os
import sys
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calculate_streak import calculate_perfect_streak, get_streak_emoji
try:  # pragma: no cover
    from config.load_config import get_config_version
    from config.versioning import get_commit_hash
    _config_version = get_config_version()
    _commit_hash = get_commit_hash()
except Exception:  # noqa: BLE001
    _config_version = 'unknown'
    _commit_hash = 'unknown'

def resolve_lineage(data_dir: str) -> tuple[str,str]:
    """Return (config_version, commit_hash) with fallbacks.

    Priority:
      1. Imported values (if not 'unknown')
      2. First non-null row in NCAA_Game_Predictions.csv
      3. Accuracy_Report.csv (latest row)
      4. Fallback 'unknown'
    """
    cfg = _config_version
    ch = _commit_hash
    try:
        if (cfg == 'unknown' or ch == 'unknown'):
            pred_path = os.path.join(data_dir,'NCAA_Game_Predictions.csv')
            if os.path.exists(pred_path):
                pred_df = pd.read_csv(pred_path, nrows=100)
                if 'config_version' in pred_df.columns:
                    cfg_val = pred_df['config_version'].dropna().astype(str).head(1)
                    if not cfg_val.empty:
                        cfg = cfg_val.iloc[0]
                if 'commit_hash' in pred_df.columns:
                    ch_val = pred_df['commit_hash'].dropna().astype(str).head(1)
                    if not ch_val.empty:
                        ch = ch_val.iloc[0]
        if (cfg == 'unknown' or ch == 'unknown'):
            acc_path = os.path.join(data_dir,'Accuracy_Report.csv')
            if os.path.exists(acc_path):
                acc_df = pd.read_csv(acc_path)
                if not acc_df.empty:
                    last = acc_df.tail(1)
                    if cfg == 'unknown' and 'config_version' in last.columns and pd.notna(last['config_version'].iloc[0]):
                        cfg = str(last['config_version'].iloc[0])
                    if ch == 'unknown' and 'commit_hash' in last.columns and pd.notna(last['commit_hash'].iloc[0]):
                        ch = str(last['commit_hash'].iloc[0])
    except Exception:  # noqa: BLE001
        pass
    return cfg, ch

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
        if len(accuracy_df) > 0 and accuracy_df['games_completed'].sum() > 0:
            has_accuracy_data = True
            total_predictions = int(accuracy_df['games_completed'].sum())
            total_correct = int(accuracy_df['correct_predictions'].sum())
            overall_accuracy = total_correct / total_predictions if total_predictions > 0 else 0
            
            # Note: Accuracy_Report.csv is daily aggregated data, 
            # so we can't break down by confidence level here
            high_conf = med_conf = low_conf = pd.DataFrame()
            high_acc = med_acc = low_acc = 0
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
    
    # Calculate high confidence streak
    streak, last_miss, total_perfect, streak_days = calculate_perfect_streak()
    streak_emoji = get_streak_emoji(streak)
    
    print(f"✓ Loaded metrics:")
    if has_accuracy_data:
        print(f"  - Overall accuracy: {overall_accuracy:.1%} ({total_predictions} predictions)")
    else:
        print(f"  - No completed predictions yet")
    print(f"  - Training games: {total_training_games:,}")
    print(f"  - Current season games: {current_season_games:,}")
    if current_season_accuracy:
        print(f"  - Current season tuning accuracy: {current_season_accuracy:.1%}")
    if streak > 0:
        print(f"  - High confidence streak: {streak} day(s) {streak_emoji}")
    
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
    
    # Add streak info if available
    if streak > 0:
        new_section.append(f"- **{streak_emoji} High Confidence Streak**: {streak} consecutive day(s) with perfect high confidence (≥70%) picks")
    
    if current_season_accuracy:
        new_section.append(f"- **Current Season (2025-26) Tuning**: {current_season_accuracy:.1%} accuracy on training data")
    
    new_section.append(f"- **Training Data**: {total_training_games:,} games")
    new_section.append(f"  - Current season: {current_season_games:,} games")
    new_section.append(f"  - Historical: {total_training_games - current_season_games:,} games")
    new_section.append("")
    
    new_section.append("### Model Configuration")
    new_section.append("")
    new_section.append("- **Algorithm**: Random Forest Classifier")
    new_section.append("- **Features**: Team embeddings, AP rankings, neutral site indicator (5 features)")
    new_section.append("- **Training Strategy**: Time-weighted (10x current season, exponential decay for older)")
    new_section.append("- **Hyperparameters**: Auto-tuned weekly via RandomForestClassifier optimization")
    new_section.append("")
    # Resolve lineage (fallback to predictions file values)
    resolved_cfg, resolved_commit = resolve_lineage(data_dir)
    new_section.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    new_section.append("")
    new_section.append("### Model Lineage")
    new_section.append("")
    new_section.append(f"- Config Version: `{resolved_cfg}`")
    new_section.append(f"- Commit Hash: `{resolved_commit}`")
    
    # Helper: update top banner "Current Predictions" line
    def update_current_predictions_banner(lines: list[str]) -> list[str]:
        banner_idx = None
        for i, line in enumerate(lines):
            if 'Current Predictions' in line:
                banner_idx = i
                break
        if banner_idx is None:
            return lines
        # Derive prediction date & count
        pred_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
        if os.path.exists(pred_path):
            try:
                pred_df = pd.read_csv(pred_path)
                game_count = len(pred_df)
                date_col = 'date' if 'date' in pred_df.columns else None
                pred_date = None
                if date_col:
                    # Prefer today if exists else earliest upcoming
                    today = datetime.utcnow().strftime('%Y-%m-%d')
                    if (pred_df[date_col] == today).any():
                        pred_date = today
                    else:
                        # choose earliest date
                        try:
                            pred_date = sorted(pred_df[date_col].dropna().unique())[0]
                        except Exception:
                            pred_date = today
                else:
                    pred_date = datetime.utcnow().strftime('%Y-%m-%d')
                # Format human readable date
                try:
                    pretty_date = datetime.strptime(pred_date, '%Y-%m-%d').strftime('%B %d, %Y')
                except Exception:
                    pretty_date = pred_date
                lines[banner_idx] = f"**Current Predictions**: {game_count} games for {pretty_date}\n"
            except Exception:
                pass
        # Remove stray double asterisks if any remained from earlier corruption
        lines[banner_idx] = lines[banner_idx].replace('**  ', '** ').replace('**\n','**\n')
        return lines

    # Read current README
    with open(readme_path, 'r') as f:
        readme_lines = f.readlines()
    # Update banner before altering evaluation section
    readme_lines = update_current_predictions_banner(readme_lines)
    
    # Identify ALL occurrences of Model Evaluation section
    heading_flag = '## 📈 Model Evaluation'
    indices = [i for i, line in enumerate(readme_lines) if heading_flag in line]
    if not indices:
        print("✗ Could not find Model Evaluation section in README")
        return
    first_idx = indices[0]
    # Determine end of first section (next top-level heading or EOF)
    end_first = None
    for i in range(first_idx + 1, len(readme_lines)):
        if readme_lines[i].startswith('## ') and heading_flag not in readme_lines[i]:
            end_first = i
            break
    if end_first is None:
        end_first = len(readme_lines)
    # Remove subsequent duplicate sections fully
    to_remove_ranges = []
    for dup_idx in indices[1:]:
        # find its end
        dup_end = None
        for j in range(dup_idx + 1, len(readme_lines)):
            if readme_lines[j].startswith('## '):
                dup_end = j
                break
        if dup_end is None:
            dup_end = len(readme_lines)
        to_remove_ranges.append((dup_idx, dup_end))
    # Build cleaned list excluding duplicate ranges
    cleaned = []
    skip_map = set()
    for start, end in to_remove_ranges:
        skip_map.update(range(start, end))
    for idx, line in enumerate(readme_lines):
        if idx in skip_map:
            continue
        cleaned.append(line)
    # Replace first section content
    new_readme = cleaned[:first_idx] + [l + '\n' for l in new_section] + ['\n'] + cleaned[end_first:]
    
    # After injecting evaluation section, re-run banner update (in case section replacement reintroduced old line)
    new_readme = update_current_predictions_banner(new_readme)

    # Write updated README
    with open(readme_path, 'w') as f:
        f.writelines(new_readme)
    
    print(f"\n✓ Updated {readme_path}")
    print("  - Model Evaluation section refreshed with current stats")
    print("="*80)

if __name__ == "__main__":
    update_readme_model_stats()
