#!/usr/bin/env python3
"""
Calibration Metrics for Probability Predictions

Measures how well predicted probabilities match actual outcomes.

Key Metrics:
- Expected Calibration Error (ECE): Average difference between confidence and accuracy
- Brier Score: Mean squared error of probability predictions
- Log Loss: Penalizes confident wrong predictions
- Calibration by Bucket: Breakdown by confidence levels

A well-calibrated model has:
- ECE < 0.05
- Confidence ≈ Accuracy in each bucket
- Brier score < 0.25
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt


def expected_calibration_error(
    y_true: np.ndarray, 
    y_pred: np.ndarray, 
    n_bins: int = 10
) -> float:
    """
    Calculate Expected Calibration Error (ECE).
    
    ECE measures the average difference between predicted probability
    and actual frequency across bins.
    
    Lower is better:
    - ECE < 0.05: Well-calibrated
    - ECE 0.05-0.10: Acceptable
    - ECE > 0.10: Poorly calibrated
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
        n_bins: Number of confidence bins (default: 10)
    
    Returns:
        ECE score (0-1, lower is better)
    
    Example:
        >>> y_true = np.array([1, 0, 1, 1, 0])
        >>> y_pred = np.array([0.9, 0.2, 0.8, 0.7, 0.3])
        >>> ece = expected_calibration_error(y_true, y_pred)
        >>> print(f"ECE: {ece:.4f}")
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have same length")
    
    # Create bins
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    ece = 0.0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_accuracy = y_true[mask].mean()
            bin_confidence = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_accuracy - bin_confidence)
    
    return ece


def brier_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate Brier Score (Mean Squared Error for probabilities).
    
    Measures accuracy of probability predictions.
    
    Lower is better:
    - Brier < 0.20: Excellent
    - Brier 0.20-0.25: Good
    - Brier > 0.25: Poor
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
    
    Returns:
        Brier score (0-1, lower is better)
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    return np.mean((y_pred - y_true) ** 2)


