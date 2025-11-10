# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2373 | 0.2292 | +0.0081 |
| Expected Calibration Error (ECE) | 0.0761 | 0.0876 | -0.0115 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 6.0 | 723.0 | 0.601 | 0.476 | 0.125 |
| 7.0 | 4716.0 | 0.716 | 0.647 | 0.069 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 10.0 | 0.177 | 0.500 | 0.323 |
| 2.0 | 105.0 | 0.264 | 0.276 | 0.012 |
| 3.0 | 378.0 | 0.358 | 0.455 | 0.097 |
| 4.0 | 928.0 | 0.460 | 0.474 | 0.015 |
| 5.0 | 2790.0 | 0.553 | 0.650 | 0.097 |
| 6.0 | 1161.0 | 0.633 | 0.756 | 0.123 |
| 7.0 | 63.0 | 0.716 | 0.841 | 0.125 |
| 8.0 | 4.0 | 0.806 | 1.000 | 0.194 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.