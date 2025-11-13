"""Utilities for logging model predictions for drift monitoring.

Provides append helpers used by the daily pipeline and evaluation backfills so
`model_training.drift_monitor` can consume a consistent CSV shape.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

# Default live prediction log lives under repo data directory.
DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "prediction_log.csv"

# Columns drift monitor expects at minimum when joining with outcomes.
REQUIRED_COLUMNS = {"game_id", "home_win_probability"}
BASE_OUTPUT_COLUMNS: Sequence[str] = (
    "game_id",
    "date",
    "away_team",
    "home_team",
    "predicted_winner",
    "predicted_home_win",
    "home_win_probability",
    "away_win_probability",
    "confidence",
    "home_team_id",
    "away_team_id",
    "source",
    "prediction_timestamp",
    "model_type",
    "model_version",
    "config_version",
    "commit_hash",
)


def _ensure_isoformat(values: Iterable[object]) -> list[str]:
    """Convert timestamp-like values into ISO-8601 strings."""

    iso_strings: list[str] = []
    for value in values:
        if value is None or value == "":
            iso_strings.append(datetime.utcnow().replace(microsecond=0).isoformat())
            continue
        if isinstance(value, datetime):
            iso_strings.append(value.replace(microsecond=0).isoformat())
            continue
        try:
            parsed_series = pd.to_datetime([str(value)], errors="coerce")
        except Exception:
            parsed_series = None
        if parsed_series is None or parsed_series.isna().all():
            iso_strings.append(str(value))
        else:
            parsed_value = parsed_series[0]
            if pd.isna(parsed_value):
                iso_strings.append(str(value))
                continue
            parsed_dt = parsed_value.to_pydatetime()
            iso_strings.append(parsed_dt.replace(microsecond=0).isoformat())
    return iso_strings


def prepare_log_frame(
    predictions: pd.DataFrame,
    *,
    source: str,
    model_name: str,
    model_version: str,
    config_version: str,
    commit_hash: str,
    timestamp: str | datetime | None = None,
    timestamp_column: str | None = None,
) -> pd.DataFrame:
    """Project predictor output into a standardized logging frame.

    Parameters
    ----------
    predictions : pd.DataFrame
        Output from `AdaptivePredictor.predict`.
    source : str
        Identifier for the origin (e.g. "live", "backfill_initial").
    model_name : str
        Human-readable model label (e.g. "AdaptivePredictor").
    model_version : str
        Version label or commit hash associated with the model artifacts.
    config_version : str
        Configuration schema identifier injected by the pipeline.
    commit_hash : str
        Git commit hash recorded for traceability.
    timestamp : Optional[str | datetime]
        Optional override for a single timestamp applied to each row.
    timestamp_column : Optional[str]
        Column in `predictions` providing per-row timestamps (converted to ISO-8601).

    Returns
    -------
    pd.DataFrame
        New frame containing the standardized columns required for logging.
    """

    if not REQUIRED_COLUMNS.issubset(predictions.columns):
        missing = REQUIRED_COLUMNS - set(predictions.columns)
        raise ValueError(f"Predictions frame missing required columns: {sorted(missing)}")

    df = predictions.copy()

    # Determine timestamps for each row.
    if timestamp_column and timestamp_column in df.columns:
        values = df[timestamp_column].tolist()
    else:
        values = [timestamp] * len(df)
    df["prediction_timestamp"] = _ensure_isoformat(values)

    df["source"] = source
    df["model_type"] = model_name
    df["model_version"] = model_version or ""
    df["config_version"] = config_version
    df["commit_hash"] = commit_hash

    # Ensure optional columns exist so downstream reindex succeeds.
    for col in BASE_OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in {"home_team_id", "away_team_id"} else pd.NA

    # Preserve any additional diagnostic columns for future analysis.
    ordered_cols = list(dict.fromkeys([*BASE_OUTPUT_COLUMNS]))
    extra_cols = [c for c in df.columns if c not in ordered_cols]
    return df[ordered_cols + extra_cols]


def append_predictions(
    predictions: pd.DataFrame,
    *,
    source: str,
    model_name: str,
    model_version: str,
    config_version: str,
    commit_hash: str,
    log_path: Path | None = None,
    timestamp: str | datetime | None = None,
    timestamp_column: str | None = None,
) -> pd.DataFrame:
    """Append predictions to the specified log, de-duplicating on (game_id, source)."""

    path = log_path or DEFAULT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    log_frame = prepare_log_frame(
        predictions,
        source=source,
        model_name=model_name,
        model_version=model_version,
        config_version=config_version,
        commit_hash=commit_hash,
        timestamp=timestamp,
        timestamp_column=timestamp_column,
    )

    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, log_frame], ignore_index=True, sort=False)
    else:
        combined = log_frame

    combined = combined.sort_values("prediction_timestamp").drop_duplicates(
        ["game_id", "source"], keep="last"
    )
    combined.to_csv(path, index=False)
    return combined


__all__ = ["append_predictions", "prepare_log_frame", "DEFAULT_LOG_PATH"]
