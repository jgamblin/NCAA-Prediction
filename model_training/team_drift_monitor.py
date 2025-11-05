"""Per-Team Drift Monitoring

Generates drift / performance metrics on a per-team basis keyed by team_id.
This complements the global drift monitor (drift_monitor.py) which aggregates
across all games.

Usage:
    python -m model_training.team_drift_monitor --window 25

Outputs:
    data/Drift_Metrics_By_Team.csv  (append-safe, dedup season+team_id+game_id)
    data/DRIFT_METRICS_BY_TEAM.md   (latest season snapshot per team)

Metrics (per team perspective):
    games_seen_team
    cumulative_accuracy_team / cumulative_logloss_team / cumulative_brier_team
    rolling_accuracy_team_{window} / rolling_logloss_team_{window} / brier_score_team_{window}
    cumulative_expected_wins_team (sum of team_pred_prob)
    cumulative_actual_wins_team (sum of team_label)

Edge Cases:
    - Missing team IDs -> derived via deterministic name hash (team_id_utils.ensure_team_ids)
    - Missing prediction probabilities -> metrics with prob-dependent stats become NaN
    - Duplicate game rows -> dedup by (game_id, team_id) keeping last (highest priority from merge)

"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import log_loss
try:
    from config.load_config import get_config
    _cfg = get_config()
except Exception:
    _cfg = {}
_config_version = _cfg.get('config_version','unknown')
from model_training.drift_monitor import load_completed, load_prediction_sources, prepare_labels, merge_predictions
try:  # pragma: no cover
    from config.versioning import get_commit_hash
    _commit_hash = get_commit_hash()
except Exception:  # noqa: BLE001
    _commit_hash = 'unknown'
from model_training.team_id_utils import ensure_team_ids, melt_games_to_team_rows

DATA_DIR = Path("data")
TEAM_DRIFT_CSV = DATA_DIR / "Drift_Metrics_By_Team.csv"
TEAM_DRIFT_MD = DATA_DIR / "DRIFT_METRICS_BY_TEAM.md"
ANOMALY_CSV = DATA_DIR / "Team_Anomalies.csv"
ANOMALY_THRESHOLD_ACC_DELTA = float(_cfg.get('anomaly_accuracy_delta_threshold', 0.25))
ANOMALY_MIN_GAMES = int(_cfg.get('anomaly_min_games', 15))


def build_team_rows(window: int, season_filter: str | None = None) -> pd.DataFrame:
    comp = load_completed()
    comp = prepare_labels(comp)
    preds = load_prediction_sources()
    merged = merge_predictions(comp, preds)

    # Completed games only if status available
    if 'game_status' in merged.columns:
        merged = merged[merged['game_status'] == 'Final']
    if season_filter and 'Season' in merged.columns:
        merged = merged[merged['Season'] == season_filter]

    if merged.empty:
        return pd.DataFrame()

    # Ensure team IDs present / deterministic
    merged = ensure_team_ids(merged, home_col='home_team', away_col='away_team')

    # Create per-team perspective rows
    team_rows = melt_games_to_team_rows(merged)

    # Drop potential duplicates keeping last (merged already prioritized predictions)
    team_rows = team_rows.sort_values(['game_id', 'team_id']).drop_duplicates(['game_id', 'team_id'], keep='last')

    # Sort chronological within season per team
    if 'date' in team_rows.columns:
        team_rows = team_rows.sort_values(['season', 'team_id', 'date', 'game_id'])
    else:
        team_rows = team_rows.sort_values(['season', 'team_id', 'game_id'])

    metrics_records = []

    for (season, team_id), grp in team_rows.groupby(['season', 'team_id']):
        grp = grp.reset_index(drop=True)
        preds_list: list[float] = []
        labels_list: list[int] = []
        for idx, row in grp.iterrows():
            pred = row.get('team_pred_prob')
            label = row.get('team_label')
            if label is None:
                # Skip metrics until label exists
                continue
            if pred is not None:
                preds_list.append(float(pred))
            else:
                preds_list.append(np.nan)
            labels_list.append(int(label))

            current_preds = np.array(preds_list, dtype=float)
            current_labels = np.array(labels_list, dtype=int)
            games_seen = len(current_labels)
            # Accuracy ignoring NaN preds (treat threshold on available preds)
            valid_mask = ~np.isnan(current_preds)
            if valid_mask.any():
                cumulative_accuracy = float(((current_preds[valid_mask] >= 0.5) == current_labels[valid_mask]).mean())
                try:
                    cumulative_logloss = float(log_loss(current_labels[valid_mask], current_preds[valid_mask], labels=[0,1]))
                except ValueError:
                    cumulative_logloss = np.nan
                cumulative_brier = float(np.mean((current_preds[valid_mask] - current_labels[valid_mask]) ** 2))
                expected_sum = float(np.nansum(current_preds))
            else:
                cumulative_accuracy = np.nan
                cumulative_logloss = np.nan
                cumulative_brier = np.nan
                expected_sum = np.nan
            actual_sum = int(current_labels.sum())

            if games_seen >= window and valid_mask[-window:].any():
                window_preds = current_preds[-window:][~np.isnan(current_preds[-window:])]
                window_labels = current_labels[-window:][~np.isnan(current_preds[-window:])]
                if len(window_preds) == len(window_labels) and len(window_preds) > 0:
                    rolling_accuracy = float(((window_preds >= 0.5) == window_labels).mean())
                    try:
                        rolling_logloss = float(log_loss(window_labels, window_preds, labels=[0,1]))
                    except ValueError:
                        rolling_logloss = np.nan
                    brier_w = float(np.mean((window_preds - window_labels) ** 2))
                else:
                    rolling_accuracy = np.nan
                    rolling_logloss = np.nan
                    brier_w = np.nan
            else:
                rolling_accuracy = np.nan
                rolling_logloss = np.nan
                brier_w = np.nan

            metrics_records.append({
                'season': season,
                'team_id': team_id,
                'date': row.get('date'),
                'game_id': row.get('game_id'),
                'games_seen_team': games_seen,
                'cumulative_accuracy_team': cumulative_accuracy,
                'cumulative_logloss_team': cumulative_logloss,
                'cumulative_brier_team': cumulative_brier,
                f'rolling_accuracy_team_{window}': rolling_accuracy,
                f'rolling_logloss_team_{window}': rolling_logloss,
                f'brier_score_team_{window}': brier_w,
                'cumulative_expected_wins_team': expected_sum,
                'cumulative_actual_wins_team': actual_sum,
                'config_version': _config_version,
                'commit_hash': _commit_hash,
            })

    return pd.DataFrame(metrics_records)


def append_and_save(metrics: pd.DataFrame) -> pd.DataFrame:
    if TEAM_DRIFT_CSV.exists():
        try:
            prev = pd.read_csv(TEAM_DRIFT_CSV)
        except Exception:
            prev = pd.DataFrame()
        combined = pd.concat([prev, metrics], ignore_index=True)
        combined = combined.drop_duplicates(['season', 'team_id', 'game_id'], keep='last')
    else:
        combined = metrics
    combined.to_csv(TEAM_DRIFT_CSV, index=False)
    return combined


def write_markdown(latest: pd.DataFrame, window: int):
    if latest.empty:
        return
    # Latest row per team per season
    latest_per_team = latest.sort_values(['season','team_id','games_seen_team']).groupby(['season','team_id']).tail(1)

    lines = ["# Per-Team Drift Metrics", "", f"Window Size: {window}", ""]
    # Group by season for readability
    for season, season_grp in latest_per_team.groupby('season'):
        lines.append(f"## Season {season}")
        lines.append("")
        for _, row in season_grp.sort_values('team_id').iterrows():
            lines.append(f"### Team {row['team_id']}")
            lines.append(f"Games Seen: {int(row['games_seen_team'])}")
            acc = row['cumulative_accuracy_team']
            if not np.isnan(acc):
                lines.append(f"Cumulative Accuracy: {acc:.3f}")
            r_acc = row.get(f'rolling_accuracy_team_{window}', np.nan)
            if not np.isnan(r_acc):
                lines.append(f"Rolling {window} Accuracy: {r_acc:.3f}")
            clog = row['cumulative_logloss_team']
            if not np.isnan(clog):
                lines.append(f"Cumulative LogLoss: {clog:.3f}")
            rlog = row.get(f'rolling_logloss_team_{window}', np.nan)
            if not np.isnan(rlog):
                lines.append(f"Rolling {window} LogLoss: {rlog:.3f}")
            cbrier = row['cumulative_brier_team']
            if not np.isnan(cbrier):
                lines.append(f"Cumulative Brier: {cbrier:.3f}")
            rbrier = row.get(f'brier_score_team_{window}', np.nan)
            if not np.isnan(rbrier):
                lines.append(f"Rolling {window} Brier: {rbrier:.3f}")
            exp = row.get('cumulative_expected_wins_team', np.nan)
            act = row.get('cumulative_actual_wins_team', np.nan)
            if not np.isnan(exp) and not np.isnan(act):
                lines.append(f"Expected Wins: {exp:.1f}")
                lines.append(f"Actual Wins: {act:.0f}")
            lines.append("")
        lines.append("")

    TEAM_DRIFT_MD.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Per-team drift monitoring keyed by team_id.")
    parser.add_argument("--window", type=int, default=25, help="Rolling window size (default: 25)")
    parser.add_argument("--season", type=str, default=None, help="Optional season filter (e.g., 2025-26)")
    args = parser.parse_args()

    metrics = build_team_rows(window=args.window, season_filter=args.season)
    if metrics.empty:
        print("No per-team metrics computed (no merged rows).")
        return
    combined = append_and_save(metrics)
    write_markdown(combined, window=args.window)
    try:
        detect_and_save_anomalies(combined, window=args.window)
    except Exception as e:
        print(f"Anomaly detection skipped: {e}")
    print(f"Per-team drift metrics updated. Rows now: {len(combined)}")
    print(f"CSV: {TEAM_DRIFT_CSV}")
    print(f"Markdown: {TEAM_DRIFT_MD}")

if __name__ == "__main__":
    main()


def detect_and_save_anomalies(df: pd.DataFrame, window: int):
    """Identify teams whose recent rolling accuracy deviates sharply from cumulative.

    Criteria (simple heuristic):
      - games_seen_team >= ANOMALY_MIN_GAMES
      - rolling_accuracy_team_window available
      - abs(rolling - cumulative) >= ANOMALY_THRESHOLD_ACC_DELTA
    """
    if df.empty:
        return
    roll_col = f'rolling_accuracy_team_{window}'
    needed = {'team_id','season','games_seen_team','cumulative_accuracy_team', roll_col}
    if not needed.issubset(df.columns):
        return
    latest_per_team = df.sort_values(['season','team_id','games_seen_team']).groupby(['season','team_id']).tail(1)
    latest_per_team = latest_per_team[latest_per_team['games_seen_team'] >= ANOMALY_MIN_GAMES]
    if latest_per_team.empty:
        return
    latest_per_team['acc_delta'] = (latest_per_team[roll_col] - latest_per_team['cumulative_accuracy_team']).abs()
    anomalies = latest_per_team[latest_per_team['acc_delta'] >= ANOMALY_THRESHOLD_ACC_DELTA].copy()
    if anomalies.empty:
        print("No team anomalies detected.")
        return
    anomalies = anomalies.sort_values('acc_delta', ascending=False)
    anomalies['config_version'] = _config_version
    anomalies['commit_hash'] = _commit_hash
    anomalies.to_csv(ANOMALY_CSV, index=False)
    print(f"Anomalies detected: {len(anomalies)} (written {ANOMALY_CSV})")


def write_anomalies_markdown(anomalies_csv: Path, markdown_path: Path, window: int):
    """Generate TEAM_ANOMALIES.md from anomalies CSV (extracted from daily_pipeline logic).

    anomalies_csv: Path to Team_Anomalies.csv
    markdown_path: Output markdown file path
    window: rolling window size used for rolling accuracy
    """
    if not anomalies_csv.exists():
        return False
    an_df = pd.read_csv(anomalies_csv)
    if an_df.empty:
        return False
    roll_col = f'rolling_accuracy_team_{window}'
    lines = [
        "# Team Anomalies","",f"Window: {window}","",
        "| team_id | season | games_seen | cumulative_acc | rolling_acc | acc_delta |",
        "|---------|--------|------------|---------------|------------|----------|"
    ]
    for _, r in an_df.iterrows():
        lines.append(
            f"| {r['team_id']} | {r['season']} | {int(r['games_seen_team'])} | "
            f"{r['cumulative_accuracy_team']:.3f} | {r.get(roll_col, float('nan')):.3f} | {r.get('acc_delta', float('nan')):.3f} |"
        )
    markdown_path.write_text("\n".join(lines))
    return True
