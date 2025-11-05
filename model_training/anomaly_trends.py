"""Anomaly Trend Visualization

Generates a time-series plot of accuracy deltas (rolling vs cumulative) for teams
flagged as anomalies in Team_Anomalies.csv over recent dates.

Reads:
  data/Team_Anomalies.csv (latest anomalies snapshot per team)
  data/Drift_Metrics_By_Team.csv (historical per-team metrics)

Outputs:
  data/Anomaly_Trends.png (line chart of acc_delta over time for anomalous teams)
  data/Anomaly_Trends.csv (raw extracted time series)

Run:
  python -m model_training.anomaly_trends --window 25
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DATA_DIR = Path('data')
ANOMALIES = DATA_DIR / 'Team_Anomalies.csv'
TEAM_DRIFT = DATA_DIR / 'Drift_Metrics_By_Team.csv'
OUT_PNG = DATA_DIR / 'Anomaly_Trends.png'
OUT_CSV = DATA_DIR / 'Anomaly_Trends.csv'

def load_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not ANOMALIES.exists():
        raise FileNotFoundError(f"Missing anomalies file: {ANOMALIES}")
    an = pd.read_csv(ANOMALIES)
    if not TEAM_DRIFT.exists():
        raise FileNotFoundError(f"Missing team drift metrics file: {TEAM_DRIFT}")
    drift = pd.read_csv(TEAM_DRIFT)
    return an, drift


def build_time_series(an: pd.DataFrame, drift: pd.DataFrame, window: int) -> pd.DataFrame:
    if an.empty or drift.empty:
        return pd.DataFrame()
    roll_col = f'rolling_accuracy_team_{window}'
    needed = {'team_id','season','cumulative_accuracy_team',roll_col,'games_seen_team'}
    if not needed.issubset(drift.columns):
        # attempt fallback: detect actual rolling accuracy column
        alt = [c for c in drift.columns if c.startswith('rolling_accuracy_team_')]
        if alt:
            roll_col = alt[0]
        else:
            return pd.DataFrame()
    # Latest anomalies per team
    latest_an_ids = an['team_id'].unique().tolist()
    ts_rows = []
    drift_sorted = drift.sort_values(['season','team_id','games_seen_team'])
    # Restrict drift to anomaly teams
    filtered = drift_sorted[drift_sorted['team_id'].isin(latest_an_ids)].copy()
    for (season, team_id), grp in filtered.groupby(['season','team_id']):
        grp = grp.reset_index(drop=True)
        cumulative = grp['cumulative_accuracy_team']
        rolling = grp[roll_col]
        for idx, r in grp.iterrows():
            if pd.isna(r['cumulative_accuracy_team']) or pd.isna(r[roll_col]):
                continue
            ts_rows.append({
                'season': season,
                'team_id': team_id,
                'games_seen_team': r['games_seen_team'],
                'cumulative_accuracy_team': r['cumulative_accuracy_team'],
                'rolling_accuracy_team': r[roll_col],
                'acc_delta': abs(r[roll_col] - r['cumulative_accuracy_team'])
            })
    return pd.DataFrame(ts_rows)


def plot_trends(ts: pd.DataFrame):
    if ts.empty:
        print('No anomaly time series data to plot.')
        return
    # Plot each team as a separate line colored by season + team
    plt.figure(figsize=(10,6))
    # Create label combining season/team for clarity
    ts['series'] = ts['season'].astype(str) + ':' + ts['team_id']
    for key, grp in ts.groupby('series'):
        grp = grp.sort_values('games_seen_team')
        plt.plot(grp['games_seen_team'], grp['acc_delta'], label=key, linewidth=1.6)
    plt.xlabel('Games Seen (Team Perspective)')
    plt.ylabel('| Rolling - Cumulative Accuracy |')
    plt.title('Anomaly Accuracy Delta Over Time')
    # Limit legend size
    handles, labels = plt.gca().get_legend_handles_labels()
    max_leg = 15
    if len(labels) > max_leg:
        plt.legend(handles[:max_leg], labels[:max_leg], title='Season:Team (truncated)', fontsize='small')
    else:
        plt.legend(fontsize='small')
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=110)
    plt.close()
    print(f"✓ Anomaly trend plot written: {OUT_PNG}")


def main():
    parser = argparse.ArgumentParser(description='Generate anomaly trend visualization.')
    parser.add_argument('--window', type=int, default=25, help='Rolling window size (default 25)')
    args = parser.parse_args()
    try:
        an, drift = load_sources()
    except Exception as e:
        print(f"Skipping anomaly trends: {e}")
        return
    ts = build_time_series(an, drift, window=args.window)
    if ts.empty:
        print('No anomaly trend rows produced.')
        return
    ts.to_csv(OUT_CSV, index=False)
    print(f"✓ Anomaly trend time series written: {OUT_CSV} ({len(ts)} rows)")
    plot_trends(ts)

if __name__ == '__main__':
    main()
