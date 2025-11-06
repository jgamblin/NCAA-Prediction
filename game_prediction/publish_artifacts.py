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
    new_section.append("")
    new_section.append("### Lineage")
    new_section.append("")
    new_section.append(f"- Config Version: `{cfg}`")
    new_section.append(f"- Commit Hash: `{ch}`")
    new_section.append(f"*Refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    new_section.append("")
    # Replace first occurrence of evaluation heading in README
    with open(README_PATH) as f:
        lines = f.readlines()
    lines = _update_readme_banner(lines)
    heading = '## 📈 Model Evaluation'
    # Old heading variants from earlier rewrite
    alt_heading = '## 📈 Model Evaluation (Auto‑Updated)'
    candidates = [i for i,l in enumerate(lines) if (heading in l) or (alt_heading in l)]
    if not candidates:
        # append at top after Live Snapshot if missing
        insert_idx = 0
        for i,l in enumerate(lines):
            if '## 🔎 Live Snapshot' in l:
                insert_idx = i + 1
                break
        new_lines = lines[:insert_idx] + [s + '\n' for s in new_section] + lines[insert_idx:]
    else:
        start = candidates[0]
        end = len(lines)
        for i in range(start+1, len(lines)):
            if lines[i].startswith('## ') and ('Model Evaluation' not in lines[i]):
                end = i
                break
        new_lines = lines[:start] + [s + '\n' for s in new_section] + lines[end:]
    new_lines = _update_readme_banner(new_lines)
    with open(README_PATH,'w') as f:
        f.writelines(new_lines)
    print(f"✓ README evaluation & banner updated (cfg={cfg}, commit={ch})")


# --------------------------------------------------------------------------------------
# Predictions markdown generator (elevated formatting)
# --------------------------------------------------------------------------------------
def generate_predictions_markdown():
    # timezone-aware UTC datetime (datetime.utcnow deprecated)
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S UTC')
    cfg, ch = resolve_lineage()
    md: list[str] = []
    md.append('# 🏀 NCAA Basketball Predictions')
    md.append('')
    md.append(f'**Last Updated**: {timestamp}')
    md.append(f'**Lineage**: config `{cfg}` · commit `{ch}`')
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
    md.append('---')
    md.append('')
    md.append('## 🔎 Today Snapshot')
    md.append('')
    md.append(f'- **Games Predicted Today**: {total_games}')
    md.append(f'- **Average Confidence**: {avg_conf:.1%}')
    high = today_games[today_games['confidence'] >= 0.7]
    medium = today_games[(today_games['confidence'] >= 0.6) & (today_games['confidence'] < 0.7)]
    low = today_games[today_games['confidence'] < 0.6]
    md.append(f'- **High (≥70%)**: {len(high)} · **Medium (60-70%)**: {len(medium)} · **Other (<60%)**: {len(low)}')
    md.append('')
    # Streak
    streak, last_miss, _tp, _sd = calculate_perfect_streak()
    # Extended streaks (top1 & top5) from detailed predictions
    details_path = os.path.join(DATA_DIR, 'Prediction_Details.csv')
    ext_streaks = compute_top_pick_streaks(details_path)
    if streak > 0:
        md.append(f"- **High Confidence Streak**: {streak} day(s){' (last miss ' + last_miss + ')' if last_miss else ''}")
        md.append('')
    # Add top1 & top5 streak summary
    md.append('### 🏅 Pick Streaks')
    md.append('')
    md.append(f"- **#1 Pick Streak**: {ext_streaks['top1_streak']} day(s)" + (f" (last miss {ext_streaks['top1_last_miss']})" if ext_streaks['top1_last_miss'] else ""))
    md.append(f"- **Top 5 Picks Perfect Streak**: {ext_streaks['top5_streak']} day(s)" + (f" (last miss {ext_streaks['top5_last_miss']})" if ext_streaks['top5_last_miss'] else ""))
    md.append('')
    # Recent streak table
    if ext_streaks['recent_days']:
        md.append('| Date | Games | #1 Correct | Top5 All Correct |')
        md.append('|------|-------|------------|------------------|')
        for d in ext_streaks['recent_days']:
            md.append(f"| {d['date']} | {d['games']} | {'✅' if d['top1_correct'] else '❌'} | {'✅' if d['top5_all_correct'] else ('—' if d['games']<5 else '❌')} |")
        md.append('')
    # Confidence tiers tables
    def tier_table(df: pd.DataFrame, title: str):
        if df.empty:
            return
        md.append(f'### {title}')
        md.append('')
        md.append('| # | Winner | Opponent | Confidence |')
        md.append('|---|--------|---------|------------|')
        for i, (_, g) in enumerate(df.sort_values('confidence', ascending=False).iterrows(), 1):
            winner = g['predicted_winner']
            loser = g['home_team'] if winner == g['away_team'] else g['away_team']
            md.append(f"| {i} | **{winner}** | {loser} | {g['confidence']:.1%} |")
        md.append('')
    tier_table(high, '🎯 High Confidence Picks (≥70%)')
    tier_table(medium, '📊 Medium Confidence Picks (60–70%)')
    # Summary stats
    if total_games:
        md.append('### 📈 Distribution Summary')
        md.append('')
        home_favored = int(today_games['predicted_home_win'].sum()) if 'predicted_home_win' in today_games.columns else 0
        away_favored = total_games - home_favored
        md.append(f'- Home Teams Favored: {home_favored}')
        md.append(f'- Away Teams Favored: {away_favored}')
        md.append(f'- Max Confidence: {today_games["confidence"].max():.1%}')
        md.append(f'- Min Confidence: {today_games["confidence"].min():.1%}')
        md.append('')
    md.append('### 📋 Full Data')
    md.append('')
    md.append(f'[→ View full predictions CSV ({len(preds)} rows)](data/NCAA_Game_Predictions.csv)')
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
                md.append('---')
                md.append('')
                md.append('## 🧪 Performance Overview')
                md.append('')
                md.append(f'- **Overall Accuracy**: {overall:.1%} ({tot} evaluated)')
                md.append(f'- **Last 10 Days**: {recent_acc:.1%} ({recent_tot} games)')
                md.append('')
                md.append('### Last 7 Days')
                md.append('')
                last7 = acc_df.tail(7)
                md.append('| Date | Games | Correct | Accuracy | Avg Confidence |')
                md.append('|------|-------|---------|----------|----------------|')
                for _, r in last7.iterrows():
                    games = int(r.get('games_completed',0)); corr = int(r.get('correct_predictions',0))
                    accv = r.get('accuracy',0.0) or 0.0; conf = r.get('avg_confidence',0.0) or 0.0
                    if games:
                        md.append(f"| {r['date']} | {games} | {corr} | {accv:.1%} | {conf:.1%} |")
                    else:
                        md.append(f"| {r['date']} | - | - | - | - |")
                md.append('')
        except Exception:
            pass
    md.append('---')
    md.append('')
    md.append('## 🚀 Usage')
    md.append('')
    md.append('```bash')
    md.append('python3 daily_pipeline.py   # full refresh')
    md.append('python3 game_prediction/publish_artifacts.py --predictions-only  # regenerate this file only')
    md.append('```')
    md.append('')
    md.append('## 📚 Notes')
    md.append('')
    md.append('- Confidence = max(prob_home_win, 1 - prob_home_win)')
    md.append('- High confidence threshold: 70%')
    md.append('- All predictions are experimental; use responsibly.')
    md.append('')
    md.append('*Auto-generated by `publish_artifacts.py`*')
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
