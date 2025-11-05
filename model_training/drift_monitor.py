"""Refactored Drift Monitoring

Reads prediction sources (live + backfill) and completed game outcomes, then
computes rolling and cumulative performance metrics per season. Priority order
for prediction rows per game_id: live > backfill_initial > reconstructed (if added later).

Sources:
 - data/prediction_log.csv         (live operational predictions)
 - data/historical_backfill.csv    (initial backfill predictions)
 - data/Completed_Games.csv        (game outcomes & scores)

Outputs:
 - data/Drift_Metrics.csv  (append-safe; dedup by season+game_id)
 - data/DRIFT_METRICS.md   (latest season snapshots)

Metrics:
 - games_seen
 - cumulative_accuracy / logloss / brier
 - rolling_accuracy_{window} / rolling_logloss_{window} / brier_score_{window}
 - model_type, model_version (from prediction row)
 - source (live/backfill_initial)

Run:
    python -m model_training.drift_monitor --window 25
"""
from __future__ import annotations
import argparse
import os
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import log_loss

PRED_LOG = Path("data") / "prediction_log.csv"
BACKFILL = Path("data") / "historical_backfill.csv"

DATA_DIR = Path("data")
COMPLETED = DATA_DIR / "Completed_Games.csv"
PREDICTIONS = DATA_DIR / "NCAA_Game_Predictions.csv"
DRIFT_CSV = DATA_DIR / "Drift_Metrics.csv"
DRIFT_MD = DATA_DIR / "DRIFT_METRICS.md"


def load_completed() -> pd.DataFrame:
    if not COMPLETED.exists():
        raise FileNotFoundError(f"Missing completed games file: {COMPLETED}")
    comp = pd.read_csv(COMPLETED)
    comp.columns = [c.strip() for c in comp.columns]
    # Standardize date column alias
    if "date" not in comp.columns and "game_day" in comp.columns:
        comp["date"] = comp["game_day"]
    return comp

def load_prediction_sources() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if PRED_LOG.exists():
        live_df = pd.read_csv(PRED_LOG)
        frames.append(live_df)
    if BACKFILL.exists():
        back_df = pd.read_csv(BACKFILL)
        frames.append(back_df)
    if not frames:
        raise FileNotFoundError("No prediction sources found (prediction_log.csv or historical_backfill.csv)")
    preds = pd.concat(frames, ignore_index=True)
    # Ensure required probability columns
    if "home_win_probability" not in preds.columns:
        raise ValueError("Prediction source missing 'home_win_probability' column")
    return preds


def prepare_labels(comp: pd.DataFrame) -> pd.DataFrame:
    """Add binary label column.

    Priority:
      1. If Winner & Team1 columns exist, label = (Winner == Team1)
      2. Else if home_score & away_score exist, label = (home_score > away_score) treating home as Team1.
      3. Else attempt inference using home_team/away_team + winner-like column names.
    Falls back gracefully if data only has scores.
    """
    comp = comp.copy()
    if "Winner" in comp.columns and "Team1" in comp.columns:
        comp["label"] = (comp["Winner"] == comp["Team1"]).astype(int)
        return comp
    # ESPN schema present in repository: use home/away scores
    if "home_score" in comp.columns and "away_score" in comp.columns:
        comp["label"] = (comp["home_score"] > comp["away_score"]).astype(int)
        return comp
    # Fallback: look for winner-like column
    winner_col = next((c for c in comp.columns if c.lower() in {"winner","winning_team"}), None)
    if winner_col and all(x in comp.columns for x in ["home_team","away_team"]):
        comp["label"] = (comp[winner_col] == comp["home_team"]).astype(int)
        return comp
    raise ValueError("Unable to derive labels: expected (Winner+Team1) or (home_score+away_score) columns.")


