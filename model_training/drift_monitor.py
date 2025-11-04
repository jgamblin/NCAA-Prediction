"""Drift Monitoring for NCAA Prediction Models

This script computes rolling performance metrics over the current season to help
identify prediction drift. It reads Completed_Games.csv to obtain historical
labeled outcomes and joins with the latest predictions from NCAA_Game_Predictions.csv.

Outputs:
 - data/Drift_Metrics.csv : Append-only log of per-game rolling metrics
 - data/DRIFT_METRICS.md  : Markdown summary (latest snapshot)

Metrics tracked (after each game chronologically within the season):
 - games_seen: Count of games processed in the current season
 - rolling_accuracy_25: Accuracy over last 25 games (if >= 25, else null)
 - rolling_logloss_25: Log loss over last 25 games
 - cumulative_accuracy: Accuracy over all season games so far
 - cumulative_logloss: Log loss over all season games so far
 - brier_score_25: Brier score over last 25 games
 - cumulative_brier: Brier score over all games so far
 - date, season, game_id
 - model_name: Extracted from prediction file if present (column 'model' or inferred)

Assumptions:
 - Completed_Games.csv has columns: game_id, Season, Date, Team1, Team2, Winner
 - NCAA_Game_Predictions.csv has columns: game_id, Season, Date, Team1, Team2, pred_prob, prediction (1 if Team1 predicted win else 0), model (optional)
 - Winner equals Team1 if Team1 won else Team2; we'll convert to binary label: 1 if Team1 won else 0.

If predictions for some completed games are missing, those games are skipped.
If multiple predictions per game_id exist, latest (by Date or file order) is used.

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

DATA_DIR = Path("data")
COMPLETED = DATA_DIR / "Completed_Games.csv"
PREDICTIONS = DATA_DIR / "NCAA_Game_Predictions.csv"
DRIFT_CSV = DATA_DIR / "Drift_Metrics.csv"
DRIFT_MD = DATA_DIR / "DRIFT_METRICS.md"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not COMPLETED.exists():
        raise FileNotFoundError(f"Missing completed games file: {COMPLETED}")
    if not PREDICTIONS.exists():
        raise FileNotFoundError(f"Missing predictions file: {PREDICTIONS}")
    comp = pd.read_csv(COMPLETED)
    preds = pd.read_csv(PREDICTIONS)
    # Standardize column names casing
    for df in (comp, preds):
        df.columns = [c.strip() for c in df.columns]
    return comp, preds


def prepare_labels(comp: pd.DataFrame) -> pd.DataFrame:
    # Expect Winner column containing the team name of the winner
    if "Winner" not in comp.columns:
        raise ValueError("Completed games data must contain 'Winner' column.")
    if "Team1" not in comp.columns:
        raise ValueError("Completed games data must contain 'Team1' column.")
    comp = comp.copy()
    comp["label"] = (comp["Winner"] == comp["Team1"]).astype(int)
    return comp


def merge_predictions(comp: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    # Ensure game_id present
    if "game_id" not in comp.columns or "game_id" not in preds.columns:
        raise ValueError("Both datasets must contain 'game_id'.")

    # Deduplicate predictions: keep last occurrence per game_id
    # Sort predictions deterministically: by Date if present else by game_id then index
    if "Date" in preds.columns:
        preds_sorted = preds.sort_values(["Date", "game_id"])  # explicit list avoids type ambiguity
    else:
        preds_sorted = preds.sort_values("game_id")
    preds_dedup = preds_sorted.drop_duplicates("game_id", keep="last")

    needed_cols = ["game_id", "pred_prob"]
    for col in needed_cols:
        if col not in preds_dedup.columns:
            raise ValueError(f"Predictions file must contain '{col}'.")

    merged = comp.merge(preds_dedup, on="game_id", suffixes=("_comp", "_pred"))

    # Determine model name if available
    if "model" in preds_dedup.columns:
        merged["model_name"] = preds_dedup.set_index("game_id")["model"].reindex(merged["game_id"]).values
    else:
        merged["model_name"] = "unknown"

    return merged


def compute_metrics(df: pd.DataFrame, window: int) -> pd.DataFrame:
    # Sort chronologically within season
    if "Date" not in df.columns:
        raise ValueError("Merged data must contain 'Date'.")
    if "Season" not in df.columns:
        raise ValueError("Merged data must contain 'Season'.")

    df_sorted = df.sort_values(["Season", "Date", "game_id"]).reset_index(drop=True)
    records = []

    for season, season_df in df_sorted.groupby("Season"):
        season_df = season_df.reset_index(drop=True)
        preds_list: list[float] = []
        labels_list: list[int] = []
        for idx in range(len(season_df)):
            row = season_df.iloc[idx]
            preds_list.append(float(row["pred_prob"]))
            labels_list.append(int(row["label"]))

            current_preds = np.array(preds_list, dtype=float)
            current_labels = np.array(labels_list, dtype=int)

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
                "date": row.get("Date"),
                "game_id": row.get("game_id"),
                "games_seen": games_seen,
                "cumulative_accuracy": cumulative_accuracy,
                "cumulative_logloss": cumulative_logloss,
                "cumulative_brier": cumulative_brier,
                "rolling_accuracy_{w}".format(w=window): rolling_accuracy,
                "rolling_logloss_{w}".format(w=window): rolling_logloss,
                "brier_score_{w}".format(w=window): brier_25,
                "model_name": row.get("model_name", "unknown"),
            })

    return pd.DataFrame(records)


def append_and_save(metrics: pd.DataFrame):
    if DRIFT_CSV.exists():
        prev = pd.read_csv(DRIFT_CSV)
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
        lines.append("")

    DRIFT_MD.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Monitor prediction drift with rolling metrics.")
    parser.add_argument("--window", type=int, default=25, help="Rolling window size for metrics (default: 25)")
    args = parser.parse_args()

    comp, preds = load_data()
    comp = prepare_labels(comp)
    merged = merge_predictions(comp, preds)

    metrics = compute_metrics(merged, window=args.window)
    combined = append_and_save(metrics)
    write_markdown(combined, window=args.window)

    print(f"Drift metrics updated. Rows now: {len(combined)}")
    print(f"CSV: {DRIFT_CSV}")
    print(f"Markdown: {DRIFT_MD}")


if __name__ == "__main__":
    main()
