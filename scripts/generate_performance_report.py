#!/usr/bin/env python3
"""Generate performance.md and supporting charts from pipeline artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import matplotlib

matplotlib.use("Agg")  # Headless rendering for CI / cron
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import PercentFormatter

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
ASSET_DIR = DOCS_DIR / "performance"
REPORT_PATH = REPO_ROOT / "performance.md"
ACCURACY_CSV = DATA_DIR / "Accuracy_Report.csv"
DRIFT_CSV = DATA_DIR / "Drift_Metrics.csv"

sns.set_theme(style="whitegrid")


def _load_csv(path: Path, parse_dates: Optional[list[str]] = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=parse_dates)
    except Exception:
        return pd.DataFrame()


def _plot_accuracy_trend(df: pd.DataFrame) -> Optional[str]:
    if df.empty:
        return None
    outfile = ASSET_DIR / "daily_accuracy.png"
    plt.figure(figsize=(9, 4))
    plt.plot(df["date"], df["accuracy"], marker="o", label="Daily Accuracy")
    if "rolling_accuracy" in df.columns:
        plt.plot(df["date"], df["rolling_accuracy"], label="7-Day Rolling")
    plt.gca().yaxis.set_major_formatter(PercentFormatter(1.0))
    plt.ylim(0, 1.0)
    plt.ylabel("Accuracy")
    plt.xlabel("Date")
    plt.title("Daily Prediction Accuracy")
    plt.legend(loc="lower left")
    plt.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outfile, dpi=150)
    plt.close()
    return outfile.relative_to(REPO_ROOT).as_posix()


def _plot_confidence_trend(df: pd.DataFrame) -> Optional[str]:
    if df.empty or "avg_confidence" not in df.columns:
        return None
    outfile = ASSET_DIR / "average_confidence.png"
    plt.figure(figsize=(9, 4))
    plt.plot(df["date"], df["avg_confidence"], marker="o", color="#1f77b4")
    plt.gca().yaxis.set_major_formatter(PercentFormatter(1.0))
    plt.ylim(0, 1.0)
    plt.ylabel("Average Confidence")
    plt.xlabel("Date")
    plt.title("Average Prediction Confidence")
    plt.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outfile, dpi=150)
    plt.close()
    return outfile.relative_to(REPO_ROOT).as_posix()


def _derive_accuracy_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    working = df.copy()
    if working["date"].dtype != "datetime64[ns]":
        working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"]).sort_values("date")
    working["rolling_accuracy"] = working["correct_predictions"].rolling(7).sum() / working["games_completed"].rolling(7).sum()
    return working


def _drift_snapshot(df: pd.DataFrame) -> str:
    if df.empty:
        return "No drift metrics available yet. Run the drift monitor to populate `data/Drift_Metrics.csv`."
    try:
        df = df.copy()
        date_col = "date" if "date" in df.columns else "Date"
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col]).sort_values(["season", date_col, "games_seen"])
        latest = df.tail(1).iloc[0]
        season = latest.get("season", "unknown")
        games_seen = int(latest.get("games_seen", 0))
        acc = latest.get("cumulative_accuracy")
        logloss = latest.get("cumulative_logloss")
        brier = latest.get("cumulative_brier")
        return (
            f"Latest drift snapshot (Season {season}, {games_seen} games): "
            f"accuracy {acc:.3f}, logloss {logloss:.3f}, brier {brier:.3f}."
        )
    except Exception:
        return "Unable to parse drift metrics; verify `data/Drift_Metrics.csv`."


def main() -> None:
    accuracy_df = _derive_accuracy_features(_load_csv(ACCURACY_CSV, parse_dates=["date"]))
    drift_df = _load_csv(DRIFT_CSV)

    accuracy_chart = _plot_accuracy_trend(accuracy_df)
    confidence_chart = _plot_confidence_trend(accuracy_df)

    lines: list[str] = []
    lines.append("# 📊 Model Performance Dashboard")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    if accuracy_df.empty:
        lines.append("No accuracy history available yet. Run the daily pipeline to populate `data/Accuracy_Report.csv`.")
    else:
        total_games = int(accuracy_df["games_completed"].sum())
        total_correct = int(accuracy_df["correct_predictions"].sum())
        overall_accuracy = total_correct / total_games if total_games else 0.0
        latest_row = accuracy_df.tail(1).iloc[0]
        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Overall Accuracy**: {overall_accuracy:.2%} ({total_correct}/{total_games})")
        lines.append(f"- **Most Recent Day**: {latest_row['date'].strftime('%Y-%m-%d')} — accuracy {latest_row['accuracy']:.2%} on {int(latest_row['games_completed'])} games")
        lines.append(f"- **Average Confidence (latest day)**: {latest_row.get('avg_confidence', float('nan')):.2%}")
        lines.append("")

        if accuracy_chart:
            lines.append("## Daily Accuracy")
            lines.append("")
            lines.append(f"![Daily Accuracy]({accuracy_chart})")
            lines.append("")
        if confidence_chart:
            lines.append("## Average Confidence")
            lines.append("")
            lines.append(f"![Average Confidence]({confidence_chart})")
            lines.append("")

        lines.append("### Recent History")
        lines.append("")
        lines.append("| Date | Games | Correct | Accuracy | Avg Confidence |")
        lines.append("|------|-------|---------|----------|----------------|")
        for row in accuracy_df.tail(10).itertuples(index=False):
            date_str = row.date.strftime('%Y-%m-%d') if isinstance(row.date, pd.Timestamp) else str(row.date)
            games_completed = int(float(getattr(row, 'games_completed', 0) or 0))
            correct_predictions = int(float(getattr(row, 'correct_predictions', 0) or 0))
            accuracy_pct = float(getattr(row, 'accuracy', 0.0) or 0.0)
            avg_conf = float(getattr(row, 'avg_confidence', 0.0) or 0.0)
            lines.append(
                f"| {date_str} | {games_completed} | {correct_predictions} | {accuracy_pct:.2%} | {avg_conf:.2%} |"
            )
        lines.append("")

    lines.append("## Drift Snapshot")
    lines.append("")
    lines.append(_drift_snapshot(drift_df))
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ performance.md updated at {REPORT_PATH}")


if __name__ == "__main__":  # pragma: no cover
    main()
