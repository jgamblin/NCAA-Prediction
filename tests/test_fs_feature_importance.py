import numpy as np
from model_training.ncaa_predictions_v2 import extract_fs_feature_importance


def test_extract_fs_feature_importance_ordering():
    features = ['a','fs_win_pct5_diff','b','fs_point_diff10_diff','fs_win_pct10_diff']
    importances = np.array([0.01, 0.10, 0.02, 0.30, 0.20])
    mapping = extract_fs_feature_importance(features, importances)
    # Expect descending order by importance
    keys = list(mapping.keys())
    values = list(mapping.values())
    assert values == sorted(values, reverse=True)
    assert keys[0] == 'fs_point_diff10_diff'
    assert 'fs_win_pct5_diff' in mapping
    assert 'fs_win_pct10_diff' in mapping
