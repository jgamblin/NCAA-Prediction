# Current Season Emphasis & Sample Weighting Rationale

We bias training toward the most recent season to capture up-to-date team strength, roster changes, and coaching impacts that a uniform historical average would dilute.

## Scheme
| Season recency | Weight |
|----------------|-------:|
| Current (most recent) | 10.0x |
| Previous | 3.0x |
| Two seasons ago | 1.5x |
| Older (k seasons back, k>=3) | 0.5^(k-2) |

This geometric decay preserves faint signal from older seasons while sharply emphasizing recent form.

## Benefits
- Faster adaptation to sudden team quality shifts (transfers, injuries, coaching changes).
- Higher discriminative power for early-season predictions when roster volatility is highest.
- Improves probability calibration at higher confidence bins (empirically small ECE reduction when recent season diverges from historical mean).

## Trade-offs
- Slight overfitting risk if early-season results are noisy.
- Historical patterns (e.g., consistent home court advantage for a team) carry reduced influence.

## Mitigations
- Minimum games threshold (`min_games_threshold`) prevents extremely small samples from dominating.
- Calibration layer (`sigmoid` via `CalibratedClassifierCV`) smooths raw probability output.
- Drift monitoring and anomaly detection highlight miscalibration or regime shifts.

## When to Revisit Weights
Reevaluate after:
1. Major rule changes affecting scoring.
2. Significant expansion/contraction in divisions/conferences.
3. Observed calibration degradation (ECE rising across recent runs).

## Implementation Notes
- Controlled via `use_sample_weights` flag in `config/model_params.json`.
- Automatically enforced after each tuning run (tuner sets the flag and documents scheme in metadata).
- Applied during pipeline training with a re-fit of the underlying RandomForest using `sample_weight` prior to optional calibration.

## Future Enhancements
- Dynamic weight optimization via Bayesian search over weight multipliers.
- Per-conference or per-team adaptive weighting based on recent volatility metrics.
- Ensemble blending of weighted and unweighted predictors for robustness.
