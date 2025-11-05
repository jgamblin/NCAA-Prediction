"""Conference-Level Drift Aggregation

Aggregates prediction performance metrics at the conference level.

Reads prediction sources and completed games similar to drift_monitor, then joins
team -> conference mapping based on MAJOR_CONFERENCES in check_conference_coverage.
Teams not in mapping labeled 'Other'.

Outputs:
  data/Conference_Drift.csv  (cumulative + rolling accuracy per conference)
  data/CONFERENCE_DRIFT.md   (markdown summary)

Run:
  python -m model_training.conference_drift --window 25
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import log_loss
from data_collection.check_conference_coverage import MAJOR_CONFERENCES
from model_training.drift_monitor import load_completed, load_prediction_sources, prepare_labels, merge_predictions
from model_training.team_id_utils import ensure_team_ids

DATA_DIR = Path('data')
CONF_CSV = DATA_DIR / 'Conference_Drift.csv'
CONF_MD = DATA_DIR / 'CONFERENCE_DRIFT.md'

# Flatten mapping normalized name -> conference
TEAM_TO_CONF = {}
for conf, teams in MAJOR_CONFERENCES.items():
    for t in teams:
        TEAM_TO_CONF[t] = conf  # team_name_utils normalization already applied upstream in most flows


def assign_conference(row) -> str:
    # Prefer home team mapping; fallback to away; else Other
    for col in ['home_team','away_team']:
        t = row.get(col)
        if isinstance(t, str) and t in TEAM_TO_CONF:
            return TEAM_TO_CONF[t]
    return 'Other'


def build_conference_metrics(window: int) -> pd.DataFrame:
    comp = load_completed()
    comp = prepare_labels(comp)
    preds = load_prediction_sources()
    merged = merge_predictions(comp, preds)
    if 'game_status' in merged.columns:
        merged = merged[merged['game_status'] == 'Final']
    if merged.empty:
        return pd.DataFrame()
    merged = ensure_team_ids(merged)
    merged['conference'] = merged.apply(assign_conference, axis=1)
    # Sort chronological
    date_col = 'date' if 'date' in merged.columns else ('game_day' if 'game_day' in merged.columns else None)
    if date_col is None:
        merged['__idx'] = range(len(merged))
        order_cols = ['__idx']
    else:
        order_cols = [date_col,'game_id']
    merged = merged.sort_values(order_cols)
    records = []
    for conf, grp in merged.groupby('conference'):
        preds_list = []
        labels_list = []
        for idx, r in grp.iterrows():
            preds_list.append(float(r['pred_prob']))
            labels_list.append(int(r['label']))
            p_arr = np.array(preds_list, dtype=float)
            l_arr = np.array(labels_list, dtype=int)
            games_seen = len(l_arr)
            acc = float(((p_arr >= 0.5) == l_arr).mean())
            try:
                ll = float(log_loss(l_arr, p_arr, labels=[0,1]))
            except ValueError:
                ll = np.nan
            brier = float(np.mean((p_arr - l_arr)**2))
            if games_seen >= window:
                w_preds = p_arr[-window:]
                w_labels = l_arr[-window:]
                w_acc = float(((w_preds >= 0.5) == w_labels).mean())
                try:
                    w_ll = float(log_loss(w_labels, w_preds, labels=[0,1]))
                except ValueError:
                    w_ll = np.nan
                w_brier = float(np.mean((w_preds - w_labels)**2))
            else:
                w_acc = np.nan
                w_ll = np.nan
                w_brier = np.nan
            records.append({
                'conference': conf,
                'games_seen_conf': games_seen,
                'cumulative_accuracy_conf': acc,
                'cumulative_logloss_conf': ll,
                'cumulative_brier_conf': brier,
                f'rolling_accuracy_conf_{window}': w_acc,
                f'rolling_logloss_conf_{window}': w_ll,
                f'brier_score_conf_{window}': w_brier,
            })
    return pd.DataFrame(records)


def append_and_save(df: pd.DataFrame, window: int) -> pd.DataFrame:
    if CONF_CSV.exists():
        prev = pd.read_csv(CONF_CSV)
        combined = pd.concat([prev, df], ignore_index=True)
        # Dedup by conference + games_seen_conf keeping last
        combined = combined.sort_values(['conference','games_seen_conf']).drop_duplicates(['conference','games_seen_conf'], keep='last')
    else:
        combined = df
    combined.to_csv(CONF_CSV, index=False)
    return combined


def write_markdown(df: pd.DataFrame, window: int):
    if df.empty:
        return
    latest = df.sort_values(['conference','games_seen_conf']).groupby('conference').tail(1)
    lines = ["# Conference Drift Metrics","",f"Window Size: {window}",""]
    for _, r in latest.sort_values('conference').iterrows():
        lines.append(f"## {r['conference']}")
        lines.append(f"Games Seen: {int(r['games_seen_conf'])}")
        lines.append(f"Cumulative Accuracy: {r['cumulative_accuracy_conf']:.3f}")
        if not np.isnan(r[f'rolling_accuracy_conf_{window}']):
            lines.append(f"Rolling {window} Accuracy: {r[f'rolling_accuracy_conf_{window}']:.3f}")
        if not np.isnan(r['cumulative_logloss_conf']):
            lines.append(f"Cumulative LogLoss: {r['cumulative_logloss_conf']:.3f}")
        if not np.isnan(r[f'rolling_logloss_conf_{window}']):
            lines.append(f"Rolling {window} LogLoss: {r[f'rolling_logloss_conf_{window}']:.3f}")
        if not np.isnan(r['cumulative_brier_conf']):
            lines.append(f"Cumulative Brier: {r['cumulative_brier_conf']:.3f}")
        if not np.isnan(r[f'brier_score_conf_{window}']):
            lines.append(f"Rolling {window} Brier: {r[f'brier_score_conf_{window}']:.3f}")
        lines.append("")
    CONF_MD.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description='Aggregate prediction drift metrics at conference level.')
    parser.add_argument('--window', type=int, default=25, help='Rolling window size (default 25)')
    args = parser.parse_args()
    df = build_conference_metrics(window=args.window)
    if df.empty:
        print('No conference metrics produced (missing sources?).')
        return
    combined = append_and_save(df, window=args.window)
    write_markdown(combined, window=args.window)
    print(f"Conference drift metrics updated. Rows: {len(combined)}")
    print(f"CSV: {CONF_CSV}")
    print(f"Markdown: {CONF_MD}")

if __name__ == '__main__':
    main()
