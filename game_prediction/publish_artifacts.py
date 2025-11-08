#!/usr/bin/env python3
"""Unified publishing script for README.md and predictions.md.

Modes:
  (default) Full: update README banner + evaluation section AND regenerate predictions.md
  --banner-only: only refresh Current Predictions banner in README (fast path)
  --readme-only: refresh banner + evaluation section (no predictions.md regeneration)
  --predictions-only: regenerate predictions.md (no README changes)

This consolidates logic previously split across:
  - generate_predictions_md.py
  - update_readme_stats.py

Downstream callers (e.g. daily_pipeline.py) should prefer this script.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
import json
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
README_PATH = os.path.join(PROJECT_ROOT, 'README.md')
PRED_MD_PATH = os.path.join(PROJECT_ROOT, 'predictions.md')

sys.path.insert(0, SCRIPT_DIR)
try:  # lineage imports (optional)
    from config.load_config import get_config_version  # type: ignore
    from config.versioning import get_commit_hash      # type: ignore
    CONFIG_VERSION = get_config_version()
    COMMIT_HASH = get_commit_hash()
except Exception:  # noqa: BLE001
    CONFIG_VERSION = 'unknown'
    COMMIT_HASH = 'unknown'

from calculate_streak import calculate_perfect_streak, get_streak_emoji  # noqa: E402
from typing import List, Dict, Any

# --------------------------------------------------------------------------------------
# Extended streak calculations (top1 pick, top5 picks)
# --------------------------------------------------------------------------------------
def compute_top_pick_streaks(details_path: str) -> Dict[str, Any]:
    """Compute streaks for #1 pick correctness and top-5 picks all correct.

    Returns dict with:
      top1_streak: consecutive days most recent backward with top1 prediction correct
      top1_last_miss: date of last failure of top1 (or None)
      top5_streak: consecutive days with all top5 predictions correct (requires >=5 predictions that day)
      top5_last_miss: date of last failure in top5 (or None)
      recent_days: list of dicts {date, top1_correct, top5_all_correct, games}
    Days with <1 prediction are ignored; days with <5 predictions excluded from top5 streak (not counted, do not break).
    """
    if not os.path.exists(details_path):
        return {
            'top1_streak': 0,
            'top1_last_miss': None,
            'top5_streak': 0,
            'top5_last_miss': None,
            'recent_days': []
        }
    try:
        df = pd.read_csv(details_path)
    except Exception:
        return {
            'top1_streak': 0,
            'top1_last_miss': None,
            'top5_streak': 0,
            'top5_last_miss': None,
            'recent_days': []
        }
    if df.empty or 'date' not in df.columns or 'confidence' not in df.columns or 'correct' not in df.columns:
        return {
            'top1_streak': 0,
            'top1_last_miss': None,
            'top5_streak': 0,
            'top5_last_miss': None,
            'recent_days': []
        }
    df['confidence'] = df['confidence'].astype(float)
    # Group by date
    daily = []
    for date, g in df.groupby('date'):
        g_sorted = g.sort_values('confidence', ascending=False)
        top1_correct = int(g_sorted.iloc[0]['correct']) if len(g_sorted) > 0 else 0
        top5_all_correct = False
        if len(g_sorted) >= 5:
            top5_all_correct = g_sorted.head(5)['correct'].sum() == 5
        daily.append({
            'date': date,
            'top1_correct': bool(top1_correct),
            'top5_all_correct': bool(top5_all_correct),
            'games': len(g_sorted)
        })
    # Sort by date descending for streak calculation
    daily_sorted = sorted(daily, key=lambda x: x['date'], reverse=True)
    top1_streak = 0
    top1_last_miss = None
    for d in daily_sorted:
        if d['top1_correct']:
            top1_streak += 1
        else:
            top1_last_miss = d['date']
            break
    top5_streak = 0
    top5_last_miss = None
    for d in daily_sorted:
        # Skip days with <5 predictions for top5 streak (do not break streak)
        if d['games'] < 5:
            continue
        if d['top5_all_correct']:
            top5_streak += 1
        else:
            top5_last_miss = d['date']
            break
    # Recent days oldest to newest (limit 7 for display)
    recent_display = sorted(daily_sorted, key=lambda x: x['date'])[-7:]
    return {
        'top1_streak': top1_streak,
        'top1_last_miss': top1_last_miss,
        'top5_streak': top5_streak,
        'top5_last_miss': top5_last_miss,
        'recent_days': recent_display
    }

# --------------------------------------------------------------------------------------
# Lineage resolution (fallback to CSV columns if imports gave 'unknown')
# --------------------------------------------------------------------------------------
def resolve_lineage() -> tuple[str, str]:
    cfg, ch = CONFIG_VERSION, COMMIT_HASH
    try:
        pred_path = os.path.join(DATA_DIR, 'NCAA_Game_Predictions.csv')
        if (cfg == 'unknown' or ch == 'unknown') and os.path.exists(pred_path):
            pred_df = pd.read_csv(pred_path, nrows=200)
            if cfg == 'unknown' and 'config_version' in pred_df.columns:
                v = pred_df['config_version'].dropna().astype(str).head(1)
                if not v.empty:
                    cfg = v.iloc[0]
            if ch == 'unknown' and 'commit_hash' in pred_df.columns:
                v = pred_df['commit_hash'].dropna().astype(str).head(1)
                if not v.empty:
                    ch = v.iloc[0]
        if (cfg == 'unknown' or ch == 'unknown'):
            acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
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


# --------------------------------------------------------------------------------------
# Hero Stats Section Updater
# --------------------------------------------------------------------------------------
def _update_hero_stats(lines: list[str]) -> list[str]:
    """Update the At a Glance hero stats section with current metrics."""
    start_marker = '<!-- AUTO-UPDATED: Hero Stats'
    end_marker = '<!-- END AUTO-UPDATED: Hero Stats -->'
    
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_marker in line:
            start_idx = i
        elif end_marker in line and start_idx is not None:
            end_idx = i
            break
    
    if start_idx is None or end_idx is None:
        return lines  # Section not found, skip
    
    # Gather metrics
    acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
    overall_acc = 0.0
    total_preds = 0
    today_preds = 0
    
    if os.path.exists(acc_path):
        try:
            acc_df = pd.read_csv(acc_path)
            if not acc_df.empty and acc_df['games_completed'].sum() > 0:
                total_preds = int(acc_df['games_completed'].sum())
                total_correct = int(acc_df['correct_predictions'].sum())
                overall_acc = (total_correct / total_preds * 100) if total_preds else 0.0
        except Exception:
            pass
    
    # Get today's prediction count
    pred_path = os.path.join(DATA_DIR, 'NCAA_Game_Predictions.csv')
    if os.path.exists(pred_path):
        try:
            pred_df = pd.read_csv(pred_path)
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if 'date' in pred_df.columns:
                today_preds = len(pred_df[pred_df['date'] == today])
            else:
                today_preds = len(pred_df)
        except Exception:
            pass
    
    # Training data size
    train_games = 0
    completed_path = os.path.join(DATA_DIR, 'Completed_Games.csv')
    if os.path.exists(completed_path):
        try:
            cdf = pd.read_csv(completed_path)
            train_games = len(cdf)
        except Exception:
            pass
    
    # Get streak
    streak, _, _, _ = calculate_perfect_streak()
    
    # Build new section
    new_section = [
        start_marker + ' - Do not manually edit this section -->\n',
        '## 📊 At a Glance\n',
        '\n',
        f'🎯 **{overall_acc:.1f}% Accuracy** across {total_preds} predictions  \n',
        f'📈 **{train_games:,} Historical Games** powering model  \n',
        '🤖 **Automated Daily** at 12:00 PM UTC  \n',
        f'⚡ **{today_preds} Live Predictions** for today  \n',
        f'🔥 **{streak} Day Streak** of perfect high-confidence picks\n',
        '\n',
        end_marker + '\n'
    ]
    
    return lines[:start_idx] + new_section + lines[end_idx+1:]


# --------------------------------------------------------------------------------------
# Performance Dashboard Updater
# --------------------------------------------------------------------------------------
def _update_performance_dashboard(lines: list[str]) -> list[str]:
    """Update the 3-column performance dashboard with current metrics."""
    start_marker = '<!-- AUTO-UPDATED: Performance Dashboard'
    end_marker = '<!-- END AUTO-UPDATED: Performance Dashboard -->'
    
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_marker in line:
            start_idx = i
        elif end_marker in line and start_idx is not None:
            end_idx = i
            break
    
    if start_idx is None or end_idx is None:
        return lines
    
    # Gather all metrics
    acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
    overall_acc = 0.0
    total_preds = 0
    avg_conf = 0.0
    
    if os.path.exists(acc_path):
        try:
            acc_df = pd.read_csv(acc_path)
            if not acc_df.empty and acc_df['games_completed'].sum() > 0:
                total_preds = int(acc_df['games_completed'].sum())
                total_correct = int(acc_df['correct_predictions'].sum())
                overall_acc = (total_correct / total_preds * 100) if total_preds else 0.0
                if 'avg_confidence' in acc_df.columns:
                    avg_conf = acc_df['avg_confidence'].mean() * 100
        except Exception:
            pass
    
    # Training data
    train_games = 0
    current_season_games = 0
    completed_path = os.path.join(DATA_DIR, 'Completed_Games.csv')
    if os.path.exists(completed_path):
        try:
            cdf = pd.read_csv(completed_path)
            train_games = len(cdf)
            if 'season' in cdf.columns:
                current_season_games = (cdf['season'] == '2025-26').sum()
        except Exception:
            pass
    
    # Tuning accuracy
    tuning_accuracy = None
    tuning_path = os.path.join(DATA_DIR, 'Model_Tuning_Log.json')
    if os.path.exists(tuning_path):
        try:
            with open(tuning_path) as f:
                log = json.load(f)
            if isinstance(log, list) and log:
                tuning_accuracy = log[-1].get('current_season_accuracy', 0) * 100
        except Exception:
            pass
    
    # Feature importance
    top_feature = "N/A"
    top_importance = 0.0
    feat_path = os.path.join(DATA_DIR, 'Simple_Feature_Importance.csv')
    if os.path.exists(feat_path):
        try:
            feat_df = pd.read_csv(feat_path)
            if not feat_df.empty:
                top_row = feat_df.sort_values('importance', ascending=False).iloc[0]
                top_feature = top_row['feature']
                top_importance = top_row['importance'] * 100
        except Exception:
            pass
    
    # Feature store size
    feat_store_rows = 0
    feat_store_path = os.path.join(DATA_DIR, 'feature_store', 'feature_store.csv')
    if os.path.exists(feat_store_path):
        try:
            fs_df = pd.read_csv(feat_store_path)
            feat_store_rows = len(fs_df)
        except Exception:
            pass
    
    # Lineage
    cfg, ch = resolve_lineage()
    ch_short = ch[:7] if len(ch) >= 7 else ch
    
    # Calibration (Brier)
    brier_weighted = "N/A"
    calib_path = os.path.join(PROJECT_ROOT, 'docs', 'CALIBRATION_WEIGHTING_COMPARISON.md')
    if os.path.exists(calib_path):
        try:
            with open(calib_path) as cf:
                lines_calib = cf.readlines()
            brier_line = next((l for l in lines_calib if l.strip().startswith('| Brier Score')), None)
            if brier_line:
                parts = [p.strip() for p in brier_line.split('|') if p.strip()]
                if len(parts) >= 2:
                    brier_weighted = parts[1]
        except Exception:
            pass
    
    # Timestamp
    now = datetime.now(timezone.utc)
    timestamp = now.strftime('%Y-%m-%d %H:%M UTC')
    
    # Build new section
    tuning_str = f"{tuning_accuracy:.1f}% tuning accuracy" if tuning_accuracy else "N/A"
    
    new_section = [
        start_marker + ' - Do not manually edit this section -->\n',
        '## 📈 Performance Dashboard\n',
        '\n',
        '<table>\n',
        '<tr>\n',
        '<td width="33%">\n',
        '\n',
        '### Prediction Quality\n',
        f'- **Overall**: {overall_acc:.1f}% ({total_preds} games)\n',
        f'- **High Confidence**: {avg_conf:.1f}% avg\n',
        f'- **Current Season**: {tuning_str}\n',
        '- **Algorithm**: Random Forest (calibrated)\n',
        '\n',
        '</td>\n',
        '<td width="33%">\n',
        '\n',
        '### Data Scale\n',
        f'- **Total Games**: {train_games:,}\n',
        f'- **Current Season**: {current_season_games:,} games\n',
        '- **Unique Teams**: 1,287\n',
        f'- **Feature Store**: {feat_store_rows:,} rows\n',
        '\n',
        '</td>\n',
        '<td width="33%">\n',
        '\n',
        '### Monitoring\n',
        f'- **Top Feature**: `{top_feature}` ({top_importance:.1f}%)\n',
        f'- **Lineage**: `{cfg}` @ `{ch_short}`\n',
        f'- **Last Update**: {timestamp}\n',
        f'- **Calibration**: Brier {brier_weighted}\n',
        '\n',
        '</td>\n',
        '</tr>\n',
        '</table>\n',
        '\n',
        end_marker + '\n'
    ]
    
    return lines[:start_idx] + new_section + lines[end_idx+1:]


# --------------------------------------------------------------------------------------
# Recent Performance Table Updater
# --------------------------------------------------------------------------------------
def _update_recent_performance(lines: list[str]) -> list[str]:
    """Update the Last 7 Days Performance table."""
    start_marker = '<!-- AUTO-UPDATED: Recent Performance'
    end_marker = '<!-- END AUTO-UPDATED: Recent Performance -->'
    
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_marker in line:
            start_idx = i
        elif end_marker in line and start_idx is not None:
            end_idx = i
            break
    
    if start_idx is None or end_idx is None:
        return lines
    
    # Load accuracy report
    acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
    if not os.path.exists(acc_path):
        return lines
    
    try:
        acc_df = pd.read_csv(acc_path)
        last7 = acc_df.tail(7)
        
        new_section = [
            start_marker + ' - Do not manually edit this section -->\n',
            '## 📊 Last 7 Days Performance\n',
            '\n',
            '| Date | Predictions | Completed | Accuracy | Avg Confidence | Notes |\n',
            '|------|-------------|-----------|----------|----------------|-------|\n'
        ]
        
        for _, row in last7.iterrows():
            date = row.get('date', 'N/A')
            total = int(row.get('total_predictions', 0))
            completed = int(row.get('games_completed', 0))
            acc = row.get('accuracy', 0.0)
            conf = row.get('avg_confidence', 0.0)
            
            # Format date
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date_str = date_obj.strftime('%b %d')
            except Exception:
                date_str = date
            
            # Add trend indicators
            notes = ''
            if acc >= 0.95:
                notes = '🎯 Excellent'
            elif acc >= 0.85:
                notes = '✅'
            elif acc >= 0.75:
                notes = '📊'
            else:
                notes = '📉'
            
            if conf < 0.65:
                notes += ' Low confidence day'
            
            new_section.append(
                f'| {date_str} | {total} | {completed} | {acc*100:.1f}% | {conf*100:.1f}% | {notes} |\n'
            )
        
        new_section.extend([
            '\n',
            '_Accuracy variations reflect feature store building historical context for new season teams._\n',
            '\n',
            end_marker + '\n'
        ])
        
        return lines[:start_idx] + new_section + lines[end_idx+1:]
        
    except Exception:
        return lines


# --------------------------------------------------------------------------------------
# README banner updater
# --------------------------------------------------------------------------------------
def _update_readme_banner(lines: list[str]) -> list[str]:
    banner_idx = None
    for i, line in enumerate(lines):
        if 'Current Predictions' in line:
            banner_idx = i
            break
    if banner_idx is None:
        return lines
    pred_path = os.path.join(DATA_DIR, 'NCAA_Game_Predictions.csv')
    if os.path.exists(pred_path):
        try:
            df = pd.read_csv(pred_path)
            game_count = len(df)
            date_col = 'date' if 'date' in df.columns else None
            pred_date = None
            # Use timezone-aware UTC datetime (datetime.utcnow deprecated)
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if date_col and (df[date_col] == today).any():
                pred_date = today
            elif date_col:
                try:
                    pred_date = sorted(df[date_col].dropna().unique())[0]
                except Exception:
                    pred_date = today
            else:
                pred_date = today
            try:
                pretty_date = datetime.strptime(pred_date, '%Y-%m-%d').strftime('%B %d, %Y')
            except Exception:
                pretty_date = pred_date
            lines[banner_idx] = f"**Current Predictions**: {game_count} games for {pretty_date}\n"
        except Exception:
            pass
    return lines


# --------------------------------------------------------------------------------------
# README evaluation section refresh
# --------------------------------------------------------------------------------------
def refresh_readme_evaluation():
    if not os.path.exists(README_PATH):
        print("README.md not found; skipping evaluation update.")
        return
    
    # Read README once
    with open(README_PATH) as f:
        lines = f.readlines()
    
    # Apply all updates
    lines = _update_hero_stats(lines)
    lines = _update_performance_dashboard(lines)
    lines = _update_recent_performance(lines)
    lines = _update_readme_banner(lines)
    
    # Now update the old Model Evaluation section (keep for compatibility)
    # Load accuracy
    acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
    has_accuracy = False
    overall_accuracy = 0.0
    total_predictions = 0
    if os.path.exists(acc_path):
        acc_df = pd.read_csv(acc_path)
        if not acc_df.empty and acc_df['games_completed'].sum() > 0:
            has_accuracy = True
            total_predictions = int(acc_df['games_completed'].sum())
            total_correct = int(acc_df['correct_predictions'].sum())
            overall_accuracy = total_correct / total_predictions if total_predictions else 0.0
    # Training data
    train_games = 0
    current_season_games = 0
    completed_path = os.path.join(DATA_DIR, 'Completed_Games.csv')
    if os.path.exists(completed_path):
        cdf = pd.read_csv(completed_path)
        train_games = len(cdf)
        if 'season' in cdf.columns:
            current_season_games = (cdf['season'] == '2025-26').sum()
    tuning_accuracy = None
    tuning_path = os.path.join(DATA_DIR, 'Model_Tuning_Log.json')
    if os.path.exists(tuning_path):
        try:
            with open(tuning_path) as f:
                log = json.load(f)
            if isinstance(log, list) and log:
                tuning_accuracy = log[-1].get('current_season_accuracy')
        except Exception:
            pass
    streak, last_miss, _total_perfect, _streak_days = calculate_perfect_streak()
    streak_emoji = get_streak_emoji(streak)
    cfg, ch = resolve_lineage()
    new_section = []
    new_section.append("## 📈 Model Evaluation (Auto‑Updated)")
    new_section.append("")
    new_section.append("### Current Performance")
    new_section.append("")
    if has_accuracy:
        new_section.append(f"- **Overall Accuracy**: {overall_accuracy:.1%} (on {total_predictions:,} predictions)")
    else:
        new_section.append("- **Overall Accuracy**: Pending (no completed games tracked yet)")
    if streak > 0:
        miss_info = f" (last miss: {last_miss})" if last_miss else ""
        new_section.append(f"- **{streak_emoji} High Confidence Streak**: {streak} day(s){miss_info}")
    if tuning_accuracy is not None:
        new_section.append(f"- **Current Season (2025-26) Tuning**: {tuning_accuracy:.1%}")
    new_section.append(f"- **Training Data**: {train_games:,} games (current season: {current_season_games:,})")
    # Inject calibration metrics if comparison artifact exists
    calib_path = os.path.join(PROJECT_ROOT, 'docs', 'CALIBRATION_WEIGHTING_COMPARISON.md')
    if os.path.exists(calib_path):
        try:
            with open(calib_path) as cf:
                lines_calib = cf.readlines()
            brier_line = next((l for l in lines_calib if l.strip().startswith('| Brier Score')), None)
            ece_line = next((l for l in lines_calib if l.strip().startswith('| Expected Calibration Error')), None)
            if brier_line and ece_line:
                parts_brier = [p.strip() for p in brier_line.split('|') if p.strip()]
                parts_ece = [p.strip() for p in ece_line.split('|') if p.strip()]
                # Expected format: ['Metric','Weighted','Unweighted','Delta (W-U)']
                if len(parts_brier) >= 4 and len(parts_ece) >= 4:
                    wbrier, ubrier, dbrier = parts_brier[1], parts_brier[2], parts_brier[3]
                    wece, uece, dece = parts_ece[1], parts_ece[2], parts_ece[3]
                    new_section.append("- **Calibration (Brier)**: Weighted=" + wbrier + ", Unweighted=" + ubrier + " (Δ W-U: " + dbrier + ")")
                    new_section.append("- **Calibration (ECE)**: Weighted=" + wece + ", Unweighted=" + uece + " (Δ W-U: " + dece + ")")
                    new_section.append("  *Lower is better; weighted model emphasizes current season.*")
        except Exception:
            pass
    new_section.append("")
    new_section.append("### Lineage")
    new_section.append("")
    new_section.append(f"- Config Version: `{cfg}`")
    new_section.append(f"- Commit Hash: `{ch}`")
    new_section.append(f"*Refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    new_section.append("")
    # Replace first occurrence of evaluation heading in README
    heading = '## 📈 Model Evaluation'
    # Old heading variants from earlier rewrite
    alt_heading = '## 📈 Model Evaluation (Auto‑Updated)'
    candidates = [i for i,l in enumerate(lines) if (heading in l) or (alt_heading in l)]
    if not candidates:
        # append at end if missing
        new_lines = lines + [s + '\n' for s in new_section]
    else:
        start = candidates[0]
        end = len(lines)
        for i in range(start+1, len(lines)):
            if lines[i].startswith('## ') and ('Model Evaluation' not in lines[i]):
                end = i
                break
        new_lines = lines[:start] + [s + '\n' for s in new_section] + lines[end:]
    
    # Write updated README
    with open(README_PATH,'w') as f:
        f.writelines(new_lines)
    print(f"✓ README hero stats, dashboard, recent performance & evaluation updated (cfg={cfg}, commit={ch})")


# --------------------------------------------------------------------------------------
# Predictions markdown generator (elevated formatting)
# --------------------------------------------------------------------------------------
def generate_predictions_markdown():
    # timezone-aware UTC datetime (datetime.utcnow deprecated)
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    pretty_date = now.strftime('%A, %B %d, %Y')
    timestamp = now.strftime('%Y-%m-%d %H:%M UTC')
    cfg, ch = resolve_lineage()
    
    md: list[str] = []
    md.append('# 🏀 NCAA Basketball Predictions')
    md.append(f'## {pretty_date}')
    md.append('')
    
    # Load predictions
    pred_path = os.path.join(DATA_DIR, 'NCAA_Game_Predictions.csv')
    try:
        preds = pd.read_csv(pred_path)
    except FileNotFoundError:
        md.append('*No predictions available. Run `python3 daily_pipeline.py`.*')
        _write_md(md)
        print('✗ predictions CSV missing; wrote placeholder predictions.md')
        return
    
    # Filter today and upcoming
    today_games = preds[preds['date'] == today_str].copy() if 'date' in preds.columns else preds.copy()
    total_games = len(today_games)
    avg_conf = today_games['confidence'].mean() if total_games else 0.0
    
    # Get overall accuracy
    acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
    season_acc = 0.0
    if os.path.exists(acc_path):
        try:
            acc_df = pd.read_csv(acc_path)
            if not acc_df.empty and acc_df['games_completed'].sum() > 0:
                total_correct = int(acc_df['correct_predictions'].sum())
                total_preds = int(acc_df['games_completed'].sum())
                season_acc = (total_correct / total_preds) if total_preds else 0.0
        except Exception:
            pass
    
    # Streak info
    streak, _, _, _ = calculate_perfect_streak()
    details_path = os.path.join(DATA_DIR, 'Prediction_Details.csv')
    ext_streaks = compute_top_pick_streaks(details_path)
    
    # Hero stat bar
    md.append(f'📊 **{total_games} Games** | 🎯 **{avg_conf:.1%} Avg Confidence** | 🔥 **{ext_streaks["top1_streak"]}-Day Streak** | ⚡ **{season_acc:.1%} Season Accuracy**')
    md.append('')
    md.append('---')
    md.append('')
    
    # Featured Matchups - Top 3 + notable games
    if total_games > 0:
        sorted_games = today_games.sort_values('confidence', ascending=False)
        
        md.append('## � Featured Matchups')
        md.append('')
        md.append('### Top Confidence Picks')
        md.append('')
        
        # Top 3 with medals - each on its own line
        medals = ['🥇', '🥈', '🥉']
        for i, (_, game) in enumerate(sorted_games.head(3).iterrows()):
            winner = game['predicted_winner']
            loser = game['home_team'] if winner == game['away_team'] else game['away_team']
            conf = game['confidence']
            medal = medals[i] if i < 3 else f'{i+1}.'
            md.append(f'{medal} **{winner}** vs {loser} — **{conf:.1%}**  ')
        
        md.append('')
        
        # Games to Watch - smart selection (diverse + context-aware)
        if len(sorted_games) > 3:
            md.append('### Games to Watch')
            md.append('')
            
            watch_games = []
            already_featured = set()
            
            # Add top 3 to already featured
            for _, game in sorted_games.head(3).iterrows():
                key = f"{game['home_team']}|{game['away_team']}"
                already_featured.add(key)
            
            # Priority 1: Ranked matchups (both teams ranked)
            for _, game in sorted_games.iloc[3:].iterrows():
                if len(watch_games) >= 5:
                    break
                key = f"{game['home_team']}|{game['away_team']}"
                if key in already_featured:
                    continue
                
                home_ranked = 'home_rank' in game and pd.notna(game['home_rank']) and game['home_rank'] > 0
                away_ranked = 'away_rank' in game and pd.notna(game['away_rank']) and game['away_rank'] > 0
                
                if home_ranked and away_ranked:
                    watch_games.append((game, '🏆 Ranked matchup'))
                    already_featured.add(key)
            
            # Priority 2: Neutral site games (potential tournament/showcase)
            for _, game in sorted_games.iloc[3:].iterrows():
                if len(watch_games) >= 5:
                    break
                key = f"{game['home_team']}|{game['away_team']}"
                if key in already_featured:
                    continue
                
                is_neutral = 'is_neutral' in game and game['is_neutral'] == 1
                if is_neutral and game['confidence'] >= 0.85:
                    watch_games.append((game, '🏟️ Neutral site'))
                    already_featured.add(key)
            
            # Priority 3: Close games (confidence 75-85% = competitive)
            for _, game in sorted_games.iloc[3:].iterrows():
                if len(watch_games) >= 5:
                    break
                key = f"{game['home_team']}|{game['away_team']}"
                if key in already_featured:
                    continue
                
                if 0.75 <= game['confidence'] <= 0.85:
                    watch_games.append((game, '⚔️ Competitive'))
                    already_featured.add(key)
            
            # Priority 4: Major conference / high profile (one team ranked)
            for _, game in sorted_games.iloc[3:].iterrows():
                if len(watch_games) >= 5:
                    break
                key = f"{game['home_team']}|{game['away_team']}"
                if key in already_featured:
                    continue
                
                home_ranked = 'home_rank' in game and pd.notna(game['home_rank']) and game['home_rank'] > 0
                away_ranked = 'away_rank' in game and pd.notna(game['away_rank']) and game['away_rank'] > 0
                
                if (home_ranked or away_ranked) and game['confidence'] >= 0.85:
                    watch_games.append((game, '⭐ High-profile'))
                    already_featured.add(key)
            
            # Priority 5: Fill remaining with next highest confidence
            for _, game in sorted_games.iloc[3:].iterrows():
                if len(watch_games) >= 5:
                    break
                key = f"{game['home_team']}|{game['away_team']}"
                if key in already_featured:
                    continue
                
                watch_games.append((game, ''))
                already_featured.add(key)
            
            # Display games to watch
            for game, context in watch_games:
                winner = game['predicted_winner']
                loser = game['home_team'] if winner == game['away_team'] else game['away_team']
                conf = game['confidence']
                context_str = f' {context}' if context else ''
                md.append(f'- **{winner}** vs {loser} — {conf:.1%}{context_str}')
            
            md.append('')
        
        md.append('---')
        md.append('')
    
    # Predictions by confidence tier
    md.append('## 📊 All Predictions by Confidence')
    md.append('')
    
    # Group by confidence bands
    very_high = today_games[today_games['confidence'] >= 0.90]
    high = today_games[(today_games['confidence'] >= 0.80) & (today_games['confidence'] < 0.90)]
    medium = today_games[(today_games['confidence'] >= 0.70) & (today_games['confidence'] < 0.80)]
    lower = today_games[today_games['confidence'] < 0.70]
    
    def confidence_table(df: pd.DataFrame, title: str, emoji: str, show_all: bool = False):
        if df.empty:
            return
        count = len(df)
        md.append(f'### {emoji} {title} — {count} games')
        md.append('')
        
        # Show top 10 or all depending on flag
        display_df = df if show_all or count <= 10 else df.head(10)
        
        md.append('| Winner | Opponent | Confidence |')
        md.append('|--------|----------|------------|')
        for _, g in display_df.sort_values('confidence', ascending=False).iterrows():
            winner = g['predicted_winner']
            loser = g['home_team'] if winner == g['away_team'] else g['away_team']
            md.append(f'| **{winner}** | {loser} | {g["confidence"]:.1%} |')
        
        if not show_all and count > 10:
            md.append(f'| ... | *{count - 10} more games* | ... |')
        
        md.append('')
    
    confidence_table(very_high, 'Very High Confidence (≥90%)', '🔥')
    confidence_table(high, 'High Confidence (80-90%)', '⭐')
    confidence_table(medium, 'Medium Confidence (70-80%)', '📊', show_all=True)
    confidence_table(lower, 'Lower Confidence (<70%)', '⚠️', show_all=True)
    
    md.append('� *Showing top 10 for large groups. [View full predictions CSV](data/NCAA_Game_Predictions.csv) for complete list.*')
    md.append('')
    md.append('---')
    md.append('')
    # Historical accuracy summary
    acc_path = os.path.join(DATA_DIR, 'Accuracy_Report.csv')
    if os.path.exists(acc_path):
        try:
            acc_df = pd.read_csv(acc_path)
            if not acc_df.empty and acc_df['games_completed'].sum() > 0:
                tot = int(acc_df['games_completed'].sum()); cor = int(acc_df['correct_predictions'].sum())
                overall = cor / tot if tot else 0
                recent = acc_df.tail(10)
                recent_tot = int(recent['games_completed'].sum()); recent_cor = int(recent['correct_predictions'].sum())
                recent_acc = recent_cor / recent_tot if recent_tot else 0
                
                md.append('## 📈 Model Performance')
                md.append('')
                
                # Recent form with emoji indicators
                last4 = acc_df.tail(4)
                form_icons = []
                for _, r in last4.iterrows():
                    acc_val = r.get('accuracy', 0.0) or 0.0
                    if acc_val >= 0.90:
                        form_icons.append('🎯')
                    elif acc_val >= 0.85:
                        form_icons.append('✅')
                    elif acc_val >= 0.75:
                        form_icons.append('📊')
                    else:
                        form_icons.append('📉')
                form_str = ''.join(form_icons)
                
                # Streak status
                streak_status = f"🔥 {ext_streaks['top1_streak']}-day #1 pick streak active" if ext_streaks['top1_streak'] > 0 else "Building new streak"
                
                md.append(f'**Recent Form**: {form_str} (Last 4 days)')  
                md.append(f'**Streak Status**: {streak_status}')
                md.append('')
                md.append(f'- **Overall Accuracy**: {overall:.1%} ({tot:,} evaluated)')
                md.append(f'- **Last 10 Days**: {recent_acc:.1%} ({recent_tot} games)')
                md.append('')
                
                md.append('### Daily Breakdown')
                md.append('')
                last7 = acc_df.tail(7)
                md.append('| Date | Games | Correct | Accuracy | Confidence | Trend |')
                md.append('|------|-------|---------|----------|------------|-------|')
                
                prev_acc = None
                for _, r in last7.iterrows():
                    games = int(r.get('games_completed',0)); corr = int(r.get('correct_predictions',0))
                    accv = r.get('accuracy',0.0) or 0.0; conf = r.get('avg_confidence',0.0) or 0.0
                    
                    # Trend indicator
                    trend = '—'
                    if prev_acc is not None and games > 0:
                        if accv > prev_acc + 0.05:
                            trend = '↗️'
                        elif accv < prev_acc - 0.05:
                            trend = '↘️'
                        else:
                            trend = '➡️'
                    prev_acc = accv if games > 0 else prev_acc
                    
                    if games:
                        date_str = r['date']
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            date_str = date_obj.strftime('%b %d')
                        except Exception:
                            pass
                        md.append(f"| {date_str} | {games} | {corr} | {accv:.1%} | {conf:.1%} | {trend} |")
                    else:
                        md.append(f"| {r['date']} | - | - | - | - | - |")
                md.append('')
                
                # Pick streak details
                md.append('### 🏅 Streak Performance')
                md.append('')
                md.append(f'- **#1 Pick Accuracy**: {ext_streaks["top1_streak"]} consecutive days correct')
                md.append(f'- **Top 5 Picks**: {ext_streaks["top5_streak"]} days with all 5 correct')
                if ext_streaks['recent_days']:
                    md.append('')
                    md.append('| Date | Games | #1 ✓ | Top5 ✓ |')
                    md.append('|------|-------|-------|--------|')
                    for d in ext_streaks['recent_days'][-5:]:  # Last 5 days only
                        date_str = d['date']
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            date_str = date_obj.strftime('%b %d')
                        except Exception:
                            pass
                        md.append(f"| {date_str} | {d['games']} | {'✅' if d['top1_correct'] else '❌'} | {'✅' if d['top5_all_correct'] else ('—' if d['games']<5 else '❌')} |")
                md.append('')
        except Exception:
            pass
    md.append('---')
    md.append('')
    md.append('## � About These Predictions')
    md.append('')
    md.append('### Methodology')
    md.append('- **Algorithm**: Random Forest classifier with time-weighted training')
    md.append('- **Confidence**: Probability of predicted winner (≥70% = high confidence)')
    md.append('- **Features**: Team encodings, rankings, neutral site, rolling performance metrics')
    md.append('- **Training**: 29,520 historical games with 10x weight on current season')
    md.append('')
    md.append('### Usage')
    md.append('```bash')
    md.append('python3 daily_pipeline.py   # Full refresh')
    md.append('python3 game_prediction/publish_artifacts.py --predictions-only  # Regenerate this file')
    md.append('```')
    md.append('')
    md.append('### Important Notes')
    md.append('⚠️ **Experimental predictions** — Use for entertainment and analysis only  ')
    md.append('📊 **Low-data games excluded** — Teams need 75+ historical games for inclusion  ')
    md.append('🔄 **Updated daily** — Fresh predictions generated at 12:00 PM UTC')
    md.append('')
    md.append('---')
    md.append('')
    md.append(f'**Model Lineage**: Config `{cfg}` · Commit `{ch[:7]}`  ')
    md.append(f'**Generated**: {timestamp}  ')
    md.append('**Pipeline**: `publish_artifacts.py`')
    
    _write_md(md)
    print(f"✓ predictions.md updated ({total_games} today, cfg={cfg}, commit={ch})")


def _write_md(lines: list[str]):
    with open(PRED_MD_PATH,'w') as f:
        f.write('\n'.join(lines))


# --------------------------------------------------------------------------------------
# Entry point / argument parsing
# --------------------------------------------------------------------------------------
def main():
    args = set(sys.argv[1:])
    banner_only = '--banner-only' in args
    readme_only = '--readme-only' in args
    predictions_only = '--predictions-only' in args
    if sum(bool(x) for x in [banner_only, readme_only, predictions_only]) > 1:
        print('⚠️ Specify at most one mode flag. Aborting.')
        return
    if banner_only:
        # Just banner
        if not os.path.exists(README_PATH):
            print('README missing; cannot update banner.')
            return
        with open(README_PATH) as f:
            lines = f.readlines()
        lines = _update_readme_banner(lines)
        with open(README_PATH,'w') as f:
            f.writelines(lines)
        print('✓ README banner refreshed (banner-only mode)')
        return
    if predictions_only:
        generate_predictions_markdown()
        return
    if readme_only:
        refresh_readme_evaluation()
        return
    # Full mode
    generate_predictions_markdown()
    refresh_readme_evaluation()


if __name__ == '__main__':
    main()
