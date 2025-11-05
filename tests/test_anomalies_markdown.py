import os
from pathlib import Path
import pandas as pd
from model_training.team_drift_monitor import write_anomalies_markdown

DATA_DIR = Path('data')


def test_write_anomalies_markdown(tmp_path):
    # Create fake anomalies CSV
    anomalies_csv = tmp_path / 'Team_Anomalies.csv'
    md_path = tmp_path / 'TEAM_ANOMALIES.md'
    df = pd.DataFrame({
        'team_id':['t1','t2'],
        'season':['2025-26','2025-26'],
        'games_seen_team':[30,40],
        'cumulative_accuracy_team':[0.70,0.55],
        'rolling_accuracy_team_25':[0.40,0.85],
        'acc_delta':[0.30,0.30]
    })
    df.to_csv(anomalies_csv, index=False)
    assert write_anomalies_markdown(anomalies_csv, md_path, window=25)
    text = md_path.read_text()
    assert '| t1 |' in text and '| t2 |' in text
    assert 'Window: 25' in text