def log_loss(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-15) -> float:
    """
    Calculate Log Loss (Cross-Entropy Loss).
    
    Heavily penalizes confident wrong predictions.
    
    Lower is better:
    - Log loss < 0.5: Good
    - Log loss 0.5-0.7: Acceptable
    - Log loss > 0.7: Poor
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
        eps: Small constant to avoid log(0)
    
    Returns:
        Log loss (0-∞, lower is better)
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    # Clip predictions to avoid log(0)
    y_pred = np.clip(y_pred, eps, 1 - eps)
    
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))


def calibration_by_bucket(
    y_true: np.ndarray, 
    y_pred: np.ndarray,
    buckets: List[Tuple[float, float, str]] = None
) -> pd.DataFrame:
    """
    Calculate calibration metrics by confidence bucket.
    
    Shows how accuracy varies across confidence levels.
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
        buckets: List of (min, max, label) tuples
    
    Returns:
        DataFrame with calibration stats per bucket
    """
    if buckets is None:
        buckets = [
            (0.80, 1.00, '80%+'),
            (0.70, 0.80, '70-80%'),
            (0.60, 0.70, '60-70%'),
            (0.50, 0.60, '50-60%'),
            (0.00, 0.50, '<50%'),
        ]
    
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    results = []
    
    for low, high, label in buckets:
        mask = (y_pred >= low) & (y_pred < high)
        
        if mask.sum() > 0:
            bucket_data = {
                'bucket': label,
                'games': mask.sum(),
                'avg_confidence': y_pred[mask].mean(),
                'accuracy': y_true[mask].mean(),
                'gap': y_pred[mask].mean() - y_true[mask].mean(),
                'brier': np.mean((y_pred[mask] - y_true[mask]) ** 2)
            }
            results.append(bucket_data)
    
    return pd.DataFrame(results)


def reliability_diagram(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bins: int = 10,
    save_path: str = None
) -> None:
    """
    Plot reliability diagram (calibration curve).
    
    Perfect calibration = diagonal line.
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
        n_bins: Number of bins (default: 10)
        save_path: Optional path to save figure
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    # Calculate bin statistics
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    bin_confidences = []
    bin_accuracies = []
    bin_counts = []
    
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_confidences.append(y_pred[mask].mean())
            bin_accuracies.append(y_true[mask].mean())
            bin_counts.append(mask.sum())
    
    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Calibration curve
    ax1.plot([0, 1], [0, 1], 'k--', linewidth=2, label='Perfect Calibration')
    ax1.plot(bin_confidences, bin_accuracies, 'o-', linewidth=2, 
             markersize=8, label='Model Calibration')
    
    for i, (conf, acc, count) in enumerate(zip(bin_confidences, bin_accuracies, bin_counts)):
        ax1.annotate(f'{count}', (conf, acc), fontsize=8, ha='right')
    
    ax1.set_xlabel('Confidence (Predicted Probability)', fontsize=12)
    ax1.set_ylabel('Accuracy (Actual Frequency)', fontsize=12)
    ax1.set_title('Calibration Curve', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim([0, 1])
    ax1.set_ylim([0, 1])
    
    # Histogram
    ax2.hist(y_pred, bins=20, edgecolor='black', alpha=0.7)
    ax2.set_xlabel('Predicted Probability', fontsize=12)
    ax2.set_ylabel('Count', fontsize=12)
    ax2.set_title('Prediction Distribution', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Calibration diagram saved to {save_path}")
    else:
        plt.show()


def print_calibration_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    title: str = "Calibration Report"
) -> None:
    """
    Print comprehensive calibration report.
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred: Predicted probabilities (0-1)
        title: Report title
    """
    print("="*80)
    print(title)
    print("="*80)
    print()
    
    # Overall metrics
    ece = expected_calibration_error(y_true, y_pred)
    brier = brier_score(y_true, y_pred)
    logloss = log_loss(y_true, y_pred)
    accuracy = y_true.mean()
    avg_conf = y_pred.mean()
    
    print("Overall Metrics:")
    print(f"  Total predictions:    {len(y_true):,}")
    print(f"  Accuracy:             {accuracy:.1%}")
    print(f"  Average confidence:   {avg_conf:.1%}")
    print(f"  Calibration gap:      {abs(avg_conf - accuracy):.1%}")
    print()
    print(f"  ECE:                  {ece:.4f} {'✅' if ece < 0.05 else '⚠️' if ece < 0.10 else '❌'}")
    print(f"  Brier Score:          {brier:.4f} {'✅' if brier < 0.20 else '⚠️' if brier < 0.25 else '❌'}")
    print(f"  Log Loss:             {logloss:.4f} {'✅' if logloss < 0.50 else '⚠️' if logloss < 0.70 else '❌'}")
    print()
    
    # By bucket
    print("Calibration by Confidence Bucket:")
    print(f"{'Bucket':12} {'Games':>7} {'Avg Conf':>10} {'Accuracy':>10} {'Gap':>8} {'Status':>8}")
    print("-" * 70)
    
    buckets_df = calibration_by_bucket(y_true, y_pred)
    for _, row in buckets_df.iterrows():
        gap = row['gap']
        status = '✅' if abs(gap) < 0.05 else '⚠️' if abs(gap) < 0.10 else '❌'
        
        print(f"{row['bucket']:12} {row['games']:7} "
              f"{row['avg_confidence']:10.1%} {row['accuracy']:10.1%} "
              f"{gap:8.1%} {status:>8}")
    
    print()
    print("Legend:")
    print("  ✅ Well-calibrated (gap < 5%)")
    print("  ⚠️  Acceptable (gap 5-10%)")
    print("  ❌ Poorly calibrated (gap > 10%)")
    print("="*80)


if __name__ == '__main__':
    # Example usage
    print("Calibration Metrics Example\n")
    
    # Simulate some predictions
    np.random.seed(42)
    n = 1000
    
    # Well-calibrated model
    y_true_good = np.random.binomial(1, 0.7, n)
    y_pred_good = np.clip(np.random.normal(0.7, 0.15, n), 0, 1)
    
    # Overconfident model
    y_true_bad = np.random.binomial(1, 0.6, n)
    y_pred_bad = np.clip(np.random.normal(0.8, 0.1, n), 0, 1)
    
    print("1. Well-Calibrated Model:")
    print_calibration_report(y_true_good, y_pred_good, "Well-Calibrated Model")
    
    print("\n")
    
    print("2. Overconfident Model:")
    print_calibration_report(y_true_bad, y_pred_bad, "Overconfident Model")
