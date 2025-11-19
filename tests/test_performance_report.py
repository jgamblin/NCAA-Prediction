"""Test performance report generation."""

import tempfile
from pathlib import Path
import pandas as pd
import pytest
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


def test_performance_report_with_sample_data():
    """Test that performance report can be generated with sample data."""
    from generate_performance_report import main, _derive_accuracy_features, _drift_snapshot
    import generate_performance_report as gpr
    
    # Create sample accuracy data
    sample_data = {
        'date': pd.date_range('2025-11-10', periods=10),
        'total_predictions': [20] * 10,
        'games_completed': [20] * 10,
        'correct_predictions': [16, 17, 18, 15, 16, 17, 16, 18, 17, 16],
        'accuracy': [0.8, 0.85, 0.9, 0.75, 0.8, 0.85, 0.8, 0.9, 0.85, 0.8],
        'avg_confidence': [0.85] * 10,
    }
    df = pd.DataFrame(sample_data)
    
    # Test _derive_accuracy_features
    result_df = _derive_accuracy_features(df)
    assert 'rolling_accuracy' in result_df.columns
    assert len(result_df) == 10
    
    # Test _drift_snapshot with empty df
    drift_msg = _drift_snapshot(pd.DataFrame())
    assert "No drift metrics available" in drift_msg
    
    # Test _drift_snapshot with sample data
    sample_drift = pd.DataFrame({
        'date': ['2025-11-19'],
        'season': ['2025-26'],
        'games_seen': [100],
        'cumulative_accuracy': [0.75],
        'cumulative_logloss': [0.58],
        'cumulative_brier': [0.19],
    })
    drift_msg = _drift_snapshot(sample_drift)
    assert "Season 2025-26" in drift_msg
    assert "100 games" in drift_msg
    

def test_performance_report_generation_end_to_end():
    """Test full performance report generation with temporary files."""
    from generate_performance_report import main
    import generate_performance_report as gpr
    
    # Save original paths
    orig_accuracy = gpr.ACCURACY_CSV
    orig_drift = gpr.DRIFT_CSV
    orig_report = gpr.REPORT_PATH
    orig_asset_dir = gpr.ASSET_DIR
    orig_repo_root = gpr.REPO_ROOT
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create temporary directories
            data_dir = tmppath / "data"
            docs_dir = tmppath / "docs"
            asset_dir = docs_dir / "performance"
            data_dir.mkdir()
            docs_dir.mkdir()
            asset_dir.mkdir(parents=True)
            
            # Create sample accuracy CSV
            accuracy_csv = data_dir / "Accuracy_Report.csv"
            sample_data = {
                'date': pd.date_range('2025-11-10', periods=10),
                'total_predictions': [20] * 10,
                'games_completed': [20] * 10,
                'correct_predictions': [16, 17, 18, 15, 16, 17, 16, 18, 17, 16],
                'accuracy': [0.8, 0.85, 0.9, 0.75, 0.8, 0.85, 0.8, 0.9, 0.85, 0.8],
                'avg_confidence': [0.85] * 10,
                'config_version': ['test'] * 10,
                'commit_hash': ['abc123'] * 10,
            }
            pd.DataFrame(sample_data).to_csv(accuracy_csv, index=False)
            
            # Create empty drift CSV
            drift_csv = data_dir / "Drift_Metrics.csv"
            drift_csv.write_text("date,season,games_seen,cumulative_accuracy,cumulative_logloss,cumulative_brier\n")
            
            report_path = tmppath / "performance.md"
            
            # Override paths
            gpr.ACCURACY_CSV = accuracy_csv
            gpr.DRIFT_CSV = drift_csv
            gpr.REPORT_PATH = report_path
            gpr.ASSET_DIR = asset_dir
            gpr.REPO_ROOT = tmppath
            
            # Run main
            main()
            
            # Verify report was created
            assert report_path.exists()
            content = report_path.read_text()
            
            # Check for key sections
            assert "# 📊 Model Performance Dashboard" in content
            assert "## Overview" in content
            assert "Overall Accuracy" in content
            assert "7-Day Rolling Accuracy" in content
            assert "## Daily Accuracy" in content
            assert "## Average Confidence" in content
            assert "### Recent History" in content
            assert "## Drift Snapshot" in content
            assert "## Performance Trends" in content
            assert "Last 7 Days" in content
            assert "Back to Main README" in content
            assert "View Latest Predictions" in content
            
            # Verify charts were created
            assert (asset_dir / "daily_accuracy.png").exists()
            assert (asset_dir / "average_confidence.png").exists()
    finally:
        # Restore original paths
        gpr.ACCURACY_CSV = orig_accuracy
        gpr.DRIFT_CSV = orig_drift
        gpr.REPORT_PATH = orig_report
        gpr.ASSET_DIR = orig_asset_dir
        gpr.REPO_ROOT = orig_repo_root


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
