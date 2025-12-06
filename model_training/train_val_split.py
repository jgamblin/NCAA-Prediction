#!/usr/bin/env python3
"""
Train/Validation/Test Split for Temporal Data

CRITICAL: NCAA prediction data MUST use temporal splits, not random splits.
Random splits leak future information and create overoptimistic metrics.

Temporal split ensures:
- Training: Past data only
- Validation: Recent past (for calibration)
- Test: Most recent (simulates real prediction)

This prevents overfitting and ensures proper calibration.
"""

import pandas as pd
from datetime import timedelta
from typing import Tuple


def temporal_split(
    df: pd.DataFrame, 
    val_days: int = 14, 
    test_days: int = 7
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Create temporal train/validation/test split.
    
    Training: All games up to (latest - val_days - test_days)
    Validation: Games in (latest - val_days - test_days) to (latest - test_days)
    Test: Last test_days of games
    
    This simulates real prediction:
    - Train on historical data
    - Calibrate on recent past (validation)
    - Test on "future" (most recent games)
    
    Args:
        df: DataFrame with 'date' column
        val_days: Days to use for validation (default: 14)
        test_days: Days to use for test (default: 7)
    
    Returns:
        train_df, val_df, test_df
    
    Example:
        >>> train, val, test = temporal_split(games_df, val_days=14, test_days=7)
        >>> print(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
    """
    if 'date' not in df.columns:
        raise ValueError("DataFrame must have 'date' column")
    
    df_sorted = df.sort_values('date').copy()
    
    # Convert date to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df_sorted['date']):
        df_sorted['date'] = pd.to_datetime(df_sorted['date'])
    
    latest_date = df_sorted['date'].max()
    
    # Calculate split points
    test_start = latest_date - pd.Timedelta(days=test_days)
    val_start = test_start - pd.Timedelta(days=val_days)
    
    # Split data
    train_df = df_sorted[df_sorted['date'] < val_start].copy()
    val_df = df_sorted[
        (df_sorted['date'] >= val_start) & (df_sorted['date'] < test_start)
    ].copy()
    test_df = df_sorted[df_sorted['date'] >= test_start].copy()
    
    print(f"Temporal split created:")
    print(f"  Training:   {len(train_df):5} games (up to {val_start.date()})")
    print(f"  Validation: {len(val_df):5} games ({val_start.date()} to {test_start.date()})")
    print(f"  Test:       {len(test_df):5} games (from {test_start.date()})")
    
    # Validate split
    _validate_temporal_split(train_df, val_df, test_df)
    
    return train_df, val_df, test_df


def create_validation_split(
    df: pd.DataFrame, 
    val_days: int = 14
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create train/validation split (no test set).
    
    Used during model training when we only need calibration,
    not final testing.
    
    Training: All games up to (latest - val_days)
    Validation: Last val_days of games
    
    Args:
        df: DataFrame with 'date' column
        val_days: Days to use for validation (default: 14)
    
    Returns:
        train_df, val_df
    """
    if 'date' not in df.columns:
        raise ValueError("DataFrame must have 'date' column")
    
    df_sorted = df.sort_values('date').copy()
    
    # Convert date to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df_sorted['date']):
        df_sorted['date'] = pd.to_datetime(df_sorted['date'])
    
    latest_date = df_sorted['date'].max()
    val_cutoff = latest_date - pd.Timedelta(days=val_days)
    
    train_df = df_sorted[df_sorted['date'] < val_cutoff].copy()
    val_df = df_sorted[df_sorted['date'] >= val_cutoff].copy()
    
    print(f"Train/Val split created:")
    print(f"  Training:   {len(train_df):5} games (up to {val_cutoff.date()})")
    print(f"  Validation: {len(val_df):5} games (last {val_days} days)")
    
    # Validate split
    if len(train_df) == 0:
        raise ValueError("Training set is empty!")
    if len(val_df) == 0:
        raise ValueError("Validation set is empty!")
    if train_df['date'].max() >= val_df['date'].min():
        raise ValueError("Data leakage! Train and validation sets overlap")
    
    print("  ✓ Split validated (no data leakage)")
    
    return train_df, val_df


def _validate_temporal_split(
    train_df: pd.DataFrame, 
    val_df: pd.DataFrame, 
    test_df: pd.DataFrame
) -> None:
    """
    Validate that temporal split has no data leakage.
    
    Ensures:
    - All sets are non-empty
    - Training date < validation date < test date
    - No overlap between sets
    """
    if len(train_df) == 0:
        raise ValueError("Training set is empty!")
    if len(val_df) == 0:
        raise ValueError("Validation set is empty!")
    if len(test_df) == 0:
        raise ValueError("Test set is empty!")
    
    # Check temporal ordering
    train_max = train_df['date'].max()
    val_min = val_df['date'].min()
    val_max = val_df['date'].max()
    test_min = test_df['date'].min()
    
    if train_max >= val_min:
        raise ValueError(f"Data leakage! Training extends into validation: {train_max} >= {val_min}")
    
    if val_max >= test_min:
        raise ValueError(f"Data leakage! Validation extends into test: {val_max} >= {test_min}")
    
    print("  ✓ Temporal split validated (no data leakage)")


def rolling_window_split(
    df: pd.DataFrame,
    window_days: int = 90,
    step_days: int = 7,
    min_train_games: int = 100
):
    """
    Create rolling window splits for backtesting.
    
    Useful for testing model performance over time.
    
    Args:
        df: DataFrame with 'date' column
        window_days: Training window size (default: 90)
        step_days: Step size between windows (default: 7)
        min_train_games: Minimum games required for training
    
    Yields:
        (train_df, test_df, period_label) tuples
    
    Example:
        >>> for train, test, label in rolling_window_split(games_df):
        ...     model.fit(train)
        ...     predictions = model.predict(test)
        ...     print(f"{label}: {accuracy}")
    """
    if 'date' not in df.columns:
        raise ValueError("DataFrame must have 'date' column")
    
    df_sorted = df.sort_values('date').copy()
    
    # Convert date to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df_sorted['date']):
        df_sorted['date'] = pd.to_datetime(df_sorted['date'])
    
    dates = sorted(df_sorted['date'].unique())
    
    # Find first valid training window
    first_date = dates[0]
    last_date = dates[-1]
    
    current_date = first_date + pd.Timedelta(days=window_days)
    
    while current_date + pd.Timedelta(days=step_days) <= last_date:
        train_start = current_date - pd.Timedelta(days=window_days)
        train_end = current_date
        test_end = current_date + pd.Timedelta(days=step_days)
        
        train_mask = (df_sorted['date'] >= train_start) & (df_sorted['date'] < train_end)
        test_mask = (df_sorted['date'] >= train_end) & (df_sorted['date'] < test_end)
        
        train_data = df_sorted[train_mask].copy()
        test_data = df_sorted[test_mask].copy()
        
        # Only yield if we have enough training data
        if len(train_data) >= min_train_games and len(test_data) > 0:
            period_label = f"{train_end.date()} to {test_end.date()}"
            yield train_data, test_data, period_label
        
        current_date += pd.Timedelta(days=step_days)


if __name__ == '__main__':
    # Example usage
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from backend.repositories.games_repository import GamesRepository
    from backend.database import get_db_connection
    
    print("="*80)
    print("TRAIN/VAL/TEST SPLIT EXAMPLE")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    completed_games = games_repo.get_completed_games_df()
    
    print(f"Total games: {len(completed_games)}")
    print()
    
    # Create split
    train, val, test = temporal_split(completed_games, val_days=14, test_days=7)
    
    print()
    print("Split summary:")
    print(f"  Train: {len(train)} games ({len(train)/len(completed_games)*100:.1f}%)")
    print(f"  Val:   {len(val)} games ({len(val)/len(completed_games)*100:.1f}%)")
    print(f"  Test:  {len(test)} games ({len(test)/len(completed_games)*100:.1f}%)")
    
    db.close()
