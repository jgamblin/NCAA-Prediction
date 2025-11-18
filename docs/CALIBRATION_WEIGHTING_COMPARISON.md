# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2368 | 0.2278 | +0.0090 |
| Expected Calibration Error (ECE) | 0.0595 | 0.0783 | -0.0189 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 5.0 | 5470.0 | 0.563 | 0.621 | 0.059 |
| 6.0 | 17.0 | 0.672 | 1.000 | 0.328 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 48.0 | 0.165 | 0.188 | 0.023 |
| 2.0 | 169.0 | 0.266 | 0.373 | 0.107 |
| 3.0 | 401.0 | 0.355 | 0.491 | 0.136 |
| 4.0 | 762.0 | 0.460 | 0.487 | 0.027 |
| 5.0 | 2447.0 | 0.557 | 0.618 | 0.061 |
| 6.0 | 1475.0 | 0.638 | 0.751 | 0.113 |
| 7.0 | 165.0 | 0.723 | 0.824 | 0.101 |
| 8.0 | 20.0 | 0.853 | 1.000 | 0.147 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.