def merge_predictions(comp: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    if "game_id" not in comp.columns or "game_id" not in preds.columns:
        raise ValueError("Both datasets must contain 'game_id'.")
    # Priority: live > backfill_initial > reconstructed (future). Keep best per game_id.
    priority = {"live": 3, "backfill_initial": 2, "reconstructed": 1}
    preds['__priority'] = preds['source'].map(priority).fillna(0)
    # Deduplicate keeping highest priority then latest timestamp
    preds_sorted = preds.sort_values(['game_id', '__priority', 'prediction_timestamp'])
    preds_dedup = preds_sorted.groupby('game_id').tail(1)

    # Add pred_prob alias for computations (assume home_win_probability)
    preds_dedup['pred_prob'] = preds_dedup['home_win_probability']

    merged = comp.merge(preds_dedup, on='game_id', how='inner', suffixes=('_comp', '_pred'))
    # Ensure date column (prefer comp date)
    if 'date' not in merged.columns and 'game_date' in merged.columns:
        merged['date'] = merged['game_date']
    # Fill Season if missing
    if 'Season' not in merged.columns and 'season' in merged.columns:
        merged['Season'] = merged['season']
    # Provide model_name
    if 'model_type' in merged.columns:
        merged['model_name'] = merged['model_type']
    else:
        merged['model_name'] = 'unknown'
    return merged


def compute_metrics(df: pd.DataFrame, window: int) -> pd.DataFrame:
    # Sort chronologically within season; accept lowercase 'date'
    date_col = None
    if "Date" in df.columns:
        date_col = "Date"
    elif "date" in df.columns:
        date_col = "date"
    else:
        raise ValueError("Merged data must contain 'Date' or 'date'.")
    if "Season" not in df.columns:
        # Attempt to map season from comp dataset using game_id if season missing after merge
        if "Season_comp" in df.columns:
            df["Season"] = df["Season_comp"]
        elif "season" in df.columns:
            df["Season"] = df["season"]
        else:
            raise ValueError("Merged data must contain 'Season' (or season/Season_comp).")

    df_sorted = df.sort_values(["Season", date_col, "game_id"]).reset_index(drop=True)
    records = []

    for season, season_df in df_sorted.groupby("Season"):
        season_df = season_df.reset_index(drop=True)
        preds_list: list[float] = []
        labels_list: list[int] = []
        expected_cumulative: list[float] = []  # running sum of predicted probs
        actual_cumulative: list[int] = []      # running sum of labels
        for idx in range(len(season_df)):
            row = season_df.iloc[idx]
            preds_list.append(float(row["pred_prob"]))
            labels_list.append(int(row["label"]))

            current_preds = np.array(preds_list, dtype=float)
            current_labels = np.array(labels_list, dtype=int)
            expected_sum = float(current_preds.sum())
            actual_sum = int(current_labels.sum())
            expected_cumulative.append(expected_sum)
            actual_cumulative.append(actual_sum)

            games_seen: int = idx + 1
            cumulative_accuracy = float(((current_preds >= 0.5) == current_labels).mean())
            try:
                cumulative_logloss = float(log_loss(current_labels, current_preds, labels=[0, 1]))
            except ValueError:
                cumulative_logloss = np.nan
            cumulative_brier = float(np.mean((current_preds - current_labels) ** 2))

            if games_seen >= window:
                window_preds = current_preds[-window:]
                window_labels = current_labels[-window:]
                rolling_accuracy = float(((window_preds >= 0.5) == window_labels).mean())
                try:
                    rolling_logloss = float(log_loss(window_labels, window_preds, labels=[0, 1]))
                except ValueError:
                    rolling_logloss = np.nan
                brier_25 = float(np.mean((window_preds - window_labels) ** 2))
            else:
                rolling_accuracy = np.nan
                rolling_logloss = np.nan
                brier_25 = np.nan

            records.append({
                "season": season,
                "date": row.get(date_col),
                "game_id": row.get("game_id"),
                "games_seen": games_seen,
                "cumulative_accuracy": cumulative_accuracy,
                "cumulative_logloss": cumulative_logloss,
                "cumulative_brier": cumulative_brier,
                "rolling_accuracy_{w}".format(w=window): rolling_accuracy,
                "rolling_logloss_{w}".format(w=window): rolling_logloss,
                "brier_score_{w}".format(w=window): brier_25,
                "model_name": row.get("model_name", "unknown"),
                "model_version": row.get("model_version", ""),
                "source": row.get("source", ""),
                "cumulative_expected_home_wins": expected_sum,
                "cumulative_actual_home_wins": actual_sum,
            })

    return pd.DataFrame(records)


def append_and_save(metrics: pd.DataFrame):
    if DRIFT_CSV.exists():
        try:
            prev = pd.read_csv(DRIFT_CSV)
        except Exception:
            prev = pd.DataFrame()
        combined = pd.concat([prev, metrics], ignore_index=True)
        # Drop potential duplicates (same season + game_id)
        combined = combined.drop_duplicates(["season", "game_id"], keep="last")
    else:
        combined = metrics
    combined.to_csv(DRIFT_CSV, index=False)
    return combined


def write_markdown(latest: pd.DataFrame, window: int):
    if latest.empty:
        return
    # Latest per season = last row of each season
    latest_per_season = latest.sort_values(["season", "games_seen"]).groupby("season").tail(1)

    lines = ["# Drift Monitoring Metrics", "", f"Window Size: {window}", ""]
    for _, row in latest_per_season.iterrows():
        lines.append(f"## Season {row['season']}")
        lines.append("")
        lines.append(f"Games Seen: {int(row['games_seen'])}")
        lines.append(f"Cumulative Accuracy: {row['cumulative_accuracy']:.3f}")
        if not np.isnan(row[f'rolling_accuracy_{window}']):
            lines.append(f"Rolling {window} Accuracy: {row[f'rolling_accuracy_{window}']:.3f}")
        lines.append(f"Cumulative LogLoss: {row['cumulative_logloss']:.3f}" if not np.isnan(row['cumulative_logloss']) else "Cumulative LogLoss: NA")
        if not np.isnan(row[f'rolling_logloss_{window}']):
            lines.append(f"Rolling {window} LogLoss: {row[f'rolling_logloss_{window}']:.3f}")
        lines.append(f"Cumulative Brier: {row['cumulative_brier']:.3f}" if not np.isnan(row['cumulative_brier']) else "Cumulative Brier: NA")
        if not np.isnan(row[f'brier_score_{window}']):
            lines.append(f"Rolling {window} Brier: {row[f'brier_score_{window}']:.3f}")
        lines.append(f"Model: {row['model_name']}")
        mv = row.get('model_version', '')
        if mv:
            lines.append(f"Model Version: {mv[:12]}")
        # Expected vs observed
        exp = row.get('cumulative_expected_home_wins', np.nan)
        act = row.get('cumulative_actual_home_wins', np.nan)
        if not np.isnan(exp) and not np.isnan(act):
            diff = exp - act
            lines.append(f"Expected Home Wins: {exp:.1f}")
            lines.append(f"Actual Home Wins: {act:.0f}")
            lines.append(f"Expected - Actual: {diff:+.1f}")
        lines.append("")

    DRIFT_MD.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Monitor prediction drift using logged & backfilled predictions.")
    parser.add_argument("--window", type=int, default=25, help="Rolling window size (default: 25)")
    parser.add_argument("--season", type=str, default=None, help="Optional season filter (e.g., 2025-26)")
    args = parser.parse_args()

    comp = load_completed()
    comp = prepare_labels(comp)
    preds = load_prediction_sources()

    merged = merge_predictions(comp, preds)
    # Filter to completed games only (game_status == Final if present)
    if 'game_status' in merged.columns:
        merged = merged[merged['game_status'] == 'Final']
    # Optional season restriction
    if args.season and 'Season' in merged.columns:
        merged = merged[merged['Season'] == args.season]

    if merged.empty:
        print("No merged prediction/outcome rows to compute drift.")
        return

    metrics = compute_metrics(merged, window=args.window)
    combined = append_and_save(metrics)
    write_markdown(combined, window=args.window)

    print(f"Drift metrics updated. Rows now: {len(combined)}")
    print(f"CSV: {DRIFT_CSV}")
    print(f"Markdown: {DRIFT_MD}")


if __name__ == "__main__":
    main()
