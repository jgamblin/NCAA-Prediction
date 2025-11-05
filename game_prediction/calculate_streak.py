#!/usr/bin/env python3
"""
Calculate the streak of days with perfect top 5 (high confidence) predictions.
"""

import pandas as pd
import os
from datetime import datetime


def calculate_perfect_streak():
    """
    Calculate how many consecutive days we've had perfect top 5 picks.
    Top 5 = predictions with confidence >= 70%
    Returns: (current_streak, last_miss_date, total_perfect_days)
    """
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    detailed_path = os.path.join(data_dir, 'Prediction_Details.csv')
    
    if not os.path.exists(detailed_path):
        return 0, None, 0, []
    
    # Load detailed predictions
    df = pd.read_csv(detailed_path)
    
    # Filter for high confidence predictions (top tier)
    df['confidence'] = df['confidence'].astype(float)
    high_conf = df[df['confidence'] >= 0.70].copy()
    
    if len(high_conf) == 0:
        return 0, None, 0, []
    
    # Group by date and check if all predictions were correct
    daily_results = high_conf.groupby('date').agg({
        'correct': ['sum', 'count'],
        'confidence': 'mean'
    }).reset_index()
    
    daily_results.columns = ['date', 'correct_count', 'total_count', 'avg_confidence']
    daily_results['all_correct'] = daily_results['correct_count'] == daily_results['total_count']
    
    # Sort by date (most recent first for streak calculation)
    daily_results = daily_results.sort_values('date', ascending=False)
    
    # Calculate current streak (consecutive perfect days from most recent)
    current_streak = 0
    last_miss_date = None
    
    for idx, row in daily_results.iterrows():
        if row['all_correct']:
            current_streak += 1
        else:
            last_miss_date = row['date']
            break
    
    # Total perfect days
    total_perfect_days = daily_results['all_correct'].sum()
    
    # Get details of streak days
    streak_days = []
    for idx, row in daily_results.head(current_streak).iterrows():
        streak_days.append({
            'date': row['date'],
            'correct': int(row['correct_count']),
            'total': int(row['total_count']),
            'avg_confidence': row['avg_confidence']
        })
    
    # Reverse to show oldest to newest
    streak_days = list(reversed(streak_days))
    
    return current_streak, last_miss_date, total_perfect_days, streak_days


def get_streak_emoji(streak):
    """Return an appropriate emoji for the streak length."""
    if streak == 0:
        return "😔"
    elif streak == 1:
        return "🎯"
    elif streak <= 3:
        return "🔥"
    elif streak <= 7:
        return "🔥🔥"
    elif streak <= 14:
        return "🔥🔥🔥"
    else:
        return "🔥🔥🔥💯"


if __name__ == "__main__":
    streak, last_miss, total_perfect, streak_days = calculate_perfect_streak()
    
    print("="*80)
    print("HIGH CONFIDENCE PICKS STREAK TRACKER")
    print("="*80)
    print()
    
    emoji = get_streak_emoji(streak)
    
    if streak > 0:
        print(f"{emoji} CURRENT STREAK: {streak} day(s) with perfect top picks!")
        print()
        if last_miss:
            print(f"Last miss: {last_miss}")
        print(f"Total perfect days: {total_perfect}")
        print()
        
        if len(streak_days) > 0:
            print("Streak breakdown:")
            for day in streak_days[-7:]:  # Show last 7 days max
                print(f"  {day['date']}: {day['correct']}/{day['total']} correct (avg {day['avg_confidence']:.1%} confidence)")
    else:
        print(f"{emoji} No current streak - most recent high confidence picks had misses")
        if last_miss:
            print(f"Last miss: {last_miss}")
        print(f"Total perfect days historically: {total_perfect}")
    
    print()
    print("="*80)
