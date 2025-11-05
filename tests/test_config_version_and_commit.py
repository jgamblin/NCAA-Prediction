import pandas as pd
from pathlib import Path

def test_predictions_has_config_and_commit():
    path = Path('data') / 'NCAA_Game_Predictions.csv'
    assert path.exists(), 'Predictions CSV missing'
    df = pd.read_csv(path)
    assert 'config_version' in df.columns, 'config_version column missing in predictions'
    assert 'commit_hash' in df.columns, 'commit_hash column missing in predictions'
    assert df['config_version'].notna().all(), 'config_version has NaN'
    assert df['commit_hash'].notna().all(), 'commit_hash has NaN'


def test_anomalies_has_config_version_if_exists():
    path = Path('data') / 'Team_Anomalies.csv'
    if not path.exists():
        return  # acceptable if no anomalies produced
    df = pd.read_csv(path)
    if not df.empty:
        assert 'config_version' in df.columns, 'config_version missing in anomalies'
        assert df['config_version'].notna().all(), 'config_version NaN in anomalies'
