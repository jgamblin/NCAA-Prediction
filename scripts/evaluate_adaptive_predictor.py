#!/usr/bin/env python3
"""Comprehensive evaluation harness for AdaptivePredictor bias monitoring.

Generates out-of-sample predictions via leave-one-season-out evaluation and
reports accuracy as well as home-pick share by season and conference.

Outputs CSV summaries under data/evaluation/ and a markdown synopsis under
docs/evaluation/ for the supplied configuration label.

Example:
    python scripts/evaluate_adaptive_predictor.py \
        --label tuned \
        --home-shift auto:0.55
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold

import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.model_params_loader import load_model_params
from data_collection.team_name_utils import normalize_team_name
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.prediction_logger import append_predictions as log_predictions

try:
    from data_collection.check_conference_coverage import MAJOR_CONFERENCES
except Exception:  # pragma: no cover - fallback when import fails
    MAJOR_CONFERENCES = {}

try:
    from config.load_config import get_config_version
    from config.versioning import get_commit_hash

    _config_version = get_config_version()
    _commit_hash = get_commit_hash()
except Exception:  # pragma: no cover - fallback when versioning unavailable
    _config_version = "unknown"
    _commit_hash = "unknown"

DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
EVAL_DATA_DIR = DATA_DIR / "evaluation"
EVAL_DOCS_DIR = DOCS_DIR / "evaluation"


def load_completed_games() -> pd.DataFrame:
    """Load completed games with derived outcomes and clean columns."""

    normalized_path = DATA_DIR / "Completed_Games_Normalized.csv"
    raw_path = DATA_DIR / "Completed_Games.csv"
    src = normalized_path if normalized_path.exists() else raw_path
    if not src.exists():
        raise FileNotFoundError(f"Completed games file not found: {src}")

    df = pd.read_csv(src)
    required_cols = {"home_team", "away_team"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Completed games missing columns: {sorted(missing)}")

    if "home_win" not in df.columns:
        score_cols = {"home_score", "away_score"}
        if not score_cols.issubset(df.columns):
            raise ValueError("home_win column absent and cannot be derived")
        df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)

    df = df.dropna(subset=["home_team", "away_team", "home_win"])
    if "season" not in df.columns:
        df["season"] = "Unknown"
    df["season"] = df["season"].fillna("Unknown").astype(str)
    return df


def build_conference_lookup() -> dict[str, str]:
    """Create mapping from normalized team name to conference label."""

    mapping: dict[str, str] = {}
    for conference, members in MAJOR_CONFERENCES.items():
        for team in members:
            normalized = normalize_team_name(team)
            mapping[normalized] = conference
    return mapping


def format_markdown_table(headers: list[str], rows: Iterable[Iterable[str]]) -> str:
    """Render a simple markdown table given headers and row strings."""

    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = ["| " + " | ".join(map(str, row)) + " |" for row in rows]
    return "\n".join([header_line, separator_line, *body_lines])


def prediction_splits(
    df: pd.DataFrame,
    groups: pd.Series,
) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    """Yield train/test indices for evaluation.

    Prefers leave-one-season-out to avoid evaluating a season the model saw
    during training. Falls back to 5-fold stratified splits if only one unique
    season is present.
    """

    unique_groups = groups.dropna().unique()
    if len(unique_groups) > 1:
        logo = LeaveOneGroupOut()
        return logo.split(df, df["home_win"], groups)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    return skf.split(df, df["home_win"])


def evaluate_configuration(
    df: pd.DataFrame,
    label: str,
    home_shift: str,
    min_games_threshold: str | int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Train/evaluate AdaptivePredictor for the supplied configuration."""

    params = load_model_params()
    model_params = params.get("adaptive_predictor", params.get("simple_predictor", {}))
    # Remove keys the AdaptivePredictor constructor does not support
    unsupported = {"use_sample_weights"}
    for key in unsupported:
        model_params.pop(key, None)

    groups = df["season"].fillna("Unknown")
    splits = list(prediction_splits(df, groups))
    if not splits:
        raise RuntimeError("No evaluation splits produced; dataset too small?")

    all_predictions: list[pd.DataFrame] = []

    for fold_idx, (train_idx, test_idx) in enumerate(splits, start=1):
        train = df.iloc[train_idx].copy()
        test = df.iloc[test_idx].copy()
        min_games_arg = (
            str(min_games_threshold)
            if isinstance(min_games_threshold, int)
            else min_games_threshold
        )

        predictor = AdaptivePredictor(
            n_estimators=model_params.get("n_estimators", 100),
            max_depth=model_params.get("max_depth", 20),
            min_samples_split=model_params.get("min_samples_split", 10),
            min_games_threshold=min_games_arg,
            calibrate=model_params.get("calibrate", True),
            calibration_method=model_params.get("calibration_method", "sigmoid"),
            home_court_logit_shift=home_shift,
            feature_importance_path=str(EVAL_DATA_DIR / f"{label}_feature_importance_fold{fold_idx}.csv"),
            confidence_temperature=model_params.get("confidence_temperature", 'auto'),
        )
        print(f"\n=== Fold {fold_idx}/{len(splits)} [{label}] ===")
        predictor.fit(train)
        preds = predictor.predict(test, skip_low_data=False)
        merged = preds.merge(
            test[["game_id", "season", "home_win"]],
            on="game_id",
            how="left",
        )
        merged["season"] = merged["season"].fillna("Unknown")
        merged["label"] = label
        all_predictions.append(merged)

    predictions = pd.concat(all_predictions, ignore_index=True)
    predictions["home_win"] = predictions["home_win"].astype(int)
    predictions["predicted_home_win"] = predictions["predicted_home_win"].astype(int)

    conf_lookup = build_conference_lookup()
    predictions["home_conf"] = predictions["home_team"].apply(
        lambda team: conf_lookup.get(team, "Other")
    )
    predictions["away_conf"] = predictions["away_team"].apply(
        lambda team: conf_lookup.get(team, "Other")
    )

    season_metrics = build_season_metrics(predictions)
    conference_metrics = build_conference_metrics(predictions)
    return predictions, season_metrics, conference_metrics


