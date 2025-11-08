# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2703 | 0.2126 | +0.0577 |
| Expected Calibration Error (ECE) | 0.2192 | 0.0431 | +0.1760 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 7.0 | 702.0 | 0.762 | 0.483 | 0.279 |
| 8.0 | 5222.0 | 0.890 | 0.679 | 0.211 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 16.0 | 0.179 | 0.438 | 0.259 |
| 2.0 | 43.0 | 0.259 | 0.372 | 0.113 |
| 3.0 | 129.0 | 0.360 | 0.403 | 0.043 |
| 4.0 | 338.0 | 0.456 | 0.470 | 0.014 |
| 5.0 | 817.0 | 0.558 | 0.526 | 0.031 |
| 6.0 | 2429.0 | 0.660 | 0.620 | 0.040 |
| 7.0 | 1995.0 | 0.737 | 0.792 | 0.056 |
| 8.0 | 151.0 | 0.826 | 0.834 | 0.009 |
| 9.0 | 6.0 | 0.904 | 1.000 | 0.096 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.