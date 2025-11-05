import numpy as np
from model_training.ncaa_predictions_v2 import calibration_report

def test_calibration_report_basic():
    # Simple deterministic probabilities
    y_true = np.array([0,1,1,0,1,0,1,1,0,0])
    y_proba = np.array([0.2,0.8,0.7,0.4,0.9,0.1,0.6,0.55,0.3,0.25])
    brier, df = calibration_report(y_true, y_proba, bins=5)
    # Manual brier calculation
    manual_brier = float(np.mean((y_proba - y_true) ** 2))
    assert abs(brier - manual_brier) < 1e-9
    assert df['bin_count'].sum() == len(y_true)
    # Ensure structure
    assert {'bin_count','mean_pred','mean_actual','abs_gap'}.issubset(df.columns)