def build_season_metrics(preds: pd.DataFrame) -> pd.DataFrame:
    """Aggregate accuracy and bias metrics per season."""

    rows: list[dict[str, object]] = []
    grouped = preds.groupby(["label", "season"], dropna=False)
    for (label, season), grp in grouped:
        rows.append(
            {
                "label": label,
                "season": season,
                "games": int(len(grp)),
                "accuracy": float((grp["predicted_home_win"] == grp["home_win"]).mean()),
                "home_pick_rate": float(grp["predicted_home_win"].mean()),
                "home_win_rate": float(grp["home_win"].mean()),
                "avg_home_probability": float(grp["home_win_probability"].mean()),
                "avg_confidence": float(grp["confidence"].mean()),
            }
        )

    return pd.DataFrame(rows).sort_values(["label", "season"]).reset_index(drop=True)


def build_conference_metrics(preds: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics per conference, split by home/away role."""

    perspectives: list[pd.DataFrame] = []

    home_view = preds[
        [
            "label",
            "game_id",
            "home_conf",
            "home_win",
            "predicted_home_win",
            "home_win_probability",
        ]
    ].copy()
    home_view.rename(
        columns={
            "home_conf": "conference",
            "home_win": "team_win",
            "predicted_home_win": "team_pred_win",
            "home_win_probability": "team_prob_win",
        },
        inplace=True,
    )
    home_view["role"] = "home"
    perspectives.append(home_view)

    away_view = preds[
        [
            "label",
            "game_id",
            "away_conf",
            "home_win",
            "predicted_home_win",
            "away_win_probability",
        ]
    ].copy()
    away_view.rename(
        columns={
            "away_conf": "conference",
            "home_win": "team_win",
            "predicted_home_win": "team_pred_win",
            "away_win_probability": "team_prob_win",
        },
        inplace=True,
    )
    away_view["team_win"] = 1 - away_view["team_win"]
    away_view["team_pred_win"] = 1 - away_view["team_pred_win"]
    away_view["role"] = "away"
    perspectives.append(away_view)

    combined = pd.concat(perspectives, ignore_index=True)
    combined["conference"] = combined["conference"].fillna("Other")

    rows: list[dict[str, object]] = []
    grouped = combined.groupby(["label", "conference", "role"], dropna=False)
    for (label, conference, role), grp in grouped:
        rows.append(
            {
                "label": label,
                "conference": conference,
                "role": role,
                "games": int(len(grp)),
                "accuracy": float((grp["team_pred_win"] == grp["team_win"]).mean()),
                "pick_rate": float(grp["team_pred_win"].mean()),
                "win_rate": float(grp["team_win"].mean()),
                "avg_team_probability": float(grp["team_prob_win"].mean()),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["label", "conference", "role"])
        .reset_index(drop=True)
    )


def overall_metrics(season_metrics: pd.DataFrame) -> pd.DataFrame:
    """Compute overall metrics aggregated across seasons for each label."""

    cols = ["games", "accuracy", "home_pick_rate", "home_win_rate", "avg_home_probability", "avg_confidence"]
    overall_rows: list[dict[str, object]] = []
    for label, grp in season_metrics.groupby("label"):
        total_games = grp["games"].sum()
        weights = grp["games"].to_numpy(dtype=float) / total_games if total_games else np.zeros(len(grp))
        weighted = {
            col: float(np.dot(grp[col].to_numpy(dtype=float), weights)) if total_games else float("nan")
            for col in cols[1:]
        }
        overall_rows.append(
            {
                "label": label,
                "games": int(total_games),
                **weighted,
            }
        )
    return pd.DataFrame(overall_rows)


def write_outputs(
    label: str,
    predictions: pd.DataFrame,
    season_metrics: pd.DataFrame,
    conference_metrics: pd.DataFrame,
) -> None:
    """Persist evaluation artifacts to disk."""

    EVAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    season_path = EVAL_DATA_DIR / f"{label}_season_metrics.csv"
    conference_path = EVAL_DATA_DIR / f"{label}_conference_metrics.csv"
    season_metrics.to_csv(season_path, index=False)
    conference_metrics.to_csv(conference_path, index=False)

    overall = overall_metrics(season_metrics)
    overall_row = overall[overall["label"] == label].iloc[0].to_dict()

    markdown_lines = [
        f"# AdaptivePredictor Bias Evaluation ({label})",
        "",
        f"* Games evaluated: {overall_row['games']}",
        f"* Overall accuracy: {overall_row['accuracy']:.3f}",
        f"* Home pick rate: {overall_row['home_pick_rate']:.3f}",
        f"* Actual home win rate: {overall_row['home_win_rate']:.3f}",
        f"* Avg predicted home probability: {overall_row['avg_home_probability']:.3f}",
    ]

    markdown_lines.append("\n## Per-Season Metrics")
    season_subset = season_metrics[season_metrics["label"] == label]
    season_table = format_markdown_table(
        ["Season", "Games", "Accuracy", "Home Pick", "Home Win", "Avg Home P"],
        (
            (
                row["season"],
                row["games"],
                f"{row['accuracy']:.3f}",
                f"{row['home_pick_rate']:.3f}",
                f"{row['home_win_rate']:.3f}",
                f"{row['avg_home_probability']:.3f}",
            )
            for _, row in season_subset.iterrows()
        ),
    )
    markdown_lines.append(season_table)

    markdown_lines.append("\n## Conference Metrics (Home)")
    conf_home = conference_metrics[
        (conference_metrics["label"] == label) & (conference_metrics["role"] == "home")
    ]
    conf_home_table = format_markdown_table(
        ["Conference", "Games", "Accuracy", "Pick Rate", "Win Rate", "Avg Prob"],
        (
            (
                row["conference"],
                row["games"],
                f"{row['accuracy']:.3f}",
                f"{row['pick_rate']:.3f}",
                f"{row['win_rate']:.3f}",
                f"{row['avg_team_probability']:.3f}",
            )
            for _, row in conf_home.iterrows()
        ),
    )
    markdown_lines.append(conf_home_table)

    markdown_lines.append("\n## Conference Metrics (Away)")
    conf_away = conference_metrics[
        (conference_metrics["label"] == label) & (conference_metrics["role"] == "away")
    ]
    conf_away_table = format_markdown_table(
        ["Conference", "Games", "Accuracy", "Pick Rate", "Win Rate", "Avg Prob"],
        (
            (
                row["conference"],
                row["games"],
                f"{row['accuracy']:.3f}",
                f"{row['pick_rate']:.3f}",
                f"{row['win_rate']:.3f}",
                f"{row['avg_team_probability']:.3f}",
            )
            for _, row in conf_away.iterrows()
        ),
    )
    markdown_lines.append(conf_away_table)

    md_path = EVAL_DOCS_DIR / f"{label}_summary.md"
    md_path.write_text("\n".join(markdown_lines))

    print("\nEvaluation artifacts written:")
    print(f"  Seasons CSV:     {season_path}")
    print(f"  Conferences CSV: {conference_path}")
    print(f"  Markdown:        {md_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate AdaptivePredictor bias metrics")
    parser.add_argument("--label", default="current", help="Label for this configuration run")
    parser.add_argument(
        "--home-shift",
        default="auto:0.55",
        help="Home court logit shift mode (e.g., 'auto:0.55', 'none')",
    )
    parser.add_argument(
        "--min-games-threshold",
        default="auto",
        help="Minimum games threshold (int or 'auto')",
    )
    parser.add_argument(
        "--write-backfill",
        action="store_true",
        help="Write evaluation predictions to data/historical_backfill.csv",
    )
    parser.add_argument(
        "--backfill-path",
        default=str(DATA_DIR / "historical_backfill.csv"),
        help="Destination CSV for backfilled predictions",
    )
    parser.add_argument(
        "--backfill-source",
        default="backfill_initial",
        help="Source label used in drift monitoring for backfilled rows",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        min_games: str | int
        min_games = int(args.min_games_threshold)
    except ValueError:
        min_games = args.min_games_threshold

    games_df = load_completed_games()
    predictions, season_metrics, conference_metrics = evaluate_configuration(
        games_df,
        label=args.label,
        home_shift=args.home_shift,
        min_games_threshold=min_games,
    )

    write_outputs(args.label, predictions, season_metrics, conference_metrics)

    if args.write_backfill:
        params = load_model_params()
        metadata = params.get("metadata", {}) if params else {}
        model_version = metadata.get("tuner_commit") or metadata.get("model_version", "") or args.label
        timestamp_column = "date" if "date" in predictions.columns else None
        appended = log_predictions(
            predictions,
            source=args.backfill_source,
            model_name="AdaptivePredictor",
            model_version=model_version,
            config_version=_config_version,
            commit_hash=_commit_hash,
            log_path=Path(args.backfill_path),
            timestamp_column=timestamp_column,
        )
        print(
            f"✓ Backfill predictions written to {args.backfill_path} (rows now: {len(appended)})"
        )

    overall = overall_metrics(season_metrics)
    overall_row = overall[overall["label"] == args.label].iloc[0]
    print(
        f"\n[{args.label}] Overall accuracy {overall_row['accuracy']:.3f} | "
        f"home pick rate {overall_row['home_pick_rate']:.3f} | "
        f"home win rate {overall_row['home_win_rate']:.3f} | "
        f"games {int(overall_row['games'])}"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
