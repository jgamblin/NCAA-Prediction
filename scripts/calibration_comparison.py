#!/usr/bin/env python3
"""Compare calibration (reliability) of weighted vs unweighted SimplePredictor.

Produces a markdown report at docs/CALIBRATION_WEIGHTING_COMPARISON.md with:
 - Bin-wise predicted vs empirical accuracy
 - Brier score comparison
 - ECE (expected calibration error)

Usage: python3 scripts/calibration_comparison.py
"""
from __future__ import annotations

import os
import pandas as pd
import numpy as np
from pathlib import Path

from model_training.simple_predictor import SimplePredictor  # type: ignore
from config.model_params_loader import load_model_params  # type: ignore

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
OUT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'CALIBRATION_WEIGHTING_COMPARISON.md'

N_BINS = 10

def season_weight(series: pd.Series) -> np.ndarray:  # type: ignore[return-type]
    # Same scheme documented in metadata
    seasons = sorted(series.unique(), reverse=True)
    mapping = {}
    for i, s in enumerate(seasons):
        if i == 0:
            mapping[s] = 10.0
        elif i == 1:
            mapping[s] = 3.0
        elif i == 2:
            mapping[s] = 1.5
        else:
            mapping[s] = 0.5 ** (i - 2)
    return series.map(mapping).values

def prepare_data() -> pd.DataFrame:
    norm_path = DATA_DIR / 'Completed_Games_Normalized.csv'
    raw_path = DATA_DIR / 'Completed_Games.csv'
    src = norm_path if norm_path.exists() else raw_path
    df = pd.read_csv(src)
    # Basic filters: need home_win column & drop rows with missing
    # Derive home_win if absent (final scores)
    if 'home_win' not in df.columns:
        if {'home_score','away_score'}.issubset(df.columns):
            df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
        else:
            raise RuntimeError('home_win column missing and cannot be derived (scores absent).')
    df = df.dropna(subset=['home_team','away_team'])
    # Ensure season present
    if 'season' not in df.columns:
        if 'Season' in df.columns:
            df['season'] = df['Season']
        else:
            df['season'] = 'unknown'
    return df

def train_and_predict(df: pd.DataFrame, weighted: bool) -> pd.DataFrame:
    # Shuffle and split
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    split = int(len(df)*0.2)
    test = df.iloc[:split].copy()
    train = df.iloc[split:].copy()
    predictor = SimplePredictor(
        n_estimators=100, max_depth=15, min_samples_split=20,
        min_games_threshold=0, calibrate=True, calibration_method='sigmoid'
    )
    if weighted and 'season' in train.columns:
        # initial fit
        predictor.fit(train)
        weights = season_weight(train['season'])
        try:
            avail = [c for c in predictor.feature_cols if c in train.columns]
            X = train[avail]
            y = train['home_win']
            predictor._raw_model.fit(X, y, sample_weight=weights)
            if predictor.calibrate:
                from sklearn.calibration import CalibratedClassifierCV
                # method already constrained ('sigmoid' or 'isotonic'); cast for type checker
                predictor.model = CalibratedClassifierCV(predictor._raw_model, method=str(predictor.calibration_method), cv=5)  # type: ignore[arg-type]
                predictor.model.fit(X, y)
        except Exception:
            # fallback to unweighted already fit
            pass
    else:
        predictor.fit(train)
    preds = predictor.predict(test)
    return preds.merge(test[['game_id','home_win']], on='game_id', how='left')

def reliability_curve(df: pd.DataFrame) -> pd.DataFrame:
    # Use home_win_probability as forecast & home_win as outcome
    probs = df['home_win_probability'].clip(0,1)
    outcomes = df['home_win'].astype(int)
    bins = np.linspace(0,1,N_BINS+1)
    bin_ids = np.digitize(probs, bins) - 1
    rows = []
    for b in range(N_BINS):
        mask = bin_ids==b
        if not mask.any():
            continue
        p_mean = probs[mask].mean()
        o_mean = outcomes[mask].mean()
        rows.append({
            'bin': b,
            'count': int(mask.sum()),
            'pred_mean': p_mean,
            'outcome_mean': o_mean,
            'abs_gap': abs(p_mean - o_mean)
        })
    return pd.DataFrame(rows)

def brier_score(df: pd.DataFrame) -> float:
    return float(np.mean((df['home_win_probability'].clip(0,1) - df['home_win'])**2))

def ece(curve: pd.DataFrame, total: int) -> float:
    return float(np.sum(curve['abs_gap'] * (curve['count']/total)))

def main():
    data = prepare_data()
    weighted_preds = train_and_predict(data, weighted=True)
    unweighted_preds = train_and_predict(data, weighted=False)
    wc = reliability_curve(weighted_preds)
    uc = reliability_curve(unweighted_preds)
    w_brier = brier_score(weighted_preds)
    u_brier = brier_score(unweighted_preds)
    w_ece = ece(wc, len(weighted_preds))
    u_ece = ece(uc, len(unweighted_preds))

    lines = ["# Calibration Comparison: Weighted vs Unweighted", "", "| Metric | Weighted | Unweighted | Delta (W-U) |", "|--------|---------:|-----------:|------------:|"]
    lines.append(f"| Brier Score | {w_brier:.4f} | {u_brier:.4f} | {(w_brier-u_brier):+.4f} |")
    lines.append(f"| Expected Calibration Error (ECE) | {w_ece:.4f} | {u_ece:.4f} | {(w_ece-u_ece):+.4f} |")
    lines.append("\n## Reliability Bins (Weighted)")
    lines.append("| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |")
    lines.append("|-----|------:|----------:|-------------:|--------:|")
    for _,r in wc.iterrows():
        lines.append(f"| {r['bin']} | {r['count']} | {r['pred_mean']:.3f} | {r['outcome_mean']:.3f} | {r['abs_gap']:.3f} |")
    lines.append("\n## Reliability Bins (Unweighted)")
    lines.append("| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |")
    lines.append("|-----|------:|----------:|-------------:|--------:|")
    for _,r in uc.iterrows():
        lines.append(f"| {r['bin']} | {r['count']} | {r['pred_mean']:.3f} | {r['outcome_mean']:.3f} | {r['abs_gap']:.3f} |")
    lines.append("\n### Notes")
    lines.append("- Brier score lower is better; ECE lower indicates closer calibration.")
    lines.append("- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.")
    OUT_PATH.write_text("\n".join(lines))
    print(f"✓ Calibration comparison written to {OUT_PATH}")

if __name__ == '__main__':
    main()
